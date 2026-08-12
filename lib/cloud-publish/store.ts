import { randomUUID } from "node:crypto";
import type { Document } from "mongodb";

import { cloudDb } from "../cloud-rag/mongodb";
import type { OwnerIdentity } from "./auth";
import { publicDocumentView, toOwnerExport } from "./contracts";
import type { ParsedUpload } from "./parsers";
import {
  DEFAULT_PROCESSING_PROFILE,
  buildChunkPreview,
  cleanPublicText,
  detectPii,
  recommendProcessingProfile,
  type ProcessingProfile,
} from "./processing";
import { PublishConflictError, type DraftRecord, type Publication, type PublishRepository } from "./publishing";
import { DEFAULT_SPACE_ID } from "../cloud-rag/spaces";
import { ensureCloudSpaces, listOwnerSpaces, requireActivePublicSpaces, spaceNameMap } from "./spaces";

const draftsName = () => process.env.CLOUD_DRAFTS_COLLECTION_NAME || "portfolio_public_drafts";
const documentsName = () => process.env.CLOUD_DOCUMENTS_COLLECTION_NAME || "portfolio_public_documents";
const chunksName = () => process.env.CLOUD_COLLECTION_NAME || "portfolio_knowledge_public";
const expiresAt = () => new Date(Date.now() + 7 * 24 * 60 * 60 * 1000);

let indexesReady: Promise<void> | undefined;

export async function ensurePublishIndexes(): Promise<void> {
  if (!indexesReady) indexesReady = (async () => {
    const db = await cloudDb();
    await Promise.all([
      db.collection(draftsName()).createIndex({ expires_at: 1 }, { expireAfterSeconds: 0 }),
      db.collection(draftsName()).createIndex({ owner_id: 1, updated_at: -1 }),
      db.collection(documentsName()).createIndex({ doc_id: 1 }, { unique: true }),
      db.collection(documentsName()).createIndex({ status: 1, updated_at: -1 }),
      db.collection(chunksName()).createIndex({ doc_id: 1, source_origin: 1 }),
      db.collection(chunksName()).createIndex({ chunk_id: 1 }, { unique: true, sparse: true }),
      db.collection(documentsName()).createIndex({ space_id: 1, status: 1, updated_at: -1 }),
      db.collection(chunksName()).createIndex({ space_id: 1, doc_id: 1 }),
    ]);
  })().catch((error) => {
    indexesReady = undefined;
    throw error;
  });
  return indexesReady;
}

function toDraftRecord(row: Document): DraftRecord {
  return {
    draftId: String(row.draft_id),
    ...(row.doc_id ? { docId: String(row.doc_id) } : {}),
    ownerId: String(row.owner_id),
    spaceId: String(row.space_id || DEFAULT_SPACE_ID),
    title: String(row.title || "Untitled"),
    summary: String(row.summary || ""),
    category: String(row.category || "portfolio"),
    language: row.language === "zh" ? "zh" : "en",
    ...(row.source_url ? { sourceUrl: String(row.source_url) } : {}),
    ...(row.file_name ? { fileName: String(row.file_name) } : {}),
    ...(row.file_type ? { fileType: String(row.file_type) } : {}),
    parsedBody: String(row.parsed_body || ""),
    cleanedBody: String(row.cleaned_body || ""),
    processingProfile: row.processing_profile as ProcessingProfile,
    preview: row.preview,
    piiFindings: row.pii_findings || [],
    status: row.status,
    publicationVersion: Number(row.publication_version || 1),
  };
}

function draftView(row: Document) {
  return {
    draftId: String(row.draft_id),
    ...(row.doc_id ? { docId: String(row.doc_id) } : {}),
    spaceId: String(row.space_id || DEFAULT_SPACE_ID),
    title: String(row.title || "Untitled"),
    summary: String(row.summary || ""),
    category: String(row.category || "portfolio"),
    language: row.language === "zh" ? "zh" : "en",
    sourceUrl: String(row.source_url || ""),
    fileName: String(row.file_name || ""),
    fileType: String(row.file_type || ""),
    sizeBytes: Number(row.size_bytes || 0),
    parsedBody: String(row.parsed_body || ""),
    cleanedBody: String(row.cleaned_body || ""),
    processingProfile: row.processing_profile,
    preview: row.preview,
    piiFindings: row.pii_findings || [],
    status: String(row.status || "draft"),
    failureCode: String(row.failure_code || ""),
    publicationVersion: Number(row.publication_version || 1),
    createdAt: row.created_at instanceof Date ? row.created_at.toISOString() : "",
    updatedAt: row.updated_at instanceof Date ? row.updated_at.toISOString() : "",
    expiresAt: row.expires_at instanceof Date ? row.expires_at.toISOString() : "",
  };
}

