from __future__ import annotations

import unittest
from unittest.mock import patch

from src.portfolio_rag import Settings, adaptive_search, full_text_search, hybrid_search


class PortfolioRetrievalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = Settings(
            mongodb_uri="mongodb://localhost",
            ollama_base_url="http://localhost:11434",
            ollama_model="qwen2.5:3b",
        )

    @patch("src.portfolio_rag.hybrid_search")
    @patch("src.portfolio_rag.vector_search")
    def test_adaptive_search_keeps_clear_queries_on_fast_vector_path(self, vector, hybrid) -> None:
        vector.return_value = [
            {"chunk_id": "a", "score": 0.84},
            {"chunk_id": "b", "score": 0.62},
        ]
        diagnostics = {}

        results = adaptive_search(
            object(), object(), self.settings, "What MongoDB experience does Junyi have?",
            diagnostics=diagnostics,
        )

        self.assertEqual(results, vector.return_value)
        hybrid.assert_not_called()
        self.assertEqual(diagnostics["retrieval_path"], "vector")
        self.assertFalse(diagnostics["reranker_triggered"])

    @patch("src.portfolio_rag.try_load_reranker")
    @patch("src.portfolio_rag.hybrid_search")
    @patch("src.portfolio_rag.vector_search")
    def test_adaptive_search_routes_low_confidence_to_hybrid_rerank(
        self, vector, hybrid, load_reranker
    ) -> None:
        vector.return_value = [
            {"chunk_id": "a", "score": 0.39},
            {"chunk_id": "b", "score": 0.38},
        ]
        reranker = object()
        load_reranker.return_value = (reranker, None)
        hybrid.return_value = [{"chunk_id": "b", "reranker_score": 0.9}]
        diagnostics = {}

        results = adaptive_search(
            object(), object(), self.settings, "What is the latest deployment?",
            diagnostics=diagnostics,
        )

        self.assertEqual(results, hybrid.return_value)
        self.assertEqual(hybrid.call_args.kwargs["reranker"], reranker)
        self.assertEqual(diagnostics["retrieval_path"], "hybrid-rerank")
        self.assertTrue(diagnostics["reranker_triggered"])
        self.assertIn("low-confidence", diagnostics["reranker_reasons"])

    @patch("src.portfolio_rag.try_load_reranker")
    @patch("src.portfolio_rag.hybrid_search")
    @patch("src.portfolio_rag.vector_search")
    def test_adaptive_search_falls_back_to_vector_when_reranker_is_unavailable(
        self, vector, hybrid, load_reranker
    ) -> None:
        vector.return_value = [{"chunk_id": "a", "score": 0.31}]
        load_reranker.return_value = (None, "model unavailable")
        diagnostics = {}

        results = adaptive_search(
            object(), object(), self.settings, "Summarize Junyi's AI projects",
            diagnostics=diagnostics,
        )

        self.assertEqual(results, vector.return_value)
        hybrid.assert_not_called()
        self.assertEqual(diagnostics["retrieval_path"], "vector")
        self.assertEqual(diagnostics["fallback_reason"], "model unavailable")

    @patch("src.portfolio_rag.sparse_search")
    def test_full_text_search_normalizes_bm25_scores_and_selects_top_k(self, sparse) -> None:
        sparse.return_value = [
            {"chunk_id": "a", "doc_id": "a", "visibility": "public", "bm25_score": 12.0},
            {"chunk_id": "b", "doc_id": "b", "visibility": "public", "bm25_score": 6.0},
        ]

        results = full_text_search(object(), self.settings, "MongoDB", top_k=1, scope="public")

        self.assertEqual([row["chunk_id"] for row in results], ["a"])
        self.assertEqual(results[0]["retrieval_channels"], ["bm25"])
        self.assertEqual(results[0]["bm25_rank"], 1)
        self.assertEqual(results[0]["score"], 1.0)

    @patch("src.portfolio_rag.sparse_search")
    @patch("src.portfolio_rag.vector_candidates")
    def test_hybrid_search_fuses_independent_candidate_sets(self, vector, sparse) -> None:
        vector.return_value = [
            {"chunk_id": "dense", "doc_id": "d1", "score": 0.9, "visibility": "public"},
            {"chunk_id": "both", "doc_id": "d2", "score": 0.8, "visibility": "public"},
        ]
        sparse.return_value = [
            {"chunk_id": "exact", "doc_id": "d3", "bm25_score": 8.0, "visibility": "public"},
            {"chunk_id": "both", "doc_id": "d2", "bm25_score": 7.0, "visibility": "public"},
        ]

        results = hybrid_search(object(), object(), self.settings, "QANet", top_k=3, scope="public")

        self.assertEqual(results[0]["chunk_id"], "both")
        self.assertEqual({row["chunk_id"] for row in results}, {"both", "dense", "exact"})
        self.assertEqual(results[0]["retrieval_channels"], ["vector", "bm25"])

    @patch("src.portfolio_rag.sparse_search")
    @patch("src.portfolio_rag.vector_candidates")
    def test_hybrid_search_can_apply_a_cross_encoder_after_fusion(self, vector, sparse) -> None:
        vector.return_value = [{"chunk_id": "a", "body": "generic", "score": 0.9, "visibility": "public"}]
        sparse.return_value = [{"chunk_id": "b", "body": "QANet evidence", "bm25_score": 2.0, "visibility": "public"}]

        class Reranker:
            def predict(self, pairs):
                return [0.1, 0.9]

        results = hybrid_search(
            object(), object(), self.settings, "QANet", top_k=2, scope="public", reranker=Reranker()
        )

        self.assertEqual(results[0]["chunk_id"], "b")


if __name__ == "__main__":
    unittest.main()
