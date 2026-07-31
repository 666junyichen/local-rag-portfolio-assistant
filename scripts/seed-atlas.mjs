import { MongoClient } from "mongodb";
import fs from "node:fs/promises";
import fsSync from "node:fs";
import path from "node:path";

function loadDotEnv(file = ".env") {
  const envPath = path.resolve(process.cwd(), file);
  if (!fsSync.existsSync(envPath)) return;
  const text = fsSync.readFileSync(envPath, "utf8");
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) continue;
    const [key, ...valueParts] = trimmed.split("=");
    if (!process.env[key]) {
      process.env[key] = valueParts.join("=").replace(/^['"]|['"]$/g, "");
    }
  }
}

const CHUNK_SIZE = 800;
const CHUNK_OVERLAP = 80;
const MOJIBAKE_PATTERN = /\u6D93|\u935C|\u7487|\u93AC|\u6FDE|\u7EE0|\u93C1|\u95C4|\uFFFD/;

function chunkText(text) {
  const chunks = [];
  let start = 0;
  while (start < text.length) {
    const end = Math.min(start + CHUNK_SIZE, text.length);
    chunks.push(text.slice(start, end));
    if (end === text.length) break;
    start = Math.max(0, end - CHUNK_OVERLAP);
  }
  return chunks;
}

async function geminiEmbedding(input) {
  if (!process.env.GEMINI_API_KEY) throw new Error("GEMINI_API_KEY is required.");
  const model = process.env.GEMINI_EMBEDDING_MODEL || "gemini-embedding-001";
  const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${model}:embedContent`, {
    method: "POST",
    headers: {
      "x-goog-api-key": process.env.GEMINI_API_KEY,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: `models/${model}`,
      taskType: "RETRIEVAL_DOCUMENT",
      content: {
        parts: [{ text: input }],
      },
    }),
  });

  if (!response.ok) {
    throw new Error(`Embedding request failed: ${response.status} ${await response.text()}`);
  }

  const result = await response.json();
  const values = (result.embedding && result.embedding.values) || (result.embeddings && result.embeddings[0].values);
  if (!values) throw new Error("Gemini embedding response did not include vector values.");
  return values;
}

async function embedInBatches(texts, batchSize = 32) {
  const vectors = [];
  for (let i = 0; i < texts.length; i += 1) {
    const embedded = await geminiEmbedding(texts[i]);
    vectors.push(embedded);
    console.log(`embedded=${i + 1}/${texts.length}`);
  }
  return vectors;
}

async function main() {
  loadDotEnv();
  if (!process.env.MONGODB_URI) throw new Error("MONGODB_URI is required.");
  if (!process.env.GEMINI_API_KEY) throw new Error("GEMINI_API_KEY is required.");
  if (!process.env.MONGODB_URI.includes("mongodb+srv://")) {
    console.warn("Warning: MONGODB_URI does not look like an Atlas SRV URI. Vector Search requires MongoDB Atlas.");
  }

  const docsPath = path.join(process.cwd(), "data", "portfolio_docs.json");
  const rawDocs = JSON.parse(await fs.readFile(docsPath, "utf8"));
  const docs = rawDocs.filter((doc) => !MOJIBAKE_PATTERN.test(`${doc.title}\n${doc.body}`));
  const chunks = [];

  for (const doc of docs) {
    for (const [index, body] of chunkText(doc.body).entries()) {
      chunks.push({
        ...doc,
        body,
        chunk_index: index,
        source_title: doc.title,
        seeded_at: new Date(),
      });
    }
  }

  console.log(`docs=${docs.length} skipped=${rawDocs.length - docs.length} chunks=${chunks.length}`);
  const vectors = await embedInBatches(chunks.map((chunk) => chunk.body));
  const records = chunks.map((chunk, index) => ({ ...chunk, embedding: vectors[index] }));

  const dbName = process.env.DB_NAME || "portfolio_rag";
  const collectionName = process.env.COLLECTION_NAME || "portfolio_knowledge_base";
  const vectorIndexName = process.env.VECTOR_INDEX_NAME || "vector_index";

  const client = new MongoClient(process.env.MONGODB_URI);
  await client.connect();
  const collection = client.db(dbName).collection(collectionName);

  await collection.deleteMany({});
  if (records.length) await collection.insertMany(records);

  try {
    await collection.dropSearchIndex(vectorIndexName);
    await new Promise((resolve) => setTimeout(resolve, 5000));
  } catch (error) {
    if (!String(error.message).includes("not found")) {
      console.warn(`dropSearchIndex warning: ${error.message}`);
    }
  }

  await collection.createSearchIndex({
    name: vectorIndexName,
    type: "vectorSearch",
    definition: {
      fields: [
        {
          type: "vector",
          path: "embedding",
          numDimensions: vectors[0].length,
          similarity: "cosine",
        },
      ],
    },
  });

  await collection.createIndex({ title: 1 });
  await collection.createIndex({ "metadata.category": 1 });
  await client.close();

  console.log(`seeded=${records.length} index=${vectorIndexName} dimensions=${vectors[0].length}`);
  console.log("MongoDB Atlas may need a short time to finish building the Vector Search index.");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
