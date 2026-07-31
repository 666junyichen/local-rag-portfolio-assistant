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


SUPPORTED_EXTENSIONS = {".json", ".md", ".txt", ".csv", ".docx", ".pdf"}


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
