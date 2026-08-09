import { requireOwner } from "@/lib/cloud-publish/auth";
import { publishApiError } from "@/lib/cloud-publish/http";
import { listOwnerWorkspace } from "@/lib/cloud-publish/store";

export async function GET() {
  try {
    const owner = await requireOwner();
    return Response.json(await listOwnerWorkspace(owner));
  } catch (error) {
    return publishApiError(error);
  }
}
