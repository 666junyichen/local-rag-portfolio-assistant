from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class RetrievalSettings:
    top_k: int = 5
    score_threshold: float | None = None
    scope: str = "public"

    def __post_init__(self) -> None:
        if not 1 <= self.top_k <= 10:
            raise ValueError("top_k must be between 1 and 10")
        if self.score_threshold is not None and not 0 <= self.score_threshold <= 1:
            raise ValueError("score_threshold must be between 0 and 1")
        if self.scope not in {"public", "all"}:
            raise ValueError("scope must be public or all")


def apply_keyword_rerank(rows: Iterable[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    """Boost exact technical terms inside an already retrieved vector candidate set."""
    stop_words = {"and", "are", "for", "from", "has", "have", "the", "what", "which", "with", "experience"}
    tokens = {
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9.+#-]{1,}", query)
        if token.lower() not in stop_words
    }
    reranked = []
    for row in rows:
        item = dict(row)
        searchable = " ".join(
            str(value)
            for value in (
                item.get("title", ""),
                item.get("body", ""),
                (item.get("metadata") or {}).get("category", ""),
            )
        ).lower()
        matches = sum(token in searchable for token in tokens)
        item["rank_score"] = float(item.get("score", 0)) + min(matches * 0.06, 0.18)
        reranked.append(item)
    return reranked


def select_results(rows: Iterable[dict[str, Any]], settings: RetrievalSettings) -> list[dict[str, Any]]:
    selected = []
    for row in rows:
        visibility = row.get("visibility") or (row.get("metadata") or {}).get("visibility") or "public"
        score = float(row.get("score", 0))
        if settings.scope == "public" and visibility != "public":
            continue
        if settings.score_threshold is not None and score < settings.score_threshold:
            continue
        selected.append(row)
    selected.sort(
        key=lambda item: float(item.get("rank_score", item.get("score", 0))),
        reverse=True,
    )
    return selected[: settings.top_k]
