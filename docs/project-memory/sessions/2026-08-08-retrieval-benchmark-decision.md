# Retrieval Benchmark Decision

## Goal

Resolve the duplicate local startup warning, refresh retrieval evidence on the Phase A index, and use measured results to constrain Phase B.

## Changes

- Made `start-local.ps1` idempotent when a healthy Streamlit server already owns port 8505.
- Re-ran all three 50-question retrieval modes on the current 111-source, 689-child local index.
- Updated public documentation and project memory with the measured results and Phase B decision.

## Verification

- Vector: Hit@5 0.925, Recall@5 0.838, MRR 0.906, nDCG@5 0.830, 182 ms.
- Hybrid RRF: Hit@5 0.925, Recall@5 0.838, MRR 0.867, nDCG@5 0.813, 93 ms.
- Hybrid + Rerank: Hit@5 1.000, Recall@5 0.954, MRR 0.924, nDCG@5 0.889, 1.49 s.
- Every mode retained no-answer accuracy 1.000 and zero privacy violations.
- `tests/test_local_runtime.py`: 10 passed.
- A repeated local startup returned success and reported the healthy existing server.

## Decision

Keep Vector as the fast default. Use the reranker as an explicit high-precision path and investigate adaptive routing plus freshness-aware ranking in Phase B. Do not begin broad Agentic RAG work without new benchmark evidence.
