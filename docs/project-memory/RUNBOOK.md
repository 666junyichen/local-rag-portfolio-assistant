# Runbook

## Start A Session

1. Follow the mandatory start protocol in [AGENTS.md](../../AGENTS.md).
2. Read [Current State](CURRENT_STATE.md) and [Known Issues](KNOWN_ISSUES.md).
3. Confirm branch and worktree status.
4. Run the project-memory validator.
5. Work on the recorded next action with failing tests first.

## End A Session

1. Run focused tests and the full suite when feasible.
2. Update `state.json` first, then mirror it in `CURRENT_STATE.md`.
3. Update issues, decisions, testing evidence, roadmap, and changelog when their facts changed.
4. Create a session note from [the session template](sessions/TEMPLATE.md).
5. Run the validator and review the staged diff for private or machine-specific content.

## Update State Safely

- Use only `pending`, `in_progress`, `blocked`, or `completed`.
- Give every completed task at least one test-evidence object.
- Use ISO dates and a timezone-qualified ISO datetime.
- Keep blockers and next action concrete.
- Do not mark a phase complete from a passing count alone.

## Recover From Validation Failure

Read every `ERROR:` line, correct the source file, and rerun the validator. Do not weaken a rule merely to accept an inconsistent repository. If a rule itself is wrong, add a failing temporary-fixture test that demonstrates the intended replacement behavior before changing the checker.
