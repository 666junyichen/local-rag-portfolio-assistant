from __future__ import annotations

import json
import shutil
import subprocess
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
                        "outcome": "passed",
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
        "known_blockers": ["CJK-adjacent URLs", "IPv6 and new-TLD URLs"],
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
- Updated: `{state['updated_at']}`
- Next action: {state['next_action']}

## Status

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
    _init_git_repository(root)


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
    ("label", "state_key", "wrong_value"),
    [
        ("Active branch", "active_branch", "wrong-branch"),
        ("Active phase", "active_phase", "Phase B"),
        ("Updated", "updated_at", "2026-08-08T01:00:00+10:00"),
        ("Next action", "next_action", "Do something else."),
    ],
)
def test_current_state_metadata_uses_exact_labeled_values(
    tmp_path: Path, label: str, state_key: str, wrong_value: str
) -> None:
    _write_valid_repository(tmp_path)
    state = _state()
    current = tmp_path / "docs/project-memory/CURRENT_STATE.md"
    text = current.read_text(encoding="utf-8")
    original = state[state_key]
    assert isinstance(original, str)
    text = text.replace(f"- {label}: `{original}`", f"- {label}: `{wrong_value}`")
    if label == "Next action":
        text = text.replace(
            f"- {label}: `{wrong_value}`",
            f"- {label}: {wrong_value}",
        ).replace(f"- {label}: {original}", f"- {label}: {wrong_value}")
    current.write_text(
        f"{text}\nCorrect value mentioned elsewhere: {original}\n",
        encoding="utf-8",
    )

    assert any(
        f"CURRENT_STATE.md does not match {state_key}" in error
        for error in validate_repository(tmp_path)
    )


def test_current_state_requires_updated_metadata_label(tmp_path: Path) -> None:
    _write_valid_repository(tmp_path)
    state = _state()
    current = tmp_path / "docs/project-memory/CURRENT_STATE.md"
    current.write_text(
        current.read_text(encoding="utf-8").replace(
            f"- Updated: `{state['updated_at']}`\n", ""
        ),
        encoding="utf-8",
    )

    assert any(
        "CURRENT_STATE.md missing metadata field: updated_at" in error
        for error in validate_repository(tmp_path)
    )


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


@pytest.mark.parametrize("change", ["extra", "missing"])
def test_current_state_task_ids_must_exactly_match_state(
    tmp_path: Path, change: str
) -> None:
    _write_valid_repository(tmp_path)
    current = tmp_path / "docs/project-memory/CURRENT_STATE.md"
    text = current.read_text(encoding="utf-8")
    row = "| 2 | in_progress | false | false | Cleaning |"
    if change == "extra":
        text = text.replace(row, f"{row}\n| 99 | pending | false | false | Stale |")
    else:
        text = text.replace(f"{row}\n", "")
    current.write_text(text, encoding="utf-8")

    assert any(
        "CURRENT_STATE.md task IDs do not match state.json" in error
        for error in validate_repository(tmp_path)
    )


@pytest.mark.parametrize("boolean_id", [True, False])
def test_boolean_task_ids_are_rejected(tmp_path: Path, boolean_id: bool) -> None:
    _write_valid_repository(tmp_path)
    _mutate_state(
        tmp_path,
        lambda state: state["tasks"][0].update(id=boolean_id),
    )

    assert any(
        f"invalid or duplicate task id: {boolean_id!r}" in error
        for error in validate_repository(tmp_path)
    )


def test_zero_task_id_remains_valid_for_task_zero(tmp_path: Path) -> None:
    _write_valid_repository(tmp_path)
    state_path = tmp_path / "docs/project-memory/state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["tasks"][0]["id"] = 0
    state_path.write_text(json.dumps(state), encoding="utf-8")
    current = tmp_path / "docs/project-memory/CURRENT_STATE.md"
    current.write_text(
        current.read_text(encoding="utf-8").replace(
            "| 1 | completed | true | true | Profiles |",
            "| 0 | completed | true | true | Profiles |",
        ),
        encoding="utf-8",
    )

    assert validate_repository(tmp_path) == []


