import { retrieveForQuestion } from "@/lib/cloud-rag/retrieval";
import { retrieveRequestSchema } from "@/lib/cloud-rag/validation";
import { requireActivePublicSpaces } from "@/lib/cloud-publish/spaces";

export const runtime = "nodejs";

export async function POST(request: Request) {
  try {
    const body = retrieveRequestSchema.parse(await request.json());
    body.settings.spaceIds = await requireActivePublicSpaces(body.settings.spaceIds);
    const sources = await retrieveForQuestion(body.question, body.settings);
    return Response.json({ candidates: sources, selectedContext: sources, settings: body.settings });
  } catch (error) {
    return Response.json({ error: error instanceof Error ? error.message : "Retrieval failed" }, { status: 400 });
  }
}
