export type PublishableDraft = {
  status?: string;
  piiFindings?: Array<{ kind?: string; blocking?: boolean }>;
  cleanedBody?: string;
};

export function assertDraftPublishable(
  draft: PublishableDraft,
  allowedStatuses: string[] = ["ready"],
): void {
  if (!draft.status || !allowedStatuses.includes(draft.status)) {
    throw new Error("Draft is not ready to publish");
  }
  if (draft.piiFindings?.some((finding) => finding.blocking)) {
    throw new Error("PII must be removed before publishing");
  }
  if (draft.cleanedBody !== undefined && !draft.cleanedBody.trim()) {
    throw new Error("Cleaned document body is empty");
  }
}

function iso(value: unknown): string {
  const date = value instanceof Date ? value : new Date(String(value || ""));
  return Number.isNaN(date.valueOf()) ? "" : date.toISOString();
}

export function publicHttpUrl(value: unknown): string | undefined {
  const raw = String(value || "").trim();
  if (!raw) return undefined;
  try {
    const url = new URL(raw);
    return url.protocol === "http:" || url.protocol === "https:" ? raw : undefined;
  } catch {
    return undefined;
  }
}

export function publicDocumentView(doc: Record<string, unknown>) {
  const sourceUrl = publicHttpUrl(doc.source_url);
  return {
    docId: String(doc.doc_id || ""),
    spaceId: String(doc.space_id || "portfolio"),
    spaceName: String(doc.space_name || "Portfolio"),
    title: String(doc.title || "Untitled"),
    summary: String(doc.summary || ""),
    category: String(doc.category || "portfolio"),
    language: doc.language === "zh" ? "zh" : "en",
    updatedAt: iso(doc.updated_at || doc.published_at),
    ...(sourceUrl ? { sourceUrl } : {}),
  };
}

export function seedOwnedFilter(activeDocIds: string[]) {
  return { source_origin: "repo_seed", doc_id: { $nin: activeDocIds } };
}

const EXPORT_DENYLIST = new Set(["_id", "embedding", "owner_id", "owner_email"]);

export function toOwnerExport(doc: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(Object.entries(doc).filter(([key]) => !EXPORT_DENYLIST.has(key)));
}
