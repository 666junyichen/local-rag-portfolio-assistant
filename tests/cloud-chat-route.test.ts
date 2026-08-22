import { beforeEach, describe, expect, it, vi } from "vitest";

const retrieveForQuestion = vi.fn();
const generateText = vi.fn();
const buildPrompt = vi.fn();

vi.mock("@/lib/cloud-rag/retrieval", () => ({ retrieveForQuestion }));
vi.mock("@/lib/cloud-rag/gemini", () => ({ generateText }));
vi.mock("@/lib/cloud-rag/prompt", () => ({ buildPrompt }));
vi.mock("@/lib/cloud-rag/rate-limit", () => ({ enforceRateLimit: vi.fn().mockResolvedValue(true) }));
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

  it("sends only deduplicated parent context to Gemini and exposes truncation metadata", async () => {
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
});
