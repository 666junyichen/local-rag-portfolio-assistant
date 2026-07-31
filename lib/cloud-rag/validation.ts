import { z } from "zod";

const turn = z.object({
  role: z.enum(["user", "assistant"]),
  content: z.string().trim().max(2000),
});

export const chatRequestSchema = z.object({
  question: z.string().trim().min(1).max(500),
  language: z.enum(["zh", "en"]).default("zh"),
  history: z.array(turn).default([]).transform((items) => items.slice(-12)),
  settings: z.object({
    topK: z.number().int().min(1).max(10).default(5),
    scoreThreshold: z.number().min(0).max(1).nullable().default(null),
  }).default({ topK: 5, scoreThreshold: null }),
});

export const retrieveRequestSchema = chatRequestSchema.pick({ question: true, language: true, settings: true });
