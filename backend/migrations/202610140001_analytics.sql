-- First-party aggregate product analytics. Browser identifiers are random UUIDs;
-- the table contains no account IDs, IP addresses, content, or user-entered text.
create table if not exists public.mm_analytics_events (
  id bigint generated always as identity primary key,
  visitor_key uuid not null,
  event_name text not null check (event_name in ('page_view','feature_used','heartbeat')),
  page_path text not null check (page_path in ('/','/contact','/faq','/privacy','/dashboard','/workspace','/youtube','/instagram','/chat','/graph','/stored','/profile','/settings')),
  feature_key text check (feature_key is null or feature_key in ('youtube','instagram','ask_ai','stored')),
  occurred_at timestamptz not null default now(),
  check ((event_name in ('page_view','heartbeat') and feature_key is null) or (event_name='feature_used' and feature_key is not null))
);
create index if not exists mm_analytics_events_time_idx on public.mm_analytics_events(occurred_at desc);
create index if not exists mm_analytics_events_visitor_time_idx on public.mm_analytics_events(visitor_key, occurred_at desc);
create index if not exists mm_analytics_events_page_time_idx on public.mm_analytics_events(page_path, occurred_at desc) where event_name='page_view';
create index if not exists mm_analytics_events_feature_time_idx on public.mm_analytics_events(feature_key, occurred_at desc) where event_name='feature_used';
alter table public.mm_analytics_events enable row level security;
revoke all on public.mm_analytics_events from anon, authenticated;
grant select, insert, delete on public.mm_analytics_events to service_role;
grant usage, select on sequence public.mm_analytics_events_id_seq to service_role;
