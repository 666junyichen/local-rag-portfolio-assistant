import { describe, expect, it } from "vitest";

import {
  DEFAULT_PROCESSING_PROFILE,
  SHARED_PROCESSING_PROFILES,
  estimateTokens,
  recommendProcessingProfile,
} from "../lib/cloud-publish/processing";


describe("shared processing profiles", () => {
  it("uses the canonical parent-child profile as the cloud default", () => {
    expect(DEFAULT_PROCESSING_PROFILE).toEqual(SHARED_PROCESSING_PROFILES.parent_child);
  });

  it("maps the canonical resume profile into the cloud upload contract", () => {
    expect(recommendProcessingProfile({ fileName: "candidate-resume.docx" })).toEqual(
      SHARED_PROCESSING_PROFILES.resume_semantic,
    );
  });

  it("uses the same deterministic multilingual token count as local Python", () => {
    expect(estimateTokens("MongoDB Vector Search v2.0 + RAG / BM25.")).toBe(8);
    expect(estimateTokens("检索RAG")).toBe(3);
  });
});
