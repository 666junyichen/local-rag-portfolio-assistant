import type { GenerationResult } from "./types";

const embeddingModel = () => process.env.GEMINI_EMBEDDING_MODEL || "gemini-embedding-001";
const chatModel = () => process.env.GEMINI_CHAT_MODEL || "gemini-3.5-flash";
const fallbackChatModel = () => process.env.GEMINI_FALLBACK_MODEL || "gemini-3.5-flash-lite";

type Fetcher = (input: string | URL | Request, init?: RequestInit) => Promise<Response>;
type Sleeper = (milliseconds: number) => Promise<void>;

const sleep: Sleeper = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

export async function requestWithRetry<T = unknown>(
  url: string,
  init: RequestInit,
  fetcher: Fetcher = fetch,
  sleeper: Sleeper = sleep,
  maxRetries = 2,
): Promise<T> {
  const delays = [350, 900].slice(0, maxRetries);
  for (let attempt = 0; attempt <= delays.length; attempt += 1) {
    let response: Response;
    try {
      response = await fetcher(url, { ...init, signal: init.signal || AbortSignal.timeout(15_000) });
    } catch (error) {
      if (attempt === delays.length) throw error;
      await sleeper(delays[attempt]);
      continue;
    }
    if (response.ok) return response.json() as Promise<T>;
    const retryable = response.status === 429 || response.status >= 500;
    if (!retryable || attempt === delays.length) {
      throw new Error(`Gemini request failed (${response.status})`);
    }
    await sleeper(delays[attempt]);
  }
  throw new Error("Gemini request failed");
}

async function callGemini<T = unknown>(path: string, payload: unknown, maxRetries = 2): Promise<T> {
  if (!process.env.GEMINI_API_KEY) throw new Error("GEMINI_API_KEY is not configured");
  return requestWithRetry<T>(`https://generativelanguage.googleapis.com/v1beta/${path}`, {
    method: "POST",
    headers: { "x-goog-api-key": process.env.GEMINI_API_KEY, "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }, fetch, sleep, maxRetries);
}

export async function embedQuery(text: string): Promise<number[]> {
  const model = embeddingModel();
  const result = await callGemini<{ embedding?: { values?: number[] } }>(`models/${model}:embedContent`, {
    model: `models/${model}`,
    taskType: "RETRIEVAL_QUERY",
    content: { parts: [{ text }] },
  });
  const values = result.embedding?.values;
  if (!values) throw new Error("Gemini embedding response is empty");
  return values;
}

export async function embedDocuments(texts: string[], fetcher: Fetcher = fetch): Promise<number[][]> {
  if (!texts.length) return [];
  if (!process.env.GEMINI_API_KEY) throw new Error("GEMINI_API_KEY is not configured");
  const model = embeddingModel();
  const output: number[][] = [];
  const batchSize = 20;
  for (let start = 0; start < texts.length; start += batchSize) {
    const batch = texts.slice(start, start + batchSize);
    const result = await requestWithRetry<{ embeddings?: Array<{ values?: number[] }> }>(
      `https://generativelanguage.googleapis.com/v1beta/models/${model}:batchEmbedContents`,
      {
        method: "POST",
        headers: { "x-goog-api-key": process.env.GEMINI_API_KEY, "Content-Type": "application/json" },
        body: JSON.stringify({
          requests: batch.map((text) => ({
            model: `models/${model}`,
            taskType: "RETRIEVAL_DOCUMENT",
            content: { parts: [{ text }] },
          })),
        }),
      },
      fetcher,
      sleep,
    );
    const embeddings = result.embeddings || [];
    if (embeddings.length !== batch.length || embeddings.some((embedding) => !embedding.values?.length)) {
      throw new Error("Gemini embedding response is incomplete");
    }
    output.push(...embeddings.map((embedding) => embedding.values!));
  }
  return output;
}

export function buildGenerationPayload(prompt: string, thinkingEnabled: boolean, maxOutputTokens = 1000) {
  return {
    contents: [{ role: "user", parts: [{ text: prompt }] }],
    generationConfig: {
      temperature: 0.15,
      maxOutputTokens,
      ...(thinkingEnabled ? { thinkingConfig: { thinkingBudget: 0 } } : {}),
    },
  };
}

type GenerationResponse = {
  candidates?: Array<{
    content?: { parts?: Array<{ text?: string }> };
    finishReason?: string;
  }>;
};

export function parseGenerationResponse(result: GenerationResponse): GenerationResult {
  const candidate = result.candidates?.[0];
  const finishReason = candidate?.finishReason || null;
  return {
    text: candidate?.content?.parts?.map((part) => part.text || "").join("").trim() || "",
    finishReason,
    truncated: finishReason === "MAX_TOKENS" || finishReason === "LENGTH",
  };
}

export async function generateText(
  prompt: string,
  options: { maxOutputTokens?: number } = {},
): Promise<GenerationResult> {
  const maxOutputTokens = Math.min(Math.max(options.maxOutputTokens || 1000, 1), 1600);
  let result: GenerationResponse;
  try {
    result = await callGemini<GenerationResponse>(
      `models/${chatModel()}:generateContent`,
      buildGenerationPayload(prompt, true, maxOutputTokens),
      0,
    );
  } catch (error) {
    console.warn("Primary Gemini model unavailable; using fallback", error);
    result = await callGemini<GenerationResponse>(
      `models/${fallbackChatModel()}:generateContent`,
      buildGenerationPayload(prompt, false, maxOutputTokens),
      1,
    );
  }
  return parseGenerationResponse(result);
}
