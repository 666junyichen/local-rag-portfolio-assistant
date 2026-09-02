import { createHash } from "node:crypto";
import fs from "node:fs/promises";
import fsSync from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { MongoClient } from "mongodb";

function loadDotEnv(file) {
  const envPath = path.resolve(process.cwd(), file);
  if (!fsSync.existsSync(envPath)) return;
  for (const line of fsSync.readFileSync(envPath, "utf8").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) continue;
    const [key, ...parts] = trimmed.split("=");
    if (!process.env[key]) process.env[key] = parts.join("=").replace(/^['"]|['"]$/g, "");
  }
}

const digest = (value, size = 20) => createHash("sha256").update(value, "utf8").digest("hex").slice(0, size);
const mojibake = /\uFFFD|(?:涓|鍏|绠|鏁|鎶|鐨|绯|闄|鍖|锛){3,}/;

export function normalizePublicDocuments(rows) {
  if (!Array.isArray(rows)) throw new Error("portfolio_docs.json must contain a JSON array");
  const hashes = new Set();
  const docIds = new Set();
  return rows.map((raw, index) => {
    const title = String(raw.title || "").trim();
    const body = String(raw.body || "").trim();
    const visibility = raw.visibility || raw.metadata?.visibility || "public";
    if (!title || !body) throw new Error(`Document ${index + 1} has an empty title or body`);
    if (visibility !== "public") throw new Error(`Document ${index + 1} is not public; cloud seed aborted`);
    if (mojibake.test(`${title}\n${body}`)) throw new Error(`Document ${index + 1} contains mojibake`);
    const contentHash = raw.content_hash || digest(body, 64);
    if (hashes.has(contentHash)) throw new Error(`Duplicate content hash at document ${index + 1}`);
    hashes.add(contentHash);
    const docId = raw.doc_id || `doc_${digest(`${title}\n${contentHash}`)}`;
    if (docIds.has(docId)) throw new Error(`Duplicate doc_id at document ${index + 1}: ${docId}`);
    docIds.add(docId);
    const metadata = raw.metadata || {};
    return {
      ...raw,
      title,
      body,
      doc_id: docId,
      content_hash: contentHash,
      visibility: "public",
      status: "published",
      source_origin: "repo_seed",
      space_id: String(raw.space_id || metadata.space_id || "portfolio"),
      space_name: String(raw.space_name || metadata.space_name || "Portfolio"),
      summary: String(raw.summary || body.slice(0, 240)).trim(),
      category: String(raw.category || metadata.category || "portfolio"),
      language: raw.language === "zh" || metadata.language === "zh" ? "zh" : "en",
      source_url: raw.source_url || raw.url || null,
      metadata: {
        ...metadata,
        visibility: "public",
        source_origin: "repo_seed",
        space_id: String(raw.space_id || metadata.space_id || "portfolio"),
        space_name: String(raw.space_name || metadata.space_name || "Portfolio"),
      },
    };
  });
}

export function chunkDocuments(documents, size = 800, overlap = 80) {
  const records = [];
  for (const doc of documents) {
    let start = 0; let index = 0;
    while (start < doc.body.length) {
      const rawBody = doc.body.slice(start, start + size);
      const metadata = doc.metadata || {};
      const prefixParts = [`Document: ${doc.title}`];
      if (metadata.project) prefixParts.push(`Project: ${metadata.project}`);
      if (metadata.category) prefixParts.push(`Category: ${metadata.category}`);
      if (metadata.source) prefixParts.push(`Source: ${metadata.source}`);
      if (doc.updated || metadata.modified_at) prefixParts.push(`Updated: ${doc.updated || metadata.modified_at}`);
      const contextPrefix = `[${prefixParts.join(" | ")}]`;
      records.push({
        ...doc,
        source_origin: "repo_seed",
        body: rawBody,
        raw_body: rawBody,
        retrieval_text: `${contextPrefix}\n${rawBody}`,
        context_prefix: contextPrefix,
        section_path: "",
        source_updated_at: doc.updated || metadata.modified_at || null,
        validity_status: "active",
        chunk_index: index,
        chunk_id: `${doc.doc_id}_chunk_${index}_${digest(rawBody, 10)}`,
      });
      if (start + size >= doc.body.length) break;
      start += size - overlap; index += 1;
    }
  }
  const chunkIds = new Set();
  for (const record of records) {
    if (chunkIds.has(record.chunk_id)) throw new Error(`Duplicate chunk_id generated: ${record.chunk_id}`);
    chunkIds.add(record.chunk_id);
  }
  return records;
}

export async function syncRepoSeedCatalog({ documentsCollection, documents, session, now }) {
  const documentIds = documents.map((document) => document.doc_id);
  if (documents.length) {
    await documentsCollection.bulkWrite(documents.map((document) => ({
      updateOne: {
        filter: { source_origin: "repo_seed", doc_id: document.doc_id },
        update: {
          $set: {
            doc_id: document.doc_id,
            source_origin: "repo_seed",
            space_id: document.space_id,
            space_name: document.space_name,
            title: document.title,
            summary: document.summary,
            category: document.category,
            language: document.language,
            cleaned_body: document.body,
            content_hash: document.content_hash,
            status: "published",
            visibility: "public",
            publication_version: 1,
            source_url: document.source_url,
            updated_at: now,
            published_at: now,
          },
          $setOnInsert: { created_at: now },
        },
        upsert: true,
      },
    })), { session });
  }
  await documentsCollection.deleteMany(
    { source_origin: "repo_seed", doc_id: { $nin: documentIds } },
    { session },
  );
}

export const publicTextIndexDefinition = { mappings: {
  dynamic: false,
  fields: {
    title: { type: "string" },
    body: { type: "string" },
    retrieval_text: { type: "string" },
    visibility: { type: "token" },
    space_id: { type: "token" },
    metadata: { type: "document", dynamic: true },
  },
} };

export function mergePublicTextIndexDefinition(existingDefinition = {}) {
  const existingMappings = existingDefinition.mappings && typeof existingDefinition.mappings === "object"
    ? existingDefinition.mappings
    : {};
  const existingFields = existingMappings.fields && typeof existingMappings.fields === "object"
    ? existingMappings.fields
    : {};
  return {
    ...publicTextIndexDefinition,
    ...existingDefinition,
    mappings: {
      ...publicTextIndexDefinition.mappings,
      ...existingMappings,
      fields: {
        ...publicTextIndexDefinition.mappings.fields,
        ...existingFields,
        ...Object.fromEntries(
          Object.entries(publicTextIndexDefinition.mappings.fields)
            .filter(([field]) => !existingFields[field]),
        ),
      },
    },
  };
}

export async function reconcilePublicTextIndex(collection, existingSearchIndexes, textIndexName) {
  const existingTextIndex = existingSearchIndexes.find((index) => index.name === textIndexName);
  const textDefinition = existingTextIndex?.latestDefinition || existingTextIndex?.definition;
  const requiredFields = Object.keys(publicTextIndexDefinition.mappings.fields);
  const existingFields = textDefinition?.mappings?.fields || {};
  const missingFields = requiredFields.filter((field) => !existingFields[field]);
  try {
    if (!existingTextIndex) {
      await collection.createSearchIndex({ name: textIndexName, type: "search", definition: publicTextIndexDefinition });
      return { name: textIndexName, status: "created", available: true };
    }
    if (!textDefinition || missingFields.length) {
      await collection.updateSearchIndex(textIndexName, mergePublicTextIndexDefinition(textDefinition || {}));
      return { name: textIndexName, status: "updated", available: true, addedFields: missingFields };
    }
    return { name: textIndexName, status: "ready", available: true };
  } catch (error) {
    return {
      name: textIndexName,
      status: "unavailable",
      available: false,
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

const seedProviders = new Set(["openai", "gemini"]);

function normalizeSeedProvider(value) {
  const normalized = String(value || "").trim().toLowerCase();
  return seedProviders.has(normalized) ? normalized : null;
}

export function resolveSeedEmbeddingConfig() {
  const provider = normalizeSeedProvider(process.env.CLOUD_EMBEDDING_PROVIDER)
    || (process.env.OPENAI_API_KEY ? "openai" : "gemini");
  if (provider === "openai") {
    return {
      provider,
      model: process.env.OPENAI_EMBEDDING_MODEL || "text-embedding-3-small",
      apiKeyEnv: "OPENAI_API_KEY",
    };
  }
  return {
    provider: "gemini",
    model: process.env.GEMINI_EMBEDDING_MODEL || "gemini-embedding-001",
    apiKeyEnv: "GEMINI_API_KEY",
  };
}

function requireSeedEmbeddingCredentials(config) {
  if (!process.env[config.apiKeyEnv]) throw new Error(`${config.apiKeyEnv} is required for ${config.provider} embeddings`);
}

function openAIEmbeddingPayload(texts, model) {
  const dimensions = Number(process.env.OPENAI_EMBEDDING_DIMENSIONS || 0);
  return {
    model,
    input: texts,
    encoding_format: "float",
    ...(Number.isInteger(dimensions) && dimensions > 0 ? { dimensions } : {}),
  };
}

async function embedOpenAIDocumentBatch(texts, model) {
  const response = await fetch("https://api.openai.com/v1/embeddings", {
    method: "POST",
    headers: { Authorization: `Bearer ${process.env.OPENAI_API_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify(openAIEmbeddingPayload(texts, model)),
  });
  if (!response.ok) throw new Error(`OpenAI embedding failed (${response.status})`);
  const result = await response.json();
  const rows = [...(result.data || [])].sort((left, right) => Number(left.index || 0) - Number(right.index || 0));
  if (rows.length !== texts.length || rows.some((row) => !row.embedding?.length)) {
    throw new Error("OpenAI returned incomplete embeddings");
  }
  return rows.map((row) => row.embedding);
}

async function embedGeminiDocument(text, model) {
  const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${model}:embedContent`, {
    method: "POST",
    headers: { "x-goog-api-key": process.env.GEMINI_API_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({ model: `models/${model}`, taskType: "RETRIEVAL_DOCUMENT", content: { parts: [{ text }] } }),
  });
  if (!response.ok) throw new Error(`Gemini embedding failed (${response.status})`);
  const result = await response.json();
  if (!result.embedding?.values) throw new Error("Gemini returned no embedding");
  return result.embedding.values;
}

async function embedSeedDocuments(texts, config) {
  if (!texts.length) return [];
  requireSeedEmbeddingCredentials(config);
  if (config.provider === "openai") {
    const output = [];
    const batchSize = 96;
    for (let start = 0; start < texts.length; start += batchSize) {
      const batch = texts.slice(start, start + batchSize);
      output.push(...await embedOpenAIDocumentBatch(batch, config.model));
      console.log(`Embedded ${Math.min(start + batch.length, texts.length)}/${texts.length} with OpenAI`);
    }
    return output;
  }
  const output = [];
  for (let index = 0; index < texts.length; index += 1) {
    output.push(await embedGeminiDocument(texts[index], config.model));
    console.log(`Embedded ${index + 1}/${texts.length} with Gemini`);
  }
  return output;
}

export function buildVectorIndexDefinition(embeddingDimensions) {
  return { fields: [
      { type: "vector", path: "embedding", numDimensions: embeddingDimensions, similarity: "cosine" },
      { type: "filter", path: "visibility" },
      { type: "filter", path: "space_id" },
      { type: "filter", path: "metadata.category" },
      { type: "filter", path: "metadata.language" },
    ] };
}

async function main() {
  loadDotEnv(".env.local"); loadDotEnv(".env");
  const publicPath = path.resolve(process.cwd(), "data", "portfolio_docs.json");
  const documents = normalizePublicDocuments(JSON.parse(await fs.readFile(publicPath, "utf8")));
  const chunks = chunkDocuments(documents);
  console.log(`Validated ${documents.length} public documents and ${chunks.length} chunks.`);
  if (process.argv.includes("--validate")) return;
  const applyRequested = process.argv.includes("--apply");
  if (!applyRequested) {
    console.log("Seed is validation-only by default. Pass --apply --confirm=SEED_PUBLIC_PORTFOLIO to write Atlas data.");
    return;
  }
  if (!process.argv.includes("--confirm=SEED_PUBLIC_PORTFOLIO")) {
    throw new Error("Atlas seed requires --confirm=SEED_PUBLIC_PORTFOLIO");
  }
  const catalogOnly = process.argv.includes("--catalog-only");
  const spacesOnly = process.argv.includes("--spaces-only");
  if (!process.env.MONGODB_URI) throw new Error("MONGODB_URI is required");
  const embeddingConfig = resolveSeedEmbeddingConfig();
  if (!catalogOnly && !spacesOnly && chunks.length) requireSeedEmbeddingCredentials(embeddingConfig);
  if (!catalogOnly && !spacesOnly) {
    const embeddings = await embedSeedDocuments(chunks.map((chunk) => chunk.retrieval_text), embeddingConfig);
    for (let index = 0; index < chunks.length; index += 1) {
      chunks[index].embedding = embeddings[index];
    }
  }
  const client = new MongoClient(process.env.MONGODB_URI);
  await client.connect();
  const db = client.db(process.env.CLOUD_DB_NAME || "portfolio_rag");
  const collection = db.collection(process.env.CLOUD_COLLECTION_NAME || "portfolio_knowledge_public");
  const documentsCollection = db.collection(process.env.CLOUD_DOCUMENTS_COLLECTION_NAME || "portfolio_public_documents");
  const metadataCollection = db.collection(process.env.CLOUD_METADATA_COLLECTION_NAME || "portfolio_public_metadata");
  const spacesCollection = db.collection(process.env.CLOUD_SPACES_COLLECTION_NAME || "portfolio_public_spaces");
  const now = new Date();

  await spacesCollection.bulkWrite([
    ["portfolio", "Portfolio", "Public resume, internship, and project evidence."],
  ].map(([spaceId, name, description]) => ({ updateOne: {
    filter: { space_id: spaceId },
    update: { $setOnInsert: { space_id: spaceId, name, description, status: "active", visibility: "public", created_at: now, updated_at: now } },
    upsert: true,
  } })));
  await spacesCollection.createIndex({ space_id: 1 }, { unique: true });
  await Promise.all([
    documentsCollection.updateMany({ space_id: { $exists: false } }, { $set: { space_id: "portfolio", space_name: "Portfolio" } }),
    collection.updateMany({ space_id: { $exists: false } }, { $set: {
      space_id: "portfolio",
      space_name: "Portfolio",
      "metadata.space_id": "portfolio",
      "metadata.space_name": "Portfolio",
    } }),
  ]);

  if (spacesOnly) {
    const indexName = process.env.CLOUD_VECTOR_INDEX_NAME || "vector_index_public";
    const textIndexName = process.env.CLOUD_TEXT_INDEX_NAME || "text_index_public";
    const indexes = await collection.listSearchIndexes().toArray().catch(() => []);
    const vectorIndex = indexes.find((index) => index.name === indexName);
    const vectorDefinition = vectorIndex?.latestDefinition || vectorIndex?.definition;
    if (vectorDefinition && !vectorDefinition.fields?.some((field) => field.path === "space_id")) {
      await collection.updateSearchIndex(indexName, {
        ...vectorDefinition,
        fields: [...(vectorDefinition.fields || []), { type: "filter", path: "space_id" }],
      });
    }
    const textIndexResult = await reconcilePublicTextIndex(collection, indexes, textIndexName);
    if (!textIndexResult.available) console.warn(`Atlas text index unavailable: ${textIndexResult.error}. Vector retrieval remains available.`);
    await collection.createIndex({ visibility: 1, space_id: 1, doc_id: 1 });
    await documentsCollection.createIndex({ doc_id: 1 }, { unique: true });
    await client.close();
    console.log("Space migration complete without generating embeddings.");
    return;
  }

  if (catalogOnly) {
    const session = client.startSession();
    try {
      await session.withTransaction(async () => {
        await syncRepoSeedCatalog({ documentsCollection, documents, session, now });
      });
    } finally {
      await session.endSession();
    }
    await documentsCollection.createIndex({ doc_id: 1 }, { unique: true });
    const ownerUploadCount = await documentsCollection.countDocuments({ source_origin: "owner_upload" });
    await client.close();
    console.log(`Backfilled ${documents.length} repository catalog records without generating embeddings. Preserved ${ownerUploadCount} owner-upload documents.`);
    return;
  }
  const indexName = process.env.CLOUD_VECTOR_INDEX_NAME || "vector_index_public";
  const textIndexName = process.env.CLOUD_TEXT_INDEX_NAME || "text_index_public";
  if (!chunks.length) {
    const existingSearchIndexes = await collection.listSearchIndexes().toArray().catch(() => []);
    const session = client.startSession();
    try {
      await session.withTransaction(async () => {
        await collection.deleteMany({ source_origin: "repo_seed" }, { session });
        await syncRepoSeedCatalog({ documentsCollection, documents, session, now });
        await metadataCollection.deleteOne({ _id: "repo_seed_embedding" }, { session });
      });
    } finally {
      await session.endSession();
    }
    const textIndexResult = await reconcilePublicTextIndex(collection, existingSearchIndexes, textIndexName);
    console.log(`Text index ${textIndexName}: ${textIndexResult.status}`);
    if (!textIndexResult.available) console.warn(`Atlas text index unavailable: ${textIndexResult.error}. Vector retrieval remains available.`);
    await collection.createIndex({ visibility: 1, space_id: 1, doc_id: 1 });
    await collection.createIndex({ chunk_id: 1 }, { unique: true, sparse: true });
    await documentsCollection.createIndex({ doc_id: 1 }, { unique: true });
    const ownerUploadCount = await collection.countDocuments({ source_origin: "owner_upload" });
    await client.close();
    console.log(`No repository public seed documents found. Cleared repository seed chunks/catalog records and preserved ${ownerUploadCount} owner-upload chunks.`);
    return;
  }
  const embeddingProvider = embeddingConfig.provider;
  const embeddingModel = embeddingConfig.model;
  const embeddingDimensions = chunks[0]?.embedding?.length || 0;
  if (!embeddingDimensions) throw new Error("The seed produced no embedding dimensions");

  const existingContract = await metadataCollection.findOne({ _id: "repo_seed_embedding" });
  if (existingContract && (
    (existingContract.provider && existingContract.provider !== embeddingProvider)
    || existingContract.model !== embeddingModel
    || Number(existingContract.num_dimensions) !== embeddingDimensions
  )) {
    console.log(`Embedding contract changed from ${existingContract.provider || "legacy"}:${existingContract.model}/${existingContract.num_dimensions} to ${embeddingProvider}:${embeddingModel}/${embeddingDimensions}.`);
  }
  const existingSearchIndexes = await collection.listSearchIndexes().toArray().catch(() => []);
  const existingVectorIndex = existingSearchIndexes.find((index) => index.name === indexName);
  const vectorDefinition = existingVectorIndex?.latestDefinition || existingVectorIndex?.definition;
  const vectorField = vectorDefinition?.fields?.find((field) => field.path === "embedding");
  const vectorIndexDefinition = buildVectorIndexDefinition(embeddingDimensions);
  const vectorNeedsUpdate = !vectorDefinition?.fields?.some((field) => field.path === "space_id")
    || !vectorField?.numDimensions
    || Number(vectorField.numDimensions) !== embeddingDimensions;
  await metadataCollection.createIndex({ updated_at: 1 });
  const chunkIds = chunks.map((chunk) => chunk.chunk_id);
  const session = client.startSession();
  try {
    await session.withTransaction(async () => {
      await collection.bulkWrite(chunks.map((chunk) => ({
        replaceOne: {
          filter: { source_origin: "repo_seed", chunk_id: chunk.chunk_id },
          replacement: { ...chunk, source_origin: "repo_seed", seeded_at: now },
          upsert: true,
        },
      })), { session });
      await collection.deleteMany(
        { source_origin: "repo_seed", chunk_id: { $nin: chunkIds } },
        { session },
      );
      await syncRepoSeedCatalog({ documentsCollection, documents, session, now });
      await metadataCollection.updateOne(
        { _id: "repo_seed_embedding" },
        { $set: { provider: embeddingProvider, model: embeddingModel, num_dimensions: embeddingDimensions, updated_at: now } },
        { upsert: true, session },
      );
    });
  } finally {
    await session.endSession();
  }

  if (!existingSearchIndexes.some((index) => index.name === indexName)) await collection.createSearchIndex({ name: indexName, type: "vectorSearch", definition: vectorIndexDefinition });
  else if (vectorNeedsUpdate) await collection.updateSearchIndex(indexName, vectorIndexDefinition);

  const textIndexResult = await reconcilePublicTextIndex(collection, existingSearchIndexes, textIndexName);
  console.log(`Text index ${textIndexName}: ${textIndexResult.status}`);
  if (!textIndexResult.available) console.warn(`Atlas text index unavailable: ${textIndexResult.error}. Vector retrieval remains available.`);
  await collection.createIndex({ visibility: 1, space_id: 1, doc_id: 1 });
  await collection.createIndex({ chunk_id: 1 }, { unique: true, sparse: true });
  await documentsCollection.createIndex({ doc_id: 1 }, { unique: true });
  const ownerUploadCount = await collection.countDocuments({ source_origin: "owner_upload" });
  await client.close();
  console.log(`Seeded ${chunks.length} repository chunks and ${documents.length} catalog records. Preserved ${ownerUploadCount} owner-upload chunks.`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  main().catch((error) => { console.error(error.message); process.exit(1); });
}
