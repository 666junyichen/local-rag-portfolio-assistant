# Session: 2026-08-11 Safe Knowledge Reset

## Scope

Implement one default Portfolio space and guarded local/cloud reset workflows without changing retained repository documents or external private source files.

## Changes

- Removed empty template spaces from runtime defaults and hid cross-space controls when only Portfolio exists.
- Added local reset preview, whole-catalog duplicate/version counts, ignored backup creation, exact confirmation, cleanup, and import guards.
- Added Owner cloud reset preview, embedding-free JSON backup, state fingerprint, exact confirmation, and managed-collection cleanup.
- Changed repository Atlas seed to validation-only by default with an explicit apply command.
- Scoped version and duplicate analysis to active manual uploads in the current space.

## Verification

| Command | Result |
|---|---|
| `.\\.venv\\Scripts\\python.exe -m pytest -q` | 270 passed, 3 subtests passed |
| `npm test` | 66 passed across 13 Vitest files |
| `npm run build` | Next.js production build passed with 19 pages and API routes |
| `.\\.venv\\Scripts\\python.exe scripts\\check_streamlit_pages.py` | All three Streamlit pages and five retrieval modes passed |
| Guarded local reset | Backed up and cleared 7,049 documents, 689 chunks, 23 chat messages, and three runtime evaluation files; one empty Portfolio space remains |
| Guarded production reset | Fingerprint-verified backup captured three spaces, one draft, 27 documents, and 27 chunks; deployed APIs now report one Portfolio space and zero knowledge documents |

## Decisions And Concerns

- Local and cloud backups remain in `.project-memory/private/backups/` and are excluded from Git and indexing.
- Retained repository documents remain untouched and cannot silently repopulate either knowledge base.

## Handoff

- Manually upload three to five trusted Portfolio files, review parsing/cleaning/PII/chunks, rebuild the local index, and create expected-source Retrieval Lab questions.
- [Current State](../CURRENT_STATE.md) and `state.json` agree.
