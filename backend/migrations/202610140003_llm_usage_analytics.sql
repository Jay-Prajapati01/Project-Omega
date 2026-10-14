-- Redacted provider-attempt telemetry. No prompts, completions or raw keys.
create table if not exists public.mm_llm_usage_events (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  request_id text not null,
  tenant_id text,
  user_id text,
  task_type text not null check (task_type in ('ask_ai','ingestion_summary','other')),
  provider text not null,
  model text not null,
  key_alias text not null,
  quota_scope text,
  status text not null check (status in ('success','rate_limited','auth_error','upstream_error','timeout','invalid_request','unknown')),
  http_status integer,
  latency_ms integer,
  input_tokens integer,
  output_tokens integer,
  total_tokens integer,
  retry_count integer not null default 0,
  fallback_used boolean not null default false,
  fallback_reason text,
  error_code text,
  rpd_limit integer,
  rpd_remaining integer,
  rpd_reset text,
  tpm_limit integer,
  tpm_remaining integer,
  tpm_reset text
);
create index if not exists mm_llm_usage_events_created_idx on public.mm_llm_usage_events(created_at desc);
create index if not exists mm_llm_usage_events_model_task_idx on public.mm_llm_usage_events(model,task_type,created_at desc);
create index if not exists mm_llm_usage_events_alias_idx on public.mm_llm_usage_events(key_alias,created_at desc);
create index if not exists mm_llm_usage_events_status_idx on public.mm_llm_usage_events(status,created_at desc);
alter table public.mm_llm_usage_events enable row level security;
revoke all on public.mm_llm_usage_events from anon, authenticated;
grant select, insert, delete on public.mm_llm_usage_events to service_role;
grant usage, select on sequence public.mm_llm_usage_events_id_seq to service_role;

-- Run this bounded cleanup periodically (e.g. a daily scheduled DB job), using
-- the configured LLM_USAGE_RETENTION_DAYS value (90 days by default).
comment on table public.mm_llm_usage_events is
  'Provider attempt metrics only; no prompt/completion/API key. Delete rows older than configured retention.';
