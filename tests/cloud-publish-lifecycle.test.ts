import { describe, expect, it, vi } from "vitest";

import {
  PublishConflictError,
  PublishQuotaUnavailableError,
  buildPublication,
  publishDraft,
  type DraftRecord,
  type PublishRepository,
} from "../lib/cloud-publish/publishing";
import { DEFAULT_PROCESSING_PROFILE, buildChunkPreview } from "../lib/cloud-publish/processing";

function readyDraft(overrides: Partial<DraftRecord> = {}): DraftRecord {
  const cleanedBody = "Portfolio RAG uses MongoDB Vector Search and Gemini for grounded public answers.";
  return {
    draftId: "draft-1",
    ownerId: "owner-1",
    title: "Portfolio RAG",
    summary: "A grounded portfolio assistant",
    category: "project",
    language: "en",
    cleanedBody,
    parsedBody: cleanedBody,
    processingProfile: DEFAULT_PROCESSING_PROFILE,
    preview: buildChunkPreview(cleanedBody, DEFAULT_PROCESSING_PROFILE, { title: "Portfolio RAG" }),
    piiFindings: [],
    status: "ready",
    publicationVersion: 1,
    ...overrides,
  };
}

describe("owner publication lifecycle", () => {
  it("builds deterministic public document and chunk identifiers", () => {
    const draft = readyDraft();
    const first = buildPublication(draft, draft.preview.children.map(() => [0.1, 0.2]));
    const second = buildPublication(draft, draft.preview.children.map(() => [0.1, 0.2]));

    expect(first.document.doc_id).toBe(second.document.doc_id);
    expect(first.chunks.map((chunk) => chunk.chunk_id)).toEqual(second.chunks.map((chunk) => chunk.chunk_id));
    expect(first.document.source_origin).toBe("owner_upload");
    expect(first.chunks.every((chunk) => chunk.visibility === "public" && chunk.validity_status === "active")).toBe(true);
    expect(first.chunks.every((chunk) => chunk.entity_title && chunk.semantic_group_id)).toBe(true);
    expect(first.chunks.every((chunk) => (
      (chunk.metadata as Record<string, unknown>).entity_title === chunk.entity_title
      && (chunk.metadata as Record<string, unknown>).semantic_group_id === chunk.semantic_group_id
    ))).toBe(true);
  });

  it("blocks PII before the embedding provider is called", async () => {
    const draft = readyDraft({ piiFindings: [{ kind: "email", label: "Email", start: 0, end: 4, preview: "masked", blocking: true }] });
    const repository = fakeRepository(draft);
    const embed = vi.fn();

    await expect(publishDraft(repository, { userId: "owner-1", email: "owner@example.com" }, "draft-1", embed)).rejects.toThrow(/PII/i);
    expect(embed).not.toHaveBeenCalled();
    expect(repository.commitPublication).not.toHaveBeenCalled();
  });

  it("commits one publication after all embeddings succeed", async () => {
    const draft = readyDraft();
    const repository = fakeRepository(draft);
    const embed = vi.fn(async (texts: string[]) => texts.map(() => [0.1, 0.2, 0.3]));

    const result = await publishDraft(repository, { userId: "owner-1", email: "owner@example.com" }, "draft-1", embed);

    expect(embed).toHaveBeenCalledOnce();
    expect(repository.claimDraft).toHaveBeenCalledOnce();
    expect(repository.commitPublication).toHaveBeenCalledOnce();
    expect(result.document.status).toBe("published");
  });

  it("returns the existing publication when a completed publish request is retried", async () => {
    const source = readyDraft({ docId: "owner-doc-1" });
    const existing = buildPublication(source, source.preview.children.map(() => [0.1, 0.2]));
    const repository = fakeRepository({ ...source, status: "published" }, { existing });
    const embed = vi.fn();

    const result = await publishDraft(repository, { userId: "owner-1", email: "owner@example.com" }, "draft-1", embed);

    expect(result).toEqual(existing);
    expect(embed).not.toHaveBeenCalled();
    expect(repository.claimDraft).not.toHaveBeenCalled();
    expect(repository.commitPublication).not.toHaveBeenCalled();
  });

  it("rejects a concurrent publish when another request already claimed the draft", async () => {
    const draft = readyDraft();
    const repository = fakeRepository(draft);
    repository.claimDraft.mockResolvedValueOnce(null);

    await expect(publishDraft(repository, { userId: "owner-1", email: "owner@example.com" }, "draft-1", vi.fn()))
      .rejects.toBeInstanceOf(PublishConflictError);
    expect(repository.commitPublication).not.toHaveBeenCalled();
  });

  it("keeps the draft and records a recoverable state when free Gemini quota is unavailable", async () => {
    const draft = readyDraft();
    const repository = fakeRepository(draft);
    const embed = vi.fn().mockRejectedValue(new Error("Gemini request failed (429)"));

    await expect(publishDraft(repository, { userId: "owner-1", email: "owner@example.com" }, "draft-1", embed))
      .rejects.toBeInstanceOf(PublishQuotaUnavailableError);
    expect(repository.markDraftFailure).toHaveBeenCalledWith("owner-1", "draft-1", "free_quota_unavailable");
    expect(repository.commitPublication).not.toHaveBeenCalled();
  });
});

function fakeRepository(
  draft: DraftRecord,
  options: { existing?: ReturnType<typeof buildPublication> } = {},
): PublishRepository & Record<string, ReturnType<typeof vi.fn>> {
  return {
    getDraft: vi.fn(async () => draft),
    claimDraft: vi.fn(async () => ({ ...draft, status: "publishing" as const })),
    getPublication: vi.fn(async () => options.existing || null),
    commitPublication: vi.fn(async () => undefined),
    markDraftFailure: vi.fn(async () => undefined),
  };
}
