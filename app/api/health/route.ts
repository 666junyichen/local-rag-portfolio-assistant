import { cloudDb } from "@/lib/cloud-rag/mongodb";

export const runtime = "nodejs";

export async function GET() {
  const status = { atlas: false, gemini: Boolean(process.env.GEMINI_API_KEY), vectorIndex: false };
  try {
    const db = await cloudDb();
    await db.command({ ping: 1 });
    status.atlas = true;
    const collection = db.collection(process.env.CLOUD_COLLECTION_NAME || "portfolio_knowledge_public");
    const indexes = await collection.listSearchIndexes(process.env.CLOUD_VECTOR_INDEX_NAME || "vector_index_public").toArray() as Array<{ status?: string; queryable?: boolean }>;
    status.vectorIndex = indexes.some((index) => index.status === "READY" || index.queryable === true);
  } catch {
    // Health output deliberately contains no configuration values.
  }
  return Response.json(status, { status: status.atlas && status.gemini && status.vectorIndex ? 200 : 503 });
}
