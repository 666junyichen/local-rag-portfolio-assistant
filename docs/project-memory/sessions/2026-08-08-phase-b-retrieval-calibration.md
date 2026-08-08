# Session: 2026-08-08 Phase B Retrieval Calibration

## Scope

Calibrate local configuration reload, runtime diagnostics, freshness ranking, and adaptive reranker routing. Cloud retrieval behavior and private source data were not changed.

## Changes

- Made the project `.env` authoritative for local settings and added explicit cache reload behavior.
- Separated local UI, database, index, Embedding, and Ollama/model health.
- Kept Vector as the fast path, added bounded freshness ranking, and routed the local Cross-Encoder only for complex or low-confidence questions.
- Added retrieval path, trigger reasons, fallback details, and latency to Chat, Retrieval Lab, and evaluation reports.

## Verification

| Command | Result |
|---|---|
| `.\.venv\Scripts\python.exe -m pytest tests\test_local_runtime.py tests\test_query_planning.py tests\test_retrieval.py tests\test_portfolio_retrieval.py tests\test_streamlit_contract.py -q` | 46 passed, 3 subtests passed |
| `.\.venv\Scripts\python.exe scripts\evaluate_retrieval.py --mode baseline` | Hit@5 0.925, MRR 0.90625, no-answer 1.000, privacy violations 0 |
| `.\.venv\Scripts\python.exe scripts\evaluate_retrieval.py --mode adaptive` | Hit@5 0.975, MRR 0.9167, freshness Hit@5 1.000, no-answer 1.000, privacy violations 0 |
| `.\.venv\Scripts\python.exe -m pytest -q` | 250 passed, 3 subtests passed |
| `.\.venv\Scripts\python.exe -m pytest tests\test_streamlit_contract.py -q` | 7 passed, 3 subtests passed after the standalone checker accepted Adaptive mode |

## Decisions And Concerns

- Plain Hybrid remains an experiment rather than the default because it reduced MRR.
- The reranker remains free and local-only; unavailable models produce a visible Vector fallback.
- Broader Agentic RAG, GraphRAG, OCR, and paid services remain deferred.

## Handoff

- The milestone suite passed and the Phase B branch was fast-forwarded into `main`.
- Collect future Retrieval Lab evidence before changing thresholds or expanding Phase B.
- Confirm [Current State](../CURRENT_STATE.md) and `state.json` agree.
