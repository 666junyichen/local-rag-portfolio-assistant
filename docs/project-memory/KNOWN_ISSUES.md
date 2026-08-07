# Known Issues

## Task 2 Quality Blockers

Task 2 remains in progress despite a latest checkpoint of `148 passed`. Passing existing tests is necessary but does not resolve the missing boundary cases below.

| Blocker | Required behavior before approval |
|---|---|
| CJK-adjacent URLs | URL removal must stop at adjacent CJK text and preserve that text and punctuation. |
| IPv6 and new-TLD URLs | Recognize supported IPv6 URL forms and valid contemporary top-level domains without deleting domain-like prose. |
| Unicode-adjacent emails | Remove a valid email without consuming neighboring Unicode letters or punctuation. |
| Apostrophe emails | Handle valid apostrophes in the local part while preserving surrounding prose. |
| CRLF migration behavior | Define and test deterministic behavior for legacy profiles and text using Windows line endings. |

## Resolution Rule

Each blocker needs a failing regression test first, an implementation fix, focused passing evidence, and a full-suite run. Task 2 remains `in_progress` and `final_quality_approved` remains false until all five cases pass review.
