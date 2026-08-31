import type { Collection, Document } from "mongodb";
import { cloudDb } from "./mongodb";
import { embedQuery } from "./gemini";
import type { AnswerIntent, RetrievalDiagnostics, RetrievalMode, RetrievalResult, RetrievalSettings, Source } from "./types";
import { planQuery, shouldRefuseWithoutRetrieval } from "./query-planning";
import { classifyAnswerIntent } from "./prompt";
import { DEFAULT_SPACE_ID, normalizeSpaceIds, spaceFilter } from "./spaces";
import { spaceNameMap } from "../cloud-publish/spaces";

export function mapSource(doc: Document): Source | null {
  if (doc.visibility !== "public") return null;
  if (doc.validity_status && doc.validity_status !== "active") return null;
  const metadata = doc.metadata || {};
  const parentChunkId = doc.parent_chunk_id || metadata.parent_chunk_id;
  const semanticGroupId = doc.semantic_group_id || metadata.semantic_group_id;
  const sectionType = doc.section_type || metadata.section_type;
  const entityTitle = doc.entity_title || metadata.entity_title;
  return {
    docId: String(doc.doc_id || ""),
    chunkId: String(doc.chunk_id || ""),
    title: String(doc.title || "Untitled"),
    category: String(metadata.category || "portfolio"),
    language: metadata.language === "zh" ? "zh" : "en",
    ...(doc.url || doc.source_url ? { url: String(doc.url || doc.source_url) } : {}),
    snippet: String(doc.parent_body || doc.raw_body || doc.body || "").slice(0, 1200),
    matchedSnippet: String(doc.child_body || doc.retrieval_text || doc.raw_body || doc.body || "").slice(0, 1200),
    score: Number(doc.score || 0),
    spaceId: String(doc.space_id || DEFAULT_SPACE_ID),
    spaceName: String(doc.space_name || doc.metadata?.space_name || "Portfolio"),
    ...(parentChunkId ? { parentChunkId: String(parentChunkId) } : {}),
    ...(semanticGroupId ? { semanticGroupId: String(semanticGroupId) } : {}),
    ...(sectionType ? { sectionType: String(sectionType) } : {}),
    ...(entityTitle ? { entityTitle: String(entityTitle) } : {}),
    ...(Array.isArray(doc.retrieval_channels) ? { retrievalChannels: doc.retrieval_channels } : {}),
    ...(doc.vector_rank ? { vectorRank: Number(doc.vector_rank) } : {}),
    ...(doc.bm25_rank ? { bm25Rank: Number(doc.bm25_rank) } : {}),
    ...(doc.fusion_score ? { fusionScore: Number(doc.fusion_score) } : {}),
    ...(doc.retrieval_path ? { retrievalPath: doc.retrieval_path } : {}),
    ...(doc.fallback_reason ? { fallbackReason: String(doc.fallback_reason) } : {}),
  };
}

export function reciprocalRankFusion(vectorRows: Document[], sparseRows: Document[], rrfK = 60, vectorWeight = 2.0, sparseWeight = 0.7): Document[] {
  const fused = new Map<string, Document>();
  for (const [channel, rows, weight] of [["vector", vectorRows, vectorWeight], ["bm25", sparseRows, sparseWeight]] as const) {
    rows.forEach((raw, index) => {
      const key = String(raw.chunk_id || raw.doc_id || raw._id || "");
      if (!key) return;
      const item = fused.get(key) || { ...raw, retrieval_channels: [], fusion_score: 0 };
      for (const [name, value] of Object.entries(raw)) if (item[name] === undefined) item[name] = value;
      item[`${channel}_rank`] = index + 1;
      if (!item.retrieval_channels.includes(channel)) item.retrieval_channels.push(channel);
      item.fusion_score += weight / (rrfK + index + 1);
      fused.set(key, item);
    });
  }
  return [...fused.values()].sort((left, right) => Number(right.fusion_score) - Number(left.fusion_score));
}

export function buildVectorPipeline(queryVector: number[], topK: number, candidateLimit: number, rawSpaceIds?: string[]): Document[] {
  const selectedSpaceFilter = spaceFilter(rawSpaceIds);
  return [
    { $vectorSearch: {
      index: process.env.CLOUD_VECTOR_INDEX_NAME || "vector_index_public",
      path: "embedding",
      queryVector,
      numCandidates: Math.max(topK * 20, 100),
      limit: candidateLimit,
      filter: { visibility: "public", ...selectedSpaceFilter },
    } },
    { $match: { $or: [{ validity_status: "active" }, { validity_status: { $exists: false } }] } },
    { $project: { _id: 0, embedding: 0, score: { $meta: "vectorSearchScore" } } },
  ];
}

