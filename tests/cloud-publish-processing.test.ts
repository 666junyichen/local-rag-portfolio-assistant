import { describe, expect, it } from "vitest";
import {
  DEFAULT_PROCESSING_PROFILE,
  buildChunkPreview,
  cleanPublicText,
  detectPii,
  processingProfileForRevision,
  recommendProcessingProfile,
} from "../lib/cloud-publish/processing";

describe("public document processing", () => {
  it("chooses standard or parent-child for generic DOCX by content length", () => {
    expect(recommendProcessingProfile({
      fileName: "architecture-notes.docx",
      fileType: "docx",
      title: "System architecture notes",
      body: "MongoDB deployment and service boundaries.",
    }).chunkMode).toBe("standard");

    expect(recommendProcessingProfile({
      fileName: "architecture-handbook.docx",
      fileType: "docx",
      title: "System architecture handbook",
      body: "MongoDB deployment and service boundaries. ".repeat(2200),
    }).chunkMode).toBe("parent_child");
  });

  it("uses resume structure in the title or body before trusting generic file names", () => {
    expect(recommendProcessingProfile({
      fileName: "candidate.docx",
      fileType: "docx",
      title: "Candidate Resume",
      body: "Education and project experience.",
    }).chunkMode).toBe("resume_semantic");

    expect(recommendProcessingProfile({
      fileName: "upload.docx",
      fileType: "docx",
      title: "Untitled upload",
      body: [
        "Education",
        "University of Sydney | Master of Data Science",
        "Projects",
        "Local RAG Portfolio Assistant",
        "Skills",
        "Python, TypeScript, MongoDB",
      ].join("\n\n"),
    }).chunkMode).toBe("resume_semantic");

    expect(recommendProcessingProfile({
      fileName: "upload.docx",
      fileType: "docx",
      title: "未命名上传",
      body: [
        "教育背景",
        "悉尼大学 | 数据科学硕士",
        "项目经历",
        "Local RAG Portfolio Assistant",
        "专业技能",
        "Python、TypeScript、MongoDB",
      ].join("\n\n"),
    }).chunkMode).toBe("resume_semantic");

    expect(recommendProcessingProfile({
      fileName: "resume-parser-notes.docx",
      fileType: "docx",
      title: "Parser notes",
      body: "This document explains how a resume parser handles text.",
    }).chunkMode).toBe("standard");
  });

  it("upgrades an old parent-child resume revision without changing ordinary documents", () => {
    const legacy = { ...DEFAULT_PROCESSING_PROFILE, chunkMode: "parent_child" as const };
    expect(processingProfileForRevision(legacy, {
      fileName: "",
      fileType: "docx",
      title: "Candidate Resume",
      body: "Education and project experience.",
    }).chunkMode).toBe("resume_semantic");
    expect(processingProfileForRevision(legacy, {
      fileName: "architecture.docx",
      fileType: "docx",
      title: "Architecture Notes",
      body: "Service boundaries.",
    }).chunkMode).toBe("parent_child");
  });

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

  it.each([
    { fileName: "candidate-resume.docx", fileType: "docx", title: "Candidate Resume" },
    { fileName: "notes.md", fileType: "md", title: "陈君奕简历" },
    { fileName: "notes.txt", fileType: "txt", title: "Junyi Resume" },
    { fileName: "notes.pdf", fileType: "pdf", title: "Junyi CV" },
  ])("recommends resume semantic processing for $fileName", (upload) => {
    expect(recommendProcessingProfile(upload)).toMatchObject({
      chunkMode: "resume_semantic",
      childMaxTokens: 180,
      parentMaxTokens: 320,
    });
  });

  it("keeps every resume entity in a separate semantic parent with complete metadata", () => {
    const profile = recommendProcessingProfile({
      fileName: "陈君奕简历.docx",
      fileType: "docx",
      title: "陈君奕简历",
    });
    const body = [
      "个人简历",
      "陈君奕",
      "求职方向：AI 应用工程师",
      "教育背景",
      "悉尼大学 | 数据科学硕士 | 2025.02 - 2026.12",
      "相关课程：机器学习、深度学习、数据隐私",
      "南京师范大学 | 理学学士 | 2022.02 - 2024.12",
      "相关课程：Python、SQL、数据分析",
      "实习经历",
      "南京软通动力有限公司 | AI 实习生 | 2024.06 - 2024.07",
      "负责模型评测和数据清洗。",
      "C51 Consulting | Student Consultant | 2025.11 - 2025.12",
      "负责行业研究和客户报告。",
      "项目经验",
      "Local RAG Portfolio Assistant | 2026",
      "技术栈：Python、MongoDB Vector Search、Ollama",
      "成果：实现本地私有知识库检索与来源引用。",
      "QANet Debugging and Controlled Experiments | 2026",
      "技术栈：Python、PyTorch、QANet",
      "成果：完成受控实验与模型修复。",
      "专业技能",
      "AI 与数据：RAG、机器学习、模型评测",
      "Web 开发：React、Next.js、TypeScript",
      "获奖经历",
      "2025 Outstanding Quality Award",
      "2024 Data Science Capstone Award",
    ].join("\n\n");

    const preview = buildChunkPreview(body, profile, { title: "陈君奕简历" });
    const projects = preview.parents.filter((chunk) => chunk.sectionType === "project");

    expect(projects).toHaveLength(2);
    expect(preview.parents.filter((chunk) => chunk.sectionType === "education")).toHaveLength(2);
    expect(preview.parents.filter((chunk) => chunk.sectionType === "internship")).toHaveLength(2);
    expect(preview.parents.filter((chunk) => chunk.sectionType === "skill")).toHaveLength(2);
    expect(preview.parents.filter((chunk) => chunk.sectionType === "award")).toHaveLength(2);
    expect(projects[0].parentBody).toContain("Local RAG Portfolio Assistant");
    expect(projects[0].parentBody).not.toContain("QANet Debugging");
    expect(projects[1].parentBody).toContain("QANet Debugging");
    expect(projects[1].parentBody).not.toContain("Local RAG Portfolio Assistant");

    for (const parent of preview.parents) {
      expect(parent.tokenCount).toBeLessThanOrEqual(320);
      expect(parent.parentChunkId).toMatch(/^parent_/);
      expect(parent.entityTitle).toBeTruthy();
      expect(parent.sectionPath).toContain(parent.entityTitle);
      expect(parent.semanticGroupId).toMatch(/^group_/);
    }
    for (const child of preview.children) {
      const parent = preview.parents.find((item) => item.parentChunkId === child.parentChunkId);
      expect(child.tokenCount).toBeLessThanOrEqual(180);
      expect(child.entityTitle).toBe(parent?.entityTitle);
      expect(child.semanticGroupId).toBe(parent?.semanticGroupId);
    }
  });

  it("splits an oversized project only inside that entity and repeats its title", () => {
    const profile = recommendProcessingProfile({
      fileName: "resume.docx",
      fileType: "docx",
      title: "Resume",
    });
    const detail = Array.from(
      { length: 45 },
      (_, index) => `项目成果 ${index + 1}：完成检索评测、来源引用和稳定性验证。`,
    ).join("\n\n");
    const body = [
      "项目经验",
      "Local RAG Portfolio Assistant | 2026",
      "技术栈：Python、MongoDB、Ollama",
      detail,
      "QANet Debugging | 2026",
      "技术栈：Python、PyTorch",
      "成果：完成模型修复。",
    ].join("\n\n");

    const preview = buildChunkPreview(body, profile, { title: "Resume" });
    const ragParents = preview.parents.filter((chunk) => chunk.entityTitle.includes("Local RAG"));

    expect(ragParents.length).toBeGreaterThan(1);
    expect(new Set(ragParents.map((chunk) => chunk.semanticGroupId)).size).toBe(1);
    expect(ragParents.every((chunk) => chunk.parentBody.includes("Local RAG Portfolio Assistant"))).toBe(true);
    expect(ragParents.every((chunk) => !chunk.parentBody.includes("QANet Debugging"))).toBe(true);
    expect(ragParents.every((chunk) => chunk.tokenCount <= 320)).toBe(true);
  });
});
