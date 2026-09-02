import { buildPrompt } from "@/lib/cloud-rag/prompt";
import { generateText } from "@/lib/cloud-rag/ai-providers";
import { enforceRateLimit, enforceUsageBudget } from "@/lib/cloud-rag/rate-limit";
import { retrieveForQuestion } from "@/lib/cloud-rag/retrieval";
import { sse } from "@/lib/cloud-rag/sse";
import { chatRequestSchema } from "@/lib/cloud-rag/validation";
import { requireActivePublicSpaces } from "@/lib/cloud-publish/spaces";
import type { Language, Source } from "@/lib/cloud-rag/types";

export const runtime = "nodejs";
export const maxDuration = 60;

const encoder = new TextEncoder();

function compactEvidenceLine(source: Source, index: number, language: Language): string {
  const text = (source.snippet || source.matchedSnippet || "").replace(/\s+/g, " ").trim();
  const excerpt = text.length > 180 ? `${text.slice(0, 177)}...` : text;
  const title = source.title || source.entityTitle || source.docId || `Source ${index + 1}`;
  if (language === "zh") return `${index + 1}. ${title}：${excerpt}`;
  return `${index + 1}. ${title}: ${excerpt}`;
}

function evidenceOnlyFallback(sources: Source[], language: Language): string {
  const lines = sources.slice(0, 5).map((source, index) => compactEvidenceLine(source, index, language)).join("\n");
  if (language === "zh") {
    return [
      "AI 生成服务当前不可用，但我已经从公开知识库检索到以下证据。修复 API key 或额度后会恢复完整自然语言回答：",
      lines,
    ].filter(Boolean).join("\n\n");
  }
  return [
    "AI generation is currently unavailable, but I found these public knowledge-base sources. Full natural-language answers will resume after the API key or quota is fixed:",
    lines,
  ].filter(Boolean).join("\n\n");
}

export async function POST(request: Request) {
  try {
    const body = chatRequestSchema.parse(await request.json());
    body.settings.spaceIds = await requireActivePublicSpaces(body.settings.spaceIds);
    const ip = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || "unknown";
    if (!(await enforceRateLimit(ip))) {
      return Response.json({ error: "Too many requests. Please try again in one minute." }, { status: 429 });
    }
    const usageBudget = await enforceUsageBudget();
    if (!usageBudget.allowed) {
      const zhScope = usageBudget.scope === "monthly" ? "本月" : "今天";
      const enScope = usageBudget.scope === "monthly" ? "monthly" : "daily";
      return Response.json({
        error: body.language === "zh"
          ? `${zhScope}公开 Demo 问答次数已达到上限（${usageBudget.limit}）。请稍后再试。`
          : `The public demo has reached its ${enScope} chat limit (${usageBudget.limit}). Please try again later.`,
      }, { status: 429 });
    }
    const retrieval = await retrieveForQuestion(body.question, body.settings);
    const stream = new ReadableStream({
      async start(controller) {
        const send = (event: string, payload: unknown) => controller.enqueue(encoder.encode(sse(event, payload)));
        try {
          send("retrieval", {
            sources: retrieval.selectedContext,
            settings: body.settings,
            intent: retrieval.intent,
            retrieval: retrieval.retrieval,
          });
          if (!retrieval.selectedContext.length) {
            const fallback = body.language === "zh"
              ? "当前公开知识库没有足够依据回答这个问题。"
              : "The public knowledge base does not contain enough evidence to answer this question.";
            send("token", { text: fallback });
            send("done", { intent: retrieval.intent, retrieval: retrieval.retrieval, finishReason: null, truncated: false });
            return;
          }

          const prompt = buildPrompt(
            body.question,
            retrieval.selectedContext,
            body.history,
            body.language,
            retrieval.intent,
          );
          const generation = await generateText(prompt, {
            maxOutputTokens: retrieval.intent === "exhaustive" ? 1600 : 1000,
          });
          for (const token of generation.text.match(/.{1,18}/gs) || [generation.text]) {
            send("token", { text: token });
          }
          if (generation.truncated) {
            send("warning", {
              message: body.language === "zh"
                ? "回答达到模型输出上限，可能未完整列出所有有证据的项目。"
                : "The answer reached the model output limit and may not include every supported item.",
              finishReason: generation.finishReason,
              truncated: true,
            });
          }
          send("done", {
            intent: retrieval.intent,
            retrieval: retrieval.retrieval,
            finishReason: generation.finishReason,
            truncated: generation.truncated,
          });
        } catch (error) {
          console.warn(
            "Cloud RAG generation unavailable; returning evidence-only fallback",
            error instanceof Error ? error.message : error,
          );
          send("warning", {
            message: body.language === "zh"
              ? "AI 生成服务当前不可用；已返回公开知识库证据。"
              : "AI generation is currently unavailable; retrieved public evidence is returned.",
          });
          send("token", { text: evidenceOnlyFallback(retrieval.selectedContext, body.language) });
          send("done", {
            intent: retrieval.intent,
            retrieval: retrieval.retrieval,
            finishReason: null,
            truncated: false,
            generationFallback: true,
          });
        } finally {
          controller.close();
        }
      },
    });
    return new Response(stream, {
      headers: {
        "Content-Type": "text/event-stream; charset=utf-8",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
      },
    });
  } catch (error) {
    return Response.json({ error: error instanceof Error ? error.message : "Invalid request" }, { status: 400 });
  }
}
