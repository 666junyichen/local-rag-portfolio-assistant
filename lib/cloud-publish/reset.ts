import { createHash } from "node:crypto";
import type { Document } from "mongodb";

import { cloudDb } from "../cloud-rag/mongodb";
import { PublishConflictError } from "./publishing";


export const CLOUD_RESET_CONFIRMATION = "RESET PORTFOLIO";

type ResetCursor = {
  sort(specification: Document): { toArray(): Promise<Document[]> };
};

export type ResetCollection = {
  find(filter?: Document, options?: Document): ResetCursor;
  deleteMany(filter: Document): Promise<{ deletedCount: number }>;
  updateOne(
    filter: Document,
    update: Document,
    options?: Document,
  ): Promise<unknown>;
};

export type CloudResetCollections = {
  spaces: ResetCollection;
  drafts: ResetCollection;
  documents: ResetCollection;
  chunks: ResetCollection;
  metadata: ResetCollection;
};

type BackupData = {
  spaces: Document[];
  drafts: Document[];
  documents: Document[];
  chunks: Document[];
  metadata: Document[];
};

export type CloudResetBackup = {
  schemaVersion: 1;
  fingerprint: string;
  snapshot: Record<keyof BackupData, number>;
  data: BackupData;
};

const spacesName = () => process.env.CLOUD_SPACES_COLLECTION_NAME || "portfolio_public_spaces";
const draftsName = () => process.env.CLOUD_DRAFTS_COLLECTION_NAME || "portfolio_public_drafts";
const documentsName = () => process.env.CLOUD_DOCUMENTS_COLLECTION_NAME || "portfolio_public_documents";
const chunksName = () => process.env.CLOUD_COLLECTION_NAME || "portfolio_knowledge_public";
const metadataName = () => process.env.CLOUD_METADATA_COLLECTION_NAME || "portfolio_public_metadata";

function sanitize(value: unknown): unknown {
  if (value instanceof Date) return value.toISOString();
  if (Array.isArray(value)) return value.map(sanitize);
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    const result: Record<string, unknown> = {};
    for (const key of Object.keys(record).sort()) {
      if (key === "_id" || key === "embedding") continue;
      result[key] = sanitize(record[key]);
    }
    return result;
  }
  return value;
}

function canonicalJson(value: unknown): string {
  return JSON.stringify(sanitize(value));
}

async function readCollection(collection: ResetCollection): Promise<Document[]> {
  const rows = await collection.find({}, { projection: { embedding: 0 } }).sort({ _id: 1 }).toArray();
  return rows
    .map((row) => sanitize(row) as Document)
    .sort((first, second) => canonicalJson(first).localeCompare(canonicalJson(second)));
}

export async function buildCloudResetBackup(
  collections: CloudResetCollections,
): Promise<CloudResetBackup> {
  const [spaces, drafts, documents, chunks, metadata] = await Promise.all([
    readCollection(collections.spaces),
    readCollection(collections.drafts),
    readCollection(collections.documents),
    readCollection(collections.chunks),
    readCollection(collections.metadata),
  ]);
  const data = { spaces, drafts, documents, chunks, metadata };
  const snapshot = {
    spaces: spaces.length,
    drafts: drafts.length,
    documents: documents.length,
    chunks: chunks.length,
    metadata: metadata.length,
  };
  const fingerprint = createHash("sha256").update(canonicalJson(data)).digest("hex");
  return { schemaVersion: 1, fingerprint, snapshot, data };
}

export async function resetCloudCollections(
  collections: CloudResetCollections,
  confirmation: string,
  expectedFingerprint: string,
) {
  if (confirmation !== CLOUD_RESET_CONFIRMATION) {
    throw new Error(`Type ${CLOUD_RESET_CONFIRMATION} to confirm the reset`);
  }
  const current = await buildCloudResetBackup(collections);
  if (!expectedFingerprint || expectedFingerprint !== current.fingerprint) {
    throw new PublishConflictError(
      "Cloud knowledge changed after the backup was downloaded. Download a fresh backup and retry.",
    );
  }

  const [drafts, documents, chunks, metadata, spaces] = await Promise.all([
    collections.drafts.deleteMany({}),
    collections.documents.deleteMany({}),
    collections.chunks.deleteMany({}),
    collections.metadata.deleteMany({}),
    collections.spaces.deleteMany({ space_id: { $ne: "portfolio" } }),
  ]);
  const now = new Date();
  await collections.spaces.updateOne(
    { space_id: "portfolio" },
    {
      $set: {
        name: "Portfolio",
        description: "Public resume, internship, and project evidence.",
        status: "active",
        visibility: "public",
        updated_at: now,
      },
      $setOnInsert: { created_at: now },
    },
    { upsert: true },
  );
  return {
    deleted: {
      drafts: drafts.deletedCount,
      documents: documents.deletedCount,
      chunks: chunks.deletedCount,
      metadata: metadata.deletedCount,
      spaces: spaces.deletedCount,
    },
  };
}

async function cloudResetCollections(): Promise<CloudResetCollections> {
  const db = await cloudDb();
  return {
    spaces: db.collection(spacesName()) as unknown as ResetCollection,
    drafts: db.collection(draftsName()) as unknown as ResetCollection,
    documents: db.collection(documentsName()) as unknown as ResetCollection,
    chunks: db.collection(chunksName()) as unknown as ResetCollection,
    metadata: db.collection(metadataName()) as unknown as ResetCollection,
  };
}

export async function previewCloudReset() {
  const backup = await buildCloudResetBackup(await cloudResetCollections());
  return { fingerprint: backup.fingerprint, snapshot: backup.snapshot };
}

export async function exportCloudResetBackup() {
  return buildCloudResetBackup(await cloudResetCollections());
}

export async function resetCloudKnowledge(confirmation: string, fingerprint: string) {
  return resetCloudCollections(
    await cloudResetCollections(),
    confirmation,
    fingerprint,
  );
}
