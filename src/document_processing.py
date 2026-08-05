from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from langchain_text_splitters import RecursiveCharacterTextSplitter
import numpy as np


SUPPORTED_EXTENSIONS = {".json", ".md", ".txt", ".csv", ".docx", ".pdf"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


@dataclass(frozen=True)
class ChunkConfig:
    strategy: str = "recursive"
    chunk_size: int = 800
    chunk_overlap: int = 80

    def __post_init__(self) -> None:
        if self.strategy not in {"recursive", "markdown", "paragraph"}:
            raise ValueError("strategy must be recursive, markdown, or paragraph")
        if not 200 <= self.chunk_size <= 2000:
            raise ValueError("chunk_size must be between 200 and 2000")
        if self.chunk_overlap < 0:
            raise ValueError("chunk_overlap cannot be negative")
        if self.chunk_overlap > self.chunk_size * 0.25:
            raise ValueError("chunk_overlap cannot exceed 25% of chunk_size")


def clean_text(value: str) -> str:
    value = html.unescape(value.replace("\x00", " "))
    value = re.sub(r"<script[\s\S]*?</script>", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"<style[\s\S]*?</style>", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"[\t\f\v ]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def recommend_chunk_config(document: dict[str, Any]) -> ChunkConfig:
    metadata = document.get("metadata") or {}
    source = str(metadata.get("source") or document.get("path") or document.get("relative_path") or "")
    file_type = str(metadata.get("file_type") or Path(source).suffix.lstrip(".")).lower()
    title = str(document.get("title") or "").lower()
    body_length = len(str(document.get("body") or ""))
    if file_type == "docx" or "resume" in title or "简历" in title:
        return ChunkConfig("recursive", 600, 60)
    if file_type in {"md", "markdown"} or title.startswith("readme"):
        return ChunkConfig("markdown", 800, 80)
    if file_type == "txt":
        return ChunkConfig("paragraph", 700, 70)
    if file_type == "pdf":
        return ChunkConfig("recursive", 800, 100)
    if file_type == "csv":
        return ChunkConfig("recursive", 800, 0)
    if file_type == "json" and body_length <= 800:
        return ChunkConfig("recursive", 800, 0)
    if file_type in {"py", "js", "ts", "tsx", "html", "htm"}:
        return ChunkConfig("recursive", 900, 80)
    return ChunkConfig()


def chunk_metrics(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    lengths = [len(str(chunk.get("body") or "")) for chunk in chunks]
    if not lengths:
        return {
            "count": 0,
            "average_length": 0,
            "min_length": 0,
            "max_length": 0,
            "too_short_ratio": 0.0,
            "warnings": ["No chunks were generated."],
        }
    too_short_ratio = sum(length < 100 for length in lengths) / len(lengths)
    warnings = []
    if too_short_ratio >= 0.25:
        warnings.append("Many chunks are shorter than 100 characters; increase chunk size.")
    if max(lengths) > 1600:
        warnings.append("Some chunks are very long; retrieval may include unrelated context.")
    return {
        "count": len(lengths),
        "average_length": round(sum(lengths) / len(lengths)),
        "min_length": min(lengths),
        "max_length": max(lengths),
        "too_short_ratio": round(too_short_ratio, 3),
        "warnings": warnings,
    }


def detect_pii(text: str) -> list[dict[str, str]]:
    patterns = {
        "email": r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        "phone": r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)",
    }
    findings = []
    for finding_type, pattern in patterns.items():
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            findings.append({"type": finding_type, "value": match.group(0)})
    return findings


def rank_preview_chunks(
    chunks: list[dict[str, Any]],
    query: str,
    model: Any,
    *,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    if not chunks or not query.strip():
        return []
    query_vector = np.asarray(model.encode_query([query.strip()]), dtype=float)[0]
    document_vectors = np.asarray(
        model.encode_document([str(chunk.get("body") or "") for chunk in chunks]),
        dtype=float,
    )
    query_norm = np.linalg.norm(query_vector) or 1.0
    document_norms = np.linalg.norm(document_vectors, axis=1)
    document_norms[document_norms == 0] = 1.0
    scores = (document_vectors @ query_vector) / (document_norms * query_norm)
    ranked = sorted(
        ({**chunk, "score": round(float(score), 4)} for chunk, score in zip(chunks, scores)),
        key=lambda item: item["score"],
        reverse=True,
    )
    return ranked[: max(1, min(top_k, len(ranked)))]


def _digest(value: str, length: int = 20) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def normalize_document(
    raw: dict[str, Any],
    *,
    default_visibility: str = "private",
) -> dict[str, Any]:
    title = clean_text(str(raw.get("title") or "Untitled document"))
    body = clean_text(str(raw.get("body") or ""))
    if not body:
        raise ValueError("document body cannot be empty")

    metadata = dict(raw.get("metadata") or {})
    visibility = str(raw.get("visibility") or metadata.get("visibility") or default_visibility)
    if visibility not in {"public", "private"}:
        raise ValueError("visibility must be public or private")
    metadata["visibility"] = visibility

    content_hash = _digest(body, 64)
    identity_source = f"{title}\n{content_hash}"
    doc_id = str(raw.get("doc_id") or f"doc_{_digest(identity_source)}")
    return {
        **{key: value for key, value in raw.items() if key not in {"metadata", "body", "title"}},
        "doc_id": doc_id,
        "title": title,
        "body": body,
        "visibility": visibility,
        "content_hash": content_hash,
        "metadata": metadata,
    }


def _recursive_parts(text: str, config: ChunkConfig) -> list[str]:
    separators = ["\n#{1,6} ", "\n\n", "\n", "。", ". ", " ", ""]
    splitter = RecursiveCharacterTextSplitter(
        separators=separators,
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
        is_separator_regex=True,
    )
    return splitter.split_text(text)


def _paragraph_parts(text: str, config: ChunkConfig) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    grouped: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip()
        if current and len(candidate) > config.chunk_size:
            grouped.extend(_recursive_parts(current, config))
            current = paragraph
        else:
            current = candidate
    if current:
        grouped.extend(_recursive_parts(current, config))
    return grouped


def _markdown_parts(text: str, config: ChunkConfig) -> list[str]:
    sections = re.split(r"(?=^#{1,6}\s+)", text, flags=re.MULTILINE)
    parts: list[str] = []
    for section in sections:
        if section.strip():
            parts.extend(_recursive_parts(section.strip(), config))
    return parts


def split_document(document: dict[str, Any], config: ChunkConfig | None = None) -> list[dict[str, Any]]:
    config = config or ChunkConfig()
    normalized = normalize_document(document, default_visibility=document.get("visibility", "private"))
    if config.strategy == "markdown":
        bodies = _markdown_parts(normalized["body"], config)
    elif config.strategy == "paragraph":
        bodies = _paragraph_parts(normalized["body"], config)
    else:
        bodies = _recursive_parts(normalized["body"], config)

    chunks: list[dict[str, Any]] = []
    for index, body in enumerate(filter(None, (part.strip() for part in bodies))):
        chunk_id = f"{normalized['doc_id']}_chunk_{index}_{_digest(body, 10)}"
        chunks.append({
            **{key: value for key, value in normalized.items() if key != "body"},
            "chunk_id": chunk_id,
            "chunk_index": index,
            "body": body,
        })
    return chunks


def _read_docx(path: Path) -> str:
    namespaces = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))
    paragraphs = []
    for paragraph in root.findall(".//w:p", namespaces):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", namespaces)).strip()
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)


