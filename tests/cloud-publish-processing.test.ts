import { describe, expect, it } from "vitest";
import {
  DEFAULT_PROCESSING_PROFILE,
  buildChunkPreview,
  cleanPublicText,
  detectPii,
} from "../lib/cloud-publish/processing";

describe("public document processing", () => {
  it("normalizes text and optionally removes URLs and email addresses", () => {
    const cleaned = cleanPublicText(
      "Project\tupdate\r\n\r\nContact me@example.com at https://example.com.\n\n\nDone",
      { ...DEFAULT_PROCESSING_PROFILE, removeEmails: true, removeUrls: true },
    );
    expect(cleaned).toBe("Project update\n\nContact at .\n\nDone");
  });

  it("detects publish-blocking PII without echoing the matched value", () => {
    const input = "Email: private@example.com\nPhone: +61 412 345 678\n身份证：11010519491231002X\n家庭住址：测试路 10 号";
    const findings = detectPii(input);
    expect(findings.map((finding) => finding.kind)).toEqual(["email", "phone", "national_id", "address"]);
    expect(JSON.stringify(findings)).not.toContain("private@example.com");
    expect(findings.every((finding) => finding.blocking)).toBe(true);
  });

  it("detects compact Chinese and Australian mobile numbers", () => {
    const findings = detectPii("CN: 13800138000\nAU: 0412345678");
    expect(findings.map((finding) => finding.kind)).toEqual(["phone", "phone"]);
  });

  it("indexes child chunks while retaining their parent answer context", () => {
    const text = Array.from({ length: 18 }, (_, index) => `Paragraph ${index + 1} describes MongoDB, RAG, retrieval, and project evidence.`).join("\n\n");
    const preview = buildChunkPreview(text, {
      ...DEFAULT_PROCESSING_PROFILE,
      chunkMode: "parent_child",
      childMaxTokens: 32,
      parentMaxTokens: 120,
      childOverlapTokens: 4,
    }, { title: "RAG project" });
    expect(preview.parents.length).toBeGreaterThan(1);
    expect(preview.children.length).toBeGreaterThan(preview.parents.length);
    expect(preview.children.every((child) => child.parentBody.length >= child.rawBody.length)).toBe(true);
    expect(preview.children.every((child) => child.retrievalText.includes("RAG project"))).toBe(true);
  });

  it("applies the configured overlap between neighboring retrieval chunks", () => {
    const firstUnit = "甲".repeat(20);
    const secondUnit = "乙".repeat(20);
    const preview = buildChunkPreview(`${firstUnit}\n\n${secondUnit}`, {
      ...DEFAULT_PROCESSING_PROFILE,
      chunkMode: "parent_child",
      childMaxTokens: 24,
      childOverlapTokens: 4,
      parentMaxTokens: 100,
    }, { title: "Overlap example" });

    expect(preview.children).toHaveLength(2);
    expect(preview.children[1].rawBody).toBe(`${"甲".repeat(4)}\n\n${secondUnit}`);
    expect(preview.children[1].tokenCount).toBeLessThanOrEqual(24);
  });

  it("keeps Chinese resume sections in separate semantic parents", () => {
    const resume = [
      "教育背景",
      "University of Sydney | Master of Data Science",
      "项目经验",
      "Local RAG Portfolio Assistant",
      "Built MongoDB Vector Search and Ollama generation.",
      "实习经历",
      "AI Intern | Built an evaluation workflow.",
    ].join("\n\n");
    const preview = buildChunkPreview(resume, {
      ...DEFAULT_PROCESSING_PROFILE,
      chunkMode: "resume_semantic",
    }, { title: "Master Resume" });
    expect(preview.parents.map((parent) => parent.sectionType)).toEqual(["education", "project", "internship"]);
    expect(preview.parents.some((parent) => parent.rawBody.includes("教育背景") && parent.rawBody.includes("项目经验"))).toBe(false);
  });
});
