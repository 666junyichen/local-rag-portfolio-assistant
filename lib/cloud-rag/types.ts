export type Language = "zh" | "en";

export type RetrievalSettings = {
  topK: number;
  scoreThreshold: number | null;
  spaceIds: string[];
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
  spaceId: string;
  spaceName: string;
  retrievalChannels?: Array<"vector" | "bm25">;
  vectorRank?: number;
  bm25Rank?: number;
  fusionScore?: number;
};

export type ChatTurn = { role: "user" | "assistant"; content: string };