def _read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise RuntimeError("PDF support requires pypdf") from error
    return "\n\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)


def _text_document(path: Path, body: str) -> dict[str, Any]:
    return normalize_document(
        {
            "title": path.stem,
            "body": body,
            "metadata": {"source": path.name, "file_type": path.suffix.lower().lstrip(".")},
        }
    )


def parse_uploaded_file(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"unsupported file type: {suffix}")

    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        rows = payload if isinstance(payload, list) else [payload]
        return [normalize_document(dict(row)) for row in rows]
    if suffix == ".csv":
        text = path.read_text(encoding="utf-8-sig")
        rows = list(csv.DictReader(io.StringIO(text)))
        return [
            normalize_document(
                {
                    "title": row.get("title") or f"{path.stem} row {index + 1}",
                    "body": row.get("body") or " | ".join(f"{key}: {value}" for key, value in row.items()),
                    "metadata": {"source": path.name, "file_type": "csv"},
                }
            )
            for index, row in enumerate(rows)
        ]
    if suffix == ".docx":
        return [_text_document(path, _read_docx(path))]
    if suffix == ".pdf":
        return [_text_document(path, _read_pdf(path))]
    return [_text_document(path, path.read_text(encoding="utf-8-sig"))]


def persist_and_parse_upload(name: str, data: bytes, uploads_dir: Path) -> list[dict[str, Any]]:
    """Persist an upload locally and return a stable parsed representation."""
    uploads_dir.mkdir(parents=True, exist_ok=True)
    target = uploads_dir / Path(name).name
    if not target.exists() or target.read_bytes() != data:
        target.write_bytes(data)
    return parse_uploaded_file(target)
