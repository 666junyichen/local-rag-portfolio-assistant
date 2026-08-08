from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class QueryPlan:
    original: str
    mode: str
    subqueries: tuple[str, ...]
    max_rounds: int = 1


@dataclass(frozen=True)
class RerankerDecision:
    enabled: bool
    reasons: tuple[str, ...]


COMPLEX_MARKERS = (
    "compare", "comparison", "summarize", "summary", "across", "differences",
    "对比", "比较", "总结", "归纳", "综合", "分别", "哪些项目", "项目和技能",
)

SENSITIVE_MARKERS = (
    "passport", "salary", "gpa", "home address", "date of birth", "birthday",
    "phone number", "private email", "wechat", "raw file", "full private", "private resume",
    "护照", "薪资", "工资", "绩点", "住址", "家庭地址", "出生日期", "生日",
    "手机号码", "电话号码", "私人邮箱", "微信号", "私有文件", "原始文件", "未公开", "简历全文",
)

FRESHNESS_MARKERS = (
    "latest", "newest", "most recent", "current", "currently", "up to date",
    "最新", "最近", "当前", "现在", "现阶段", "更新时间", "毕业时间",
)


def should_refuse_without_retrieval(question: str) -> bool:
    lowered = question.lower()
    return any(marker in lowered for marker in SENSITIVE_MARKERS)


def is_freshness_query(question: str) -> bool:
    lowered = question.lower()
    return any(marker in lowered for marker in FRESHNESS_MARKERS)


def should_use_precision_reranker(
    question: str,
    rows: list[dict],
    *,
    force: bool = False,
) -> RerankerDecision:
    """Route only queries that benefit from slower local precision ranking."""
    reasons: list[str] = []
    if force:
        reasons.append("user-requested")
    if plan_query(question).mode == "complex":
        reasons.append("complex-query")
    scores = sorted(
        (float(row.get("score") or row.get("rank_score") or 0) for row in rows),
        reverse=True,
    )
    if not scores or scores[0] < 0.45 or (len(scores) > 1 and scores[0] - scores[1] < 0.02):
        reasons.append("low-confidence")
    return RerankerDecision(bool(reasons), tuple(dict.fromkeys(reasons)))


def plan_query(question: str) -> QueryPlan:
    original = question.strip()
    lowered = original.lower()
    if not any(marker in lowered for marker in COMPLEX_MARKERS):
        return QueryPlan(original, "simple", (original,))

    pieces = [
        value.strip(" ,，。?？")
        for value in re.split(r"\b(?:and|versus|vs\.?|compared with)\b|[、，]|(?:和|与)", original, flags=re.IGNORECASE)
        if value.strip(" ,，。?？")
    ]
    subqueries = [original]
    for piece in pieces:
        if piece != original and len(piece) >= 4 and piece not in subqueries:
            subqueries.append(piece)
        if len(subqueries) == 3:
            break
    return QueryPlan(original, "complex", tuple(subqueries), max_rounds=2)
