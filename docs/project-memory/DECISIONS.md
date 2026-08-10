# Decisions

## 2026-08-07: Structured State Is Authoritative

Use `state.json` as the machine-readable source of truth and require `CURRENT_STATE.md` to mirror handoff-critical fields. This supports automation without making contributors read raw JSON for ordinary work.

## 2026-08-07: Validation Stays Dependency-Free

Implement the memory checker with the Python standard library. It must run before services, databases, model downloads, or application dependencies are available.

## 2026-08-07: Temporary Repositories For Validator Tests

Validator behavior is tested with complete temporary fixtures that are corrupted one rule at a time. One read-only integration test validates the checked-in repository. Tests never modify repository memory.

## 2026-08-07: Private Content Is Never Project Memory

Tracked memory may describe private-data boundaries but must not contain private document bodies, personal contact details, credentials, or machine-specific user paths. Local private notes belong only in the ignored directory.

## 2026-08-07: Passing Tests Do Not Imply Phase Approval

Record Task 2's `148 passed` checkpoint while keeping the task in progress. Completion requires the named quality blockers to be fixed and reviewed.

## 2026-08-08: Verification Is Risk-Based And Time-Boxed

Use focused tests during implementation and one full-suite run at a stable task or merge milestone. Combine review findings into one fix pass, limit ordinary review to 15 minutes, and defer non-critical hardening ideas to `KNOWN_ISSUES.md`. This prevents documentation and isolated regex changes from repeatedly loading the entire application test surface.

## 2026-08-08: Phase B Is Retrieval Calibration, Not Feature Expansion

The refreshed 50-question benchmark shows that Vector is the strongest fast default, plain Hybrid RRF lowers ranking quality, and Cross-Encoder reranking provides the best quality at higher latency. Phase B should therefore focus on freshness-aware ranking and routing the reranker only to questions that need higher precision. Agentic RAG, GraphRAG, OCR, and new paid services remain deferred until a measured failure requires them.

## 2026-08-08: Local Configuration Is File-Authoritative

For local Streamlit execution, the repository `.env` overrides stale or empty values inherited from a long-lived shell. Local mode only consumes `LOCAL_MONGODB_URI` and Ollama settings; cloud Atlas and Gemini credentials remain outside the local private-data path.

## 2026-08-08: Adaptive Retrieval Is The Interactive Default

Keep Vector as the fast first pass. Apply deterministic recency features only when the query expresses freshness intent, and invoke the cached local Cross-Encoder only for complex, explicitly requested, or low-confidence queries. If the free local reranker is unavailable, report the fallback and continue with Vector instead of downloading during a request.

## 2026-08-09: Cloud Upload Is Owner-Only And Public-Only

Do not create an anonymous or multi-tenant upload product. Cloud uploads require a Clerk identity whose verified primary email is allowlisted by `OWNER_EMAILS`, and every accepted document is a draft for eventual public publication. Local SQLite, private uploads, and `portfolio_knowledge_local` never enter this path.

## 2026-08-09: Original Cloud Uploads Are Transient

Parse supported files in the request, then discard the original binary. Store only draft text, metadata, processing configuration, PII findings, and preview data with a seven-day TTL. Do not add Vercel Blob until a measured requirement justifies retaining source files.

## 2026-08-09: Catalog Backfills Must Not Spend Embedding Quota

Keep retrieval-chunk seeding separate from document-catalog maintenance. `--catalog-only` may synchronize `repo_seed` document metadata without calling Gemini or rewriting retrieval chunks, while full seed remains responsible for embedding/index contracts. Both modes preserve `owner_upload` records.

## 2026-08-10: Knowledge Spaces Share Collections And Indexes

Represent Portfolio, RAG Learning, Project Docs, and future knowledge areas with a required `space_id` metadata field instead of separate MongoDB collections or indexes. Default to one active space, allow up to five selected public spaces, and preserve at least one candidate from each selected space that returns evidence. Moving a document changes metadata only and does not regenerate embeddings. Local private spaces remain isolated from Vercel and cloud APIs.

## 2026-08-10: Empty Evidence Is A Successful Grounded Refusal

An active knowledge space with no matching evidence returns a normal SSE response containing retrieval, localized refusal, and done events. It must not call Gemini and must not turn absence of evidence into an HTTP 500 error.
