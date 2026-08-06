from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


CHUNK_MODES = {"general", "parent_child", "resume_semantic"}
PARENT_MODES = {"paragraph", "full_document", "semantic_section"}
LEGACY_STRATEGIES = {"markdown", "paragraph", "recursive", "resume_semantic"}
MIN_CHUNK_TOKENS = 200
MAX_CHUNK_TOKENS = 2000
MIN_CHILD_TOKENS = 1
LONG_DOCUMENT_TOKENS = 2000
RESUME_FILE_TYPES = {"docx", "pdf", "md", "markdown", "txt"}
BASE_TOKEN_PATTERN = re.compile(r"[\u3400-\u9fff]|[^\W_]+|[^\w\s]")
SCRIPT_RUN_PATTERN = re.compile(
    r"[\u0e00-\u0e7f\u1100-\u11ff\u3040-\u30ff\u3130-\u318f"
    r"\u31f0-\u31ff\uac00-\ud7af]+"
)


def _validate_integer(name: str, value: int, minimum: int, maximum: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")


@dataclass(frozen=True)
class PreprocessingProfile:
    normalize_whitespace: bool = True
    remove_urls: bool = False
    remove_emails: bool = False

    def __post_init__(self) -> None:
        for name in ("normalize_whitespace", "remove_urls", "remove_emails"):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name} must be a boolean")

    def to_dict(self) -> dict[str, bool]:
        return {
            "normalize_whitespace": self.normalize_whitespace,
            "remove_urls": self.remove_urls,
            "remove_emails": self.remove_emails,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PreprocessingProfile:
        return cls(**dict(data))


@dataclass(frozen=True)
class ProcessingProfile:
    profile_version: int = 1
    chunk_mode: str = "general"
    delimiter: str = "\n\n"
    max_tokens: int = 800
    overlap_tokens: int = 80
    parent_mode: str = "paragraph"
    parent_max_tokens: int = 700
    child_max_tokens: int = 180
    preprocessing: PreprocessingProfile = PreprocessingProfile()
    index_mode: str = "high_quality"

    def __post_init__(self) -> None:
        if type(self.profile_version) is not int or self.profile_version != 1:
            raise ValueError("profile_version must be 1")
        if self.chunk_mode not in CHUNK_MODES:
            raise ValueError(f"unsupported chunk_mode: {self.chunk_mode}")
        if self.parent_mode not in PARENT_MODES:
            raise ValueError(f"unsupported parent_mode: {self.parent_mode}")
        if self.index_mode != "high_quality":
            raise ValueError("index_mode must be high_quality in Phase A")
        if not isinstance(self.delimiter, str) or self.delimiter == "":
            raise ValueError("delimiter must be a non-empty string")
        if not isinstance(self.preprocessing, PreprocessingProfile):
            raise ValueError("preprocessing must be a PreprocessingProfile")

        max_tokens_minimum = (
            MIN_CHILD_TOKENS
            if self.chunk_mode == "parent_child"
            else MIN_CHUNK_TOKENS
        )
        _validate_integer(
            "max_tokens", self.max_tokens, max_tokens_minimum, MAX_CHUNK_TOKENS
        )
        _validate_integer(
            "parent_max_tokens",
            self.parent_max_tokens,
            MIN_CHUNK_TOKENS,
            MAX_CHUNK_TOKENS,
        )
        _validate_integer(
            "child_max_tokens",
            self.child_max_tokens,
            MIN_CHILD_TOKENS,
            MAX_CHUNK_TOKENS,
        )
        _validate_integer("overlap_tokens", self.overlap_tokens, 0, MAX_CHUNK_TOKENS)
        if (
            self.chunk_mode == "parent_child"
            and self.max_tokens != self.child_max_tokens
        ):
            raise ValueError(
                "max_tokens must equal child_max_tokens for parent_child mode"
            )
        if (
            self.chunk_mode == "parent_child"
            and self.child_max_tokens >= self.parent_max_tokens
        ):
            raise ValueError(
                "child_max_tokens must be smaller than parent_max_tokens"
            )
        overlap_budget = (
            self.child_max_tokens
            if self.chunk_mode == "parent_child"
            else self.max_tokens
        )
        if self.overlap_tokens > overlap_budget * 0.25:
            budget_name = (
                "child_max_tokens"
                if self.chunk_mode == "parent_child"
                else "max_tokens"
            )
            raise ValueError(
                f"overlap_tokens cannot exceed 25% of {budget_name}"
            )

    @classmethod
    def parent_child(cls, **overrides: Any) -> ProcessingProfile:
        if "chunk_mode" in overrides:
            raise ValueError("chunk_mode cannot be overridden by parent_child()")
        values: dict[str, Any] = {
            "chunk_mode": "parent_child",
            "max_tokens": 180,
            "child_max_tokens": 180,
            "parent_max_tokens": 700,
            "overlap_tokens": 20,
            "parent_mode": "paragraph",
        }
        values.update(overrides)
        return cls(**values)

    @classmethod
    def resume_semantic(cls, **overrides: Any) -> ProcessingProfile:
        if "chunk_mode" in overrides:
            raise ValueError("chunk_mode cannot be overridden by resume_semantic()")
        values: dict[str, Any] = {
            "chunk_mode": "resume_semantic",
            "max_tokens": 320,
            "overlap_tokens": 0,
            "parent_mode": "semantic_section",
        }
        values.update(overrides)
        return cls(**values)

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_version": self.profile_version,
            "chunk_mode": self.chunk_mode,
            "delimiter": self.delimiter,
            "max_tokens": self.max_tokens,
            "overlap_tokens": self.overlap_tokens,
            "parent_mode": self.parent_mode,
            "parent_max_tokens": self.parent_max_tokens,
            "child_max_tokens": self.child_max_tokens,
            "preprocessing": self.preprocessing.to_dict(),
            "index_mode": self.index_mode,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ProcessingProfile:
        values = dict(data)
        preprocessing = values.get("preprocessing", {})
        if isinstance(preprocessing, Mapping):
            values["preprocessing"] = PreprocessingProfile.from_dict(preprocessing)
        return cls(**values)

    def digest(self) -> str:
        serialized = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _legacy_token_value(value: int, unit: str, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("legacy chunk values must be integers")
    converted = math.ceil(value / 4) if unit == "characters" else value
    return max(minimum, min(converted, MAX_CHUNK_TOKENS))


def _normalize_identity(value: object) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value)).casefold()
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _basename(value: object) -> str:
    return re.split(r"[\\/]", str(value))[-1]


