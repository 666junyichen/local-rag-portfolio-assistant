# Phase A Tasks 3-7

## Goal

Finish hierarchical chunking, SQLite profile persistence, hierarchy-aware retrieval, Knowledge Studio controls, and Retrieval Lab diagnostics.

## Changes

- Added canonical parent and child chunk records with stable IDs and processing-profile hashes.
- Indexed child chunks for Vector/BM25 retrieval and expanded matches to parent evidence.
- Added idempotent SQLite profile migration and startup integration.
- Unified upload preview, library preview, saved configuration, and ingestion around `ProcessingProfile`.
- Added Vector, full-text BM25, Hybrid RRF, and Hybrid + Cross-Encoder modes with diagnostic ranks and fallback reasons.

## Verification

- Focused subsystem checkpoint: 82 tests and 3 Streamlit subtests passed.
- Real Master resume: 28 semantic parents, 40 retrieval children, and seven recognized section types.
- Python compilation and `git diff --check` passed.

## Remaining

Task 8 must run the one milestone suite, migrate and rebuild the real local index after integration, verify the browser flow, update release documentation, merge to `main`, and push.
