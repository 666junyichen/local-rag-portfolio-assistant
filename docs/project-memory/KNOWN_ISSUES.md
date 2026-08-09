# Known Issues

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

## Owner Publish Studio Deployment Gate

The Owner publishing implementation, public catalog, admin authorization tests, build, catalog backfill, and local browser acceptance passed on 2026-08-09. Production Owner login is not active until the Vercel project has a Clerk integration or manually supplied Clerk keys plus `OWNER_EMAILS`. The application fails closed while these values are absent: visitors cannot see a Studio navigation item, `/studio` shows a configuration notice, and admin APIs return an unavailable/unauthorized response.

The public Knowledge catalog does not share this blocker. It already contains the 27 repository-seeded records, and the catalog-only seed path can refresh metadata without calling Gemini or changing retrieval embeddings.
