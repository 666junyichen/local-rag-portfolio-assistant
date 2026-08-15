# Session: 2026-08-15 Public Chunk Preview Completeness

## Scope

Investigated why the Owner public resume preview appeared to omit project content and updated the Publish Studio preview surface.

## Changes

- Confirmed the server preview contained 35 answer parents and 48 retrieval children.
- Removed the client-side 20-child display cap.
- Added complete retrieval-child and answer-parent views.
- Added a distinct project semantic-group count and explicit matched-child/returned-parent inspection.

## Verification

| Command | Result |
|---|---|
| `npm test -- tests/cloud-publish-preview-view.test.ts tests/cloud-publish-processing.test.ts` | 16 tests passed across 2 files |
| `npm run build` | Next.js production build passed and compiled 19 routes |

## Decisions And Concerns

- Preview completeness and chunk-generation completeness are separate contracts; the UI must never silently truncate generated evidence.
- This change does not alter parsing, semantic chunk boundaries, embeddings, or published Atlas data.

## Handoff

- Review all answer parents in Publish Studio and compare the distinct project-group count with the expected resume project list before publishing.
- [Current State](../CURRENT_STATE.md) and `state.json` agree.
