# Architecture

## Memory Layers

The memory system has three deliberately small layers:

1. `state.json` stores current branch, phase, task state, evidence, blockers, and next action in a machine-readable form.
2. Markdown files provide rationale, operating instructions, and human-readable status without private source content.
3. `scripts/check_project_memory.py` validates structure, consistency, links, privacy patterns, and the private-directory ignore rule.

The validator is dependency-free Python so it can run before project services or optional model dependencies are available. Tests exercise temporary repository fixtures and never rewrite checked-in state.

## Consistency Boundary

`CURRENT_STATE.md` mirrors the fields that matter during handoff: branch, phase, task statuses, verification date, blockers, and next action. Detailed history belongs in session notes and `CHANGELOG.md`; decisions belong in `DECISIONS.md`.

## Privacy Boundary

Tracked memory contains metadata and summaries only. Private working material is isolated under `.project-memory/private/` and excluded by Git. See [Data Privacy](DATA_PRIVACY.md) for the content rules.

## Application Boundary

Task 0 does not alter Phase A application behavior. It is limited to documentation, repository guidance, validation scripts, tests, and ignore configuration.
