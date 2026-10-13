-- GCP job lifecycle store + durable per-tenant quotas.
-- Jobs live here through every state (queued, processing, completed, failed,
-- cancelled); the dispatcher claims rows transactionally so no Redis server
-- is required when JOB_BACKEND is postgres or gcp.
create table if not exists public.mm_jobs (
  job_id uuid primary key,
  tenant_id uuid not null references public.mm_tenants(id),
  user_id uuid not null references auth.users(id) on delete cascade,
  resource_id text not null,
  job_type text not null,
  payload jsonb not null default '{}',
  fingerprint text not null,
  status text not null default 'queued'
    check (status in ('queued', 'processing', 'completed', 'failed', 'cancelled')),
  attempts integer not null default 0,
  lease text,
  next_at timestamptz not null default now(),
  result jsonb,
  error jsonb,
  dlq boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists mm_jobs_due_idx
  on public.mm_jobs(status, next_at) where status in ('queued', 'processing');
create index if not exists mm_jobs_owner_idx
  on public.mm_jobs(tenant_id, user_id, created_at desc);
create index if not exists mm_jobs_dlq_idx
  on public.mm_jobs(dlq) where dlq;

-- Atomic numeric quota counters (jobs, upload bytes). One row per
-- tenant/kind/day; increments are a single upsert so concurrent API
-- replicas share exact usage without per-unit timestamp rows.
create table if not exists public.mm_quotas (
  tenant_id uuid not null references public.mm_tenants(id),
  kind text not null,
  day text not null,
  used bigint not null default 0,
  updated_at timestamptz not null default now(),
  primary key (tenant_id, kind, day)
);

alter table public.mm_jobs enable row level security;
alter table public.mm_quotas enable row level security;
-- No browser policies: all application access goes through authenticated FastAPI.
revoke all on public.mm_jobs, public.mm_quotas from anon, authenticated;
grant all on public.mm_jobs, public.mm_quotas to service_role;
