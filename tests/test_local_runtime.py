from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.local_status import collection_status
from src.local_runtime import check_ollama, check_search_index, run_command_streaming
from src.portfolio_rag import Settings, get_collections, load_settings, wait_for_index


class _Response:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class LocalRuntimeTests(unittest.TestCase):
    def test_stream_command_forwards_each_output_line(self) -> None:
        class Process:
            stdout = iter(["Loading model\n", "Embedding 27 documents\n"])

            def wait(self):
                return 0

        lines: list[str] = []
        exit_code = run_command_streaming(
            ["python", "ingest.py"],
            Path("."),
            lines.append,
            popen_factory=lambda *args, **kwargs: Process(),
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(lines, ["Loading model", "Embedding 27 documents"])

    @patch("src.portfolio_rag.time.sleep")
    def test_wait_for_index_reports_status_changes(self, _sleep) -> None:
        class Collection:
            statuses = iter(["PENDING", "READY"])

            def list_search_indexes(self, name):
                return iter([{"status": next(self.statuses)}])

        messages: list[str] = []
        wait_for_index(Collection(), "vector_index", timeout=10, progress=messages.append)

        self.assertEqual(messages, ["Vector index status: PENDING", "Vector index status: READY"])

    @patch("src.portfolio_rag.MongoClient")
    def test_mongodb_connection_uses_a_short_local_timeout(self, mongo_client) -> None:
        client = mongo_client.return_value
        client.__getitem__.return_value.__getitem__.side_effect = ["knowledge", "history"]

        get_collections(Settings("mongodb://localhost:62262", "http://localhost:11434", "qwen2.5:3b"))

        mongo_client.assert_called_once_with(
            "mongodb://localhost:62262",
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
        )

    def test_collection_status_reports_document_count_and_index_state(self) -> None:
        class Collection:
            def count_documents(self, query):
                self.query = query
                return 27

            def list_search_indexes(self, name):
                self.index_name = name
                return iter([{"status": "READY"}])

        collection = Collection()

        self.assertEqual(collection_status(collection, "vector_index"), "27|READY")
        self.assertEqual(collection.query, {})
        self.assertEqual(collection.index_name, "vector_index")

    def test_search_index_status_is_reported_independently(self) -> None:
        class Collection:
            def list_search_indexes(self, name):
                return iter([{"status": "READY"}])

        status = check_search_index(Collection(), "vector_index", "Vector index")

        self.assertTrue(status.available)
        self.assertEqual(status.detail, "Vector index: READY")

    def test_missing_search_index_has_a_specific_diagnostic(self) -> None:
        class Collection:
            def list_search_indexes(self, name):
                return iter([])

        status = check_search_index(Collection(), "text_index", "BM25 index")

        self.assertFalse(status.available)
        self.assertEqual(status.detail, "BM25 index: MISSING")

    def test_local_settings_do_not_fall_back_to_cloud_mongodb_uri(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text("MONGODB_URI=mongodb+srv://cloud.example\n", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ValueError, "LOCAL_MONGODB_URI"):
                    load_settings(env_path)

    def test_project_env_overrides_stale_local_process_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "LOCAL_MONGODB_URI=mongodb://localhost:62262/?directConnection=true\n"
                "OLLAMA_BASE_URL=http://localhost:11434\n"
                "OLLAMA_MODEL=qwen2.5:3b\n",
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {
                    "LOCAL_MONGODB_URI": "",
                    "OLLAMA_BASE_URL": "http://stale-host:11434",
                    "OLLAMA_MODEL": "stale-model",
                },
                clear=True,
            ):
                settings = load_settings(env_path)

        self.assertEqual(
            settings.mongodb_uri,
            "mongodb://localhost:62262/?directConnection=true",
        )
        self.assertEqual(settings.ollama_base_url, "http://localhost:11434")
        self.assertEqual(settings.ollama_model, "qwen2.5:3b")

    def test_ollama_check_reports_required_model(self) -> None:
        def opener(request, timeout):
            self.assertEqual(request.full_url, "http://localhost:11434/api/tags")
            self.assertEqual(timeout, 3)
            return _Response({"models": [{"name": "qwen2.5:3b"}]})

        status = check_ollama("http://localhost:11434", "qwen2.5:3b", opener=opener)

        self.assertTrue(status.available)
        self.assertIn("qwen2.5:3b", status.detail)

    def test_ollama_check_reports_missing_model(self) -> None:
        status = check_ollama(
            "http://localhost:11434",
            "qwen2.5:3b",
            opener=lambda request, timeout: _Response({"models": []}),
        )

        self.assertFalse(status.available)
        self.assertIn("not installed", status.detail)

    def test_streamlit_app_does_not_use_invalid_checkmark_icon(self) -> None:
        app_source = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
        self.assertNotIn('icon="✓"', app_source)

    def test_streamlit_app_exposes_reload_and_split_runtime_statuses(self) -> None:
        app_source = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")

        self.assertIn("Reload local configuration", app_source)
        self.assertIn("st.cache_resource.clear()", app_source)
        self.assertIn("Phase A feature version", app_source)
        self.assertIn("Streamlit UI", app_source)
        self.assertIn("Vector index", app_source)
        self.assertIn("BM25 index", app_source)
        self.assertNotIn("MONGODB_URI=", app_source)
        self.assertNotIn("GEMINI_API_KEY=", app_source)

    def test_start_script_guards_against_stale_streamlit_and_runs_ui_preflight(self) -> None:
        script = (
            Path(__file__).resolve().parents[1] / "scripts" / "start-local.ps1"
        ).read_text(encoding="utf-8")

        self.assertIn("Get-NetTCPConnection -LocalPort 8505", script)
        self.assertIn("scripts\\check_streamlit_pages.py", script)
        self.assertIn("git branch --show-current", script)
        self.assertIn("git rev-parse --short HEAD", script)
        self.assertIn("--server.fileWatcherType none", script)

    def test_start_script_validates_rag_when_streamlit_is_already_healthy(self) -> None:
        script = (
            Path(__file__).resolve().parents[1] / "scripts" / "start-local.ps1"
        ).read_text(encoding="utf-8")

        self.assertIn("http://localhost:8505/_stcore/health", script)
        self.assertIn("Streamlit UI is already running", script)
        self.assertNotRegex(script, r"if \(\$StreamlitHealthy\).*?exit 0")
        self.assertIn("Local RAG dependencies and indexes are ready", script)


if __name__ == "__main__":
    unittest.main()
