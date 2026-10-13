-- Supports the per-tenant daily admission count in app/services/jobs_pg.py:
-- WHERE tenant_id = ? AND created_at >= date_trunc('day', now()).
-- The existing (tenant_id, user_id, created_at) index has an intervening
-- user_id column and cannot efficiently bound this tenant-wide date range.
-- Apply before launch while mm_jobs is small; on a large live table, use the
-- operator's concurrent-index workflow rather than running this transaction.
create index if not exists mm_jobs_tenant_created_idx
  on public.mm_jobs (tenant_id, created_at desc);
