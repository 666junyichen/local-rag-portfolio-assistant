from __future__ import annotations

import math
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    category: str
    language: str
    question: str
    expected_doc_ids: tuple[str, ...]
    relevance: Mapping[str, int]
    should_answer: bool
    scope: str = "public"
    required_facts: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "BenchmarkCase":
        return cls(
            case_id=str(value["case_id"]),
            category=str(value["category"]),
            language=str(value["language"]),
            question=str(value["question"]),
            expected_doc_ids=tuple(str(item) for item in value.get("expected_doc_ids", [])),
            relevance={str(key): int(score) for key, score in value.get("relevance", {}).items()},
            should_answer=bool(value.get("should_answer", True)),
            scope=str(value.get("scope", "public")),
            required_facts=tuple(str(item) for item in value.get("required_facts", [])),
        )


def load_benchmark(path: str | Path) -> list[BenchmarkCase]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("benchmark must contain a JSON array")
    cases = [BenchmarkCase.from_dict(item) for item in payload]
    identifiers = [case.case_id for case in cases]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("duplicate benchmark case_id")
    for case in cases:
        if case.language not in {"zh", "en"}:
            raise ValueError(f"unsupported benchmark language: {case.language}")
        if case.scope not in {"public", "all"}:
            raise ValueError(f"unsupported benchmark scope: {case.scope}")
        if case.should_answer and not case.expected_doc_ids:
            raise ValueError(f"answerable case {case.case_id} has no expected_doc_ids")
    return cases


def _doc_ids(rows: Sequence[Mapping[str, Any]], limit: int) -> list[str]:
    return [str(row.get("doc_id") or "") for row in rows[:limit]]


def _dcg(doc_ids: Sequence[str], relevance: Mapping[str, int]) -> float:
    return sum(float(relevance.get(doc_id, 0)) / math.log2(rank + 2) for rank, doc_id in enumerate(doc_ids))


def evaluate_rankings(
    cases: Iterable[BenchmarkCase],
    rankings: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    ks: tuple[int, ...] = (1, 3, 5),
    latencies_ms: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    case_list = list(cases)
    answerable = [case for case in case_list if case.should_answer]
    no_answer = [case for case in case_list if not case.should_answer]
    hit_totals = {k: 0.0 for k in ks}
    recall_totals = {k: 0.0 for k in ks}
    ndcg_totals = {k: 0.0 for k in ks}
    reciprocal_ranks: list[float] = []
    privacy_violations = 0

    for case in case_list:
        rows = list(rankings.get(case.case_id, []))
        if case.scope == "public":
            privacy_violations += sum(
                (row.get("visibility") or (row.get("metadata") or {}).get("visibility")) == "private"
                for row in rows
            )
        if not case.should_answer:
            continue
        expected = set(case.expected_doc_ids)
        all_ids = _doc_ids(rows, max(ks))
        first_rank = next((index + 1 for index, doc_id in enumerate(all_ids) if doc_id in expected), None)
        reciprocal_ranks.append(1.0 / first_rank if first_rank else 0.0)
        for k in ks:
            ids = all_ids[:k]
            retrieved = expected.intersection(ids)
            hit_totals[k] += float(bool(retrieved))
            recall_totals[k] += len(retrieved) / len(expected) if expected else 1.0
            ideal = sorted(case.relevance.values(), reverse=True)[:k]
            ideal_dcg = sum(float(gain) / math.log2(rank + 2) for rank, gain in enumerate(ideal))
            ndcg_totals[k] += _dcg(ids, case.relevance) / ideal_dcg if ideal_dcg else 1.0

    denominator = max(len(answerable), 1)
    no_answer_correct = sum(not rankings.get(case.case_id) for case in no_answer)
    latency_values = list((latencies_ms or {}).values())
    return {
        "case_count": len(case_list),
        "answerable_count": len(answerable),
        "no_answer_count": len(no_answer),
        "hit_at_k": {str(k): hit_totals[k] / denominator for k in ks},
        "recall_at_k": {str(k): recall_totals[k] / denominator for k in ks},
        "mrr": sum(reciprocal_ranks) / denominator,
        "ndcg_at_k": {str(k): ndcg_totals[k] / denominator for k in ks},
        "no_answer_accuracy": no_answer_correct / len(no_answer) if no_answer else 1.0,
        "privacy_violation_count": privacy_violations,
        "average_latency_ms": sum(latency_values) / len(latency_values) if latency_values else 0.0,
    }
