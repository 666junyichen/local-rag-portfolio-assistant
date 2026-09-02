import { beforeEach, describe, expect, it, vi } from "vitest";

const embedQuery = vi.fn();
const aggregate = vi.fn();
const cloudDb = vi.fn();

vi.mock("@/lib/cloud-rag/ai-providers", () => ({ embedQuery }));
vi.mock("@/lib/cloud-rag/mongodb", () => ({ cloudDb }));
vi.mock("../lib/cloud-rag/ai-providers", () => ({ embedQuery }));
vi.mock("../lib/cloud-rag/mongodb", () => ({ cloudDb }));
vi.mock("../lib/cloud-publish/spaces", () => ({
  spaceNameMap: vi.fn(async (spaceIds: string[]) => new Map(spaceIds.map((spaceId) => [spaceId, "Portfolio"]))),
}));

describe("cloud retrieval provider fallback", () => {
  beforeEach(() => {
    embedQuery.mockReset();
    aggregate.mockReset();
    cloudDb.mockReset();
    cloudDb.mockResolvedValue({
      collection: vi.fn().mockReturnValue({ aggregate }),
    });
  });

  it("uses Atlas BM25 when cloud embedding is denied", async () => {
    const consoleWarn = vi.spyOn(console, "warn").mockImplementation(() => {});
    embedQuery.mockRejectedValue(new Error("OpenAI request failed (429)"));
    aggregate.mockImplementation((pipeline: Array<Record<string, unknown>>) => {
      if (pipeline[0]?.$vectorSearch) throw new Error("vector search should not run without an embedding");
      return {
        toArray: async () => [{
          visibility: "public",
          validity_status: "active",
          doc_id: "resume",
          chunk_id: "resume-project-rag",
          title: "Master Resume",
          parent_body: "Local RAG Portfolio Assistant 体现了 RAG 应用能力。",
          child_body: "RAG 项目",
          bm25_score: 8,
          space_id: "portfolio",
          space_name: "Portfolio",
          section_type: "project",
          metadata: { category: "project", language: "zh" },
        }],
      };
    });

    let result;
    try {
      const { retrieveForQuestion } = await import("../lib/cloud-rag/retrieval");
      result = await retrieveForQuestion("Junyi 最强的 AI 项目有哪些?", {
        topK: 5,
        scoreThreshold: null,
        spaceIds: ["portfolio"],
        retrievalMode: "adaptive",
      });
    } finally {
      consoleWarn.mockRestore();
    }

    expect(result.selectedContext).toHaveLength(1);
    expect(result.selectedContext[0]).toMatchObject({
      title: "Master Resume",
      retrievalChannels: ["bm25"],
      retrievalPath: "bm25",
      fallbackReason: "Cloud embedding is unavailable; using Atlas BM25 text search.",
    });
    expect(result.retrieval).toMatchObject({
      requestedMode: "adaptive",
      appliedMode: "bm25",
      capabilities: { vector: false, bm25: true, hybrid: false, rerank: false, adaptive: true },
      vectorCandidates: 0,
      bm25Candidates: 1,
    });
  });
});
