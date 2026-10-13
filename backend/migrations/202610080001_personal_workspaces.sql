-- Every account owns one private workspace. Apply after cloud_workers.sql.
-- Existing shared workspaces need a deliberate data migration first: assigning
-- their shared sources to one user would disclose or discard another's data.
do $$
begin
  if exists (
    select 1 from public.mm_memberships where active
    group by tenant_id having count(*) > 1
  ) then
    raise exception 'Shared active workspaces exist; split and migrate their data before enabling personal workspaces';
  end if;
end $$;

create unique index if not exists mm_one_active_user_per_workspace
  on public.mm_memberships(tenant_id) where active;

-- Runs within the auth.users insert transaction. A failed provisioning rolls
-- back signup, so no account can be created without an isolated workspace.
create or replace function public.mm_create_personal_workspace()
returns trigger
language plpgsql security definer set search_path = ''
as $$
declare new_tenant uuid;
begin
  insert into public.mm_tenants(name) values ('Personal workspace') returning id into new_tenant;
  insert into public.mm_memberships(tenant_id, user_id, active)
    values (new_tenant, new.id, true);
  return new;
end;
$$;

revoke all on function public.mm_create_personal_workspace() from public, anon, authenticated;
drop trigger if exists mm_provision_personal_workspace on auth.users;
create trigger mm_provision_personal_workspace
  after insert on auth.users for each row
  execute function public.mm_create_personal_workspace();

-- Provision users created before this migration who have no active workspace.
do $$
declare account record; new_tenant uuid;
begin
  for account in
    select u.id from auth.users u
    where not exists (select 1 from public.mm_memberships m where m.user_id = u.id and m.active)
  loop
    insert into public.mm_tenants(name) values ('Personal workspace') returning id into new_tenant;
    insert into public.mm_memberships(tenant_id, user_id, active)
      values (new_tenant, account.id, true);
  end loop;
end $$;
