# ASVS 4.0.3 Level 1 review of the workspace API, the policies and the worker (2026-09-08)

## Scope

Commit `da912d4` (`git rev-parse --short HEAD`). When the review began HEAD was `2cb593e` and the directories `app/`, `db/`, `worker/` and `tests/` were untracked workspace files, with uncommitted edits to `src/plan_intake.py`, `src/tark_benchmark.py` and `src/tark_memo.py`. Those files were committed as `da912d4` while the review was in progress. The twelve files below were re-checked after that commit (line counts and every cited line) and are byte for byte what `da912d4` holds. At the time of writing the working tree is clean.

Files reviewed in full, nothing else was read and nothing was run:

- `db/001_schema.sql` (144 lines)
- `db/002_policies.sql` (75 lines)
- `db/003_storage.sql` (21 lines)
- `app/auth.py` (97 lines)
- `app/main.py` (366 lines)
- `app/supabase.py` (132 lines)
- `app/settings.py` (58 lines)
- `app/admin.py` (131 lines)
- `worker/run_job.py` (273 lines)
- `worker/templates/run_job.yml` (54 lines)
- `worker/templates/keep_alive.yml` (20 lines)
- `worker/templates/backup.yml` (32 lines)

Threat model used: Supabase Auth issues the credentials. The browser holds the user's JWT and the public anon key, so PostgREST and Storage are a public API surface that the user can call directly, and the row-level security policies are the access control. The FastAPI routes are a convenience on top of that surface. The service key lives only in the worker (a private repository's Actions secrets) and in the operator's shell. Control ids are from ASVS 4.0.3. Where a requirement is described without a certain id, the id is marked approximate. Level 2 controls that the task asked for are included and marked as such and do not count as fails.

## V2 Authentication

| Control | Verdict | Evidence | Note |
|---|---|---|---|
| V2.1 to V2.9 (password security, general authenticator, authenticator lifecycle, credential storage, credential recovery, lookup secrets, out of band, one time verifiers, cryptographic verifiers) | Not applicable | app/auth.py:1-10, app/main.py:188-192, db/001_schema.sql:4-5 | Supabase Auth owns every credential. The API verifies a token and issues nothing. No password, hash or reset code exists in the twelve files. |
| 2.3.1 System generated initial passwords or activation codes are random and expire | Not applicable | app/admin.py:55-62, app/supabase.py:110-114 | The invite is Supabase's own endpoint. The link, its randomness and its expiry are the provider's. |
| 2.10.4 (Level 2 in the standard, included because the task asks) Secrets and API keys are not in source code | Pass | app/settings.py:30-43, app/admin.py:36-39, worker/run_job.py:80-83, worker/templates/run_job.yml:44-53, worker/templates/backup.yml:28-31 | Every secret is read from the environment or the Actions secrets context. No literal key, secret or token appears in any of the twelve files. |
| Verification of the provider's session token (approximate, the closest control is 3.5.3 which is Level 2) | Pass | app/auth.py:20, 60-90 | The algorithm from the unverified header is only accepted from the allow list at line 20 or as HS256 at line 76, so none and unknown algorithms are refused at line 81. Asymmetric tokens are verified with the key named by kid from the project's JWKS (lines 50-57, 69-75). HS256 is verified only with the configured secret (lines 76-79). The audience must be authenticated (lines 75, 79). Expiry is enforced by the library (lines 82-83). An empty sub is refused (lines 86-88). The anon and service key JWTs carry no aud claim and are refused as bearers. The issuer claim is not checked (see Observations). |

## V3 Session Management

| Control | Verdict | Evidence | Note |
|---|---|---|---|
| 3.1.1 The application never reveals session tokens in URL parameters | Pass | app/auth.py:93-97, app/main.py:188-190 | Only the Authorization header is read. The signed download URL at app/main.py:344 and app/supabase.py:90-96 carries a storage token in its query string. That is a capability for one object with a 300 second life by default (app/settings.py:21), not the session token. |
| 3.2.1 A new session token is generated on authentication | Not applicable | app/auth.py:1-3 | Supabase issues the token. |
| 3.2.2 Session tokens possess at least 64 bits of entropy | Not applicable | app/auth.py:75, 79 | The token is a signed JWT from Supabase. |
| 3.2.3 Session tokens are stored in the browser using secure methods | Not applicable | app/main.py:1-11 | The front end is outside the files reviewed. |
| 3.3.1 Logout and expiration invalidate the session token | Pass | app/auth.py:82-83, app/main.py:9-11 | Expiry is checked on every request. Logout is the provider's and the API has no logout route. An access token issued before a logout is accepted until its exp claim, and the API cannot see the logout. The window is the project's access token lifetime (see Observations). |
| 3.3.2 Re-authentication occurs periodically when users remain logged in | Not applicable | app/auth.py:1-10 | Refresh token policy is the provider's. |
| 3.4.1 to 3.4.5 Cookie attributes (Secure, HttpOnly, SameSite, host prefix, path) | Not applicable | app/main.py:156-158, 188-190 | No cookie is set or read. The token travels as a bearer header and the CORS middleware does not allow credentials. |
| 3.7.1 A full, valid login session is required before sensitive transactions | Pass | app/main.py:226, 237, 241, 256, 260, 279, 283, 287, 325, 340, 353, 357 | Every route except /api/health declares the claims dependency, which verifies the token before the handler runs. |

## V4 Access Control

