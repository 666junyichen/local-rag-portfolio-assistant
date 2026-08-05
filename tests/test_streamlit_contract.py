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

    def test_knowledge_studio_uses_an_editable_clean_body_as_chunk_source(self) -> None:
        source = (ROOT / "pages" / "1_Knowledge_Studio.py").read_text(encoding="utf-8")

        self.assertIn('st.text_area("清洗正文"', source)
        self.assertIn("replace_document_body(document, clean_body)", source)
        self.assertNotIn('st.code(document["body"][:12000]', source)

    def test_knowledge_studio_syncs_raw_edits_and_rechunks_clean_edits(self) -> None:
        app = AppTest.from_file(
            str(ROOT / "pages" / "1_Knowledge_Studio.py"),
            default_timeout=90,
        ).run()
        app.file_uploader[0].upload(
            "editor-contract.txt",
            b"Original evidence only.",
            "text/plain",
        ).run()

        raw_editor = next(item for item in app.text_area if item.label == "解析正文")
        raw_editor.set_value("<p>Updated RAG evidence.</p>\n\nFinal version.").run()
        clean_editor = next(item for item in app.text_area if item.label == "清洗正文")

        self.assertEqual(clean_editor.value, "Updated RAG evidence.\n\nFinal version.")

        clean_editor.set_value("Manually redacted evidence.").run()
        self.assertTrue(
            any(
                "Chunk 1" in item.label and "tokens" in item.label and "27 chars" in item.label
                for item in app.expander
            )
        )
        self.assertTrue(any(item.value == "Manually redacted evidence." for item in app.markdown))
        self.assertEqual(list(app.exception), [])


if __name__ == "__main__":
    unittest.main()
