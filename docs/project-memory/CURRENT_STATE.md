# Current State

- Active branch: `feat/adaptive-retrieval-parity`
- Active phase: `Adaptive Retrieval Parity`
- Last verified: `2026-08-22`
- Updated: `2026-08-22T20:06:59+10:00`
- Next action: Rerun the Atlas `--spaces-only` migration when SRV DNS connectivity is healthy, then rerun a current-corpus cloud benchmark keyed to the published Master resume semantic parents before changing the public default. Keep Vector as the cloud default unless adaptive or hybrid strictly beats the baseline without no-answer or privacy regression. Owner must still review Publish Studio answer parents before publishing new resume drafts.

## Status

Tasks 0-16 are completed and reviewed. Owner production acceptance covers sign-in, email and phone PII blocking, sanitized preview, publication, Knowledge visibility, grounded Retrieve and Chat responses, unpublish, and permanent synthetic-data cleanup. A no-evidence Chat stream regression found during unpublish verification was fixed and deployed; an active empty space now returns a grounded refusal with HTTP 200 instead of a server error.

Task 16 aligns local and cloud retrieval decisions without merging their data boundaries. Upload processing profile recommendations now prefer document structure and body evidence before weak file-name hints: short generic documents stay Standard, long generic documents use Parent-child, and resumes can be detected from title or multi-section resume body structure. Cloud `/api/retrieve` and Chat now accept `vector`, `bm25`, `hybrid`, `hybrid-rerank`, and `adaptive`, and return requested mode, applied mode, capabilities, fallback reason, and source path. If Atlas Search is unavailable, cloud BM25/Hybrid/Adaptive precision paths report a Vector fallback instead of silently pretending Hybrid is active.

Task 16 also makes `text_index_public` reconciliation explicit in the Atlas seed script and adds a public-safe `/api/retrieve` benchmark script. The benchmark writes ignored reports under `evals/latest-cloud-retrieval*.json` and now requires a candidate to produce positive retrieval quality and strictly beat Vector before recommending a default switch. Production deployment `dpl_HC25hFeSYj8ibiXPsiKF5oQCXnSF` is Ready and aliased to the public URL. A live production probe returned one published Owner document, `陈君奕简历 - Master`, with 47 vector candidates; the old 50-question repo-document benchmark is therefore not aligned with the current single-document semantic-resume corpus and must not be used to promote Hybrid.

Task 15 fixes a Publish Studio presentation defect that made complete resume-semantic output look incomplete. The server generated 35 answer parents and 48 retrieval children, but the page rendered only the first 20 children. The Studio now exposes all generated chunks, switches between child matches and parent answer contexts, and reports distinct project semantic groups.

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
| 15 | completed | true | true | Complete public parent/child preview with distinct project-group evidence |
| 16 | completed | true | true | Adaptive retrieval contract, cloud fallback diagnostics, text-index reconciliation, and public benchmark script |

## Known Blockers

- Atlas SRV DNS lookups for the public cluster time out from this environment, so the `text_index_public` migration cannot be rerun locally even though production retrieval can reach Atlas.

See [Known Issues](KNOWN_ISSUES.md) for acceptance criteria and [Testing](TESTING.md) for the evidence contract.
