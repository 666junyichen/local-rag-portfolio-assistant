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

1. Run focused tests for the changed behavior and the full test suite when feasible.
2. Update `state.json`, `CURRENT_STATE.md`, relevant issue/decision/testing documents, `CHANGELOG.md`, and a dated session note.
3. Record exact commands and results. Never describe a partial test checkpoint as phase completion.
4. Run `python scripts/check_project_memory.py` after the updates.
5. Review staged content for credentials, private document bodies, phone numbers, email addresses, and machine-specific absolute paths.
6. Keep private working notes only under `.project-memory/private/`, which must remain ignored.

## Scope And Safety

- Treat `docs/project-memory/state.json` as the machine-readable source of truth and `CURRENT_STATE.md` as its human-readable mirror.
- Use only repository-relative paths in tracked memory files.
- Do not place credentials, environment values, private document excerpts, personal contact details, or local user paths in tracked files.
- Add decisions; do not silently rewrite historical rationale. Correct errors with a dated superseding entry.
