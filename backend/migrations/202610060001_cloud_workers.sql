-- Apply in Supabase SQL editor. No existing local data is assigned to a tenant automatically.
create table if not exists public.mm_tenants (
  id uuid primary key default gen_random_uuid(), name text not null
);
create table if not exists public.mm_memberships (
  tenant_id uuid not null references public.mm_tenants(id),
  user_id uuid not null references auth.users(id) on delete cascade,
  active boolean not null default true,
  primary key (tenant_id,user_id)
);
-- Beta: one active workspace per user; backend never accepts a tenant header.
create unique index if not exists mm_one_active_workspace
  on public.mm_memberships(user_id) where active;
create table if not exists public.mm_state (
  tenant_id uuid not null references public.mm_tenants(id),
  kind text not null check (kind in ('store','graph')),
  body jsonb not null, primary key (tenant_id,kind)
);
create table if not exists public.mm_job_results (
  job_id uuid primary key, tenant_id uuid not null references public.mm_tenants(id),
  user_id uuid not null references auth.users(id), resource_id text not null,
  body jsonb not null, created_at timestamptz not null default now()
);
alter table public.mm_tenants enable row level security;
alter table public.mm_memberships enable row level security;
alter table public.mm_state enable row level security;
alter table public.mm_job_results enable row level security;
-- No browser policies: all application access goes through authenticated FastAPI.
revoke all on public.mm_tenants,public.mm_memberships,public.mm_state,public.mm_job_results from anon,authenticated;
grant all on public.mm_tenants,public.mm_memberships,public.mm_state,public.mm_job_results to service_role;
insert into storage.buckets(id,name,public,file_size_limit)
  values ('mindmesh-private','mindmesh-private',false,209715200)
  on conflict(id) do update set public=false;
