import { beforeEach, describe, expect, it, vi } from "vitest";

const retrieveForQuestion = vi.fn();
const generateText = vi.fn();

vi.mock("@/lib/cloud-rag/retrieval", () => ({ retrieveForQuestion }));
vi.mock("@/lib/cloud-rag/gemini", () => ({ generateText }));
vi.mock("@/lib/cloud-rag/prompt", () => ({ buildPrompt: vi.fn() }));
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
  });

  it("streams a grounded refusal when the selected spaces have no evidence", async () => {
    retrieveForQuestion.mockResolvedValue([]);
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
    expect(body).toContain("does not contain enough evidence");
    expect(body).toContain("event: done");
    expect(generateText).not.toHaveBeenCalled();
  });
});
