from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime
from pathlib import Path
from urllib.parse import unquote


MEMORY_ROOT = Path("docs/project-memory")
REQUIRED_FILES = (
    Path("AGENTS.md"),
    Path("README.md"),
    MEMORY_ROOT / "README.md",
    MEMORY_ROOT / "CURRENT_STATE.md",
    MEMORY_ROOT / "ARCHITECTURE.md",
    MEMORY_ROOT / "ROADMAP.md",
    MEMORY_ROOT / "KNOWN_ISSUES.md",
    MEMORY_ROOT / "DECISIONS.md",
    MEMORY_ROOT / "TESTING.md",
    MEMORY_ROOT / "RUNBOOK.md",
    MEMORY_ROOT / "DATA_PRIVACY.md",
    MEMORY_ROOT / "CHANGELOG.md",
    MEMORY_ROOT / "PRIVATE_NOTE_TEMPLATE.md",
    MEMORY_ROOT / "state.json",
    MEMORY_ROOT / "sessions/TEMPLATE.md",
    MEMORY_ROOT / "sessions/2026-08-07-project-memory-bootstrap.md",
)
REQUIRED_STATE_KEYS = {
    "schema_version",
    "active_branch",
    "active_phase",
    "tasks",
    "last_verified",
    "known_blockers",
    "next_action",
    "updated_at",
}
VALID_STATUSES = {"pending", "in_progress", "blocked", "completed"}
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*]\(([^)]+)\)")
SENSITIVE_PATTERNS = (
    re.compile(
        r"(?im)^\s*(?:export\s+)?[A-Z][A-Z0-9_]+\s*=\s*"
        r"(?!<|\.\.\.|example|placeholder|redacted|\$\{)\S+"
    ),
    re.compile(
        r"(?i)\b(?:api[_ -]?key|token|secret)\s*[:=]\s*"
        r"(?!<|\.\.\.|example|placeholder|redacted)\S+"
    ),
    re.compile(r"(?i)\b[A-Z]:[\\/]Users[\\/][^\\/\s]+[\\/]"),
)


def validate_repository(root: Path) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    errors.extend(_validate_required_files(root))
    state = _load_and_validate_state(root, errors)
    _validate_markdown_links(root, errors)
    _validate_current_state(root, state, errors)
    _validate_public_memory(root, errors)
    _validate_private_ignore(root, errors)
    _validate_readme_status_link(root, errors)
    return errors


def _validate_required_files(root: Path) -> list[str]:
    return [
        f"missing required file: {path.as_posix()}"
        for path in REQUIRED_FILES
        if not (root / path).is_file()
    ]


def _load_and_validate_state(root: Path, errors: list[str]) -> dict[str, object] | None:
    path = root / MEMORY_ROOT / "state.json"
    if not path.is_file():
        return None
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"invalid state.json: {exc}")
        return None
    if not isinstance(state, dict):
        errors.append("state.json must contain a JSON object")
        return None

    for key in sorted(REQUIRED_STATE_KEYS - state.keys()):
        errors.append(f"state.json missing required key: {key}")
    if state.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    for key in ("active_branch", "active_phase", "next_action"):
        if key in state and (not isinstance(state[key], str) or not state[key].strip()):
            errors.append(f"{key} must be a non-empty string")
    _validate_iso_date(state.get("last_verified"), "last_verified", errors)
    _validate_iso_datetime(state.get("updated_at"), errors)
    blockers = state.get("known_blockers")
    if not isinstance(blockers, list) or not all(isinstance(item, str) and item for item in blockers):
        errors.append("known_blockers must be a list of non-empty strings")
    _validate_tasks(state.get("tasks"), errors)
    return state


def _validate_iso_date(value: object, field: str, errors: list[str]) -> None:
    if not isinstance(value, str):
        errors.append(f"{field} must be an ISO date")
        return
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        errors.append(f"{field} must be an ISO date")
        return
    if parsed.isoformat() != value:
        errors.append(f"{field} must be an ISO date")


def _validate_iso_datetime(value: object, errors: list[str]) -> None:
    if not isinstance(value, str):
        errors.append("updated_at must be an ISO datetime with a timezone")
        return
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        errors.append("updated_at must be an ISO datetime with a timezone")
        return
    if parsed.tzinfo is None:
        errors.append("updated_at must be an ISO datetime with a timezone")


