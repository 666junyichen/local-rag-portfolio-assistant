import { cloudDb } from "@/lib/cloud-rag/mongodb";

export const runtime = "nodejs";

type SearchIndexStatus = { status?: string; state?: string; queryable?: boolean };

function isSearchIndexReady(index: SearchIndexStatus): boolean {
  const status = String(index.status || index.state || "").toUpperCase();
  return index.queryable === true || status === "READY" || status === "QUERYABLE" || status === "ACTIVE";
}

async function canQueryTextIndex(collection: ReturnType<Awaited<ReturnType<typeof cloudDb>>["collection"]>, textIndexName: string): Promise<boolean> {
  try {
    await collection.aggregate([
      { $search: { index: textIndexName, text: { query: "health", path: ["title", "retrieval_text", "body", "metadata.category"] } } },
      { $limit: 1 },
      { $project: { _id: 0 } },
    ]).toArray();
    return true;
  } catch {
    return false;
  }
}

export async function GET() {
  const status = { atlas: false, gemini: Boolean(process.env.GEMINI_API_KEY), vectorIndex: false, textIndex: false };
  try {
    const db = await cloudDb();
    await db.command({ ping: 1 });
    status.atlas = true;
    const collection = db.collection(process.env.CLOUD_COLLECTION_NAME || "portfolio_knowledge_public");
    const vectorIndexName = process.env.CLOUD_VECTOR_INDEX_NAME || "vector_index_public";
    const textIndexName = process.env.CLOUD_TEXT_INDEX_NAME || "text_index_public";
    const indexes = await collection.listSearchIndexes(vectorIndexName).toArray() as SearchIndexStatus[];
    status.vectorIndex = indexes.some(isSearchIndexReady);
    const textIndexes = await collection.listSearchIndexes(textIndexName).toArray() as SearchIndexStatus[];
    status.textIndex = textIndexes.some(isSearchIndexReady);
    if (!status.textIndex) status.textIndex = await canQueryTextIndex(collection, textIndexName);
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
