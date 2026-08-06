from __future__ import annotations

import hashlib
import json
import math
import re
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
        if not isinstance(self.delimiter, str):
            raise ValueError("delimiter must be a string")
        if not isinstance(self.preprocessing, PreprocessingProfile):
            raise ValueError("preprocessing must be a PreprocessingProfile")

        _validate_integer(
            "max_tokens", self.max_tokens, MIN_CHUNK_TOKENS, MAX_CHUNK_TOKENS
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
        if self.overlap_tokens > self.max_tokens * 0.25:
            raise ValueError("overlap_tokens cannot exceed 25% of max_tokens")
        if (
            self.chunk_mode == "parent_child"
            and self.child_max_tokens >= self.parent_max_tokens
        ):
            raise ValueError(
                "child_max_tokens must be smaller than parent_max_tokens"
            )

    @classmethod
    def parent_child(cls, **overrides: Any) -> ProcessingProfile:
        values: dict[str, Any] = {
            "chunk_mode": "parent_child",
            "child_max_tokens": 180,
            "parent_max_tokens": 700,
            "overlap_tokens": 20,
            "parent_mode": "paragraph",
        }
        values.update(overrides)
        return cls(**values)

    @classmethod
    def resume_semantic(cls, **overrides: Any) -> ProcessingProfile:
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
    normalized_type = file_type.strip().lower().lstrip(".")
    normalized_title = title.strip().lower()

    if normalized_strategy not in LEGACY_STRATEGIES:
        raise ValueError(f"unsupported legacy strategy: {strategy}")
    if normalized_unit not in {"characters", "tokens"}:
        raise ValueError(f"unsupported legacy unit: {unit}")
    if (
        normalized_strategy == "resume_semantic"
        or normalized_type == "docx"
        or "resume" in normalized_title
    ):
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
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9.+#:_/-]*|[^\s]", value))


def recommend_processing_profile(document: Mapping[str, Any]) -> ProcessingProfile:
    metadata = document.get("metadata") or {}
    if not isinstance(metadata, Mapping):
        metadata = {}
    source = str(
        metadata.get("source")
        or document.get("path")
        or document.get("relative_path")
        or ""
    )
    file_type = str(
        metadata.get("file_type") or Path(source).suffix.lstrip(".")
    ).lower()
    title = str(document.get("title") or "").lower()
    body = str(document.get("body") or "")

    if file_type == "docx" or "resume" in title:
        return ProcessingProfile.resume_semantic()
    if file_type == "csv":
        return ProcessingProfile(max_tokens=800, overlap_tokens=0)
    if file_type == "json" and _estimated_tokens(body) <= LONG_DOCUMENT_TOKENS:
        return ProcessingProfile(max_tokens=800, overlap_tokens=0)
    if file_type in {"pdf", "md", "markdown", "txt", "doc", "odt", "rtf"}:
        if _estimated_tokens(body) > LONG_DOCUMENT_TOKENS:
            return ProcessingProfile.parent_child()
    return ProcessingProfile()
