import { describe, expect, it } from "vitest";

import * as promptModule from "../lib/cloud-rag/prompt";
import * as retrievalModule from "../lib/cloud-rag/retrieval";
import type { Source } from "../lib/cloud-rag/types";

const source = (
  chunkId: string,
  parentChunkId: string,
  semanticGroupId: string,
  score: number,
): Source => ({
  docId: "resume",
  chunkId,
  parentChunkId,
  semanticGroupId,
  sectionType: "project",
  entityTitle: `Project ${semanticGroupId}`,
  title: "Master Resume",
  category: "project",
  language: "en",
  snippet: `Parent evidence for ${semanticGroupId}`,
  matchedSnippet: `Matched child ${chunkId}`,
  score,
  spaceId: "portfolio",
  spaceName: "Portfolio",
});

describe("cloud parent context and answer intent", () => {
  it("maps child diagnostics and parent metadata without replacing parent evidence", () => {
    const mapped = retrievalModule.mapSource({
      visibility: "public",
      validity_status: "active",
      doc_id: "resume",
      chunk_id: "child-1",
      parent_chunk_id: "parent-1",
      semantic_group_id: "project-rag",
      section_type: "project",
      entity_title: "Local RAG Portfolio Assistant",
      child_body: "MongoDB Vector Search and Ollama",
      parent_body: "Local RAG Portfolio Assistant combines retrieval and grounded generation.",
      score: 0.91,
    });

    expect(mapped).toMatchObject({
      parentChunkId: "parent-1",
      semanticGroupId: "project-rag",
      sectionType: "project",
      entityTitle: "Local RAG Portfolio Assistant",
      matchedSnippet: "MongoDB Vector Search and Ollama",
      snippet: "Local RAG Portfolio Assistant combines retrieval and grounded generation.",
    });
  });

  it("keeps child candidates but selects one highest-scoring context per parent and semantic group", () => {
    const selectParentContext = (retrievalModule as unknown as {
      selectParentContext?: (candidates: Source[], intent: string, topK: number) => Source[];
    }).selectParentContext;
    expect(typeof selectParentContext).toBe("function");
    if (!selectParentContext) return;

    const candidates = [
      source("child-1", "parent-1", "rag", 0.95),
      source("child-2", "parent-1", "rag", 0.92),
      source("child-3", "parent-2", "qanet", 0.9),
    ];
    const selected = selectParentContext(candidates, "fact", 5);

    expect(candidates).toHaveLength(3);
    expect(selected.map((item) => item.chunkId)).toEqual(["child-1", "child-3"]);
  });

  it("uses 12 unique entities for exhaustive questions, 3-5 for strongest questions, and topK for facts", () => {
    const selectParentContext = (retrievalModule as unknown as {
      selectParentContext?: (candidates: Source[], intent: string, topK: number) => Source[];
    }).selectParentContext;
    expect(typeof selectParentContext).toBe("function");
    if (!selectParentContext) return;

    const candidates = Array.from({ length: 15 }, (_, index) => source(
      `child-${index}`,
      `parent-${index}`,
      `project-${index}`,
      1 - index / 100,
    ));
    expect(selectParentContext(candidates, "exhaustive", 2)).toHaveLength(12);
    expect(selectParentContext(candidates, "ranked", 1)).toHaveLength(3);
    expect(selectParentContext(candidates, "ranked", 10)).toHaveLength(5);
    expect(selectParentContext(candidates, "fact", 2)).toHaveLength(2);
  });

  it("keeps ranked and exhaustive project questions focused on project parents", () => {
    const candidates = [
      { ...source("skill", "skill-parent", "skills", 0.99), sectionType: "skill", entityTitle: "AI skills" },
      source("rag", "rag-parent", "rag", 0.95),
      { ...source("internship", "intern-parent", "internship", 0.94), sectionType: "internship", entityTitle: "AI internship" },
      source("qanet", "qanet-parent", "qanet", 0.93),
      source("accessibility", "accessibility-parent", "accessibility", 0.92),
    ];

    expect(retrievalModule.selectParentContext(candidates, "ranked", 5, "最强的 AI 项目有哪些？")
      .map((item) => item.sectionType)).toEqual(["project", "project", "project"]);
    expect(retrievalModule.selectParentContext(candidates, "exhaustive", 5, "What are all AI projects?")
      .map((item) => item.sectionType)).toEqual(["project", "project", "project"]);
    expect(retrievalModule.selectParentContext(candidates, "fact", 2, "What AI skills are documented?")
      .map((item) => item.sectionType)).toEqual(["skill", "project"]);
  });

  it("classifies strongest questions before exhaustive wording and adds intent-specific prompt rules", () => {
    const classifyAnswerIntent = (promptModule as unknown as {
      classifyAnswerIntent?: (question: string) => string;
    }).classifyAnswerIntent;
    expect(typeof classifyAnswerIntent).toBe("function");
    if (!classifyAnswerIntent) return;

    expect(classifyAnswerIntent("Junyi 最强的 AI 项目有哪些？")).toBe("ranked");
    expect(classifyAnswerIntent("Junyi 有哪些 AI 项目？")).toBe("exhaustive");
    expect(classifyAnswerIntent("Junyi 的 MongoDB 项目叫什么？")).toBe("fact");

    const sources = [source("child-1", "parent-1", "rag", 0.9)];
    const exhaustivePrompt = promptModule.buildPrompt("有哪些项目？", sources, [], "zh", "exhaustive");
    const rankedPrompt = promptModule.buildPrompt("最强项目？", sources, [], "zh", "ranked");
    expect(exhaustivePrompt).toContain("12");
    expect(exhaustivePrompt).toContain("distinct");
    expect(rankedPrompt).toContain("3-5");
    expect(rankedPrompt).toContain("selection criteria");
  });
});
