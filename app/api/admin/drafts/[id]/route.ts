import { requireOwner } from "@/lib/cloud-publish/auth";
import { publishApiError } from "@/lib/cloud-publish/http";
import { getOwnerDraft, updateOwnerDraft } from "@/lib/cloud-publish/store";

type Context = { params: Promise<{ id: string }> };

export async function GET(_: Request, context: Context) {
  try {
    const owner = await requireOwner();
    const { id } = await context.params;
    const draft = await getOwnerDraft(owner, id);
    if (!draft) return Response.json({ error: "Resource not found" }, { status: 404 });
    return Response.json({ draft });
  } catch (error) {
    return publishApiError(error);
  }
}

export async function PATCH(request: Request, context: Context) {
  try {
    const owner = await requireOwner();
    const { id } = await context.params;
    const body = await request.json();
    const draft = await updateOwnerDraft(owner, id, body && typeof body === "object" ? body : {});
    return Response.json({ draft, previewInvalidated: true });
  } catch (error) {
    return publishApiError(error);
  }
}
