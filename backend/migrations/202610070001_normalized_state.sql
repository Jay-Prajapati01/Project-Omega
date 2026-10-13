-- Normalized domain schema (audit P0-5), stage 1: tables, constraints, indexes.
--
-- The application STILL reads/writes the JSON documents in mm_state; this
-- migration establishes the target schema plus the indexes/constraints the
-- cutover requires, and adds the retention index mm_job_results was missing.
-- See docs/AUTHORIZATION_MATRIX.md and the migration plan note at the bottom.
--
-- Apply with: supabase db push  (or paste into the SQL editor)

-- ---------------------------------------------------------------------------
-- Sources: one row per ingested source (was: mm_state.body['sources'] array)
-- ---------------------------------------------------------------------------
create table if not exists public.mm_sources (
  source_id      text        not null,
  tenant_id      uuid        not null references public.mm_tenants(id) on delete cascade,
  user_id        uuid        not null references auth.users(id),
  source_type    text        not null check (source_type in
                   ('youtube','instagram','pdf','document','audio','web')),
  title          text        not null default '',
  url            text,
  file_path      text,
  file_name      text,
  file_size      bigint      check (file_size is null or file_size >= 0),
  mime_type      text,
  summary        text,
  key_topics     jsonb       not null default '[]'::jsonb,
  chunks_indexed integer     not null default 0 check (chunks_indexed >= 0),
  page_count     integer     check (page_count is null or page_count >= 0),
  created_at     timestamptz not null default now(),
  deleted_at     timestamptz,
  primary key (tenant_id, source_id)
);
create index if not exists mm_sources_tenant_created
  on public.mm_sources(tenant_id, created_at desc);
create index if not exists mm_sources_tenant_type
  on public.mm_sources(tenant_id, source_type, created_at desc);
-- Duplicate detection within a tenant for URL sources.
create unique index if not exists mm_sources_tenant_url
  on public.mm_sources(tenant_id, url) where url is not null and deleted_at is null;

-- ---------------------------------------------------------------------------
-- Notes (was: mm_state.body['notes'] array)
-- ---------------------------------------------------------------------------
create table if not exists public.mm_notes (
  note_id    text        not null,
  tenant_id  uuid        not null references public.mm_tenants(id) on delete cascade,
  user_id    uuid        not null references auth.users(id),
  title      text        not null check (char_length(title) between 1 and 300),
  body       text        not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz,
  primary key (tenant_id, note_id)
);
create index if not exists mm_notes_tenant_created
  on public.mm_notes(tenant_id, created_at desc) where deleted_at is null;

-- ---------------------------------------------------------------------------
-- Conversations + messages (was: mm_state.body['conversations'] array)
-- Chat history is per USER inside a shared tenant (see authorization matrix).
-- ---------------------------------------------------------------------------
create table if not exists public.mm_conversations (
  conversation_id uuid        primary key,
  tenant_id       uuid        not null references public.mm_tenants(id) on delete cascade,
  user_id         uuid        not null references auth.users(id),
  title           text        not null default '',
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  deleted_at      timestamptz
);
create index if not exists mm_conversations_owner
  on public.mm_conversations(tenant_id, user_id, updated_at desc)
  where deleted_at is null;

create table if not exists public.mm_messages (
  message_id      bigserial   primary key,
  conversation_id uuid        not null references public.mm_conversations(conversation_id) on delete cascade,
  role            text        not null check (role in ('user','assistant')),
  content         text        not null,
  citations       jsonb       not null default '[]'::jsonb,
  created_at      timestamptz not null default now()
);
create index if not exists mm_messages_conversation
  on public.mm_messages(conversation_id, message_id);

-- ---------------------------------------------------------------------------
-- Knowledge graph (was: mm_state.body['graph'] = {nodes, edges} jsonb)
-- ---------------------------------------------------------------------------
create table if not exists public.mm_graph_nodes (
  tenant_id   uuid    not null references public.mm_tenants(id) on delete cascade,
  name        text    not null,
  count       integer not null default 1 check (count >= 1),
  primary key (tenant_id, name)
);
create table if not exists public.mm_graph_edges (
  tenant_id   uuid    not null references public.mm_tenants(id) on delete cascade,
  source      text    not null,
  target      text    not null,
  label       text    not null,
  source_id   text    not null,
  source_type text    not null,
  title       text,
  created_at  timestamptz not null default now(),
  primary key (tenant_id, source, target, label, source_id)
);
create index if not exists public_mm_graph_edges_source
  on public.mm_graph_edges(tenant_id, source_id);

-- ---------------------------------------------------------------------------
-- Retention/ops fixes on existing tables (audit P0-11 retention, P1-7 index)
-- ---------------------------------------------------------------------------
create index if not exists mm_job_results_tenant_created
  on public.mm_job_results(tenant_id, created_at);
create index if not exists mm_job_results_created
  on public.mm_job_results(created_at);

-- ---------------------------------------------------------------------------
-- RLS: same policy as the existing mm_* tables — no browser access at all.
-- ---------------------------------------------------------------------------
alter table public.mm_sources        enable row level security;
alter table public.mm_notes          enable row level security;
alter table public.mm_conversations  enable row level security;
alter table public.mm_messages       enable row level security;
alter table public.mm_graph_nodes    enable row level security;
alter table public.mm_graph_edges    enable row level security;
revoke all on public.mm_sources,public.mm_notes,public.mm_conversations,
             public.mm_messages,public.mm_graph_nodes,public.mm_graph_edges
  from anon,authenticated;
grant all on public.mm_sources,public.mm_notes,public.mm_conversations,
             public.mm_messages,public.mm_graph_nodes,public.mm_graph_edges
  to service_role;

-- ---------------------------------------------------------------------------
-- Migration plan (next steps, NOT run by this file):
--   1. Backfill: INSERT INTO mm_sources SELECT … FROM jsonb_to_recordset of
--      mm_state.body (one tenant at a time, verify row counts).
--   2. Switch app reads/writes to the tables behind a feature flag; dual-write
--      for one release; compare counts.
--   3. Drop the sources/notes/conversations/graph keys from mm_state.
--   4. Never mix vectors: reindex into the BGE-M3 collection via
--      scripts/migrate_cloud.py (768-dim Nomic points stay quarantined).
-- ---------------------------------------------------------------------------
