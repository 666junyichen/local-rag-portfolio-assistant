import { describe, expect, it, vi } from "vitest";

const retrieveForQuestion = vi.fn();

vi.mock("@/lib/cloud-rag/retrieval", () => ({ retrieveForQuestion }));
vi.mock("@/lib/cloud-rag/validation", () => ({
  retrieveRequestSchema: { parse: (value: unknown) => value },
}));
vi.mock("@/lib/cloud-publish/spaces", () => ({
  requireActivePublicSpaces: vi.fn().mockResolvedValue(["portfolio"]),
}));

describe("cloud retrieve route", () => {
  it("returns child candidates separately from deduplicated parent context", async () => {
    const child = { chunkId: "child-1", matchedSnippet: "matched child" };
    const parent = { chunkId: "child-1", parentChunkId: "parent-1", snippet: "parent evidence" };
    retrieveForQuestion.mockResolvedValue({
      candidates: [child, { ...child, chunkId: "child-2" }],
      selectedContext: [parent],
      intent: "fact",
    });

    const { POST } = await import("../app/api/retrieve/route");
    const response = await POST(new Request("https://example.test/api/retrieve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: "Which project uses MongoDB?",
        settings: { topK: 5, scoreThreshold: null, spaceIds: ["portfolio"] },
      }),
    }));
    const payload = await response.json();

    expect(payload.candidates).toEqual([child, { ...child, chunkId: "child-2" }]);
    expect(payload.selectedContext).toEqual([parent]);
    expect(payload.intent).toBe("fact");
  });
});
