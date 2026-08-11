import { requireOwner } from "@/lib/cloud-publish/auth";
import { publishApiError } from "@/lib/cloud-publish/http";
import { exportOwnerDocuments } from "@/lib/cloud-publish/store";
import { exportCloudResetBackup } from "@/lib/cloud-publish/reset";

export async function GET(request: Request) {
  try {
    const owner = await requireOwner();
    const resetScope = new URL(request.url).searchParams.get("scope") === "reset";
    const payload = resetScope
      ? { exportedAt: new Date().toISOString(), ...(await exportCloudResetBackup()) }
      : { exportedAt: new Date().toISOString(), documents: await exportOwnerDocuments(owner) };
    const body = JSON.stringify(payload, null, 2);
    return new Response(body, {
      headers: {
        "Content-Type": "application/json; charset=utf-8",
        "Content-Disposition": `attachment; filename=${resetScope ? "portfolio-reset-backup.json" : "portfolio-public-documents.json"}`,
      },
    });
  } catch (error) {
    return publishApiError(error);
  }
}
