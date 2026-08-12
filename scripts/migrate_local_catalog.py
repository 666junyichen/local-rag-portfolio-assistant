from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ingestion import ensure_local_catalog  # noqa: E402


def main() -> None:
    catalog = ensure_local_catalog(ROOT / "data", import_legacy=True)
    print(f"Catalog path: {catalog.path}")
    print(f"Total documents: {catalog.count()}")
    print(f"Active documents: {catalog.count({'status': 'active'})}")
    print(f"Discovered documents: {catalog.count({'status': 'discovered'})}")
    print(f"Excluded documents: {catalog.count({'status': 'excluded'})}")


if __name__ == "__main__":
    main()
