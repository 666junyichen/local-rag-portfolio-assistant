import path from "node:path";

const MAX_UPLOAD_BYTES = 4 * 1024 * 1024;
const MAX_EXTRACTED_CHARS = 250_000;
const SUPPORTED_EXTENSIONS = new Set(["pdf", "docx", "md", "markdown", "txt", "csv"]);

export type ParsedUpload = {
  fileName: string;
  fileType: "pdf" | "docx" | "md" | "txt" | "csv";
  sizeBytes: number;
  title: string;
  body: string;
  language: "zh" | "en";
  warnings: string[];
};

export type ParserAdapters = {
  parseDocx?: (data: Uint8Array) => Promise<string>;
  parsePdf?: (data: Uint8Array) => Promise<{ text: string; pages: number }>;
  detectFileType?: (data: Uint8Array) => Promise<{ ext: string; mime: string } | undefined>;
};

export type PublishParseErrorCode =
  | "empty_file"
  | "encrypted_pdf"
  | "file_too_large"
  | "invalid_file"
  | "needs_ocr"
  | "unsupported_file";

export class PublishParseError extends Error {
  constructor(public readonly code: PublishParseErrorCode, message: string) {
    super(message);
    this.name = "PublishParseError";
  }
}

const normalizeExtension = (fileName: string) => path.extname(fileName).toLowerCase().replace(/^\./, "");

async function defaultDetectFileType(data: Uint8Array) {
  const { fileTypeFromBuffer } = await import("file-type");
  return fileTypeFromBuffer(data);
}

async function defaultParseDocx(data: Uint8Array): Promise<string> {
  const mammoth = await import("mammoth");
  const result = await mammoth.extractRawText({ buffer: Buffer.from(data) });
  return result.value;
}

async function defaultParsePdf(data: Uint8Array): Promise<{ text: string; pages: number }> {
  const { PDFParse } = await import("pdf-parse");
  const parser = new PDFParse({ data });
  try {
    const result = await parser.getText();
    return { text: result.text || "", pages: result.total || 0 };
  } catch (error) {
    const message = error instanceof Error ? error.message.toLowerCase() : "";
    if (message.includes("password") || message.includes("encrypted")) {
      throw new PublishParseError("encrypted_pdf", "Encrypted PDFs are not supported.");
    }
    throw new PublishParseError("invalid_file", "The PDF could not be parsed.");
  } finally {
    await parser.destroy();
  }
}

function markdownTitle(body: string): string | undefined {
  return body.match(/^#\s+(.+)$/m)?.[1]?.trim();
}

function deriveTitle(fileName: string, body: string, fileType: ParsedUpload["fileType"]): string {
  if (fileType === "md") return markdownTitle(body) || path.parse(fileName).name;
  return path.parse(fileName).name;
}

function detectLanguage(body: string): "zh" | "en" {
  const cjk = body.match(/[\u3400-\u9fff]/g)?.length || 0;
  return cjk >= Math.max(3, body.length * 0.05) ? "zh" : "en";
}

async function parseCsv(data: Uint8Array): Promise<string> {
  const { parse } = await import("csv-parse/sync");
  let rows: Record<string, unknown>[];
  try {
    rows = parse(new TextDecoder("utf-8").decode(data), {
      bom: true,
      columns: true,
      skip_empty_lines: true,
      relax_column_count: true,
      trim: true,
    });
  } catch {
    throw new PublishParseError("invalid_file", "The CSV could not be parsed.");
  }
  return rows
    .map((row) => Object.entries(row).map(([key, value]) => `${key}: ${String(value ?? "").trim()}`).join("\n"))
    .filter(Boolean)
    .join("\n\n");
}

function normalizedFileType(extension: string): ParsedUpload["fileType"] {
  if (extension === "markdown") return "md";
  return extension as ParsedUpload["fileType"];
}

async function verifyBinaryType(
  extension: string,
  data: Uint8Array,
  detectFileType: NonNullable<ParserAdapters["detectFileType"]>,
) {
  if (extension !== "pdf" && extension !== "docx") return;
  const detected = await detectFileType(data);
  const valid = extension === "pdf" ? detected?.ext === "pdf" : detected?.ext === "docx" || detected?.ext === "zip";
  if (!valid) throw new PublishParseError("invalid_file", `The .${extension} file signature is invalid.`);
}

export async function parseUpload(file: File, adapters: ParserAdapters = {}): Promise<ParsedUpload> {
  const extension = normalizeExtension(file.name);
  if (!SUPPORTED_EXTENSIONS.has(extension)) {
    throw new PublishParseError("unsupported_file", "Supported formats are PDF, DOCX, Markdown, TXT, and CSV.");
  }
  if (!file.size) throw new PublishParseError("empty_file", "The uploaded file is empty.");
  if (file.size > MAX_UPLOAD_BYTES) {
    throw new PublishParseError("file_too_large", "Each uploaded file must be 4 MB or smaller.");
  }

  const data = new Uint8Array(await file.arrayBuffer());
  const detectFileType = adapters.detectFileType || defaultDetectFileType;
  await verifyBinaryType(extension, data, detectFileType);

  const fileType = normalizedFileType(extension);
  let body = "";
  let warnings: string[] = [];
  if (fileType === "docx") body = await (adapters.parseDocx || defaultParseDocx)(data);
  else if (fileType === "pdf") {
    const result = await (adapters.parsePdf || defaultParsePdf)(data);
    body = result.text;
    if (body.trim().length < Math.max(40, result.pages * 20)) {
      throw new PublishParseError("needs_ocr", "This PDF appears to be scanned. OCR is not enabled.");
    }
  } else if (fileType === "csv") body = await parseCsv(data);
  else body = new TextDecoder("utf-8", { fatal: false }).decode(data);

  body = body.replace(/\u0000/g, "").replace(/\r\n?/g, "\n").trim();
  if (!body) throw new PublishParseError("empty_file", "No readable text was found in the file.");
  if (body.length > MAX_EXTRACTED_CHARS) {
    body = body.slice(0, MAX_EXTRACTED_CHARS);
    warnings = ["Extracted text was limited to 250,000 characters."];
  }

  return {
    fileName: path.basename(file.name),
    fileType,
    sizeBytes: file.size,
    title: deriveTitle(file.name, body, fileType),
    body,
    language: detectLanguage(body),
    warnings,
  };
}
