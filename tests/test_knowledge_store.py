from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.knowledge_store import (
    archive_public_document,
    publish_document,
    remove_document,
    save_private_documents,
    update_public_document,
)


class KnowledgeStoreTests(unittest.TestCase):
    def test_publish_document_marks_it_public_and_prevents_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "portfolio_docs.json"
            path.write_text("[]", encoding="utf-8")
            draft = {"title": "Project", "body": "Evidence safe for a public portfolio."}

            first = publish_document(path, draft)
            second = publish_document(path, draft)
            saved = json.loads(path.read_text(encoding="utf-8"))

        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(saved[0]["visibility"], "public")
        self.assertEqual(len(saved), 1)

    def test_publish_document_replaces_existing_document_with_same_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "portfolio_docs.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "doc_id": "resume",
                            "title": "Resume",
                            "body": "Old public resume.",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            result = publish_document(
                path,
                {
                    "doc_id": "resume",
                    "title": "Resume",
                    "body": "Updated public resume with new evidence.",
                },
            )
            saved = json.loads(path.read_text(encoding="utf-8"))

        self.assertFalse(result["created"])
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["doc_id"], "resume")
        self.assertEqual(saved[0]["body"], "Updated public resume with new evidence.")

    def test_private_save_forces_private_visibility(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "local_private_docs.json"
            save_private_documents(path, [{"title": "Draft", "body": "Private resume draft."}])
            saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(saved[0]["visibility"], "private")

    def test_remove_document_uses_doc_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "portfolio_docs.json"
            path.write_text(
                json.dumps([{"doc_id": "keep", "title": "Keep", "body": "Keep body."}, {"doc_id": "drop", "title": "Drop", "body": "Drop body."}]),
                encoding="utf-8",
            )
            removed = remove_document(path, "drop", default_visibility="public")
            saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertTrue(removed)
        self.assertEqual([item["doc_id"] for item in saved], ["keep"])

    def test_archive_public_document_removes_public_record_and_keeps_local_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            public_path = root / "portfolio_docs.json"
            archive_path = root / "archive" / "public_docs.json"
            public_path.write_text(
                json.dumps([{"doc_id": "drop", "title": "Drop", "body": "Public body."}]),
                encoding="utf-8",
            )
            self.assertTrue(archive_public_document(public_path, archive_path, "drop"))
            self.assertEqual(json.loads(public_path.read_text(encoding="utf-8")), [])
            archived = json.loads(archive_path.read_text(encoding="utf-8"))
            self.assertEqual(archived[0]["doc_id"], "drop")
            self.assertIn("archived_at", archived[0])

    def test_update_public_document_preserves_id_and_changes_summary_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "portfolio_docs.json"
            path.write_text(
                json.dumps([{"doc_id": "project", "title": "Old", "body": "Old body.", "metadata": {"category": "project"}}]),
                encoding="utf-8",
            )
            updated = update_public_document(
                path,
                "project",
                {"title": "New", "body": "New body.", "url": "https://example.com", "category": "summary", "updated": "2026-08-04"},
            )
            self.assertTrue(updated)
            saved = json.loads(path.read_text(encoding="utf-8"))[0]
            self.assertEqual(saved["doc_id"], "project")
            self.assertEqual(saved["metadata"]["category"], "summary")


if __name__ == "__main__":
    unittest.main()
