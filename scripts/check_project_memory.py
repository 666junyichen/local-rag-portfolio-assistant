from __future__ import annotations

import argparse
import json
import re
import subprocess
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
)
HTTP_URL_PATTERN = re.compile(r"(?i)\bhttps?://[^\s<>()]+")
WINDOWS_DRIVE_PATH_PATTERN = re.compile(r"(?i)[A-Z]:[\\/]")
WINDOWS_UNC_PATH_PATTERN = re.compile(
    r"(?<![\\/])[\\/]{2}[^\\/\s]+[\\/][^\\/\s]+"
)
POSIX_USER_PATH_PATTERN = re.compile(
    r"(?i)/(?:Users|home)/[^/\s]+(?=/|\s|$)"
)
CURRENT_METADATA_FIELDS = {
    "Active branch": "active_branch",
    "Active phase": "active_phase",
    "Last verified": "last_verified",
    "Updated": "updated_at",
    "Next action": "next_action",
}


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


def _validate_iso_date(value: object, field: str, errors: list[str]) -> bool:
    if not isinstance(value, str):
        errors.append(f"{field} must be an ISO date")
        return False
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        errors.append(f"{field} must be an ISO date")
        return False
    if parsed.isoformat() != value:
        errors.append(f"{field} must be an ISO date")
        return False
    return True


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
        if type(task_id) is not int or task_id < 0:
            errors.append(f"invalid or duplicate task id: {task_id!r}")
        elif task_id in seen_ids:
            errors.append(f"invalid or duplicate task id: {task_id!r}")
        else:
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
        evidence_valid = bool(evidence)
        has_valid_passed_evidence = False
        if status == "completed" and not evidence:
            errors.append(f"completed task {task_id} has no test evidence")
        for item in evidence:
            if not isinstance(item, dict):
                errors.append(f"task {task_id} has invalid test evidence")
                evidence_valid = False
                continue
            item_valid = True
            for field in ("command", "result"):
                value = item.get(field)
                if not isinstance(value, str) or not value.strip():
                    errors.append(
                        f"task {task_id} evidence {field} must be a non-empty string"
                    )
                    item_valid = False
            outcome = item.get("outcome")
            if type(outcome) is not str or outcome not in {"passed", "failed"}:
                errors.append(
                    f"task {task_id} evidence outcome must be 'passed' or 'failed'"
                )
                item_valid = False
            if not _validate_iso_date(
                item.get("verified_at"), f"task {task_id} evidence verified_at", errors
            ):
                item_valid = False
            evidence_valid = evidence_valid and item_valid
            if item_valid and outcome == "passed":
                has_valid_passed_evidence = True
        reviewed = task.get("reviewed")
        approved = task.get("final_quality_approved")
        if reviewed is True and not evidence_valid:
            errors.append(
                f"task {task_id} reviewed=true requires non-empty valid test evidence"
            )
        if reviewed is True and not has_valid_passed_evidence:
            errors.append(
                f"task {task_id} reviewed=true requires passed test evidence"
            )
        if approved is True:
            if reviewed is not True:
                errors.append(
                    f"task {task_id} final_quality_approved requires reviewed=true"
                )
            if status != "completed":
                errors.append(
                    f"task {task_id} final_quality_approved requires status=completed"
                )
            if not evidence_valid:
                errors.append(
                    f"task {task_id} final_quality_approved requires non-empty valid test evidence"
                )
            if not has_valid_passed_evidence:
                errors.append(
                    f"task {task_id} final_quality_approved requires passed test evidence"
                )


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
    metadata = _current_metadata(text, errors)
    for key in CURRENT_METADATA_FIELDS.values():
        value = state.get(key)
        if isinstance(value, str) and metadata.get(key) != value:
            errors.append(f"CURRENT_STATE.md does not match {key}")
    tasks = state.get("tasks")
    if isinstance(tasks, list):
        current_rows = _current_task_rows(text, errors)
        state_task_ids = {
            task["id"]
            for task in tasks
            if isinstance(task, dict)
            and type(task.get("id")) is int
            and task["id"] >= 0
        }
        current_task_ids = set(current_rows)
        if current_task_ids != state_task_ids:
            missing = sorted(state_task_ids - current_task_ids)
            extra = sorted(current_task_ids - state_task_ids)
            errors.append(
                "CURRENT_STATE.md task IDs do not match state.json "
                f"(missing: {missing}; extra: {extra})"
            )
        for task in tasks:
            if not isinstance(task, dict):
                continue
            task_id = task.get("id")
            if type(task_id) is not int or task_id < 0:
                continue
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
        current_blockers = _current_section_bullets(text, "## Known Blockers", errors)
        if current_blockers != blockers:
            errors.append("CURRENT_STATE.md known blockers do not match state.json")