const sourceRank = (source: Source) => source.fusionScore || source.score;

function selectedContextLimit(intent: AnswerIntent, topK: number): number {
  if (intent === "exhaustive") return 12;
  if (intent === "ranked") return Math.min(5, Math.max(3, topK));
  return topK;
}

function candidateLimit(intent: AnswerIntent, topK: number): number {
  if (intent === "exhaustive") return 50;
  if (intent === "ranked") return 20;
  return Math.min(Math.max(topK * 4, 10), 40);
}

const projectQuestion = (question: string) => /项目|專案|projects?/iu.test(question);
const TEXT_INDEX_UNAVAILABLE = "Atlas Search text index is unavailable; using Vector Search.";
const ADAPTIVE_TEXT_INDEX_UNAVAILABLE = "Atlas Search text index is unavailable; adaptive used Vector Search.";
const CLOUD_RERANK_UNAVAILABLE = "Cloud reranker is unavailable; applied Hybrid without reranking.";
const VECTOR_EMBEDDING_UNAVAILABLE = "Gemini embedding is unavailable; using Atlas BM25 text search.";
const VECTOR_SEARCH_UNAVAILABLE = "Atlas Vector Search is unavailable; using Atlas BM25 text search.";
const NO_CLOUD_RETRIEVAL_PATH = "No cloud retrieval path is available because Gemini embedding and Atlas Search text index are unavailable.";

type SparseResult = {
  rows: Document[];
  available: boolean;
};

type VectorResult = {
  rows: Document[];
  available: boolean;
  fallbackReason?: string;
};

type RetrievalPathInput = {
  requestedMode?: RetrievalMode;
  question: string;
  vectorRows: Document[];
  vectorAvailable?: boolean;
  vectorFallbackReason?: string;
  textSearchAvailable: boolean;
};

function precisionReasons(question: string, vectorRows: Document[]): string[] {
  const reasons: string[] = [];
  if (planQuery(question).mode === "complex") reasons.push("complex-query");
  const scores = vectorRows
    .map((row) => Number(row.score || row.rank_score || 0))
    .sort((left, right) => right - left);
  if (!scores.length || scores[0] < 0.45 || (scores.length > 1 && scores[0] - scores[1] < 0.02)) {
    reasons.push("low-confidence");
  }
  return [...new Set(reasons)];
}

export function chooseCloudRetrievalPath(input: RetrievalPathInput): RetrievalDiagnostics {
  const requestedMode = input.requestedMode || "vector";
  const vectorAvailable = input.vectorAvailable !== false;
  const vectorFallbackReason = input.vectorFallbackReason || VECTOR_EMBEDDING_UNAVAILABLE;
  const capabilities = {
    vector: vectorAvailable,
    bm25: input.textSearchAvailable,
    hybrid: vectorAvailable && input.textSearchAvailable,
    rerank: false,
    adaptive: true,
  };
  const rerankerReasons = requestedMode === "adaptive" && vectorAvailable
    ? precisionReasons(input.question, input.vectorRows)
    : [];
  let appliedMode: RetrievalMode = requestedMode;
  let fallbackReason: string | undefined;

  if (!vectorAvailable) {
    if (input.textSearchAvailable) {
      appliedMode = "bm25";
      fallbackReason = requestedMode === "bm25" ? undefined : vectorFallbackReason;
    } else {
      appliedMode = requestedMode === "bm25" ? "bm25" : "vector";
      fallbackReason = NO_CLOUD_RETRIEVAL_PATH;
    }
  } else if (requestedMode === "vector") {
    appliedMode = "vector";
  } else if (requestedMode === "bm25") {
    appliedMode = input.textSearchAvailable ? "bm25" : "vector";
    if (!input.textSearchAvailable) fallbackReason = TEXT_INDEX_UNAVAILABLE;
  } else if (requestedMode === "hybrid") {
    appliedMode = input.textSearchAvailable ? "hybrid" : "vector";
    if (!input.textSearchAvailable) fallbackReason = TEXT_INDEX_UNAVAILABLE;
  } else if (requestedMode === "hybrid-rerank") {
    appliedMode = input.textSearchAvailable ? "hybrid" : "vector";
    fallbackReason = input.textSearchAvailable
      ? CLOUD_RERANK_UNAVAILABLE
      : "Atlas Search text index is unavailable and cloud reranker is unavailable; using Vector Search.";
  } else if (requestedMode === "adaptive") {
    if (!rerankerReasons.length) {
      appliedMode = "vector";
    } else if (input.textSearchAvailable) {
      appliedMode = "hybrid";
      fallbackReason = CLOUD_RERANK_UNAVAILABLE;
    } else {
      appliedMode = "vector";
      fallbackReason = ADAPTIVE_TEXT_INDEX_UNAVAILABLE;
    }
  }

  return {
    requestedMode,
    appliedMode,
    retrievalPath: appliedMode,
    capabilities,
    ...(fallbackReason ? { fallbackReason } : {}),
    rerankerTriggered: false,
    rerankerReasons,
    vectorCandidates: input.vectorRows.length,
  };
}

