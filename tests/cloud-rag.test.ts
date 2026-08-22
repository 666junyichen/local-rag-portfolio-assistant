import { describe, expect, it } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { buildVectorPipeline, chooseCloudRetrievalPath, mapSource, reciprocalRankFusion } from "../lib/cloud-rag/retrieval";
import { sse } from "../lib/cloud-rag/sse";
import { chatRequestSchema } from "../lib/cloud-rag/validation";

describe("cloud RAG contracts", () => {
  it("limits conversation history and validates questions", () => {
    const parsed = chatRequestSchema.parse({
      question: "What projects?",
      history: Array.from({ length: 20 }, (_, index) => ({ role: index % 2 ? "assistant" : "user", content: String(index) })),
      settings: { topK: 5, scoreThreshold: null, retrievalMode: "adaptive" },
    });
    expect(parsed.history).toHaveLength(12);
    expect(parsed.settings.retrievalMode).toBe("adaptive");
    expect(() => chatRequestSchema.parse({ question: "x".repeat(501) })).toThrow();
    expect(() => chatRequestSchema.parse({
      question: "What projects?",
      settings: { topK: 5, scoreThreshold: null, retrievalMode: "semantic" },
    })).toThrow();
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

  it("reports vector fallback when requested cloud modes need a missing text index", () => {
    expect(chooseCloudRetrievalPath({
      requestedMode: "hybrid",
      question: "MongoDB project",
      vectorRows: [{ score: 0.88 }],
      textSearchAvailable: false,
    })).toMatchObject({
      requestedMode: "hybrid",
      appliedMode: "vector",
      fallbackReason: "Atlas Search text index is unavailable; using Vector Search.",
      capabilities: { vector: true, bm25: false, hybrid: false, rerank: false, adaptive: true },
    });

    expect(chooseCloudRetrievalPath({
      requestedMode: "adaptive",
      question: "Compare the project and skill evidence",
      vectorRows: [{ score: 0.22 }],
      textSearchAvailable: false,
    })).toMatchObject({
      requestedMode: "adaptive",
      appliedMode: "vector",
      fallbackReason: "Atlas Search text index is unavailable; adaptive used Vector Search.",
      rerankerTriggered: false,
      rerankerReasons: ["complex-query", "low-confidence"],
    });
  });

  it("provides a public-safe cloud retrieval benchmark script", () => {
    const script = fs.readFileSync(path.resolve(process.cwd(), "scripts/evaluate-cloud-retrieval.mjs"), "utf8");
    expect(script).toContain("evals/rag_benchmark.json");
    expect(script).toContain("retrievalMode");
    expect(script).toContain("latest-cloud-retrieval");
    expect(script).toContain("/api/retrieve");
    expect(script).toContain("isCapabilityFallback");
    expect(script).toContain("strictlyImprovesBaseline");
    expect(script).toContain("outside the public retrieval boundary");
    expect(script).not.toContain("/api/chat");
  });

  it("keeps vector when benchmark candidates only tie a zero-quality baseline", async () => {
    // @ts-expect-error The executable benchmark script intentionally has no declaration file.
    const { promotionGate } = await import("../scripts/evaluate-cloud-retrieval.mjs");
    const zeroMetrics = {
      answerable: 40,
      hit_at_5: 0,
      recall_at_5: 0,
      mrr: 0,
      no_answer_accuracy: 1,
      privacy_violations: 0,
      avg_latency_ms: 1000,
    };

    expect(promotionGate({
      vector: { degraded: false, metrics: zeroMetrics },
      hybrid: { degraded: false, metrics: zeroMetrics },
    })).toBe("Keep cloud default on vector; no candidate beat the baseline without regression.");

    expect(promotionGate({
      vector: { degraded: false, metrics: { ...zeroMetrics, hit_at_5: 0.5, recall_at_5: 0.4, mrr: 0.3 } },
      adaptive: { degraded: false, metrics: { ...zeroMetrics, hit_at_5: 0.55, recall_at_5: 0.45, mrr: 0.31 } },
    })).toBe("Candidate default: adaptive met the benchmark gate.");
  });
});