def _current_metadata(text: str, errors: list[str]) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for line in text.splitlines():
        if line.startswith("## "):
            break
        if not line.startswith("- ") or ":" not in line:
            continue
        label, raw_value = line[2:].split(":", 1)
        key = CURRENT_METADATA_FIELDS.get(label.strip())
        if key is None:
            continue
        if key in metadata:
            errors.append(f"CURRENT_STATE.md duplicate metadata field: {key}")
            continue
        value = raw_value.strip()
        if len(value) >= 2 and value.startswith("`") and value.endswith("`"):
            value = value[1:-1]
        metadata[key] = value
    for key in CURRENT_METADATA_FIELDS.values():
        if key not in metadata:
            errors.append(f"CURRENT_STATE.md missing metadata field: {key}")
    return metadata


def _current_section_bullets(
    text: str, heading: str, errors: list[str]
) -> list[str]:
    bullets: list[str] = []
    in_section = False
    found = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            if stripped == heading:
                if found:
                    errors.append(f"CURRENT_STATE.md duplicate section: {heading}")
                    continue
                found = True
                in_section = True
                continue
            if in_section:
                break
        if in_section and stripped.startswith("- "):
            bullets.append(stripped[2:].strip())
    if not found:
        errors.append(f"CURRENT_STATE.md missing section: {heading}")
    return bullets


def _current_task_rows(
    text: str, errors: list[str]
) -> dict[object, tuple[str, str, str]]:
    rows: dict[object, tuple[str, str, str]] = {}
    expected_header = (
        "task",
        "status",
        "reviewed",
        "final quality approved",
        "summary",
    )
    in_status = False
    in_task_table = False
    rows_started = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            if stripped == "## Status":
                in_status = True
                continue
            if in_status:
                break
        if not in_status:
            continue
        if not stripped.startswith("|"):
            if in_task_table and rows_started:
                break
            continue
        columns = [column.strip() for column in stripped.split("|")[1:-1]]
        if len(columns) < 5:
            continue
        if not in_task_table:
            if tuple(column.casefold() for column in columns[:5]) == expected_header:
                in_task_table = True
            continue
        if all(re.fullmatch(r":?-+:?", column) for column in columns[:5]):
            continue
        try:
            task_id = int(columns[0])
        except ValueError:
            continue
        rows_started = True
        if task_id in rows:
            errors.append(f"duplicate task row in CURRENT_STATE.md: {task_id}")
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
        non_http_text = HTTP_URL_PATTERN.sub("", text)
        if (
            any(pattern.search(text) for pattern in SENSITIVE_PATTERNS)
            or WINDOWS_DRIVE_PATH_PATTERN.search(non_http_text)
            or WINDOWS_UNC_PATH_PATTERN.search(non_http_text)
            or POSIX_USER_PATH_PATTERN.search(non_http_text)
        ):
            errors.append(f"potential sensitive value in {_relative(path, root)}")


def _validate_private_ignore(root: Path, errors: list[str]) -> None:
    probe = ".project-memory/private/note.md"
    command = [
        "git",
        "-c",
        f"safe.directory={root.resolve().as_posix()}",
        "-C",
        str(root),
        "check-ignore",
        "-v",
        "--no-index",
        probe,
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        errors.append(f"git check-ignore failed for {probe}: {exc}")
        return

    if completed.returncode == 0:
        return
    if completed.returncode == 1:
        errors.append(
            f".project-memory/private/ must be ignored; {probe} is trackable"
        )
        return

    detail = completed.stderr.strip() or completed.stdout.strip()
    if not detail:
        detail = f"exit code {completed.returncode}"
    errors.append(f"git check-ignore failed for {probe}: {detail}")


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