@pytest.mark.parametrize("location", ["outside_status", "inside_status"])
def test_current_state_ignores_unrelated_numeric_five_column_tables(
    tmp_path: Path, location: str
) -> None:
    _write_valid_repository(tmp_path)
    current = tmp_path / "docs/project-memory/CURRENT_STATE.md"
    text = current.read_text(encoding="utf-8")
    unrelated = """| Rank | Label | Enabled | Approved | Notes |
|---|---|---|---|---|
| 1 | sample | true | true | Not a task row |
"""
    if location == "outside_status":
        text = f"{text}\n## Metrics\n\n{unrelated}"
    else:
        marker = "## Status\n\n"
        text = text.replace(marker, f"{marker}{unrelated}\n")
    current.write_text(text, encoding="utf-8")

    assert validate_repository(tmp_path) == []


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


@pytest.mark.parametrize("invalid_outcome", [None, True, "skipped"])
def test_evidence_outcome_must_be_passed_or_failed(
    tmp_path: Path, invalid_outcome: object
) -> None:
    _write_valid_repository(tmp_path)

    def mutate(state: dict[str, object]) -> None:
        evidence = state["tasks"][0]["test_evidence"][0]
        if invalid_outcome is None:
            evidence.pop("outcome")
        else:
            evidence["outcome"] = invalid_outcome

    _mutate_state(tmp_path, mutate)

    assert any(
        "task 1 evidence outcome must be 'passed' or 'failed'" in error
        for error in validate_repository(tmp_path)
    )


def test_failed_only_evidence_cannot_support_review_or_approval(tmp_path: Path) -> None:
    _write_valid_repository(tmp_path)
    _mutate_state(
        tmp_path,
        lambda state: state["tasks"][0]["test_evidence"][0].update(outcome="failed"),
    )

    errors = validate_repository(tmp_path)
    assert any("task 1 reviewed=true requires passed test evidence" in error for error in errors)
    assert any(
        "task 1 final_quality_approved requires passed test evidence" in error
        for error in errors
    )


def test_unreviewed_task_may_record_valid_failed_evidence(tmp_path: Path) -> None:
    _write_valid_repository(tmp_path)

    def mutate(state: dict[str, object]) -> None:
        state["tasks"][1]["test_evidence"] = [
            {
                "command": "python -m pytest -q",
                "result": "1 failed",
                "outcome": "failed",
                "verified_at": "2026-08-08",
            }
        ]

    _mutate_state(tmp_path, mutate)

    assert validate_repository(tmp_path) == []


@pytest.mark.parametrize(
    ("task_update", "evidence", "expected"),
    [
        (
            {"final_quality_approved": True, "reviewed": False},
            None,
            "final_quality_approved requires reviewed=true",
        ),
        (
            {"final_quality_approved": True, "status": "in_progress"},
            None,
            "final_quality_approved requires status=completed",
        ),
        (
            {"final_quality_approved": True},
            [],
            "final_quality_approved requires non-empty valid test evidence",
        ),
        (
            {"final_quality_approved": True},
            [{"command": "pytest", "result": [], "verified_at": "2026-08-08"}],
            "final_quality_approved requires non-empty valid test evidence",
        ),
        (
            {"reviewed": True, "final_quality_approved": False},
            [],
            "reviewed=true requires non-empty valid test evidence",
        ),
    ],
)
def test_task_approval_invariants(
    tmp_path: Path,
    task_update: dict[str, object],
    evidence: list[object] | None,
    expected: str,
) -> None:
    _write_valid_repository(tmp_path)

    def mutate(state: dict[str, object]) -> None:
        task = state["tasks"][0]
        task.update(task_update)
        if evidence is not None:
            task["test_evidence"] = evidence

    _mutate_state(tmp_path, mutate)

    assert any(f"task 1 {expected}" in error for error in validate_repository(tmp_path))


