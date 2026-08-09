import { listPublicKnowledge } from "@/lib/cloud-publish/store";

export const runtime = "nodejs";

export async function GET(request: Request) {
  try {
    const url = new URL(request.url);
    const documents = await listPublicKnowledge(
      url.searchParams.get("q")?.slice(0, 100) || "",
      url.searchParams.get("category")?.slice(0, 50) || "",
      url.searchParams.getAll("spaceId"),
    );
    return Response.json({ documents });
  } catch {
    return Response.json({ error: "The public knowledge catalog is temporarily unavailable." }, { status: 503 });
  }
}
