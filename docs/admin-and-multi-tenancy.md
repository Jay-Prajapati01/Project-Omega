# Admin portal and multi-tenancy

## Roles

The backend resolves the role from verified account/workspace membership. A regular member has the user portal; `owner` and `admin` roles receive the Admin portal link. Frontend visibility is convenience only: admin API actions call the backend's role check and return forbidden when the verified user is not an administrator.

The included admin page links to the source project's promo campaign manager, which creates temporary plan grants. A grant cannot confer administrator status. The source implementation has no tenant-wide user management dashboard; tenant membership provisioning remains in the identity/database setup.

## Tenant isolation

`backend/app/core/tenant.py` defines request scope. Cloud authentication sets tenant and user identifiers only after bearer verification. Source rows, notes, jobs, quotas, provider keys, and vector searches use that scope. Job execution rechecks membership and ownership before processing. In local mode, authenticated user data is stored under a per-user directory.

Apply all migrations in `backend/migrations/` in order. Do not run cloud mode against a database that has not received those migrations. Configure Supabase issuer/JWKS and database/storage settings from the environment templates; never copy production secrets into this project.
