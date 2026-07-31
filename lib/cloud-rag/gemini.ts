const embeddingModel = () => process.env.GEMINI_EMBEDDING_MODEL || "gemini-embedding-001";
const chatModel = () => process.env.GEMINI_CHAT_MODEL || "gemini-3.5-flash";

async function callGemini(path: string, payload: unknown) {
  if (!process.env.GEMINI_API_KEY) throw new Error("GEMINI_API_KEY is not configured");
  const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/${path}`, {
    method: "POST",
    headers: { "x-goog-api-key": process.env.GEMINI_API_KEY, "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(`Gemini request failed (${response.status})`);
  return response.json();
}

export async function embedQuery(text: string): Promise<number[]> {
  const model = embeddingModel();
  const result = await callGemini(`models/${model}:embedContent`, {
    model: `models/${model}`,
    taskType: "RETRIEVAL_QUERY",
    content: { parts: [{ text }] },
  });
  const values = result.embedding?.values;
  if (!values) throw new Error("Gemini embedding response is empty");
  return values;
}

export async function generateText(prompt: string): Promise<string> {
  const result = await callGemini(`models/${chatModel()}:generateContent`, {
    contents: [{ role: "user", parts: [{ text: prompt }] }],
    generationConfig: {
      temperature: 0.15,
      maxOutputTokens: 1200,
      thinkingConfig: { thinkingBudget: 0 },
    },
  });
  return result.candidates?.[0]?.content?.parts?.map((part: { text?: string }) => part.text || "").join("").trim() || "";
}
