export type Language = "zh" | "en";

export type RetrievalSettings = {
  topK: number;
  scoreThreshold: number | null;
};

export type Source = {
  docId: string;
  chunkId: string;
  title: string;
  category: string;
  language: Language;
  url?: string;
  snippet: string;
  score: number;
};

export type ChatTurn = { role: "user" | "assistant"; content: string };
