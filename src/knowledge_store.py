from __future__ import annotations

import json
from datetime import datetime, timezone
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
    for index, item in enumerate(documents):
        if item["doc_id"] == document["doc_id"]:
            documents[index] = document
            _write(path, documents)
            return {"created": False, "document": document}
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


def archive_public_document(path: Path, archive_path: Path, doc_id: str) -> bool:
    documents = [normalize_document(item, default_visibility="public") for item in _read(path)]
    target = next((item for item in documents if item["doc_id"] == doc_id), None)
    if target is None:
        return False
    archived = _read(archive_path)
    archived.append({**target, "archived_at": datetime.now(timezone.utc).isoformat()})
    _write(archive_path, archived)
    _write(path, [item for item in documents if item["doc_id"] != doc_id])
    return True


def update_public_document(path: Path, doc_id: str, changes: dict[str, Any]) -> bool:
    documents = [normalize_document(item, default_visibility="public") for item in _read(path)]
    found = False
    updated_documents: list[dict[str, Any]] = []
    for document in documents:
        if document["doc_id"] != doc_id:
            updated_documents.append(document)
            continue
        found = True
        metadata = dict(document.get("metadata") or {})
        if "category" in changes:
            metadata["category"] = str(changes["category"]).strip()
        merged = {
            **document,
            **{key: changes[key] for key in ("title", "body", "url", "updated") if key in changes},
            "doc_id": doc_id,
            "visibility": "public",
            "metadata": {**metadata, "visibility": "public"},
        }
        normalized = normalize_document(merged, default_visibility="public")
        normalized["doc_id"] = doc_id
        updated_documents.append(normalized)
    if not found:
        return False
    _write(path, updated_documents)
    return True
