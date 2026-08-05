from __future__ import annotations

import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

from src.portfolio_rag import Settings, try_load_reranker


ROOT = Path(__file__).resolve().parents[1]


class StreamlitContractTests(unittest.TestCase):
    def test_reranker_failure_returns_hybrid_fallback(self) -> None:
        settings = Settings(
            "mongodb://localhost:62262",
            "http://localhost:11434",
            "qwen2.5:3b",
        )

        def unavailable(_settings: Settings):
            raise OSError("model cache is unavailable")

        reranker, warning = try_load_reranker(settings, loader=unavailable)

        self.assertIsNone(reranker)
        self.assertIn("model cache is unavailable", warning or "")

    def test_all_streamlit_pages_render_without_uncaught_exceptions(self) -> None:
        pages = (
            ROOT / "app.py",
            ROOT / "pages" / "1_Knowledge_Studio.py",
            ROOT / "pages" / "2_Retrieval_Lab.py",
        )

        for page in pages:
            with self.subTest(page=page.name):
                app = AppTest.from_file(str(page), default_timeout=60).run()
                self.assertEqual(list(app.exception), [])

    def test_retrieval_lab_exposes_all_retrieval_modes(self) -> None:
        app = AppTest.from_file(
            str(ROOT / "pages" / "2_Retrieval_Lab.py"),
            default_timeout=60,
        ).run()

        mode_select = next(item for item in app.selectbox if item.label == "Retrieval mode")
        self.assertEqual(
            list(mode_select.options),
            ["baseline", "hybrid", "hybrid-rerank"],
        )


if __name__ == "__main__":
    unittest.main()