function validateProfile(raw: unknown): ProcessingProfile {
  const value = { ...DEFAULT_PROCESSING_PROFILE, ...(raw && typeof raw === "object" ? raw : {}) } as ProcessingProfile;
  if (!["standard", "parent_child", "resume_semantic"].includes(value.chunkMode)) throw new Error("Invalid chunk mode");
  if (!Number.isInteger(value.childMaxTokens) || value.childMaxTokens < 50 || value.childMaxTokens > 1000) throw new Error("Child length must be between 50 and 1000 tokens");
  if (!Number.isInteger(value.childOverlapTokens) || value.childOverlapTokens < 0 || value.childOverlapTokens > Math.floor(value.childMaxTokens * 0.25)) throw new Error("Child overlap must not exceed 25% of the child length");
  if (!Number.isInteger(value.parentMaxTokens) || value.parentMaxTokens < value.childMaxTokens || value.parentMaxTokens > 2000) throw new Error("Parent length must be between child length and 2000 tokens");
  value.delimiter = String(value.delimiter || "\n\n").slice(0, 20);
  return value;
}

function makeDraft(owner: OwnerIdentity, parsed: ParsedUpload, profile = recommendProcessingProfile(parsed), spaceId = DEFAULT_SPACE_ID) {
  const now = new Date();
  const cleanedBody = cleanPublicText(parsed.body, profile);
  const piiFindings = detectPii(cleanedBody);
  const preview = buildChunkPreview(cleanedBody, profile, { title: parsed.title });
  return {
    draft_id: randomUUID(),
    owner_id: owner.userId,
    owner_email: owner.email,
    source_origin: "owner_upload",
    space_id: spaceId,
    title: parsed.title,
    summary: "",
    category: "portfolio",
    language: parsed.language,
    file_name: parsed.fileName,
    file_type: parsed.fileType,
    size_bytes: parsed.sizeBytes,
    parsed_body: parsed.body,
    cleaned_body: cleanedBody,
    processing_profile: profile,
    preview,
    pii_findings: piiFindings,
    warnings: parsed.warnings,
    status: piiFindings.length ? "draft" : "ready",
    publication_version: 1,
    created_at: now,
    updated_at: now,
    expires_at: expiresAt(),
  };
}

export async function createDrafts(owner: OwnerIdentity, uploads: ParsedUpload[], targetSpaceId = DEFAULT_SPACE_ID) {
  await ensurePublishIndexes();
  const [spaceId] = await requireActivePublicSpaces([targetSpaceId]);
  const db = await cloudDb();
  const records = uploads.map((upload) => makeDraft(owner, upload, recommendProcessingProfile(upload), spaceId));
  if (records.length) await db.collection(draftsName()).insertMany(records);
  return records.map(draftView);
}

export async function listOwnerWorkspace(owner: OwnerIdentity) {
  await ensurePublishIndexes();
  await ensureCloudSpaces();
  const db = await cloudDb();
  const [drafts, documents] = await Promise.all([
    db.collection(draftsName()).find({ owner_id: owner.userId }).sort({ updated_at: -1 }).limit(100).toArray(),
    db.collection(documentsName()).find({ owner_id: owner.userId, source_origin: "owner_upload" }).sort({ updated_at: -1 }).limit(100).toArray(),
  ]);
  const spaces = await listOwnerSpaces(owner);
  const names = new Map(spaces.map((space) => [space.spaceId, space.name]));
  return {
    drafts: drafts.map(draftView),
    documents: documents.map((row) => ({
      ...publicDocumentView({ ...row, space_name: names.get(String(row.space_id || DEFAULT_SPACE_ID)) || "Portfolio" }),
      status: String(row.status || "published"),
      publicationVersion: Number(row.publication_version || 1),
    })),
    spaces,
  };
}

