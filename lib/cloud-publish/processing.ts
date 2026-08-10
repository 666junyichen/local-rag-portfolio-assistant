import { createHash } from "node:crypto";

export type ChunkMode = "standard" | "parent_child" | "resume_semantic";

export type ProcessingProfile = {
  chunkMode: ChunkMode;
  delimiter: string;
  childMaxTokens: number;
  childOverlapTokens: number;
  parentMaxTokens: number;
  normalizeWhitespace: boolean;
  removeUrls: boolean;
  removeEmails: boolean;
};

export const DEFAULT_PROCESSING_PROFILE: ProcessingProfile = {
  chunkMode: "parent_child",
  delimiter: "\n\n",
  childMaxTokens: 180,
  childOverlapTokens: 20,
  parentMaxTokens: 700,
  normalizeWhitespace: true,
  removeUrls: false,
  removeEmails: false,
};

export type PiiFinding = {
  kind: "email" | "phone" | "national_id" | "address";
  label: string;
  start: number;
  end: number;
  preview: string;
  blocking: true;
};

export type PreviewChunk = {
  chunkId: string;
  parentChunkId: string;
  rawBody: string;
  parentBody: string;
  retrievalText: string;
  sectionType: string;
  sectionPath: string;
  tokenCount: number;
  charCount: number;
};

export type ChunkPreview = {
  parents: PreviewChunk[];
  children: PreviewChunk[];
  averageChildTokens: number;
};

const digest = (value: string, size = 16) => createHash("sha256").update(value, "utf8").digest("hex").slice(0, size);
const CJK = /[\u3400-\u9fff\uf900-\ufaff\u3040-\u30ff\uac00-\ud7af]/g;

export function estimateTokens(text: string): number {
  const cjk = text.match(CJK)?.length || 0;
  const latin = text.replace(CJK, "").replace(/\s/g, "").length;
  return Math.max(text.trim() ? 1 : 0, cjk + Math.ceil(latin / 4));
}

function removeUrls(text: string): string {
  return text.replace(/https?:\/\/[^\s<>]+/giu, (match) => {
    const punctuation = match.match(/[.,;:!?，。；：！？)）]+$/u)?.[0] || "";
    return punctuation;
  });
}

