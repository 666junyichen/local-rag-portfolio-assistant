import { describe, expect, it, vi } from "vitest";
import { buildGenerationPayload, embedDocuments, requestWithRetry } from "../lib/cloud-rag/gemini";

describe("Gemini resilience", () => {
  it("retries transient 503 responses before succeeding", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(new Response("overloaded", { status: 503 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    const result = await requestWithRetry("https://example.test", {}, fetcher, async () => undefined);
    expect(result).toEqual({ ok: true });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("does not retry permanent client errors", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response("bad request", { status: 400 }));
    await expect(requestWithRetry("https://example.test", {}, fetcher, async () => undefined)).rejects.toThrow("400");
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("omits thinking configuration for the fallback model", () => {
    const fallback = buildGenerationPayload("prompt", false);
    const primary = buildGenerationPayload("prompt", true);
    expect(fallback.generationConfig).not.toHaveProperty("thinkingConfig");
    expect(primary.generationConfig).toHaveProperty("thinkingConfig");
  });

  it("embeds public chunks as retrieval documents in bounded batches", async () => {
    const previousKey = process.env.GEMINI_API_KEY;
    process.env.GEMINI_API_KEY = "test-key";
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      embeddings: [{ values: [0.1, 0.2] }, { values: [0.3, 0.4] }],
    }), { status: 200 }));
    try {
      const values = await embedDocuments(["first public chunk", "second public chunk"], fetcher);
      expect(values).toEqual([[0.1, 0.2], [0.3, 0.4]]);
      const payload = JSON.parse(String(fetcher.mock.calls[0][1]?.body));
      expect(payload.requests.every((request: { taskType: string }) => request.taskType === "RETRIEVAL_DOCUMENT")).toBe(true);
    } finally {
      if (previousKey === undefined) delete process.env.GEMINI_API_KEY;
      else process.env.GEMINI_API_KEY = previousKey;
    }
  });
});
