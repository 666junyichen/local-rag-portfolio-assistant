from __future__ import annotations

import json
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np

from src.document_processing import (
    ChunkConfig,
    chunk_metrics,
    detect_pii,
    normalize_document,
    parse_uploaded_file,
    persist_and_parse_upload,
    rank_preview_chunks,
    recommend_chunk_config,
    split_document,
)


class DocumentProcessingTests(unittest.TestCase):
    def test_recommends_resume_chunking_from_docx_metadata(self) -> None:
        document = normalize_document(
            {
                "title": "Master Resume",
                "body": "Resume evidence. " * 500,
                "metadata": {"file_type": "docx", "source": "Master Resume.docx"},
            }
        )
        config = recommend_chunk_config(document)
        self.assertEqual(config, ChunkConfig("recursive", 600, 60))

    def test_recommends_markdown_and_short_json_chunking(self) -> None:
        markdown = normalize_document(
            {"title": "README", "body": "# Project\n" + "Evidence. " * 200, "metadata": {"file_type": "md"}}
        )
        short_json = normalize_document(
            {"title": "Summary", "body": "Short public summary.", "metadata": {"file_type": "json"}}
        )
        self.assertEqual(recommend_chunk_config(markdown), ChunkConfig("markdown", 800, 80))
        self.assertEqual(recommend_chunk_config(short_json), ChunkConfig("recursive", 800, 0))

    def test_csv_rows_never_add_chunk_overlap(self) -> None:
        document = normalize_document(
            {"title": "Experience rows", "body": "Structured row. " * 100, "metadata": {"file_type": "csv"}}
        )
        self.assertEqual(recommend_chunk_config(document), ChunkConfig("recursive", 800, 0))

    def test_chunk_metrics_flag_fragmented_content(self) -> None:
        metrics = chunk_metrics([{"body": "a" * 40}, {"body": "b" * 400}])
        self.assertEqual(metrics["count"], 2)
        self.assertEqual(metrics["min_length"], 40)
        self.assertEqual(metrics["max_length"], 400)
        self.assertEqual(metrics["too_short_ratio"], 0.5)
        self.assertTrue(metrics["warnings"])

    def test_detect_pii_finds_email_and_phone(self) -> None:
        findings = detect_pii("Email me at person@example.com or call 13776680803.")
        self.assertEqual({item["type"] for item in findings}, {"email", "phone"})

    def test_preview_retrieval_ranks_the_most_similar_chunk_first(self) -> None:
        class FakeModel:
            def encode_query(self, values):
                return np.array([[1.0, 0.0] for _ in values])

            def encode_document(self, values):
                return np.array([[1.0, 0.0] if "MongoDB" in value else [0.0, 1.0] for value in values])

        chunks = [{"body": "Frontend UI"}, {"body": "MongoDB vector search"}]
        results = rank_preview_chunks(chunks, "database experience", FakeModel(), top_k=2)
        self.assertEqual(results[0]["body"], "MongoDB vector search")
        self.assertEqual(results[0]["score"], 1.0)

    def test_persist_and_parse_upload_keeps_a_stable_docx_result(self) -> None:
        document_xml = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
          <w:body><w:p><w:r><w:t>Portfolio evidence from DOCX.</w:t></w:r></w:p></w:body>
        </w:document>'''
        with tempfile.TemporaryDirectory() as temp_dir:
            uploads_dir = Path(temp_dir)
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as archive:
                archive.writestr("word/document.xml", document_xml)

            first = persist_and_parse_upload("resume.docx", buffer.getvalue(), uploads_dir)
            second = persist_and_parse_upload("resume.docx", buffer.getvalue(), uploads_dir)

        self.assertEqual(first, second)
        self.assertEqual(first[0]["body"], "Portfolio evidence from DOCX.")

    def test_normalize_document_adds_stable_identity_and_public_visibility(self) -> None:
        raw = {
            "title": "RAG Assistant",
            "body": "A grounded portfolio assistant built with MongoDB Vector Search.",
            "metadata": {"category": "project", "language": "en"},
        }

        first = normalize_document(raw, default_visibility="public")
        second = normalize_document(raw, default_visibility="public")

        self.assertEqual(first["doc_id"], second["doc_id"])
        self.assertEqual(first["content_hash"], second["content_hash"])
        self.assertEqual(first["visibility"], "public")
        self.assertEqual(first["metadata"]["visibility"], "public")

    def test_normalize_document_defaults_new_uploads_to_private(self) -> None:
        doc = normalize_document({"title": "Draft", "body": "Private draft body."})
        self.assertEqual(doc["visibility"], "private")

    def test_chunk_config_rejects_excessive_overlap(self) -> None:
        with self.assertRaisesRegex(ValueError, "25%"):
            ChunkConfig(strategy="recursive", chunk_size=400, chunk_overlap=120)

    def test_split_document_preserves_identity_and_adds_chunk_ids(self) -> None:
        doc = normalize_document(
            {
                "title": "Long project",
                "body": "First paragraph. " * 40 + "\n\n" + "Second paragraph. " * 40,
                "metadata": {"category": "project", "language": "en"},
            },
            default_visibility="public",
        )

        chunks = split_document(doc, ChunkConfig(chunk_size=200, chunk_overlap=40))

        self.assertGreater(len(chunks), 1)
        self.assertEqual(chunks[0]["doc_id"], doc["doc_id"])
        self.assertEqual(chunks[0]["chunk_index"], 0)
        self.assertNotEqual(chunks[0]["chunk_id"], chunks[1]["chunk_id"])
        self.assertEqual(chunks[0]["visibility"], "public")

    def test_parse_json_and_csv_uploads(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            json_path = root / "docs.json"
            json_path.write_text(
                json.dumps([{"title": "One", "body": "First body long enough for ingestion."}]),
                encoding="utf-8",
            )
            csv_path = root / "docs.csv"
            csv_path.write_text("title,body\nTwo,Second body long enough for ingestion.\n", encoding="utf-8")

            json_docs = parse_uploaded_file(json_path)
            csv_docs = parse_uploaded_file(csv_path)

        self.assertEqual(json_docs[0]["title"], "One")
        self.assertEqual(csv_docs[0]["title"], "Two")
        self.assertEqual(csv_docs[0]["visibility"], "private")


if __name__ == "__main__":
    unittest.main()
