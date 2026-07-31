from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.knowledge_store import publish_document, remove_document, save_private_documents


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


if __name__ == "__main__":
    unittest.main()
