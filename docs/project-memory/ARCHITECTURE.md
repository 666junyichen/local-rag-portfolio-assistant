# Architecture

## Product Modes

The repository has two deliberately isolated RAG runtimes:

1. **Local private mode** uses Streamlit, MongoDB Atlas Local, SentenceTransformers, and Ollama. It can process private local documents and never sends them to Vercel or Gemini.
2. **Cloud public mode** uses Next.js, Vercel Functions, MongoDB Atlas Vector Search, and Gemini. It only retrieves documents explicitly published to the public collection.

The local and cloud modes use separate collections, embedding models, indexes, and configuration variables. A document never crosses the privacy boundary implicitly.

## Cloud Roles

The public application supports two roles:

- **Visitor**: can use Ask AI, inspect citations, browse the public Knowledge catalog, and run the read-only Retrieval Lab.
- **Owner**: signs in through Clerk and must match a verified address in `OWNER_EMAILS`. Only the Owner can access Publish Studio and `/api/admin/*`.

Authorization is enforced by server routes. Hiding the Studio navigation is only a user-interface convenience and is not the security boundary.

## Owner Publish Flow

```text
Owner sign-in
  -> upload PDF, DOCX, Markdown, TXT, or CSV
  -> parse in the request and discard the original file
  -> save a seven-day draft containing text and processing metadata
  -> edit and clean text
  -> block publication while PII findings remain
  -> preview Standard, Parent-child, or Resume semantic chunks
  -> create Gemini embeddings for approved child chunks
  -> publish document metadata and vector chunks atomically
```

Publication uses deterministic document and chunk identifiers plus a publication version. Retrying a completed request does not create duplicate searchable chunks. Unpublishing removes the document from retrieval while preserving revision history until the Owner permanently deletes it.

## Cloud Collections

- `portfolio_public_drafts`: temporary Owner drafts with a TTL expiry.
- `portfolio_public_documents`: document-level catalog, revisions, public metadata, and publication status.
- `portfolio_knowledge_public`: public retrieval chunks and embeddings.

Repository seed documents use `source_origin=repo_seed`; Publish Studio documents use `source_origin=owner_upload`. The seed command only replaces repository-seeded records and never removes Owner uploads.

## Retrieval Boundary

Public APIs only retrieve `visibility=public` and currently valid chunks. Embeddings are generated from retrieval child chunks; citations and answer context expand to the corresponding parent content where available. The public Knowledge endpoint returns catalog metadata only, never cleaned bodies, embeddings, Owner identifiers, draft data, or processing internals.

## Project Memory

`state.json` stores active work and evidence in machine-readable form. Markdown files provide rationale and runbooks, and `scripts/check_project_memory.py` validates consistency and privacy. Detailed history belongs in session notes and `CHANGELOG.md`; durable choices belong in `DECISIONS.md`.

See [Data Privacy](DATA_PRIVACY.md) for the content and deployment rules.
