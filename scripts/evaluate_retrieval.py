from __future__ import annotations

import json
import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluation import evaluate_rankings, load_benchmark  # noqa: E402
from src.portfolio_rag import (  # noqa: E402
    get_collections,
    load_embedding_model,
    load_reranker,
    load_settings,
    retrieve_for_question,
    vector_search,
)
from src.query_planning import should_refuse_without_retrieval  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a reproducible local retrieval configuration.")
    parser.add_argument(
        "--mode",
        choices=("adaptive", "baseline", "hybrid", "hybrid-rerank"),
        default="baseline",
    )
    parser.add_argument("--limit", type=int, default=0, help="Optional smoke-test case limit.")
    args = parser.parse_args()
    benchmark_path = ROOT / "evals" / "rag_benchmark.json"
    cases = load_benchmark(benchmark_path)
    if args.limit > 0:
        cases = cases[: args.limit]
    settings = load_settings(ROOT / ".env")
    _, collection, _ = get_collections(settings)
    model = load_embedding_model(settings)
    reranker = load_reranker(settings) if args.mode == "hybrid-rerank" else None
    rankings = {}
    latencies = {}
    diagnostics_by_case = {}
    for index, case in enumerate(cases, 1):
        started = time.perf_counter()
        diagnostics: dict = {}
        if should_refuse_without_retrieval(case.question):
            rankings[case.case_id] = []
        elif args.mode == "adaptive":
            rankings[case.case_id] = retrieve_for_question(
                collection,
                model,
                settings,
                case.question,
                top_k=10,
                scope=case.scope,
                retrieval_mode="adaptive",
                diagnostics=diagnostics,
            )
        else:
            rankings[case.case_id] = vector_search(
                collection,
                model,
                settings,
                case.question,
                top_k=10,
                scope=case.scope,
                mode="baseline" if args.mode == "baseline" else "hybrid",
                reranker=reranker,
            )
        diagnostics_by_case[case.case_id] = diagnostics
        latencies[case.case_id] = (time.perf_counter() - started) * 1000
        print(f"[{index:02d}/{len(cases)}] {case.case_id}")
    report = {
        "mode": args.mode,
        "case_count": len(cases),
        **evaluate_rankings(cases, rankings, ks=(1, 3, 5, 10), latencies_ms=latencies),
        "cases": [
            {
                "case_id": case.case_id,
                "should_answer": case.should_answer,
                "expected_doc_ids": list(case.expected_doc_ids),
                "top_results": [
                    {
                        "doc_id": row.get("doc_id"),
                        "title": row.get("title"),
                        "score": row.get("score"),
                        "fusion_score": row.get("fusion_score"),
                        "channels": row.get("retrieval_channels"),
                    }
                    for row in rankings.get(case.case_id, [])[:10]
                ],
                "latency_ms": round(latencies[case.case_id], 2),
                "diagnostics": diagnostics_by_case[case.case_id],
            }
            for case in cases
        ],
    }
    output = ROOT / "evals" / f"latest-report-{args.mode}.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Report: {output}")


if __name__ == "__main__":
    main()
