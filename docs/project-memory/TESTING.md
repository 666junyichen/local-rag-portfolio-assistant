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

- Task 16 on 2026-08-22: 44 focused TypeScript tests passed across cloud processing, shared profiles, cloud retrieval, health, chat/retrieve routes, and seed safety. 147 focused Python tests passed for processing-profile, retrieval planning, and project-memory validation. The cloud benchmark script smoke completed against an intentionally unreachable URL and wrote an ignored report instead of crashing; a follow-up regression prevents 0-quality tie results from promoting Hybrid. The Next.js production build compiled 19 pages and API routes, and Vercel production deployment `dpl_HdNcfBgMNY8izuH5jwKRUSpo6kGb` reached Ready. Production `/api/health` reported Atlas, Gemini, Vector, and text search ready. The live legacy 50-question benchmark reported Hit@5 `0.000` for Vector, Adaptive, and Hybrid because the deployed public corpus is now one Owner-published Master resume document rather than the older 27 repo-seed documents expected by `evals/rag_benchmark.json`; no-answer accuracy remained `1.000` with zero privacy violations, and the corrected gate kept the default on Vector. `npx tsc --noEmit` still fails only in pre-existing test typing issues in `tests/cloud-publish-auth.test.ts` and `tests/cloud-publish-lifecycle.test.ts`.

- Task 15 on 2026-08-15: 16 focused Publish Studio preview and cloud processing tests passed. The regression test proves a 48-child preview is returned without truncation and that all 35 parents remain selectable; the Next.js production build compiled all 19 routes successfully.

- Task 14 on 2026-08-15: 23 focused TypeScript tests passed across the Owner entry, shared profiles, cloud processing, and cross-runtime parity suites; 62 focused Python profile, hierarchy, and contract tests passed; the Next.js production build completed successfully.
- The parity fixtures compare canonical post-parser resume, Markdown, and CSV text. They verify parent and child boundaries plus retrieval metadata while allowing local SentenceTransformer and cloud Gemini embeddings to remain independent.

