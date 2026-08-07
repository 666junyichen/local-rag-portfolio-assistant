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

The tests cover valid temporary repositories, missing required files and keys, typed evidence, duplicate task rows, task-table scoping, required boolean review fields, approval drift, broken repository-relative links, drive and UNC paths, sensitive patterns, and private ignore failures. Safe URLs, drive-like URL segments, and repository-relative paths have explicit acceptance coverage. The tests also validate the checked-in memory without changing it.

## Phase Evidence

- Task 1 review checkpoint: `tests/test_processing_profiles.py` passed 56 tests on 2026-08-07.
- Task 2 latest recorded checkpoint: the full suite passed 148 tests on 2026-08-07; Phase A remained incomplete because quality blockers were still open.
- Task 0 focused evidence is recorded in `state.json` and the bootstrap session note.

Run the full Python suite before handoff:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Test evidence must include the command, result, and verification date. Completed tasks without evidence fail memory validation.
