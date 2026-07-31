import { MongoClient } from "mongodb";

let clientPromise: Promise<MongoClient> | undefined;

export function getMongoClient(): Promise<MongoClient> {
  const uri = process.env.MONGODB_URI;
  if (!uri) throw new Error("MONGODB_URI is not configured");
  if (!clientPromise) clientPromise = new MongoClient(uri, { serverSelectionTimeoutMS: 8000 }).connect();
  return clientPromise;
}

export async function cloudDb() {
  const client = await getMongoClient();
  return client.db(process.env.CLOUD_DB_NAME || "portfolio_rag");
}
