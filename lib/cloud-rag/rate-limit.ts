import { createHash } from "node:crypto";
import { cloudDb } from "./mongodb";

export async function enforceRateLimit(ip: string, limit = 10): Promise<boolean> {
  const db = await cloudDb();
  const collection = db.collection("portfolio_rate_limits");
  const bucket = Math.floor(Date.now() / 60_000);
  const key = createHash("sha256").update(`${ip}:${bucket}`).digest("hex");
  const expiresAt = new Date(Date.now() + 2 * 60_000);
  await collection.createIndex({ expiresAt: 1 }, { expireAfterSeconds: 0 });
  const result = await collection.findOneAndUpdate(
    { _id: key as never },
    { $inc: { count: 1 }, $setOnInsert: { expiresAt } },
    { upsert: true, returnDocument: "after" },
  );
  return Number(result?.count || 0) <= limit;
}
