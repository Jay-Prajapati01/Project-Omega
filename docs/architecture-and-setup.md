# Architecture and setup

## Runtime components

The website is a Next.js App Router application in `frontend/`. It serves the landing page, login/signup, dashboard, feature pages, Stored views, and the role-gated admin portal. The companion Android project is nested at `frontend/companion/`.

The API is FastAPI in `backend/app/main.py`. Selected routes are YouTube (`/api/videos`), Instagram (`/api/instagram`), Ask AI (`/api/chat`), Stored (`/api/sources`, `/api/notes`), a compatibility search endpoint (`/api/search`), and mobile quick saves (`/api/mobile`). Search and chat share tenant-scoped hybrid retrieval; the website exposes discovery inside Ask AI. Health, entitlements, and admin campaign endpoints support operations and the portals.

## Multi-tenant identity path

1. The browser or companion signs in through Supabase Auth and sends a bearer access token.
2. In cloud mode, `CloudAuthMiddleware` verifies the token and resolves the user's membership. The resulting tenant and user IDs become a request `Scope` context.
3. Services use that verified context for source ownership, note access, vector filtering, job ownership, quotas, and storage. Request payloads do not choose a tenant.
4. Cloud jobs carry a signed/verified ownership envelope and check current membership before work is executed.
5. In local authenticated mode, the data directory is namespaced by the verified user ID. Keep `AUTH_ENABLED=true` when using account-based clients.

The shipped migrations under `backend/migrations/` define tenant/workspace membership, normalized source and job state, cloud jobs, and admin/commerce records. Apply them to the intended Supabase/Postgres project before cloud execution.

Cloud Postgres connections use a bounded per-process pool. Set the maximum
database instance count and `SUPABASE_DB_POOL_MAX_SIZE` together so the total
API and worker connections remain within the Supabase pooler and database
limits. Core sources, notes, conversations, and graph state still uses the
`mm_state` JSON document; normalized tables are a staged migration target, not
yet the active read/write path.

## User and admin portals

All authenticated users receive the user workspace. Owners and admins additionally see the Admin portal link. The portal exposes the copied promo campaign manager; the API independently enforces the admin role. The source project does not contain a broad tenant provisioning console, so this clone does not invent one.

## Configuration summary

Use `backend/.env.example` and `frontend/cloud.env.example` as templates. Keep actual keys in local environment files, which are excluded from this copy. Local AI uses Ollama by default, with Groq and Hugging Face alternatives. Cloud operation additionally needs Supabase service configuration and the selected job/storage backend. Qdrant stores embeddings. See the feature pages for pipeline dependencies.
