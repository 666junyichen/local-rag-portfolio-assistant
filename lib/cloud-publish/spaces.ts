import { createHash } from "node:crypto";
import type { Document } from "mongodb";

import { cloudDb } from "../cloud-rag/mongodb";
import {
  DEFAULT_SPACE_ID,
  normalizeSpaceIds,
  publicSpaceView,
  type KnowledgeSpace,
} from "../cloud-rag/spaces";
import type { OwnerIdentity } from "./auth";

const spacesName = () => process.env.CLOUD_SPACES_COLLECTION_NAME || "portfolio_public_spaces";
const draftsName = () => process.env.CLOUD_DRAFTS_COLLECTION_NAME || "portfolio_public_drafts";
const documentsName = () => process.env.CLOUD_DOCUMENTS_COLLECTION_NAME || "portfolio_public_documents";
const chunksName = () => process.env.CLOUD_COLLECTION_NAME || "portfolio_knowledge_public";

let migrationReady: Promise<void> | undefined;

export const DEFAULT_PUBLIC_SPACES = [
  { space_id: DEFAULT_SPACE_ID, name: "Portfolio", description: "Public resume, internship, and project evidence." },
  { space_id: "rag-learning", name: "RAG Learning", description: "Public RAG books, courses, experiments, and study notes." },
  { space_id: "project-docs", name: "Project Docs", description: "Public documentation for standalone software and data projects." },
] as const;

export function withVectorSpaceFilter(definition: Document): Document {
  const fields = Array.isArray(definition.fields) ? definition.fields : [];
  if (fields.some((field) => field?.path === "space_id")) return definition;
  return {
    ...definition,
    fields: [...fields, { type: "filter", path: "space_id" }],
  };
}

export function withTextSpaceFilter(definition: Document): Document {
  const mappings = definition.mappings && typeof definition.mappings === "object"
    ? definition.mappings
    : {};
  const fields = mappings.fields && typeof mappings.fields === "object"
    ? mappings.fields
    : {};
  if (fields.space_id) return definition;
  return {
    ...definition,
    mappings: {
      ...mappings,
      fields: { ...fields, space_id: { type: "token" } },
    },
  };
}

export function publicDocumentCountMatch(): Document {
  return {
    visibility: "public",
    $or: [{ status: "published" }, { status: { $exists: false } }],
  };
}

const stableSuffix = (value: string) => createHash("sha256").update(value).digest("hex").slice(0, 6);

