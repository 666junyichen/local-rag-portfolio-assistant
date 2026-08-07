from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.local_catalog import LocalCatalog, stable_document_id
from src.processing_profiles import ProcessingProfile


class LocalCatalogTests(unittest.TestCase):
    def make_catalog(self, root: Path) -> LocalCatalog:
        return LocalCatalog(root / "catalog.sqlite3")

    def test_stable_id_uses_source_path_not_body(self) -> None:
        first = {"source": "resume_root", "relative_path": "master/resume.docx", "body": "old"}
        second = {"source": "resume_root", "relative_path": "master/resume.docx", "body": "new"}
        self.assertEqual(stable_document_id(first), stable_document_id(second))

    def test_migration_marks_selected_documents_active(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "private.json"
            rows = [
                {"source": "resume_root", "relative_path": "master/a.docx", "title": "A", "body": "A body"},
                {"source": "project_activity_root", "relative_path": "demo/src/a.py", "title": "B", "body": "B body"},
            ]
            source.write_text(json.dumps(rows), encoding="utf-8")
            catalog = self.make_catalog(root)
            catalog.migrate_json(source, active_ids={stable_document_id(rows[0])})
            self.assertEqual(catalog.count({"status": "active"}), 1)
            self.assertEqual(catalog.count({"status": "discovered"}), 1)

    def test_excluded_document_stays_excluded_after_rescan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            catalog = self.make_catalog(Path(temp_dir))
            row = {
                "source": "resume_root",
                "relative_path": "master/resume.docx",
                "title": "Resume",
                "body": "First version",
            }
            doc_id = stable_document_id(row)
            catalog.upsert_documents([row], active_ids={doc_id})
            catalog.set_status([doc_id], "excluded")
            catalog.upsert_documents([{**row, "body": "Updated version"}], active_ids={doc_id})
            self.assertEqual(catalog.get(doc_id)["status"], "excluded")

    def test_query_filters_searches_and_paginates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            catalog = self.make_catalog(Path(temp_dir))
            rows = [
                {
                    "source": "project_activity_root",
                    "relative_path": f"project-{index}/README.md",
                    "title": f"Project {index}",
                    "body": f"MongoDB evidence {index}",
                }
                for index in range(4)
            ]
            catalog.upsert_documents(rows, active_ids={stable_document_id(row) for row in rows})
            page = catalog.query(search="MongoDB", filters={"status": "active"}, page=2, page_size=2)
            self.assertEqual(page["total"], 4)
            self.assertEqual(len(page["items"]), 2)

    def test_summary_override_is_used_for_active_documents(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            catalog = self.make_catalog(Path(temp_dir))
            row = {
                "source": "resume_root",
                "relative_path": "master/resume.docx",
                "title": "Resume",
                "body": "Long extracted resume body.",
            }
            doc_id = stable_document_id(row)
            catalog.upsert_documents([row], active_ids={doc_id})
            catalog.update_summary(doc_id, "Curated RAG summary.")
            docs = catalog.active_documents()
            self.assertEqual(docs[0]["body"], "Curated RAG summary.")

    def test_exact_duplicate_groups_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            catalog = self.make_catalog(Path(temp_dir))
            rows = [
                {"source": "resume_root", "relative_path": "a.docx", "title": "A", "body": "same body"},
                {"source": "resume_root", "relative_path": "b.docx", "title": "B", "body": "same body"},
            ]
            catalog.upsert_documents(rows)
            groups = catalog.exact_duplicate_groups()
            self.assertEqual(len(groups), 1)
            self.assertEqual(groups[0]["count"], 2)

    def test_version_detection_recommends_latest_without_excluding_old_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            catalog = self.make_catalog(Path(temp_dir))
            rows = [
                {
                    "source": "resume_root",
                    "relative_path": "master/resume-v1.docx",
                    "title": "Resume v1",
                    "body": "Profile education skills project experience old version.",
                    "modified_at": "2026-01-01T00:00:00+00:00",
                },
                {
                    "source": "resume_root",
                    "relative_path": "master/resume-v2.docx",
                    "title": "Resume v2",
                    "body": "Profile education skills project experience newest version.",
                    "modified_at": "2026-07-01T00:00:00+00:00",
                },
            ]
            ids = {stable_document_id(row) for row in rows}
            catalog.upsert_documents(rows, active_ids=ids)
            groups = catalog.detect_version_groups(similarity_threshold=0.6)
            self.assertEqual(len(groups), 1)
            latest = catalog.get(stable_document_id(rows[1]))
            old = catalog.get(stable_document_id(rows[0]))
            self.assertTrue(latest["is_latest"])
            self.assertFalse(old["is_latest"])
            self.assertEqual(old["status"], "active")

    def test_version_detection_ignores_ordinary_project_documents(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            catalog = self.make_catalog(Path(temp_dir))
            rows = [
                {"source": "project_activity_root", "relative_path": "a/README.md", "title": "README v1", "body": "same project notes old"},
                {"source": "project_activity_root", "relative_path": "b/README.md", "title": "README v2", "body": "same project notes new"},
            ]
            catalog.upsert_documents(rows)
            self.assertEqual(catalog.detect_version_groups(similarity_threshold=0.1), [])

    def test_chunking_configuration_can_be_updated(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            catalog = self.make_catalog(Path(temp_dir))
            row = {"source": "resume_root", "relative_path": "resume.docx", "title": "Resume", "body": "Body"}
            doc_id = stable_document_id(row)
            catalog.upsert_documents([row])
            catalog.update_chunking(doc_id, "recursive", 600, 60, unit="tokens")
            saved = catalog.get(doc_id)
            self.assertEqual((saved["chunk_strategy"], saved["chunk_size"], saved["chunk_overlap"]), ("recursive", 600, 60))
            self.assertEqual(saved["chunk_unit"], "tokens")

    def test_processing_profile_migration_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            catalog = self.make_catalog(Path(temp_dir))
            row = {
                "source": "resume_root",
                "relative_path": "master/resume.docx",
                "title": "Master Resume",
                "body": "Education and project evidence.",
            }
            doc_id = stable_document_id(row)
            catalog.upsert_documents([row], active_ids={doc_id})

            first = catalog.migrate_processing_profiles()
            second = catalog.migrate_processing_profiles()
            saved = catalog.get(doc_id)

            self.assertEqual(first, 1)
            self.assertEqual(second, 0)
            self.assertEqual(saved["processing_profile"]["chunk_mode"], "resume_semantic")
            self.assertTrue(saved["processing_profile_hash"])

    def test_parent_child_processing_profile_can_be_updated(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            catalog = self.make_catalog(Path(temp_dir))
            row = {
                "source": "project_activity_root",
                "relative_path": "guide/readme.md",
                "title": "Guide",
                "body": "Long guide body.",
            }
            doc_id = stable_document_id(row)
            catalog.upsert_documents([row])

            updated = catalog.update_processing_profile(
                doc_id, ProcessingProfile.parent_child()
            )
            saved = catalog.get(doc_id)

            self.assertTrue(updated)
            self.assertEqual(saved["processing_profile"]["chunk_mode"], "parent_child")
            self.assertEqual(saved["chunk_size"], 180)
            self.assertEqual(saved["chunk_overlap"], 20)

    def test_image_record_is_marked_needs_ocr_and_not_activated(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            catalog = self.make_catalog(Path(temp_dir))
            row = {
                "source": "project_activity_root",
                "relative_path": "demo/screenshot.png",
                "title": "Screenshot",
                "body": "Image file screenshot.png. OCR not enabled.",
                "parse_status": "needs_ocr",
                "metadata": {"file_type": "png"},
            }
            doc_id = stable_document_id(row)
            catalog.upsert_documents([row], active_ids={doc_id})
            saved = catalog.get(doc_id)
            self.assertEqual(saved["status"], "needs_ocr")
            self.assertEqual(catalog.active_documents(), [])
