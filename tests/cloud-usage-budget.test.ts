import { beforeEach, describe, expect, it, vi } from "vitest";

const collection = {
  createIndex: vi.fn(),
  findOneAndUpdate: vi.fn(),
};
const cloudDb = vi.fn();

vi.mock("../lib/cloud-rag/mongodb", () => ({ cloudDb }));

describe("cloud chat usage budgets", () => {
  beforeEach(() => {
    collection.createIndex.mockReset();
    collection.findOneAndUpdate.mockReset();
    cloudDb.mockReset();
    cloudDb.mockResolvedValue({ collection: vi.fn().mockReturnValue(collection) });
    process.env.CLOUD_DAILY_CHAT_LIMIT = "50";
    process.env.CLOUD_MONTHLY_CHAT_LIMIT = "1500";
  });

  it("allows requests under the daily and monthly chat limits", async () => {
    collection.findOneAndUpdate
      .mockResolvedValueOnce({ count: 50 })
      .mockResolvedValueOnce({ count: 1499 });

    const { enforceUsageBudget } = await import("../lib/cloud-rag/rate-limit");
    await expect(enforceUsageBudget(new Date("2026-09-02T12:00:00Z"))).resolves.toEqual({
      allowed: true,
    });

    expect(collection.findOneAndUpdate).toHaveBeenCalledWith(
      { _id: "chat:daily:2026-09-02" },
      expect.objectContaining({ $inc: { count: 1 } }),
      expect.objectContaining({ upsert: true, returnDocument: "after" }),
    );
    expect(collection.findOneAndUpdate).toHaveBeenCalledWith(
      { _id: "chat:monthly:2026-09" },
      expect.objectContaining({ $inc: { count: 1 } }),
      expect.objectContaining({ upsert: true, returnDocument: "after" }),
    );
  });

  it("blocks requests after the daily chat limit is exceeded", async () => {
    collection.findOneAndUpdate.mockResolvedValueOnce({ count: 51 });

    const { enforceUsageBudget } = await import("../lib/cloud-rag/rate-limit");
    await expect(enforceUsageBudget(new Date("2026-09-02T12:00:00Z"))).resolves.toEqual({
      allowed: false,
      scope: "daily",
      limit: 50,
      count: 51,
    });
  });
});
