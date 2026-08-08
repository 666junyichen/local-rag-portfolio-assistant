# Current State

- Active branch: `feat/phase-b-retrieval-calibration`
- Active phase: `Phase B retrieval calibration`
- Last verified: `2026-08-08`
- Updated: `2026-08-08T18:30:00+10:00`
- Next action: Merge the verified Phase B branch to main, restart the local Streamlit process, and collect future Retrieval Lab evidence before expanding scope.

## Status

Tasks 0-9 are completed and reviewed. Processing profiles drive cleaning, parent-child/semantic chunking, SQLite persistence, child indexing, parent evidence expansion, Knowledge Studio, and Retrieval Lab. Phase B makes the project `.env` authoritative for local settings, separates UI/database/index/model health, keeps Vector as the fast default, adds bounded freshness ranking, and routes the local Cross-Encoder only for complex or low-confidence questions.

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

## Known Blockers

No active Phase A blocker. The optional browser-control connector could not attach during final automation, so visual confidence comes from the Streamlit three-page AppTest, HTTP 200 check, and the user's live local browser; functional local and cloud question-answer flows both passed.

See [Known Issues](KNOWN_ISSUES.md) for acceptance criteria and [Testing](TESTING.md) for the evidence contract.
