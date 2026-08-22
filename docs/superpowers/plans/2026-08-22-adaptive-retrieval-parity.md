# Adaptive Retrieval Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make local and cloud retrieval share the same processing-profile and retrieval-mode decisions while preserving private/local and public/cloud data isolation.

**Architecture:** Keep parsing/chunking and retrieval contracts shared, but keep runtime adapters separate. Upload chooses a persisted processing profile from document structure and body evidence first; query execution accepts a versioned retrieval mode and reports the applied path, capabilities, and fallback reason. Cloud uses Vector-only when Atlas Search text index is unavailable and can switch to BM25/Hybrid only after `text_index_public` is queryable.

**Tech Stack:** Python 3.11, TypeScript, Next.js, MongoDB Atlas Vector Search/Search, Vitest, pytest.

---

### Task 1: Processing Profile Contract

**Files:**
- Modify: `lib/cloud-publish/processing.ts`
- Modify: `src/processing_profiles.py`
- Test: `tests/cloud-publish-processing.test.ts`
- Test: `tests/test_processing_profiles.py`

- [ ] Add failing tests showing resume markers in the body/title override misleading generic file names, and generic file names do not force resume mode without resume structure.
- [ ] Implement minimal marker scoring using document structure and body before file name hints.
- [ ] Run `npm.cmd test -- tests/cloud-publish-processing.test.ts tests/cloud-shared-processing-profiles.test.ts`.
- [ ] Run `python -m pytest tests/test_processing_profiles.py -q`.

### Task 2: Cloud Retrieval Contract And Fallback

**Files:**
- Modify: `lib/cloud-rag/types.ts`
- Modify: `lib/cloud-rag/retrieval.ts`
- Modify: `app/api/retrieve/route.ts`
- Modify: `app/api/chat/route.ts`
- Test: `tests/cloud-rag.test.ts`
- Test: `tests/cloud-retrieve-route.test.ts`
- Test: `tests/cloud-chat-route.test.ts`

- [ ] Add failing tests for requested mode `hybrid` falling back to actual mode `vector` when text search is unavailable.
- [ ] Add failing tests for `adaptive` reporting vector fast path when text search and rerank capabilities are unavailable.
- [ ] Implement a versioned retrieval settings contract with requested/applied mode, capability flags, retrieval path, fallback reason, and diagnostics.
- [ ] Run `npm.cmd test -- tests/cloud-rag.test.ts tests/cloud-retrieve-route.test.ts tests/cloud-chat-route.test.ts`.

### Task 3: Atlas Text Index And Benchmark Gate

**Files:**
- Modify: `scripts/seed-atlas.mjs`
- Create: `scripts/evaluate-cloud-retrieval.mjs`
- Test: `tests/cloud-seed-safety.test.ts`
- Test: `tests/cloud-rag.test.ts`

- [ ] Add failing tests for text index creation/update result reporting without deleting unrelated indexes.
- [ ] Add a public-safe cloud retrieval benchmark that compares vector and adaptive/hybrid only when capabilities exist.
- [ ] Keep adaptive as a measured candidate rather than the public default unless benchmark results beat vector without privacy or no-answer regression.
- [ ] Run `npm.cmd test -- tests/cloud-seed-safety.test.ts tests/cloud-rag.test.ts`.

### Task 4: Documentation, Memory, Verification, Delivery

**Files:**
- Modify: `README.md`
- Modify: `docs/project-memory/CURRENT_STATE.md`
- Modify: `docs/project-memory/KNOWN_ISSUES.md`
- Modify: `docs/project-memory/DECISIONS.md`
- Modify: `docs/project-memory/TESTING.md`
- Modify: `docs/project-memory/state.json`
- Create: `docs/project-memory/sessions/2026-08-22-adaptive-retrieval-parity.md`

- [ ] Document that local and cloud share retrieval decisions but remain separate data boundaries.
- [ ] Record exact tests, current limitations, and the cloud benchmark gate.
- [ ] Run focused Python and TypeScript tests plus `npm.cmd run build`.
- [ ] Run `python scripts/check_project_memory.py`.
- [ ] Review staged changes for secrets, private bodies, local absolute paths, and unintended user edits.
- [ ] Commit, push the feature branch, deploy the verified branch, and report local plus public links.
