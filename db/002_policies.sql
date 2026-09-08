-- Row-level security (decision 8.8, rule 22): a user reads and writes only
-- rows whose workspace_id is in their memberships. The service role (the
-- worker, the admin CLI) bypasses RLS by Supabase's design and is never
-- used in the API's request path. The anon role can read nothing.
-- Re-runnable: policies are dropped and recreated.

alter table public.workspaces        enable row level security;
alter table public.workspace_members enable row level security;
alter table public.plans             enable row level security;
alter table public.products          enable row level security;
alter table public.jobs              enable row level security;
alter table public.records           enable row level security;
alter table public.documents         enable row level security;
alter table public.audit_log         enable row level security;
alter table public.spend             enable row level security;

-- no grants to anon: the anon key alone reads nothing (tested in R3-P4-3)
revoke all on all tables in schema public from anon;
grant usage on schema public to authenticated;
grant select on public.workspaces, public.workspace_members, public.records, public.documents,
                public.spend to authenticated;
grant select, insert on public.plans, public.products, public.jobs, public.audit_log to authenticated;

drop policy if exists workspaces_member_select on public.workspaces;
create policy workspaces_member_select on public.workspaces
  for select to authenticated using (public.is_member(id));

drop policy if exists members_self_select on public.workspace_members;
create policy members_self_select on public.workspace_members
  for select to authenticated using (user_id = auth.uid());

drop policy if exists plans_member_select on public.plans;
create policy plans_member_select on public.plans
  for select to authenticated using (public.is_member(workspace_id));
drop policy if exists plans_member_insert on public.plans;
create policy plans_member_insert on public.plans
  for insert to authenticated with check (public.is_member(workspace_id));

drop policy if exists products_member_select on public.products;
create policy products_member_select on public.products
  for select to authenticated using (public.is_member(workspace_id));
drop policy if exists products_member_insert on public.products;
create policy products_member_insert on public.products
  for insert to authenticated with check (public.is_member(workspace_id));

drop policy if exists jobs_member_select on public.jobs;
create policy jobs_member_select on public.jobs
  for select to authenticated using (public.is_member(workspace_id));
-- a user creates a job as queued with no runner: every other column is the worker's
drop policy if exists jobs_member_insert on public.jobs;
create policy jobs_member_insert on public.jobs
  for insert to authenticated
  with check (public.is_member(workspace_id) and state = 'queued' and runner = '' and cost_usd = 0
              and progress_step = 'queued');

drop policy if exists records_member_select on public.records;
create policy records_member_select on public.records
  for select to authenticated using (public.is_member(workspace_id));

drop policy if exists documents_member_select on public.documents;
create policy documents_member_select on public.documents
  for select to authenticated using (public.is_member(workspace_id));

drop policy if exists audit_member_select on public.audit_log;
create policy audit_member_select on public.audit_log
  for select to authenticated using (public.is_member(workspace_id));
-- a user writes only their own events into their own workspace
drop policy if exists audit_member_insert on public.audit_log;
create policy audit_member_insert on public.audit_log
  for insert to authenticated
  with check (user_id = auth.uid() and (workspace_id is null or public.is_member(workspace_id)));

drop policy if exists spend_member_select on public.spend;
create policy spend_member_select on public.spend
  for select to authenticated using (public.is_member(workspace_id));