def _validate_tasks(value: object, errors: list[str]) -> None:
    if not isinstance(value, list) or not value:
        errors.append("tasks must be a non-empty list")
        return
    seen_ids: set[object] = set()
    for task in value:
        if not isinstance(task, dict):
            errors.append("each task must be an object")
            continue
        task_id = task.get("id")
        if not isinstance(task_id, int) or task_id < 0 or task_id in seen_ids:
            errors.append(f"invalid or duplicate task id: {task_id!r}")
        seen_ids.add(task_id)
        status = task.get("status")
        if status not in VALID_STATUSES:
            errors.append(f"invalid task status for task {task_id}: {status!r}")
        if not isinstance(task.get("title"), str) or not task["title"].strip():
            errors.append(f"task {task_id} title must be a non-empty string")
        for field in ("reviewed", "final_quality_approved"):
            if field not in task:
                errors.append(f"task {task_id} missing required field: {field}")
            elif not isinstance(task[field], bool):
                errors.append(f"task {task_id} {field} must be a boolean")
        evidence = task.get("test_evidence")
        if not isinstance(evidence, list):
            errors.append(f"task {task_id} test_evidence must be a list")
            continue
        if status == "completed" and not evidence:
            errors.append(f"completed task {task_id} has no test evidence")
        for item in evidence:
            if not isinstance(item, dict) or not all(item.get(key) for key in ("command", "result", "verified_at")):
                errors.append(f"task {task_id} has invalid test evidence")
                continue
            _validate_iso_date(item["verified_at"], f"task {task_id} evidence verified_at", errors)


def _validate_markdown_links(root: Path, errors: list[str]) -> None:
    candidates = [root / "README.md", root / "AGENTS.md"]
    memory = root / MEMORY_ROOT
    if memory.is_dir():
        candidates.extend(memory.rglob("*.md"))
    for path in candidates:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for raw_target in MARKDOWN_LINK.findall(text):
            target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
            if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            target = unquote(target.split("#", 1)[0])
            resolved = (root / target.lstrip("/")) if target.startswith("/") else (path.parent / target)
            try:
                resolved.resolve().relative_to(root)
            except ValueError:
                errors.append(f"broken repository-relative link in {_relative(path, root)}: {raw_target}")
                continue
            if not resolved.exists():
                errors.append(f"broken repository-relative link in {_relative(path, root)}: {raw_target}")


def _validate_current_state(
    root: Path, state: dict[str, object] | None, errors: list[str]
) -> None:
    path = root / MEMORY_ROOT / "CURRENT_STATE.md"
    if state is None or not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    for key in ("active_branch", "active_phase", "last_verified", "next_action"):
        value = state.get(key)
        if isinstance(value, str) and value not in text:
            errors.append(f"CURRENT_STATE.md does not match {key}")
    tasks = state.get("tasks")
    if isinstance(tasks, list):
        current_rows = _current_task_rows(text)
        for task in tasks:
            if not isinstance(task, dict):
                continue
            task_id = task.get("id")
            row = current_rows.get(task_id)
            if row is None or row[0] != task.get("status"):
                errors.append(f"CURRENT_STATE.md does not match task {task_id} status")
                continue
            for index, field in ((1, "reviewed"), (2, "final_quality_approved")):
                value = task.get(field)
                if isinstance(value, bool) and row[index] != str(value).lower():
                    errors.append(f"CURRENT_STATE.md does not match task {task_id} {field}")
    blockers = state.get("known_blockers")
    if isinstance(blockers, list):
        for blocker in blockers:
            if isinstance(blocker, str) and blocker not in text:
                errors.append(f"CURRENT_STATE.md is missing blocker: {blocker}")


def _current_task_rows(text: str) -> dict[object, tuple[str, str, str]]:
    rows: dict[object, tuple[str, str, str]] = {}
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        columns = [column.strip() for column in line.split("|")[1:-1]]
        if len(columns) < 5:
            continue
        try:
            task_id = int(columns[0])
        except ValueError:
            continue
        rows[task_id] = (columns[1], columns[2], columns[3])
    return rows


def _validate_public_memory(root: Path, errors: list[str]) -> None:
    candidates = [root / "AGENTS.md"]
    memory = root / MEMORY_ROOT
    if memory.is_dir():
        candidates.extend(memory.rglob("*.md"))
        candidates.append(memory / "state.json")
    for path in candidates:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if any(pattern.search(text) for pattern in SENSITIVE_PATTERNS):
            errors.append(f"potential sensitive value in {_relative(path, root)}")


def _validate_private_ignore(root: Path, errors: list[str]) -> None:
    path = root / ".gitignore"
    if not path.is_file():
        errors.append(".project-memory/private/ must be ignored")
        return
    ignored = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        rule = raw_line.strip()
        if not rule or rule.startswith("#"):
            continue
        negated = rule.startswith("!")
        normalized = rule.lstrip("!").lstrip("/")
        if normalized == ".project-memory/private/":
            ignored = not negated
    if not ignored:
        errors.append(".project-memory/private/ must be ignored")


def _validate_readme_status_link(root: Path, errors: list[str]) -> None:
    path = root / "README.md"
    if path.is_file() and not re.search(
        r"\[Project Status]\(docs/project-memory/CURRENT_STATE\.md\)",
        path.read_text(encoding="utf-8"),
    ):
        errors.append("README.md must link Project Status to docs/project-memory/CURRENT_STATE.md")


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root).as_posix()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate persistent project memory.")
    parser.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    errors = validate_repository(args.root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Project memory validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
