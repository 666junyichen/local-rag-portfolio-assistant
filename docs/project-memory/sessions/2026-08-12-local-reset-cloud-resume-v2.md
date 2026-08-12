# 2026-08-12 Local Reset And Cloud Resume v2

## Goal

Make the local reset remain empty across restarts and improve public resume retrieval so answer evidence is complete, distinct, and traceable to semantic sections.

## Changes

- Removed implicit legacy catalog import from ordinary local startup.
- Allowed zero-document local indexes without forced ingestion or smoke generation.
- Added a backup-gated terminal reset entrypoint.
- Added cloud resume-semantic parent/child chunking and persisted entity metadata.
- Upgraded old resume revisions from generic parent-child configuration.
- Split child candidates from deduplicated parent answer context.
- Added exhaustive and ranked answer intent limits plus finish-reason reporting.

## Focused Verification

- Local reset/empty-runtime group: 29 passed.
- Cloud publication/retrieval/generation group: 32 passed.
- A first Vitest launch hit a transient Windows Rollup DLL lock; an immediate retry passed without dependency changes.
- Milestone verification passed 274 Python tests plus 3 subtests, 82 TypeScript tests, the Next.js production build, and all three Streamlit pages.
- The build found that Mammoth has no `convertToMarkdown` API. A failing parser test was added, DOCX conversion was changed to supported HTML parsing with structural preservation, and 22 focused tests plus a fresh build passed.

## Pending Acceptance

- Run one final milestone suite.
- Execute and verify the real local reset from the merged commit.
- Deploy production and republish the Master resume as v2.
- Verify public exhaustive and ranked questions and source deduplication.
