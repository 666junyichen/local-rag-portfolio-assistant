import { requireOwner } from "@/lib/cloud-publish/auth";
import { publishApiError } from "@/lib/cloud-publish/http";
import { deleteOwnerDocument, moveOwnerDocument } from "@/lib/cloud-publish/store";

type Context = { params: Promise<{ id: string }> };

export async function DELETE(_: Request, context: Context) {
  try {
    const owner = await requireOwner();
    const { id } = await context.params;
    return Response.json(await deleteOwnerDocument(owner, id));
  } catch (error) {
    return publishApiError(error);
  }
}

export async function PATCH(request: Request, context: Context) {
  try {
    const owner = await requireOwner();
    const { id } = await context.params;
    const body = await request.json();
    return Response.json(await moveOwnerDocument(owner, id, String(body.spaceId || "")));
  } catch (error) {
    return publishApiError(error);
  }
}
