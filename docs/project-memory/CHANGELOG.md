# Project Memory Changelog

## 2026-08-11

- Reduced default knowledge spaces to one empty-ready `Portfolio` space and hid cross-space controls until a second active space exists.
- Added a local Danger Zone with reset scope counts, ignored backups, exact confirmation, catalog/import guards, and cleanup of local chunks, chat, runtime evaluations, and internal upload copies without deleting source files.
- Added an Owner-only cloud Danger Zone with full managed-data export, embedding-free backup, SHA-256 state fingerprint, exact confirmation, and collection-scoped reset.
- Made repository Atlas seed validation-only by default and required an explicit apply command to write retained public JSON back to Atlas.
- Limited duplicate and version analysis to active manual uploads in the current space after reset.

## 2026-08-10

- Added Knowledge Spaces across cloud and local schemas, APIs, retrieval settings, source evidence, and user interfaces.
- Added Portfolio, RAG Learning, and Project Docs defaults plus Owner space management and document moves without re-embedding.
- Added single-space isolation and up-to-five-space retrieval with per-space candidate preservation.
- Completed the Owner production publication lifecycle using a removable synthetic document and left no test data in the public catalog.
- Fixed empty-space Chat streaming so a no-evidence query returns a localized grounded refusal instead of HTTP 500.
- Limited Vitest discovery to the main repository so historical worktrees no longer duplicate test execution.
- Fixed MongoDB Local knowledge-space migration by rebuilding only the Vector Search index definition while preserving existing embeddings and source documents.

## 2026-08-09

- Added a searchable public Knowledge catalog that exposes only allowlisted document metadata.
- Added Clerk-backed Owner authorization with verified-email allowlisting and server-side checks on every admin route.
- Added Publish Studio draft, parse, clean, PII-check, chunk-preview, publish, revise, unpublish, delete, and export workflows.
- Added PDF, DOCX, Markdown, TXT, and CSV cloud parsing while keeping original uploads transient.
- Added transactional and idempotent publication so concurrent retries do not duplicate chunks or versions.
- Added a seven-day TTL for unpublished cloud drafts and graceful Gemini free-quota retry behavior.
- Hardened repository seed operations so they preserve Owner uploads and validate embedding/index contracts.
- Added a catalog-only seed mode that backfills metadata without spending Gemini embedding quota.
- Restored compatibility with the existing Atlas Vector Index by applying non-indexed validity checks after Vector Search.

## 2026-08-08

- Added a local configuration reload action that clears Streamlit resource and reranker caches.
- Split local runtime diagnostics into UI, configuration, MongoDB, Vector index, BM25 index, Embedding, and Ollama/model status.
- Added adaptive retrieval with freshness-aware ranking and selective local Cross-Encoder reranking.
- Added actual retrieval path, reranker decision, fallback reason, and latency diagnostics to Chat and Retrieval Lab.
- Kept Vector Search as the fast default after benchmark evidence showed plain Hybrid RRF reduced ranking quality.
- Made repeated local startup idempotent when a healthy Streamlit server already owns port 8505.
- Added parent-child and resume-semantic chunk hierarchies with child retrieval and parent evidence expansion.
- Added persisted processing profiles for cleaning, delimiters, parent/child limits, and preprocessing rules.
- Added standalone BM25 full-text retrieval plus Vector, Hybrid RRF, and Hybrid + Rerank diagnostics.
- Unified Knowledge Studio preview, library inspection, saved configuration, and ingestion boundaries.
- Added a risk-based, 15-minute verification and review budget to prevent repeated full-suite runs for small changes.
- Required both the private directory and child probe to be ignored by the repository `.gitignore`, excluding file-only and local Git exclude rules.
- Replaced private-ignore text matching with an effective Git probe, including wildcard-negation, restored-precedence, and command-failure coverage.
- Normalized equivalent private-directory ignore and negation forms with ordered precedence.
- Added typed passed/failed evidence outcomes and passed-evidence approval gates.
- Enforced the exact ordered blocker list under the intended current-state section.
- Rejected bare and descendant POSIX user-home paths.
- Parsed labeled current-state metadata and enforced exact field equality.
- Rejected local POSIX user-home paths while preserving HTTP/HTTPS URL paths.
- Enforced reviewed and final-quality approval evidence/status invariants.
- Limited drive-like path exceptions to actual HTTP and HTTPS URLs.
- Enforced exact task-ID set equality between structured and human-readable state.
- Rejected boolean task IDs through exact integer type validation.
- Scoped task-row parsing to the intended status table while preserving duplicate detection.
- Added UNC-path rejection without treating drive-like URL path segments as local paths.
- Rejected duplicate task rows in the human-readable state table.
- Expanded machine-specific path detection to every Windows drive and both separator styles.
- Required evidence command and result values to be non-empty strings.

## 2026-08-07

- Required and type-checked task review and final-quality approval fields.
- Added approval-field drift detection between structured and human-readable state.
- Made the tracked private-note template a required project-memory file.
- Added the mandatory repository start/end protocol.
- Added structured state and the human-readable Phase A status mirror.
- Recorded Task 1 as completed/reviewed, Task 2 as in progress, and Tasks 3-8 as pending.
- Recorded all five Task 2 quality blockers and the next action.
- Added the dependency-free validator and temporary-fixture test coverage.
- Added the ignored private-memory boundary and safe tracked templates.
