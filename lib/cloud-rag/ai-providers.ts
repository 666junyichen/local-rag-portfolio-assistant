import {
  embedDocuments as embedGeminiDocuments,
  embedQuery as embedGeminiQuery,
  generateText as generateGeminiText,
} from "./gemini";
import {
  embedOpenAIDocuments,
  embedOpenAIQuery,
  generateOpenAIText,
} from "./openai";
import type { GenerationResult } from "./types";

export type CloudProvider = "openai" | "gemini";

const providerNames = new Set<CloudProvider>(["openai", "gemini"]);

function normalizeProvider(value: string | undefined): CloudProvider | null {
  const normalized = value?.trim().toLowerCase();
  return normalized && providerNames.has(normalized as CloudProvider) ? normalized as CloudProvider : null;
}

function providerHasCredential(provider: CloudProvider): boolean {
  if (provider === "openai") return Boolean(process.env.OPENAI_API_KEY);
  return Boolean(process.env.GEMINI_API_KEY);
}

function defaultPrimaryProvider(): CloudProvider {
  if (process.env.OPENAI_API_KEY) return "openai";
  return "gemini";
}

function parseFallbackProviders(value: string | undefined): CloudProvider[] {
  return (value || "")
    .split(",")
    .map((item) => normalizeProvider(item))
    .filter((item): item is CloudProvider => Boolean(item));
}

function uniqueProviders(items: CloudProvider[]): CloudProvider[] {
  return [...new Set(items)].filter(providerHasCredential);
}

export function chatProviderOrder(): CloudProvider[] {
  const primary = normalizeProvider(process.env.CLOUD_CHAT_PROVIDER) || defaultPrimaryProvider();
  const fallbacks = parseFallbackProviders(
    process.env.CLOUD_CHAT_FALLBACK_PROVIDER
      || (primary === "openai" ? "gemini" : "openai"),
  );
  return uniqueProviders([primary, ...fallbacks]);
}

export function embeddingProviderOrder(): CloudProvider[] {
  const primary = normalizeProvider(process.env.CLOUD_EMBEDDING_PROVIDER) || defaultPrimaryProvider();
  const fallbacks = parseFallbackProviders(process.env.CLOUD_EMBEDDING_FALLBACK_PROVIDER);
  return uniqueProviders([primary, ...fallbacks]);
}

function formatFailure(provider: CloudProvider, error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);
  return `${provider}: ${message}`;
}

export async function generateText(
  prompt: string,
  options: { maxOutputTokens?: number } = {},
): Promise<GenerationResult> {
  const failures: string[] = [];
  for (const provider of chatProviderOrder()) {
    try {
      const result = provider === "openai"
        ? await generateOpenAIText(prompt, options)
        : await generateGeminiText(prompt, options);
      return {
        ...result,
        provider,
        ...(failures.length ? { fallbackReason: failures.join("; ") } : {}),
      };
    } catch (error) {
      failures.push(formatFailure(provider, error));
      console.warn(`Cloud ${provider} generation unavailable; trying fallback provider`, error);
    }
  }
  throw new Error(`Cloud generation providers unavailable${failures.length ? `: ${failures.join("; ")}` : ""}`);
}

export async function embedQuery(text: string): Promise<number[]> {
  const failures: string[] = [];
  for (const provider of embeddingProviderOrder()) {
    try {
      return provider === "openai" ? await embedOpenAIQuery(text) : await embedGeminiQuery(text);
    } catch (error) {
      failures.push(formatFailure(provider, error));
      console.warn(`Cloud ${provider} embedding unavailable`, error);
    }
  }
  throw new Error(`Cloud embedding providers unavailable${failures.length ? `: ${failures.join("; ")}` : ""}`);
}

export async function embedDocuments(texts: string[]): Promise<number[][]> {
  const failures: string[] = [];
  for (const provider of embeddingProviderOrder()) {
    try {
      return provider === "openai" ? await embedOpenAIDocuments(texts) : await embedGeminiDocuments(texts);
    } catch (error) {
      failures.push(formatFailure(provider, error));
      console.warn(`Cloud ${provider} document embedding unavailable`, error);
    }
  }
  throw new Error(`Cloud embedding providers unavailable${failures.length ? `: ${failures.join("; ")}` : ""}`);
}
