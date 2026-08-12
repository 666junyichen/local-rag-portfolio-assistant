from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch


def test_run_reset_uses_project_settings_and_closes_mongo_client(tmp_path: Path) -> None:
    from scripts import reset_local_knowledge

    settings = object()
    client = Mock()
    chunks = Mock()
    history = Mock()
    catalog = Mock()
    expected = {"documents_deleted": 2, "chunks_deleted": 4}

    with (
        patch.object(reset_local_knowledge, "load_settings", return_value=settings) as load,
        patch.object(
            reset_local_knowledge,
            "get_collections",
            return_value=(client, chunks, history),
        ) as collections,
        patch.object(reset_local_knowledge, "LocalCatalog", return_value=catalog) as catalog_type,
        patch.object(
            reset_local_knowledge,
            "perform_local_reset",
            return_value=expected,
        ) as perform,
    ):
        result = reset_local_knowledge.run_reset(
            root=tmp_path,
            confirmation="RESET PORTFOLIO",
        )

    assert result == expected
    load.assert_called_once_with(tmp_path / ".env")
    collections.assert_called_once_with(settings)
    catalog_type.assert_called_once_with(tmp_path / "data" / "local_catalog.sqlite3")
    perform.assert_called_once_with(
        root=tmp_path,
        catalog=catalog,
        chunks=chunks,
        history=history,
        confirmation="RESET PORTFOLIO",
    )
    client.close.assert_called_once_with()
