import { describe, expect, it, vi } from "vitest";
import { buildGenerationPayload, requestWithRetry } from "../lib/cloud-rag/gemini";

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
});
