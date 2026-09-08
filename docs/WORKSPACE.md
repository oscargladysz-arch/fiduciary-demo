# Tark workspace runbook (R3-P4)

The workspace is the self-serve path of decision 8.7: a design partner
logs in, submits a fund for a plan, and gets the Investment Selection
Record. Code in the public repository (`app/`, `worker/`, `db/`, `src/`),
accounts and secrets in Oscar's hands, the worker in the private repository
`tark-workspace`. Everything runs on free tiers (decision 8.9). Nothing in
this file is a secret, and nothing in this file charges money.

Status line (the build report repeats it): the code, the schema, the
policies, the workflows and the offline gates exist and run against a fake
Supabase and the mocked model in this repository. No Supabase project, no
Render service and no private repository has been created or exercised
from the cloud session (decision 8.4 and 8.24: this session has no network
to those hosts). Every step below that touches a host is Oscar's or the
laptop session's, and is marked so. The unattended path has not passed
R3-P4-8.

## 1. What runs where

| Piece | Where | Key it holds | Public or private |
|---|---|---|---|
| Postgres, Auth, Storage | Supabase free tier | none of ours | the project, private |
| The API (`app/`) | Render free web service, from this repository's `main` | anon key, JWT secret or signing keys, the dispatch token | public code, secrets in Render's environment |
| The static app (`web/`) | GitHub Pages (the same bundle as the demo, built with `TARK_ADAPTER=api`) | anon key only (public by design) | public |
| The worker (`worker/`) | GitHub Actions in `tark-workspace` | service key, model key, SEC contact | private repository, private logs |
| The admin CLI (`app/admin.py`) | Oscar's shell | service key | private environment |
| The laptop runner (`worker/run_job.py`) | Oscar's laptop | service key, model key | private environment |

The service key never enters the API. The API verifies the user's Supabase
JWT and forwards that same token to Supabase, so row-level security
(`db/002_policies.sql`) decides every read and write. The anon key alone
reads nothing (no grant to the anon role).

## 2. Create the Supabase project and apply the schema (Oscar, laptop session)

1. Create a project on the free tier. Choose a strong database password and
   keep it in a password manager. Do not enable any add-on.
2. Read the free-tier limits on the day and fill section 12.
3. In the SQL editor, run `db/001_schema.sql`, then `db/002_policies.sql`,
   then `db/003_storage.sql`, in that order. Each is re-runnable.
   Every time a table or a function is added later, in a file or through the
   dashboard, revoke the default grants on it before anyone can reach it.
   The database gives every new object to the anon and the authenticated
   roles by default, and `alter default privileges` covers tables only, and
   only for the role that ran the file. A new table needs its own policies
   and its own revoke, a new function needs its own revoke.
4. In Authentication settings: enable email and password, disable public
   sign-ups (invite only), set the site URL to the app's URL, and set the
   invite email's redirect to the app's login route.
5. Copy from the project settings: the project URL, the anon key, the
   service role key, and either the JWT secret (legacy projects) or note
   that the project uses JWT signing keys (the API then reads the JWKS at
   `<url>/auth/v1/.well-known/jwks.json` and needs no secret).
6. Run the tenancy tests from the laptop (section 8) before inviting anyone.

## 3. Create the private repository and its secrets (Oscar)

1. Create `tark-workspace`, private, empty.
2. Copy `worker/templates/run_job.yml`, `keep_alive.yml` and `backup.yml`
   to its `.github/workflows/`, replacing `OWNER/fiduciary-demo` with the
   public repository's name.
3. Secrets (Settings, Secrets and variables, Actions): `SUPABASE_URL`,
   `SUPABASE_SERVICE_KEY`, `ANTHROPIC_API_KEY`, `TARK_SEC_CONTACT`,
   `DATABASE_URL` (the direct connection string, for the backup).
   Variables: `TARK_API_URL` (the Render URL), `TARK_BUDGET_USD` (50 unless
   Oscar raises it), `TARK_TIME_BUDGET_S` (4800), `TARK_INGEST_MODEL`,
   `TARK_PRICES_JSON` (the confirmed price list, decision 8.34).
4. Create a fine-grained personal access token scoped to `tark-workspace`
   only with the single permission Contents: read and write (the permission
   `repository_dispatch` needs), 90-day expiry. This is `TARK_DISPATCH_TOKEN`
   for Render. Rotate it per section 11.
5. `private/identity.json` (R3-P3-9) lives here and nowhere else.

## 4. Create the Render service (Oscar)

1. New web service from the public repository, branch `main`, runtime
   Python 3.11, free instance. Build command
   `pip install -r requirements.txt`, start command
   `uvicorn app.main:app --host 0.0.0.0 --port $PORT --no-server-header`,
   health check path `/api/health`.
