# Current State

- Active branch: `main`
- Active phase: `Owner Publish Studio`
- Last verified: `2026-08-10`
- Updated: `2026-08-10T01:11:51+10:00`
- Next action: Complete the Git-triggered production rebuild, then verify Owner sign-in, PII blocking, publication, retrieval, and unpublish.

## Status

Tasks 0-9 are completed and reviewed. Task 10's code, merge, push, public deployment, and visitor acceptance are complete: the cloud app now has an Owner-only Publish Studio, a searchable public Knowledge catalog, transient upload parsing, mandatory PII cleanup, previewable chunking, transactional publication, revision/unpublish/delete/export workflows, and server-side authorization on every admin route. The Clerk Marketplace terms are accepted, the Clerk resource is connected to the Vercel project, and the server-side Owner allowlist is configured as a sensitive Production variable. A new production rebuild and authenticated Owner publication acceptance remain pending.

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
| 10 | in_progress | true | false | Public deployment and visitor acceptance passed; production Clerk login and publication remain pending |

## Known Blockers

- The Vercel CLI session expired during the direct redeploy attempt; the next Git push will trigger the production rebuild instead.

See [Known Issues](KNOWN_ISSUES.md) for acceptance criteria and [Testing](TESTING.md) for the evidence contract.
