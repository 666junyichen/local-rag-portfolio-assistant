from __future__ import annotations

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
    selected.sort(key=lambda item: float(item.get("score", 0)), reverse=True)
    return selected[: settings.top_k]
