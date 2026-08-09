from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.local_catalog import LocalCatalog  # noqa: E402
from src.portfolio_rag import get_collections, load_settings  # noqa: E402
from src.space_migration import migrate_collection_spaces  # noqa: E402


def main() -> None:
    LocalCatalog(ROOT / "data" / "local_catalog.sqlite3")
    settings = load_settings(ROOT / ".env")
    _, collection, _ = get_collections(settings)
    result = migrate_collection_spaces(
        collection,
        vector_index_name=settings.vector_index_name,
        text_index_name=settings.text_index_name,
    )
    print(
        f"Knowledge spaces migrated: {result['migrated_chunks']} chunks; "
        f"updated indexes: {', '.join(result['updated_indexes']) or 'none'}."
    )


if __name__ == "__main__":
    main()