function annotateVectorRows(rows: Document[], diagnostics: RetrievalDiagnostics): Document[] {
  return rows.map((row, index) => ({
    ...row,
    retrieval_channels: ["vector"],
    vector_rank: index + 1,
    retrieval_path: diagnostics.retrievalPath,
    ...(diagnostics.fallbackReason ? { fallback_reason: diagnostics.fallbackReason } : {}),
  }));
}

function annotateSparseRows(rows: Document[], diagnostics: RetrievalDiagnostics): Document[] {
  const maxBm25 = Math.max(0, ...rows.map((row) => Number(row.bm25_score || 0)));
  return rows.map((row, index) => ({
    ...row,
    bm25_rank: index + 1,
    retrieval_channels: ["bm25"],
    score: maxBm25 ? Number(row.bm25_score || 0) / maxBm25 : 0,
    retrieval_path: diagnostics.retrievalPath,
    ...(diagnostics.fallbackReason ? { fallback_reason: diagnostics.fallbackReason } : {}),
  }));
}

function annotateHybridRows(rows: Document[], diagnostics: RetrievalDiagnostics): Document[] {
  const maxBm25 = Math.max(0, ...rows.map((row) => Number(row.bm25_score || 0)));
  return rows.map((row) => ({
    ...row,
    retrieval_path: diagnostics.retrievalPath,
    ...(row.score === undefined ? { score: maxBm25 ? Number(row.bm25_score || 0) / maxBm25 : 0 } : {}),
    ...(diagnostics.fallbackReason ? { fallback_reason: diagnostics.fallbackReason } : {}),
  }));
}

export function selectParentContext(candidates: Source[], intent: AnswerIntent, topK: number, question = ""): Source[] {
  const selected: Source[] = [];
  const seenParents = new Set<string>();
  const seenSemanticGroups = new Set<string>();
  const limit = selectedContextLimit(intent, topK);

  const rankedCandidates = [...candidates].sort((left, right) => sourceRank(right) - sourceRank(left));
  const projectCandidates = rankedCandidates.filter((source) => source.sectionType === "project");
  const scopedCandidates = projectQuestion(question) && intent !== "fact" && projectCandidates.length
    ? projectCandidates
    : rankedCandidates;

  for (const source of scopedCandidates) {
    const scope = `${source.spaceId}:${source.docId}`;
    const parentKey = `${scope}:${source.parentChunkId || source.chunkId}`;
    const semanticKey = source.semanticGroupId ? `${scope}:${source.semanticGroupId}` : "";
    if (seenParents.has(parentKey) || (semanticKey && seenSemanticGroups.has(semanticKey))) continue;
    seenParents.add(parentKey);
    if (semanticKey) seenSemanticGroups.add(semanticKey);
    selected.push(source);
    if (selected.length >= limit) break;
  }
  return selected;
}

