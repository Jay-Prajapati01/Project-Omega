# Stored

The `/stored` page is the user-facing library for processed source items. It loads the source list and metadata from the tenant-scoped sources API, supports source detail/open/delete actions, and links to source-specific views. Ask AI now owns conversational retrieval and ranked source discovery. The legacy `/api/search` endpoint remains available for compatibility; the former `/search` website route redirects to `/chat`. Workspace notes use `/api/notes` and are included in Ask AI retrieval.

Ingestion from YouTube and Instagram writes a normalized source record and content chunks. Qdrant stores vectors for semantic retrieval; source metadata and content are held by the configured local or cloud storage/database services. Cloud mode uses tenant-aware Postgres/Supabase and object storage/job records; local authenticated mode namespaces data under the verified user.

Deleting a source removes the source's indexed material through the source service. Ask AI retrieval relies on the verified ownership scope and cannot select a tenant from a user-supplied ID.
