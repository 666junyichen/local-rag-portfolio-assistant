import { beforeEach, describe, expect, it, vi } from "vitest";

const retrieveForQuestion = vi.fn();
const generateText = vi.fn();
const buildPrompt = vi.fn();

vi.mock("@/lib/cloud-rag/retrieval", () => ({ retrieveForQuestion }));
vi.mock("@/lib/cloud-rag/ai-providers", () => ({ generateText }));
vi.mock("@/lib/cloud-rag/prompt", () => ({ buildPrompt }));
vi.mock("@/lib/cloud-rag/rate-limit", () => ({
  enforceRateLimit: vi.fn().mockResolvedValue(true),
  enforceUsageBudget: vi.fn().mockResolvedValue({ allowed: true }),
}));
vi.mock("@/lib/cloud-rag/sse", () => ({
  sse: (event: string, payload: unknown) => `event: ${event}\ndata: ${JSON.stringify(payload)}\n\n`,
}));
vi.mock("@/lib/cloud-rag/validation", () => ({
  chatRequestSchema: { parse: (value: unknown) => value },
}));
vi.mock("@/lib/cloud-publish/spaces", () => ({
  requireActivePublicSpaces: vi.fn().mockResolvedValue(["project-docs"]),
}));

describe("cloud chat route", () => {
  beforeEach(() => {
    retrieveForQuestion.mockReset();
    generateText.mockReset();
    buildPrompt.mockReset();
  });

  it("streams a grounded refusal when the selected spaces have no evidence", async () => {
    retrieveForQuestion.mockResolvedValue({
      candidates: [],
      selectedContext: [],
      intent: "fact",
      retrieval: {
        requestedMode: "hybrid",
        appliedMode: "vector",
        retrievalPath: "vector",
        capabilities: { vector: true, bm25: false, hybrid: false, rerank: false, adaptive: true },
        fallbackReason: "Atlas Search text index is unavailable; using Vector Search.",
      },
    });
    const { POST } = await import("../app/api/chat/route");
    const response = await POST(new Request("https://example.test/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: "What is the missing fact?",
        language: "en",
        history: [],
        settings: { topK: 5, scoreThreshold: null, spaceIds: ["project-docs"] },
      }),
    }));

    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toContain("text/event-stream");
    const body = await response.text();
    expect(body).toContain("event: retrieval");
    expect(body).toContain('"requestedMode":"hybrid"');
    expect(body).toContain('"appliedMode":"vector"');
    expect(body).toContain("Atlas Search text index is unavailable");
    expect(body).toContain("does not contain enough evidence");
    expect(body).toContain("event: done");
    expect(generateText).not.toHaveBeenCalled();
  });

  it("sends only deduplicated parent context to the configured generator and exposes truncation metadata", async () => {
    const parent = {
      docId: "resume", chunkId: "child-1", parentChunkId: "parent-1", semanticGroupId: "rag",
      title: "Master Resume", category: "project", language: "en", snippet: "Full parent evidence",
      matchedSnippet: "Matched child", score: 0.9, spaceId: "portfolio", spaceName: "Portfolio",
    };
    retrieveForQuestion.mockResolvedValue({
      candidates: [parent, { ...parent, chunkId: "duplicate-child" }],
      selectedContext: [parent],
      intent: "exhaustive",
    });
    buildPrompt.mockReturnValue("grounded prompt");
    generateText.mockResolvedValue({ text: "Partial answer", finishReason: "MAX_TOKENS", truncated: true });

    const { POST } = await import("../app/api/chat/route");
    const response = await POST(new Request("https://example.test/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: "What are all projects?",
        language: "en",
        history: [],
        settings: { topK: 5, scoreThreshold: null, spaceIds: ["project-docs"] },
      }),
    }));

    const body = await response.text();
    expect(buildPrompt).toHaveBeenCalledWith(
      "What are all projects?",
      [parent],
      [],
      "en",
      "exhaustive",
    );
    expect(generateText).toHaveBeenCalledTimes(1);
    expect(generateText).toHaveBeenCalledWith("grounded prompt", { maxOutputTokens: 1600 });
    expect(body).toContain('event: warning');
    expect(body).toContain('"finishReason":"MAX_TOKENS"');
    expect(body).toContain('"truncated":true');
    expect(body).not.toContain("duplicate-child");
  });

  it("streams evidence-only fallback when cloud generation is unavailable", async () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    const consoleWarn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const parent = {
      docId: "resume", chunkId: "child-1", parentChunkId: "parent-1", semanticGroupId: "rag",
      title: "Master Resume", category: "project", language: "zh", snippet: "Local RAG Portfolio Assistant 体现了 RAG 应用能力。",
      matchedSnippet: "RAG 项目", score: 1, spaceId: "portfolio", spaceName: "Portfolio",
    };
    retrieveForQuestion.mockResolvedValue({
      candidates: [parent],
      selectedContext: [parent],
      intent: "ranked",
      retrieval: {
        requestedMode: "adaptive",
        appliedMode: "bm25",
        retrievalPath: "bm25",
        capabilities: { vector: false, bm25: true, hybrid: false, rerank: false, adaptive: true },
        fallbackReason: "Cloud embedding is unavailable; using Atlas BM25 text search.",
      },
    });
    buildPrompt.mockReturnValue("grounded prompt");
    generateText.mockRejectedValue(new Error("OpenAI request failed (429)"));

    try {
      const { POST } = await import("../app/api/chat/route");
      const response = await POST(new Request("https://example.test/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: "Junyi 最强的 AI 项目有哪些?",
          language: "zh",
          history: [],
          settings: { topK: 5, scoreThreshold: null, spaceIds: ["portfolio"], retrievalMode: "adaptive" },
        }),
      }));

      const body = await response.text();
      expect(response.status).toBe(200);
      expect(body).toContain("event: retrieval");
      expect(body).toContain("Cloud embedding is unavailable");
      expect(body).toContain("event: warning");
      expect(body).toContain("AI 生成服务当前不可用");
      expect(body).toContain("Local RAG Portfolio Assistant");
      expect(body).toContain("event: done");
      expect(body).not.toContain("event: error");
      expect(consoleWarn).toHaveBeenCalledWith(
        "Cloud RAG generation unavailable; returning evidence-only fallback",
        "OpenAI request failed (429)",
      );
      expect(consoleError).not.toHaveBeenCalled();
    } finally {
      consoleError.mockRestore();
      consoleWarn.mockRestore();
    }
  });
});
