# Current State

- Active branch: `main`
- Active phase: `Shared Chunking Contract`
- Last verified: `2026-08-15`
- Updated: `2026-08-15T17:20:00+10:00`
- Next action: Upload one trusted document locally and publicly, then compare Retrieval Lab evidence without changing embedding providers.

## Status

Tasks 0-14 are completed and reviewed. Owner production acceptance now covers sign-in, email and phone PII blocking, sanitized preview, publication, Knowledge visibility, grounded Retrieve and Chat responses, unpublish, and permanent synthetic-data cleanup. A no-evidence Chat stream regression found during unpublish verification was fixed and deployed; an active empty space now returns a grounded refusal with HTTP 200 instead of a server error.

Task 14 makes the local Python chunker the checked-in contract for cloud TypeScript processing. General, parent-child, and resume-semantic profiles now come from one versioned JSON source; fixed resume, Markdown, and CSV fixtures verify matching parent boundaries, child boundaries, and retrieval metadata. Embedding remains intentionally runtime-specific. The public Knowledge page also exposes an Owner-only upload-and-management entry that fails closed for visitors.

Task 13 is complete. The local catalog was reset from the current runtime and remained empty across two fresh Streamlit starts: zero documents, zero duplicate groups, zero knowledge chunks, and one active `portfolio` space. Normal startup no longer imports the legacy catalog or repository documents.

The Master resume is published as semantic v2 with 35 answer parents and 47 retrieval children. Production retrieval deduplicates parent evidence and restricts project-list questions to project sections. The ranked question returned five distinct project parents; the exhaustive question returned eleven project parents. The deployment for commit `0741793` is Ready.

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
| 13 | completed | true | true | Local empty-state reset and cloud semantic resume v2 retrieval accepted in production |
| 14 | completed | true | true | Shared Python/TypeScript chunking contract and Owner-only Knowledge management entry |

## Known Blockers

No active blockers.

See [Known Issues](KNOWN_ISSUES.md) for acceptance criteria and [Testing](TESTING.md) for the evidence contract.
