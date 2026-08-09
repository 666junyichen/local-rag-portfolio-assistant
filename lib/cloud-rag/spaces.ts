import type { Document, Filter } from "mongodb";

export const DEFAULT_SPACE_ID = "portfolio";
export const MAX_SELECTED_SPACES = 5;

export type KnowledgeSpace = {
  spaceId: string;
  name: string;
  description: string;
  status: "active" | "archived";
  documentCount: number;
};

const SPACE_ID_PATTERN = /^[a-z0-9][a-z0-9-]{0,47}$/;

export function normalizeSpaceIds(raw?: string[]): string[] {
  const values = (raw || [])
    .map((value) => String(value || "").trim().toLowerCase().replace(/_/g, "-"))
    .filter(Boolean);
  const unique = [...new Set(values)];
  const result = unique.length ? unique : [DEFAULT_SPACE_ID];
  if (result.length > MAX_SELECTED_SPACES) throw new Error("Select no more than five knowledge spaces");
  if (result.some((value) => !SPACE_ID_PATTERN.test(value))) throw new Error("Invalid knowledge space identifier");
  return result;
}

export function spaceFilter(raw?: string[]): Document {
  const spaceIds = normalizeSpaceIds(raw);
  return spaceIds.length === 1 ? { space_id: spaceIds[0] } : { space_id: { $in: spaceIds } };
}

export function publicSpaceView(row: Document): KnowledgeSpace {
  return {
    spaceId: String(row.space_id || DEFAULT_SPACE_ID),
    name: String(row.name || "Portfolio"),
    description: String(row.description || ""),
    status: row.status === "archived" ? "archived" : "active",
    documentCount: Number(row.document_count || 0),
  };
}

export function activeSpaceFilter(raw?: string[]): Filter<Document> {
  return { status: "active", ...spaceFilter(raw) };
}

