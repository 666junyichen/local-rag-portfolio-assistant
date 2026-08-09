import { requireOwner } from "@/lib/cloud-publish/auth";
import { publishApiError } from "@/lib/cloud-publish/http";
import { updateOwnerSpace } from "@/lib/cloud-publish/spaces";

export const runtime = "nodejs";

export async function PATCH(request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const owner = await requireOwner();
    const { id } = await params;
    const body = await request.json();
    const space = await updateOwnerSpace(owner, id, {
      ...(body.name !== undefined ? { name: String(body.name) } : {}),
      ...(body.description !== undefined ? { description: String(body.description) } : {}),
      ...(body.status === "active" || body.status === "archived" ? { status: body.status } : {}),
    });
    return Response.json({ space });
  } catch (error) {
    return publishApiError(error);
  }
}

