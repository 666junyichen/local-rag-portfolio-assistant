from __future__ import annotations

import unittest

from src.retrieval import RetrievalSettings, apply_keyword_rerank, select_results


class RetrievalTests(unittest.TestCase):
    def test_keyword_rerank_promotes_explicit_technical_terms(self) -> None:
        rows = [
            {"title": "Generic profile", "body": "General AI experience", "score": 0.82},
            {"title": "Local RAG", "body": "MongoDB Vector Search RAG assistant", "score": 0.78},
        ]

        reranked = apply_keyword_rerank(rows, "RAG and MongoDB experience")
        selected = select_results(reranked, RetrievalSettings(top_k=1))

        self.assertEqual(selected[0]["title"], "Local RAG")
        self.assertEqual(selected[0]["score"], 0.78)

    def test_settings_enforce_top_k_range(self) -> None:
        with self.assertRaises(ValueError):
            RetrievalSettings(top_k=11)

    def test_select_results_filters_visibility_score_and_limit(self) -> None:
        rows = [
            {"title": "Public strong", "visibility": "public", "score": 0.9},
            {"title": "Private strong", "visibility": "private", "score": 0.95},
            {"title": "Public weak", "visibility": "public", "score": 0.4},
            {"title": "Public medium", "visibility": "public", "score": 0.8},
        ]

        selected = select_results(
            rows,
            RetrievalSettings(top_k=2, score_threshold=0.5, scope="public"),
        )

        self.assertEqual([row["title"] for row in selected], ["Public strong", "Public medium"])

    def test_public_and_private_scope_keeps_private_results(self) -> None:
        rows = [{"title": "Private", "visibility": "private", "score": 0.8}]
        selected = select_results(rows, RetrievalSettings(scope="all"))
        self.assertEqual(len(selected), 1)


if __name__ == "__main__":
    unittest.main()
