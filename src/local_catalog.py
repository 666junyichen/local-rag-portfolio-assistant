from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

from src.document_processing import normalize_document, recommend_chunk_config


CATALOG_STATUSES = {"discovered", "active", "excluded", "parse_error", "needs_ocr"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_document_id(document: dict[str, Any]) -> str:
    metadata = document.get("metadata") or {}
    source = str(document.get("source") or metadata.get("source_root") or "local")
    path = str(
        document.get("relative_path")
        or document.get("path")
        or metadata.get("source_path")
        or metadata.get("source")
        or document.get("title")
        or "untitled"
    )
    normalized_path = path.replace("/", "\\").strip().lower()
    canonical = f"{source}|{normalized_path}"
    return f"local_{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:24]}"


class LocalCatalog:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    doc_id TEXT PRIMARY KEY,
                    content_hash TEXT NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    visibility TEXT NOT NULL DEFAULT 'private',
                    status TEXT NOT NULL DEFAULT 'discovered',
                    source TEXT NOT NULL DEFAULT '',
                    source_path TEXT NOT NULL DEFAULT '',
                    relative_path TEXT NOT NULL DEFAULT '',
                    project TEXT NOT NULL DEFAULT '',
                    file_name TEXT NOT NULL DEFAULT '',
                    file_type TEXT NOT NULL DEFAULT '',
                    size_bytes INTEGER NOT NULL DEFAULT 0,
                    modified_at TEXT,
                    parse_status TEXT NOT NULL DEFAULT 'ready',
                    parse_message TEXT NOT NULL DEFAULT '',
                    language TEXT NOT NULL DEFAULT '',
                    version_group_id TEXT,
                    is_latest INTEGER NOT NULL DEFAULT 0,
                    chunk_strategy TEXT NOT NULL DEFAULT 'recursive',
                    chunk_size INTEGER NOT NULL DEFAULT 800,
                    chunk_overlap INTEGER NOT NULL DEFAULT 80,
                    chunk_unit TEXT NOT NULL DEFAULT 'characters',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
                CREATE INDEX IF NOT EXISTS idx_documents_source ON documents(source);
                CREATE INDEX IF NOT EXISTS idx_documents_file_type ON documents(file_type);
                CREATE INDEX IF NOT EXISTS idx_documents_project ON documents(project);
                CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(content_hash);
                """
            )
            columns = {row[1] for row in connection.execute("PRAGMA table_info(documents)").fetchall()}
            if "chunk_unit" not in columns:
                connection.execute(
                    "ALTER TABLE documents ADD COLUMN chunk_unit TEXT NOT NULL DEFAULT 'characters'"
                )

    def _record(self, raw: dict[str, Any], status: str) -> dict[str, Any]:
        normalized = normalize_document(raw, default_visibility="private")
        metadata = dict(normalized.get("metadata") or {})
        relative_path = str(raw.get("relative_path") or metadata.get("relative_path") or "")
        source_path = str(raw.get("path") or metadata.get("source_path") or "")
        source = str(raw.get("source") or metadata.get("source_root") or "manual_upload")
        file_name = str(metadata.get("source") or Path(source_path or relative_path).name)
        file_type = str(metadata.get("file_type") or Path(file_name or relative_path).suffix.lstrip(".")).lower()
        project = str(raw.get("project") or (relative_path.replace("/", "\\").split("\\", 1)[0] if relative_path else ""))
        path = Path(source_path) if source_path else None
        size_bytes = int(raw.get("size_bytes") or metadata.get("size_bytes") or 0)
        modified_at = raw.get("modified_at") or metadata.get("modified_at")
        if path and path.exists():
            stat = path.stat()
            size_bytes = size_bytes or stat.st_size
            modified_at = modified_at or datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()
        config = recommend_chunk_config(normalized)
        configured = metadata.get("chunking") or {}
        strategy = str(configured.get("strategy") or config.strategy)
        chunk_size = int(configured.get("chunk_size") or config.chunk_size)
        overlap = int(configured.get("chunk_overlap") if configured.get("chunk_overlap") is not None else config.chunk_overlap)
        unit = str(configured.get("unit") or config.unit)
        now = _utc_now()
        parse_status = str(raw.get("parse_status") or metadata.get("parse_status") or "ready")
        effective_status = parse_status if parse_status in {"parse_error", "needs_ocr"} else status
        return {
            "doc_id": stable_document_id(raw),
            "content_hash": normalized["content_hash"],
            "title": normalized["title"],
            "body": normalized["body"],
            "summary": str(raw.get("summary") or ""),
            "visibility": "private",
            "status": effective_status,
            "source": source,
            "source_path": source_path,
            "relative_path": relative_path,
            "project": project,
            "file_name": file_name,
            "file_type": file_type,
            "size_bytes": size_bytes,
            "modified_at": modified_at,
            "parse_status": parse_status,
            "parse_message": str(raw.get("parse_message") or metadata.get("parse_message") or ""),
            "language": str(metadata.get("language") or ""),
            "version_group_id": raw.get("version_group_id"),
            "is_latest": int(bool(raw.get("is_latest", False))),
            "chunk_strategy": strategy,
            "chunk_size": chunk_size,
            "chunk_overlap": overlap,
            "chunk_unit": unit,
            "metadata_json": json.dumps(metadata, ensure_ascii=False),
            "created_at": now,
            "updated_at": now,
        }

    def upsert_documents(self, rows: Iterable[dict[str, Any]], *, active_ids: set[str] | None = None) -> int:
        active_ids = active_ids or set()
        records = [self._record(raw, "active" if stable_document_id(raw) in active_ids else "discovered") for raw in rows]
        if not records:
            return 0
        columns = list(records[0])
        placeholders = ", ".join("?" for _ in columns)
        updates = ", ".join(
            f"{column}=excluded.{column}"
            for column in columns
            if column not in {"doc_id", "status", "created_at", "summary", "is_latest", "version_group_id"}
        )
        sql = (
            f"INSERT INTO documents ({', '.join(columns)}) VALUES ({placeholders}) "
            f"ON CONFLICT(doc_id) DO UPDATE SET {updates}"
        )
        with self._connect() as connection:
            connection.executemany(sql, [[record[column] for column in columns] for record in records])
        return len(records)

    def migrate_json(self, source: Path, *, active_ids: set[str] | None = None) -> int:
        payload = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"{source.name} must contain a JSON array")
        return self.upsert_documents(payload, active_ids=active_ids)

    def _row(self, row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        item = dict(row)
        item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
        item["is_latest"] = bool(item["is_latest"])
        return item

    def get(self, doc_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            return self._row(connection.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,)).fetchone())

    def _filter_sql(self, filters: dict[str, Any], search: str = "") -> tuple[str, list[Any]]:
        allowed = {"status", "source", "file_type", "project", "parse_status", "visibility"}
        conditions: list[str] = []
        values: list[Any] = []
        for key, value in filters.items():
            if key not in allowed or value in (None, "", "all"):
                continue
            conditions.append(f"{key} = ?")
            values.append(value)
        if search.strip():
            term = f"%{search.strip()}%"
            conditions.append("(title LIKE ? OR body LIKE ? OR summary LIKE ? OR source_path LIKE ? OR relative_path LIKE ?)")
            values.extend([term] * 5)
        return (" WHERE " + " AND ".join(conditions) if conditions else ""), values

    def count(self, filters: dict[str, Any] | None = None) -> int:
        clauses, values = self._filter_sql(filters or {})
        with self._connect() as connection:
            return int(connection.execute(f"SELECT COUNT(*) FROM documents{clauses}", values).fetchone()[0])

    def query(
        self,
        *,
        search: str = "",
        filters: dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        clauses, values = self._filter_sql(filters or {}, search)
        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        with self._connect() as connection:
            total = int(connection.execute(f"SELECT COUNT(*) FROM documents{clauses}", values).fetchone()[0])
            rows = connection.execute(
                f"SELECT * FROM documents{clauses} ORDER BY modified_at DESC, title ASC LIMIT ? OFFSET ?",
                [*values, page_size, (page - 1) * page_size],
            ).fetchall()
        return {"items": [self._row(row) for row in rows], "total": total, "page": page, "page_size": page_size}

    def set_status(self, doc_ids: Iterable[str], status: str) -> int:
        if status not in CATALOG_STATUSES:
            raise ValueError(f"Unsupported catalog status: {status}")
        ids = list(dict.fromkeys(doc_ids))
        with self._connect() as connection:
            cursor = connection.executemany(
                "UPDATE documents SET status = ?, updated_at = ? WHERE doc_id = ?",
                [(status, _utc_now(), doc_id) for doc_id in ids],
            )
        return cursor.rowcount

    def update_summary(self, doc_id: str, summary: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE documents SET summary = ?, updated_at = ? WHERE doc_id = ?",
                (summary.strip(), _utc_now(), doc_id),
            )
        return cursor.rowcount > 0

    def update_chunking(
        self,
        doc_id: str,
        strategy: str,
        chunk_size: int,
        overlap: int,
        *,
        unit: str = "characters",
    ) -> bool:
        if strategy not in {"recursive", "markdown", "paragraph"}:
            raise ValueError(f"Unsupported chunk strategy: {strategy}")
        if not 200 <= chunk_size <= 2000:
            raise ValueError("Chunk size must be between 200 and 2000")
        if overlap < 0 or overlap > chunk_size * 0.25:
            raise ValueError("Overlap must be between 0 and 25% of chunk size")
        if unit not in {"characters", "tokens"}:
            raise ValueError("Unit must be characters or tokens")
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE documents
                SET chunk_strategy = ?, chunk_size = ?, chunk_overlap = ?, chunk_unit = ?, updated_at = ?
                WHERE doc_id = ?
                """,
                (strategy, chunk_size, overlap, unit, _utc_now(), doc_id),
            )
        return cursor.rowcount > 0

    @staticmethod
    def _version_title(title: str) -> str:
        value = title.lower()
        value = re.sub(r"\b(v(?:ersion)?\s*)?\d+(?:\.\d+)*\b", " ", value)
        value = re.sub(r"\b(copy|final|latest|master|old|new|updated|中文|英文|cn|en)\b", " ", value)
        value = re.sub(r"[^\w\u4e00-\u9fff]+", " ", value)
        return " ".join(value.split())

    @staticmethod
    def _body_features(body: str) -> set[str]:
        normalized = re.sub(r"\s+", " ", body.lower()).strip()
        words = {token for token in re.findall(r"[\w\u4e00-\u9fff]+", normalized) if 2 <= len(token) <= 40}
        compact = re.sub(r"\s+", "", normalized)
        shingles = {compact[index : index + 12] for index in range(0, max(0, len(compact) - 11), 6)}
        return words | shingles

    def detect_version_groups(self, similarity_threshold: float = 0.78) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM documents
                WHERE source IN ('resume_root', 'manual_upload')
                ORDER BY modified_at DESC, updated_at DESC
                """
            ).fetchall()
        items = [self._row(row) for row in rows]
        title_keys = {
            item["doc_id"]: self._version_title(Path(item["file_name"] or item["title"]).stem)
            for item in items
        }
        body_features = {item["doc_id"]: self._body_features(item["body"][:20000]) for item in items}
        parent = {item["doc_id"]: item["doc_id"] for item in items}

        def find(doc_id: str) -> str:
            while parent[doc_id] != doc_id:
                parent[doc_id] = parent[parent[doc_id]]
                doc_id = parent[doc_id]
            return doc_id

        def union(first: str, second: str) -> None:
            first_root, second_root = find(first), find(second)
            if first_root != second_root:
                parent[second_root] = first_root

        for index, first in enumerate(items):
            first_title = title_keys[first["doc_id"]]
            for second in items[index + 1 :]:
                second_title = title_keys[second["doc_id"]]
                if first["content_hash"] == second["content_hash"]:
                    union(first["doc_id"], second["doc_id"])
                    continue
                title_score = SequenceMatcher(None, first_title, second_title).ratio()
                if not first_title or (first_title != second_title and title_score < 0.85):
                    continue
                first_features = body_features[first["doc_id"]]
                second_features = body_features[second["doc_id"]]
                union_size = len(first_features | second_features)
                body_score = len(first_features & second_features) / union_size if union_size else 0.0
                if body_score >= similarity_threshold:
                    union(first["doc_id"], second["doc_id"])

        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            grouped.setdefault(find(item["doc_id"]), []).append(item)

        groups: list[dict[str, Any]] = []
        with self._connect() as connection:
            connection.execute("UPDATE documents SET version_group_id = NULL, is_latest = 0")
            for members in grouped.values():
                if len(members) < 2:
                    continue
                group_id = "version_" + hashlib.sha256(
                    "|".join(sorted(item["doc_id"] for item in members)).encode("utf-8")
                ).hexdigest()[:16]
                latest = max(
                    members,
                    key=lambda item: (item.get("modified_at") or "", item.get("updated_at") or ""),
                )
                connection.executemany(
                    "UPDATE documents SET version_group_id = ?, is_latest = ? WHERE doc_id = ?",
                    [(group_id, int(item["doc_id"] == latest["doc_id"]), item["doc_id"]) for item in members],
                )
                groups.append(
                    {"group_id": group_id, "latest_doc_id": latest["doc_id"], "documents": members}
                )
        return groups

    def active_documents(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM documents WHERE status = 'active' ORDER BY title").fetchall()
        documents = []
        for row in rows:
            item = self._row(row)
            metadata = dict(item["metadata"])
            metadata.update(
                {
                    "source_path": item["source_path"],
                    "relative_path": item["relative_path"],
                    "file_type": item["file_type"],
                    "modified_at": item["modified_at"],
                    "chunking": {
                        "strategy": item["chunk_strategy"],
                        "chunk_size": item["chunk_size"],
                        "chunk_overlap": item["chunk_overlap"],
                        "unit": item["chunk_unit"],
                    },
                }
            )
            documents.append(
                {
                    "doc_id": item["doc_id"],
                    "title": item["title"],
                    "body": item["summary"] or item["body"],
                    "visibility": "private",
                    "content_hash": item["content_hash"],
                    "source": item["source"],
                    "relative_path": item["relative_path"],
                    "metadata": metadata,
                }
            )
        return documents

    def exact_duplicate_groups(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT content_hash, COUNT(*) AS count, GROUP_CONCAT(doc_id) AS doc_ids
                FROM documents GROUP BY content_hash HAVING COUNT(*) > 1 ORDER BY count DESC
                """
            ).fetchall()
        return [
            {"content_hash": row["content_hash"], "count": row["count"], "doc_ids": row["doc_ids"].split(",")}
            for row in rows
        ]
