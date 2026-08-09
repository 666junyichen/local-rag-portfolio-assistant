import { requireOwner } from "@/lib/cloud-publish/auth";
import { publishApiError } from "@/lib/cloud-publish/http";
import { PublishParseError, parseUpload } from "@/lib/cloud-publish/parsers";
import { createDrafts, listOwnerWorkspace } from "@/lib/cloud-publish/store";

export const runtime = "nodejs";

export async function GET() {
  try {
    const owner = await requireOwner();
    return Response.json(await listOwnerWorkspace(owner));
  } catch (error) {
    return publishApiError(error);
  }
}

export async function POST(request: Request) {
  try {
    const owner = await requireOwner();
    const form = await request.formData();
    const files = form.getAll("files").filter((item): item is File => item instanceof File).slice(0, 10);
    if (!files.length) return Response.json({ error: "Choose at least one file." }, { status: 400 });
    const parsed = [];
    const errors: Array<{ fileName: string; code: string; message: string }> = [];
    for (const file of files) {
      try {
        parsed.push(await parseUpload(file));
      } catch (error) {
        if (error instanceof PublishParseError) errors.push({ fileName: file.name, code: error.code, message: error.message });
        else errors.push({ fileName: file.name, code: "parse_failed", message: "The file could not be parsed." });
      }
    }
    const drafts = await createDrafts(owner, parsed, String(form.get("spaceId") || "portfolio"));
    return Response.json({ drafts, errors }, { status: errors.length ? 207 : 201 });
  } catch (error) {
    return publishApiError(error);
  }
}
