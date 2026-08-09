import { describe, expect, it } from "vitest";

import { buildPublication, type DraftRecord } from "../lib/cloud-publish/publishing";
import { buildVectorPipeline, mapSource, mergeSpaceCandidates } from "../lib/cloud-rag/retrieval";
import {
  DEFAULT_SPACE_ID,
  normalizeSpaceIds,
  publicSpaceView,
  spaceFilter,
} from "../lib/cloud-rag/spaces";
import { retrieveRequestSchema } from "../lib/cloud-rag/validation";
import { DEFAULT_PROCESSING_PROFILE, buildChunkPreview } from "../lib/cloud-publish/processing";
import {
  DEFAULT_PUBLIC_SPACES,
  withTextSpaceFilter,
  withVectorSpaceFilter,
} from "../lib/cloud-publish/spaces";

describe("cloud knowledge spaces", () => {
  it("ships the three intended starter spaces", () => {
    expect(DEFAULT_PUBLIC_SPACES.map((space) => space.space_id)).toEqual(["portfolio", "rag-learning", "project-docs"]);
  });

  it("adds space filters to existing Atlas index definitions idempotently", () => {
    const vector = withVectorSpaceFilter({ fields: [{ type: "vector", path: "embedding", numDimensions: 3 }] });
    expect(vector.fields).toContainEqual({ type: "filter", path: "space_id" });
    expect(withVectorSpaceFilter(vector)).toEqual(vector);

    const text = withTextSpaceFilter({ mappings: { dynamic: false, fields: { body: { type: "string" } } } });
    expect(text.mappings.fields.space_id).toEqual({ type: "token" });
    expect(withTextSpaceFilter(text)).toEqual(text);
  });

  it("defaults empty selections to portfolio and rejects more than five spaces", () => {
    expect(normalizeSpaceIds()).toEqual([DEFAULT_SPACE_ID]);
    expect(normalizeSpaceIds([])).toEqual([DEFAULT_SPACE_ID]);
    expect(normalizeSpaceIds([" rag-learning ", "rag-learning", "project_docs"])).toEqual([
      "rag-learning",
      "project-docs",
    ]);
    expect(() => normalizeSpaceIds(["a", "b", "c", "d", "e", "f"])).toThrow(/five/i);
  });

  it("builds MongoDB filters for one or several spaces", () => {
    expect(spaceFilter(["portfolio"])).toEqual({ space_id: "portfolio" });
    expect(spaceFilter(["portfolio", "rag-learning"])).toEqual({
      space_id: { $in: ["portfolio", "rag-learning"] },
    });
  });

  it("only exposes active public space fields", () => {
    expect(publicSpaceView({
      space_id: "portfolio",
      name: "Portfolio",
      description: "Public portfolio evidence",
      status: "active",
      document_count: 27,
      owner_id: "secret",
    })).toEqual({
      spaceId: "portfolio",
      name: "Portfolio",
      description: "Public portfolio evidence",
      status: "active",
      documentCount: 27,
    });
  });

  it("validates space selections on retrieve requests", () => {
    const parsed = retrieveRequestSchema.parse({ question: "Which RAG projects?", settings: { topK: 5, scoreThreshold: null } });
    expect(parsed.settings.spaceIds).toEqual(["portfolio"]);
    expect(() => retrieveRequestSchema.parse({
      question: "compare",
      settings: { topK: 5, scoreThreshold: null, spaceIds: ["a", "b", "c", "d", "e", "f"] },
    })).toThrow();
  });

  it("adds the selected space to vector filters and mapped sources", () => {
    const pipeline = buildVectorPipeline([0.1, 0.2], 5, 30, ["rag-learning"]);
    expect(pipeline[0]).toMatchObject({ $vectorSearch: { filter: { visibility: "public", space_id: "rag-learning" } } });
    expect(mapSource({
      visibility: "public",
      validity_status: "active",
      doc_id: "d1",
      chunk_id: "c1",
      title: "RAG Notes",
      body: "Evidence",
      score: 0.9,
      space_id: "rag-learning",
      space_name: "RAG Learning",
      metadata: { language: "en" },
    })).toMatchObject({ spaceId: "rag-learning", spaceName: "RAG Learning" });
  });

  it("publishes documents and chunks into the draft target space", () => {
    const cleanedBody = "A unique public project statement without PII.";
    const preview = buildChunkPreview(cleanedBody, DEFAULT_PROCESSING_PROFILE, { title: "Project" });
    const draft: DraftRecord = {
      draftId: "draft-1",
      ownerId: "owner-1",
      spaceId: "project-docs",
      title: "Project",
      summary: "",
      category: "project",
      language: "en",
      parsedBody: cleanedBody,
      cleanedBody,
      processingProfile: DEFAULT_PROCESSING_PROFILE,
      preview,
      piiFindings: [],
      status: "ready",
      publicationVersion: 1,
    };
    const publication = buildPublication(draft, preview.children.map(() => [0.1, 0.2]));
    expect(publication.document.space_id).toBe("project-docs");
    expect(publication.chunks.every((chunk) => chunk.space_id === "project-docs")).toBe(true);
  });

  it("reserves evidence from every selected space before filling remaining Top-K slots", () => {
    const source = (spaceId: string, chunkId: string, score: number) => ({
      docId: `${spaceId}-doc`, chunkId, title: chunkId, category: "test", language: "en" as const,
      snippet: chunkId, score, spaceId, spaceName: spaceId,
    });
    const merged = mergeSpaceCandidates([
      [source("portfolio", "p1", 0.99), source("portfolio", "p2", 0.98), source("portfolio", "p3", 0.97)],
      [source("rag-learning", "r1", 0.7), source("rag-learning", "r2", 0.6)],
    ], 3, null);
    expect(merged.map((item) => item.chunkId)).toEqual(["p1", "r1", "p2"]);
  });
});
