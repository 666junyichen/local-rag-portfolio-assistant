from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.portfolio_rag import get_collections, load_settings  # noqa: E402


def collection_status(collection: Any, index_name: str) -> str:
    indexes = list(collection.list_search_indexes(name=index_name))
    status = indexes[0].get("status", "MISSING") if indexes else "MISSING"
    return f"{collection.count_documents({})}|{status}"


def main() -> None:
    try:
        settings = load_settings(ROOT / ".env")
        _, collection, _ = get_collections(settings)
        print(collection_status(collection, settings.vector_index_name))
    except Exception as error:
        print(f"Local knowledge index unavailable ({type(error).__name__}).", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
