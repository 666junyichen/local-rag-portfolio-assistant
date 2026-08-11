import { requireOwner } from "@/lib/cloud-publish/auth";
import { publishApiError } from "@/lib/cloud-publish/http";
import { previewCloudReset } from "@/lib/cloud-publish/reset";


export async function POST() {
  try {
    await requireOwner();
    return Response.json(await previewCloudReset());
  } catch (error) {
    return publishApiError(error);
  }
}
