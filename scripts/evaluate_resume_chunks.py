from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.document_processing import (  # noqa: E402
    chunk_metrics,
    parse_uploaded_file,
    rank_preview_chunks,
    recommend_chunk_config,
    split_document,
)
from src.portfolio_rag import load_embedding_model, load_settings  # noqa: E402


def find_default_resume() -> Path:
    candidates = sorted((ROOT / "data" / "local_uploads").glob("*Master.docx"))
    if not candidates:
        raise FileNotFoundError(
            "No *Master.docx was found in data/local_uploads. Pass --document explicitly."
        )
    return candidates[0]


def is_relevant(result: dict[str, Any], case: dict[str, Any]) -> bool:
    if result.get("section_type") != case["expected_section_type"]:
        return False
    expected_entity = str(case.get("expected_entity_contains") or "").lower()
    if not expected_entity:
        return True
    entity = str(result.get("entity_title") or "").lower()
    body = str(result.get("body") or "").lower()
    return expected_entity in entity or expected_entity in body


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate semantic resume chunk retrieval.")
    parser.add_argument("--document", type=Path, default=None)
    parser.add_argument(
        "--benchmark",
        type=Path,
        default=ROOT / "evals" / "resume_semantic_benchmark.json",
    )
    args = parser.parse_args()

    document_path = args.document or find_default_resume()
    document = parse_uploaded_file(document_path)[0]
    config = recommend_chunk_config(document)
    chunks = split_document(document, config)
    cases = json.loads(args.benchmark.read_text(encoding="utf-8"))
    model = load_embedding_model(load_settings())

    hits = {1: 0, 3: 0, 5: 0}
    reciprocal_rank = 0.0
    print(f"Document: {document_path}")
    print(f"Config: {config}")
    print(f"Chunk metrics: {chunk_metrics(chunks)}")

    for number, case in enumerate(cases, start=1):
        results = rank_preview_chunks(chunks, case["question"], model, top_k=5)
        relevant_rank = next(
            (rank for rank, result in enumerate(results, start=1) if is_relevant(result, case)),
            None,
        )
        if relevant_rank:
            reciprocal_rank += 1 / relevant_rank
            for cutoff in hits:
                hits[cutoff] += int(relevant_rank <= cutoff)
        print(f"\n{number}. {case['question']} | relevant rank: {relevant_rank or '-'}")
        for rank, result in enumerate(results, start=1):
            display_score = float(
                result.get(
                    "intent_score",
                    result.get("fusion_score", result.get("score", result.get("bm25_score", 0))),
                )
            )
            print(
                f"   {rank}. {result['section_type']} | {result['entity_title']} | "
                f"score={display_score:.4f} | {result['retrieval_priority']}"
            )

    total = len(cases) or 1
    print("\nResume semantic retrieval summary")
    for cutoff in (1, 3, 5):
        print(f"Hit@{cutoff}: {hits[cutoff] / total:.3f}")
    print(f"MRR: {reciprocal_rank / total:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
