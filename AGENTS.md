# Repository Agent Protocol

This protocol is mandatory for every agent or contributor working in this repository. The files under [project memory](docs/project-memory/README.md) are the durable handoff record; chat history is not a substitute.

## Start Protocol

Before changing files, you MUST:

1. Read `docs/project-memory/state.json` and `docs/project-memory/CURRENT_STATE.md`.
2. Read `docs/project-memory/KNOWN_ISSUES.md`, `docs/project-memory/DECISIONS.md`, and the latest file in `docs/project-memory/sessions/`.
3. Confirm the current Git branch and working-tree status. Do not discard changes you did not create.
4. Run `python scripts/check_project_memory.py` and resolve memory drift before application work.
5. Select the recorded `next_action`, or update the memory files first when priorities have changed.

## End Protocol

Before handing off or committing completed work, you MUST:

1. Run focused tests for the changed behavior. Run the full test suite once, only after the task is stable or at a merge/handoff milestone.
2. Update `state.json`, `CURRENT_STATE.md`, relevant issue/decision/testing documents, `CHANGELOG.md`, and a dated session note.
3. Record exact commands and results. Never describe a partial test checkpoint as phase completion.
4. Run `python scripts/check_project_memory.py` after the updates.
5. Review staged content for credentials, private document bodies, phone numbers, email addresses, and machine-specific absolute paths.
6. Keep private working notes only under `.project-memory/private/`, which must remain ignored.

## Time And Cost Budget

- During red-green-refactor loops, run only the directly affected test module or test case. Do not run the full suite after each small fix.
- Documentation-only changes run the project-memory validator and focused documentation tests. They do not trigger model, database, browser, or full application tests.
- Use one implementation pass, one combined spec/quality review, and at most one consolidated fix-and-recheck cycle per task. Additional non-critical edge cases go to `KNOWN_ISSUES.md` for a later hardening task.
- Stop a review after 15 minutes and report the current result. Continue only when a high-severity privacy, data-loss, security, or core-functional defect remains.
- Reuse the same reviewer for rechecks when possible. Do not create a fresh reviewer for every small patch.
- Record only the latest focused result and latest milestone result in `state.json`. Detailed intermediate history belongs in the dated session note.
- Before running any expensive command, state why it is needed and whether a cheaper focused check can answer the same question.

## Scope And Safety

- Treat `docs/project-memory/state.json` as the machine-readable source of truth and `CURRENT_STATE.md` as its human-readable mirror.
- Use only repository-relative paths in tracked memory files.
- Do not place credentials, environment values, private document excerpts, personal contact details, or local user paths in tracked files.
- Add decisions; do not silently rewrite historical rationale. Correct errors with a dated superseding entry.
