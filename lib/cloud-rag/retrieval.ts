import type { Collection, Document } from "mongodb";
import { cloudDb } from "./mongodb";
import { embedQuery } from "./gemini";
import type { AnswerIntent, RetrievalResult, RetrievalSettings, Source } from "./types";
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

export function selectParentContext(candidates: Source[], intent: AnswerIntent, topK: number): Source[] {
  const selected: Source[] = [];
  const seenParents = new Set<string>();
  const seenSemanticGroups = new Set<string>();
  const limit = selectedContextLimit(intent, topK);

  for (const source of [...candidates].sort((left, right) => sourceRank(right) - sourceRank(left))) {
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
  queryVector: number[],
  spaceId: string,
  settings: RetrievalSettings,
): Promise<Source[]> {
  const candidateLimit = Math.min(Math.max(settings.topK * 10, 30), 50);
  const [vectorDocs, sparseDocs] = await Promise.all([
    collection.aggregate(buildVectorPipeline(queryVector, settings.topK, candidateLimit, [spaceId])).toArray(),
    collection.aggregate([
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
    ]).toArray().catch(() => []),
  ]);
  const docs = reciprocalRankFusion(vectorDocs, sparseDocs);
  const maxBm25 = Math.max(0, ...docs.map((doc) => Number(doc.bm25_score || 0)));
  docs.forEach((doc) => {
    doc.space_id = doc.space_id || spaceId;
    if (doc.score === undefined) doc.score = maxBm25 ? Number(doc.bm25_score || 0) / maxBm25 : 0;
  });
  return docs.map(mapSource).filter((source): source is Source => Boolean(source));
}

export async function retrieve(question: string, settings: RetrievalSettings): Promise<Source[]> {
  const db = await cloudDb();
  const collection = db.collection(process.env.CLOUD_COLLECTION_NAME || "portfolio_knowledge_public");
  const queryVector = await embedQuery(question);
  const spaceIds = normalizeSpaceIds(settings.spaceIds);
  const [groups, names] = await Promise.all([
    Promise.all(spaceIds.map((spaceId) => retrieveSpaceCandidates(collection, question, queryVector, spaceId, settings))),
    spaceNameMap(spaceIds),
  ]);
  groups.flat().forEach((source) => { source.spaceName = names.get(source.spaceId) || source.spaceName || source.spaceId; });
  return mergeSpaceCandidates(groups, settings.topK, settings.scoreThreshold);
}

export async function retrieveForQuestion(question: string, settings: RetrievalSettings): Promise<RetrievalResult> {
  const intent = classifyAnswerIntent(question);
  if (shouldRefuseWithoutRetrieval(question)) return { candidates: [], selectedContext: [], intent };
  const plan = planQuery(question);
  const expandedSettings = { ...settings, topK: candidateLimit(intent, settings.topK) };
  if (plan.mode === "simple") {
    const candidates = await retrieve(question, expandedSettings);
    return { candidates, selectedContext: selectParentContext(candidates, intent, settings.topK), intent };
  }
  const groups = await Promise.all(plan.subqueries.map((subquery) => retrieve(subquery, expandedSettings)));
  const merged = new Map<string, Source & { agentQueryHits: number }>();
  groups.flat().forEach((source) => {
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
  return { candidates, selectedContext: selectParentContext(candidates, intent, settings.topK), intent };
}
