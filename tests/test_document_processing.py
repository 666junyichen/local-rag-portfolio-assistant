from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.document_processing import (
    ChunkConfig,
    normalize_document,
    parse_uploaded_file,
    split_document,
)


class DocumentProcessingTests(unittest.TestCase):
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
