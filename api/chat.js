const { MongoClient } = require("mongodb");

let cachedClient;

const DB_NAME = process.env.DB_NAME || "portfolio_rag";
const COLLECTION_NAME = process.env.COLLECTION_NAME || "portfolio_knowledge_base";
const VECTOR_INDEX_NAME = process.env.VECTOR_INDEX_NAME || "vector_index";
const EMBEDDING_MODEL = process.env.GEMINI_EMBEDDING_MODEL || "gemini-embedding-001";
const CHAT_MODEL = process.env.GEMINI_CHAT_MODEL || "gemini-3.5-flash";

function json(res, status, payload) {
  res.statusCode = status;
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.end(JSON.stringify(payload));
}

async function getClient() {
  if (cachedClient) return cachedClient;
  if (!process.env.MONGODB_URI) {
    throw new Error("MONGODB_URI is not configured.");
  }
  cachedClient = new MongoClient(process.env.MONGODB_URI, {
    serverSelectionTimeoutMS: 8000,
  });
  await cachedClient.connect();
  return cachedClient;
}

async function gemini(path, payload) {
  if (!process.env.GEMINI_API_KEY) {
    throw new Error("GEMINI_API_KEY is not configured.");
  }

  const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/${path}`, {
    method: "POST",
    headers: {
      "x-goog-api-key": process.env.GEMINI_API_KEY,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Gemini ${path} failed: ${response.status} ${detail.slice(0, 300)}`);
  }

  return response.json();
}

async function embed(text) {
  const result = await gemini(`models/${EMBEDDING_MODEL}:embedContent`, {
    model: `models/${EMBEDDING_MODEL}`,
    taskType: "RETRIEVAL_QUERY",
    content: {
      parts: [{ text: `task: question answering | query: ${text}` }],
    },
  });
  return (result.embedding && result.embedding.values) || (result.embeddings && result.embeddings[0].values);
}

async function retrieveContext(question) {
  const client = await getClient();
  const collection = client.db(DB_NAME).collection(COLLECTION_NAME);
  const queryVector = await embed(question);

  const docs = await collection
    .aggregate([
      {
        $vectorSearch: {
          index: VECTOR_INDEX_NAME,
          path: "embedding",
          queryVector,
          numCandidates: 80,
          limit: 5,
        },
      },
      {
        $project: {
          _id: 0,
          score: { $meta: "vectorSearchScore" },
          title: 1,
          body: 1,
          url: 1,
          metadata: 1,
        },
      },
    ])
    .toArray();

  return docs;
}

function buildSystemPrompt(docs) {
  const context = docs
    .map((doc, index) => {
      const title = doc.title || `Source ${index + 1}`;
      const url = doc.url ? `\nURL: ${doc.url}` : "";
      return `### ${title}${url}\n${doc.body}`;
    })
    .join("\n\n");

  return [
    "You are Junyi Chen's portfolio assistant for recruiters and interviewers.",
    "Answer only from the provided portfolio context. Do not invent experience, metrics, awards, employers, or project outcomes.",
    "If the context is insufficient, say that the available portfolio data does not confirm it.",
    "Answer in the same language as the user's question. For Chinese questions, use natural professional Chinese while keeping technical terms in English when useful.",
    "Keep answers concise, concrete, and recruiter-friendly. Mention project names, tools, and evidence when relevant.",
    "",
    "Portfolio context:",
    context || "No retrieved context.",
  ].join("\n");
}

function extractGeminiText(response) {
  if (response.output_text) return response.output_text;
  const stepText = (response.steps || [])
    .flatMap((step) => step.content || [])
    .map((part) => part.text)
    .filter(Boolean)
    .join("\n")
    .trim();
  return stepText || "";
}

async function answerQuestion(question, history) {
  const docs = await retrieveContext(question);
  const recentHistory = history
    .slice(-6)
    .map((item) => `${item.role === "assistant" ? "Assistant" : "User"}: ${String(item.content || "").slice(0, 1200)}`)
    .join("\n");

  const completion = await gemini("interactions", {
    model: CHAT_MODEL,
    system_instruction: buildSystemPrompt(docs),
    input: [recentHistory, `User question: ${question}`].filter(Boolean).join("\n\n"),
    generation_config: {
      temperature: 0.2,
    },
  });

  return {
    answer: extractGeminiText(completion) || "The assistant could not generate an answer from the retrieved portfolio context.",
    sources: docs.map((doc) => ({
      title: doc.title,
      url: doc.url,
      score: doc.score,
      category: doc.metadata && doc.metadata.category,
    })),
  };
}

module.exports = async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") return json(res, 200, { ok: true });
  if (req.method !== "POST") return json(res, 405, { error: "Method not allowed" });

  try {
    const body = typeof req.body === "object" && req.body ? req.body : JSON.parse(req.body || "{}");
    const question = String(body.question || "").trim();
    const history = Array.isArray(body.history) ? body.history : [];

    if (!question) {
      return json(res, 400, { error: "Please enter a question." });
    }

    if (!process.env.MONGODB_URI || !process.env.GEMINI_API_KEY) {
      return json(res, 503, {
        error: "Cloud RAG is not configured yet.",
        detail: "This deployment needs MONGODB_URI and GEMINI_API_KEY environment variables before the online assistant can answer questions.",
      });
    }

    const result = await answerQuestion(question, history);
    return json(res, 200, result);
  } catch (error) {
    console.error(error);
    return json(res, 500, {
      error: "The online RAG assistant could not answer right now.",
      detail: error.message,
    });
  }
};
