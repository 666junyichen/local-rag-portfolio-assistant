from __future__ import annotations

import json
import sys
from pathlib import Path

from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.portfolio_rag import (  # noqa: E402
    chunk_documents,
    create_vector_index,
    embed_texts,
    get_collections,
    load_embedding_model,
    load_settings,
)


def main() -> None:
    settings = load_settings(ROOT / ".env")
    data_path = ROOT / "data" / "portfolio_docs.json"
    docs = json.loads(data_path.read_text(encoding="utf-8"))

    _, collection, history = get_collections(settings)
    model = load_embedding_model(settings)
    dimensions = model.encode_query(["hello"]).shape[1]

    chunks = chunk_documents(docs)
    texts = [chunk["body"] for chunk in chunks]
    embeddings = embed_texts(model, texts, input_type="document")
    for chunk, embedding in tqdm(list(zip(chunks, embeddings)), desc="Attaching embeddings"):
        chunk["embedding"] = embedding

    collection.delete_many({})
    result = collection.insert_many(chunks)
    history.create_index([("session_id", 1), ("timestamp", 1)])
    create_vector_index(collection, settings, dimensions)

    print(f"Loaded source documents: {len(docs)}")
    print(f"Inserted chunks: {len(result.inserted_ids)}")
    print(f"Vector index: {settings.vector_index_name}")
    print("Ingestion complete.")


if __name__ == "__main__":
    main()
