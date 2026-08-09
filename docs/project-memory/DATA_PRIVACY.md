# Data Privacy

## Never Track

- Credentials, access tokens, key values, secrets, or environment assignment lines.
- Private document bodies or excerpts.
- Phone numbers, personal email addresses, or other direct contact details.
- Absolute paths containing a local user profile.
- Bare or descendant POSIX user-home paths under `/Users` or `/home`.
- Generated local catalogs, uploads, or private evaluation material.

## Safe To Track

- Repository-relative file paths.
- Task status, test counts, commit identifiers, and non-sensitive commands.
- Abstract descriptions of defects and architecture.
- Sanitized templates that contain no copied source content.

## Local Notes

Store private working notes only under `.project-memory/private/`. That directory is ignored and must never be force-added. Start from [the safe template](PRIVATE_NOTE_TEMPLATE.md), then keep the populated copy local.

The validator scans public project-memory files and `AGENTS.md` for credential-like assignments, key labels with values, and local Windows user paths. This is a guardrail, not a replacement for reviewing staged changes.

## Runtime Boundaries

- Local private documents may be stored in the ignored SQLite catalog and the local MongoDB collection. They are processed with local embedding and Ollama models.
- Vercel never connects to the local SQLite catalog, local uploads, or the local MongoDB collection.
- Cloud publication only accepts documents deliberately uploaded by the authenticated Owner for public release.
- The original cloud-uploaded file is parsed in memory and discarded. Atlas stores draft text and metadata, not the original PDF or Word file.
- Drafts expire automatically. Published document metadata and retrieval chunks remain until the Owner unpublishes or deletes them.

## Publication Controls

- Server-side Clerk authorization protects every administrative endpoint.
- The Owner must use a verified email address listed in `OWNER_EMAILS`.
- PII checks cover email addresses, phone numbers, identity-card patterns, and explicitly labelled home addresses. A draft with findings cannot be published.
- Gemini only receives chunks after the PII gate passes and the Owner explicitly confirms publication.
- The public Knowledge API exposes a small metadata allowlist. It never returns cleaned text, embeddings, draft fields, account identifiers, or private processing configuration.

## Seed Safety

Repository seed synchronization is scoped to `source_origin=repo_seed`. It must not call an unscoped collection-wide deletion, so Owner-published documents survive future seed updates.
