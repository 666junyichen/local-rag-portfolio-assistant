# Roadmap

Phase A follows the approved implementation plan in task order. A later task may begin only when its prerequisites are complete or the state file records an explicit reason to work out of order.

| Task | Outcome | Current status |
|---|---|---|
| 0 | Persistent project memory | completed |
| 1 | Versioned processing profiles | completed and reviewed |
| 2 | Configurable cleaning and structural units | completed and reviewed |
| 3 | Canonical general, resume, and parent-child chunking | completed and reviewed |
| 4 | SQLite profile migration and persistence | completed and reviewed |
| 5 | Hierarchy-aware ingestion and retrieval | completed and reviewed |
| 6 | Dify-style Knowledge Studio controls | completed and reviewed |
| 7 | Retrieval Lab consistency and diagnostics | completed and reviewed |
| 8 | Migration, integration, and documentation | completed and reviewed |
| 12 | Single-space defaults and safe knowledge reset | implementation verified; real resets pending |

Phase A is complete. The benchmark-supported Phase B candidate is deliberately narrow: improve freshness ranking and route expensive reranking only where it adds value. Broader Agentic RAG work remains deferred.

Task 10's implementation and local acceptance are complete: Clerk Owner authorization, transient file parsing, mandatory PII cleanup, previewable public chunking, transactional Atlas publication, revision lifecycle controls, and a read-only public knowledge catalog are in place. The remaining deployment gate is external Clerk configuration and production Owner-login verification. It does not connect local private sources to Vercel.
