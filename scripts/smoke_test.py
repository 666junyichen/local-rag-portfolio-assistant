from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.portfolio_rag import generate_answer, get_collections, load_embedding_model, load_settings, vector_search  # noqa: E402


def main() -> None:
    settings = load_settings(ROOT / ".env")
    _, collection, _ = get_collections(settings)
    model = load_embedding_model(settings)

    query = "What are Junyi Chen's strongest projects for AI and data roles?"
    results = vector_search(collection, model, settings, query, top_k=3)
    print(f"retrieved={len(results)}")
    if results:
        print(f"top_title={results[0].get('title')}")

    answer = generate_answer(collection, model, settings, query, top_k=3)
    print("answer_preview=" + answer[:500].replace("\n", " "))
    print("smoke_test=OK")


if __name__ == "__main__":
    main()