@pytest.mark.parametrize("change", ["missing", "extra", "reordered", "misplaced"])
def test_current_state_known_blockers_must_match_exact_section_bullets(
    tmp_path: Path, change: str
) -> None:
    _write_valid_repository(tmp_path)
    current = tmp_path / "docs/project-memory/CURRENT_STATE.md"
    text = current.read_text(encoding="utf-8")
    first = "- CJK-adjacent URLs"
    second = "- IPv6 and new-TLD URLs"
    if change == "missing":
        text = text.replace(f"{first}\n", "") + "\nMentioned elsewhere: CJK-adjacent URLs\n"
    elif change == "extra":
        text = text.replace(second, f"{second}\n- Stale blocker")
    elif change == "reordered":
        text = text.replace(f"{first}\n{second}", f"{second}\n{first}")
    else:
        text = text.replace(f"{first}\n", "")
        text += f"\n## Misplaced\n\n{first}\n"
    current.write_text(text, encoding="utf-8")

    assert any(
        "CURRENT_STATE.md known blockers do not match state.json" in error
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
        "\\\\" + "server\\private\\notes.txt",
        "//" + "server/share/notes.txt",
        "file:" + "///C:/private/notes.txt",
        "/" + "C:/private/notes.txt",
        "ftp:" + "//example.com/archive/C:/guide",
        "/Users/" + "someone/private/notes.txt",
        "/home/" + "someone/private/notes.txt",
        "/Users/" + "someone",
        "/home/" + "someone",
        "file:" + "///home/someone/private/notes.txt",
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
        "See https://example.com/privacy, https://example.com/archive/C:/guide, "
        "http://localhost:8505/archive/D:/guide, "
        "https://example.com/Users/demo/guide, and "
        "https://example.com/home/demo/guide, "
        "https://example.com/Users/demo, and https://example.com/home/demo.\n"
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


@pytest.mark.parametrize(
    "negation",
    ["!.project-memory/private", "!/.project-memory/private"],
)
def test_equivalent_private_directory_negations_make_note_trackable(
    tmp_path: Path, negation: str
) -> None:
    _write_valid_repository(tmp_path)
    (tmp_path / ".gitignore").write_text(
        f".project-memory/private/\n{negation}\n",
        encoding="utf-8",
    )
    note = tmp_path / ".project-memory/private/note.md"
    note.parent.mkdir(parents=True)
    note.write_text("private", encoding="utf-8")

    assert _git_check_ignore(tmp_path, note) == 1
    assert any(
        ".project-memory/private/ must be ignored" in error
        for error in validate_repository(tmp_path)
    )


@pytest.mark.parametrize(
    "final_rule",
    [".project-memory/private", "/.project-memory/private/"],
)
def test_later_equivalent_ignore_rule_restores_private_protection(
    tmp_path: Path, final_rule: str
) -> None:
    _write_valid_repository(tmp_path)
    (tmp_path / ".gitignore").write_text(
        ".project-memory/private/\n"
        "!.project-memory/private\n"
        f"{final_rule}\n",
        encoding="utf-8",
    )
    note = tmp_path / ".project-memory/private/note.md"
    note.parent.mkdir(parents=True)
    note.write_text("private", encoding="utf-8")

    assert _git_check_ignore(tmp_path, note) == 0
    assert validate_repository(tmp_path) == []


def test_wildcard_private_negation_makes_probe_trackable(tmp_path: Path) -> None:
    _write_valid_repository(tmp_path)
    (tmp_path / ".gitignore").write_text(
        ".project-memory/private/\n!**/private/\n",
        encoding="utf-8",
    )
    note = tmp_path / ".project-memory/private/note.md"

    assert _git_check_ignore(tmp_path, note) == 1
    assert any(
        ".project-memory/private/ must be ignored" in error
        for error in validate_repository(tmp_path)
    )


def test_later_ignore_rule_restores_protection_after_wildcard_negation(
    tmp_path: Path,
) -> None:
    _write_valid_repository(tmp_path)
    (tmp_path / ".gitignore").write_text(
        ".project-memory/private/\n"
        "!**/private/\n"
        ".project-memory/private/\n",
        encoding="utf-8",
    )
    note = tmp_path / ".project-memory/private/note.md"

    assert _git_check_ignore(tmp_path, note) == 0
    assert validate_repository(tmp_path) == []


def test_git_check_ignore_failure_is_reported_explicitly(tmp_path: Path) -> None:
    _write_valid_repository(tmp_path)
    shutil.rmtree(tmp_path / ".git")

    assert any(
        "git check-ignore failed" in error and "not a git repository" in error.lower()
        for error in validate_repository(tmp_path)
    )


def _init_git_repository(root: Path) -> None:
    subprocess.run(
        ["git", "-C", str(root), "init", "-q"],
        check=True,
        capture_output=True,
        text=True,
    )


def _git_check_ignore(root: Path, path: Path) -> int:
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "check-ignore",
            "--no-index",
            path.relative_to(root).as_posix(),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.returncode


def _mutate_state(root: Path, mutation) -> None:
    path = root / "docs/project-memory/state.json"
    state = json.loads(path.read_text(encoding="utf-8"))
    mutation(state)
    path.write_text(json.dumps(state), encoding="utf-8")
