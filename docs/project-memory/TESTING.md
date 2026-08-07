# Testing

## Memory Validation

Run the validator directly:

```powershell
.\.venv\Scripts\python.exe scripts\check_project_memory.py
```

Run its focused tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_project_memory.py -q
```

The tests cover valid temporary repositories, missing required files and keys, structured metadata, typed passed/failed evidence, passed-evidence approval gates, exact blocker bullets, exact task-ID sets, duplicate task rows, task-table scoping, exact integer IDs, approval drift, broken repository-relative links, Windows and POSIX user paths, sensitive patterns, and private ignore failures. Private-ignore tests use Git itself to prove equivalent negations make a note trackable and that a later ignore restores protection. Failed evidence remains valid history for unreviewed tasks, while HTTP/HTTPS URL segments, Task 0, and repository-relative paths have explicit acceptance coverage. The tests also validate the checked-in memory without changing it.

## Phase Evidence

- Task 1 review checkpoint: `tests/test_processing_profiles.py` passed 56 tests on 2026-08-07.
- Task 2 latest recorded checkpoint: the full suite passed 148 tests on 2026-08-07; Phase A remained incomplete because quality blockers were still open.
- Task 0 focused evidence is recorded in `state.json` and the bootstrap session note.

Run the full Python suite before handoff:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Test evidence must include non-empty command/result strings, an `outcome` of `passed` or `failed`, and an ISO verification date. Reviewed or final-quality-approved tasks require at least one fully valid passed entry; failed-only evidence cannot support approval.
