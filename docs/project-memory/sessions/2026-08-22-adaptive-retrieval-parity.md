# Session: 2026-08-22 Adaptive Retrieval Parity

## Scope

Unify local and cloud retrieval decision contracts while preserving the existing local-private and cloud-public data boundary. This change does not publish private documents, change embedding models, delete Atlas indexes, or make cloud Hybrid the default.

## Changes

- Updated Python and TypeScript processing profile recommendations so document structure and body evidence can select resume-semantic processing before weak file-name hints.
- Kept short generic documents on Standard processing, long generic documents on Parent-child, and structured CSV/JSON files on compact Standard processing.
- Added the cloud retrieval mode contract: `vector`, `bm25`, `hybrid`, `hybrid-rerank`, and `adaptive`.
- Added cloud retrieval diagnostics with requested mode, applied mode, capability flags, fallback reason, reranker reasons, and source retrieval path.
- Changed cloud Atlas Search failure from a silent empty BM25 set into an explicit Vector fallback.
- Added structured `text_index_public` reconciliation in `scripts/seed-atlas.mjs` without deleting unrelated search indexes or overwriting existing analyzer fields.
- Added `scripts/evaluate-cloud-retrieval.mjs` and `npm run evaluate:cloud` for public `/api/retrieve` benchmark runs.
- Kept `/api/health` green when Atlas, Gemini, and Vector Search are ready, while exposing text search as an optional capability flag.

## Verification

| Command | Result |
|---|---|
| `npm.cmd test -- tests/cloud-rag.test.ts tests/cloud-chat-route.test.ts tests/cloud-retrieve-route.test.ts tests/cloud-seed-safety.test.ts tests/cloud-publish-processing.test.ts tests/cloud-shared-processing-profiles.test.ts tests/cloud-health-route.test.ts` | 41 tests passed across 7 files |
| `.\.venv\Scripts\python.exe -m pytest tests/test_processing_profiles.py tests/test_query_planning.py tests/test_portfolio_retrieval.py tests/test_project_memory.py -q` | 147 passed |
| `node scripts/evaluate-cloud-retrieval.mjs --limit=1 --modes=vector --base-url=http://127.0.0.1:9 --out=evals/latest-cloud-retrieval-smoke.json` | Script handled an unreachable URL and wrote an ignored report |
| `npm.cmd run build` | Next.js production build passed with 19 pages and API routes |
| `npx.cmd tsc --noEmit` | Still fails only in pre-existing test typing issues outside the changed retrieval implementation |

## Decisions And Concerns

- Cloud and local share mode names and decision semantics, but not private data, collections, embeddings, or model runtimes.
- Cloud BM25/Hybrid is a capability, not a promise. If `text_index_public` is unavailable, cloud retrieval reports Vector fallback.
- Keep Vector as the public default until the cloud benchmark proves adaptive or hybrid improves retrieval without no-answer or privacy regression.

## Handoff

- Push and deploy this branch, then run `npm run evaluate:cloud -- --base-url=<deployed-url> --modes=vector,adaptive,hybrid`. If `/api/health` still reports `textIndex=false`, treat adaptive/hybrid results as capability-degraded and rerun after `text_index_public` becomes READY.
- Owner must still review every Publish Studio answer parent before publishing any new resume draft.