2. Environment: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET`
   (legacy projects only), `TARK_APP_ORIGIN` (the static app's origin,
   exactly one), `TARK_DISPATCH_REPO` (`<owner>/tark-workspace`),
   `TARK_DISPATCH_TOKEN`, `TARK_SIGNED_URL_SECONDS` (300). Render sets
   `RENDER_GIT_COMMIT`, which the API pins on every job.
3. Never add `SUPABASE_SERVICE_KEY` or `ANTHROPIC_API_KEY` to Render.
4. Read the free-tier limits on the day and fill section 12. The free
   service sleeps after idle minutes: the keep-alive workflow (section 9)
   calls `/api/health` every 10 minutes.

## 5. Deploy and roll back

Deploy: push to `main` after a green hook. Render builds and swaps on
health. The static app deploys through `gates.yml` as before (the public
demo) and, with `TARK_ADAPTER=api TARK_API_BASE=<render url>/api`, as the
workspace build. Roll back: in Render, redeploy the previous successful
deploy from its deploys list, or `git revert` the commit on `main` and
push. The schema never rolls back by itself: a schema change ships with a
new `db/00N_*.sql` file that is re-runnable, and the runbook entry that
says how to undo it.

## 6. Invite a partner (Oscar, admin CLI)

```
export SUPABASE_URL=... SUPABASE_SERVICE_KEY=...      # in the shell, never in a file
python -m app.admin workspace "Partner name, plan sponsor type"
python -m app.admin invite partner@example.com "Partner name, plan sponsor type"
```

Supabase Auth sends the invite. The partner sets a password on the app's
login route. The membership row is written by the CLI and the invite is in
`audit_log`. One user per workspace this round (R3-P4-0).

Removal is by request to the admin: `python -m app.admin delete-workspace
"<name>"` removes every object under the workspace's storage prefix, one
page of the listing at a time, and then the workspace row, which cascades
through every table. If an object is still there after the removal pass,
the command refuses to delete the rows and names what is left, because a
row that names an object is the honest state while the object exists. The
auth user stays in Supabase Auth and is deleted there by hand. The app's
notice says removal is by request.

## 7. Run a job, read its log, and what to do when it fails

A job is created by the partner (`POST /api/jobs`) and dispatched to the
worker workflow with `repository_dispatch`. The job row shows the step
(`preparing the record`, `fetching filings`, `extracting cell k of 32`,
`computing benchmark and liquidity`, `writing documents`, `writing views`,
`uploading`, `done` or `failed`) and the detail. The Actions log is in the
private repository under the workflow run named by the job id.

From the laptop, the same job with the same code:

```
export SUPABASE_URL=... SUPABASE_SERVICE_KEY=... ANTHROPIC_API_KEY=... TARK_SEC_CONTACT=...
python -m worker.run_job <job_id> --runner laptop            # the real model, under TARK_BUDGET_USD
python -m worker.run_job <job_id> --runner laptop --mock     # the rehearsal: mocked model, synthetic filing
```

What a job produces for a fund nobody has typed yet: the 55 cells (the
extractable 32 from the filings, the census prefills, the engine cells
where the inputs exist), a liquidity match whose capacity side says the
dealing terms are not on record, a benchmark selection that escalates
because no strategy has been judged, and the Investment Selection Record
that says all of that in words. A person's registry entry
(`python -m app.admin set-registry <product_id> entry.json`) and a facts
mapping in `src/build_facts.py` are what turn that into the reference
products' depth. For the proof run (ACAP Strategic Fund, R3-P4-8) the
laptop session writes both before October 16, from the filings.

When a job fails, the row's `failure_reason` is the sentence to read
first. Then:

| Reason starts with | Meaning | Action |
|---|---|---|
| the model budget is spent | the spend ledger is at `TARK_BUDGET_USD` | Oscar raises the variable in the private repository (and the laptop shell), then `python -m app.admin requeue <job_id>` |
| the cost estimate | this job alone would exceed what remains | same, or wait for a smaller corpus |
| the wall-time budget | the extraction stopped cleanly, cells so far are kept in the job's working copy but no record was written | requeue, or raise `TARK_TIME_BUDGET_S` |
| no filings held, refused | the fetcher found nothing for the registry's document sets | check the CIK on EDGAR, set a registry entry with the right forms, requeue |
| the record did not validate | a pipeline invariant failed | read the Actions log, fix in the public repository, requeue with the new commit |
| the workspace storage or database refused | a policy or a quota | check the Supabase dashboard for the free-tier limit, then requeue |
| the runner hit an unexpected | a defect | the Actions log names the class, file an issue, run from the laptop |

`python -m app.admin jobs` lists the last 50 jobs with state, runner and
cost. A job that is `running` with no live workflow (a runner died) is
requeued with `--running`, after a look at its `updated_at` and the
Actions list, so two runners never write under one prefix.

## 8. Tenancy tests and the security review (laptop session)

```
export SUPABASE_URL=... SUPABASE_ANON_KEY=... SUPABASE_SERVICE_KEY=... TARK_API_URL=...
python tests/tenancy/test_tenancy.py            # creates tagged users and rows, tests, deletes them
python tests/tenancy/test_tenancy.py --cleanup  # if a run was interrupted
```

The tests are generated from `db/001_schema.sql`: every table with
`workspace_id` is tested for user A reading B's rows by workspace id and by
row id, plus storage paths, the anon key, every API route without a token
and with an expired one (set `TARK_EXPIRED_TOKEN` to a real expired token
for that case), and a signed URL after its expiry. The ASVS review of the
policies, the auth module and the storage rules is
`docs/security/asvs_review_<date>.md`, re-run after every fix.

## 9. Free-tier operations: keep-alive and backups

`keep_alive.yml` calls `/api/health` every 10 minutes and, once a day,
`/api/health?db_check=1`, which runs `select public.ping()` with the anon
key so the Supabase project does not pause for inactivity.
`backup.yml` runs `python -m worker.backup` nightly: `pg_dump` of the
public schema and data plus a listing of the bucket, under
`backups/<date>/` in the bucket, pruned after 30 days. Once the proof run
passes, pin the variable `TARK_PIPELINE_REF` in the private repository to
that commit, so the nightly job runs code that CI has run. The bucket's
size cap (50 MB per object) applies to the dump too: when the database
outgrows it, give the backups their own bucket.

Restore test (once before October 23, on a local Postgres, never the
project):

```
createdb tark_restore
python -m worker.restore <date> --target postgresql://localhost/tark_restore
```

It prints the row count per table. Record the date and the counts here:

| Date | Backup | Rows restored | By |
|---|---|---|---|
| not yet run | | | |

## 10. Raise the budget

`TARK_BUDGET_USD` is a total across every job (decision 8.13), read by
the worker from the private repository's variables and by the laptop
runner from the shell. The API does not read it. Raising it is Oscar's
action: change the variable, then requeue the refused job. `python -m
app.admin budget` prints spent, budget and remaining, where spent is the
sum of every job's estimate at the configured price list.

## 11. Rotate a key

| Key | Where it lives | Rotate by |
|---|---|---|
| Supabase service key | private repository secrets, Oscar's shell | Supabase project settings, then update both places |
| Supabase anon key | Render environment, the static build | same, then redeploy both |
| JWT secret or signing keys | Render environment (secret) or none (JWKS) | Supabase Auth settings, then update Render |
| `TARK_DISPATCH_TOKEN` | Render environment | GitHub, fine-grained tokens, then update Render |
| `ANTHROPIC_API_KEY` | private repository secrets, Oscar's shell | the console, then update both |
| `DATABASE_URL` password | private repository secrets | Supabase project settings, then update |

No key is in this repository, a build, a log line or a screenshot (rule 8).
`app/settings.py` redacts every known secret from the API's log lines.

## 12. Free-tier limits, as read on the day (to fill at setup)

Fill from each host's pricing page on the day of setup, never from memory.

| Service | Tier | Limit | Read on | What stops at the limit |
|---|---|---|---|---|
| Supabase database size | free | | | writes fail, the project may pause |
| Supabase storage size | free | | | uploads fail (a job fails at `uploading`) |
| Supabase egress | free | | | downloads throttle or fail |
| Supabase inactivity pause | free | | | the project pauses, the keep-alive query prevents it |
| Render instance hours | free | | | the service stops until the month rolls |
| Render idle sleep | free | | | cold starts, the keep-alive prevents them |
| Render memory | free | | | the API restarts |
| GitHub Actions private minutes | free | | | jobs queue until the month rolls, the laptop runner takes over |

## 13. The fallback (R3-P4-9)

If the unattended path is not ready, the budget blocks a job, or a job
fails twice, Oscar runs `python -m worker.run_job <job_id> --runner laptop`
with his keys. Same library, same rows, the partner sees the same status
and result, `runner = laptop` in the audit log. Rehearse once with `--mock`
before October 16 and record the date here:

| Date | Job | Result | Notes |
|---|---|---|---|
| not yet rehearsed | | | |

## 14. Views the workspace serves

`/api/records/<id>/<view>.json` serves the files the worker wrote under the
record's prefix: `record` (the 55 cells, each with the copy layer's
rendering, the coverage, the registry fields, human verification pending),
`selection`, `liquidity` (this plan's match), `cohort`, `facts`, `report`
(the ingest report with the cost), and `documents` through the documents
rows. `/api/reference/<key>/<view>.json` serves the same views for the 16
reference products from the public record. R3-P1's adapters read these
shapes (`schema` names `tark.record.v1` and so on).
