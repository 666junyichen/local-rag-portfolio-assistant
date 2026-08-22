import { buildPrompt } from "@/lib/cloud-rag/prompt";
import { generateText } from "@/lib/cloud-rag/gemini";
import { enforceRateLimit } from "@/lib/cloud-rag/rate-limit";
import { retrieveForQuestion } from "@/lib/cloud-rag/retrieval";
import { sse } from "@/lib/cloud-rag/sse";
import { chatRequestSchema } from "@/lib/cloud-rag/validation";
import { requireActivePublicSpaces } from "@/lib/cloud-publish/spaces";

export const runtime = "nodejs";
export const maxDuration = 60;

const encoder = new TextEncoder();

export async function POST(request: Request) {
  try {
    const body = chatRequestSchema.parse(await request.json());
    body.settings.spaceIds = await requireActivePublicSpaces(body.settings.spaceIds);
    const ip = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || "unknown";
    if (!(await enforceRateLimit(ip))) {
      return Response.json({ error: "Too many requests. Please try again in one minute." }, { status: 429 });
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
          console.error("Cloud RAG generation failed", error);
          send("error", {
            message: body.language === "zh"
              ? "AI 生成服务暂时繁忙，检索结果已经保留，请稍后重试。"
              : "The AI generation service is temporarily busy. Retrieved evidence is preserved; please retry shortly.",
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
