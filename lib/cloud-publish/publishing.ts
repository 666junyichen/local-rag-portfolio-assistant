import { createHash } from "node:crypto";

import type { OwnerIdentity } from "./auth";
import { assertDraftPublishable, publicHttpUrl } from "./contracts";
import type { ChunkPreview, PiiFinding, ProcessingProfile } from "./processing";

export type DraftStatus = "draft" | "ready" | "publishing" | "published" | "failed";

export type DraftRecord = {
  draftId: string;
  docId?: string;
  ownerId: string;
  spaceId: string;
  title: string;
  summary: string;
  category: string;
  language: "zh" | "en";
  sourceUrl?: string;
  fileName?: string;
  fileType?: string;
  parsedBody: string;
  cleanedBody: string;
  processingProfile: ProcessingProfile;
  preview: ChunkPreview;
  piiFindings: PiiFinding[];
  status: DraftStatus;
  publicationVersion: number;
};

export type Publication = {
  document: Record<string, unknown>;
  chunks: Array<Record<string, unknown>>;
};

export interface PublishRepository {
  getDraft(ownerId: string, draftId: string): Promise<DraftRecord | null>;
  claimDraft(ownerId: string, draftId: string): Promise<DraftRecord | null>;
  getPublication(ownerId: string, docId: string): Promise<Publication | null>;
  commitPublication(publication: Publication, draft: DraftRecord): Promise<void>;
  markDraftFailure(ownerId: string, draftId: string, reason: string): Promise<void>;
}

export type EmbedDocuments = (texts: string[]) => Promise<number[][]>;

const digest = (value: string, size = 24) => createHash("sha256").update(value, "utf8").digest("hex").slice(0, size);

export class PublishQuotaUnavailableError extends Error {
  constructor() {
    super("Gemini free quota is temporarily unavailable. The draft was kept for a later retry.");
    this.name = "PublishQuotaUnavailableError";
  }
}

export class PublishConflictError extends Error {
  constructor(message = "This draft is already being published. Refresh the workspace before retrying.") {
    super(message);
    this.name = "PublishConflictError";
  }
}

export function buildPublication(draft: DraftRecord, embeddings: number[][], now = new Date()): Publication {
  assertDraftPublishable(
    { status: draft.status, piiFindings: draft.piiFindings, cleanedBody: draft.cleanedBody },
    ["ready", "publishing"],
  );
  if (embeddings.length !== draft.preview.children.length || embeddings.some((item) => !item.length)) {
    throw new Error("Embedding count does not match the preview chunks");
  }
  const docId = draft.docId || `owner_${digest(`${draft.ownerId}:${draft.draftId}`)}`;
  const contentHash = digest(draft.cleanedBody, 64);
  const version = Math.max(1, draft.publicationVersion || 1);
  const sourceUrl = publicHttpUrl(draft.sourceUrl);
  const spaceId = draft.spaceId || "portfolio";
  const document = {
    doc_id: docId,
    owner_id: draft.ownerId,
    source_origin: "owner_upload",
    space_id: spaceId,
    title: draft.title.trim(),
    summary: draft.summary.trim(),
    category: draft.category.trim() || "portfolio",
    language: draft.language,
    cleaned_body: draft.cleanedBody,
    content_hash: contentHash,
    processing_profile: draft.processingProfile,
    status: "published",
    visibility: "public",
    publication_version: version,
    file_name: draft.fileName || null,
    file_type: draft.fileType || null,
    source_url: sourceUrl || null,
    updated_at: now,
    published_at: now,
  };
  const chunks = draft.preview.children.map((chunk, index) => ({
    doc_id: docId,
    chunk_id: `${docId}_v${version}_${digest(`${chunk.chunkId}:${chunk.retrievalText}`, 16)}`,
    parent_chunk_id: chunk.parentChunkId,
    source_origin: "owner_upload",
    space_id: spaceId,
    owner_id: draft.ownerId,
    title: draft.title.trim(),
    summary: draft.summary.trim(),
    body: chunk.parentBody,
    raw_body: chunk.parentBody,
    child_body: chunk.rawBody,
    parent_body: chunk.parentBody,
    retrieval_text: chunk.retrievalText,
    section_path: chunk.sectionPath,
    section_type: chunk.sectionType,
    entity_title: chunk.entityTitle,
    semantic_group_id: chunk.semanticGroupId,
    token_count: chunk.tokenCount,
    embedding: embeddings[index],
    visibility: "public",
    validity_status: "active",
    publication_version: version,
    content_hash: contentHash,
    url: sourceUrl || null,
    metadata: {
      category: draft.category.trim() || "portfolio",
      language: draft.language,
      visibility: "public",
      source_origin: "owner_upload",
      space_id: spaceId,
      entity_title: chunk.entityTitle,
      semantic_group_id: chunk.semanticGroupId,
      parent_chunk_id: chunk.parentChunkId,
    },
    updated_at: now,
  }));
  return { document, chunks };
}

export async function publishDraft(
  repository: PublishRepository,
  owner: OwnerIdentity,
  draftId: string,
  embedDocuments: EmbedDocuments,
): Promise<Publication> {
  const draft = await repository.getDraft(owner.userId, draftId);
  if (!draft) throw new Error("Draft not found");
  if (draft.ownerId !== owner.userId) throw new Error("Draft not found");

  if (draft.status === "published" && draft.docId) {
    const existing = await repository.getPublication(owner.userId, draft.docId);
    if (existing) return existing;
    throw new PublishConflictError("The draft is marked published, but its publication could not be loaded.");
  }
  assertDraftPublishable({ status: draft.status, piiFindings: draft.piiFindings, cleanedBody: draft.cleanedBody });

  const claimed = await repository.claimDraft(owner.userId, draftId);
  if (!claimed) {
    const latest = await repository.getDraft(owner.userId, draftId);
    if (latest?.status === "published" && latest.docId) {
      const existing = await repository.getPublication(owner.userId, latest.docId);
      if (existing) return existing;
    }
    throw new PublishConflictError();
  }

  let embeddings: number[][];
  try {
    embeddings = await embedDocuments(claimed.preview.children.map((chunk) => chunk.retrievalText));
  } catch (error) {
    const message = error instanceof Error ? error.message : "";
    if (/\b429\b|quota|resource exhausted/i.test(message)) {
      await repository.markDraftFailure(owner.userId, draftId, "free_quota_unavailable");
      throw new PublishQuotaUnavailableError();
    }
    await repository.markDraftFailure(owner.userId, draftId, "embedding_provider_unavailable");
    throw error;
  }

  const publication = buildPublication(claimed, embeddings);
  await repository.commitPublication(publication, claimed);
  return publication;
}
