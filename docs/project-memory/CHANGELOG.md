# Project Memory Changelog

## 2026-08-08

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
