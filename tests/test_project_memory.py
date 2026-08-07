from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.check_project_memory import validate_repository


REQUIRED_MARKDOWN = (
    "README.md",
    "CURRENT_STATE.md",
    "ARCHITECTURE.md",
    "ROADMAP.md",
    "KNOWN_ISSUES.md",
    "DECISIONS.md",
    "TESTING.md",
    "RUNBOOK.md",
    "DATA_PRIVACY.md",
    "CHANGELOG.md",
    "PRIVATE_NOTE_TEMPLATE.md",
    "sessions/TEMPLATE.md",
    "sessions/2026-08-07-project-memory-bootstrap.md",
)


def _state() -> dict[str, object]:
    return {
        "schema_version": 1,
        "active_branch": "feat/knowledge-studio-phase-a",
        "active_phase": "Phase A",
        "tasks": [
            {
                "id": 1,
                "title": "Profiles",
                "status": "completed",
                "reviewed": True,
                "final_quality_approved": True,
                "test_evidence": [
                    {
                        "command": "python -m pytest tests/test_processing_profiles.py -q",
                        "result": "passed",
                        "verified_at": "2026-08-07",
                    }
                ],
            },
            {
                "id": 2,
                "title": "Cleaning",
                "status": "in_progress",
                "reviewed": False,
                "final_quality_approved": False,
                "test_evidence": [],
            },
        ],
        "last_verified": "2026-08-07",
        "known_blockers": ["CJK-adjacent URLs"],
        "next_action": "Fix Task 2, then implement parent-child chunking.",
        "updated_at": "2026-08-07T12:00:00+10:00",
    }


def _current_state(state: dict[str, object]) -> str:
    tasks = state["tasks"]
    assert isinstance(tasks, list)
    rows = "\n".join(
        "| "
        f"{task['id']} | {task['status']} | "
        f"{str(task['reviewed']).lower()} | "
        f"{str(task['final_quality_approved']).lower()} | "
        f"{task['title']} |"
        for task in tasks
    )
    blockers = "\n".join(f"- {item}" for item in state["known_blockers"])
    return f"""# Current State

- Active branch: `{state['active_branch']}`
- Active phase: `{state['active_phase']}`
- Last verified: `{state['last_verified']}`
- Next action: {state['next_action']}

| Task | Status | Reviewed | Final quality approved | Summary |
|---|---|---|---|---|
{rows}

## Known Blockers

{blockers}
"""


def _write_valid_repository(root: Path) -> None:
    memory = root / "docs" / "project-memory"
    (memory / "sessions").mkdir(parents=True)
    (root / "scripts").mkdir()
    (root / "tests").mkdir()
    state = _state()

    (root / "AGENTS.md").write_text("# Protocol\n", encoding="utf-8")
    (root / "README.md").write_text(
        "# Project\n\n[Project Status](docs/project-memory/CURRENT_STATE.md)\n",
        encoding="utf-8",
    )
    (root / ".gitignore").write_text(".project-memory/private/\n", encoding="utf-8")
    (memory / "state.json").write_text(
        json.dumps(state, indent=2) + "\n", encoding="utf-8"
    )
    for relative in REQUIRED_MARKDOWN:
        path = memory / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        body = _current_state(state) if relative == "CURRENT_STATE.md" else f"# {path.stem}\n"
        path.write_text(body, encoding="utf-8")


def test_valid_project_memory_fixture_passes(tmp_path: Path) -> None:
    _write_valid_repository(tmp_path)

    assert validate_repository(tmp_path) == []


def test_checked_in_project_memory_passes_validation() -> None:
    repository_root = Path(__file__).resolve().parents[1]

    assert validate_repository(repository_root) == []


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (lambda root: (root / "docs/project-memory/RUNBOOK.md").unlink(), "missing required file"),
        (
            lambda root: (root / "docs/project-memory/PRIVATE_NOTE_TEMPLATE.md").unlink(),
            "missing required file: docs/project-memory/PRIVATE_NOTE_TEMPLATE.md",
        ),
        (
            lambda root: _mutate_state(root, lambda state: state.pop("next_action")),
            "missing required key: next_action",
        ),
        (
            lambda root: _mutate_state(
                root, lambda state: state["tasks"][0].update(status="done")
            ),
            "invalid task status",
        ),
        (
            lambda root: _mutate_state(
                root, lambda state: state.update(last_verified="07/08/2026")
            ),
            "last_verified must be an ISO date",
        ),
        (
            lambda root: _mutate_state(
                root, lambda state: state["tasks"][0].update(test_evidence=[])
            ),
            "completed task 1 has no test evidence",
        ),
        (
            lambda root: _mutate_state(
                root, lambda state: state["tasks"][0].pop("reviewed")
            ),
            "task 1 missing required field: reviewed",
        ),
        (
            lambda root: _mutate_state(
                root, lambda state: state["tasks"][0].update(reviewed="yes")
            ),
            "task 1 reviewed must be a boolean",
        ),
        (
            lambda root: _mutate_state(
                root, lambda state: state["tasks"][0].pop("final_quality_approved")
            ),
            "task 1 missing required field: final_quality_approved",
        ),
        (
            lambda root: _mutate_state(
                root, lambda state: state["tasks"][0].update(final_quality_approved=1)
            ),
            "task 1 final_quality_approved must be a boolean",
        ),
    ],
)
def test_invalid_schema_fixtures_report_actionable_errors(
    tmp_path: Path, mutation, expected: str
) -> None:
    _write_valid_repository(tmp_path)
    mutation(tmp_path)

    assert any(expected in error for error in validate_repository(tmp_path))


