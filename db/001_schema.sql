-- Tark workspace schema (decision 8.8: Supabase Postgres, Auth and Storage).
-- Apply in the Supabase SQL editor or with psql, in file order:
--   001_schema.sql, 002_policies.sql, 003_storage.sql
-- Every tenant-scoped table carries workspace_id. Users come from auth.users
-- (Supabase Auth). Nothing here stores a password, a token or a key.
-- Re-runnable: every statement is idempotent.

create extension if not exists pgcrypto;

create table if not exists public.workspaces (
  id          uuid primary key default gen_random_uuid(),
  name        text not null check (length(name) between 1 and 120),
  created_at  timestamptz not null default now()
);

create table if not exists public.workspace_members (
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  user_id      uuid not null references auth.users(id) on delete cascade,
  created_at   timestamptz not null default now(),
  primary key (workspace_id, user_id)
);
create index if not exists workspace_members_user_idx on public.workspace_members (user_id);

create table if not exists public.plans (
  id           uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  intake       jsonb not null,
  source_note  text not null default '',
  created_at   timestamptz not null default now(),
  unique (id, workspace_id)        -- the target of the jobs composite key (ASVS 4.1.2)
);
create index if not exists plans_workspace_idx on public.plans (workspace_id);

create table if not exists public.products (
  id           uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  cik          text not null check (cik ~ '^[0-9]{1,10}$'),
  name         text not null default '',
  wrapper      text not null default '',
  product_key  text not null check (product_key ~ '^[a-z0-9_]{2,32}$'),
  registry_entry jsonb,            -- a person's registry judgment for the job (the admin CLI sets it), else the worker's default
  created_at   timestamptz not null default now(),
  unique (workspace_id, cik),
  unique (id, workspace_id)        -- the target of the jobs composite key (ASVS 4.1.2)
);
create index if not exists products_workspace_idx on public.products (workspace_id);

create table if not exists public.jobs (
  id               uuid primary key default gen_random_uuid(),
  workspace_id     uuid not null references public.workspaces(id) on delete cascade,
  product_id       uuid not null references public.products(id) on delete cascade,
  plan_id          uuid not null references public.plans(id) on delete cascade,
  state            text not null default 'queued'
                   check (state in ('queued', 'running', 'done', 'failed')),
  progress_step    text not null default 'queued',
  progress_detail  text not null default '',
  runner           text not null default '' check (runner in ('', 'actions', 'laptop')),
  pipeline_commit  text not null default '',
  attempts         integer not null default 0,
  created_at       timestamptz not null default now(),
  claimed_at       timestamptz,
  started_at       timestamptz,
  finished_at      timestamptz,
  updated_at       timestamptz not null default now(),
  failure_reason   text not null default '',
  tokens_in        bigint not null default 0,
  tokens_out       bigint not null default 0,
  cost_usd         numeric(12, 6) not null default 0,
  -- the product and the plan must belong to the job's own workspace, whatever
  -- the caller writes (ASVS 4.1.2): a composite key the policy cannot lose
  foreign key (product_id, workspace_id) references public.products (id, workspace_id) on delete cascade,
  foreign key (plan_id, workspace_id) references public.plans (id, workspace_id) on delete cascade
);
create index if not exists jobs_workspace_idx on public.jobs (workspace_id, created_at desc);
-- the same composite keys on a project created from an earlier version of this file
do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'products_id_workspace_id_key') then
    alter table public.products add constraint products_id_workspace_id_key unique (id, workspace_id);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'plans_id_workspace_id_key') then
    alter table public.plans add constraint plans_id_workspace_id_key unique (id, workspace_id);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'jobs_product_id_workspace_id_fkey') then
    alter table public.jobs add constraint jobs_product_id_workspace_id_fkey
      foreign key (product_id, workspace_id) references public.products (id, workspace_id) on delete cascade;
  end if;
  if not exists (select 1 from pg_constraint where conname = 'jobs_plan_id_workspace_id_fkey') then
    alter table public.jobs add constraint jobs_plan_id_workspace_id_fkey
      foreign key (plan_id, workspace_id) references public.plans (id, workspace_id) on delete cascade;
  end if;
end $$;
-- one job per product and plan pair at a time (R3-P4-4)
create unique index if not exists jobs_one_active_per_pair
  on public.jobs (product_id, plan_id) where state in ('queued', 'running');

create table if not exists public.records (
  id               uuid primary key default gen_random_uuid(),
  workspace_id     uuid not null references public.workspaces(id) on delete cascade,
  product_id       uuid not null references public.products(id) on delete cascade,
  plan_id          uuid not null references public.plans(id) on delete cascade,
  job_id           uuid not null references public.jobs(id) on delete cascade,
  version          integer not null default 1,
  artifacts_prefix text not null,
  record_hash      text not null,
  created_at       timestamptz not null default now(),
  unique (job_id)
);
create index if not exists records_workspace_idx on public.records (workspace_id, created_at desc);

create table if not exists public.documents (
  id            uuid primary key default gen_random_uuid(),
  workspace_id  uuid not null references public.workspaces(id) on delete cascade,
  record_id     uuid not null references public.records(id) on delete cascade,
  kind          text not null check (kind in ('selection_record', 'attachment', 'ingest_report', 'view', 'artifact')),
  storage_path  text not null,
  size_bytes    bigint not null,
  sha256        text not null check (sha256 ~ '^[0-9a-f]{64}$'),
  created_at    timestamptz not null default now(),
  unique (storage_path)
);
create index if not exists documents_record_idx on public.documents (record_id);

create table if not exists public.audit_log (
  id            bigint generated always as identity primary key,
  workspace_id  uuid references public.workspaces(id) on delete set null,
  user_id       uuid,
  event         text not null check (event in ('login', 'invite', 'plan_created', 'product_created', 'job_created',
                                                'job_claimed', 'job_done', 'job_failed', 'download', 'health')),
  detail        jsonb not null default '{}'::jsonb,
  created_at    timestamptz not null default now()
);
create index if not exists audit_log_workspace_idx on public.audit_log (workspace_id, created_at desc);

create table if not exists public.spend (
  id            bigint generated always as identity primary key,
  workspace_id  uuid not null references public.workspaces(id) on delete cascade,
  job_id        uuid not null references public.jobs(id) on delete cascade,
  cost_usd      numeric(12, 6) not null check (cost_usd >= 0),
  note          text not null default '',
  created_at    timestamptz not null default now()
);
create index if not exists spend_job_idx on public.spend (job_id);

-- the total the budget guard consults (decision 8.13: one total, not monthly)
create or replace function public.spend_total() returns numeric
language sql stable security definer set search_path = public as $$
  select coalesce(sum(cost_usd), 0) from public.spend;
$$;

-- membership test used by every policy. security definer so a policy on
-- workspace_members itself does not recurse.
create or replace function public.is_member(ws uuid) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from public.workspace_members m
    where m.workspace_id = ws and m.user_id = auth.uid()
  );
$$;
-- Supabase grants execute on every new function to anon and authenticated by
-- default, and a revoke from public alone leaves those grants (ASVS 4.1.3)
revoke all on function public.is_member(uuid) from public, anon;
grant execute on function public.is_member(uuid) to authenticated, service_role;
revoke all on function public.spend_total() from public, anon, authenticated;
grant execute on function public.spend_total() to service_role;

-- the keep-alive's one trivial query a day (R3-P4-7)
create or replace function public.ping() returns text
language sql stable as $$ select 'ok'::text $$;
grant execute on function public.ping() to anon, authenticated, service_role;