export async function getOwnerDraft(owner: OwnerIdentity, draftId: string) {
  const db = await cloudDb();
  const row = await db.collection(draftsName()).findOne({ draft_id: draftId, owner_id: owner.userId });
  return row ? draftView(row) : null;
}

const EDITABLE_FIELDS: Record<string, string> = {
  title: "title",
  summary: "summary",
  category: "category",
  language: "language",
  sourceUrl: "source_url",
  parsedBody: "parsed_body",
  cleanedBody: "cleaned_body",
  spaceId: "space_id",
};

export async function updateOwnerDraft(owner: OwnerIdentity, draftId: string, patch: Record<string, unknown>) {
  const db = await cloudDb();
  const update: Record<string, unknown> = { updated_at: new Date(), expires_at: expiresAt(), status: "draft", failure_code: "" };
  for (const [input, stored] of Object.entries(EDITABLE_FIELDS)) {
    if (patch[input] !== undefined) update[stored] = String(patch[input]).slice(0, input.endsWith("Body") ? 250_000 : 2000);
  }
  if (patch.processingProfile !== undefined) update.processing_profile = validateProfile(patch.processingProfile);
  if (patch.spaceId !== undefined) {
    const [spaceId] = await requireActivePublicSpaces([String(patch.spaceId)]);
    update.space_id = spaceId;
  }
  const result = await db.collection(draftsName()).findOneAndUpdate(
    { draft_id: draftId, owner_id: owner.userId, status: { $ne: "published" } },
    { $set: update, $unset: { preview: "", pii_findings: "" } },
    { returnDocument: "after" },
  );
  if (!result) throw new Error("Draft not found");
  return draftView(result);
}

export async function previewOwnerDraft(owner: OwnerIdentity, draftId: string) {
  const db = await cloudDb();
  const collection = db.collection(draftsName());
  const row = await collection.findOne({ draft_id: draftId, owner_id: owner.userId, status: { $ne: "published" } });
  if (!row) throw new Error("Draft not found");
  const profile = validateProfile(row.processing_profile);
  const editableBody = String(row.cleaned_body || row.parsed_body || "");
  const cleanedBody = cleanPublicText(editableBody, profile);
  if (!cleanedBody) throw new Error("Cleaned document body is empty");
  const piiFindings = detectPii(cleanedBody);
  const preview = buildChunkPreview(cleanedBody, profile, { title: String(row.title || "Untitled") });
  const result = await collection.findOneAndUpdate(
    { _id: row._id },
    { $set: {
      cleaned_body: cleanedBody,
      processing_profile: profile,
      preview,
      pii_findings: piiFindings,
      status: piiFindings.length ? "draft" : "ready",
      failure_code: "",
      updated_at: new Date(),
      expires_at: expiresAt(),
    } },
    { returnDocument: "after" },
  );
  return draftView(result!);
}

export async function listPublicKnowledge(search = "", category = "", rawSpaceIds?: string[]) {
  const spaceIds = await requireActivePublicSpaces(rawSpaceIds);
  const db = await cloudDb();
  const filter: Document = {
    visibility: "public",
    status: "published",
    space_id: spaceIds.length === 1 ? spaceIds[0] : { $in: spaceIds },
  };
  if (category) filter.category = category;
  if (search) filter.$or = [
    { title: { $regex: search.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), $options: "i" } },
    { summary: { $regex: search.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), $options: "i" } },
  ];
  const rows = await db.collection(documentsName()).find(filter).sort({ updated_at: -1 }).limit(100).toArray();
  const names = await spaceNameMap(spaceIds);
  return rows.map((row) => publicDocumentView({ ...row, space_name: names.get(String(row.space_id || DEFAULT_SPACE_ID)) || "Portfolio" }));
}

export class MongoPublishRepository implements PublishRepository {
  async getDraft(ownerId: string, draftId: string): Promise<DraftRecord | null> {
    const db = await cloudDb();
    const row = await db.collection(draftsName()).findOne({ draft_id: draftId, owner_id: ownerId });
    return row ? toDraftRecord(row) : null;
  }

