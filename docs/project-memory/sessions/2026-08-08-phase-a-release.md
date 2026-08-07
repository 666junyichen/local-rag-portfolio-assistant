# Phase A Release

## Goal

Migrate real local state, rebuild retrieval indexes, run the single milestone suite, verify both runtimes, and release Phase A.

## Verification

- Python milestone: 238 tests and 3 Streamlit subtests passed.
- TypeScript: 10 tests passed; Next.js production build passed.
- Local catalog: 7,048 records migrated to versioned processing profiles.
- Local index: 111 active sources produced 689 child chunks; Vector index reached READY and BM25 text index remained available.
- Local generation: smoke test and a Chinese RAG/MongoDB question returned evidence-grounded answers.
- Cloud health: Atlas, Gemini, and Vector Index reported ready; a public Chinese SSE request returned sources and a Chinese answer.

## Runtime

The local Streamlit process is running on port 8505 with healthy MongoDB and Ollama containers. The public deployment remains Vector-only because the current Atlas environment does not expose a text index.

## Next

Use Retrieval Lab to collect benchmark evidence before deciding whether Phase B features are justified.
