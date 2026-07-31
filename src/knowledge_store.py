from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from src.document_processing import normalize_document


def _read(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{path.name} must contain a JSON array")
    return [dict(item) for item in payload]


def _write(path: Path, documents: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(list(documents), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def publish_document(path: Path, raw: dict[str, Any]) -> dict[str, Any]:
    documents = [normalize_document(item, default_visibility="public") for item in _read(path)]
    document = normalize_document(raw, default_visibility="public")
    document["visibility"] = "public"
    document["metadata"]["visibility"] = "public"
    duplicate = next(
        (item for item in documents if item["content_hash"] == document["content_hash"]),
        None,
    )
    if duplicate:
        return {"created": False, "document": duplicate}
    documents.append(document)
    _write(path, documents)
    return {"created": True, "document": document}


def save_private_documents(path: Path, rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    existing = [normalize_document(item, default_visibility="private") for item in _read(path)]
    by_hash = {item["content_hash"]: item for item in existing}
    for raw in rows:
        document = normalize_document(raw, default_visibility="private")
        document["visibility"] = "private"
        document["metadata"]["visibility"] = "private"
        by_hash[document["content_hash"]] = document
    documents = list(by_hash.values())
    _write(path, documents)
    return documents


def remove_document(path: Path, doc_id: str, *, default_visibility: str) -> bool:
    documents = [normalize_document(item, default_visibility=default_visibility) for item in _read(path)]
    kept = [item for item in documents if item["doc_id"] != doc_id]
    if len(kept) == len(documents):
        return False
    _write(path, kept)
    return True
