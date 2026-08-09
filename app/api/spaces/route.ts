import { listPublicSpaces } from "@/lib/cloud-publish/spaces";

export const runtime = "nodejs";

export async function GET() {
  try {
    return Response.json({ spaces: await listPublicSpaces() });
  } catch {
    return Response.json({ error: "Knowledge spaces are temporarily unavailable." }, { status: 503 });
  }
}

