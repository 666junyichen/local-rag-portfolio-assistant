from __future__ import annotations

import unittest

from src.retrieval import (
    RetrievalSettings,
    apply_keyword_rerank,
    bm25_rank,
    reciprocal_rank_fusion,
    rerank_with_cross_encoder,
    select_results,
)


class RetrievalTests(unittest.TestCase):
    def test_bm25_can_recall_an_exact_term_missing_from_semantic_candidates(self) -> None:
        rows = [
            {"chunk_id": "generic", "body": "General machine learning project"},
            {"chunk_id": "qanet", "body": "QANet debugging on SQuAD v1.1"},
        ]

        ranked = bm25_rank(rows, "QANet", top_k=1)

        self.assertEqual(ranked[0]["chunk_id"], "qanet")
        self.assertGreater(ranked[0]["bm25_score"], 0)

    def test_rrf_promotes_a_chunk_returned_by_both_retrievers(self) -> None:
        vector = [
            {"chunk_id": "vector-only", "score": 0.95},
            {"chunk_id": "both", "score": 0.8},
        ]
        sparse = [
            {"chunk_id": "sparse-only", "bm25_score": 5.0},
            {"chunk_id": "both", "bm25_score": 4.0},
        ]

        fused = reciprocal_rank_fusion(vector, sparse, rrf_k=60)

        self.assertEqual(fused[0]["chunk_id"], "both")
        self.assertEqual(fused[0]["retrieval_channels"], ["vector", "bm25"])
        self.assertEqual(fused[0]["vector_rank"], 2)
        self.assertEqual(fused[0]["bm25_rank"], 2)

    def test_weighted_rrf_can_preserve_a_strong_vector_first_result(self) -> None:
        vector = [{"chunk_id": "dense", "score": 0.95}, {"chunk_id": "both", "score": 0.8}]
        sparse = [{"chunk_id": "exact", "bm25_score": 8.0}, {"chunk_id": "both", "bm25_score": 7.0}]

        fused = reciprocal_rank_fusion(vector, sparse, vector_weight=2.0, sparse_weight=0.7)

        self.assertEqual(fused[0]["chunk_id"], "both")
        self.assertGreater(fused[1]["fusion_score"], fused[2]["fusion_score"])

    def test_cross_encoder_scores_replace_fusion_order_for_final_ranking(self) -> None:
        class FakeReranker:
            def predict(self, pairs):
                self.pairs = pairs
                return [0.1, 0.9]

        rows = [
            {"chunk_id": "first", "body": "generic", "fusion_score": 0.04},
            {"chunk_id": "second", "body": "specific evidence", "fusion_score": 0.03},
        ]

        reranked = rerank_with_cross_encoder(rows, "specific question", FakeReranker(), top_k=2)

        self.assertEqual([row["chunk_id"] for row in reranked], ["second", "first"])
        self.assertEqual(reranked[0]["reranker_score"], 0.9)

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
