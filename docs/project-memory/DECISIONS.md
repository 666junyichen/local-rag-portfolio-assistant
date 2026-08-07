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
