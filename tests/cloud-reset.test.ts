import { describe, expect, it } from "vitest";

import {
  CLOUD_RESET_CONFIRMATION,
  buildCloudResetBackup,
  resetCloudCollections,
} from "../lib/cloud-publish/reset";
import { PublishConflictError } from "../lib/cloud-publish/publishing";

class FakeCursor {
  constructor(private readonly rows: Record<string, unknown>[]) {}
  sort() { return this; }
  async toArray() { return structuredClone(this.rows); }
}

class FakeCollection {
  deletedFilters: Record<string, unknown>[] = [];
  updates: Array<{ filter: Record<string, unknown>; update: Record<string, unknown> }> = [];

  constructor(public rows: Record<string, unknown>[]) {}
  find() { return new FakeCursor(this.rows); }
  async deleteMany(filter: Record<string, unknown>) {
    this.deletedFilters.push(filter);
    const before = this.rows.length;
    if (Object.keys(filter).length === 0) this.rows = [];
    else if (filter.space_id && typeof filter.space_id === "object") {
      this.rows = this.rows.filter((row) => row.space_id === "portfolio");
    }
    return { deletedCount: before - this.rows.length };
  }
  async updateOne(filter: Record<string, unknown>, update: Record<string, unknown>) {
    this.updates.push({ filter, update });
    return { matchedCount: 1, upsertedCount: 0 };
  }
}

function collections() {
  return {
    spaces: new FakeCollection([
      { _id: "s1", space_id: "portfolio", name: "Portfolio" },
      { _id: "s2", space_id: "other", name: "Other" },
    ]),
    drafts: new FakeCollection([{ _id: "r1", draft_id: "draft-1", cleaned_body: "Draft" }]),
    documents: new FakeCollection([{ _id: "d1", doc_id: "doc-1", cleaned_body: "Document" }]),
    chunks: new FakeCollection([{ _id: "c1", chunk_id: "chunk-1", body: "Evidence", embedding: [1, 2, 3] }]),
    metadata: new FakeCollection([{ _id: "repo_seed_embedding", model: "gemini-embedding-001" }]),
  };
}

describe("owner cloud knowledge reset", () => {
  it("exports every managed collection without embeddings and creates a stable fingerprint", async () => {
    const source = collections();
    const first = await buildCloudResetBackup(source);
    const second = await buildCloudResetBackup(source);

    expect(first.fingerprint).toBe(second.fingerprint);
    expect(first.snapshot).toEqual({ spaces: 2, drafts: 1, documents: 1, chunks: 1, metadata: 1 });
    expect(first.data.chunks[0]).not.toHaveProperty("embedding");
  });

  it("requires exact confirmation and rejects stale downloaded backups", async () => {
    const source = collections();
    const backup = await buildCloudResetBackup(source);

    await expect(resetCloudCollections(source, "wrong", backup.fingerprint)).rejects.toThrow(/RESET PORTFOLIO/);
    source.documents.rows.push({ doc_id: "new-document", cleaned_body: "Changed after download" });
    await expect(
      resetCloudCollections(source, CLOUD_RESET_CONFIRMATION, backup.fingerprint),
    ).rejects.toBeInstanceOf(PublishConflictError);
  });

  it("clears managed knowledge data and preserves a single active Portfolio space", async () => {
    const source = collections();
    const backup = await buildCloudResetBackup(source);
    const result = await resetCloudCollections(source, CLOUD_RESET_CONFIRMATION, backup.fingerprint);

    expect(result.deleted).toEqual({ drafts: 1, documents: 1, chunks: 1, metadata: 1, spaces: 1 });
    expect(source.spaces.rows).toHaveLength(1);
    expect(source.spaces.updates[0]?.filter).toEqual({ space_id: "portfolio" });
    expect(source.drafts.rows).toEqual([]);
    expect(source.documents.rows).toEqual([]);
    expect(source.chunks.rows).toEqual([]);
  });
});
