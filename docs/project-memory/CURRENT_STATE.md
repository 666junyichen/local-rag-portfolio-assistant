# Current State

- Active branch: `feat/reset-retrieval-fix`
- Active phase: `Local Reset and Cloud Retrieval Accuracy`
- Last verified: `2026-08-12`
- Updated: `2026-08-12T23:20:00+10:00`
- Next action: Run the milestone tests once, merge to main, execute the guarded local reset, deploy production, republish the Master resume as semantic v2, and verify exhaustive and ranked questions.

## Status

Tasks 0-10 are completed and reviewed. Owner production acceptance now covers sign-in, email and phone PII blocking, sanitized preview, publication, Knowledge visibility, grounded Retrieve and Chat responses, unpublish, and permanent synthetic-data cleanup. A no-evidence Chat stream regression found during unpublish verification was fixed and deployed; an active empty space now returns a grounded refusal with HTTP 200 instead of a server error.

Task 12's reset controls were completed, but its local acceptance state did not remain true: a stale Streamlit runtime reintroduced the legacy catalog after the reset. Task 13 removes automatic legacy import from normal startup, treats an empty catalog as ready, adds a terminal reset entrypoint, and requires a fresh post-restart datastore check before claiming the local reset is complete.

Task 13 also upgrades cloud publication and retrieval. Resume-like uploads and old resume revisions use semantic parent blocks, retrieval indexes children, selected context is deduplicated by parent and semantic group, and public answers distinguish exhaustive questions from ranked "strongest" questions. Focused local tests passed 29 cases and focused cloud tests passed 32 cases; the milestone suite, real local reset, production deployment, and Master v2 republish remain pending.

Task 11 adds public and local Knowledge Spaces. Cloud data is migrated to the default `portfolio` space, Owner uploads can target and move between spaces, and Ask AI, Knowledge, Retrieval Lab, and Sources carry space filters and labels. Single-space isolation and cross-space evidence preservation passed production acceptance. The real local migration now also passes: both local indexes are `READY` with `space_id` filters, a single-space query retrieved three Portfolio sources, and the Ollama smoke test generated a grounded answer.

The public catalog was backfilled with 27 repository documents without regenerating Gemini embeddings. A real Chinese cloud question returned five grounded sources after the legacy Atlas Vector Search filter was made compatible with the existing index. The public Retrieval Lab returned five public-only chunks, and the catalog rendered without horizontal overflow at 390x844.

The refreshed 50-question benchmark on the 689-child index found that Vector remains the best fast default. Plain Hybrid RRF matched Vector Hit@5 but reduced MRR from 0.906 to 0.867. Hybrid + Cross-Encoder Rerank reached Hit@5 1.000, Recall@5 0.954, MRR 0.924, and nDCG@5 0.889 at 1.49 seconds average latency. The remaining baseline weakness is freshness ranking; this evidence narrows Phase B to freshness-aware ranking and selective reranker routing.

Phase B's adaptive path triggered the reranker for 15 of 50 benchmark questions. It achieved Hit@5 0.975, MRR 0.9167, freshness Hit@5 1.000, no-answer accuracy 1.000, and zero privacy violations at 697 ms average latency. The fast Vector baseline remains unchanged at MRR 0.90625, so the adaptive route improves quality without paying reranker latency on every query.

| Task | Status | Reviewed | Final quality approved | Summary |
|---|---|---|---|---|
| 0 | completed | true | true | Persistent project-memory protocol, validator, and tests |
| 1 | completed | true | true | Versioned processing profiles, reviewed |
| 2 | completed | true | true | Configurable cleaning and structural units with boundary regressions covered |
| 3 | completed | true | true | General, resume semantic, and parent-child hierarchy |
| 4 | completed | true | true | Idempotent SQLite profile migration and persistence |
| 5 | completed | true | true | Child indexing with parent evidence expansion and deduplication |
| 6 | completed | true | true | Dify-style preprocessing, segmentation, preview, and persistence controls |
| 7 | completed | true | true | Vector, BM25, Hybrid, and Hybrid + Rerank diagnostics |
| 8 | completed | true | true | Real catalog migration, local reindex, full tests, cloud checks, and documentation |
| 9 | completed | true | true | File-authoritative local configuration, split runtime health, freshness ranking, and adaptive reranker routing |
| 10 | completed | true | true | Owner production publication lifecycle and synthetic-data cleanup passed |
| 11 | completed | true | true | Cloud and local Knowledge Spaces, index migration, single/cross-space filtering, and smoke validation |
| 12 | completed | true | true | One default Portfolio space, verified ignored backups, and completed local/cloud knowledge resets |
| 13 | in_progress | false | false | Harden local empty-state reset and publish/retrieve semantic resume v2 evidence |

## Known Blockers

- Real local reset and Master resume v2 production republish are pending final acceptance.

See [Known Issues](KNOWN_ISSUES.md) for acceptance criteria and [Testing](TESTING.md) for the evidence contract.
