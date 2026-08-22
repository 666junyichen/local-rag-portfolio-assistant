import { beforeEach, describe, expect, it, vi } from "vitest";

const listSearchIndexes = vi.fn();
const cloudDb = vi.fn();

vi.mock("@/lib/cloud-rag/mongodb", () => ({ cloudDb }));

describe("cloud health route", () => {
  beforeEach(() => {
    process.env.GEMINI_API_KEY = "test-gemini";
    listSearchIndexes.mockReset();
    cloudDb.mockReset();
    cloudDb.mockResolvedValue({
      command: vi.fn().mockResolvedValue({ ok: 1 }),
      collection: vi.fn().mockReturnValue({ listSearchIndexes }),
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
});
