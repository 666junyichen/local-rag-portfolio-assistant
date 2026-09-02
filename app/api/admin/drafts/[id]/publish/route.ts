import { embedDocuments } from "@/lib/cloud-rag/ai-providers";
import { requireOwner } from "@/lib/cloud-publish/auth";
import { publishApiError } from "@/lib/cloud-publish/http";
import { publishDraft } from "@/lib/cloud-publish/publishing";
import { MongoPublishRepository } from "@/lib/cloud-publish/store";

type Context = { params: Promise<{ id: string }> };

export async function POST(_: Request, context: Context) {
  try {
    const owner = await requireOwner();
    const { id } = await context.params;
    const publication = await publishDraft(new MongoPublishRepository(), owner, id, embedDocuments);
    return Response.json({
      document: { docId: publication.document.doc_id, status: publication.document.status },
      chunkCount: publication.chunks.length,
    });
  } catch (error) {
    return publishApiError(error);
  }
}
