-- MindMesh commerce, BYOK and administration. Apply before enabling the UI.
-- All sensitive writes flow through FastAPI using the service role; browser
-- roles only receive their own safe entitlement and credential metadata.
create extension if not exists pgcrypto;

create table if not exists public.mm_profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  status text not null default 'active' check (status in ('active','suspended','deleted')),
  created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create table if not exists public.mm_user_roles (
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null check (role in ('owner','admin','member')),
  granted_by uuid references auth.users(id), granted_at timestamptz not null default now(), revoked_at timestamptz,
  primary key (user_id, role)
);
create unique index if not exists mm_one_active_owner on public.mm_user_roles(role) where role='owner' and revoked_at is null;

create table if not exists public.mm_plan_catalog (
  plan_key text primary key check (plan_key in ('free','plus','pro')),
  display_name text not null, price_paise integer not null check(price_paise >= 0), currency text not null default 'INR',
  gateway_plan_id text, active boolean not null default true, sort_order integer not null
);
insert into public.mm_plan_catalog(plan_key,display_name,price_paise,sort_order) values
  ('free','Free',0,1),('plus','Plus',29900,2),('pro','Pro',79900,3)
on conflict(plan_key) do update set display_name=excluded.display_name, price_paise=excluded.price_paise, sort_order=excluded.sort_order;
create table if not exists public.mm_plan_limits (
  plan_key text not null references public.mm_plan_catalog(plan_key), feature_key text not null,
  monthly_limit integer not null check(monthly_limit >= 0), item_cap integer, primary key(plan_key,feature_key)
);
insert into public.mm_plan_limits(plan_key,feature_key,monthly_limit,item_cap) values
 ('free','youtube',3,900),('plus','youtube',20,1800),('pro','youtube',60,2700),
 ('free','instagram',5,90),('plus','instagram',30,180),('pro','instagram',100,300),
 ('free','pdf',5,10),('plus','pdf',30,50),('pro','pdf',100,100),
 ('free','documents',10,null),('plus','documents',50,null),('pro','documents',150,null),
 ('free','audio',3,600),('plus','audio',20,1200),('pro','audio',60,2700),
 ('free','web',10,null),('plus','web',60,null),('pro','web',200,null),
 ('free','search',50,null),('plus','search',500,null),('pro','search',2000,null),
 ('free','chat',25,null),('plus','chat',200,null),('pro','chat',800,null)
on conflict(plan_key,feature_key) do update set monthly_limit=excluded.monthly_limit,item_cap=excluded.item_cap;

create table if not exists public.mm_subscriptions (
  user_id uuid primary key references auth.users(id) on delete cascade,
  base_plan text not null default 'free' references public.mm_plan_catalog(plan_key), provider text not null default 'none',
  provider_subscription_id text unique, status text not null default 'active', current_period_start timestamptz,
  current_period_end timestamptz, cancel_at_period_end boolean not null default false, updated_at timestamptz not null default now()
);
create table if not exists public.mm_promo_codes (
  id uuid primary key default gen_random_uuid(), code_hmac text not null unique, preview_prefix text not null,
  campaign_name text not null, description text, kind text not null check(kind in ('plan_grant','beta_grant')),
  allowed_plans text[] not null check(array_length(allowed_plans,1) > 0), duration_hours integer not null check(duration_hours between 1 and 8760),
  starts_at timestamptz not null default now(), redeem_until timestamptz, max_total_redemptions integer, max_per_user integer not null default 1,
  status text not null default 'active' check(status in ('active','paused','revoked')), new_users_only boolean not null default false,
  revoke_existing_grants boolean not null default false, created_by uuid references auth.users(id), created_at timestamptz not null default now()
);
create table if not exists public.mm_promo_redemptions (
  id uuid primary key default gen_random_uuid(), promo_id uuid not null references public.mm_promo_codes(id), user_id uuid not null references auth.users(id) on delete cascade,
  chosen_plan text not null references public.mm_plan_catalog(plan_key), redeemed_at timestamptz not null default now(),
  unique(promo_id,user_id)
);
create table if not exists public.mm_access_grants (
  id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
  promo_id uuid references public.mm_promo_codes(id), redemption_id uuid unique references public.mm_promo_redemptions(id),
  plan_key text not null references public.mm_plan_catalog(plan_key), cohort text, starts_at timestamptz not null default now(),
  expires_at timestamptz not null, revoked_at timestamptz, granted_by uuid references auth.users(id), created_at timestamptz not null default now()
);
create index if not exists mm_access_grants_active_idx on public.mm_access_grants(user_id, starts_at, expires_at) where revoked_at is null;

create table if not exists public.mm_usage_counters (
  user_id uuid not null references auth.users(id) on delete cascade, feature_key text not null, period_key text not null,
  consumed integer not null default 0 check(consumed >= 0), updated_at timestamptz not null default now(), primary key(user_id,feature_key,period_key)
);
create table if not exists public.mm_ai_credentials (
  user_id uuid not null references auth.users(id) on delete cascade, provider text not null check(provider in ('groq','gemini')),
  ciphertext bytea not null, nonce bytea not null, key_version text not null, last4 text not null, status text not null default 'verified',
  verified_at timestamptz, updated_at timestamptz not null default now(), primary key(user_id,provider)
);
create table if not exists public.mm_provider_preferences (
  user_id uuid not null references auth.users(id) on delete cascade, purpose text not null check(purpose in ('llm','embeddings','transcription')),
  mode text not null default 'managed' check(mode in ('managed','byok')), provider text not null, fallback_to_managed boolean not null default false,
  primary key(user_id,purpose)
);
create table if not exists public.mm_admin_audit_logs (
  id bigint generated always as identity primary key, actor_id uuid references auth.users(id), action text not null,
  target_id text, details jsonb not null default '{}', created_at timestamptz not null default now()
);

alter table public.mm_profiles enable row level security;
alter table public.mm_subscriptions enable row level security;
alter table public.mm_access_grants enable row level security;
alter table public.mm_usage_counters enable row level security;
alter table public.mm_ai_credentials enable row level security;
alter table public.mm_provider_preferences enable row level security;
alter table public.mm_user_roles enable row level security;
alter table public.mm_promo_codes enable row level security;
alter table public.mm_promo_redemptions enable row level security;
alter table public.mm_admin_audit_logs enable row level security;
revoke all on public.mm_profiles,public.mm_subscriptions,public.mm_access_grants,public.mm_usage_counters,public.mm_ai_credentials,public.mm_provider_preferences,public.mm_user_roles,public.mm_promo_codes,public.mm_promo_redemptions,public.mm_admin_audit_logs from anon,authenticated;
grant all on public.mm_profiles,public.mm_subscriptions,public.mm_access_grants,public.mm_usage_counters,public.mm_ai_credentials,public.mm_provider_preferences,public.mm_user_roles,public.mm_promo_codes,public.mm_promo_redemptions,public.mm_admin_audit_logs to service_role;
