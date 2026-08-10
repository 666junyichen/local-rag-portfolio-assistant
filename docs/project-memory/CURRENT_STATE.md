# Current State

- Active branch: `main`
- Active phase: `Knowledge Spaces Production Acceptance`
- Last verified: `2026-08-10`
- Updated: `2026-08-10T15:10:00+10:00`
- Next action: Restore the WSL2 kernel, start Docker, run the local knowledge-space migration, then collect real single-space and cross-space Retrieval Lab examples.

## Status

Tasks 0-10 are completed and reviewed. Owner production acceptance now covers sign-in, email and phone PII blocking, sanitized preview, publication, Knowledge visibility, grounded Retrieve and Chat responses, unpublish, and permanent synthetic-data cleanup. A no-evidence Chat stream regression found during unpublish verification was fixed and deployed; an active empty space now returns a grounded refusal with HTTP 200 instead of a server error.

Task 11 adds public and local Knowledge Spaces. Cloud data is migrated to the default `portfolio` space, Owner uploads can target and move between spaces, and Ask AI, Knowledge, Retrieval Lab, and Sources carry space filters and labels. Single-space isolation and cross-space evidence preservation passed production acceptance. Local code, unit tests, and all three Streamlit pages pass, but the real local MongoDB migration remains pending because the Docker engine cannot start while the WSL2 kernel file is missing.

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
| 11 | in_progress | true | false | Cloud knowledge spaces passed; local MongoDB migration is blocked by the missing WSL2 kernel |

## Known Blockers

- The local Docker engine cannot start because the WSL2 kernel file is missing; local MongoDB knowledge-space migration remains pending.

See [Known Issues](KNOWN_ISSUES.md) for acceptance criteria and [Testing](TESTING.md) for the evidence contract.
