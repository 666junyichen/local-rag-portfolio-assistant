import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

describe("cloud seed safety", () => {
  const script = fs.readFileSync(path.resolve(process.cwd(), "scripts/seed-atlas.mjs"), "utf8");

  it("never wipes owner-uploaded public knowledge", () => {
    expect(script).not.toContain("deleteMany({})");
    expect(script).toContain('source_origin: "repo_seed"');
    expect(script).toContain('source_origin: "owner_upload"');
  });

  it("maintains both the public document catalog and retrieval chunks", () => {
    expect(script).toContain("CLOUD_DOCUMENTS_COLLECTION_NAME");
    expect(script).toContain("portfolio_public_documents");
    expect(script).toContain("bulkWrite");
  });

  it("exports validation helpers and rejects duplicate document identifiers", () => {
    expect(script).toContain("export function normalizePublicDocuments");
    expect(script).toContain("Duplicate doc_id");
  });

  it("rejects duplicate doc_id values before connecting to Atlas", async () => {
    // @ts-expect-error The executable seed script intentionally has no declaration file.
    const { normalizePublicDocuments } = await import("../scripts/seed-atlas.mjs");
    const rows = [
      { doc_id: "same-id", title: "First", body: "First public body" },
      { doc_id: "same-id", title: "Second", body: "Second public body" },
    ];
    expect(() => normalizePublicDocuments(rows)).toThrow(/Duplicate doc_id/);
  });

  it("runs database writes in a transaction and records the embedding contract", () => {
    expect(script).toContain("withTransaction");
    expect(script).toContain("repo_seed_embedding");
    expect(script).toContain("numDimensions");
  });

  it("can backfill the public catalog without generating new embeddings", async () => {
    // @ts-expect-error The executable seed script intentionally has no declaration file.
    const { normalizePublicDocuments, syncRepoSeedCatalog } = await import("../scripts/seed-atlas.mjs");
    const documents = normalizePublicDocuments([
      { doc_id: "public-doc", title: "Public document", body: "Public evidence" },
    ]);
    const calls: Array<{ method: string; value: unknown }> = [];
    const documentsCollection = {
      bulkWrite: async (value: unknown) => calls.push({ method: "bulkWrite", value }),
      deleteMany: async (value: unknown) => calls.push({ method: "deleteMany", value }),
    };

    await syncRepoSeedCatalog({ documentsCollection, documents, session: {}, now: new Date("2026-08-09T00:00:00Z") });

    expect(script).toContain("--catalog-only");
    expect(calls).toHaveLength(2);
    expect(calls[0]?.value).toEqual(expect.arrayContaining([
      expect.objectContaining({
        updateOne: expect.objectContaining({
          filter: { source_origin: "repo_seed", doc_id: "public-doc" },
        }),
      }),
    ]));
    expect(calls[1]?.value).toEqual({ source_origin: "repo_seed", doc_id: { $nin: ["public-doc"] } });
  });
});
