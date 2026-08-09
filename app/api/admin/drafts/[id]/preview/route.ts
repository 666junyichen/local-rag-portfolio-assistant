import { requireOwner } from "@/lib/cloud-publish/auth";
import { publishApiError } from "@/lib/cloud-publish/http";
import { previewOwnerDraft } from "@/lib/cloud-publish/store";

type Context = { params: Promise<{ id: string }> };

export async function POST(_: Request, context: Context) {
  try {
    const owner = await requireOwner();
    const { id } = await context.params;
    return Response.json({ draft: await previewOwnerDraft(owner, id) });
  } catch (error) {
    return publishApiError(error);
  }
}
