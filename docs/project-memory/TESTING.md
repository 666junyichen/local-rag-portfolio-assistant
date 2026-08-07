# Testing

## Verification Levels

Use the smallest level that can detect the current change:

1. **Edit loop:** run one affected test case or module.
2. **Task checkpoint:** run all tests for the changed subsystem plus the project-memory validator.
3. **Milestone:** run the full Python suite once after the task is stable, and run TypeScript/build/browser checks only when those surfaces changed.

Do not repeat the milestone suite after every review comment. A review fix first receives focused regression coverage; related fixes are batched before the single milestone rerun. Reviews are time-boxed to 15 minutes and one consolidated recheck unless a high-severity issue remains.

## Memory Validation

Run the validator directly:

```powershell
.\.venv\Scripts\python.exe scripts\check_project_memory.py
```

Run its focused tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_project_memory.py -q
```

The tests cover valid temporary Git repositories, missing required files and keys, structured metadata, typed passed/failed evidence, passed-evidence approval gates, exact blocker bullets, exact task-ID sets, duplicate task rows, task-table scoping, exact integer IDs, approval drift, broken repository-relative links, Windows and POSIX user paths, sensitive patterns, and private ignore failures. Private-ignore validation uses verbose `git check-ignore --no-index` probes for both `.project-memory/private/` and `.project-memory/private/note.md`, so wildcard negations and later-rule precedence follow effective Git semantics. Both probes must be protected by the repository's tracked `.gitignore`; filename-only rules, untracked `.gitignore` files, `.git/info/exclude`, global excludes, trackable probes, malformed output, and Git command failures are rejected. Failed evidence remains valid history for unreviewed tasks, while HTTP/HTTPS URL segments, Task 0, and repository-relative paths have explicit acceptance coverage. The tests also validate the checked-in memory without changing it.

## Phase Evidence

- Task 1 review checkpoint: `tests/test_processing_profiles.py` passed 56 tests on 2026-08-07.
- Task 2 focused approval: `tests/test_document_processing.py` passed 38 tests on 2026-08-08, including the recorded URL, email, Unicode-boundary, apostrophe, IPv6/new-TLD, and CRLF cases.
- Task 0 focused evidence is recorded in `state.json` and the bootstrap session note.

Run the full Python suite once before a feature-task handoff or merge milestone:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Test evidence must include non-empty command/result strings, an `outcome` of `passed` or `failed`, and an ISO verification date. Reviewed or final-quality-approved tasks require at least one fully valid passed entry; failed-only evidence cannot support approval.

Keep only the latest focused result and latest milestone result in `state.json`. Put intermediate red/green iterations in the dated session note so the machine-readable state stays concise.