def test_broken_repository_relative_markdown_link_is_rejected(tmp_path: Path) -> None:
    _write_valid_repository(tmp_path)
    architecture = tmp_path / "docs/project-memory/ARCHITECTURE.md"
    architecture.write_text("# Architecture\n\n[Missing](missing-file.md)\n", encoding="utf-8")

    assert any("broken repository-relative link" in error for error in validate_repository(tmp_path))


def test_current_state_must_match_machine_state(tmp_path: Path) -> None:
    _write_valid_repository(tmp_path)
    current = tmp_path / "docs/project-memory/CURRENT_STATE.md"
    current.write_text(current.read_text(encoding="utf-8").replace("Phase A", "Phase B"), encoding="utf-8")

    assert any("CURRENT_STATE.md does not match active_phase" in error for error in validate_repository(tmp_path))


@pytest.mark.parametrize(
    ("current_row", "expected"),
    [
        ("| 1 | completed | false | true | Profiles |", "task 1 reviewed"),
        ("| 1 | completed | true | false | Profiles |", "task 1 final_quality_approved"),
    ],
)
def test_current_state_detects_task_approval_drift(
    tmp_path: Path, current_row: str, expected: str
) -> None:
    _write_valid_repository(tmp_path)
    current = tmp_path / "docs/project-memory/CURRENT_STATE.md"
    text = current.read_text(encoding="utf-8")
    current.write_text(
        text.replace("| 1 | completed | true | true | Profiles |", current_row),
        encoding="utf-8",
    )

    assert any(expected in error for error in validate_repository(tmp_path))


def test_current_state_rejects_duplicate_task_rows_even_when_last_row_matches(
    tmp_path: Path,
) -> None:
    _write_valid_repository(tmp_path)
    current = tmp_path / "docs/project-memory/CURRENT_STATE.md"
    text = current.read_text(encoding="utf-8")
    matching_row = "| 1 | completed | true | true | Profiles |"
    conflicting_row = "| 1 | pending | false | false | Stale duplicate |"
    current.write_text(
        text.replace(matching_row, f"{conflicting_row}\n{matching_row}"),
        encoding="utf-8",
    )

    assert any("duplicate task row in CURRENT_STATE.md: 1" in error for error in validate_repository(tmp_path))


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("command", 123),
        ("command", "   "),
        ("result", ["passed"]),
        ("result", ""),
    ],
)
def test_evidence_command_and_result_must_be_non_empty_strings(
    tmp_path: Path, field: str, invalid_value: object
) -> None:
    _write_valid_repository(tmp_path)
    _mutate_state(
        tmp_path,
        lambda state: state["tasks"][0]["test_evidence"][0].update(
            {field: invalid_value}
        ),
    )

    assert any(
        f"task 1 evidence {field} must be a non-empty string" in error
        for error in validate_repository(tmp_path)
    )


@pytest.mark.parametrize(
    "unsafe_text",
    [
        "SERVICE_" + "TOKEN=not-a-placeholder",
        "DATABASE_" + "URL=postgres://example.invalid/project",
        "api_" + "key: not-a-placeholder",
        "C:" + "\\Users\\someone\\private\\notes.txt",
        "C:" + "/Users/someone/private/notes.txt",
        "D:" + "\\private\\notes.txt",
        "Z:" + "/private/notes.txt",
    ],
)
def test_public_memory_docs_reject_sensitive_patterns(tmp_path: Path, unsafe_text: str) -> None:
    _write_valid_repository(tmp_path)
    privacy = tmp_path / "docs/project-memory/DATA_PRIVACY.md"
    privacy.write_text(f"# Privacy\n\n{unsafe_text}\n", encoding="utf-8")

    assert any("potential sensitive value" in error for error in validate_repository(tmp_path))


def test_public_memory_allows_urls_and_repository_relative_paths(tmp_path: Path) -> None:
    _write_valid_repository(tmp_path)
    privacy = tmp_path / "docs/project-memory/DATA_PRIVACY.md"
    privacy.write_text(
        "# Privacy\n\n"
        "See https://example.com/privacy and http://localhost:8505/status.\n"
        "Read docs/project-memory/RUNBOOK.md and scripts/check_project_memory.py.\n",
        encoding="utf-8",
    )

    assert validate_repository(tmp_path) == []


def test_private_memory_directory_must_be_ignored(tmp_path: Path) -> None:
    _write_valid_repository(tmp_path)
    (tmp_path / ".gitignore").write_text(".project-memory/cache/\n", encoding="utf-8")

    assert any(".project-memory/private/ must be ignored" in error for error in validate_repository(tmp_path))


def test_private_memory_ignore_rule_cannot_be_negated_later(tmp_path: Path) -> None:
    _write_valid_repository(tmp_path)
    (tmp_path / ".gitignore").write_text(
        ".project-memory/private/\n!.project-memory/private/\n",
        encoding="utf-8",
    )

    assert any(".project-memory/private/ must be ignored" in error for error in validate_repository(tmp_path))


def _mutate_state(root: Path, mutation) -> None:
    path = root / "docs/project-memory/state.json"
    state = json.loads(path.read_text(encoding="utf-8"))
    mutation(state)
    path.write_text(json.dumps(state), encoding="utf-8")
