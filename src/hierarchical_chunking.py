from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.document_processing import (
    ChunkConfig,
    build_context_prefix,
    count_tokens,
    normalize_document,
    split_document,
)
from src.processing_profiles import ProcessingProfile


def _stable_id(*parts: object, length: int = 20) -> str:
    value = "\n".join(str(part) for part in parts)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


@dataclass(frozen=True)
class ChunkRecord:
    chunk_id: str
    doc_id: str
    parent_chunk_id: str | None
    semantic_group_id: str
    raw_body: str
    retrieval_text: str
    parent_body: str
    section_type: str
    section_path: str
    entity_title: str
    token_count: int
    character_count: int
    retrieval_priority: str
    visibility: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        values = asdict(self)
        values["body"] = self.raw_body
        return values


@dataclass(frozen=True)
class ChunkHierarchy:
    parents: tuple[ChunkRecord, ...]
    children: tuple[ChunkRecord, ...]
    processing_profile_hash: str


def _record_from_chunk(
    chunk: dict[str, Any],
    *,
    chunk_id: str,
    parent_chunk_id: str | None,
    parent_body: str,
) -> ChunkRecord:
    raw_body = str(chunk.get("raw_body") or chunk.get("body") or "").strip()
    return ChunkRecord(
        chunk_id=chunk_id,
        doc_id=str(chunk["doc_id"]),
        parent_chunk_id=parent_chunk_id,
        semantic_group_id=str(chunk.get("semantic_group_id") or chunk_id),
        raw_body=raw_body,
        retrieval_text=str(chunk.get("retrieval_text") or raw_body),
        parent_body=parent_body,
        section_type=str(chunk.get("section_type") or "document"),
        section_path=str(chunk.get("section_path") or ""),
        entity_title=str(chunk.get("entity_title") or chunk.get("title") or "Untitled"),
        token_count=count_tokens(raw_body),
        character_count=len(raw_body),
        retrieval_priority=str(chunk.get("retrieval_priority") or "primary"),
        visibility=str(chunk.get("visibility") or "private"),
        metadata=dict(chunk.get("metadata") or {}),
    )


def _config(strategy: str, size: int, overlap: int = 0) -> ChunkConfig:
    return ChunkConfig(strategy=strategy, chunk_size=size, chunk_overlap=overlap, unit="tokens")


def _parent_chunks(document: dict[str, Any], profile: ProcessingProfile) -> list[dict[str, Any]]:
    if profile.chunk_mode == "resume_semantic":
        return split_document(document, _config("resume_semantic", profile.max_tokens))
    if profile.chunk_mode == "parent_child":
        strategy = "paragraph" if profile.parent_mode == "paragraph" else "recursive"
        return split_document(document, _config(strategy, profile.parent_max_tokens))
    return split_document(
        document,
        _config("recursive", profile.max_tokens, profile.overlap_tokens),
    )


def _child_chunks(
    document: dict[str, Any],
    parent: ChunkRecord,
    profile: ProcessingProfile,
) -> list[ChunkRecord]:
    if profile.chunk_mode == "general":
        return [
            ChunkRecord(
                **{
                    **asdict(parent),
                    "chunk_id": f"child_{_stable_id(parent.chunk_id, parent.raw_body)}",
                    "parent_chunk_id": parent.chunk_id,
                }
            )
        ]

    child_document = {
        **document,
        "body": parent.raw_body,
        "title": parent.entity_title,
        "metadata": {
            **dict(document.get("metadata") or {}),
            "parent_chunk_id": parent.chunk_id,
        },
    }
    splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n", ". ", " ", ""],
        chunk_size=profile.child_max_tokens,
        chunk_overlap=profile.overlap_tokens,
        length_function=count_tokens,
    )
    parts = [part.strip() for part in splitter.split_text(parent.raw_body) if part.strip()]
    records: list[ChunkRecord] = []
    for index, body in enumerate(parts):
        child_id = f"child_{_stable_id(parent.chunk_id, index, body)}"
        context_prefix = build_context_prefix(
            child_document, parent.section_path, parent.entity_title
        )
        child = _record_from_chunk(
            {
                **child_document,
                "raw_body": body,
                "retrieval_text": f"{context_prefix}\n{body}",
                "section_type": parent.section_type,
                "section_path": parent.section_path,
                "entity_title": parent.entity_title,
                "semantic_group_id": parent.semantic_group_id,
                "retrieval_priority": parent.retrieval_priority,
            },
            chunk_id=child_id,
            parent_chunk_id=parent.chunk_id,
            parent_body=parent.raw_body,
        )
        records.append(child)
    return records


def build_chunk_hierarchy(
    document: dict[str, Any], profile: ProcessingProfile
) -> ChunkHierarchy:
    normalized = normalize_document(
        document, default_visibility=str(document.get("visibility") or "private")
    )
    parent_records: list[ChunkRecord] = []
    child_records: list[ChunkRecord] = []
    for index, chunk in enumerate(_parent_chunks(normalized, profile)):
        parent_id = f"parent_{_stable_id(normalized['doc_id'], index, chunk.get('body', ''))}"
        parent = _record_from_chunk(
            chunk,
            chunk_id=parent_id,
            parent_chunk_id=None,
            parent_body=str(chunk.get("body") or "").strip(),
        )
        parent_records.append(parent)
        child_records.extend(_child_chunks(normalized, parent, profile))
    return ChunkHierarchy(
        parents=tuple(parent_records),
        children=tuple(child_records),
        processing_profile_hash=profile.digest(),
    )
