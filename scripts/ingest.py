from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.portfolio_rag import (  # noqa: E402
    create_vector_index,
    create_text_index,
    embed_texts,
    get_collections,
    load_embedding_model,
    load_settings,
)
from src.ingestion import build_chunk_records, load_knowledge_documents  # noqa: E402


def main() -> None:
    def report(message: str) -> None:
        print(f"[ingest] {message}", flush=True)

    report("Loading local configuration...")
    settings = load_settings(ROOT / ".env")
    report("Reading public and private source documents...")
    docs = load_knowledge_documents(ROOT / "data", include_private=True)
    report(f"Loaded source documents: {len(docs)}")

    report("Connecting to MongoDB Local Atlas...")
    _, collection, history = get_collections(settings)
    report(f"Loading embedding model: {settings.embedding_model_id}")
    model = load_embedding_model(settings)
    dimensions = model.encode_query(["hello"]).shape[1]
    report(f"Embedding dimensions: {dimensions}")

    chunks = build_chunk_records(docs)
    report(f"Prepared chunks: {len(chunks)}")
    texts = [chunk.get("retrieval_text") or chunk["body"] for chunk in chunks]
    report("Generating document embeddings. This is the longest step on CPU...")
    embeddings = embed_texts(model, texts, input_type="document")
    for chunk, embedding in zip(chunks, embeddings):
        chunk["embedding"] = embedding
    report("Embeddings generated.")

    report("Replacing local knowledge collection...")
    collection.delete_many({})
    if chunks:
        result = collection.insert_many(chunks)
        inserted_count = len(result.inserted_ids)
    else:
        inserted_count = 0
    report(f"Inserted chunks: {inserted_count}")
    history.create_index([("session_id", 1), ("timestamp", 1)])
    create_vector_index(collection, settings, dimensions, progress=report)
    create_text_index(collection, settings, progress=report)

    report(f"Vector index: {settings.vector_index_name}")
    report(f"Text index: {settings.text_index_name}")
    report("Ingestion complete.")


if __name__ == "__main__":
    main()
