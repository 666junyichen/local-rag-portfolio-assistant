# Known Issues

## Resolved: Task 2 Quality Blockers

Task 2 was approved on 2026-08-08 after focused regression coverage passed.

| Blocker | Required behavior before approval |
|---|---|
| CJK-adjacent URLs | URL removal must stop at adjacent CJK text and preserve that text and punctuation. |
| IPv6 and new-TLD URLs | Recognize supported IPv6 URL forms and valid contemporary top-level domains without deleting domain-like prose. |
| Unicode-adjacent emails | Remove a valid email without consuming neighboring Unicode letters or punctuation. |
| Apostrophe emails | Handle valid apostrophes in the local part while preserving surrounding prose. |
| CRLF migration behavior | Define and test deterministic behavior for legacy profiles and text using Windows line endings. |

## Resolution Evidence

The focused command `.\.venv\Scripts\python.exe -m pytest tests\test_document_processing.py -q` passed all 38 tests. The full suite remains reserved for the Phase A milestone.

## Resolved: Phase A Release Checkpoint

The real local catalog was migrated, the Vector/BM25 indexes were rebuilt, the milestone suite passed, and local/cloud question-answer flows were verified. The optional automated browser connector could not attach, but all three Streamlit pages passed application rendering tests and the live server returned HTTP 200.

## Remaining Cloud Limitation

The public Atlas deployment currently reports `textIndex=false`, so the public Demo remains on stable Vector Search. Local Retrieval Lab provides BM25, Hybrid RRF, and Hybrid + Rerank. Do not describe cloud BM25 as enabled until Atlas index capacity is available and the public collection is reseeded.
