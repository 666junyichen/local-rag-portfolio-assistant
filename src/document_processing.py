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

from src.processing_profiles import PreprocessingProfile


SUPPORTED_EXTENSIONS = {".json", ".md", ".txt", ".csv", ".docx", ".pdf"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

SCRIPT_PATTERN = re.compile(r"<script[\s\S]*?</script>", re.IGNORECASE)
STYLE_PATTERN = re.compile(r"<style[\s\S]*?</style>", re.IGNORECASE)
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
HORIZONTAL_WHITESPACE_PATTERN = re.compile(r"[\t\f\v ]+")
NON_LF_LINE_BREAK_PATTERN = re.compile(r"\r\n?")
LINE_BREAK_PADDING_PATTERN = re.compile(r" *\n *")
EXCESS_LINE_BREAKS_PATTERN = re.compile(r"\n{3,}")
EMAIL_PATTERN = re.compile(
    r"""
    (?<![\w.+-])
    [A-Z0-9_%+-]+(?:\.[A-Z0-9_%+-]+)*
    @
    [A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?
    (?:\.[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?)*
    \.[A-Z]{2,63}
    (?![\w-]|\.[A-Z0-9])
    """,
    re.IGNORECASE | re.VERBOSE,
)
URL_PATTERN = re.compile(
    r"""
    (?<![@\w])
    (?:
        https?://(?:localhost|[A-Z0-9](?:[A-Z0-9.-]*[A-Z0-9])?)(?::\d{1,5})?
        |
        (?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+
        (?:com|org|net|edu|gov|io|dev|app|ai|co|me|info|biz|au|cn|uk)
    )
    (?![\w-])
    (?:/[A-Z0-9._~%!$&'()*+,;=:@/-]*)?
    (?:\?[A-Z0-9._~%!$&'()*+,;=:@/?-]*)?
    (?:\#[A-Z0-9._~%!$&'()*+,;=:@/?-]*)?
    """,
    re.IGNORECASE | re.VERBOSE,
)
TRAILING_URL_DELIMITERS = ".,;:!?)]}'\"\u2019\u201d"

RESUME_SECTION_HEADINGS = {
    "个人简历": ("profile", "基本信息"),
    "基本信息": ("profile", "基本信息"),
    "education": ("education", "Education"),
    "教育背景": ("education", "教育背景"),
    "个人简介": ("summary", "个人简介"),
    "profile": ("summary", "Profile"),
    "实习经历": ("internship", "实习经历"),
    "工作经历": ("internship", "工作经历"),
    "experience": ("internship", "Experience"),
    "项目经验": ("project", "项目经验"),
    "projects": ("project", "Projects"),
    "获奖与校园经历": ("award", "获奖与校园经历"),
    "获奖经历": ("award", "获奖经历"),
    "awards": ("award", "Awards"),
    "专业技能": ("skill", "专业技能"),
    "skills": ("skill", "Skills"),
}
RESUME_SKILL_HEADINGS = {
    "编程与开发",
    "ai与数据能力",
    "ai 与数据能力",
    "工具与协作",
    "programming and development",
    "ai and data",
    "tools and collaboration",
}


@dataclass(frozen=True)
class ChunkConfig:
    strategy: str = "recursive"
    chunk_size: int = 800
    chunk_overlap: int = 80
    unit: str = "characters"

    def __post_init__(self) -> None:
        if self.strategy not in {"recursive", "markdown", "paragraph", "resume_semantic"}:
            raise ValueError("strategy must be recursive, markdown, paragraph, or resume_semantic")
        if not 200 <= self.chunk_size <= 2000:
            raise ValueError("chunk_size must be between 200 and 2000")
        if self.chunk_overlap < 0:
            raise ValueError("chunk_overlap cannot be negative")
        if self.chunk_overlap > self.chunk_size * 0.25:
            raise ValueError("chunk_overlap cannot exceed 25% of chunk_size")
        if self.unit not in {"characters", "tokens"}:
            raise ValueError("unit must be characters or tokens")


def count_tokens(value: str) -> int:
    """Fast multilingual token estimate used for deterministic chunk budgets."""
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9.+#:_/-]*|[\u3400-\u9fff]|[^\s]", value))


def _measure(value: str, config: ChunkConfig) -> int:
    return count_tokens(value) if config.unit == "tokens" else len(value)


def _sanitize_markup(value: str) -> str:
    value = html.unescape(value.replace("\x00", " "))
    value = SCRIPT_PATTERN.sub(" ", value)
    value = STYLE_PATTERN.sub(" ", value)
    return HTML_TAG_PATTERN.sub(" ", value)


def _normalize_whitespace(value: str) -> str:
    value = NON_LF_LINE_BREAK_PATTERN.sub("\n", value)
    value = HORIZONTAL_WHITESPACE_PATTERN.sub(" ", value)
    value = LINE_BREAK_PADDING_PATTERN.sub("\n", value)
    value = EXCESS_LINE_BREAKS_PATTERN.sub("\n\n", value)
    return value.strip()


def _remove_url(match: re.Match[str]) -> str:
    matched = match.group(0)
    trailing = matched[len(matched.rstrip(TRAILING_URL_DELIMITERS)):]
    return trailing


def clean_text(value: str, profile: PreprocessingProfile | None = None) -> str:
    profile = profile or PreprocessingProfile()
    value = _sanitize_markup(value)
    if profile.remove_emails:
        value = EMAIL_PATTERN.sub("", value)
    if profile.remove_urls:
        value = URL_PATTERN.sub(_remove_url, value)
    if profile.normalize_whitespace:
        value = _normalize_whitespace(value)
    return value


def recommend_chunk_config(document: dict[str, Any]) -> ChunkConfig:
    metadata = document.get("metadata") or {}
    source = str(metadata.get("source") or document.get("path") or document.get("relative_path") or "")
    file_type = str(metadata.get("file_type") or Path(source).suffix.lstrip(".")).lower()
    title = str(document.get("title") or "").lower()
    body_length = len(str(document.get("body") or ""))
    if file_type == "docx" or "resume" in title or "简历" in title:
        return ChunkConfig("resume_semantic", 320, 0, unit="tokens")
    if file_type in {"md", "markdown"} or title.startswith("readme"):
        return ChunkConfig("markdown", 800, 80, unit="tokens")
    if file_type == "txt":
        return ChunkConfig("paragraph", 700, 70, unit="tokens")
    if file_type == "pdf":
        return ChunkConfig("recursive", 800, 100, unit="tokens")
    if file_type == "csv":
        return ChunkConfig("recursive", 800, 0, unit="tokens")
    if file_type == "json" and body_length <= 800:
        return ChunkConfig("recursive", 800, 0, unit="tokens")
    if file_type in {"py", "js", "ts", "tsx", "html", "htm"}:
        return ChunkConfig("recursive", 900, 80, unit="tokens")
    return ChunkConfig(unit="tokens")


def chunk_metrics(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    lengths = [len(str(chunk.get("body") or "")) for chunk in chunks]
    token_lengths = [count_tokens(str(chunk.get("body") or "")) for chunk in chunks]
    if not lengths:
        return {
            "count": 0,
            "average_length": 0,
            "min_length": 0,
            "max_length": 0,
            "too_short_ratio": 0.0,
            "average_tokens": 0,
            "min_tokens": 0,
            "max_tokens": 0,
            "cross_topic_count": 0,
            "warnings": ["No chunks were generated."],
        }
    too_short_ratio = sum(length < 100 for length in lengths) / len(lengths)
    warnings = []
    is_semantic = any(str(chunk.get("section_type") or "document") != "document" for chunk in chunks)
    if too_short_ratio >= 0.25 and not is_semantic:
        warnings.append("Many chunks are shorter than 100 characters; increase chunk size.")
    if max(lengths) > 1600:
        warnings.append("Some chunks are very long; retrieval may include unrelated context.")
    cross_topic_count = sum(len(_section_types_in_text(str(chunk.get("body") or ""))) > 1 for chunk in chunks)
    if cross_topic_count:
        warnings.append(f"{cross_topic_count} chunks cross top-level resume sections; use resume semantic chunking.")
    return {
        "count": len(lengths),
        "average_length": round(sum(lengths) / len(lengths)),
        "min_length": min(lengths),
        "max_length": max(lengths),
        "too_short_ratio": round(too_short_ratio, 3),
        "average_tokens": round(sum(token_lengths) / len(token_lengths)),
        "min_tokens": min(token_lengths),
        "max_tokens": max(token_lengths),
        "cross_topic_count": cross_topic_count,
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
    preview_chunks = [
        {
            **chunk,
            "chunk_id": chunk.get("chunk_id") or f"preview_{index}",
            "visibility": chunk.get("visibility") or "private",
        }
        for index, chunk in enumerate(chunks)
    ]
    query_vector = np.asarray(model.encode_query([query.strip()]), dtype=float)[0]
    document_vectors = np.asarray(
        model.encode_document(
            [str(chunk.get("retrieval_text") or chunk.get("body") or "") for chunk in preview_chunks]
        ),
        dtype=float,
    )
    query_norm = np.linalg.norm(query_vector) or 1.0
    document_norms = np.linalg.norm(document_vectors, axis=1)
    document_norms[document_norms == 0] = 1.0
    scores = (document_vectors @ query_vector) / (document_norms * query_norm)
    vector_rows = sorted(
        ({**chunk, "score": round(float(score), 4)} for chunk, score in zip(preview_chunks, scores)),
        key=lambda item: item["score"],
        reverse=True,
    )
    from src.retrieval import (
        RetrievalSettings,
        apply_section_intent_rerank,
        bm25_rank,
        reciprocal_rank_fusion,
        select_results,
    )

    sparse_rows = bm25_rank(
        preview_chunks,
        query,
        top_k=min(max(top_k * 4, 20), len(preview_chunks)),
    )
    fused = reciprocal_rank_fusion(
        vector_rows[: min(max(top_k * 4, 20), len(vector_rows))],
        sparse_rows,
        vector_weight=1.0,
        sparse_weight=1.2,
    )
    max_bm25 = max((float(row.get("bm25_score", 0)) for row in fused), default=0.0)
    for row in fused:
        if row.get("score") is None:
            row["score"] = float(row.get("bm25_score", 0)) / max_bm25 if max_bm25 else 0.0
    fused = apply_section_intent_rerank(fused, query)
    return select_results(fused, RetrievalSettings(top_k=min(max(top_k, 1), 10), scope="all"))


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


def replace_document_body(document: dict[str, Any], body: str) -> dict[str, Any]:
    """Return an edited document while keeping its stable source identity."""
    return normalize_document(
        {
            **document,
            "doc_id": document.get("doc_id"),
            "body": body,
        },
        default_visibility=str(document.get("visibility") or "private"),
    )


def _heading_key(value: str) -> str:
    return re.sub(r"[\s:*#：]+", "", value).strip().lower()


def _section_heading(value: str) -> tuple[str, str] | None:
    key = _heading_key(value)
    for heading, section in RESUME_SECTION_HEADINGS.items():
        if key == _heading_key(heading):
            return section
    return None


def _section_types_in_text(value: str) -> set[str]:
    return {
        section[0]
        for paragraph in re.split(r"\n+", value)
        if (section := _section_heading(paragraph.strip())) is not None
    }


def _looks_like_entity_start(
    paragraph: str,
    next_paragraph: str,
    section_type: str,
) -> bool:
    lowered = paragraph.lower()
    next_lowered = next_paragraph.lower()
    has_date = bool(re.search(r"(?:19|20)\d{2}(?:[./-]\d{1,2})?", paragraph))
    if section_type == "education":
        return has_date and any(term in lowered for term in ("大学", "university", "college"))
    if section_type == "internship":
        return has_date and (
            any(term in lowered for term in ("公司", "实习", "顾问", "intern", "consultant"))
            or "｜" in paragraph
            or "|" in paragraph
        )
    if section_type == "project":
        return (
            next_lowered.startswith(("技术栈", "tech stack"))
            or "github / demo" in lowered
            or "github/demo" in lowered
            or (has_date and ("｜" in paragraph or "|" in paragraph) and not paragraph.startswith("-"))
        )
    if section_type == "award":
        return has_date and not paragraph.startswith("-")
    return False


def _skill_entity_start(paragraph: str) -> bool:
    key = _heading_key(paragraph)
    if key in {_heading_key(value) for value in RESUME_SKILL_HEADINGS}:
        return True
    return bool(re.match(r"^[^：:\n]{2,24}[：:]", paragraph)) and not paragraph.startswith("-")


def _unit_group_id(document_id: str, section_type: str, entity_title: str) -> str:
    basis = f"{document_id}\n{section_type}\n{_heading_key(entity_title)}"
    return f"group_{_digest(basis, 20)}"


def _resume_semantic_units(document: dict[str, Any]) -> list[dict[str, Any]]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", document["body"]) if part.strip()]
    units: list[dict[str, Any]] = []
    section_type = "profile"
    section_label = "基本信息"
    current: list[str] = []
    current_title = "基本信息"
    current_priority = "primary"
    summary_index = 0
    has_structured_skill_group = False
    in_secondary_skill_tail = False

    def flush() -> None:
        nonlocal current
        if not current:
            return
        title = current_title or section_label
        priority = current_priority
        group_title = title
        if section_type == "summary":
            priority = "primary" if summary_index == 1 else "secondary"
            group_title = section_label
        units.append(
            {
                "paragraphs": current,
                "section_type": section_type,
                "section_label": section_label,
                "entity_title": title,
                "semantic_group_id": _unit_group_id(document["doc_id"], section_type, group_title),
                "retrieval_priority": priority,
            }
        )
        current = []

    for index, paragraph in enumerate(paragraphs):
        next_paragraph = paragraphs[index + 1] if index + 1 < len(paragraphs) else ""
        heading = _section_heading(paragraph)
        if heading:
            flush()
            section_type, section_label = heading
            current_title = section_label
            current_priority = "primary"
            in_secondary_skill_tail = False
            continue
        if section_type == "summary":
            flush()
            summary_index += 1
            current_title = f"{section_label} {summary_index}"
            current = [paragraph]
            flush()
            continue
        starts_entity = _looks_like_entity_start(paragraph, next_paragraph, section_type)
        is_structured_skill_group = False
        if section_type == "skill":
            is_structured_skill_group = _heading_key(paragraph) in {
                _heading_key(value) for value in RESUME_SKILL_HEADINGS
            }
            if is_structured_skill_group:
                starts_entity = True
            elif has_structured_skill_group:
                starts_entity = not in_secondary_skill_tail
            else:
                starts_entity = _skill_entity_start(paragraph)
        if starts_entity:
            flush()
            current_title = paragraph
            if section_type == "skill":
                if is_structured_skill_group:
                    current_priority = "primary"
                    has_structured_skill_group = True
                    in_secondary_skill_tail = False
                elif has_structured_skill_group:
                    current_title = "Additional skill variants"
                    current_priority = "secondary"
                    in_secondary_skill_tail = True
                else:
                    current_priority = "primary"
            else:
                current_priority = "primary"
            current = [paragraph]
        else:
            if not current:
                current_title = section_label
            current.append(paragraph)
    flush()
    return units


def _split_to_budget(value: str, budget: int, unit: str) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n", "。", ". ", " ", ""],
        chunk_size=max(budget, 40),
        chunk_overlap=0,
        length_function=count_tokens if unit == "tokens" else len,
    )
    return [part.strip() for part in splitter.split_text(value) if part.strip()]


def _split_resume_unit(unit: dict[str, Any], config: ChunkConfig) -> list[dict[str, Any]]:
    paragraphs = list(unit["paragraphs"])
    entity_title = str(unit["entity_title"])
    combined = "\n\n".join(paragraphs)
    if _measure(combined, config) <= config.chunk_size:
        return [{**unit, "body": combined}]

    title_is_body = bool(paragraphs and paragraphs[0] == entity_title)
    content = paragraphs[1:] if title_is_body else paragraphs
    title_cost = _measure(entity_title, config) + 2
    body_budget = max(config.chunk_size - title_cost, 40)
    parts: list[str] = []
    for paragraph in content:
        if _measure(paragraph, config) > body_budget:
            parts.extend(_split_to_budget(paragraph, body_budget, config.unit))
        else:
            parts.append(paragraph)

    results: list[dict[str, Any]] = []
    current: list[str] = []
    for part in parts:
        candidate = "\n\n".join([entity_title, *current, part])
        if current and _measure(candidate, config) > config.chunk_size:
            results.append({**unit, "body": "\n\n".join([entity_title, *current])})
            current = [part]
        else:
            current.append(part)
    if current:
        results.append({**unit, "body": "\n\n".join([entity_title, *current])})
    return results


def _resume_semantic_parts(document: dict[str, Any], config: ChunkConfig) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    for unit in _resume_semantic_units(document):
        parts.extend(_split_resume_unit(unit, config))
    return parts


def _recursive_parts(text: str, config: ChunkConfig) -> list[str]:
    separators = ["\n#{1,6} ", "\n\n", "\n", "。", ". ", " ", ""]
    splitter = RecursiveCharacterTextSplitter(
        separators=separators,
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
        length_function=lambda value: _measure(value, config),
        is_separator_regex=True,
    )
    return splitter.split_text(text)


def _paragraph_parts(text: str, config: ChunkConfig) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    grouped: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip()
        if current and _measure(candidate, config) > config.chunk_size:
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


def build_context_prefix(
    document: dict[str, Any],
    section_path: str = "",
    entity_title: str = "",
) -> str:
    metadata = document.get("metadata") or {}
    values = [f"Document: {document.get('title', 'Untitled')}"]
    project = metadata.get("project") or document.get("project")
    source = metadata.get("source") or document.get("relative_path") or document.get("source_path")
    updated = document.get("updated") or metadata.get("modified_at") or document.get("modified_at")
    if project:
        values.append(f"Project: {project}")
    if section_path:
        values.append(f"Section: {section_path}")
    if entity_title and entity_title not in section_path:
        values.append(f"Entity: {entity_title}")
    if source:
        values.append(f"Source: {source}")
    if updated:
        values.append(f"Updated: {updated}")
    return "[" + " | ".join(str(value) for value in values) + "]"


def split_document(document: dict[str, Any], config: ChunkConfig | None = None) -> list[dict[str, Any]]:
    config = config or ChunkConfig()
    normalized = normalize_document(document, default_visibility=document.get("visibility", "private"))
    semantic_parts: list[dict[str, Any]] | None = None
    if config.strategy == "resume_semantic":
        semantic_parts = _resume_semantic_parts(normalized, config)
        bodies = [part["body"] for part in semantic_parts]
    elif config.strategy == "markdown":
        bodies = _markdown_parts(normalized["body"], config)
    elif config.strategy == "paragraph":
        bodies = _paragraph_parts(normalized["body"], config)
    else:
        bodies = _recursive_parts(normalized["body"], config)

    chunks: list[dict[str, Any]] = []
    for index, body in enumerate(filter(None, (part.strip() for part in bodies))):
        semantic = semantic_parts[index] if semantic_parts is not None else {}
        heading = re.match(r"^#{1,6}\s+(.+)", body)
        entity_title = str(semantic.get("entity_title") or (heading.group(1).strip() if heading else ""))
        section_label = str(semantic.get("section_label") or "")
        section_path = str(
            semantic.get("section_path")
            or (f"{section_label} > {entity_title}" if section_label and entity_title else entity_title)
        )
        context_prefix = build_context_prefix(normalized, section_path, entity_title)
        retrieval_text = f"{context_prefix}\n{body}"
        chunk_id = f"{normalized['doc_id']}_chunk_{index}_{_digest(body, 10)}"
        chunks.append({
            **{key: value for key, value in normalized.items() if key != "body"},
            "chunk_id": chunk_id,
            "chunk_index": index,
            "body": body,
            "raw_body": body,
            "retrieval_text": retrieval_text,
            "context_prefix": context_prefix,
            "section_path": section_path,
            "section_type": semantic.get("section_type") or "document",
            "entity_title": entity_title or normalized["title"],
            "semantic_group_id": semantic.get("semantic_group_id") or chunk_id,
            "retrieval_priority": semantic.get("retrieval_priority") or "primary",
            "token_count": count_tokens(body),
            "source_updated_at": normalized.get("updated")
            or (normalized.get("metadata") or {}).get("modified_at"),
            "validity_status": normalized.get("validity_status") or "active",
            "chunk_unit": config.unit,
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
