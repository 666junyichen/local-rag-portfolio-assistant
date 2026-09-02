import { createHash } from "node:crypto";
import { cloudDb } from "./mongodb";

type UsageBudgetScope = "daily" | "monthly";
type UsageBudgetResult = {
  allowed: boolean;
  scope?: UsageBudgetScope;
  limit?: number;
  count?: number;
};

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

function limitFromEnv(name: string, fallback: number): number {
  const value = Number(process.env[name] || fallback);
  if (!Number.isFinite(value) || value <= 0) return 0;
  return Math.floor(value);
}

function usageBuckets(now: Date) {
  const day = now.toISOString().slice(0, 10);
  const month = day.slice(0, 7);
  return [
    {
      scope: "daily" as const,
      key: `chat:daily:${day}`,
      limit: limitFromEnv("CLOUD_DAILY_CHAT_LIMIT", 50),
      expiresAt: new Date(now.getTime() + 3 * 24 * 60 * 60 * 1000),
    },
    {
      scope: "monthly" as const,
      key: `chat:monthly:${month}`,
      limit: limitFromEnv("CLOUD_MONTHLY_CHAT_LIMIT", 1500),
      expiresAt: new Date(now.getTime() + 40 * 24 * 60 * 60 * 1000),
    },
  ];
}

export async function enforceUsageBudget(now = new Date()): Promise<UsageBudgetResult> {
  const buckets = usageBuckets(now).filter((bucket) => bucket.limit > 0);
  if (!buckets.length) return { allowed: true };
  const db = await cloudDb();
  const collection = db.collection("portfolio_usage_limits");
  await collection.createIndex({ expiresAt: 1 }, { expireAfterSeconds: 0 });
  for (const bucket of buckets) {
    const result = await collection.findOneAndUpdate(
      { _id: bucket.key as never },
      {
        $inc: { count: 1 },
        $setOnInsert: { scope: bucket.scope, expiresAt: bucket.expiresAt, createdAt: now },
        $set: { updatedAt: now },
      },
      { upsert: true, returnDocument: "after" },
    );
    const count = Number(result?.count || 0);
    if (count > bucket.limit) {
      return { allowed: false, scope: bucket.scope, limit: bucket.limit, count };
    }
  }
  return { allowed: true };
}
