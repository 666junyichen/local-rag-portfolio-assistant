import { describe, expect, it, vi } from "vitest";

import {
  buildOpenAIEmbeddingPayload,
  buildOpenAIResponsesPayload,
  embedOpenAIDocuments,
  parseOpenAIGenerationResponse,
} from "../lib/cloud-rag/openai";

describe("OpenAI cloud provider", () => {
  it("builds the requested low-cost chat and embedding payloads", () => {
    expect(buildOpenAIResponsesPayload("grounded prompt", 1600, "gpt-5.6-luna")).toMatchObject({
      model: "gpt-5.6-luna",
      input: "grounded prompt",
      max_output_tokens: 1600,
      reasoning: { effort: "none" },
    });

    expect(buildOpenAIEmbeddingPayload(["first", "second"], "text-embedding-3-small")).toEqual({
      model: "text-embedding-3-small",
      input: ["first", "second"],
      encoding_format: "float",
    });
  });

  it("parses Responses API output when output_text is empty but message content contains text", () => {
    expect(parseOpenAIGenerationResponse({
      status: "completed",
      output_text: "",
      output: [{
        type: "message",
        status: "completed",
        role: "assistant",
        content: [{ type: "output_text", text: "ok" }],
      }],
    })).toEqual({
      text: "ok",
      finishReason: null,
      truncated: false,
    });
  });

  it("embeds public chunks with OpenAI in batches and preserves response order", async () => {
    const previousKey = process.env.OPENAI_API_KEY;
    process.env.OPENAI_API_KEY = "test-openai-key";
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      model: "text-embedding-3-small",
      data: [
        { index: 1, embedding: [0.3, 0.4] },
        { index: 0, embedding: [0.1, 0.2] },
      ],
    }), { status: 200 }));

    try {
      await expect(embedOpenAIDocuments(["first public chunk", "second public chunk"], fetcher))
        .resolves.toEqual([[0.1, 0.2], [0.3, 0.4]]);
      expect(fetcher).toHaveBeenCalledTimes(1);
      const request = JSON.parse(String(fetcher.mock.calls[0][1]?.body));
      expect(request.model).toBe("text-embedding-3-small");
      expect(request.input).toEqual(["first public chunk", "second public chunk"]);
    } finally {
      if (previousKey === undefined) delete process.env.OPENAI_API_KEY;
      else process.env.OPENAI_API_KEY = previousKey;
    }
  });
});
