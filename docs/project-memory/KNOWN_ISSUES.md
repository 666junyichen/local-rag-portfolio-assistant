# Known Issues

## Resolved: Public Preview Appeared Incomplete

Publish Studio previously rendered only the first 20 retrieval children even when the server generated a larger complete preview. This was a display cap, not evidence that resume content had been discarded. The page now renders every generated child or parent on demand and reports distinct project semantic groups so coverage can be checked before publication.

## Remaining Parser Boundary

The shared chunking contract starts from normalized text after parsing. DOCX, PDF, Markdown, and CSV parser implementations remain runtime-specific and retain their own parser tests. Add binary parser parity only if real uploads reveal different normalized text; do not add Python or model runtimes to Vercel solely for parser symmetry.

## Resolved: Task 13 Runtime And Production Acceptance

Task 13 passed on 2026-08-13. The terminal-driven reset remained empty across two fresh Streamlit starts with one `portfolio` space. The Master resume v2 was published atomically, production parent evidence was deduplicated, and ranked and exhaustive project questions returned only distinct project sections.

## Resolved: Real Knowledge Reset Execution

The guarded local and production resets completed on 2026-08-11. Both backups are stored under the Git-ignored private project-memory directory. Local SQLite and MongoDB now contain no knowledge documents, chunks, chat history, or runtime evaluation artifacts; production Atlas contains no drafts, documents, chunks, or publication metadata. Both runtimes retain exactly one empty active `portfolio` space, and local legacy/repository auto-import is disabled.

## Resolved: Task 2 Quality Blockers

Task 2 was approved on 2026-08-08 after focused regression coverage passed.

| Blocker | Required behavior before approval |
|---|---|
| CJK-adjacent URLs | URL removal must stop at adjacent CJK text and preserve that text and punctuation. |
| IPv6 and new-TLD URLs | Recognize supported IPv6 URL forms and valid contemporary top-level domains without deleting domain-like prose. |
| Unicode-adjacent emails | Remove a valid email without consuming neighboring Unicode letters or punctuation. |
| Apostrophe emails | Handle valid apostrophes in the local part while preserving surrounding prose. |
| CRLF migration behavior | Define and test deterministic behavior for legacy profiles and text using Windows line endings. |

## Resolution Evidence

The focused command `.\.venv\Scripts\python.exe -m pytest tests\test_document_processing.py -q` passed all 38 tests. The full suite remains reserved for the Phase A milestone.

## Resolved: Phase A Release Checkpoint

The real local catalog was migrated, the Vector/BM25 indexes were rebuilt, the milestone suite passed, and local/cloud question-answer flows were verified. The optional automated browser connector could not attach, but all three Streamlit pages passed application rendering tests and the live server returned HTTP 200.

## Remaining Cloud Limitation

The public Atlas deployment previously reported `textIndex=false`, so the public Demo remained on stable Vector Search. Cloud retrieval now accepts the same mode names as local retrieval and reports capability-aware fallback diagnostics, but cloud BM25 and Hybrid are active only when `text_index_public` exists and is queryable. Do not describe cloud BM25 as enabled until the deployed `/api/health` reports the text index ready and `/api/retrieve` returns `capabilities.bm25=true`.

## Remaining Cloud Benchmark Gate

Run `npm run evaluate:cloud -- --base-url=<deployed-url> --modes=vector,adaptive,hybrid` against the current deployment, and rerun after `text_index_public` becomes READY if `/api/health` still reports `textIndex=false`. Keep Vector as the cloud default unless adaptive or hybrid meets or beats Vector on Hit@5 and MRR with no-answer accuracy `1.000` and privacy violations `0`. A report where adaptive or hybrid degrades to Vector is useful operational evidence, but it does not justify changing the default.

## Retrieval Calibration Evidence

The refreshed benchmark shows that plain Hybrid RRF does not improve the current curated corpus: it matches Vector Hit@5 while lowering MRR and nDCG@5. Do not make plain Hybrid the default solely because it combines two retrieval channels. The reranker improves every answerable case into Top-5 but costs about 1.49 seconds per query.

Phase B resolved the measured freshness gap: all five freshness benchmark cases now hit an expected source in Top-5. Adaptive routing improves MRR while invoking the reranker only for complex or low-confidence questions. Continue collecting real Retrieval Lab examples before changing routing thresholds or adding multi-step Agentic RAG.

## Remaining Local Limitation

The optional Cross-Encoder is intentionally loaded from the local model cache only. If it is absent, adaptive retrieval falls back to Vector and reports the reason instead of downloading a model during a user request. Install or pre-cache the free reranker separately when high-precision mode is required.

## Resolved: Owner Publish Studio Deployment Gate

Clerk Owner sign-in and the production allowlist are active. The complete synthetic lifecycle passed on 2026-08-10: upload, PII block, sanitization, publication, public retrieval/chat, unpublish, and permanent cleanup. Anonymous visitors still cannot see Studio or call admin APIs.

## Resolved: Knowledge Spaces Local Index Migration

The local migration originally failed with `"mappings" is required` because MongoDB Local interpreted PyMongo's vector-index update as a standard Search definition. Passing an explicit `type` field was also rejected by that runtime. The migration now recreates only the Vector Search index definition with `type=vectorSearch`, updates the text index in place, and does not regenerate embeddings or change source documents.

On 2026-08-10 both indexes reached `READY` with `space_id` filters. A real Portfolio query retrieved three sources and the local Ollama smoke test passed. The remaining operational caveat is model cold-start latency; the first generation after startup can take several minutes on CPU, while a warmed model responds much faster.

The public Knowledge catalog already contains the repository-seeded records, and the catalog-only seed path can refresh metadata without calling Gemini or changing retrieval embeddings.
