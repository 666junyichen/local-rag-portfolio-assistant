import { z } from "zod";

import { DEFAULT_SPACE_ID, MAX_SELECTED_SPACES } from "./spaces";

const turn = z.object({
  role: z.enum(["user", "assistant"]),
  content: z.string().trim().max(2000),
});

const retrievalMode = z.enum(["vector", "bm25", "hybrid", "hybrid-rerank", "adaptive"]).default("vector");

export const chatRequestSchema = z.object({
  question: z.string().trim().min(1).max(500),
  language: z.enum(["zh", "en"]).default("zh"),
  history: z.array(turn).default([]).transform((items) => items.slice(-12)),
  settings: z.object({
    topK: z.number().int().min(1).max(10).default(5),
    scoreThreshold: z.number().min(0).max(1).nullable().default(null),
    retrievalMode,
    spaceIds: z.array(z.string().trim().toLowerCase().regex(/^[a-z0-9][a-z0-9-]{0,47}$/))
      .max(MAX_SELECTED_SPACES).default([DEFAULT_SPACE_ID])
      .transform((items) => [...new Set(items.length ? items : [DEFAULT_SPACE_ID])]),
  }).default({ topK: 5, scoreThreshold: null, retrievalMode: "vector", spaceIds: [DEFAULT_SPACE_ID] }),
});

export const retrieveRequestSchema = chatRequestSchema.pick({ question: true, language: true, settings: true });
