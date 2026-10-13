# Scaling readiness

This tracks the scale topics in the supplied guide. Load tests must never target production or call paid AI/payment providers.

## Current state

- **Database:** migrations define indexes for normalized sources, notes, conversations, messages, jobs, and related tables. A targeted index now supports the daily per-tenant job-count query. However, `backend/migrations/202610070001_normalized_state.sql` says the app still reads/writes source, note, conversation, and graph data through `mm_state` JSON. The normalized indexes do not speed up those current JSON-array operations.
- **Connections:** cloud Postgres now uses a bounded process pool, default maximum 5, with prepared statements disabled for transaction-pooler compatibility. Pool capacity must be calculated across every API and worker process.
- **Caching:** embeddings use a bounded per-process LRU in configured provider paths. There is no shared cache for private user data. Authenticated API responses use `Cache-Control: no-store`.
- **Hosting:** deployment is not yet configured or live, so host plan limits and production concurrency are unknown. The code has Docker and cloud worker paths; do not assume local disk is durable or shared across replicas.
- **Load tests:** a read-only k6 staging scenario is now present at `backend/loadtests/k6_staging_readonly.js`. It needs an isolated test database, representative seeded data, 100 distinct test-user tokens by default, and paid provider calls disabled or mocked. It has not been run because this workspace has no confirmed staging target.

## Work order before opening to public traffic

1. Choose the cloud deployment and staging topology. Confirm database, Qdrant, object storage, Redis, and workers are external/shared where multi-instance operation requires it. Confirm no essential data is stored only on instance-local disk.
2. Verify the database connection budget: `max API processes × pool size + max worker processes × pool size`, plus database/admin overhead. Configure the provider's TLS transaction pooler and verify connection behavior with the actual deployment settings.
3. Seed staging with representative tenants, sources, notes, conversations, and jobs. Record actual common/slow query plans and timings. Decide whether normalized tables should be cut over; if yes, use a reviewed backfill/dual-write/verification migration before reads switch. Add only indexes justified by measured SQL query predicates and ordering.
4. Run `backend/loadtests/k6_staging_readonly.js` against staging only. Before the run, verify the database is isolated, seed representative data, create enough staging users/tokens, and temporarily set staging's anonymous per-IP limit above the test generator's request rate. This workload exercises the public home/health paths and authenticated source/note/graph/stats reads; it does not create jobs, upload data, or call AI/payment providers. For costly ingestion/AI flows, add separate stubbed scenarios. Ramp gradually; track p95 latency, errors, 429s, DB connections, pool wait, CPU/memory, queue depth, and provider spend. Set thresholds based on the chosen host and product SLO rather than blindly copying generic numbers.
5. Apply caching only after measurement. Public immutable assets/pages may use CDN caching. User-specific content must remain uncached or use a tenant/user-scoped key, deliberate TTL, and invalidation on writes. Check that separate accounts cannot observe one another's data.
6. Re-run the same staging workload after each material change, review results, and retain a rollback path. A successful application build alone is not evidence of traffic capacity.

## Pool settings

`SUPABASE_DB_POOL_MAX_SIZE` defaults to `5` per process and can be reduced for smaller database limits. `SUPABASE_DB_POOL_TIMEOUT_SECONDS` defaults to `10`. These values do not increase database capacity; aggregate connections are bounded by the deployment's maximum number of processes.

The k6 scenario defaults to a 100-VU peak and generic p95/error thresholds from the guide; tune them to staging capacity. It requires `TARGET_ENV=staging`, `STAGING_CONFIRMATION=I_HAVE_VERIFIED_THIS_IS_STAGING`, `API_BASE_URL`, `WEB_BASE_URL`, and `AUTH_TOKENS_FILE` containing one distinct, current staging access token per virtual user. Keep that token file out of version control. Do not run until the target URLs are confirmed as staging.