  async claimDraft(ownerId: string, draftId: string): Promise<DraftRecord | null> {
    const db = await cloudDb();
    const row = await db.collection(draftsName()).findOneAndUpdate(
      { draft_id: draftId, owner_id: ownerId, status: "ready" },
      { $set: { status: "publishing", failure_code: "", updated_at: new Date(), expires_at: expiresAt() } },
      { returnDocument: "after" },
    );
    return row ? toDraftRecord(row) : null;
  }

  async getPublication(ownerId: string, docId: string): Promise<Publication | null> {
    const db = await cloudDb();
    const document = await db.collection(documentsName()).findOne({
      doc_id: docId,
      owner_id: ownerId,
      source_origin: "owner_upload",
    });
    if (!document) return null;
    const chunks = await db.collection(chunksName()).find({
      doc_id: docId,
      owner_id: ownerId,
      source_origin: "owner_upload",
    }).sort({ chunk_id: 1 }).toArray();
    const withoutId = ({ _id: _ignored, ...value }: Document) => value;
    return { document: withoutId(document), chunks: chunks.map(withoutId) };
  }

  async markDraftFailure(ownerId: string, draftId: string, reason: string): Promise<void> {
    const db = await cloudDb();
    const retryable = reason === "free_quota_unavailable";
    await db.collection(draftsName()).updateOne(
      { draft_id: draftId, owner_id: ownerId },
      { $set: { status: retryable ? "ready" : "failed", failure_code: reason, updated_at: new Date(), expires_at: expiresAt() } },
    );
  }

  async commitPublication(publication: Publication, draft: DraftRecord): Promise<void> {
    await ensurePublishIndexes();
    const db = await cloudDb();
    const document = publication.document;
    const docId = String(document.doc_id);
    const chunkIds = publication.chunks.map((chunk) => String(chunk.chunk_id));
    const session = db.client.startSession();
    try {
      await session.withTransaction(async () => {
        const existing = await db.collection(documentsName()).findOne(
          { doc_id: docId, owner_id: draft.ownerId, source_origin: "owner_upload" },
          { session },
        );
        const incomingVersion = Number(document.publication_version || 1);
        const existingVersion = Number(existing?.publication_version || 0);
        if (existingVersion > incomingVersion) throw new PublishConflictError("A newer publication already exists.");
        if (existingVersion === incomingVersion && existing?.content_hash !== document.content_hash) {
          throw new PublishConflictError("Another revision already used this publication version.");
        }

        await db.collection(documentsName()).updateOne(
          { doc_id: docId, owner_id: draft.ownerId, source_origin: "owner_upload" },
          { $set: document, $setOnInsert: { created_at: new Date() } },
          { upsert: true, session },
        );
        if (publication.chunks.length) {
          await db.collection(chunksName()).bulkWrite(publication.chunks.map((chunk) => ({
            replaceOne: { filter: { chunk_id: chunk.chunk_id }, replacement: chunk, upsert: true },
          })), { session });
        }
        await db.collection(chunksName()).deleteMany({
          doc_id: docId,
          source_origin: "owner_upload",
          ...(chunkIds.length ? { chunk_id: { $nin: chunkIds } } : {}),
        }, { session });
        const draftResult = await db.collection(draftsName()).updateOne(
          { draft_id: draft.draftId, owner_id: draft.ownerId, status: "publishing" },
          { $set: { status: "published", doc_id: docId, failure_code: "", updated_at: new Date() } },
          { session },
        );
        if (!draftResult.matchedCount) throw new PublishConflictError("The draft publication state changed before commit.");
      });
    } finally {
      await session.endSession();
    }
  }
}

export async function unpublishOwnerDocument(owner: OwnerIdentity, docId: string) {
  const db = await cloudDb();
  const session = db.client.startSession();
  try {
    await session.withTransaction(async () => {
      await db.collection(chunksName()).updateMany(
        { doc_id: docId, source_origin: "owner_upload", owner_id: owner.userId },
        { $set: { visibility: "private", validity_status: "inactive", updated_at: new Date() } },
        { session },
      );
      const result = await db.collection(documentsName()).updateOne(
        { doc_id: docId, owner_id: owner.userId, source_origin: "owner_upload" },
        { $set: { status: "archived", visibility: "private", updated_at: new Date() } },
        { session },
      );
      if (!result.matchedCount) throw new Error("Document not found");
      await db.collection(chunksName()).deleteMany(
        { doc_id: docId, source_origin: "owner_upload", owner_id: owner.userId },
        { session },
      );
    });
  } finally {
    await session.endSession();
  }
  return { docId, status: "archived" };
}

