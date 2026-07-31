import type { Document } from "mongodb";
import { cloudDb } from "./mongodb";
import { embedQuery } from "./gemini";
import type { RetrievalSettings, Source } from "./types";

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
    snippet: String(doc.body || "").slice(0, 1200),
    score: Number(doc.score || 0),
  };
}

export async function retrieve(question: string, settings: RetrievalSettings): Promise<Source[]> {
  const db = await cloudDb();
  const collection = db.collection(process.env.CLOUD_COLLECTION_NAME || "portfolio_knowledge_public");
  const queryVector = await embedQuery(question);
  const docs = await collection.aggregate([
    { $vectorSearch: {
      index: process.env.CLOUD_VECTOR_INDEX_NAME || "vector_index_public",
      path: "embedding",
      queryVector,
      numCandidates: Math.max(settings.topK * 20, 100),
      limit: Math.min(settings.topK * 3, 30),
      filter: { visibility: "public" },
    } },
    { $project: { _id: 0, embedding: 0, score: { $meta: "vectorSearchScore" } } },
  ]).toArray();
  return docs.map(mapSource).filter((source): source is Source => Boolean(source))
    .filter((source) => settings.scoreThreshold === null || source.score >= settings.scoreThreshold)
    .slice(0, settings.topK);
}
