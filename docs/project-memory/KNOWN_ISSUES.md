# Known Issues

## Pending: Real Knowledge Reset Execution

The single-space defaults, backup generation, fingerprint validation, confirmation gates, and data-clear operations pass automated tests. The real local SQLite/MongoDB reset and production Atlas reset must still be executed after merge and deployment. Completion requires a verified local backup, a downloaded cloud JSON backup, zero remaining documents/chunks/drafts/history/runtime evaluations, and exactly one empty active `portfolio` space in each runtime.

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

The public Atlas deployment currently reports `textIndex=false`, so the public Demo remains on stable Vector Search. Local Retrieval Lab provides BM25, Hybrid RRF, and Hybrid + Rerank. Do not describe cloud BM25 as enabled until Atlas index capacity is available and the public collection is reseeded.

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
