import { requireOwner } from "@/lib/cloud-publish/auth";
import { publishApiError } from "@/lib/cloud-publish/http";
import { exportOwnerDocuments } from "@/lib/cloud-publish/store";

export async function GET() {
  try {
    const owner = await requireOwner();
    const body = JSON.stringify({ exportedAt: new Date().toISOString(), documents: await exportOwnerDocuments(owner) }, null, 2);
    return new Response(body, {
      headers: {
        "Content-Type": "application/json; charset=utf-8",
        "Content-Disposition": "attachment; filename=portfolio-public-documents.json",
      },
    });
  } catch (error) {
    return publishApiError(error);
  }
}