export async function moveOwnerDocument(owner: OwnerIdentity, docId: string, targetSpaceId: string) {
  const [spaceId] = await requireActivePublicSpaces([targetSpaceId]);
  const names = await spaceNameMap([spaceId]);
  const spaceName = names.get(spaceId) || spaceId;
  const db = await cloudDb();
  const session = db.client.startSession();
  try {
    await session.withTransaction(async () => {
      const result = await db.collection(documentsName()).updateOne(
        { doc_id: docId, owner_id: owner.userId, source_origin: "owner_upload" },
        { $set: { space_id: spaceId, space_name: spaceName, updated_at: new Date() } },
        { session },
      );
      if (!result.matchedCount) throw new Error("Document not found");
      await Promise.all([
        db.collection(chunksName()).updateMany(
          { doc_id: docId, owner_id: owner.userId, source_origin: "owner_upload" },
          { $set: {
            space_id: spaceId,
            space_name: spaceName,
            "metadata.space_id": spaceId,
            "metadata.space_name": spaceName,
            updated_at: new Date(),
          } },
          { session },
        ),
        db.collection(draftsName()).updateMany(
          { doc_id: docId, owner_id: owner.userId },
          { $set: { space_id: spaceId, updated_at: new Date() } },
          { session },
        ),
      ]);
    });
  } finally {
    await session.endSession();
  }
  return { docId, spaceId, spaceName };
}

export async function reviseOwnerDocument(owner: OwnerIdentity, docId: string) {
  const db = await cloudDb();
  const document = await db.collection(documentsName()).findOne({ doc_id: docId, owner_id: owner.userId, source_origin: "owner_upload" });
  if (!document) throw new Error("Document not found");
  const now = new Date();
  const profile = validateProfile(document.processing_profile);
  const cleanedBody = String(document.cleaned_body || "");
  const record = {
    draft_id: randomUUID(),
    doc_id: docId,
    owner_id: owner.userId,
    owner_email: owner.email,
    source_origin: "owner_upload",
    space_id: String(document.space_id || DEFAULT_SPACE_ID),
    title: document.title,
    summary: document.summary || "",
    category: document.category || "portfolio",
    language: document.language === "zh" ? "zh" : "en",
    source_url: document.source_url || "",
    parsed_body: cleanedBody,
    cleaned_body: cleanedBody,
    processing_profile: profile,
    preview: buildChunkPreview(cleanedBody, profile, { title: String(document.title || "Untitled") }),
    pii_findings: detectPii(cleanedBody),
    status: "ready",
    publication_version: Number(document.publication_version || 1) + 1,
    created_at: now,
    updated_at: now,
    expires_at: expiresAt(),
  };
  await db.collection(draftsName()).insertOne(record);
  return draftView(record);
}

export async function deleteOwnerDocument(owner: OwnerIdentity, docId: string) {
  const db = await cloudDb();
  const session = db.client.startSession();
  try {
    await session.withTransaction(async () => {
      await db.collection(chunksName()).updateMany(
        { doc_id: docId, source_origin: "owner_upload", owner_id: owner.userId },
        { $set: { visibility: "private", validity_status: "inactive", updated_at: new Date() } },
        { session },
      );
      const result = await db.collection(documentsName()).deleteOne(
        { doc_id: docId, owner_id: owner.userId, source_origin: "owner_upload" },
        { session },
      );
      if (!result.deletedCount) throw new Error("Document not found");
      await db.collection(chunksName()).deleteMany(
        { doc_id: docId, source_origin: "owner_upload", owner_id: owner.userId },
        { session },
      );
      await db.collection(draftsName()).deleteMany({ doc_id: docId, owner_id: owner.userId }, { session });
    });
  } finally {
    await session.endSession();
  }
  return { docId, deleted: true };
}

export async function exportOwnerDocuments(owner: OwnerIdentity) {
  const db = await cloudDb();
  const rows = await db.collection(documentsName()).find({ owner_id: owner.userId, source_origin: "owner_upload" }).sort({ updated_at: -1 }).toArray();
  return rows.map(toOwnerExport);
}
