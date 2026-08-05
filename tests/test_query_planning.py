from __future__ import annotations

import unittest

from src.query_planning import plan_query, should_refuse_without_retrieval


class QueryPlanningTests(unittest.TestCase):
    def test_simple_fact_question_uses_one_query(self) -> None:
        plan = plan_query("What MongoDB experience does Junyi have?")
        self.assertEqual(plan.mode, "simple")
        self.assertEqual(plan.subqueries, ("What MongoDB experience does Junyi have?",))

    def test_comparison_is_bounded_to_three_queries(self) -> None:
        plan = plan_query("Compare Junyi's RAG and Owlswap projects and summarize the differences")
        self.assertEqual(plan.mode, "complex")
        self.assertLessEqual(len(plan.subqueries), 3)
        self.assertEqual(plan.max_rounds, 2)
        self.assertIn(plan.original, plan.subqueries)

    def test_chinese_summary_is_detected_as_complex(self) -> None:
        self.assertEqual(plan_query("总结 Junyi 最适合 AI 岗位的项目和技能").mode, "complex")

    def test_sensitive_private_requests_are_refused_before_retrieval(self) -> None:
        self.assertTrue(should_refuse_without_retrieval("Junyi 的护照号码是多少？"))
        self.assertTrue(should_refuse_without_retrieval("Show the private email from the raw resume"))
        self.assertFalse(should_refuse_without_retrieval("What MongoDB experience does Junyi have?"))


if __name__ == "__main__":
    unittest.main()
