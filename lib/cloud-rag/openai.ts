import type { GenerationResult } from "./types";

const OPENAI_BASE_URL = "https://api.openai.com/v1";

type Fetcher = (input: string | URL | Request, init?: RequestInit) => Promise<Response>;
type Sleeper = (milliseconds: number) => Promise<void>;

type OpenAIResponseContent = { type?: string; text?: string };
type OpenAIGenerationResponse = {
  status?: string;
  output_text?: string;
  incomplete_details?: { reason?: string | null } | null;
  output?: Array<{
    type?: string;
    status?: string;
    role?: string;
    content?: OpenAIResponseContent[];
  }>;
};

type OpenAIEmbeddingResponse = {
  model?: string;
  data?: Array<{ index?: number; embedding?: number[] }>;
};

const sleep: Sleeper = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));
const chatModel = () => process.env.OPENAI_CHAT_MODEL || "gpt-5.6-luna";
const embeddingModel = () => process.env.OPENAI_EMBEDDING_MODEL || "text-embedding-3-small";
const reasoningEffort = () => process.env.OPENAI_REASONING_EFFORT || "none";
const embeddingDimensions = () => {
  const raw = process.env.OPENAI_EMBEDDING_DIMENSIONS;
  if (!raw) return undefined;
  const value = Number(raw);
  return Number.isInteger(value) && value > 0 ? value : undefined;
};

function openAIUrl(path: string) {
  const base = (process.env.OPENAI_BASE_URL || OPENAI_BASE_URL).replace(/\/+$/, "");
  return `${base}/${path.replace(/^\/+/, "")}`;
}

function parseErrorBody(body: string): string {
  if (!body) return "";
  try {
    const parsed = JSON.parse(body) as { error?: { message?: string; code?: string; type?: string } };
    return [parsed.error?.message, parsed.error?.code, parsed.error?.type].filter(Boolean).join(" ");
  } catch {
    return body.slice(0, 240);
  }
}

export async function requestOpenAI<T = unknown>(
  path: string,
  payload: unknown,
  fetcher: Fetcher = fetch,
  sleeper: Sleeper = sleep,
  maxRetries = 1,
): Promise<T> {
  if (!process.env.OPENAI_API_KEY) throw new Error("OPENAI_API_KEY is not configured");
  const delays = [350].slice(0, maxRetries);
  for (let attempt = 0; attempt <= delays.length; attempt += 1) {
    let response: Response;
    try {
      response = await fetcher(openAIUrl(path), {
        method: "POST",
        headers: {
          Authorization: `Bearer ${process.env.OPENAI_API_KEY}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(30_000),
      });
    } catch (error) {
      if (attempt === delays.length) throw error;
      await sleeper(delays[attempt]);
      continue;
    }

    const body = await response.text();
    if (response.ok) return (body ? JSON.parse(body) : {}) as T;

    const retryable = response.status >= 500;
    if (!retryable || attempt === delays.length) {
      const detail = parseErrorBody(body);
      throw new Error(`OpenAI request failed (${response.status})${detail ? `: ${detail}` : ""}`);
    }
    await sleeper(delays[attempt]);
  }
  throw new Error("OpenAI request failed");
}

export function buildOpenAIResponsesPayload(prompt: string, maxOutputTokens = 1000, model = chatModel()) {
  return {
    model,
    input: prompt,
    max_output_tokens: Math.min(Math.max(maxOutputTokens, 1), 1600),
    reasoning: { effort: reasoningEffort() },
  };
}

export function parseOpenAIGenerationResponse(result: OpenAIGenerationResponse): GenerationResult {
  const contentText = result.output
    ?.flatMap((item) => item.content || [])
    .map((part) => part.text || "")
    .join("")
    .trim() || "";
  const text = (result.output_text || "").trim() || contentText;
  const incompleteReason = result.incomplete_details?.reason || null;
  const finishReason = incompleteReason || (result.status && result.status !== "completed" ? result.status : null);
  return {
    text,
    finishReason,
    truncated: incompleteReason === "max_output_tokens" || result.status === "incomplete",
  };
}

export async function generateOpenAIText(
  prompt: string,
  options: { maxOutputTokens?: number } = {},
): Promise<GenerationResult> {
  const result = await requestOpenAI<OpenAIGenerationResponse>(
    "responses",
    buildOpenAIResponsesPayload(prompt, options.maxOutputTokens || 1000),
  );
  return parseOpenAIGenerationResponse(result);
}

export function buildOpenAIEmbeddingPayload(texts: string[], model = embeddingModel()) {
  return {
    model,
    input: texts,
    encoding_format: "float",
    ...(embeddingDimensions() ? { dimensions: embeddingDimensions() } : {}),
  };
}

export async function embedOpenAIQuery(text: string): Promise<number[]> {
  const result = await requestOpenAI<OpenAIEmbeddingResponse>(
    "embeddings",
    buildOpenAIEmbeddingPayload([text]),
  );
  const embedding = result.data?.[0]?.embedding;
  if (!embedding?.length) throw new Error("OpenAI embedding response is empty");
  return embedding;
}

export async function embedOpenAIDocuments(texts: string[], fetcher: Fetcher = fetch): Promise<number[][]> {
  if (!texts.length) return [];
  const output: number[][] = [];
  const batchSize = 96;
  for (let start = 0; start < texts.length; start += batchSize) {
    const batch = texts.slice(start, start + batchSize);
    const result = await requestOpenAI<OpenAIEmbeddingResponse>(
      "embeddings",
      buildOpenAIEmbeddingPayload(batch),
      fetcher,
      sleep,
    );
    const rows = [...(result.data || [])].sort((left, right) => Number(left.index || 0) - Number(right.index || 0));
    if (rows.length !== batch.length || rows.some((row) => !row.embedding?.length)) {
      throw new Error("OpenAI embedding response is incomplete");
    }
    output.push(...rows.map((row) => row.embedding!));
  }
  return output;
}
