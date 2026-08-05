from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.document_processing import ChunkConfig, count_tokens
from src.ingestion import (
    build_chunk_records,
    ensure_local_catalog,
    load_knowledge_documents,
    select_private_documents,
)
from src.local_catalog import stable_document_id


class IngestionTests(unittest.TestCase):
    def test_private_project_sources_are_curated_per_project(self) -> None:
        rows = [
            {
                "title": f"Project file {index}",
                "body": f"Useful project evidence {index} with enough text.",
                "source": "project_activity_root",
                "relative_path": f"demo-project/{'README.md' if index == 5 else f'src/file{index}.py'}",
            }
            for index in range(6)
        ]
        rows.append({
            "title": "Master resume",
            "body": "Private resume evidence that must remain available.",
            "source": "resume_root",
            "relative_path": "master/resume.docx",
        })

        selected = select_private_documents(rows, per_project_limit=2)

        self.assertEqual(len(selected), 3)
        self.assertTrue(any(row["title"] == "Master resume" for row in selected))
        self.assertTrue(any("README" in row["relative_path"] for row in selected))

    def test_build_chunks_honors_document_chunking_metadata(self) -> None:
        document = {
            "title": "Resume",
            "body": "Project evidence and technical result. " * 80,
            "visibility": "private",
            "metadata": {
                "chunking": {"strategy": "recursive", "chunk_size": 300, "chunk_overlap": 30, "unit": "tokens"}
            },
        }
        chunks = build_chunk_records([document])
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(count_tokens(chunk["body"]) <= 300 for chunk in chunks))
        self.assertTrue(all(chunk["chunk_unit"] == "tokens" for chunk in chunks))

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

    def test_catalog_migration_preserves_all_rows_and_only_activates_curated_subset(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            (data_dir / "portfolio_docs.json").write_text("[]", encoding="utf-8")
            private_rows = [
                {"source": "resume_root", "relative_path": "master/resume.docx", "title": "Resume", "body": "Resume evidence."},
                {"source": "project_activity_root", "relative_path": "demo/README.md", "title": "Demo", "body": "Project evidence."},
                {"source": "project_activity_root", "relative_path": "demo/notes.txt", "title": "Notes", "body": "Extra notes."},
            ]
            (data_dir / "local_private_docs.json").write_text(json.dumps(private_rows), encoding="utf-8")
            catalog = ensure_local_catalog(data_dir, per_project_limit=1, resume_limit=1)
            self.assertEqual(catalog.count(), 3)
            self.assertEqual(catalog.count({"status": "active"}), 2)
            self.assertEqual(catalog.count({"status": "discovered"}), 1)

    def test_load_knowledge_documents_prefers_active_catalog_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            (data_dir / "portfolio_docs.json").write_text(
                json.dumps([{"title": "Public", "body": "Public portfolio evidence."}]), encoding="utf-8"
            )
            private_rows = [
                {"source": "resume_root", "relative_path": "a.docx", "title": "A", "body": "Active private evidence."},
                {"source": "resume_root", "relative_path": "b.docx", "title": "B", "body": "Excluded private evidence."},
            ]
            (data_dir / "local_private_docs.json").write_text(json.dumps(private_rows), encoding="utf-8")
            catalog = ensure_local_catalog(data_dir, per_project_limit=0, resume_limit=2)
            catalog.set_status([stable_document_id(private_rows[1])], "excluded")
            documents = load_knowledge_documents(data_dir, include_private=True)
            self.assertEqual(len(documents), 2)
            self.assertEqual(sum(item["visibility"] == "private" for item in documents), 1)


if __name__ == "__main__":
    unittest.main()
