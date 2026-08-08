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
- Tasks 3-7 subsystem checkpoint: 82 tests and 3 Streamlit subtests passed on 2026-08-08.
- Real resume structure check: the Master DOCX produced 28 semantic parent blocks and 40 retrieval children instead of seven mixed chunks.
- Phase A milestone: `238 passed, 3 subtests passed` in 50.39 seconds.
- Cloud regression: 10 Vitest tests passed and the Next.js production build completed.
- Local integration: 7,048 catalog rows migrated; 111 active sources produced 689 indexed children; Vector index reached READY; smoke test and a Chinese local answer passed.
- Public integration: `/api/health` reported Atlas, Gemini, and Vector Index ready; a Chinese SSE chat returned sources and a Chinese answer. The cloud text index remains intentionally disabled on the current Atlas tier.
- Post-Phase A benchmark refresh on 2026-08-08: Vector Hit@5 0.925, Recall@5 0.838, MRR 0.906, nDCG@5 0.830, 182 ms average latency; Hybrid RRF Hit@5 0.925, Recall@5 0.838, MRR 0.867, nDCG@5 0.813, 93 ms; Hybrid + Rerank Hit@5 1.000, Recall@5 0.954, MRR 0.924, nDCG@5 0.889, 1.49 s. All modes retained no-answer accuracy 1.000 and zero privacy violations.
- Phase B adaptive benchmark on 2026-08-08: Hit@5 0.975, Recall@5 0.908, MRR 0.9167, nDCG@5 0.864, freshness Hit@5 1.000, no-answer accuracy 1.000, and zero privacy violations. The local reranker was triggered for 15 of 50 questions and average latency was 697 ms.
- Phase B focused checkpoint: 46 tests and 3 Streamlit subtests passed for environment reload, runtime diagnostics, freshness ranking, adaptive routing, fallback behavior, and UI contracts.
- Phase B milestone suite: `250 passed, 3 subtests passed` in 66.60 seconds on 2026-08-08.
- Runtime regression: `tests/test_local_runtime.py` passed 10 tests; rerunning `start-local.ps1` against a healthy server returned success and reused `http://localhost:8505`.
- Task 0 focused evidence is recorded in `state.json` and the bootstrap session note.

Run the full Python suite once before a feature-task handoff or merge milestone:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Test evidence must include non-empty command/result strings, an `outcome` of `passed` or `failed`, and an ISO verification date. Reviewed or final-quality-approved tasks require at least one fully valid passed entry; failed-only evidence cannot support approval.

Keep only the latest focused result and latest milestone result in `state.json`. Put intermediate red/green iterations in the dated session note so the machine-readable state stays concise.
