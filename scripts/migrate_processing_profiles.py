from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.local_catalog import LocalCatalog  # noqa: E402


def main() -> None:
    load_dotenv()
    path = Path(os.getenv("LOCAL_CATALOG_PATH", ROOT / "data" / "local_catalog.sqlite3"))
    migrated = LocalCatalog(path).migrate_processing_profiles()
    print(f"Migrated processing profiles: {migrated}")


if __name__ == "__main__":
    main()
