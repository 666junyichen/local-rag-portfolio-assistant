export type Language = "zh" | "en";
export type AnswerIntent = "exhaustive" | "ranked" | "fact";

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
  parentChunkId?: string;
  semanticGroupId?: string;
  sectionType?: string;
  entityTitle?: string;
  matchedSnippet?: string;
  retrievalChannels?: Array<"vector" | "bm25">;
  vectorRank?: number;
  bm25Rank?: number;
  fusionScore?: number;
};

export type RetrievalResult = {
  candidates: Source[];
  selectedContext: Source[];
  intent: AnswerIntent;
};

export type GenerationResult = {
  text: string;
  finishReason: string | null;
  truncated: boolean;
};

export type ChatTurn = { role: "user" | "assistant"; content: string };
