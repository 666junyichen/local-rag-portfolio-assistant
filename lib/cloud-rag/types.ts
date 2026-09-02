export type Language = "zh" | "en";
export type AnswerIntent = "exhaustive" | "ranked" | "fact";
export type RetrievalMode = "vector" | "bm25" | "hybrid" | "hybrid-rerank" | "adaptive";

export type RetrievalCapabilities = {
  vector: boolean;
  bm25: boolean;
  hybrid: boolean;
  rerank: boolean;
  adaptive: boolean;
};

export type RetrievalSettings = {
  topK: number;
  scoreThreshold: number | null;
  spaceIds: string[];
  retrievalMode?: RetrievalMode;
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
  retrievalPath?: RetrievalMode;
  fallbackReason?: string;
};

export type RetrievalDiagnostics = {
  requestedMode: RetrievalMode;
  appliedMode: RetrievalMode;
  retrievalPath: RetrievalMode;
  capabilities: RetrievalCapabilities;
  fallbackReason?: string;
  rerankerTriggered?: boolean;
  rerankerReasons?: string[];
  vectorCandidates?: number;
  bm25Candidates?: number;
};

export type RetrievalResult = {
  candidates: Source[];
  selectedContext: Source[];
  intent: AnswerIntent;
  retrieval: RetrievalDiagnostics;
};

export type GenerationResult = {
  text: string;
  finishReason: string | null;
  truncated: boolean;
  provider?: "openai" | "gemini";
  fallbackReason?: string;
};

export type ChatTurn = { role: "user" | "assistant"; content: string };