- Task 13 production acceptance on 2026-08-13: the guarded local reset left zero documents, duplicate groups, chunks, chat records, and runtime evaluations; two fresh Streamlit starts retained the empty state and one `portfolio` space.
- The Master resume v2 publication produced 35 semantic answer parents and 47 retrieval children. Production checks returned five distinct `project` parents for the ranked question and eleven `project` parents for the exhaustive question. The final focused parent-context regression passed 5 tests and Vercel reported the production deployment Ready.
- Task 13 milestone on 2026-08-12: Python passed 274 tests and 3 Streamlit subtests in 84 seconds; TypeScript passed 82 tests across 15 files; Next.js compiled 19 pages and API routes; the standalone Streamlit checker passed Chat, Knowledge Studio, Retrieval Lab, and all retrieval modes.
- The first Task 13 build exposed use of a nonexistent Mammoth `convertToMarkdown` API. A red-green parser regression replaced it with supported HTML conversion that preserves headings, list items, paragraphs, and table rows; 22 focused parser/processing tests and a fresh production build passed afterward.

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
- Post-merge startup regression: the standalone page checker was updated for Adaptive mode; 7 Streamlit contract tests and 3 subtests passed, and all three pages passed the independent AppTest preflight.
- Runtime regression: `tests/test_local_runtime.py` passed 10 tests; rerunning `start-local.ps1` against a healthy server returned success and reused `http://localhost:8505`.
- Owner Publish Studio milestone on 2026-08-09: 46 Vitest tests passed across 9 files, covering Owner identity, public contracts, parsers, PII/processing, publication idempotency/concurrency/quota fallback, retrieval compatibility, and seed safety.
- The Next.js production build passed with `/studio` rendered dynamically and all admin, knowledge, chat, retrieval, and health routes compiled.
- `node scripts/seed-atlas.mjs --validate` validated 27 public documents and 27 chunks. The quota-free `--catalog-only` path backfilled 27 catalog records while preserving Owner records and making no Gemini embedding calls.
- Browser acceptance passed at desktop and 390x844: guest navigation omitted Studio, the public catalog listed 27 records and filtered MongoDB results, Chinese Chat returned a grounded answer with five sources, Retrieval Lab returned five public-only chunks, and missing Clerk configuration failed closed.
- Production visitor acceptance on 2026-08-09: the Vercel Knowledge page rendered 27 records with no Studio navigation for guests; direct `/studio` access showed the intended fail-closed Clerk configuration state. Owner login and publication remain unverified until Clerk production configuration is available.
- Clerk provisioning checkpoint on 2026-08-10: Marketplace terms were accepted, the Clerk resource reported `Available` and connected to the Vercel project, both Clerk key names were present in the pulled local environment, and the Owner allowlist was added as a sensitive Production variable. No key values were printed or committed.
- The Python milestone remained green at `251 passed, 3 subtests passed`; Task 10 changed only the cloud TypeScript/Next.js surface after that run, so the suite was not repeated unnecessarily.
- Knowledge Spaces production acceptance on 2026-08-10 used one synthetic document: email and compact-phone PII were blocked, sanitized publication appeared only in `Project Docs`, Retrieve and Chat returned grounded evidence, a Portfolio-only query excluded it, and a cross-space query preserved evidence from both selected spaces.
- Unpublish removed the synthetic document from Knowledge, Retrieve, and Chat. Permanent cleanup removed its document and draft records, and the final public API reported zero documents in `Project Docs`.
- The no-evidence Chat regression was reproduced by `tests/cloud-chat-route.test.ts` as `Controller is already closed`, fixed by giving the SSE stream one close path, deployed, and verified in production as HTTP 200 with retrieval, refusal, and done events.
- Knowledge Spaces cloud milestone: `npm test` passed 60 tests across 11 main-repository Vitest files; `npm run build` compiled 17 pages and API routes.
- Python milestone on 2026-08-10: `263 passed, 3 subtests passed` in 103.46 seconds. `scripts/check_streamlit_pages.py` passed Chat, Knowledge Studio, Retrieval Lab, and all five retrieval modes.
- Knowledge Spaces local integration on 2026-08-10: the migration completed without re-embedding; `text_index` and `vector_index` both reached `READY` with `space_id` filters. The focused migration/retrieval suite passed 26 tests, all three Streamlit pages passed AppTest, a real Portfolio query returned three sources, and `scripts/smoke_test.py` generated a grounded Ollama answer.
- Safe-reset milestone on 2026-08-11: `270 passed, 3 subtests passed`; `npm test` passed 66 tests across 13 files; `npm run build` compiled 19 pages and API routes; and `scripts/check_streamlit_pages.py` passed all three local pages and five retrieval modes.
- Real local reset acceptance on 2026-08-11: an ignored backup was created before clearing 7,049 catalog documents, 689 MongoDB chunks, 23 chat messages, and three runtime evaluation files. Verification found zero documents/chunks/chat records, exactly one `portfolio` space, `legacy_import_completed=true`, and `include_repo_public=false`; retained repository documents and external source files were unchanged.
- Real production reset acceptance on 2026-08-11: a fingerprint-verified ignored JSON backup captured three spaces, one draft, 27 documents, and 27 chunks. Atlas verification and the deployed `/api/spaces` and `/api/knowledge` contracts then reported exactly one `portfolio` space and zero drafts, documents, chunks, metadata, and public knowledge records.
- The first smoke-test attempt exceeded 180 seconds during model cold start. A four-token Ollama warm-up completed in 9.65 seconds, after which the full smoke test passed in 107.5 seconds. Treat this as local CPU/model-loading latency rather than an index failure.
- Task 0 focused evidence is recorded in `state.json` and the bootstrap session note.

Run the full Python suite once before a feature-task handoff or merge milestone:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Test evidence must include non-empty command/result strings, an `outcome` of `passed` or `failed`, and an ISO verification date. Reviewed or final-quality-approved tasks require at least one fully valid passed entry; failed-only evidence cannot support approval.

Keep only the latest focused result and latest milestone result in `state.json`. Put intermediate red/green iterations in the dated session note so the machine-readable state stays concise.