| Control | Verdict | Evidence | Note |
|---|---|---|---|
| 4.1.1 Access control rules are enforced on a trusted service layer | Pass | app/main.py:194-195, app/supabase.py:36-40, db/002_policies.sql:7-15, 24-75, db/003_storage.sql:12-19 | Row-level security in Postgres decides every read and write. The API forwards the user's JWT with the public anon key and holds nothing stronger. The per-table map is under this table. |
| 4.1.2 User and data attributes used by access controls cannot be manipulated by end users | Fail | db/002_policies.sql:50-54, worker/run_job.py:142-145, 158-160, 218-230 | Policy `jobs_member_insert` pins membership of workspace_id, state, runner, cost_usd and progress_step only. A member of workspace A, holding their JWT and the anon key, can POST /rest/v1/jobs directly with workspace_id A and a product_id and plan_id that belong to workspace B. The worker then reads that product and plan with the service key (run_job.py:142-143), writes B's plan intake into the job directory (158-160), runs the pipeline on it and uploads the outputs, the records row and the documents rows under A (218-230). B's plan data reaches A. The caller must know a foreign uuid (random v4), which a former member or a leaked log can supply. The same policy leaves attempts, tokens_in, tokens_out, pipeline_commit, failure_reason, progress_detail, claimed_at, started_at and finished_at caller chosen at insert. The API route at app/main.py:289-293 is correct, the gap is only on the direct PostgREST path. |
| 4.1.3 The principle of least privilege exists | Fail | db/001_schema.sql:123, 136-139 | The good part first. The API never holds the service key (app/settings.py:12-23 has no field for it, app/main.py:195 uses the anon key plus the user's token, app/main.py:218 the anon key alone). The service key appears only in app/admin.py:36, worker/run_job.py:80 and the private repository's secrets (run_job.yml:46, backup.yml:30). The child process environment drops the service key (worker/run_job.py:163). The anon role has no table grant (002_policies.sql:18) and no policy. Storage has no write policy for authenticated (003_storage.sql:10-19). The fail: db/001_schema.sql:138 revokes `spend_total` from public only. Supabase's default privileges grant execute on every new function in public to anon and authenticated, and a revoke from public does not remove those grants. `spend_total` is security definer (001_schema.sql:123) so RLS on spend does not apply. A POST to /rest/v1/rpc/spend_total with the anon key alone returns the total spend across every workspace. The same pattern at line 136 leaves `is_member` executable by anon, harmless because auth.uid() is null there. |
| 4.1.5 Access controls fail securely, including when an exception occurs | Pass | app/main.py:164-174, 176-192, 197-202, app/auth.py:52-54 | A refused token is a 401 with one sentence. A JWKS fetch failure raises through the dependency and becomes the generic 500. Supabase 401 and 403 become a 403 with no detail. An audit failure is logged and grants nothing. |
| 4.2.1 Sensitive data and APIs are protected against insecure direct object reference | Pass | app/main.py:37, 204-210, 282-300, 324-349, 352-361 | Every id-addressed route is scoped, the list is under this table. Absent and foreign ids answer the same 404 sentence (app/main.py:206, 209), so no enumeration oracle exists. The one cross-tenant reference reachable is the direct PostgREST insert counted under 4.1.2. |
| 4.2.2 The application defends against CSRF | Pass | app/main.py:156-158, 188-190 | Bearer token in a header, no cookies, CORS restricted to one origin without credentials. A cross-site form cannot attach the token. |
| 4.3.1 Administrative interfaces use appropriate multi-factor authentication | Not applicable | app/admin.py:33-39 | The admin surface is a local command line that reads the service key from the operator's environment. The web administrative interface is the Supabase dashboard, outside the files reviewed (see Observations). |
| 4.3.2 Directory browsing is disabled | Pass | app/main.py:151, 123-144 | No static mount. The reference routes open named files built from allow-listed keys only. |
| Tenant isolation in every table and every storage path (approximate, the standard covers it under 4.1.1, 4.1.2 and 4.2.1) | Pass | db/002_policies.sql:24-75, db/003_storage.sql:13-19 | Every tenant table carries workspace_id (001_schema.sql:17, 26, 35, 48, 75, 89, 102, 113) and every select policy calls `is_member(workspace_id)`. Storage reads require the first folder of the object name to be a workspace uuid the caller belongs to (003_storage.sql:17-18). Backups under backups/ fail the folder regex and are unreadable by users. The one insert-side gap is counted under 4.1.2. |
| No service key in the request path (approximate, part of 4.1.3) | Pass | app/settings.py:12-23, 46-47, app/main.py:194-195, 218 | The settings object has no service key field. SUPABASE_SERVICE_KEY appears in app/settings.py only as a name to redact. |

Per route, how the id is scoped:

- `GET /api/jobs/{job_id}` (app/main.py:282-284): `one()` at 204-210 requires the lowercase uuid shape (UUID_RE at 37) and selects `id=eq.<id>` with the user's token, `jobs_member_select` (002_policies.sql:46-48) filters to the caller's workspaces, absent and foreign both answer 404. Scoped.
- `POST /api/jobs` (app/main.py:286-300): product_id and plan_id are read through `one()`, so both must be visible under `products_member_select` and `plans_member_select`. Line 291 refuses when their workspace_ids differ. Line 293 takes workspace_id from the product row and not from the body. Scoped at the API. The database policy alone does not repeat this check (4.1.2).
- `GET /api/records/{record_id}/{view}.json` (app/main.py:324-336): `one()` under `records_member_select` (002_policies.sql:56-58), view is allow-listed at 36 and 326, the object is fetched with the user's token under `workspace_member_read` (003_storage.sql:13-19), which checks the first folder of `artifacts_prefix` against membership. Scoped twice.
- `GET /api/documents/{document_id}` (app/main.py:339-349): `one()` under `documents_member_select` (002_policies.sql:60-62), the signing request at 344 carries the user's token so the storage select policy applies again before a URL is minted. Scoped twice.
- `POST /api/plans` and `POST /api/products` (app/main.py:240-252, 259-275): workspace_id comes from the body and is not checked by the API. `plans_member_insert` (002_policies.sql:35-37) and `products_member_insert` (002_policies.sql:42-44) refuse a workspace the caller is not a member of. Scoped by the database.
- `GET /api/plans`, `GET /api/products`, `GET /api/jobs` (app/main.py:236-238, 255-257, 278-280): no filter, the select policies scope the result.
- `GET /api/me` (app/main.py:225-233): filters on the token's sub, `members_self_select` (002_policies.sql:28-30) restricts to the caller's own rows anyway. The workspace list is built from database values.
- `GET /api/reference/index.json` and `GET /api/reference/{key}/{view}.json` (app/main.py:352-361): public reference data with no tenant, key and plan key constrained by KEY_RE (38, 124, 133), view by VIEWS.
- `GET /api/health` (app/main.py:213-222): no id, no token, no tenant data.

Per table, what a user may do (the service role bypasses all of it):

- workspaces: select as a member (002_policies.sql:25-26). No insert, update or delete for users.
- workspace_members: select own rows only (28-30). No write for users, so nobody adds themselves.
- plans: select and insert as a member (33-37). No update or delete, on purpose (a plan is immutable once used by a job).
- products: select and insert as a member (40-44). No update or delete, the registry entry is the admin's (app/admin.py:65-72).
- jobs: select as a member (47-48), insert with five pinned columns (51-54). No update or delete, so a user cannot cancel a job or edit its state, and the worker owns every other column. The insert gap is under 4.1.2.
- records, documents, spend: select only (57-58, 61-62, 74-75). Written only by the worker.
- audit_log: select as a member (65-66), insert with user_id equal to the caller and workspace null or a membership (69-71). The event column is not restricted (see Observations).
- anon: no grant (18), no policy on any table, no storage policy. It can execute `ping` (001_schema.sql:144) as intended, and `spend_total` by the default privileges gap (4.1.3).
- storage.objects: select under a workspace folder the caller belongs to (003_storage.sql:13-19). No insert, update or delete policy for authenticated, so uploads are the service role's only.

## V5 Validation and Encoding

| Control | Verdict | Evidence | Note |
|---|---|---|---|
| 5.1.1 The application has defenses against HTTP parameter pollution | Pass | app/main.py:214, 340, 357, 57-71 | The three query parameters are scalars, FastAPI takes one value each. Bodies are typed models. |
| 5.1.2 Frameworks protect against mass parameter assignment | Pass | app/main.py:57-71, 250, 272-273, 293-295 | Each insert dictionary is built field by field from the model, unknown body fields are ignored. At the database layer the jobs insert accepts free columns, counted under 4.1.2. |
| 5.1.3 All input is validated using positive validation | Fail | app/main.py:58, 64, 59-60, 261-263, 105 | Passes: ids by UUID_RE (37, 205), views by VIEWS (36, 124, 326), reference keys by KEY_RE (38, 124, 133), job creation ids through `one()` (289-290). Fails: `PlanIn.workspace_id` and `ProductIn.workspace_id` (58, 64) are unvalidated strings sent to PostgREST. A non-uuid becomes a 400 from PostgREST which the handler at 185-186 turns into a 502 that tells the user to try again. The cik at 261-263 is checked with `str.isdigit` only, which accepts non-ASCII digits and any length, while the column takes one to ten ASCII digits (001_schema.sql:36), so those inputs also become a 502. A digit string longer than 4300 characters makes `int()` at 105 raise and become a generic 500. `source_note` (60) and `intake` (59) have no size cap and the API sets no request body limit. |
| 5.1.4 Structured data is strongly typed and validated against a schema | Pass | app/main.py:57-71, 244, 250 | Pydantic models for the three bodies. The intake goes through `plan_intake.scaffold`, the record's own validator, and the scaffolded output is what is stored, not the raw body. |
| 5.1.5 URL redirects and forwards only allow destinations on an allow list | Pass | app/main.py:346-347, app/supabase.py:93 | The one redirect targets a URL built on the configured Supabase host. No user value reaches the Location header. |
| 5.2.2 Unstructured data is sanitized to enforce allowed characters and length | Fail | app/main.py:60, db/001_schema.sql:28 | `source_note` has no length limit in the model or the column. It is stored and returned as JSON, so the risk is storage growth and a large row in every plans listing, not injection. Same fix item as 5.1.3. |
| 5.2.4 The application avoids eval or dynamic code execution | Pass | app/main.py:104, 109, 114, 118, 137, 144, worker/run_job.py:183, 217, app/admin.py:115 | `json.loads` only. No eval, exec, pickle or template engine. |
| 5.2.6 The application protects against SSRF | Pass | app/main.py:309, app/supabase.py:43, app/auth.py:52 | Outbound targets are the configured Supabase URL and the literal api.github.com. No user value becomes a URL or a host. |
| 5.3.1 and 5.3.3 Output encoding and context-aware escaping | Pass | app/main.py:170, 180, 336, 40, 42 | Every response is JSON through FastAPI or a JSON body from storage returned as application/json with nosniff and a CSP of default-src none. The API renders no HTML. The scaffold's refusal text at 246 may echo the caller's own intake value, still inside a JSON string. |
| 5.3.4 Data selection or database queries use parameterized queries (no injection into PostgREST filters) | Pass | app/supabase.py:125-132, app/main.py:207, 228, 230 | The values a user can influence that reach `_filters` are uuids that passed UUID_RE (207) and the token's sub (228). The `in.(...)` list at 230 is built from database values. `_filters` at supabase.py:131 passes any value whose first segment is an operator name through unchanged, which is a hazard for any future caller that forwards free text (see Observations). The admin CLI uses that pass-through on purpose at app/admin.py:76. |
| 5.3.8 The application protects against OS command injection | Fail | worker/templates/run_job.yml:54, worker/run_job.py:166-175 | The worker is fine: `subprocess.Popen` takes an argv list with no shell, the cik and product_key elements are constrained by the column checks (001_schema.sql:36, 39), and plan_key always begins with ws_ (app/main.py:247-248) so it cannot be parsed as an option. The template is not: run_job.yml:54 expands `${{ github.event.client_payload.job_id || inputs.job_id }}` inside the run script before bash parses it. A job_id that closes the double quote and appends a command runs on the runner with SUPABASE_SERVICE_KEY, ANTHROPIC_API_KEY and TARK_SEC_CONTACT in the environment (44-48). The sender needs the dispatch token or write access to the private repository, so a leaked dispatch token becomes a service key compromise, which is more than the "can only dispatch that workflow" scope described at app/settings.py:18. keep_alive.yml:17 and 20 expand `vars.TARK_API_URL` the same way, that value is set by repository administrators (see Observations). |
| 5.3.9 The application protects against local or remote file inclusion | Pass | app/main.py:123-144, 153 | Reference paths are built from KEY_RE-checked keys and a cohort id read from the trusted registry file. The worker's file name handling is under 12.3.1. |
| 5.5.3 Deserialization of untrusted data is avoided or protected | Pass | app/main.py:57-71, worker/run_job.py:183 | JSON only. The worker parses the child's stdout lines as JSON and ignores what does not parse. |

## V7 Error Handling and Logging

| Control | Verdict | Evidence | Note |
|---|---|---|---|
| 7.1.1 The application does not log credentials or payment details | Pass | app/main.py:160-162, 169, 178, 202, 317, 320, app/settings.py:46-58, app/auth.py:24, worker/run_job.py:98-99, 163 | Every API log line passes through `redact`, and the lines carry only method, path, exception class and status. AuthError text never includes the token. The worker's `say` redacts too. The child process does not receive the service key. |
| 7.1.2 The application does not log other sensitive data | Pass | worker/run_job.py:212, 249 | Line 212 logs the last 600 characters of the child's stderr and line 249 the first 200 characters of an exception text, both redacted, into the private repository's Actions log. Either could carry a fragment of a filing or a plan value. Acceptable for a private log, worth knowing. |
| 7.1.3 (Level 2) The application logs security relevant events including failed authentication and access control failures | Not applicable | app/main.py:188-192, 231, 251, 274, 296, 345, app/admin.py:61, worker/run_job.py:117, 135, 240, app/main.py:155, 162 | Level 2, so not counted. Audit rows exist for login, plan_created, product_created, job_created, download, invite, job_claimed, job_done and job_failed. A refused token (188-192) and a 422 are not logged anywhere. The "login" row is written on every /api/me call, not on a login. The API's log is an in-memory ring of 200 lines that nothing writes to stdout or a sink, so it vanishes on restart and never reaches Render's log stream (see Observations). |
| 7.4.1 A generic message is shown when an unexpected error occurs | Pass | app/main.py:164-174, 176-186 | One sentence and a 500 for any exception, the class name goes to the private log. Supabase failures map to 403, 409 or 502 with fixed sentences. FastAPI's own 422 for a malformed body is a structured list that echoes the offending value back to its sender, not a stack trace. |
| No stack traces to clients (approximate, part of 7.4.1) | Pass | app/main.py:168-171 | The middleware catches every exception before Starlette's default error page. |

## V8 Data Protection

| Control | Verdict | Evidence | Note |
|---|---|---|---|
| 8.2.1 Anti-caching headers are set so sensitive data is not cached in browsers | Pass | app/main.py:45, 172-173, 181, 184, 186 | Cache-Control no-store on every response, including the 302 at 347 and the handler-built responses. |
| 8.3.1 Sensitive data is sent in the body or headers, never in query strings | Pass | app/main.py:188-190, 344, app/settings.py:21, 41 | Credentials travel in the Authorization header. The signed download URL carries a storage token in its query for 300 seconds by default. TARK_SIGNED_URL_SECONDS has no upper bound (see Observations). |
| 8.3.2 Users have a method to remove or export their data on demand | Fail | app/main.py:9-11, db/002_policies.sql:24-75, app/admin.py:6-11, app/supabase.py:59-81 | No route deletes anything, no policy allows a user delete, the admin CLI has no delete command and the client has no row delete method. Export by hand exists through the JSON routes and the signed downloads. |
| Secrets come from the environment only and are never returned (approximate, overlaps 2.10.4) | Pass | app/settings.py:1-4, 30-43, 46-58, app/main.py:215, 232-233 | /api/health and /api/me return no configuration value beyond the public pipeline commit. |
| Signed URLs expire quickly (approximate) | Pass | app/settings.py:21, 41, app/main.py:344, 348, app/supabase.py:91 | 300 seconds by default, sent to Supabase as expiresIn, echoed to the caller as expires_in. |

## V9 Communications

| Control | Verdict | Evidence | Note |
|---|---|---|---|
| 9.1.1 TLS is used for all client connectivity | Pass | app/main.py:41, 309, app/supabase.py:43, app/auth.py:52, worker/templates/keep_alive.yml:17 | The API sets HSTS for its own host (one year with includeSubDomains, no preload). httpx verifies certificates by default for the Supabase and GitHub calls, and the GitHub base URL is a literal https. Nothing asserts that SUPABASE_URL (app/settings.py:33) or vars.TARK_API_URL begins with https, an http value would be used silently (see Observations). |
| 9.1.2 and 9.1.3 Strong TLS configuration, old versions disabled | Not applicable | app/main.py:2 | TLS is terminated by Render, Supabase and GitHub. |
| HSTS from the hosts (approximate, 14.4.5 covers the header) | Pass | app/main.py:41 | Set by the API for its host. The static app's host and Supabase set their own. |

## V11 Business Logic (added, two Level 1 controls apply)

| Control | Verdict | Evidence | Note |
|---|---|---|---|
| 11.1.4 The application has sufficient anti-automation controls against excessive requests and denial of service | Fail | app/auth.py:50-57, 70-72, app/main.py:216-218 | A request whose unverified header names an unknown kid forces a fresh JWKS fetch with a 10 second timeout inside a synchronous dependency. An unauthenticated sender can therefore make the API perform one outbound request per inbound request and hold a threadpool thread for each. No route has a rate limit. /api/health with db_check reaches the database without a token. |
| 11.1.5 Business logic limits protect against likely business risks | Pass | worker/run_job.py:107-114, 146-148, db/001_schema.sql:70-71 | The conditional claim prevents two runners on one job, the partial unique index prevents a second active job per product and plan, the spend total is checked against the budget before the model is called. A user can still queue an unbounded number of jobs across pairs and each one dispatches a workflow (app/main.py:297), the budget stops model spend but not runner minutes. |

## V12 Files and Resources

| Control | Verdict | Evidence | Note |
|---|---|---|---|
| 12.1.1 The application does not accept large files that could fill storage | Pass | db/003_storage.sql:7-8, app/main.py:9-11 | The bucket caps objects at 52428800 bytes and the API has no upload route. JSON bodies have no cap, counted under 5.1.3. |
| 12.3.1 User-submitted filename metadata is not used directly by system or framework filesystems, and path traversal is prevented | Fail | worker/run_job.py:160, 167, app/main.py:247-248, 244 | The API is fine: ids and views are allow-listed before any path is built. The worker is not: line 160 writes `data/plans/<plan_key>.json` and line 167 passes plan_key as an argument, and plan_key comes from a plans row that a user wrote through POST /api/plans. The API only prefixes ws_ and truncates it. The worker, which runs with the service key, performs no check of its own. Whether `plan_intake.scaffold` constrains the alphabet is outside the files reviewed, so this is a fail at the point of use: a plan_key containing a slash or dot-dot writes the plan JSON outside the job directory on the runner. The manifest paths at 220-223 are read and uploaded without normalization too, they come from the pipeline the worker itself runs. |
| 12.3.2 User-submitted filename metadata is validated or ignored when served | Pass | app/main.py:343-344, app/supabase.py:94-95 | The download name is the last segment of the storage path the worker wrote, sent as a URL-encoded query value to the storage host, never to a filesystem. |
| 12.4.1 Files from untrusted sources are stored outside the web root | Pass | db/003_storage.sql:6-8, worker/run_job.py:223 | Objects live in a private bucket on the storage host, never on the API's disk. |
| 12.4.2 Files from untrusted sources are scanned | Not applicable | db/003_storage.sql:10-11 | Users upload nothing. The worker writes its own outputs. |
| 12.5.1 The web tier only serves files with specific extensions | Pass | app/main.py:324-336, 339-349 | The API serves JSON views by name and hands out signed URLs for everything else. |
| 12.5.2 Direct requests to uploaded files are never executed as HTML or JavaScript | Pass | app/main.py:40, 42, 336, app/supabase.py:94-95 | Views are returned as application/json with nosniff and a CSP of default-src none. Downloads carry the download parameter so the storage host answers with an attachment disposition. |
| 12.6.1 The server accepts connections only to resources on an allow list | Pass | app/main.py:309, app/supabase.py:43 | Same evidence as 5.2.6. |
| Upload only by the service role, with a content type and a size limit (approximate, the task's control) | Pass | db/003_storage.sql:7-8, 10-19, worker/run_job.py:222-225 | Only a select policy exists for authenticated on storage.objects, so RLS denies insert, update and delete to users. The worker uploads with the service key. The content type is guessed from the file name, application/octet-stream when unknown. The bucket sets no allowed_mime_types (see Observations). |

## V13 API and Web Service

| Control | Verdict | Evidence | Note |
|---|---|---|---|
| 13.1.1 All application components use the same encodings and parsers | Pass | app/main.py:57-71, 336 | JSON in, JSON out, one parser. |
| 13.1.3 API URLs do not expose sensitive information such as keys or session tokens | Pass | app/main.py:282, 324, 339, 356 | Paths carry ids only. The signed URL on the storage host is the one URL with a token, by the provider's design. |
| 13.2.1 Enabled RESTful HTTP methods are valid for the user or action | Pass | app/main.py:157, 213-361 | Each route declares one method and the router answers 405 to others. CORS preflight allows GET and POST only. |
| 13.2.2 JSON schema validation is in place and verified before input is accepted | Pass | app/main.py:57-71, 244 | Pydantic models for every body, the intake validated by the record's own scaffold. |
| 13.2.3 RESTful services that use cookies are protected from CSRF | Not applicable | app/main.py:156-158 | No cookies. |
| 13.2.5 (Level 2) REST services explicitly check the incoming Content-Type | Not applicable | app/main.py:57-71 | Level 2. FastAPI parses the body as JSON only for an application/json content type and refuses others with 422. |
| JSON only (approximate, the task's control) | Pass | app/main.py:57-71, 336 | No form, multipart or HTML handling exists. |

## V14 Configuration

| Control | Verdict | Evidence | Note |
|---|---|---|---|
| 14.2.1 All components are up to date, with dependency pinning | Fail | worker/templates/backup.yml:25, 28-31, worker/templates/run_job.yml:27, 32, 41, worker/templates/backup.yml:14, 19 | backup.yml:25 installs httpx with no version at all, and that job holds DATABASE_URL and the service key. run_job.yml:41 installs the public checkout's requirements.txt, which is outside these files. The actions are pinned to a major tag (checkout v4, setup-python v5), not a commit. |
| 14.2.2 Unneeded features, documentation, sample applications and configurations are removed | Pass | app/main.py:151, app/supabase.py:116-119 | Swagger, ReDoc and the OpenAPI document are disabled. `user_of_token` in supabase.py is unused by any caller, dead but harmless. |
| 14.3.2 Debug modes are disabled in production | Pass | app/main.py:6, 151 | FastAPI is constructed without debug, the documented uvicorn command has no reload. |
| 14.3.3 HTTP headers and responses do not expose detailed version information | Pass | app/main.py:215 | /api/health returns the first 12 characters of the pipeline commit without a token. The pipeline repository is public, so this names nothing secret. Uvicorn adds a server header with its name and no version (see Observations). |
| 14.4.1 Every HTTP response contains a Content-Type header with a safe character set | Pass | app/main.py:336, 170, 180 | application/json on every JSON response. |
| 14.4.2 All API responses contain Content-Disposition attachment with a filename | Fail | app/main.py:39-46 | SECURITY_HEADERS has no Content-Disposition. With nosniff and the CSP the practical risk is low, the fix is one dictionary entry. |
| 14.4.3 A Content Security Policy is in place | Pass | app/main.py:40 | default-src none, frame-ancestors none, base-uri none. Right for a JSON API. |
| 14.4.4 X-Content-Type-Options nosniff is set | Pass | app/main.py:42 | On every response through the middleware at 172-173. |
| 14.4.5 Strict-Transport-Security is set | Pass | app/main.py:41 | One year with includeSubDomains. |
| 14.4.6 A Referrer-Policy is set | Pass | app/main.py:43 | no-referrer. |
| 14.4.7 The content cannot be embedded in a third party site by default | Pass | app/main.py:40 | frame-ancestors none. No X-Frame-Options for legacy browsers, acceptable for an API that returns no HTML. |
| 14.5.1 The server accepts only the HTTP methods in use | Pass | app/main.py:157, 213-361 | Same evidence as 13.2.1. |
| 14.5.2 The supplied Origin header is not used for authentication or access control | Pass | app/main.py:156-158, 188-190 | Origin feeds the CORS response headers only. Access is the token's. |
| 14.5.3 CORS uses a strict allow list of trusted domains | Pass | app/main.py:156-158 | allow_origins is the one configured origin. When TARK_APP_ORIGIN is unset there is no CORS middleware at all, so the default is closed. allow_headers is limited to authorization and content-type, credentials are not allowed. |
| No documentation pages (approximate, part of 14.2.2) | Pass | app/main.py:151 | docs_url, redoc_url and openapi_url are None. |
| Workflow templates do not run on the public repository and do not expose a secret (approximate, the closest controls are 14.1.x which are Level 2) | Pass | worker/templates/run_job.yml:1-4, 44-48, worker/templates/backup.yml:1-3, 28-31, worker/templates/keep_alive.yml:1 | The templates live under worker/templates/ and the public repository's .github/workflows/ holds only gates.yml, so none of them runs here. Secrets enter as step environment from the private repository's secrets context, GitHub masks them in logs, and no step echoes them. No template declares a permissions block, so the job token carries the repository's default permissions (see Observations). The shell expansion in run_job.yml:54 is counted under 5.3.8. |

## Fails to fix before R3-P4 exits

1. db/002_policies.sql:50-54 and worker/run_job.py:142-145 (4.1.2). Add to the with check of `jobs_member_insert`: `and exists (select 1 from public.products p where p.id = jobs.product_id and p.workspace_id = jobs.workspace_id) and exists (select 1 from public.plans q where q.id = jobs.plan_id and q.workspace_id = jobs.workspace_id) and attempts = 0 and tokens_in = 0 and tokens_out = 0 and failure_reason = '' and progress_detail = '' and claimed_at is null and started_at is null and finished_at is null`. The durable form is a composite foreign key that survives any later policy edit: `unique (id, workspace_id)` on products and on plans, then on jobs `foreign key (product_id, workspace_id) references public.products (id, workspace_id)` and the same for plan_id. In the worker, after line 143, refuse the job when `product["workspace_id"] != ws or plan["workspace_id"] != ws`.
2. db/001_schema.sql:138 (4.1.3). Replace the revoke with `revoke all on function public.spend_total() from public, anon, authenticated`. Do the same at line 136 for `is_member` from anon. Apply the same pattern to every function added later.
3. worker/templates/run_job.yml:54 (5.3.8). Move the expression into the step's env as `JOB_ID: ${{ github.event.client_payload.job_id || inputs.job_id }}` and run `python -m worker.run_job "$JOB_ID" --runner actions`. In worker/run_job.py before line 101, refuse a job_id that does not match the uuid shape. Do the same with `vars.TARK_API_URL` in keep_alive.yml:17 and 20.
4. worker/run_job.py:160 and 167 (12.3.1). Before line 158: `if not re.fullmatch(r"[a-z0-9_]{2,32}", str(plan_obj.get("plan_key", ""))): return fail("the plan key is not one the runner accepts")`. Also refuse a manifest path at line 221 that is absolute or contains a dot-dot segment.
5. app/main.py:58, 64, 60, 261 (5.1.3, 5.2.2). `workspace_id: str = Field(pattern=UUID_RE.pattern)` on PlanIn and ProductIn. Check the cik with `re.fullmatch(r"[0-9]{1,10}", cik)` and refuse with 422. `source_note: str = Field(default="", max_length=2000)`. Refuse a body over a fixed size (a Content-Length check in the middleware, 256 KB is generous for an intake).
6. app/main.py:39-46 (14.4.2). Add a Content-Disposition entry to SECURITY_HEADERS with the value attachment and the filename api.json.
7. worker/templates/backup.yml:25 (14.2.1). Pin httpx to the version the public checkout's requirements.txt pins, in the form `python -m pip install -q "httpx==<version>"`, or install from that requirements file as run_job.yml does.
8. Data removal (8.3.2). Add a `delete` method to app/supabase.py and a `delete-workspace <workspace>` command to app/admin.py that removes the storage prefix through `delete_objects` (app/supabase.py:103) and then the workspace row, which cascades through every tenant table (db/001_schema.sql:17, 26, 35, 48, 75, 89, 113). Write one sentence in the app's notice that removal is by request to the admin.
9. app/auth.py:70-72 (11.1.4). Allow a forced JWKS refresh at most once every 30 seconds per process. When the kid is still unknown inside that window, refuse with the existing sentence without fetching.

## Observations

- Access control lives in the policies, not in the routes. The browser holds the JWT and the anon key, so every table and every column that a policy leaves open is reachable directly at /rest/v1. Any new table or column needs a policy review, and the tenancy test generator should exercise the direct PostgREST path, not only the FastAPI routes.
- db/002_policies.sql:19-22 grants select and insert to authenticated but never revokes the default privileges Supabase gives that role on every new table (all, which includes update, delete and truncate). Row-level security denies update and delete when no policy exists, and PostgREST exposes no truncate, so this holds by one layer today. Add `revoke all on all tables in schema public from authenticated` before the grants so the grant layer says what the comment at line 10-11 of 003_storage.sql and the header of 002 claim.
- db/002_policies.sql:68-71 `audit_member_insert` lets a user write any event in the check list of db/001_schema.sql:104-105, including invite, job_claimed, job_done, job_failed and health, with any detail JSON. A member can forge worker events into the trail their workspace reads. Restrict the event column in the policy to login, plan_created, product_created, job_created and download, and cap the size of detail.
- app/auth.py:75, 79 do not check the issuer. Supabase tokens carry iss equal to the project URL plus /auth/v1. Passing that as issuer to jwt.decode binds the HS256 path to this project even when a secret is reused. Also pass options requiring exp and sub so a token without exp is refused rather than tolerated by line 90.
- 3.3.1 window: the API accepts an access token until its exp, whatever the user did at the provider. Set the project's access token lifetime to the shortest the app tolerates.
- app/main.py:231 writes a "login" audit row on every /api/me call. Rename the event or write it once per token (for example keyed by the token's iat). Refused tokens at 188-192 and 422 refusals are not logged at all, a line by kind would cost nothing.
- app/main.py:155, 162: the log ring never leaves memory. Print each redacted line to stdout as well so Render keeps it.
- app/main.py:182-184 answers every 409 with the job sentence. A duplicate product (db/001_schema.sql:42) is also a 409 and gets the wrong sentence.
- app/supabase.py:131: `_filters` treats any value whose first segment is an operator name as a raw PostgREST expression. Add a `raw()` marker type for the admin's deliberate uses and quote everything else, so a future route cannot forward free text into a filter.
- worker/templates/run_job.yml:30: the checkout ref comes from the dispatch payload. A holder of the dispatch token can name any commit reachable in the public repository, including a fork pull request head, and the runner executes that worker code with the secrets. Add a step that checks the commit is an ancestor of main (`git merge-base --is-ancestor`) before the run step, or take the commit from a repository variable the deploy updates.
- None of the three templates declares a permissions block. Add `permissions: contents: read` (or an empty block) so the job token cannot write to the private repository. backup.yml:17 checks out main rather than a commit, so whoever can push to the public main branch runs code with DATABASE_URL in the nightly job. Pin it.
- worker/run_job.py:163 strips the service key, the URL and the dispatch token from the child's environment but not DATABASE_URL, which the laptop runner's shell may hold. Add it to the list.
- worker/run_job.py:175-208 reads stdout to end of file before touching stderr. A child that writes more than the pipe buffer to stderr blocks on the write while the parent waits on stdout, and the job hangs until the Actions timeout. Redirect stderr to a file or drain both pipes.
- worker/run_job.py:222 guesses the content type from the file name. db/003_storage.sql:6-8 sets no allowed_mime_types on the bucket. Set the list to what the worker writes (json, pdf, docx, markdown, text, csv) so a wrong object type is refused at the store.
- app/settings.py:41: TARK_SIGNED_URL_SECONDS has no upper bound. Clamp it to an hour.
- app/settings.py:33 and keep_alive.yml:17: assert the scheme is https at load time so a misconfigured URL fails loudly.
- app/admin.py:76 requeues a running job. If the runner is still alive, two runners write under the same prefix with upsert (app/supabase.py:87) and the second records insert fails on unique(job_id) after uploading. Requeue only failed jobs by default, and running ones behind an explicit flag after a check of updated_at.
- db/003_storage.sql:7 applies the 52428800 byte cap to backups in the same bucket. A pg_dump over that size fails to upload. Consider a second bucket for backups.
- Uvicorn adds a server header naming itself. Run it with the no-server-header flag.
- FastAPI's 422 for a malformed body is a structured list with the offending value, not one sentence, which departs from rule 11. A handler for RequestValidationError that returns one sentence would align it.
- app/auth.py:35-37 `Claims.expired` and the role field are unused. Either use them or drop them.
- 4.3.1: the Supabase dashboard is the real administrative interface. Turn on MFA for the Supabase organization and for the GitHub account that owns the private repository.
- The per-workspace job count is unbounded (11.1.5). A queued cap per workspace would bound runner minutes as the spend ledger bounds model dollars.

## Counts

Pass 59, Fail 10, Not applicable 13 (82 verdict rows, 10 fails across 9 fix items, Level 2 rows are marked and counted as Not applicable).

## Re-run after the fixes (2026-09-08, second pass)

Commit `65f2757`. A fresh reviewer read the twelve files again in full, plus `app/testing.py`, `app/test_workspace.py`, `worker/test_worker.py`, `tests/tenancy/test_tenancy.py` and sections 4, 6, 7 and 9 of `docs/WORKSPACE.md`. Nothing was run. Every line cited below was read in the working tree at that commit.

### The ten Fail rows

| Control | Was | Now | Evidence (file:line) | Note |
|---|---|---|---|---|
| 4.1.2 User and data attributes used by access controls cannot be manipulated by end users | Fail | Pass | db/001_schema.sql:71-72, 76-92, db/002_policies.sql:60-65, worker/run_job.py:155-156 | Three layers, and the durable one is the table. The composite foreign keys make a job row whose product or plan sits in another workspace impossible whatever a policy later says, and the block at 001:76-92 adds them to a project created from the earlier file. The policy also pins attempts, tokens_in, tokens_out, failure_reason, progress_detail and the three timestamps, and the worker refuses the job again at 155-156. The direct insert is exercised at app/test_workspace.py:247-269. What a direct caller still chooses is pipeline_commit, created_at and updated_at, which set a display value and reach no runner. |
| 4.1.3 The principle of least privilege exists | Fail | Pass | db/001_schema.sql:162-165, db/002_policies.sql:21-23, app/testing.py:142-145 | `spend_total` is revoked from public, anon and authenticated and granted to service_role alone, so the anon key no longer reads the spend total across every workspace. `is_member` is revoked from public and anon and granted to authenticated and service_role, which is what the policies need. The table grants now start from a revoke rather than from Supabase's defaults. A function added later still needs its own revoke, because line 23 sets default privileges for tables only. |
| 5.1.3 All input is validated using positive validation | Fail | Partly | app/main.py:62, 64, 68, 277-279, 170-171 | workspace_id on both bodies is a uuid pattern, source_note has a maximum length, and the CIK is checked with an ASCII-only `re.fullmatch` of one to ten digits before it reaches `int()` at line 109, so the non-ASCII digit and the 4300 digit paths are closed. The body cap is bypassable: line 170 reads Content-Length only, so a chunked request that sends no Content-Length skips the check and the whole body is read. The direct PostgREST path takes an intake of any size in any case. |
| 5.2.2 Unstructured data is sanitized to enforce allowed characters and length | Fail | Partly | app/main.py:64, db/001_schema.sql:28, db/002_policies.sql:41-42 | The model caps source_note at 2000 characters. The column still carries no check, and `plans_member_insert` lets a member post straight to /rest/v1/plans, so on the surface this review treats as the real one the value is still unbounded. The fix belongs in the column. |
| 5.3.8 The application protects against OS command injection | Fail | Pass | worker/templates/run_job.yml:28, 65, keep_alive.yml:18, 21, 24, worker/run_job.py:106 | No workflow expression reaches a shell. Every remaining expression sits in a `with`, `env` or `concurrency` block that bash never parses, and the three run scripts read shell variables inside double quotes. The runner refuses a job id that is not a uuid before its first query, gated at worker/test_worker.py:179-180. |
| 8.3.2 Users have a method to remove or export their data on demand | Fail | Partly | app/supabase.py:80-86, app/admin.py:76-87, docs/WORKSPACE.md:107-113, app/test_workspace.py:319-324 | The delete method, the `delete-workspace` command and the runbook sentence exist and the gate exercises them. Two gaps. The sentence in the app's own notice that fix item 8 asks for is not there (web/src/app/App.tsx:62 carries the footer and says nothing about removal). And the removal itself has a listing limit, see the new findings. |
| 11.1.4 The application has sufficient anti-automation controls against excessive requests and denial of service | Fail | Fail | app/auth.py:57-70, app/main.py:229-238 | The forced refresh window at 58-63 works only once a key set is cached. Line 64 refetches whenever `self._keys` is empty, and on a legacy HS256 project the JWKS holds no keys, so it stays empty forever. An unauthenticated sender whose token header says ES256 therefore still makes the API perform one outbound fetch with a 10 second timeout per inbound request, which is the original amplification with an extra step. The offline gate at app/test_workspace.py:150-157 seeds a cached key first, so it does not cover this path. Separately /api/health?db_check=1 still reaches the database with no token and no route has a rate limit. |
| 12.3.1 User-submitted filename metadata is not used directly by system or framework filesystems, and path traversal is prevented | Fail | Pass | worker/run_job.py:51, 158-159, 241-242 | plan_key and product_key must match `[a-z0-9_]{2,32}` before the plan file is written at 173 and before either becomes an argument at 180-181, and a manifest path that is absolute or holds a dot-dot segment stops the upload before any byte is read. Two nits are under the new findings and neither escapes the job directory. |
| 14.2.1 All components are up to date, with dependency pinning | Fail | Partly | worker/templates/backup.yml:24-27, requirements.txt:6-9 | The bare `pip install httpx` is gone and the backup job installs the checkout's requirements file, which is what the fix item asked for. That file pins no version for httpx, fastapi, uvicorn or pyjwt, so the job holding DATABASE_URL and the service key still resolves whatever is current on the day. The actions are still at major tags rather than commits (backup.yml:16, 21, run_job.yml:32, 43). |
| 14.4.2 All API responses contain Content-Disposition attachment with a filename | Fail | Pass | app/main.py:47, 180-181, app/test_workspace.py:172-173 | Every response carries it, including the 401, the 413 and the 422. No legitimate client of this API breaks. The static app reads the routes with fetch, where the header has no effect on the response body, the browser never needs to read the header so its absence from the CORS expose list costs nothing, and the only response where the header is inert is the 302 at app/main.py:363, which a browser follows rather than saves. |

### The observations

| Observation | Status | Evidence |
|---|---|---|
| Any new table or column needs a policy review, and the tenancy generator should exercise the direct PostgREST path | Partly taken | The offline gate now drives the direct path (app/test_workspace.py:247-269, 378) and the worker gate drives the cross-workspace job (worker/test_worker.py:167-178). The project-level generator still only reads (tests/tenancy/test_tenancy.py:122-125) and never attempts an insert or an rpc call. |
| Revoke the default privileges Supabase gives authenticated before the grants | Taken | db/002_policies.sql:21-23 |
| Restrict the event column of `audit_member_insert` and cap the size of detail | Taken | db/002_policies.sql:81-85, gated at app/test_workspace.py:263-269 |
| Check the issuer, and require exp and sub | Taken | app/auth.py:21, 53-55, 89, 94, gated at app/test_workspace.py:114-126 |
| Set the project's access token lifetime to the shortest the app tolerates | Not taken | docs/WORKSPACE.md:41-44 lists the Authentication settings to change and the lifetime is not among them |
| Rename the login event or write it once per token, and log refused tokens and 422s | Partly taken | The 422 is logged at app/main.py:186. The login row is still written on every /api/me call (app/main.py:247) and a refused token still reaches no log (app/main.py:204-208) |
| Print each redacted log line to stdout so the host keeps it | Not taken | app/main.py:164-166 still only appends to the in-memory ring |
| A duplicate product should not answer with the job sentence | Taken | app/main.py:196-200, gated at app/test_workspace.py:224-226 |
| Add a raw marker type to `_filters` so a future route cannot forward free text | Not taken | app/supabase.py:133-140 is unchanged |
| Check the dispatched checkout commit is an ancestor of main | Taken | worker/templates/run_job.yml:38-42, and the check runs before the install step and before any pipeline code executes |
| Declare a permissions block in the three templates and pin the backup checkout | Partly taken | worker/templates/run_job.yml:21-22, keep_alive.yml:11-12, backup.yml:9-10 declare contents read. backup.yml:19 still falls back to main until a commit is put in the variable |
| Strip DATABASE_URL from the child environment | Taken | worker/run_job.py:176-177, which also drops SUPABASE_JWT_SECRET |
| Drain both pipes or redirect stderr | Taken | worker/run_job.py:189-193, 226-227 |
| Set allowed_mime_types on the bucket | Taken | db/003_storage.sql:6-11, with the runner refusing an unknown suffix first at worker/run_job.py:244-246 |
| Clamp TARK_SIGNED_URL_SECONDS | Taken | app/settings.py:47, gated at app/test_workspace.py:174-177 |
| Assert the https scheme at load | Partly taken | app/settings.py:33-37 covers SUPABASE_URL and TARK_APP_ORIGIN. The template's TARK_API_URL is still used as given (worker/templates/keep_alive.yml:18, 21) |
| Requeue only failed jobs by default | Taken | app/admin.py:90-96, gated at app/test_workspace.py:315-324. The look at updated_at is the operator's, named in the refusal sentence at line 96 |
| Give the backups their own bucket | Partly taken | db/003_storage.sql:7 still holds one bucket and one 52428800 byte cap. docs/WORKSPACE.md:186-188 records the condition and the remedy |
| Run uvicorn with the no-server-header flag | Taken | docs/WORKSPACE.md:72-74 |
| Answer a malformed body with one sentence | Taken | app/main.py:184-188, gated at app/test_workspace.py:202-204 |
| Use or drop `Claims.expired` and the role field | Partly taken | app/auth.py:36-38 is used by the gate at app/test_workspace.py:141-142. The role field at app/auth.py:32, 104 is read by nothing |
| Turn on MFA for the Supabase organization and the GitHub account | Not taken | docs/WORKSPACE.md:35-49 and 51-67 do not mention it |
| Bound the per-workspace job count | Not taken | No cap exists in db/002_policies.sql:57-65 or in app/main.py:302-316 |

### New findings in the changed lines

1. app/main.py:170-171. The request body cap reads Content-Length only. A chunked request that sends no Content-Length is not measured and the body is read in full. Counting bytes as the stream is consumed is the form that holds.
2. app/auth.py:64. The forced refresh window is skipped whenever the cached key set is empty, so the anti-automation fix does not hold on a project whose JWKS publishes no keys. Detail is in the 11.1.4 row above.
3. app/admin.py:82. `delete_workspace` calls `list_objects` with its default limit of 1000 and never pages, so a workspace with more objects than that keeps the remainder. It also treats the listing as flat object paths, which is what the fake returns (app/testing.py:295-299). Whether the real Storage list route returns nested paths or one folder level is outside the files reviewed. If it returns one folder level, the call removes folder names, the objects stay, and the workspace rows are deleted at app/admin.py:86 anyway, so the objects are left with no row that names them. Page the listing and confirm the shape against the real project before the runbook's removal sentence is relied on.
4. worker/run_job.py:106 and 158. Python's `re.match` with a pattern ending in the dollar sign also matches a string with one trailing newline, so a job id or a plan key with a trailing newline passes the new shape checks. Neither value escapes the job directory, and the effect is a stray newline in a file name or a filter, but `re.fullmatch` is what these two checks mean. app/main.py:221 has the same slack and predates the fixes.
5. worker/run_job.py:241. The manifest path check tests the raw string, so a percent-encoded dot-dot is not caught and would be decoded by the storage host into the object key built at line 247. The path comes from the pipeline the worker itself pinned and checked out, so this is defense in depth rather than a live path.
6. worker/run_job.py:192 and 226. `err_fh` is closed only on the path that reaches line 226. An exception between the open and that line leaves the handle to the garbage collector. A context manager around the child run closes it on every path.
7. db/002_policies.sql:23. `alter default privileges` covers tables and not functions, and applies only to objects created by the role that runs the file. A function added later, or a table created by another role through the dashboard, gets Supabase's default grants to anon and authenticated again. The comment at db/001_schema.sql:160-161 says the rule, and the rule needs a place in the schema checklist of the runbook so it is applied rather than remembered.

Second pass counts: Pass 64, Fail 5, Not applicable 13
