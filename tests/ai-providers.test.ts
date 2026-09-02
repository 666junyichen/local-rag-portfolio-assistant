import { beforeEach, describe, expect, it, vi } from "vitest";

const providerMocks = vi.hoisted(() => ({
  openai: {
    generateOpenAIText: vi.fn(),
    embedOpenAIQuery: vi.fn(),
    embedOpenAIDocuments: vi.fn(),
  },
  gemini: {
    generateText: vi.fn(),
    embedQuery: vi.fn(),
    embedDocuments: vi.fn(),
  },
}));

vi.mock("../lib/cloud-rag/openai", () => providerMocks.openai);
vi.mock("../lib/cloud-rag/gemini", () => providerMocks.gemini);

describe("cloud AI provider selection", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    vi.resetModules();
    process.env = { ...originalEnv };
    providerMocks.openai.generateOpenAIText.mockReset();
    providerMocks.openai.embedOpenAIQuery.mockReset();
    providerMocks.openai.embedOpenAIDocuments.mockReset();
    providerMocks.gemini.generateText.mockReset();
    providerMocks.gemini.embedQuery.mockReset();
    providerMocks.gemini.embedDocuments.mockReset();
  });

  it("uses OpenAI as the primary cloud generation provider and Gemini only as fallback", async () => {
    const consoleWarn = vi.spyOn(console, "warn").mockImplementation(() => {});
    process.env.OPENAI_API_KEY = "test-openai";
    process.env.GEMINI_API_KEY = "test-gemini";
    process.env.CLOUD_CHAT_PROVIDER = "openai";
    process.env.CLOUD_CHAT_FALLBACK_PROVIDER = "gemini";
    providerMocks.openai.generateOpenAIText.mockRejectedValue(new Error("OpenAI request failed (500)"));
    providerMocks.gemini.generateText.mockResolvedValue({ text: "备用回答", finishReason: null, truncated: false });

    try {
      const { generateText } = await import("../lib/cloud-rag/ai-providers");
      await expect(generateText("grounded prompt")).resolves.toMatchObject({
        text: "备用回答",
        provider: "gemini",
        fallbackReason: expect.stringContaining("openai"),
      });
    } finally {
      consoleWarn.mockRestore();
    }

    expect(providerMocks.openai.generateOpenAIText).toHaveBeenCalledWith("grounded prompt", {});
    expect(providerMocks.gemini.generateText).toHaveBeenCalledWith("grounded prompt", {});
  });

  it("uses OpenAI as the primary embedding provider", async () => {
    process.env.OPENAI_API_KEY = "test-openai";
    process.env.GEMINI_API_KEY = "test-gemini";
    process.env.CLOUD_EMBEDDING_PROVIDER = "openai";
    providerMocks.openai.embedOpenAIQuery.mockResolvedValue([0.1, 0.2, 0.3]);

    const { embedQuery } = await import("../lib/cloud-rag/ai-providers");
    await expect(embedQuery("Junyi RAG project")).resolves.toEqual([0.1, 0.2, 0.3]);

    expect(providerMocks.openai.embedOpenAIQuery).toHaveBeenCalledWith("Junyi RAG project");
    expect(providerMocks.gemini.embedQuery).not.toHaveBeenCalled();
  });

  it("does not silently mix Gemini query embeddings into an OpenAI vector index unless explicitly configured", async () => {
    const consoleWarn = vi.spyOn(console, "warn").mockImplementation(() => {});
    process.env.OPENAI_API_KEY = "test-openai";
    process.env.GEMINI_API_KEY = "test-gemini";
    process.env.CLOUD_EMBEDDING_PROVIDER = "openai";
    providerMocks.openai.embedOpenAIQuery.mockRejectedValue(new Error("OpenAI embedding failed (429)"));
    providerMocks.gemini.embedQuery.mockResolvedValue([9, 9]);

    try {
      const { embedQuery } = await import("../lib/cloud-rag/ai-providers");
      await expect(embedQuery("Junyi RAG project")).rejects.toThrow("OpenAI embedding failed");
    } finally {
      consoleWarn.mockRestore();
    }

    expect(providerMocks.gemini.embedQuery).not.toHaveBeenCalled();
  });
});
