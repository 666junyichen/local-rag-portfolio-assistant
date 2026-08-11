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

## Decisions And Concerns

- Real destructive reset execution remains separate from implementation verification so backups can be confirmed against the merged and deployed version.
- Retained repository documents remain untouched and cannot silently repopulate either knowledge base.

## Handoff

- Merge and deploy the guarded implementation, then execute and verify the local and cloud resets.
- [Current State](../CURRENT_STATE.md) and `state.json` agree.
