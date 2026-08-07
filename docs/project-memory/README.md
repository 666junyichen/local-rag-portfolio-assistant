# Project Memory

Project memory is the durable, privacy-safe handoff layer for Phase A. It records what is true now, why important choices were made, what was verified, and what the next session should do.

## Read Order

1. [Current state](CURRENT_STATE.md)
2. [Known issues](KNOWN_ISSUES.md)
3. [Architecture](ARCHITECTURE.md)
4. [Roadmap](ROADMAP.md)
5. [Runbook](RUNBOOK.md)
6. Latest note in [sessions](sessions/TEMPLATE.md)

`state.json` is authoritative for structured status. `CURRENT_STATE.md` must mirror its branch, phase, task statuses, blockers, verification date, and next action. Run `python scripts/check_project_memory.py` after every memory update.

Private notes belong only in `.project-memory/private/`. Use [the safe private-note template](PRIVATE_NOTE_TEMPLATE.md) to create a local note without copying sensitive source material.
