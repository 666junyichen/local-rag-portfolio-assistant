import type { Document } from "mongodb";
import { cloudDb } from "./mongodb";
import { embedQuery } from "./gemini";
import type { RetrievalSettings, Source } from "./types";
import { planQuery, shouldRefuseWithoutRetrieval } from "./query-planning";

export function mapSource(doc: Document): Source | null {
  if (doc.visibility !== "public") return null;
  const metadata = doc.metadata || {};
  return {
    docId: String(doc.doc_id || ""),
    chunkId: String(doc.chunk_id || ""),
    title: String(doc.title || "Untitled"),
    category: String(metadata.category || "portfolio"),
    language: metadata.language === "zh" ? "zh" : "en",
    ...(doc.url ? { url: String(doc.url) } : {}),
    snippet: String(doc.raw_body || doc.body || "").slice(0, 1200),
    score: Number(doc.score || 0),
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

export async function retrieve(question: string, settings: RetrievalSettings): Promise<Source[]> {
  const db = await cloudDb();
  const collection = db.collection(process.env.CLOUD_COLLECTION_NAME || "portfolio_knowledge_public");
  const queryVector = await embedQuery(question);
  const candidateLimit = Math.min(Math.max(settings.topK * 10, 30), 50);
  const [vectorDocs, sparseDocs] = await Promise.all([collection.aggregate([
    { $vectorSearch: {
      index: process.env.CLOUD_VECTOR_INDEX_NAME || "vector_index_public",
      path: "embedding",
      queryVector,
      numCandidates: Math.max(settings.topK * 20, 100),
      limit: candidateLimit,
      filter: { visibility: "public" },
    } },
    { $project: { _id: 0, embedding: 0, score: { $meta: "vectorSearchScore" } } },
  ]).toArray(), collection.aggregate([
    { $search: {
      index: process.env.CLOUD_TEXT_INDEX_NAME || "text_index_public",
      compound: {
        must: [{ text: { query: question, path: ["title", "retrieval_text", "body", "metadata.category"] } }],
        filter: [{ equals: { path: "visibility", value: "public" } }],
      },
    } },
    { $limit: candidateLimit },
    { $project: { _id: 0, embedding: 0, bm25_score: { $meta: "searchScore" } } },
  ]).toArray().catch(() => [])]);
  const docs = reciprocalRankFusion(vectorDocs, sparseDocs);
  const maxBm25 = Math.max(0, ...docs.map((doc) => Number(doc.bm25_score || 0)));
  docs.forEach((doc) => {
    if (doc.score === undefined) doc.score = maxBm25 ? Number(doc.bm25_score || 0) / maxBm25 : 0;
  });
  return docs.map(mapSource).filter((source): source is Source => Boolean(source))
    .filter((source) => settings.scoreThreshold === null || source.score >= settings.scoreThreshold)
    .slice(0, settings.topK);
}

export async function retrieveForQuestion(question: string, settings: RetrievalSettings): Promise<Source[]> {
  if (shouldRefuseWithoutRetrieval(question)) return [];
  const plan = planQuery(question);
  if (plan.mode === "simple") return retrieve(question, settings);
  const expandedSettings = { ...settings, topK: Math.min(Math.max(settings.topK * 2, 5), 10) };
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
  return [...merged.values()]
    .sort((left, right) => right.agentQueryHits - left.agentQueryHits || (right.fusionScore || right.score) - (left.fusionScore || left.score))
    .slice(0, settings.topK);
}
