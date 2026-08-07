from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from src.document_processing import (
    ChunkConfig,
    normalize_document,
    recommend_chunk_config,
    split_document,
)
from src.local_catalog import LocalCatalog, stable_document_id
from src.hierarchical_chunking import build_chunk_hierarchy
from src.processing_profiles import (
    ProcessingProfile,
    profile_from_legacy,
    recommend_processing_profile,
)


def _load_json_list(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{path.name} must contain a JSON array")
    return [dict(item) for item in payload]


def _project_document_priority(document: dict[str, Any]) -> tuple[int, str]:
    relative_path = str(document.get("relative_path") or document.get("path") or "")
    normalized = relative_path.replace("/", "\\")
    name = normalized.rsplit("\\", 1)[-1].lower()
    if name.startswith("readme"):
        rank = 0
    elif "\\docs\\" in f"\\{normalized.lower()}\\" and name.endswith(".md"):
        rank = 1
    elif name in {"package.json", "pyproject.toml", "requirements.txt", "architecture.md"}:
        rank = 2
    elif name.endswith((".md", ".py", ".ts", ".tsx", ".js")):
        rank = 3
    else:
        rank = 4
    return rank, normalized.lower()


def _resume_document_priority(document: dict[str, Any]) -> tuple[int, str]:
    relative_path = str(document.get("relative_path") or document.get("path") or "")
    normalized = relative_path.replace("/", "\\").lower()
    name = normalized.rsplit("\\", 1)[-1]
    if "master" in normalized and name.endswith(".docx"):
        rank = 0
    elif "master" in normalized and name.endswith(".md"):
        rank = 1
    elif name.endswith(".docx"):
        rank = 2
    elif name.endswith(".md"):
        rank = 3
    else:
        rank = 4
    return rank, normalized


def select_private_documents(
    rows: Iterable[dict[str, Any]],
    *,
    per_project_limit: int = 2,
    resume_limit: int = 12,
) -> list[dict[str, Any]]:
    """Keep private resumes/uploads and a useful, bounded sample per project."""
    always_include: list[dict[str, Any]] = []
    resumes: list[dict[str, Any]] = []
    projects: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        document = dict(row)
        source = document.get("source")
        if source == "resume_root":
            relative_path = str(document.get("relative_path") or document.get("path") or "").lower()
            noisy_parts = ("phpstudy_pro", "\\extensions\\", "\\errorpages\\", "\\www\\error\\")
            if not any(part in relative_path for part in noisy_parts):
                resumes.append(document)
            continue
        if source != "project_activity_root" or per_project_limit <= 0:
            always_include.append(document)
            continue
        relative_path = str(document.get("relative_path") or document.get("path") or "unknown")
        project_name = relative_path.replace("/", "\\").split("\\", 1)[0]
        projects.setdefault(project_name, []).append(document)

    selected = list(always_include)
    selected.extend(sorted(resumes, key=_resume_document_priority)[:resume_limit])
    for project_name in sorted(projects):
        selected.extend(sorted(projects[project_name], key=_project_document_priority)[:per_project_limit])
    return selected


def ensure_local_catalog(
    data_dir: Path,
    *,
    per_project_limit: int = 2,
    resume_limit: int = 12,
) -> LocalCatalog:
    catalog = LocalCatalog(data_dir / "local_catalog.sqlite3")
    private_path = data_dir / "local_private_docs.json"
    if catalog.count() == 0 and private_path.exists():
        rows = _load_json_list(private_path)
        selected = select_private_documents(
            rows,
            per_project_limit=per_project_limit,
            resume_limit=resume_limit,
        )
        active_ids = {stable_document_id(row) for row in selected}
        catalog.upsert_documents(rows, active_ids=active_ids)
    return catalog


def load_knowledge_documents(data_dir: Path, *, include_private: bool = True) -> list[dict[str, Any]]:
    public_path = data_dir / "portfolio_docs.json"
    documents = [normalize_document(item, default_visibility="public") for item in _load_json_list(public_path)]

    if include_private:
        catalog_path = data_dir / "local_catalog.sqlite3"
        if catalog_path.exists():
            documents.extend(LocalCatalog(catalog_path).active_documents())
        else:
            private_path = data_dir / "local_private_docs.json"
            if private_path.exists():
                private_rows = select_private_documents(_load_json_list(private_path))
                documents.extend(
                    normalize_document(item, default_visibility="private") for item in private_rows
                )
    return documents


def build_chunk_records(
    documents: Iterable[dict[str, Any]],
    config: ChunkConfig | None = None,
    *,
    profile: ProcessingProfile | None = None,
) -> list[dict[str, Any]]:
    legacy_default = config or ChunkConfig()
    seen_hashes: set[str] = set()
    chunks: list[dict[str, Any]] = []
    for raw in documents:
        default_visibility = raw.get("visibility") or (raw.get("metadata") or {}).get("visibility") or "private"
        document = normalize_document(raw, default_visibility=default_visibility)
        if document["content_hash"] in seen_hashes:
            continue
        seen_hashes.add(document["content_hash"])
        metadata = document.get("metadata") or {}
        configured_profile = metadata.get("processing_profile")
        configured = metadata.get("chunking") or {}
        if profile is not None:
            document_profile = profile
        elif configured_profile:
            document_profile = ProcessingProfile.from_dict(configured_profile)
        elif configured or config is not None:
            document_profile = profile_from_legacy(
                title=document["title"],
                file_type=str(metadata.get("file_type") or metadata.get("source") or ""),
                strategy=str(configured.get("strategy") or legacy_default.strategy),
                chunk_size=int(configured.get("chunk_size") or legacy_default.chunk_size),
                overlap=int(
                    configured.get("chunk_overlap")
                    if configured.get("chunk_overlap") is not None
                    else legacy_default.chunk_overlap
                ),
                unit=str(configured.get("unit") or legacy_default.unit),
            )
        else:
            document_profile = recommend_processing_profile(document)
        hierarchy = build_chunk_hierarchy(document, document_profile)
        for child in hierarchy.children:
            chunks.append(
                {
                    **child.to_dict(),
                    "content_hash": document["content_hash"],
                    "title": document["title"],
                    "source": document.get("source"),
                    "relative_path": document.get("relative_path"),
                    "chunk_unit": "tokens",
                    "processing_profile_hash": hierarchy.processing_profile_hash,
                    "processing_profile": document_profile.to_dict(),
                }
            )
    return chunks
