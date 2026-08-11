import { requireOwner } from "@/lib/cloud-publish/auth";
import { publishApiError } from "@/lib/cloud-publish/http";
import { resetCloudKnowledge } from "@/lib/cloud-publish/reset";


export async function POST(request: Request) {
  try {
    await requireOwner();
    const body = await request.json();
    const result = await resetCloudKnowledge(
      String(body.confirmation || ""),
      String(body.fingerprint || ""),
    );
    return Response.json(result);
  } catch (error) {
    return publishApiError(error);
  }
}
