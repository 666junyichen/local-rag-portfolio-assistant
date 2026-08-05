import { createHash } from "node:crypto";
import fs from "node:fs/promises";
import fsSync from "node:fs";
import path from "node:path";
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

function normalizePublicDocuments(rows) {
  if (!Array.isArray(rows)) throw new Error("portfolio_docs.json must contain a JSON array");
  const hashes = new Set();
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
    return { ...raw, title, body, doc_id: docId, content_hash: contentHash, visibility: "public", metadata: { ...(raw.metadata || {}), visibility: "public" } };
  });
}

function chunkDocuments(documents, size = 800, overlap = 80) {
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
  return records;
}

async function embedDocument(text) {
  const model = process.env.GEMINI_EMBEDDING_MODEL || "gemini-embedding-001";
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

async function main() {
  loadDotEnv(".env.local"); loadDotEnv(".env");
  const publicPath = path.resolve(process.cwd(), "data", "portfolio_docs.json");
  const documents = normalizePublicDocuments(JSON.parse(await fs.readFile(publicPath, "utf8")));
  const chunks = chunkDocuments(documents);
  console.log(`Validated ${documents.length} public documents and ${chunks.length} chunks.`);
  if (process.argv.includes("--validate")) return;
  if (!process.env.MONGODB_URI || !process.env.GEMINI_API_KEY) throw new Error("MONGODB_URI and GEMINI_API_KEY are required");
  for (let index = 0; index < chunks.length; index += 1) {
    chunks[index].embedding = await embedDocument(chunks[index].retrieval_text);
    console.log(`Embedded ${index + 1}/${chunks.length}`);
  }
  const client = new MongoClient(process.env.MONGODB_URI);
  await client.connect();
  const db = client.db(process.env.CLOUD_DB_NAME || "portfolio_rag");
  const collection = db.collection(process.env.CLOUD_COLLECTION_NAME || "portfolio_knowledge_public");
  const indexName = process.env.CLOUD_VECTOR_INDEX_NAME || "vector_index_public";
  const textIndexName = process.env.CLOUD_TEXT_INDEX_NAME || "text_index_public";
  await collection.deleteMany({});
  await collection.insertMany(chunks.map((chunk) => ({ ...chunk, seeded_at: new Date() })));
  try { await collection.dropSearchIndex(indexName); await new Promise((resolve) => setTimeout(resolve, 5000)); } catch (error) { if (!String(error).includes("not found")) console.warn("Index drop skipped"); }
  await collection.createSearchIndex({ name: indexName, type: "vectorSearch", definition: { fields: [
    { type: "vector", path: "embedding", numDimensions: chunks[0].embedding.length, similarity: "cosine" },
    { type: "filter", path: "visibility" },
    { type: "filter", path: "metadata.category" },
    { type: "filter", path: "metadata.language" },
  ] } });
  try { await collection.dropSearchIndex(textIndexName); await new Promise((resolve) => setTimeout(resolve, 5000)); } catch (error) { if (!String(error).includes("not found")) console.warn("Text index drop skipped"); }
  await collection.createSearchIndex({ name: textIndexName, type: "search", definition: { mappings: {
    dynamic: false,
    fields: {
      title: { type: "string" },
      body: { type: "string" },
      retrieval_text: { type: "string" },
      visibility: { type: "token" },
      metadata: { type: "document", dynamic: true },
    },
  } } });
  await collection.createIndex({ visibility: 1, doc_id: 1 });
  await client.close();
  console.log(`Seeded ${chunks.length} public chunks into ${indexName} and ${textIndexName}. Atlas may need a few minutes to make the indexes queryable.`);
}

main().catch((error) => { console.error(error.message); process.exit(1); });
