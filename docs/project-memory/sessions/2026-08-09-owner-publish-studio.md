# Session: 2026-08-09 Owner Publish Studio

## Scope

Complete the public Owner publishing workflow, public Knowledge catalog, authentication boundary, seed compatibility, retrieval regression fix, documentation, and deployment readiness.

## Changes

- Added Clerk-backed Owner authorization for Publish Studio and all administrative APIs.
- Added the public Knowledge catalog with a metadata-only response contract.
- Added upload parsing, PII blocking, cleaning, chunk preview, publish, revise, unpublish, archive, delete, and export workflows.
- Added draft TTL handling, deterministic publication identifiers, and transaction-safe lifecycle operations.
- Preserved Owner uploads during repository seed synchronization and added a catalog-only backfill mode.
- Corrected the Atlas Vector Search filter so only indexed fields are used in the vector prefilter.
- Added responsive desktop and mobile interfaces plus explicit fail-closed states when Clerk is not configured.

## Verification

| Command | Result |
|---|---|
| `npm test` | 46 tests passed across 9 files |
| `npm run build` | Next.js production build passed; all routes compiled |
| `python -m pytest` | 251 tests passed with 3 subtests |
| `node scripts/seed-atlas.mjs --catalog-only` | 27 repository documents backfilled without generating embeddings |
| Browser checks | Public catalog, Chinese chat, Retrieval Lab, mobile layout, and fail-closed Owner route verified |

## Decisions And Concerns

- Original cloud uploads are intentionally not persisted.
- Cloud drafts expire after seven days and cannot publish while PII findings remain.
- Clerk production login remains an external deployment gate until Marketplace terms and production keys are configured.
- Public retrieval remains isolated from all local private data.

## Handoff

- Validate the project-memory documents, review and commit the branch, then merge and deploy the public application.
- Configure Clerk production keys and `OWNER_EMAILS`, then verify the complete Owner login and publication flow on Vercel.
- [Current State](../CURRENT_STATE.md) and `state.json` record the same next action and blocker.
