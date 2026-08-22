import { cloudDb } from "@/lib/cloud-rag/mongodb";

export const runtime = "nodejs";

export async function GET() {
  const status = { atlas: false, gemini: Boolean(process.env.GEMINI_API_KEY), vectorIndex: false, textIndex: false };
  try {
    const db = await cloudDb();
    await db.command({ ping: 1 });
    status.atlas = true;
    const collection = db.collection(process.env.CLOUD_COLLECTION_NAME || "portfolio_knowledge_public");
    const indexes = await collection.listSearchIndexes(process.env.CLOUD_VECTOR_INDEX_NAME || "vector_index_public").toArray() as Array<{ status?: string; queryable?: boolean }>;
    status.vectorIndex = indexes.some((index) => index.status === "READY" || index.queryable === true);
    const textIndexes = await collection.listSearchIndexes(process.env.CLOUD_TEXT_INDEX_NAME || "text_index_public").toArray() as Array<{ status?: string; queryable?: boolean }>;
    status.textIndex = textIndexes.some((index) => index.status === "READY" || index.queryable === true);
  } catch {
    // Health output deliberately contains no configuration values.
  }
  const ready = status.atlas && status.gemini && status.vectorIndex;
  return Response.json({
    ...status,
    ready,
    retrievalCapabilities: {
      vector: status.vectorIndex,
      bm25: status.textIndex,
      hybrid: status.textIndex,
      adaptive: true,
      rerank: false,
    },
  }, { status: ready ? 200 : 503 });
}
