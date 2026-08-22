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

  it("requires an explicit apply flag and confirmation phrase before database writes", () => {
    expect(script).toContain('--apply');
    expect(script).toContain('--confirm=SEED_PUBLIC_PORTFOLIO');
    expect(script).toContain('Seed is validation-only by default');
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

  it("allows an empty repository seed and still cleans only repo_seed catalog records", async () => {
    // @ts-expect-error The executable seed script intentionally has no declaration file.
    const { normalizePublicDocuments, syncRepoSeedCatalog } = await import("../scripts/seed-atlas.mjs");
    const documents = normalizePublicDocuments([]);
    const calls: Array<{ method: string; value: unknown }> = [];
    const documentsCollection = {
      bulkWrite: async (value: unknown) => calls.push({ method: "bulkWrite", value }),
      deleteMany: async (value: unknown) => calls.push({ method: "deleteMany", value }),
    };

    await syncRepoSeedCatalog({ documentsCollection, documents, session: {}, now: new Date("2026-08-22T00:00:00Z") });

    expect(documents).toEqual([]);
    expect(calls).toEqual([
      { method: "deleteMany", value: { source_origin: "repo_seed", doc_id: { $nin: [] } } },
    ]);
  });

  it("assigns repository seed documents to the default Portfolio space", async () => {
    // @ts-expect-error The executable seed script intentionally has no declaration file.
    const { chunkDocuments, normalizePublicDocuments } = await import("../scripts/seed-atlas.mjs");
    const [document] = normalizePublicDocuments([{ title: "Public note", body: "Unique public evidence." }]);
    const [chunk] = chunkDocuments([document]);
    expect(document.space_id).toBe("portfolio");
    expect(chunk.space_id).toBe("portfolio");
    expect(chunk.metadata.space_name).toBe("Portfolio");
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

  it("supports a spaces-only migration that never calls Gemini embeddings", () => {
    expect(script).toContain("--spaces-only");
    expect(script).toContain("Space migration complete without generating embeddings");
  });

  it("reconciles the public text index without deleting unrelated Atlas indexes", async () => {
    // @ts-expect-error The executable seed script intentionally has no declaration file.
    const { reconcilePublicTextIndex } = await import("../scripts/seed-atlas.mjs");
    const calls: Array<{ method: string; value: unknown }> = [];
    const collection = {
      createSearchIndex: async (value: unknown) => calls.push({ method: "createSearchIndex", value }),
      updateSearchIndex: async (name: string, definition: unknown) => calls.push({ method: "updateSearchIndex", value: { name, definition } }),
      dropSearchIndex: async (name: string) => calls.push({ method: "dropSearchIndex", value: name }),
    };

    await expect(reconcilePublicTextIndex(collection, [], "text_index_public")).resolves.toEqual({
      name: "text_index_public",
      status: "created",
      available: true,
    });

    expect(calls).toEqual([
      expect.objectContaining({
        method: "createSearchIndex",
        value: expect.objectContaining({ name: "text_index_public", type: "search" }),
      }),
    ]);
    expect(calls.some((call) => call.method === "dropSearchIndex")).toBe(false);
  });

  it("adds missing public text index fields without overwriting existing analyzers", async () => {
    // @ts-expect-error The executable seed script intentionally has no declaration file.
    const { reconcilePublicTextIndex } = await import("../scripts/seed-atlas.mjs");
    const calls: Array<{ method: string; value: unknown }> = [];
    const collection = {
      createSearchIndex: async (value: unknown) => calls.push({ method: "createSearchIndex", value }),
      updateSearchIndex: async (name: string, definition: unknown) => calls.push({ method: "updateSearchIndex", value: { name, definition } }),
    };
    const existing = {
      name: "text_index_public",
      latestDefinition: {
        analyzer: "lucene.english",
        mappings: {
          dynamic: true,
          fields: {
            title: { type: "string", analyzer: "lucene.english" },
            body: { type: "string" },
          },
        },
      },
    };

    await expect(reconcilePublicTextIndex(collection, [existing], "text_index_public")).resolves.toMatchObject({
      name: "text_index_public",
      status: "updated",
      available: true,
      addedFields: expect.arrayContaining(["space_id", "retrieval_text"]),
    });

    expect(calls).toHaveLength(1);
    const update = calls[0]?.value as { name: string; definition: { analyzer: string; mappings: { dynamic: boolean; fields: Record<string, unknown> } } };
    expect(update.name).toBe("text_index_public");
    expect(update.definition.analyzer).toBe("lucene.english");
    expect(update.definition.mappings.dynamic).toBe(true);
    expect(update.definition.mappings.fields.title).toEqual({ type: "string", analyzer: "lucene.english" });
    expect(update.definition.mappings.fields.space_id).toEqual({ type: "token" });
    expect(calls.some((call) => call.method === "createSearchIndex")).toBe(false);
  });
});
