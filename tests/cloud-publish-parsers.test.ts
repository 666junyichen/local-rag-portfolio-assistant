import { describe, expect, it, vi } from "vitest";

import { PublishParseError, htmlToStructuredText, parseUpload } from "../lib/cloud-publish/parsers";

const textFile = (name: string, body: string, type = "text/plain") => new File([body], name, { type });

describe("owner upload parsing", () => {
  it("converts Mammoth HTML into stable headings, list items, and table rows", () => {
    const body = htmlToStructuredText([
      "<h1>Candidate Resume</h1>",
      "<h2>Projects</h2>",
      "<p>Portfolio RAG</p>",
      "<ul><li>MongoDB Vector Search</li><li>Ollama</li></ul>",
      "<table><tr><td>Role</td><td>AI Engineer</td></tr></table>",
    ].join(""));

    expect(body).toContain("# Candidate Resume");
    expect(body).toContain("## Projects");
    expect(body).toContain("- MongoDB Vector Search");
    expect(body).toContain("Role | AI Engineer");
  });

  it("preserves Markdown structure and derives a title", async () => {
    const result = await parseUpload(textFile("guide.md", "# RAG Guide\n\n## Retrieval\nVector search", "text/markdown"));

    expect(result.fileType).toBe("md");
    expect(result.title).toBe("RAG Guide");
    expect(result.body).toContain("## Retrieval");
  });

  it("renders CSV rows with their headers", async () => {
    const result = await parseUpload(textFile("projects.csv", "name,stack\nPortfolio RAG,MongoDB\nQANet,PyTorch", "text/csv"));

    expect(result.fileType).toBe("csv");
    expect(result.body).toContain("name: Portfolio RAG");
    expect(result.body).toContain("stack: MongoDB");
    expect(result.body).toContain("name: QANet");
  });

  it("uses the DOCX adapter and never returns the original bytes", async () => {
    const parseDocx = vi.fn().mockResolvedValue("Resume\n\nProjects\nPortfolio RAG");
    const result = await parseUpload(
      new File([new Uint8Array([80, 75, 3, 4])], "resume.docx", {
        type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      }),
      { parseDocx, detectFileType: async () => ({ ext: "docx", mime: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" }) },
    );

    expect(parseDocx).toHaveBeenCalledOnce();
    expect(result.body).toContain("Portfolio RAG");
    expect(result).not.toHaveProperty("buffer");
  });

  it("preserves structured DOCX headings and derives the resume title", async () => {
    const result = await parseUpload(
      new File([new Uint8Array([80, 75, 3, 4])], "candidate.docx"),
      {
        detectFileType: async () => ({ ext: "docx", mime: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" }),
        parseDocx: async () => [
          "# Junyi Resume",
          "## Education",
          "University of Sydney | Master of Data Science | 2025 - 2026",
          "## Projects",
          "Local RAG Portfolio Assistant | 2026",
        ].join("\n\n"),
      },
    );

    expect(result.title).toBe("Junyi Resume");
    expect(result.body).toContain("## Education");
    expect(result.body).toContain("## Projects");
  });

  it("marks image-only PDFs as needing OCR", async () => {
    await expect(parseUpload(
      new File([new Uint8Array([37, 80, 68, 70])], "scan.pdf", { type: "application/pdf" }),
      { parsePdf: async () => ({ text: "  ", pages: 2 }), detectFileType: async () => ({ ext: "pdf", mime: "application/pdf" }) },
    )).rejects.toMatchObject({ code: "needs_ocr" });
  });

  it("rejects unsupported and oversized files", async () => {
    await expect(parseUpload(textFile("macro.docm", "unsafe"))).rejects.toMatchObject({ code: "unsupported_file" });
    const oversized = new File([new Uint8Array(4 * 1024 * 1024 + 1)], "large.txt", { type: "text/plain" });
    await expect(parseUpload(oversized)).rejects.toMatchObject({ code: "file_too_large" });
  });

  it("uses stable public error messages", () => {
    const error = new PublishParseError("encrypted_pdf", "Encrypted PDFs are not supported.");
    expect(error.code).toBe("encrypted_pdf");
    expect(error.message).not.toMatch(/[A-Z]:\\/);
  });
});
