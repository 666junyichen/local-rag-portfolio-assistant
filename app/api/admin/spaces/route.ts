import { requireOwner } from "@/lib/cloud-publish/auth";
import { publishApiError } from "@/lib/cloud-publish/http";
import { createOwnerSpace, listOwnerSpaces } from "@/lib/cloud-publish/spaces";

export const runtime = "nodejs";

export async function GET() {
  try {
    const owner = await requireOwner();
    return Response.json({ spaces: await listOwnerSpaces(owner) });
  } catch (error) {
    return publishApiError(error);
  }
}

export async function POST(request: Request) {
  try {
    const owner = await requireOwner();
    const body = await request.json();
    const space = await createOwnerSpace(owner, {
      name: String(body.name || ""),
      description: String(body.description || ""),
    });
    return Response.json({ space }, { status: 201 });
  } catch (error) {
    return publishApiError(error);
  }
}

