import { beforeEach, describe, expect, it, vi } from "vitest";

const listSearchIndexes = vi.fn();
const aggregate = vi.fn();
const cloudDb = vi.fn();

vi.mock("@/lib/cloud-rag/mongodb", () => ({ cloudDb }));
vi.mock("@/lib/cloud-rag/ai-providers", () => ({
  chatProviderOrder: () => (process.env.OPENAI_API_KEY ? ["openai"] : []),
  embeddingProviderOrder: () => (process.env.OPENAI_API_KEY ? ["openai"] : []),
}));

describe("cloud health route", () => {
  beforeEach(() => {
    process.env.OPENAI_API_KEY = "test-openai";
    delete process.env.GEMINI_API_KEY;
    process.env.CLOUD_CHAT_PROVIDER = "openai";
    process.env.CLOUD_EMBEDDING_PROVIDER = "openai";
    listSearchIndexes.mockReset();
    aggregate.mockReset();
    cloudDb.mockReset();
    cloudDb.mockResolvedValue({
      command: vi.fn().mockResolvedValue({ ok: 1 }),
      collection: vi.fn().mockReturnValue({ aggregate, listSearchIndexes }),
    });
  });

  it("treats Atlas Search text index as optional when vector retrieval is ready", async () => {
    listSearchIndexes.mockImplementation((name: string) => ({
      toArray: async () => (name === "vector_index_public" ? [{ queryable: true }] : []),
    }));

    const { GET } = await import("../app/api/health/route");
    const response = await GET();
    const payload = await response.json();

    expect(response.status).toBe(200);
    expect(payload.ready).toBe(true);
    expect(payload.openai).toBe(true);
    expect(payload.gemini).toBe(false);
    expect(payload.providers).toMatchObject({
      chat: ["openai"],
      embedding: ["openai"],
    });
    expect(payload.textIndex).toBe(false);
    expect(payload.retrievalCapabilities).toMatchObject({
      vector: true,
      bm25: false,
      hybrid: false,
      adaptive: true,
    });
  });

  it("accepts Atlas queryable status names as ready search indexes", async () => {
    listSearchIndexes.mockImplementation((name: string) => ({
      toArray: async () => (name === "vector_index_public"
        ? [{ status: "READY" }]
        : [{ status: "QUERYABLE" }]),
    }));

    const { GET } = await import("../app/api/health/route");
    const response = await GET();
    const payload = await response.json();

    expect(response.status).toBe(200);
    expect(payload.textIndex).toBe(true);
    expect(payload.retrievalCapabilities).toMatchObject({
      bm25: true,
      hybrid: true,
    });
  });

  it("uses a read-only text search probe when Atlas index status is not exposed", async () => {
    listSearchIndexes.mockImplementation((name: string) => ({
      toArray: async () => (name === "vector_index_public" ? [{ status: "READY" }] : []),
    }));
    aggregate.mockReturnValue({ toArray: async () => [] });

    const { GET } = await import("../app/api/health/route");
    const response = await GET();
    const payload = await response.json();

    expect(response.status).toBe(200);
    expect(payload.textIndex).toBe(true);
    expect(aggregate).toHaveBeenCalledWith(expect.arrayContaining([
      expect.objectContaining({
        $search: expect.objectContaining({ index: "text_index_public" }),
      }),
    ]));
  });
});
