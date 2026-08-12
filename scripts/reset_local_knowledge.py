from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.local_catalog import LocalCatalog  # noqa: E402
from src.local_reset import RESET_CONFIRMATION, perform_local_reset  # noqa: E402
from src.portfolio_rag import get_collections, load_settings  # noqa: E402


def run_reset(*, root: Path, confirmation: str) -> dict[str, Any]:
    root = Path(root)
    settings = load_settings(root / ".env")
    client, chunks, history = get_collections(settings)
    try:
        catalog = LocalCatalog(root / "data" / "local_catalog.sqlite3")
        return perform_local_reset(
            root=root,
            catalog=catalog,
            chunks=chunks,
            history=history,
            confirmation=confirmation,
        )
    finally:
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Back up and clear the local Portfolio knowledge base.",
    )
    parser.add_argument(
        "--confirm",
        required=True,
        help=f'Exact confirmation text: "{RESET_CONFIRMATION}"',
    )
    args = parser.parse_args()
    result = run_reset(root=ROOT, confirmation=args.confirm)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