export function mergeSpaceCandidates(
  groups: Source[][],
  topK: number,
  scoreThreshold: number | null,
): Source[] {
  const eligible = groups.map((group) => group
    .filter((source) => scoreThreshold === null || source.score >= scoreThreshold)
    .sort((left, right) => sourceRank(right) - sourceRank(left)));
  const selected: Source[] = [];
  const seen = new Set<string>();
  const add = (source: Source) => {
    const key = source.chunkId || source.docId;
    if (seen.has(key) || selected.length >= topK) return;
    seen.add(key);
    selected.push(source);
  };
  for (const group of eligible) if (group[0]) add(group[0]);
  const remaining = eligible.flatMap((group) => group.slice(1))
    .sort((left, right) => sourceRank(right) - sourceRank(left));
  for (const source of remaining) add(source);
  return selected;
}

async function retrieveSpaceCandidates(
  collection: Collection<Document>,
  question: string,
  queryVector: number[] | null,
  vectorFallbackReason: string | undefined,
  spaceId: string,
  settings: RetrievalSettings,
): Promise<{ sources: Source[]; diagnostics: RetrievalDiagnostics }> {
  const candidateLimit = Math.min(Math.max(settings.topK * 10, 30), 50);
  const searchVector = async (): Promise<VectorResult> => {
    if (!queryVector) {
      return { rows: [], available: !vectorFallbackReason, ...(vectorFallbackReason ? { fallbackReason: vectorFallbackReason } : {}) };
    }
    try {
      const rows = await collection.aggregate(buildVectorPipeline(queryVector, settings.topK, candidateLimit, [spaceId])).toArray();
      return { rows, available: true };
    } catch {
      return { rows: [], available: false, fallbackReason: VECTOR_SEARCH_UNAVAILABLE };
    }
  };
  const searchSparse = async (): Promise<SparseResult> => {
    try {
      const rows = await collection.aggregate([
        { $search: {
          index: process.env.CLOUD_TEXT_INDEX_NAME || "text_index_public",
          compound: {
            must: [{ text: { query: question, path: ["title", "retrieval_text", "body", "metadata.category"] } }],
            filter: [
              { equals: { path: "visibility", value: "public" } },
              { equals: { path: "space_id", value: spaceId } },
            ],
          },
        } },
        { $limit: candidateLimit },
        { $project: { _id: 0, embedding: 0, bm25_score: { $meta: "searchScore" } } },
      ]).toArray();
      return { rows, available: true };
    } catch {
      return { rows: [], available: false };
    }
  };
  const [vector, sparse] = await Promise.all([
    searchVector(),
    searchSparse(),
  ]);
  const diagnostics = {
    ...chooseCloudRetrievalPath({
      requestedMode: settings.retrievalMode,
      question,
      vectorRows: vector.rows,
      vectorAvailable: vector.available,
      vectorFallbackReason: vector.fallbackReason,
      textSearchAvailable: sparse.available,
    }),
    bm25Candidates: sparse.rows.length,
  };
  let docs: Document[];
  if (diagnostics.appliedMode === "bm25") {
    docs = annotateSparseRows(sparse.rows, diagnostics);
  } else if (diagnostics.appliedMode === "hybrid" || diagnostics.appliedMode === "hybrid-rerank") {
    docs = annotateHybridRows(reciprocalRankFusion(vector.rows, sparse.rows), diagnostics);
  } else {
    docs = annotateVectorRows(vector.rows, diagnostics);
  }
  docs.forEach((doc) => { doc.space_id = doc.space_id || spaceId; });
  return {
    sources: docs.map(mapSource).filter((source): source is Source => Boolean(source)),
    diagnostics,
  };
}

type RetrievalRun = {
  sources: Source[];
  diagnostics: RetrievalDiagnostics;
};

function mergeDiagnostics(runs: RetrievalRun[], requestedMode: RetrievalMode): RetrievalDiagnostics {
  const fallbackReason = runs.map((run) => run.diagnostics.fallbackReason).find(Boolean);
  const rerankerReasons = [...new Set(runs.flatMap((run) => run.diagnostics.rerankerReasons || []))];
  const appliedMode = (
    runs.some((run) => run.diagnostics.appliedMode === "hybrid")
      ? "hybrid"
      : runs.some((run) => run.diagnostics.appliedMode === "bm25")
        ? "bm25"
        : runs[0]?.diagnostics.appliedMode || "vector"
  ) as RetrievalMode;
  return {
    requestedMode,
    appliedMode,
    retrievalPath: appliedMode,
    capabilities: {
      vector: runs.every((run) => run.diagnostics.capabilities.vector),
      bm25: runs.every((run) => run.diagnostics.capabilities.bm25),
      hybrid: runs.every((run) => run.diagnostics.capabilities.hybrid),
      rerank: false,
      adaptive: true,
    },
    ...(fallbackReason ? { fallbackReason } : {}),
    rerankerTriggered: false,
    rerankerReasons,
    vectorCandidates: runs.reduce((total, run) => total + (run.diagnostics.vectorCandidates || 0), 0),
    bm25Candidates: runs.reduce((total, run) => total + (run.diagnostics.bm25Candidates || 0), 0),
  };
}

