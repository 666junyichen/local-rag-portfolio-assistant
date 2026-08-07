# Session: 2026-08-08 Verification Budget

## Scope

Diagnose why Task 0 consumed several hours and establish a durable time/token budget for future work.

## Changes

- Identified repeated full-suite runs and repeated fresh review contexts as the main cost.
- Added focused, task-checkpoint, and milestone verification levels.
- Limited ordinary review to 15 minutes and one consolidated fix/recheck cycle.
- Reserved full Python, TypeScript, browser, model, and database checks for surfaces that changed or final milestones.

## Verification

| Command | Result |
|---|---|
| `git log --since=2026-08-07` | Confirmed repeated Task 0 review-fix commits and full-suite checkpoints |
| `python scripts/check_project_memory.py` | Project memory validation passed |
| `python -m pytest tests/test_project_memory.py -q` | 77 passed in 88.34 seconds |

## Decisions And Concerns

- The full Python suite currently takes roughly 2.5 minutes; the multi-hour delay came primarily from repeating it after small fixes and repeatedly starting fresh review contexts.
- High-severity privacy, security, data-loss, and core-functional defects remain exceptions to the review time box.

## Handoff

- Validate this protocol with focused project-memory tests only.
- Resume Task 2 using focused tests, one consolidated review, and one milestone full-suite run.
