from __future__ import annotations

import json
import shutil
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from src.local_catalog import LocalCatalog


RESET_CONFIRMATION = "RESET PORTFOLIO"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _collection_rows(collection: Any) -> list[dict[str, Any]]:
    return list(collection.find({}, {"embedding": 0}))


def build_local_reset_preview(
    *, root: Path, catalog: LocalCatalog, chunks: Any, history: Any
) -> dict[str, int]:
    root = Path(root)
    runtime_reports = list((root / "evals").glob("latest-report*.json"))
    catalog_stats = catalog.reset_statistics()
    return {
        **catalog_stats,
        "chunks": int(chunks.count_documents({})),
        "chat_messages": int(history.count_documents({})),
        "runtime_eval_files": int((root / "data" / "local_eval_questions.json").exists())
        + len(runtime_reports),
    }


def perform_local_reset(
    *,
    root: Path,
    catalog: LocalCatalog,
    chunks: Any,
    history: Any,
    confirmation: str,
) -> dict[str, Any]:
    if confirmation != RESET_CONFIRMATION:
        raise ValueError(f'Type "{RESET_CONFIRMATION}" to confirm the reset')

    root = Path(root)
    preview = build_local_reset_preview(
        root=root, catalog=catalog, chunks=chunks, history=history
    )
    backup_dir = root / ".project-memory" / "private" / "backups" / f"local-reset-{_utc_stamp()}"
    backup_dir.mkdir(parents=True, exist_ok=False)
    catalog.backup_to(backup_dir / "local_catalog.sqlite3")
    (backup_dir / "chat_history.json").write_text(
        json.dumps(_collection_rows(history), ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    (backup_dir / "manifest.json").write_text(
        json.dumps(
            {"created_at": datetime.now(timezone.utc).isoformat(), "preview": preview},
            indent=2,
        ),
        encoding="utf-8",
    )

    data_dir = root / "data"
    eval_file = data_dir / "local_eval_questions.json"
    if eval_file.exists():
        shutil.copy2(eval_file, backup_dir / eval_file.name)
        eval_file.unlink()
    for report in (root / "evals").glob("latest-report*.json"):
        shutil.copy2(report, backup_dir / report.name)
        report.unlink()

    uploads_dir = data_dir / "local_uploads"
    if uploads_dir.exists():
        shutil.copytree(uploads_dir, backup_dir / "local_uploads")
        shutil.rmtree(uploads_dir)
    uploads_dir.mkdir(parents=True, exist_ok=True)

    catalog_result = catalog.reset_for_manual_upload()
    chunks_deleted = int(chunks.delete_many({}).deleted_count)
    history_deleted = int(history.delete_many({}).deleted_count)
    return {
        "backup_dir": str(backup_dir),
        "preview": preview,
        **catalog_result,
        "chunks_deleted": chunks_deleted,
        "chat_messages_deleted": history_deleted,
    }
