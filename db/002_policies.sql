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

-- no grants to anon: the anon key alone reads nothing (tested in R3-P4-3).
-- authenticated starts from nothing too: Supabase's default privileges give
-- the role every verb on every new table, and row-level security is then the
-- only layer that denies update and delete (ASVS review, 2026-09-08)
revoke all on all tables in schema public from anon;
revoke all on all tables in schema public from authenticated;
alter default privileges in schema public revoke all on tables from anon, authenticated;
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
-- a user creates a job as queued with no runner, on a product and a plan of
-- the same workspace: every other column is the worker's (ASVS 4.1.2, the
-- composite keys in 001 hold the same rule at the table)
drop policy if exists jobs_member_insert on public.jobs;
create policy jobs_member_insert on public.jobs
  for insert to authenticated
  with check (public.is_member(workspace_id) and state = 'queued' and runner = '' and cost_usd = 0
              and progress_step = 'queued' and progress_detail = '' and attempts = 0
              and tokens_in = 0 and tokens_out = 0 and failure_reason = ''
              and claimed_at is null and started_at is null and finished_at is null
              and exists (select 1 from public.products p where p.id = jobs.product_id and p.workspace_id = jobs.workspace_id)
              and exists (select 1 from public.plans q where q.id = jobs.plan_id and q.workspace_id = jobs.workspace_id));

drop policy if exists records_member_select on public.records;
create policy records_member_select on public.records
  for select to authenticated using (public.is_member(workspace_id));

drop policy if exists documents_member_select on public.documents;
create policy documents_member_select on public.documents
  for select to authenticated using (public.is_member(workspace_id));

drop policy if exists audit_member_select on public.audit_log;
create policy audit_member_select on public.audit_log
  for select to authenticated using (public.is_member(workspace_id));
-- a user writes only their own events into their own workspace, and only the
-- events a user causes: the worker's and the admin's events are theirs to write
drop policy if exists audit_member_insert on public.audit_log;
create policy audit_member_insert on public.audit_log
  for insert to authenticated
  with check (user_id = auth.uid() and (workspace_id is null or public.is_member(workspace_id))
              and event in ('login', 'plan_created', 'product_created', 'job_created', 'download')
              and pg_column_size(detail) <= 4096);

drop policy if exists spend_member_select on public.spend;
create policy spend_member_select on public.spend
  for select to authenticated using (public.is_member(workspace_id));
