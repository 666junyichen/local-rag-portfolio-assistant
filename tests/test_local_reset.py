from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.local_catalog import LocalCatalog, stable_document_id
from src.local_reset import (
    RESET_CONFIRMATION,
    build_local_reset_preview,
    perform_local_reset,
)


class FakeCollection:
    def __init__(self, rows: list[dict]):
        self.rows = list(rows)

    def count_documents(self, _filter: dict) -> int:
        return len(self.rows)

    def find(self, _filter: dict, projection: dict | None = None):
        if not projection:
            return list(self.rows)
        return [
            {key: value for key, value in row.items() if key != "embedding"}
            for row in self.rows
        ]

    def delete_many(self, _filter: dict):
        deleted = len(self.rows)
        self.rows.clear()
        return type("DeleteResult", (), {"deleted_count": deleted})()


class LocalResetTests(unittest.TestCase):
    def test_reset_requires_exact_confirmation_and_creates_restore_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            data_dir.mkdir()
            catalog = LocalCatalog(data_dir / "local_catalog.sqlite3")
            row = {
                "source": "manual_upload",
                "relative_path": "resume.docx",
                "title": "Resume",
                "body": "Manual evidence.",
            }
            catalog.upsert_documents([row], active_ids={stable_document_id(row)})
            (data_dir / "local_eval_questions.json").write_text("[]", encoding="utf-8")
            uploads = data_dir / "local_uploads"
            uploads.mkdir()
            (uploads / "internal-copy.txt").write_text("copy", encoding="utf-8")
            chunks = FakeCollection([{"chunk_id": "c1", "embedding": [1, 2]}])
            history = FakeCollection([{"role": "user", "content": "hello"}])

            preview = build_local_reset_preview(
                root=root,
                catalog=catalog,
                chunks=chunks,
                history=history,
            )
            self.assertEqual(preview["documents"], 1)
            self.assertEqual(preview["spaces"], 1)
            self.assertEqual(preview["duplicate_groups"], 0)
            self.assertEqual(preview["version_members"], 0)

            with self.assertRaises(ValueError):
                perform_local_reset(
                    root=root,
                    catalog=catalog,
                    chunks=chunks,
                    history=history,
                    confirmation="wrong",
                )

            result = perform_local_reset(
                root=root,
                catalog=catalog,
                chunks=chunks,
                history=history,
                confirmation=RESET_CONFIRMATION,
            )

            backup = Path(result["backup_dir"])
            self.assertTrue((backup / "local_catalog.sqlite3").exists())
            self.assertEqual(json.loads((backup / "chat_history.json").read_text(encoding="utf-8"))[0]["content"], "hello")
            self.assertEqual(catalog.count(), 0)
            self.assertEqual(chunks.rows, [])
            self.assertEqual(history.rows, [])
            self.assertFalse((data_dir / "local_eval_questions.json").exists())
            self.assertFalse((uploads / "internal-copy.txt").exists())


if __name__ == "__main__":
    unittest.main()
