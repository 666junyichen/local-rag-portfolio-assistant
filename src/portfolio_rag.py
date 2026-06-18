from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.operations import SearchIndexModel
from sentence_transformers import SentenceTransformer


@dataclass(frozen=True)
class Settings:
    mongodb_uri: str
    ollama_base_url: str
    ollama_model: str
    db_name: str = "portfolio_rag"
    collection_name: str = "portfolio_knowledge_base"
    chat_history_coll: str = "portfolio_chat_history"
    vector_index_name: str = "vector_index"
    embedding_model_id: str = "voyageai/voyage-4-nano"
    embedding_local_only: bool = False


def load_settings(env_path: str | Path = ".env") -> Settings:
    load_dotenv(env_path)
    return Settings(
        mongodb_uri=os.environ["MONGODB_URI"],
        ollama_base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_model=os.environ.get("OLLAMA_MODEL", "gemma:2b"),
        db_name=os.environ.get("DB_NAME", "portfolio_rag"),
        collection_name=os.environ.get("COLLECTION_NAME", "portfolio_knowledge_base"),
        chat_history_coll=os.environ.get("CHAT_HISTORY_COLL", "portfolio_chat_history"),
        vector_index_name=os.environ.get("VECTOR_INDEX_NAME", "vector_index"),
        embedding_model_id=os.environ.get("EMBEDDING_MODEL_ID", "voyageai/voyage-4-nano"),
        embedding_local_only=os.environ.get("EMBEDDING_LOCAL_ONLY", "false").lower() == "true",
    )


def get_collections(settings: Settings) -> tuple[MongoClient, Collection, Collection]:
    client = MongoClient(settings.mongodb_uri)
    client.admin.command("ping")
    db = client[settings.db_name]
    return client, db[settings.collection_name], db[settings.chat_history_coll]


def load_embedding_model(settings: Settings) -> SentenceTransformer:
    return SentenceTransformer(
        settings.embedding_model_id,
        trust_remote_code=True,
        local_files_only=settings.embedding_local_only,
    )


def chunk_documents(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n", " ", ""],
        chunk_size=800,
        chunk_overlap=80,
    )
    chunks: list[dict[str, Any]] = []
    for doc in docs:
        for chunk in splitter.split_text(doc["body"]):
            chunk_doc = {k: v for k, v in doc.items() if k != "body"}
            chunk_doc["body"] = chunk
            chunks.append(chunk_doc)
    return chunks


def embed_texts(model: SentenceTransformer, texts: list[str], input_type: str) -> list[list[float]]:
    if input_type == "query":
        vectors = model.encode_query(texts)
    else:
        vectors = model.encode_document(texts)
    return vectors.tolist()


def create_vector_index(collection: Collection, settings: Settings, dimensions: int) -> None:
    index_model = SearchIndexModel(
        definition={
            "fields": [
                {
                    "type": "vector",
                    "path": "embedding",
                    "numDimensions": dimensions,
                    "similarity": "cosine",
                }
            ]
        },
        name=settings.vector_index_name,
        type="vectorSearch",
    )

    existing = list(collection.list_search_indexes(name=settings.vector_index_name))
    if existing:
        collection.drop_search_index(settings.vector_index_name)
        time.sleep(5)

    collection.create_search_index(model=index_model)
    wait_for_index(collection, settings.vector_index_name)


def wait_for_index(collection: Collection, index_name: str, timeout: int = 180) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        indexes = list(collection.list_search_indexes(name=index_name))
        status = indexes[0].get("status", "PENDING") if indexes else "PENDING"
        if status == "READY":
            return
        time.sleep(5)
    raise TimeoutError(f"Index {index_name!r} did not reach READY status within {timeout} seconds.")


def vector_search(
    collection: Collection,
    model: SentenceTransformer,
    settings: Settings,
    query: str,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    query_embedding = embed_texts(model, [query], input_type="query")[0]
    pipeline = [
        {
            "$vectorSearch": {
                "index": settings.vector_index_name,
                "queryVector": query_embedding,
                "path": "embedding",
                "numCandidates": top_k * 10,
                "limit": top_k,
            }
        },
        {
            "$project": {
                "_id": 0,
                "embedding": 0,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]
    return list(collection.aggregate(pipeline))


def build_system_prompt(context: str) -> str:
    return (
        "You are Junyi Chen's portfolio assistant. "
        "Answer questions based only on the provided resume, project, internship, "
        "skill, and technical background context. "
        "The context may be in English, Chinese, or both. You may translate and summarize relevant context into the user's language. "
        "Answer in the same language as the user's question unless the user explicitly asks for another language. "
        "For Chinese questions, answer in natural Chinese and keep project names or technical terms in English when useful. "
        "If the answer is not supported by the context, say you do not know based on the available portfolio data.\n\n"
        f"Context:\n{context}"
    )


def contains_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def generate_answer(
    collection: Collection,
    model: SentenceTransformer,
    settings: Settings,
    query: str,
    top_k: int = 5,
) -> str:
    results = vector_search(collection, model, settings, query, top_k=top_k)
    context = "\n\n".join(doc["body"] for doc in results)
    client = OpenAI(base_url=f"{settings.ollama_base_url}/v1", api_key="ollama")
    user_content = query
    if contains_cjk(query):
        user_content = (
            "请务必用自然、清晰的中文回答下面的问题。"
            "可以根据英文上下文翻译和总结，但不要把回答切换成英文。"
            "请直接回答用户真正问的问题，不要改写成其他问题。\n\n"
            f"用户问题：{query}"
        )
    response = client.chat.completions.create(
        model=settings.ollama_model,
        messages=[
            {"role": "system", "content": build_system_prompt(context)},
            {"role": "user", "content": user_content},
        ],
        temperature=0.1,
    )
    return response.choices[0].message.content


def store_message(history: Collection, session_id: str, role: str, content: str) -> None:
    history.insert_one(
        {
            "session_id": session_id,
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc),
        }
    )


def get_history(history: Collection, session_id: str) -> list[dict[str, str]]:
    cursor = history.find(
        {"session_id": session_id},
        {"_id": 0, "role": 1, "content": 1},
    ).sort("timestamp", 1)
    return [{"role": item["role"], "content": item["content"]} for item in cursor]