export function cleanPublicText(text: string, profile: ProcessingProfile): string {
  let cleaned = text.replace(/\r\n?/g, "\n");
  if (profile.removeUrls) cleaned = removeUrls(cleaned);
  if (profile.removeEmails) cleaned = cleaned.replace(/[\p{L}\p{N}.!#$%&'*+/=?^_`{|}~-]+@[\p{L}\p{N}-]+(?:\.[\p{L}\p{N}-]+)+/giu, "");
  if (profile.normalizeWhitespace) {
    cleaned = cleaned
      .replace(/[\t\f\v ]+/g, " ")
      .replace(/ *\n */g, "\n")
      .replace(/\n{3,}/g, "\n\n")
      .replace(/ {2,}/g, " ");
  }
  return cleaned.trim();
}

export function detectPii(text: string): PiiFinding[] {
  const findings: PiiFinding[] = [];
  const add = (kind: PiiFinding["kind"], label: string, match: RegExpExecArray) => {
    findings.push({ kind, label, start: match.index, end: match.index + match[0].length, preview: "••••", blocking: true });
  };
  const patterns: Array<[PiiFinding["kind"], string, RegExp]> = [
    ["email", "Email address", /[\p{L}\p{N}.!#$%&'*+/=?^_`{|}~-]+@[\p{L}\p{N}-]+(?:\.[\p{L}\p{N}-]+)+/giu],
    ["national_id", "National ID", /(?<!\d)\d{17}[\dXx](?!\d)/g],
    ["phone", "Phone number", /(?<!\d)(?:1[3-9]\d{9}|0?4\d{8}|(?:\+?\d{1,3}[ -]?)?(?:\(?\d{2,4}\)?[ -])\d{3,4}[ -]\d{3,4})(?!\d)/g],
    ["address", "Address", /(?:家庭住址|家庭地址|住址|home address|residential address)\s*[：:]\s*[^\n]+/giu],
  ];
  for (const [kind, label, regex] of patterns) {
    for (const match of text.matchAll(regex)) {
      if (kind === "phone" && match[0].replace(/\D/g, "").length >= 17) continue;
      if (!findings.some((item) => match.index! < item.end && match.index! + match[0].length > item.start)) add(kind, label, match as RegExpExecArray);
    }
  }
  return findings.sort((left, right) => left.start - right.start);
}

type Section = { body: string; sectionType: string; sectionPath: string };

function splitLongUnit(unit: string, maxTokens: number): string[] {
  if (estimateTokens(unit) <= maxTokens) return [unit];
  const sentences = unit.split(/(?<=[。！？.!?])\s*/u).filter(Boolean);
  if (sentences.length > 1) return packUnits(sentences, maxTokens);
  const maxChars = Math.max(40, maxTokens * 3);
  return Array.from({ length: Math.ceil(unit.length / maxChars) }, (_, index) => unit.slice(index * maxChars, (index + 1) * maxChars));
}

function packUnits(units: string[], maxTokens: number): string[] {
  const output: string[] = [];
  let current = "";
  for (const raw of units.flatMap((unit) => splitLongUnit(unit.trim(), maxTokens)).filter(Boolean)) {
    const candidate = current ? `${current}\n\n${raw}` : raw;
    if (current && estimateTokens(candidate) > maxTokens) {
      output.push(current);
      current = raw;
    } else current = candidate;
  }
  if (current) output.push(current);
  return output;
}

function tokenTail(text: string, maxTokens: number): string {
  if (maxTokens <= 0) return "";
  const characters = Array.from(text.trim());
  let start = 0;
  while (start < characters.length && estimateTokens(characters.slice(start).join("")) > maxTokens) start += 1;
  return characters.slice(start).join("").trim();
}

function packUnitsWithOverlap(units: string[], maxTokens: number, overlapTokens: number): string[] {
  const safeOverlap = Math.max(0, Math.min(overlapTokens, Math.floor(maxTokens * 0.25)));
  if (!safeOverlap) return packUnits(units, maxTokens);
  const packed = packUnits(units, Math.max(1, maxTokens - safeOverlap));
  return packed.map((body, index) => {
    if (!index) return body;
    const overlap = tokenTail(packed[index - 1], safeOverlap);
    return overlap ? `${overlap}\n\n${body}` : body;
  });
}

const HEADING_TYPES: Array<[RegExp, string]> = [
  [/^(?:教育背景|教育经历|education)$/iu, "education"],
  [/^(?:项目经验|项目经历|projects?|project experience)$/iu, "project"],
  [/^(?:实习经历|工作经历|工作经验|internships?|work experience)$/iu, "internship"],
  [/^(?:专业技能|技能|skills?)$/iu, "skill"],
  [/^(?:获奖经历|奖项|awards?)$/iu, "award"],
  [/^(?:个人简介|个人总结|summary|profile)$/iu, "summary"],
];

function headingType(line: string): string | undefined {
  const normalized = line.trim().replace(/[：:]+$/, "");
  return HEADING_TYPES.find(([pattern]) => pattern.test(normalized))?.[1];
}

function resumeSections(text: string): Section[] {
  const paragraphs = text.split(/\n{2,}/).map((item) => item.trim()).filter(Boolean);
  const sections: Section[] = [];
  let current: Section | undefined;
  for (const paragraph of paragraphs) {
    const type = headingType(paragraph);
    if (type) {
      if (current) sections.push(current);
      current = { body: paragraph, sectionType: type, sectionPath: paragraph.replace(/[：:]+$/, "") };
    } else if (current) current.body += `\n\n${paragraph}`;
    else {
      if (!sections.length || sections[sections.length - 1].sectionType !== "profile") {
        sections.push({ body: paragraph, sectionType: "profile", sectionPath: "Profile" });
      } else sections[sections.length - 1].body += `\n\n${paragraph}`;
    }
  }
  if (current) sections.push(current);
  return sections;
}

function generalSections(text: string, profile: ProcessingProfile): Section[] {
  const delimiter = profile.delimiter || "\n\n";
  const units = text.split(delimiter).map((item) => item.trim()).filter(Boolean);
  if (profile.chunkMode === "standard") {
    return packUnitsWithOverlap(units, profile.childMaxTokens, profile.childOverlapTokens)
      .map((body) => ({ body, sectionType: "general", sectionPath: "Document" }));
  }
  return packUnits(units, profile.parentMaxTokens).map((body) => ({ body, sectionType: "general", sectionPath: "Document" }));
}

function previewChunk(body: string, parentBody: string, title: string, section: Section, index: number, parentId: string): PreviewChunk {
  const retrievalText = `[Document: ${title} | Section: ${section.sectionPath}]\n${body}`;
  return {
    chunkId: `chunk_${digest(`${parentId}:${index}:${body}`)}`,
    parentChunkId: parentId,
    rawBody: body,
    parentBody,
    retrievalText,
    sectionType: section.sectionType,
    sectionPath: section.sectionPath,
    tokenCount: estimateTokens(body),
    charCount: body.length,
  };
}

export function buildChunkPreview(text: string, profile: ProcessingProfile, metadata: { title: string }): ChunkPreview {
  const sections = profile.chunkMode === "resume_semantic" ? resumeSections(text) : generalSections(text, profile);
  const parents: PreviewChunk[] = [];
  const children: PreviewChunk[] = [];
  for (const section of sections) {
    for (const parentBody of packUnits(section.body.split(/\n{2,}/), profile.parentMaxTokens)) {
      const parentId = `parent_${digest(`${metadata.title}:${section.sectionPath}:${parentBody}`)}`;
      parents.push(previewChunk(parentBody, parentBody, metadata.title, section, 0, parentId));
      if (profile.chunkMode === "standard") {
        children.push(previewChunk(parentBody, parentBody, metadata.title, section, 0, parentId));
        continue;
      }
      const childBodies = packUnitsWithOverlap(
        parentBody.split(/\n{2,}/),
        profile.childMaxTokens,
        profile.childOverlapTokens,
      );
      childBodies.forEach((body, index) => children.push(previewChunk(body, parentBody, metadata.title, section, index, parentId)));
    }
  }
  return {
    parents,
    children,
    averageChildTokens: children.length ? Math.round(children.reduce((sum, item) => sum + item.tokenCount, 0) / children.length) : 0,
  };
}
