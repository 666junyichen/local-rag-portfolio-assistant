import { describe, expect, it } from "vitest";
import { buildVectorPipeline, mapSource, reciprocalRankFusion } from "../lib/cloud-rag/retrieval";
import { sse } from "../lib/cloud-rag/sse";
import { chatRequestSchema } from "../lib/cloud-rag/validation";

describe("cloud RAG contracts", () => {
  it("limits conversation history and validates questions", () => {
    const parsed = chatRequestSchema.parse({
      question: "What projects?",
      history: Array.from({ length: 20 }, (_, index) => ({ role: index % 2 ? "assistant" : "user", content: String(index) })),
      settings: { topK: 5, scoreThreshold: null },
    });
    expect(parsed.history).toHaveLength(12);
    expect(() => chatRequestSchema.parse({ question: "x".repeat(501) })).toThrow();
  });

  it("never exposes private search results", () => {
    expect(mapSource({ visibility: "private", body: "secret" })).toBeNull();
    expect(mapSource({ visibility: "public", validity_status: "archived", body: "old" })).toBeNull();
    const source = mapSource({ visibility: "public", doc_id: "d1", chunk_id: "c1", title: "Project", body: "Public evidence", score: 0.9, metadata: { language: "en" } });
    expect(source?.snippet).toBe("Public evidence");
    expect(source).not.toHaveProperty("embedding");
  });

  it("returns the parent answer context for owner-uploaded child matches", () => {
    const source = mapSource({ visibility: "public", validity_status: "active", child_body: "MongoDB", parent_body: "Portfolio RAG uses MongoDB Vector Search.", score: 0.9 });
    expect(source?.snippet).toBe("Portfolio RAG uses MongoDB Vector Search.");
  });

  it("uses indexed visibility and knowledge-space fields in the vector pre-filter", () => {
    const pipeline = buildVectorPipeline([0.1, 0.2], 5, 30);
    expect(pipeline[0]).toEqual(expect.objectContaining({
      $vectorSearch: expect.objectContaining({ filter: { visibility: "public", space_id: "portfolio" } }),
    }));
    expect(pipeline).toContainEqual({
      $match: { $or: [{ validity_status: "active" }, { validity_status: { $exists: false } }] },
    });
  });

  it("formats custom SSE events", () => {
    expect(sse("token", { text: "hello" })).toBe('event: token\ndata: {"text":"hello"}\n\n');
  });

  it("fuses independent vector and Atlas Search candidates with RRF", () => {
    const rows = reciprocalRankFusion(
      [{ chunk_id: "dense", score: 0.9 }, { chunk_id: "both", score: 0.8 }],
      [{ chunk_id: "exact", bm25_score: 8 }, { chunk_id: "both", bm25_score: 7 }],
    );
    expect(rows[0].chunk_id).toBe("both");
    expect(rows[0].retrieval_channels).toEqual(["vector", "bm25"]);
    expect(rows[0].vector_rank).toBe(2);
    expect(rows[0].bm25_rank).toBe(2);
  });
});
