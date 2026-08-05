from __future__ import annotations

import math
import json
import tempfile
import unittest
from pathlib import Path

from src.evaluation import BenchmarkCase, evaluate_rankings, load_benchmark


class EvaluationTests(unittest.TestCase):
    def test_load_benchmark_rejects_duplicate_case_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "benchmark.json"
            case = {
                "case_id": "same",
                "category": "direct_fact",
                "language": "en",
                "question": "Question?",
                "expected_doc_ids": ["doc"],
                "relevance": {"doc": 3},
                "should_answer": True,
            }
            path.write_text(json.dumps([case, case]), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "duplicate benchmark case_id"):
                load_benchmark(path)

    def test_metrics_distinguish_hit_recall_rank_and_no_answer(self) -> None:
        cases = [
            BenchmarkCase(
                case_id="direct",
                category="direct_fact",
                language="en",
                question="Which project uses MongoDB?",
                expected_doc_ids=("mongo", "quiz"),
                relevance={"mongo": 3, "quiz": 1},
                should_answer=True,
                scope="public",
            ),
            BenchmarkCase(
                case_id="no-answer",
                category="no_answer",
                language="zh",
                question="Junyi 的护照号码是什么？",
                expected_doc_ids=(),
                relevance={},
                should_answer=False,
                scope="public",
            ),
        ]
        rankings = {
            "direct": [
                {"doc_id": "other", "visibility": "public"},
                {"doc_id": "mongo", "visibility": "public"},
            ],
            "no-answer": [],
        }

        report = evaluate_rankings(cases, rankings, ks=(1, 2))

        self.assertEqual(report["case_count"], 2)
        self.assertEqual(report["answerable_count"], 1)
        self.assertEqual(report["hit_at_k"], {"1": 0.0, "2": 1.0})
        self.assertEqual(report["recall_at_k"], {"1": 0.0, "2": 0.5})
        self.assertEqual(report["mrr"], 0.5)
        expected_ndcg = (3 / math.log2(3)) / (3 + 1 / math.log2(3))
        self.assertTrue(math.isclose(report["ndcg_at_k"]["2"], expected_ndcg, rel_tol=1e-6))
        self.assertEqual(report["no_answer_accuracy"], 1.0)
        self.assertEqual(report["privacy_violation_count"], 0)

    def test_public_scope_counts_private_results_as_privacy_violations(self) -> None:
        case = BenchmarkCase(
            case_id="privacy",
            category="privacy",
            language="en",
            question="Find private evidence",
            expected_doc_ids=(),
            relevance={},
            should_answer=False,
            scope="public",
        )

        report = evaluate_rankings(
            [case],
            {"privacy": [{"doc_id": "secret", "visibility": "private"}]},
        )

        self.assertEqual(report["privacy_violation_count"], 1)
        self.assertEqual(report["no_answer_accuracy"], 0.0)


if __name__ == "__main__":
    unittest.main()
