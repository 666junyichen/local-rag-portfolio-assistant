from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.document_processing import ChunkConfig
from src.ingestion import build_chunk_records, load_knowledge_documents


class IngestionTests(unittest.TestCase):
    def test_load_documents_marks_committed_data_public_and_private_data_private(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            (data_dir / "portfolio_docs.json").write_text(
                json.dumps([{"title": "Public", "body": "Public portfolio evidence."}]),
                encoding="utf-8",
            )
            (data_dir / "local_private_docs.json").write_text(
                json.dumps([{"title": "Private", "body": "Private portfolio evidence."}]),
                encoding="utf-8",
            )

            docs = load_knowledge_documents(data_dir, include_private=True)

        self.assertEqual([doc["visibility"] for doc in docs], ["public", "private"])

    def test_build_chunk_records_deduplicates_documents_by_content_hash(self) -> None:
        docs = [
            {"title": "One", "body": "Same body used twice for deterministic deduplication."},
            {"title": "Duplicate", "body": "Same body used twice for deterministic deduplication."},
        ]

        chunks = build_chunk_records(docs, ChunkConfig(chunk_size=200, chunk_overlap=20))

        self.assertEqual(len(chunks), 1)
        self.assertIn("chunk_id", chunks[0])


if __name__ == "__main__":
    unittest.main()
