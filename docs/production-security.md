# Production abuse protection and monitoring

The API includes IP and per-user/tenant request limits, daily job and upload
quotas, a daily AI request cap, bounded request bodies, upload validation,
SSRF protection, tenant authorization, and low-cardinality metrics. Production
rate limiting requires a shared TLS Redis endpoint (`REDIS_URL`); do not use
per-container memory limits for a multi-instance deployment. If Redis is
unavailable, API requests fail closed with `503 RATE_LIMIT_UNAVAILABLE`.

## Application settings

Set these on the API service (values are starting points; tune to observed use):

| Setting | Default | What it protects |
| --- | ---: | --- |
| `RATE_LIMIT_MAX_REQUESTS` / `RATE_LIMIT_WINDOW` | 120 / 60 sec | Per-IP ceiling for anonymous traffic and broad flood protection |
| `RATE_LIMIT_READ_PER_MIN` | 120 | Reads and searches per user/tenant |
| `RATE_LIMIT_WRITE_PER_MIN` | 60 | Mutations per user/tenant |
| `RATE_LIMIT_CHAT_PER_MIN` | 30 | AI chat, chat actions, and search requests |
| `RATE_LIMIT_POLL_PER_MIN` | 60 | Job status polling |
| `RATE_LIMIT_INGEST_PER_HOUR` | 20 | Video, Instagram, URL, and file ingestion requests |
| `RATE_LIMIT_CONTACT_PER_MIN` | 5 | Public contact form submissions per IP |
| `MAX_JOBS_PER_TENANT_PER_DAY` | 200 | New processing jobs per tenant |
| `MAX_AI_REQUESTS_PER_TENANT_PER_DAY` | 500 | AI calls per tenant, including streamed chat and answer actions |
| `MAX_UPLOAD_BYTES_PER_TENANT_PER_DAY` | 5 GiB | Aggregate uploaded bytes per tenant |

The daily AI counter limits request count, not provider tokens. Set provider-side
spending limits and alerts as well; token-level accounting needs provider usage
data to be captured and persisted before it can be enforced reliably.

`TRUST_PROXY=true` is only safe when the API is reachable exclusively through
your trusted load balancer or reverse proxy. AWS uses the last
`X-Forwarded-For` entry; GCP's global external Application Load Balancer uses
the second-last entry (the client IP it appends before its own address). Never
expose the container directly while trusting forwarded headers.

## PostgreSQL connection budget

Cloud API and worker processes use a bounded psycopg connection pool. The
default `SUPABASE_DB_POOL_MAX_SIZE=5` is a **per-process** ceiling, not a
deployment-wide ceiling. Budget the database pooler for
`max API processes × API pool size + max worker processes × worker pool size`,
plus Supabase and administrative connections. Start conservatively and
increase only after observing pool wait time and database connections. The
driver disables server-side prepared statements for transaction-mode pooler
compatibility. Prefer the provider's TLS transaction-pooler URL for many short
application connections; retain `sslmode=require` or stronger.

The API's `mm_state` store still reads and writes a tenant's JSON document.
`backend/migrations/202610070001_normalized_state.sql` creates indexed target
tables but explicitly does not switch application reads/writes or backfill
existing JSON state. Those indexes therefore do not speed up current source,
note, conversation, or graph scans. Do not claim normalized-query scale until
that migration/cutover is completed and verified against representative data.
Before adding indexes, collect query plans and timings on a staging database;
use concurrent index creation for large live tables where the migration
workflow permits it.

## Identity provider protections

Browser sign-up, sign-in, password reset, and verification requests go directly
to Supabase Auth, so API middleware cannot rate-limit them. In the Supabase
dashboard, configure Auth rate limits, enable CAPTCHA for sign-up and other
public auth flows where supported, and set the exact production Site URL and
redirect URLs. Keep the service-role key server-side only.

## AWS edge and alarms

Put AWS WAF on the public API and website entry points. Add a rate-based rule
for anonymous traffic and managed protections for common web exploits; keep
the app's identity limits because WAF cannot distinguish authenticated tenants.
Use CloudWatch alarms for sustained 429/503 rates, repeated 401/403 responses,
job enqueue spikes, worker failures, upload volume, and provider spend. Keep
request IDs in logs, but do not log bearer tokens, uploaded content, contact
form bodies, or API secrets.

## Google Cloud edge and monitoring

The separate GCP path uses Cloud Armor on the global HTTPS load balancer for
per-IP throttling and common SQL injection filtering, while the API's shared
Redis limiter continues to apply per-user/tenant quotas across Cloud Run
instances. Keep the Cloud Run API reachable only through the load balancer,
configure Cloud Monitoring uptime checks and alerts, and review Cloud Logging,
Cloud Tasks retries, Cloud Run Job failures, and provider spend. The GCP
configuration trusts the second-last forwarded IP added by Google's load
balancer; do not expose the Cloud Run service URL directly.

The API exposes low-cardinality Prometheus metrics at `/api/metrics`; restrict
that path to your monitoring system or an authenticated internal network. The
in-process counters reset when an instance restarts, so use CloudWatch logs and
AWS-level metrics/alarms for durable, cross-instance alerting.

## Before opening public access

1. Set `ENVIRONMENT=production`, `MINDMESH_EXECUTION_MODE=cloud`,
   `RATE_LIMIT_ENABLED=true`, and a TLS `REDIS_URL`.
2. Set explicit `CORS_ORIGINS` to the production website origin; do not use `*`.
3. Configure Supabase Auth rate limits/CAPTCHA and production redirect URLs.
4. Configure AWS WAF and CloudWatch alarms, then verify `/api/health/detailed`
   and confirm the `redis` and `database` checks are healthy.
5. Exercise signed-in and anonymous paths, confirm quota responses, and verify
   alerts before sharing the public URL.
