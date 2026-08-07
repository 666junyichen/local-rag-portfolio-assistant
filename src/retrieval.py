from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable, Sequence


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


def tokenize_for_search(value: str) -> list[str]:
    """Return lowercase technical terms plus CJK unigrams and bigrams."""
    lowered = value.lower()
    latin = re.findall(r"[a-z0-9][a-z0-9.+#:_/-]*", lowered)
    cjk_runs = re.findall(r"[\u3400-\u9fff]+", lowered)
    cjk_tokens: list[str] = []
    for run in cjk_runs:
        cjk_tokens.extend(run)
        cjk_tokens.extend(run[index : index + 2] for index in range(len(run) - 1))
    return latin + cjk_tokens


def bm25_rank(
    rows: Iterable[dict[str, Any]],
    query: str,
    *,
    top_k: int = 50,
    k1: float = 1.5,
    b: float = 0.75,
) -> list[dict[str, Any]]:
    documents = [dict(row) for row in rows]
    if not documents or not query.strip():
        return []
    tokenized = [
        tokenize_for_search(
            " ".join(
                str(value)
                for value in (row.get("title", ""), row.get("retrieval_text", ""), row.get("body", ""))
            )
        )
        for row in documents
    ]
    query_tokens = tokenize_for_search(query)
    if not query_tokens:
        return []
    document_frequency = Counter(token for tokens in tokenized for token in set(tokens))
    average_length = sum(len(tokens) for tokens in tokenized) / max(len(tokenized), 1)
    ranked: list[dict[str, Any]] = []
    for row, tokens in zip(documents, tokenized):
        frequencies = Counter(tokens)
        score = 0.0
        for token in query_tokens:
            frequency = frequencies[token]
            if not frequency:
                continue
            df = document_frequency[token]
            idf = math.log(1 + (len(documents) - df + 0.5) / (df + 0.5))
            denominator = frequency + k1 * (1 - b + b * len(tokens) / max(average_length, 1))
            score += idf * frequency * (k1 + 1) / denominator
        if score > 0:
            row["bm25_score"] = float(score)
            ranked.append(row)
    ranked.sort(key=lambda item: float(item["bm25_score"]), reverse=True)
    return ranked[: max(1, top_k)]


def _row_key(row: dict[str, Any]) -> str:
    return str(row.get("chunk_id") or row.get("doc_id") or row.get("_id") or "")


def reciprocal_rank_fusion(
    vector_rows: Sequence[dict[str, Any]],
    sparse_rows: Sequence[dict[str, Any]],
    *,
    rrf_k: int = 60,
    vector_weight: float = 1.0,
    sparse_weight: float = 1.0,
) -> list[dict[str, Any]]:
    fused: dict[str, dict[str, Any]] = {}
    for channel, rows, weight in (
        ("vector", vector_rows, vector_weight),
        ("bm25", sparse_rows, sparse_weight),
    ):
        for rank, raw in enumerate(rows, 1):
            key = _row_key(raw)
            if not key:
                continue
            item = fused.setdefault(key, dict(raw))
            item.update({name: value for name, value in raw.items() if name not in item})
            item[f"{channel}_rank"] = rank
            channels = item.setdefault("retrieval_channels", [])
            if channel not in channels:
                channels.append(channel)
            item["fusion_score"] = float(item.get("fusion_score", 0.0)) + weight / (rrf_k + rank)
    return sorted(fused.values(), key=lambda item: float(item["fusion_score"]), reverse=True)


def rerank_with_cross_encoder(
    rows: Sequence[dict[str, Any]],
    query: str,
    reranker: Any,
    *,
    top_k: int,
) -> list[dict[str, Any]]:
    candidates = [dict(row) for row in rows]
    if not candidates:
        return []
    pairs = [
        (query, str(row.get("retrieval_text") or row.get("raw_body") or row.get("body") or ""))
        for row in candidates
    ]
    scores = reranker.predict(pairs)
    for row, score in zip(candidates, scores):
        row["reranker_score"] = float(score)
    candidates.sort(key=lambda item: float(item["reranker_score"]), reverse=True)
    return candidates[: max(1, top_k)]


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


SECTION_INTENT_MARKERS = {
    "education": ("课程", "教育", "学校", "大学", "学过", "course", "education", "university"),
    "internship": ("实习", "工作经历", "公司经历", "internship", "intern", "work experience"),
    "award": ("获奖", "奖项", "奖", "award", "prize"),
    "skill": ("技能", "技术栈", "能力", "skill", "tech stack"),
}


def infer_section_intents(query: str) -> set[str]:
    lowered = query.lower()
    intended_sections = {
        section
        for section, markers in SECTION_INTENT_MARKERS.items()
        if any(marker in lowered for marker in markers)
    }
    asks_for_project_category = (
        "项目" in lowered
        and any(marker in lowered for marker in ("哪些", "哪个", "项目经验", "体现"))
    ) or (
        "什么项目" in lowered
    ) or any(
        marker in lowered
        for marker in ("which project", "what project", "projects", "project experience", "portfolio")
    )
    if asks_for_project_category:
        intended_sections.add("project")
    return intended_sections


def apply_section_intent_rerank(rows: Iterable[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    """Apply a small, explainable boost when the question names a resume section."""
    intended_sections = infer_section_intents(query)
    reranked: list[dict[str, Any]] = []
    for raw in rows:
        item = dict(raw)
        base_score = float(
            item.get(
                "reranker_score",
                item.get("fusion_score", item.get("rank_score", item.get("score", 0))),
            )
        )
        section_type = str(item.get("section_type") or "document")
        boost = 0.12 if section_type in intended_sections else 0.0
        if intended_sections and section_type in {"profile", "summary"}:
            boost -= 0.03
        item["intent_score"] = base_score + boost
        item["matched_section_intent"] = section_type in intended_sections
        reranked.append(item)
    reranked.sort(key=lambda item: float(item["intent_score"]), reverse=True)
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
        item = dict(row)
        raw_body = str(item.get("raw_body") or item.get("body") or "")
        parent_body = str(item.get("parent_body") or "")
        item["matched_child_body"] = raw_body
        item["parent_expanded"] = bool(parent_body and parent_body != raw_body)
        item["body"] = parent_body or raw_body
        selected.append(item)
    def result_score(item: dict[str, Any]) -> float:
        return float(
            item.get(
                "intent_score",
                item.get(
                    "reranker_score",
                    item.get("fusion_score", item.get("rank_score", item.get("score", 0))),
                ),
            )
        )

    selected.sort(
        key=lambda item: (
            str(item.get("retrieval_priority") or "primary") != "secondary",
            result_score(item),
        ),
        reverse=True,
    )
    diversified: list[dict[str, Any]] = []
    seen_groups: set[str] = set()
    for item in selected:
        group_id = str(item.get("semantic_group_id") or _row_key(item))
        if group_id and group_id in seen_groups:
            continue
        if group_id:
            seen_groups.add(group_id)
        diversified.append(item)
        if len(diversified) >= settings.top_k:
            break
    return diversified
