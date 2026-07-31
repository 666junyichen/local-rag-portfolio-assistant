import { describe, expect, it } from "vitest";
import { mapSource } from "../lib/cloud-rag/retrieval";
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
    const source = mapSource({ visibility: "public", doc_id: "d1", chunk_id: "c1", title: "Project", body: "Public evidence", score: 0.9, metadata: { language: "en" } });
    expect(source?.snippet).toBe("Public evidence");
    expect(source).not.toHaveProperty("embedding");
  });

  it("formats custom SSE events", () => {
    expect(sse("token", { text: "hello" })).toBe('event: token\ndata: {"text":"hello"}\n\n');
  });
});