def _has_resume_marker(value: object) -> bool:
    normalized = _normalize_identity(value)
    if "简历" in normalized:
        return True
    return bool(
        re.search(
            r"(?<![a-z0-9])(?:resume|cv|curriculum[\s_-]+vitae)(?![a-z0-9])",
            normalized,
        )
    )


def _is_resume_root(value: object) -> bool:
    return _normalize_identity(value).strip() == "resume_root"


def _validate_legacy_values(chunk_size: int, overlap: int) -> None:
    _validate_integer(
        "chunk_size", chunk_size, MIN_CHUNK_TOKENS, MAX_CHUNK_TOKENS
    )
    _validate_integer("overlap", overlap, 0, MAX_CHUNK_TOKENS)
    if overlap > chunk_size * 0.25:
        raise ValueError("overlap cannot exceed 25% of chunk_size")


def profile_from_legacy(
    title: str,
    file_type: str,
    strategy: str,
    chunk_size: int,
    overlap: int,
    unit: str,
) -> ProcessingProfile:
    normalized_strategy = strategy.strip().lower()
    normalized_unit = unit.strip().lower()

    if normalized_strategy not in LEGACY_STRATEGIES:
        raise ValueError(f"unsupported legacy strategy: {strategy}")
    if normalized_unit not in {"characters", "tokens"}:
        raise ValueError(f"unsupported legacy unit: {unit}")
    _validate_legacy_values(chunk_size, overlap)
    if normalized_strategy == "resume_semantic" or _has_resume_marker(
        title
    ) or _has_resume_marker(_basename(file_type)):
        return ProcessingProfile.resume_semantic()

    max_tokens = _legacy_token_value(
        chunk_size, normalized_unit, MIN_CHUNK_TOKENS
    )
    overlap_tokens = _legacy_token_value(overlap, normalized_unit, 0)
    overlap_tokens = min(overlap_tokens, max_tokens // 4)
    return ProcessingProfile(
        chunk_mode="general",
        max_tokens=max_tokens,
        overlap_tokens=overlap_tokens,
    )


def _estimated_tokens(value: str) -> int:
    # Whitespace-free scripts use a deterministic two-characters-per-token
    # approximation. CJK remains per-character; other Unicode words stay grouped.
    estimated = 0
    cursor = 0
    for match in SCRIPT_RUN_PATTERN.finditer(value):
        estimated += len(BASE_TOKEN_PATTERN.findall(value[cursor : match.start()]))
        estimated += math.ceil(len(match.group()) / 2)
        cursor = match.end()
    estimated += len(BASE_TOKEN_PATTERN.findall(value[cursor:]))
    return estimated


def _candidate_values(
    document: Mapping[str, Any], metadata: Mapping[str, Any], name: str
) -> list[object]:
    return [metadata.get(name), document.get(name)]


def recommend_processing_profile(document: Mapping[str, Any]) -> ProcessingProfile:
    metadata = document.get("metadata") or {}
    if not isinstance(metadata, Mapping):
        metadata = {}
    path_candidates = [
        value
        for name in ("source", "path", "relative_path", "file_name")
        for value in _candidate_values(document, metadata, name)
        if value
    ]
    explicit_file_type = metadata.get("file_type") or document.get("file_type")
    file_type = str(explicit_file_type or "").lower().lstrip(".")
    if not file_type:
        for candidate in path_candidates:
            suffix = Path(_basename(candidate)).suffix.lstrip(".").lower()
            if suffix:
                file_type = suffix
                break
    title = str(document.get("title") or "")
    body = str(document.get("body") or "")

    if file_type == "csv":
        return ProcessingProfile(max_tokens=800, overlap_tokens=0)
    if file_type == "json":
        if _estimated_tokens(body) <= LONG_DOCUMENT_TOKENS:
            return ProcessingProfile(max_tokens=800, overlap_tokens=0)
        return ProcessingProfile()

    source_roots = _candidate_values(document, metadata, "source_root")
    source_values = _candidate_values(document, metadata, "source")
    resume_filename = any(
        Path(_basename(value)).suffix.lstrip(".").lower() in RESUME_FILE_TYPES
        and _has_resume_marker(_basename(value))
        for value in path_candidates
    )
    if file_type in RESUME_FILE_TYPES and (
        any(_is_resume_root(value) for value in source_values + source_roots)
        or _has_resume_marker(title)
        or resume_filename
    ):
        return ProcessingProfile.resume_semantic()
    if file_type in {
        "pdf",
        "md",
        "markdown",
        "txt",
        "doc",
        "docx",
        "odt",
        "rtf",
    }:
        if _estimated_tokens(body) > LONG_DOCUMENT_TOKENS:
            return ProcessingProfile.parent_child()
    return ProcessingProfile()
