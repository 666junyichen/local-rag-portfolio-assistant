import fs from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import {
  SHARED_PROCESSING_PROFILES,
  buildChunkPreview,
  type PreviewChunk,
} from "../lib/cloud-publish/processing";

type CaseName = keyof typeof SHARED_PROCESSING_PROFILES;

type ContractCase = {
  case_id: string;
  file: string;
  profile: CaseName;
  title: string;
};

const fixtureRoot = path.join(process.cwd(), "tests", "fixtures", "chunking");
const cases = JSON.parse(fs.readFileSync(path.join(fixtureRoot, "cases.json"), "utf8")) as ContractCase[];
const expected = JSON.parse(fs.readFileSync(path.join(fixtureRoot, "expected.json"), "utf8")) as {
  cases: Record<string, { parents: unknown[]; children: unknown[] }>;
};

function normalizePreview(parents: PreviewChunk[], children: PreviewChunk[]) {
  const semanticGroups = new Map<string, number>();
  const parentIds = new Map(parents.map((parent, index) => [parent.parentChunkId, index]));
  const normalize = (chunk: PreviewChunk) => {
    if (!semanticGroups.has(chunk.semanticGroupId)) {
      semanticGroups.set(chunk.semanticGroupId, semanticGroups.size);
    }
    return {
      raw_body: chunk.rawBody,
      section_type: chunk.sectionType,
      section_path: chunk.sectionPath,
      entity_title: chunk.entityTitle,
      token_count: chunk.tokenCount,
      retrieval_priority: chunk.retrievalPriority,
      semantic_group_index: semanticGroups.get(chunk.semanticGroupId),
    };
  };

  return {
    parents: parents.map(normalize),
    children: children.map((chunk) => ({
      ...normalize(chunk),
      parent_index: parentIds.get(chunk.parentChunkId),
    })),
  };
}

describe("Python and TypeScript chunking parity", () => {
  for (const contractCase of cases) {
    const caseId = contractCase.case_id;
    it(`matches the canonical Python contract for ${caseId}`, () => {
      const body = fs.readFileSync(path.join(fixtureRoot, contractCase.file), "utf8").trim();
      const preview = buildChunkPreview(
        body,
        SHARED_PROCESSING_PROFILES[contractCase.profile],
        { title: contractCase.title },
      );

      expect(normalizePreview(preview.parents, preview.children)).toEqual(expected.cases[caseId]);
    });
  }
});