export function slugifySpaceName(value: string): string {
  const base = value.trim().toLowerCase()
    .replace(/[^a-z0-9\s-]/g, "")
    .replace(/[\s_-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40);
  return base || `space-${stableSuffix(value)}`;
}

export async function ensureCloudSpaces(): Promise<void> {
  if (!migrationReady) migrationReady = (async () => {
    const db = await cloudDb();
    const now = new Date();
    await db.collection(spacesName()).createIndex({ space_id: 1 }, { unique: true });
    await db.collection(spacesName()).bulkWrite(DEFAULT_PUBLIC_SPACES.map((space) => ({
      updateOne: {
        filter: { space_id: space.space_id },
        update: { $setOnInsert: {
          ...space,
          status: "active",
          visibility: "public",
          created_at: now,
          updated_at: now,
        } },
        upsert: true,
      },
    })));
    await Promise.all([
      db.collection(draftsName()).updateMany({ space_id: { $exists: false } }, { $set: { space_id: DEFAULT_SPACE_ID } }),
      db.collection(documentsName()).updateMany(
        { space_id: { $exists: false } },
        { $set: { space_id: DEFAULT_SPACE_ID, space_name: "Portfolio" } },
      ),
      db.collection(chunksName()).updateMany(
        { space_id: { $exists: false } },
        { $set: {
          space_id: DEFAULT_SPACE_ID,
          space_name: "Portfolio",
          "metadata.space_id": DEFAULT_SPACE_ID,
          "metadata.space_name": "Portfolio",
        } },
      ),
    ]);

    const chunks = db.collection(chunksName());
    const indexes = await chunks.listSearchIndexes().toArray().catch(() => []) as Document[];
    const vectorName = process.env.CLOUD_VECTOR_INDEX_NAME || "vector_index_public";
    const textName = process.env.CLOUD_TEXT_INDEX_NAME || "text_index_public";

    const vectorIndex = indexes.find((index) => index.name === vectorName);
    const vectorDefinition = vectorIndex?.latestDefinition || vectorIndex?.definition;
    if (vectorDefinition && !vectorDefinition.fields?.some((field: Document) => field.path === "space_id")) {
      await chunks.updateSearchIndex(vectorName, withVectorSpaceFilter(vectorDefinition));
    }

    const textIndex = indexes.find((index) => index.name === textName);
    const textDefinition = textIndex?.latestDefinition || textIndex?.definition;
    if (textDefinition && !textDefinition.mappings?.fields?.space_id) {
      await chunks.updateSearchIndex(textName, withTextSpaceFilter(textDefinition)).catch(() => {
        console.warn("Atlas text index could not be updated; vector retrieval remains available.");
      });
    }
    await chunks.createIndex({ visibility: 1, space_id: 1, doc_id: 1 });
  })().catch((error) => {
    migrationReady = undefined;
    throw error;
  });
  return migrationReady;
}

async function withDocumentCounts(rows: Document[]): Promise<KnowledgeSpace[]> {
  const db = await cloudDb();
  const counts = await db.collection(documentsName()).aggregate([
    { $match: publicDocumentCountMatch() },
    { $group: { _id: "$space_id", count: { $sum: 1 } } },
  ]).toArray();
  const bySpace = new Map(counts.map((item) => [String(item._id || DEFAULT_SPACE_ID), Number(item.count || 0)]));
  return rows.map((row) => publicSpaceView({ ...row, document_count: bySpace.get(String(row.space_id)) || 0 }));
}

export async function listPublicSpaces(): Promise<KnowledgeSpace[]> {
  await ensureCloudSpaces();
  const db = await cloudDb();
  const rows = await db.collection(spacesName()).find({ status: "active", visibility: "public" }).sort({ name: 1 }).toArray();
  return withDocumentCounts(rows);
}

export async function requireActivePublicSpaces(raw?: string[]): Promise<string[]> {
  await ensureCloudSpaces();
  const spaceIds = normalizeSpaceIds(raw);
  const db = await cloudDb();
  const count = await db.collection(spacesName()).countDocuments({
    space_id: { $in: spaceIds },
    status: "active",
    visibility: "public",
  });
  if (count !== spaceIds.length) throw new Error("One or more knowledge spaces are unavailable");
  return spaceIds;
}

export async function listOwnerSpaces(_owner: OwnerIdentity): Promise<KnowledgeSpace[]> {
  await ensureCloudSpaces();
  const db = await cloudDb();
  const rows = await db.collection(spacesName()).find({ visibility: "public" }).sort({ status: 1, name: 1 }).toArray();
  return withDocumentCounts(rows);
}

export async function createOwnerSpace(owner: OwnerIdentity, input: { name: string; description?: string }): Promise<KnowledgeSpace> {
  await ensureCloudSpaces();
  const name = input.name.trim().slice(0, 80);
  if (!name) throw new Error("Space name is required");
  const base = slugifySpaceName(name);
  const db = await cloudDb();
  let spaceId = base;
  if (await db.collection(spacesName()).findOne({ space_id: spaceId })) spaceId = `${base.slice(0, 40)}-${stableSuffix(`${owner.userId}:${name}`)}`;
  const row = {
    space_id: spaceId,
    name,
    description: String(input.description || "").trim().slice(0, 300),
    status: "active",
    visibility: "public",
    owner_id: owner.userId,
    created_at: new Date(),
    updated_at: new Date(),
  };
  await db.collection(spacesName()).insertOne(row);
  return publicSpaceView(row);
}

export async function updateOwnerSpace(
  _owner: OwnerIdentity,
  spaceId: string,
  patch: { name?: string; description?: string; status?: "active" | "archived" },
): Promise<KnowledgeSpace> {
  await ensureCloudSpaces();
  if (spaceId === DEFAULT_SPACE_ID && patch.status === "archived") throw new Error("The default Portfolio space cannot be archived");
  const update: Document = { updated_at: new Date() };
  if (patch.name !== undefined) {
    const name = patch.name.trim().slice(0, 80);
    if (!name) throw new Error("Space name is required");
    update.name = name;
  }
  if (patch.description !== undefined) update.description = patch.description.trim().slice(0, 300);
  if (patch.status !== undefined) update.status = patch.status;
  const db = await cloudDb();
  const row = await db.collection(spacesName()).findOneAndUpdate(
    { space_id: spaceId, visibility: "public" },
    { $set: update },
    { returnDocument: "after" },
  );
  if (!row) throw new Error("Knowledge space not found");
  if (update.name) {
    await Promise.all([
      db.collection(documentsName()).updateMany({ space_id: spaceId }, { $set: { space_name: update.name, updated_at: new Date() } }),
      db.collection(chunksName()).updateMany({ space_id: spaceId }, { $set: { space_name: update.name, "metadata.space_name": update.name } }),
    ]);
  }
  return publicSpaceView(row);
}

export async function spaceNameMap(spaceIds: string[]): Promise<Map<string, string>> {
  await ensureCloudSpaces();
  const db = await cloudDb();
  const rows = await db.collection(spacesName()).find({ space_id: { $in: normalizeSpaceIds(spaceIds) } }).toArray();
  return new Map(rows.map((row) => [String(row.space_id), String(row.name)]));
}
