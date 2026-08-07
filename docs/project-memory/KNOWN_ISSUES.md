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

## Phase A Release Checkpoint

Tasks 3-7 have no known code blocker after the 82-test subsystem checkpoint. Task 8 still must migrate the real local catalog after merge, rebuild the local Vector/BM25 indexes, run the one milestone suite, and complete browser acceptance before Phase A is released.
