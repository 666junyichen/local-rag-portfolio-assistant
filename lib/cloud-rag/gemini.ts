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
): Promise<T> {
  const delays = [350, 900];
  for (let attempt = 0; attempt <= delays.length; attempt += 1) {
    const response = await fetcher(url, init);
    if (response.ok) return response.json() as Promise<T>;
    const retryable = response.status === 429 || response.status >= 500;
    if (!retryable || attempt === delays.length) {
      throw new Error(`Gemini request failed (${response.status})`);
    }
    await sleeper(delays[attempt]);
  }
  throw new Error("Gemini request failed");
}

async function callGemini<T = unknown>(path: string, payload: unknown): Promise<T> {
  if (!process.env.GEMINI_API_KEY) throw new Error("GEMINI_API_KEY is not configured");
  return requestWithRetry<T>(`https://generativelanguage.googleapis.com/v1beta/${path}`, {
    method: "POST",
    headers: { "x-goog-api-key": process.env.GEMINI_API_KEY, "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
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

export async function generateText(prompt: string): Promise<string> {
  const payload = {
    contents: [{ role: "user", parts: [{ text: prompt }] }],
    generationConfig: {
      temperature: 0.15,
      maxOutputTokens: 1200,
      thinkingConfig: { thinkingBudget: 0 },
    },
  };
  type GenerationResponse = { candidates?: Array<{ content?: { parts?: Array<{ text?: string }> } }> };
  let result: GenerationResponse;
  try {
    result = await callGemini<GenerationResponse>(`models/${chatModel()}:generateContent`, payload);
  } catch (error) {
    if (!String(error).includes("(429)") && !String(error).match(/\(5\d\d\)/)) throw error;
    result = await callGemini<GenerationResponse>(`models/${fallbackChatModel()}:generateContent`, payload);
  }
  return result.candidates?.[0]?.content?.parts?.map((part: { text?: string }) => part.text || "").join("").trim() || "";
}
