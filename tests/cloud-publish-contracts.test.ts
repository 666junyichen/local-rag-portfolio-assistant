import { describe, expect, it } from "vitest";
import {
  assertDraftPublishable,
  publicDocumentView,
  seedOwnedFilter,
  toOwnerExport,
} from "../lib/cloud-publish/contracts";

describe("publish contracts", () => {
  it("blocks drafts that still contain PII", () => {
    expect(() => assertDraftPublishable({ status: "ready", piiFindings: [{ kind: "email", blocking: true }] })).toThrow(/PII/i);
    expect(() => assertDraftPublishable({ status: "ready", piiFindings: [] })).not.toThrow();
  });

  it("returns an allowlisted public knowledge view", () => {
    const view = publicDocumentView({
      doc_id: "doc-1",
      title: "Public RAG",
      summary: "A public summary",
      category: "project",
      language: "en",
      updated_at: new Date("2026-08-09T00:00:00Z"),
      source_url: "https://example.com",
      cleaned_body: "private implementation body",
      embedding: [0.1],
      owner_id: "secret-owner",
      status: "published",
    });
    expect(view).toEqual({
      docId: "doc-1",
      spaceId: "portfolio",
      spaceName: "Portfolio",
      title: "Public RAG",
      summary: "A public summary",
      category: "project",
      language: "en",
      updatedAt: "2026-08-09T00:00:00.000Z",
      sourceUrl: "https://example.com",
    });
  });

  it("never exposes non-HTTP source URLs", () => {
    const view = publicDocumentView({
      doc_id: "doc-unsafe",
      title: "Unsafe link",
      source_url: "javascript:alert(1)",
    });
    expect(view).not.toHaveProperty("sourceUrl");
  });

  it("scopes seed cleanup to repository-owned records", () => {
    expect(seedOwnedFilter(["doc-1", "doc-2"])).toEqual({
      source_origin: "repo_seed",
      doc_id: { $nin: ["doc-1", "doc-2"] },
    });
  });

  it("exports owner documents without embeddings or owner identifiers", () => {
    const exported = toOwnerExport({ doc_id: "doc-1", title: "RAG", cleaned_body: "Public text", embedding: [1], owner_id: "owner" });
    expect(exported).toMatchObject({ doc_id: "doc-1", title: "RAG", cleaned_body: "Public text" });
    expect(exported).not.toHaveProperty("embedding");
    expect(exported).not.toHaveProperty("owner_id");
  });
});
