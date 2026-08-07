# Data Privacy

## Never Track

- Credentials, access tokens, key values, secrets, or environment assignment lines.
- Private document bodies or excerpts.
- Phone numbers, personal email addresses, or other direct contact details.
- Absolute paths containing a local user profile.
- Generated local catalogs, uploads, or private evaluation material.

## Safe To Track

- Repository-relative file paths.
- Task status, test counts, commit identifiers, and non-sensitive commands.
- Abstract descriptions of defects and architecture.
- Sanitized templates that contain no copied source content.

## Local Notes

Store private working notes only under `.project-memory/private/`. That directory is ignored and must never be force-added. Start from [the safe template](PRIVATE_NOTE_TEMPLATE.md), then keep the populated copy local.

The validator scans public project-memory files and `AGENTS.md` for credential-like assignments, key labels with values, and local Windows user paths. This is a guardrail, not a replacement for reviewing staged changes.