async function retrieveWithDiagnostics(question: string, settings: RetrievalSettings): Promise<RetrievalRun> {
  const db = await cloudDb();
  const collection = db.collection(process.env.CLOUD_COLLECTION_NAME || "portfolio_knowledge_public");
  let queryVector: number[] | null = null;
  let vectorFallbackReason: string | undefined;
  if ((settings.retrievalMode || "vector") !== "bm25") {
    try {
      queryVector = await embedQuery(question);
    } catch (error) {
      console.warn("Cloud RAG embedding unavailable; falling back to Atlas BM25 when available", error instanceof Error ? error.message : error);
      vectorFallbackReason = VECTOR_EMBEDDING_UNAVAILABLE;
    }
  }
  const spaceIds = normalizeSpaceIds(settings.spaceIds);
  const [runs, names] = await Promise.all([
    Promise.all(spaceIds.map((spaceId) => retrieveSpaceCandidates(collection, question, queryVector, vectorFallbackReason, spaceId, settings))),
    spaceNameMap(spaceIds),
  ]);
  const groups = runs.map((run) => run.sources);
  groups.flat().forEach((source) => { source.spaceName = names.get(source.spaceId) || source.spaceName || source.spaceId; });
  return {
    sources: mergeSpaceCandidates(groups, settings.topK, settings.scoreThreshold),
    diagnostics: mergeDiagnostics(runs, settings.retrievalMode || "vector"),
  };
}

export async function retrieve(question: string, settings: RetrievalSettings): Promise<Source[]> {
  return (await retrieveWithDiagnostics(question, settings)).sources;
}

export async function retrieveForQuestion(question: string, settings: RetrievalSettings): Promise<RetrievalResult> {
  const intent = classifyAnswerIntent(question);
  if (shouldRefuseWithoutRetrieval(question)) {
    const requestedMode = settings.retrievalMode || "vector";
    return {
      candidates: [],
      selectedContext: [],
      intent,
      retrieval: {
        requestedMode,
        appliedMode: "vector",
        retrievalPath: "vector",
        capabilities: { vector: true, bm25: false, hybrid: false, rerank: false, adaptive: true },
        fallbackReason: "Question is outside the public retrieval boundary.",
        rerankerTriggered: false,
        rerankerReasons: [],
        vectorCandidates: 0,
        bm25Candidates: 0,
      },
    };
  }
  const plan = planQuery(question);
  const expandedSettings = { ...settings, topK: candidateLimit(intent, settings.topK) };
  if (plan.mode === "simple") {
    const run = await retrieveWithDiagnostics(question, expandedSettings);
    return {
      candidates: run.sources,
      selectedContext: selectParentContext(run.sources, intent, settings.topK, question),
      intent,
      retrieval: run.diagnostics,
    };
  }
  const runs = await Promise.all(plan.subqueries.map((subquery) => retrieveWithDiagnostics(subquery, expandedSettings)));
  const merged = new Map<string, Source & { agentQueryHits: number }>();
  runs.flatMap((run) => run.sources).forEach((source) => {
    const key = source.chunkId || source.docId;
    const existing = merged.get(key);
    if (!existing) merged.set(key, { ...source, agentQueryHits: 1 });
    else {
      existing.agentQueryHits += 1;
      existing.score = Math.max(existing.score, source.score);
      existing.fusionScore = Math.max(existing.fusionScore || 0, source.fusionScore || 0);
    }
  });
  const candidates = [...merged.values()]
    .sort((left, right) => right.agentQueryHits - left.agentQueryHits || (right.fusionScore || right.score) - (left.fusionScore || left.score))
    .slice(0, candidateLimit(intent, settings.topK));
  return {
    candidates,
    selectedContext: selectParentContext(candidates, intent, settings.topK, question),
    intent,
    retrieval: mergeDiagnostics(runs, settings.retrievalMode || "vector"),
  };
}
