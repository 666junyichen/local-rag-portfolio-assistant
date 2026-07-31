from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from src.document_processing import ChunkConfig, normalize_document, split_document


def _load_json_list(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{path.name} must contain a JSON array")
    return [dict(item) for item in payload]


def load_knowledge_documents(data_dir: Path, *, include_private: bool = True) -> list[dict[str, Any]]:
    public_path = data_dir / "portfolio_docs.json"
    documents = [normalize_document(item, default_visibility="public") for item in _load_json_list(public_path)]

    private_path = data_dir / "local_private_docs.json"
    if include_private and private_path.exists():
        documents.extend(
            normalize_document(item, default_visibility="private") for item in _load_json_list(private_path)
        )
    return documents


def build_chunk_records(
    documents: Iterable[dict[str, Any]],
    config: ChunkConfig | None = None,
) -> list[dict[str, Any]]:
    config = config or ChunkConfig()
    seen_hashes: set[str] = set()
    chunks: list[dict[str, Any]] = []
    for raw in documents:
        default_visibility = raw.get("visibility") or (raw.get("metadata") or {}).get("visibility") or "private"
        document = normalize_document(raw, default_visibility=default_visibility)
        if document["content_hash"] in seen_hashes:
            continue
        seen_hashes.add(document["content_hash"])
        chunks.extend(split_document(document, config))
    return chunks
