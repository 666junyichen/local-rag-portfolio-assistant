from __future__ import annotations

import unittest

from src.retrieval import (
    RetrievalSettings,
    apply_keyword_rerank,
    apply_freshness_rerank,
    apply_section_intent_rerank,
    bm25_rank,
    reciprocal_rank_fusion,
    rerank_with_cross_encoder,
    select_results,
)


class RetrievalTests(unittest.TestCase):

    def test_freshness_rerank_only_changes_order_for_freshness_questions(self) -> None:
        rows = [
            {"chunk_id": "older", "score": 0.62, "updated": "2025-01-01"},
            {"chunk_id": "newer", "score": 0.60, "updated": "2026-07-01"},
        ]

        fresh = apply_freshness_rerank(rows, "What is the latest deployment?")
        ordinary = apply_freshness_rerank(rows, "What was deployed?")

        self.assertEqual(fresh[0]["chunk_id"], "newer")
        self.assertTrue(fresh[0]["freshness_applied"])
        self.assertEqual([row["chunk_id"] for row in ordinary], ["older", "newer"])

    def test_freshness_rerank_reads_nested_source_dates(self) -> None:
        rows = [
            {"chunk_id": "old", "score": 0.50, "metadata": {"modified_at": "2024-02-01"}},
            {"chunk_id": "new", "score": 0.49, "source_updated_at": "2026-06-01"},
        ]

        ranked = apply_freshness_rerank(rows, "当前最新版本是什么？")

        self.assertEqual(ranked[0]["chunk_id"], "new")

    def test_section_intent_promotes_project_evidence_for_project_questions(self) -> None:
        rows = [
            {"chunk_id": "internship", "section_type": "internship", "score": 0.56},
            {"chunk_id": "project-one", "section_type": "project", "score": 0.49},
            {"chunk_id": "project-two", "section_type": "project", "score": 0.47},
            {"chunk_id": "summary", "section_type": "summary", "score": 0.53},
        ]

        reranked = apply_section_intent_rerank(rows, "Junyi 有哪些 AI 项目？")
        selected = select_results(reranked, RetrievalSettings(top_k=3, scope="all"))

        self.assertEqual([row["section_type"] for row in selected[:2]], ["project", "project"])
        self.assertGreater(selected[0]["intent_score"], rows[0]["score"])

    def test_named_project_question_does_not_force_project_section(self) -> None:
        rows = [
            {"chunk_id": "consulting", "section_type": "internship", "score": 0.50},
            {"chunk_id": "other-project", "section_type": "project", "score": 0.51},
        ]

        reranked = apply_section_intent_rerank(rows, "在 Study Australia 项目中负责什么？")

        self.assertFalse(any(row["matched_section_intent"] for row in reranked))

    def test_select_results_deduplicates_semantic_groups_and_prefers_primary_evidence(self) -> None:
        rows = [
            {
                "chunk_id": "summary-secondary",
                "semantic_group_id": "summary-group",
                "retrieval_priority": "secondary",
                "visibility": "public",
                "score": 0.99,
            },
            {
                "chunk_id": "project-rag",
                "semantic_group_id": "project-rag",
                "retrieval_priority": "primary",
                "visibility": "public",
                "score": 0.80,
            },
            {
                "chunk_id": "project-rag-continuation",
                "semantic_group_id": "project-rag",
                "retrieval_priority": "primary",
                "visibility": "public",
                "score": 0.79,
            },
            {
                "chunk_id": "project-qa",
                "semantic_group_id": "project-qa",
                "retrieval_priority": "primary",
                "visibility": "public",
                "score": 0.75,
            },
        ]

        selected = select_results(rows, RetrievalSettings(top_k=3))

        self.assertEqual([item["chunk_id"] for item in selected], ["project-rag", "project-qa", "summary-secondary"])
    def test_select_results_expands_child_match_to_parent_evidence(self) -> None:
        rows = [
            {
                "chunk_id": "child-1",
                "parent_chunk_id": "parent-1",
                "raw_body": "Focused MongoDB vector child.",
                "parent_body": "Complete Local RAG project evidence and outcomes.",
                "semantic_group_id": "rag-project",
                "score": 0.91,
                "visibility": "private",
            },
            {
                "chunk_id": "child-2",
                "parent_chunk_id": "parent-1",
                "raw_body": "Focused Ollama child.",
                "parent_body": "Complete Local RAG project evidence and outcomes.",
                "semantic_group_id": "rag-project",
                "score": 0.84,
                "visibility": "private",
            },
        ]

        selected = select_results(rows, RetrievalSettings(top_k=5, scope="all"))

        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["body"], rows[0]["parent_body"])
        self.assertEqual(selected[0]["matched_child_body"], rows[0]["raw_body"])
        self.assertTrue(selected[0]["parent_expanded"])

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

    def test_space_selection_filters_out_other_knowledge_spaces(self) -> None:
        rows = [
            {"chunk_id": "portfolio", "space_id": "portfolio", "score": 0.8},
            {"chunk_id": "rag", "space_id": "rag-learning", "score": 0.9},
        ]

        selected = select_results(
            rows,
            RetrievalSettings(scope="all", space_ids=("portfolio",)),
        )

        self.assertEqual([row["chunk_id"] for row in selected], ["portfolio"])

    def test_multi_space_results_reserve_one_candidate_per_space(self) -> None:
        rows = [
            {"chunk_id": "p1", "space_id": "portfolio", "score": 0.99},
            {"chunk_id": "p2", "space_id": "portfolio", "score": 0.98},
            {"chunk_id": "p3", "space_id": "portfolio", "score": 0.97},
            {"chunk_id": "rag", "space_id": "rag-learning", "score": 0.65},
        ]

        selected = select_results(
            rows,
            RetrievalSettings(
                top_k=2,
                scope="all",
                space_ids=("portfolio", "rag-learning"),
            ),
        )

        self.assertEqual({row["space_id"] for row in selected}, {"portfolio", "rag-learning"})

    def test_space_selection_accepts_at_most_five_unique_spaces(self) -> None:
        with self.assertRaises(ValueError):
            RetrievalSettings(space_ids=tuple(f"space-{index}" for index in range(6)))


if __name__ == "__main__":
    unittest.main()
