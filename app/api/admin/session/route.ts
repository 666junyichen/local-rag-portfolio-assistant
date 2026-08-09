import { requireOwner } from "@/lib/cloud-publish/auth";
import { publishApiError } from "@/lib/cloud-publish/http";

export async function GET() {
  try {
    const owner = await requireOwner();
    return Response.json({ owner: true, email: owner.email });
  } catch (error) {
    return publishApiError(error);
  }
}
