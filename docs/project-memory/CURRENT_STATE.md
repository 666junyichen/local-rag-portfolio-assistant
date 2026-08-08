# Current State

- Active branch: `main`
- Active phase: `Post-Phase A evaluation`
- Last verified: `2026-08-08`
- Updated: `2026-08-08T13:57:00+10:00`
- Next action: Plan a narrow Phase B for freshness-aware ranking and adaptive reranker routing; defer Agentic RAG and other broad features.

## Status

Tasks 0-8 are completed and reviewed. Processing profiles now drive cleaning, parent-child/semantic chunking, SQLite persistence, child indexing, parent evidence expansion, Knowledge Studio, and all four Retrieval Lab modes. The real local catalog and retrieval indexes have been migrated and rebuilt.

The refreshed 50-question benchmark on the 689-child index found that Vector remains the best fast default. Plain Hybrid RRF matched Vector Hit@5 but reduced MRR from 0.906 to 0.867. Hybrid + Cross-Encoder Rerank reached Hit@5 1.000, Recall@5 0.954, MRR 0.924, and nDCG@5 0.889 at 1.49 seconds average latency. The remaining baseline weakness is freshness ranking; this evidence narrows Phase B to freshness-aware ranking and selective reranker routing.

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

## Known Blockers

No active Phase A blocker. The optional browser-control connector could not attach during final automation, so visual confidence comes from the Streamlit three-page AppTest, HTTP 200 check, and the user's live local browser; functional local and cloud question-answer flows both passed.

See [Known Issues](KNOWN_ISSUES.md) for acceptance criteria and [Testing](TESTING.md) for the evidence contract.
