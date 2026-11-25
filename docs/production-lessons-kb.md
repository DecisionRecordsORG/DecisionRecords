# Production Lessons KB

This note captures operational lessons that must be applied before future deployments or agent-led changes.

## Artifact Boundaries

Decision Records has three separate artifacts:

- `website`: the private commercial marketing website in `ee/marketing`.
- `production-private`: hosted app instances that include private EE modules.
- `production-public`: the open-source Community Edition app source and release artifacts. It is not deployed as a live hosted app.

Before building, deploying, or validating anything, identify which artifact is being changed. Do not deploy the Community frontend as the commercial website.

## Website Deployments

- Validate the built site with a real browser, not only `curl`.
- Capture the production page title, `h1`, console errors, and a screenshot after deployment.
- Check the actual production URL, not only a local dev server.
- Verify local port ownership before trusting a local screenshot. Use `lsof -i :<port>` or equivalent when a port was already in use.
- Keep Angular HTML/app-shell responses on `no-cache`/`no-store`; hashed JavaScript assets can otherwise strand stale app shells.
- A successful asset upload is not a successful deployment. The acceptance check is a nonblank production page with the expected commercial homepage content.
- For the commercial marketing site in `ee/marketing`, a new route is not deployable until three surfaces are kept in sync: `src/app/app.routes.ts`, `src/app/services/seo.service.ts`, and `scripts/prerender-blog.py`. Missing the prerender entry causes direct URL requests like `/releases` to fall back to the generic SPA shell in production.
- If the marketing site is routed through the Cloudflare edge worker, a route change is not complete until `ee/infra/cloudflare-worker.js` is updated and deployed with the marketing path allowlist change. Shipping the page code without the edge routing update can send users to the app or sign-in flow instead of the marketing page.
- For route-specific production regressions, compare `curl -I` on the broken URL against a known-good marketing URL. Marketing responses should look like static-site traffic; app headers such as backend CSP or rate-limit headers usually mean the request is still being routed to the backend.
- The marketing Angular build must stay independent of local machine quirks and live internet fetches. Keep Angular CLI disk cache disabled for local builds and keep production font inlining disabled; on macOS, Angular 18 + LMDB cache can abort under Node 20, and Google Fonts inlining makes builds fail in restricted-network environments.

## MCP Validation

- Validate MCP with the protocol behavior real clients use, not only a simple `tools/list` cURL request.
- Test authenticated `GET /api/mcp` probes for older Streamable HTTP clients.
- Test `initialize`, `server/discover`, `tools/list`, and at least one `tools/call`.
- Test missing auth, invalid auth, and valid API-key paths separately.
- Re-check the current official MCP transport docs before claiming compatibility with a protocol version.

## CI And PR Checks

- Required PR checks must come from the `pull_request` or `merge_group` lane. Do not assume a green `workflow_dispatch` run will satisfy GitHub branch protection for a PR.
- Do not share a concurrency group between `pull_request` and `workflow_dispatch`. Include the event type in the concurrency key so manual diagnostics cannot cancel the canonical PR run.
- Keep the required check name reserved for the canonical lane. Manual diagnostics should publish a distinct check name such as `Quality Gate (Manual)`.
- When GitHub shows a PR as blocked with missing checks, inspect all three views before changing code: `gh pr checks <number>`, `gh run view <run-id>`, and `gh api repos/<owner>/<repo>/commits/<sha>/check-runs`.
- Recovery order for stuck PR checks:
  1. Re-run the existing `pull_request` job graph.
  2. If that lane was cancelled or never attached, push a no-op commit to trigger a fresh `pull_request` synchronize event.
  3. Use `workflow_dispatch` only to diagnose the branch outside the required-check path.
- Keep required CI helpers inside the repository that owns the workflow, or on a dependency revision that is already guaranteed on that workflow's base branch. Do not make a private-repo PR check depend on a new helper that exists only on an unreleased public-repo branch.
- When validating private submodule lineage in CI, fetch child `origin/main` inside the workflow step that already has the repository token. Do not assume a generic helper can authenticate an ad hoc fetch from a private submodule remote on its own.
- When a public-repo workflow needs to read GitHub Actions metadata from a private sibling repo, do not rely on the public repo's default `github.token`. Pass the private repo token into the specific step that calls the GitHub API, and keep the public token available separately for public-repo lookups.
- Delivery-obligation summaries should fetch deployment metadata lazily. Do not query enterprise or marketing workflow history unless at least one current contract actually requires that artifact, or a non-required private repo can turn a healthy summary job into an unnecessary failure.

## Community Release Publishing

- A release tag is not just a packaging event. It must re-run enough Community validation to stand on its own before publishing public artifacts.
- Do not assume prior PR CI is a sufficient release gate. Tagging the wrong commit or tagging after drift on `main` can still publish a broken public image if release-time validation is too shallow.
- Release metadata checks must cover the public version surface, not only `version.py`. Pinned version examples in release-facing docs should match the current Community version.
- A successful enterprise deploy does not imply that self-hosted Community users received the same shared-core fix. Shared-core changes need an explicit Community release decision, and shared-core security fixes should stay tracked as required Community patch releases until the release tag exists.
- A successful `docker build` is not a working image. Community `v2.1.0` and `latest` were published without `decision_relationships.py`: `models.py` imported it, `Dockerfile.community` copied an explicit file list that nobody updated, and the container died at startup with `ModuleNotFoundError`. Building never imports the app, and pytest runs from the repo root where every module exists, so every check stayed green.
- The Community image must be started, not only built, before it is published. `scripts/smoke_test_ce_image.sh` boots the image with only `SECRET_KEY`, waits for `/api/health`, checks database init, the Angular shell and the Docker `HEALTHCHECK`, and prints container logs on failure. It runs twice: on the image's default SQLite database and against a PostgreSQL container. CI runs it after the image build, and `release.yml` runs it before the registry login and push steps. Do not reorder those steps or add a push ahead of the smoke test.
- Do not maintain a hand-written list of application modules in a Dockerfile. `Dockerfile.community` copies root modules with `COPY *.py ./`, and `Dockerfile.community.dockerignore` is an allowlist that keeps `ee/`, tests, `run_local.py`, `.env*` and databases out of the build context. That ignore file is only honoured by BuildKit, so build the Community image with BuildKit (the default since Docker 23).
- `scripts/check_ce_image_modules.py` is the fast static version of the same guarantee: it walks first-party imports from `app.py` and fails when one is not shipped by `Dockerfile.community`, or when a forbidden file would be. It runs in commit QA, CI and release validation. Run it whenever a root module or the Dockerfile changes.
- The multi-platform release push is smoke tested on `linux/amd64` only. The Python file set is identical across platforms, but an arm64-only breakage (for example a missing wheel) would not be caught by the gate.
- The main backend test job runs on Python 3.12 while the Community image runs `python:3.11-slim`. The PostgreSQL test job and the image smoke test run on 3.11, so a syntax or stdlib feature newer than 3.11 shows up there.
- Community code paths must be exercised with the `ee` package unimportable, not only with `DECISION_RECORDS_EDITION=community`. `crypto.py` imported the private Key Vault client inside a function, so the edition flag did not protect it and saving SMTP settings returned 500 for self-hosted users. Guard optional `ee` imports with `try`/`except ImportError` and test them with the module blocked in `sys.modules`.
- Install and contributor docs must be run from a public checkout before a release. The default `ng build` and `npm start` configurations and the old `run_local.py` default all required the private `ee/` tree, and the release notes told users to download a compose file that builds from source.

## Schema Migrations

- Startup migrations must cover real upgrade paths from deployed databases, not only fresh `db.create_all()` schemas.
- When a model adds columns to long-lived tables such as `tenant_settings` or `auth_configs`, add or update the startup migration in `migrations.py`; do not rely on one-off EE scripts to carry production schema forward.
- Migration regression tests should start from a legacy on-disk schema with prior `schema_migrations` entries already recorded, then call `init_database()`. Fresh in-memory schemas hide exactly the class of drift that caused the missing `tenant_settings.allow_microsoft_oauth` production error.

## Git And Repository Safety

- Treat the public repo and `ee/` as separate Git repositories.
- Treat `ee/marketing` as a third repository whenever the commercial website changes.
- Do not stage `ee/` changes into the public repo by accident; only the submodule pointer should change there.
- Do not mix unrelated private infra or marketing changes into an application/MCP commit.
- Commit order for nested repo work is strict: `ee/marketing` first, then `ee`, then the public repo. A parent pointer update must never reference dirty child work.
- Merge order and merge strategy are also strict: merge `ee/marketing` before `ee`, then `ee` before the public repo, and use merge commits on `marketing` and `ee`. Rebase and squash merges on child repos break durable parent submodule pointers because the gitlink SHA no longer lands on child `main`.
- Nested Git checks launched from hooks must clear inherited `GIT_*` environment variables before inspecting child repositories, or staged parent commits can be misread as dirty nested submodules.
- Run the CE/EE boundary check before public commits.
- Run commit QA before committing: `uv run python scripts/qa_check.py --mode commit`.
- Enable hooks in both the public repo and `ee`, then verify them with `uv run python scripts/verify_git_hooks.py`.
- Keep delivery obligations in repo state, not in memory. If a merge creates release or deploy follow-up work, record it through `.delivery/changes/*.toml` so the next session can derive what is still owed.

## Edge Routing

- Do not route static assets by `Referer`. Chrome sends the importing module (a `.js` URL) as `Referer` for dynamic `import()`, Safari sends the page; both Angular builds emit hashed chunks at the root, so neither the file name nor the `Referer` identifies the owning origin. Serving the app's HTML on the website host made every lazy route blank in Chrome while Safari worked.
- The website host serves the website. App pages requested there are redirected (302, `no-store`) to the app host; only `/api/*` and `/auth/*` are proxied. Pages a third party embeds from the website host cannot be redirected and need an explicit exception with its own tests.
- Never use a permanent redirect at the edge for app routing: browsers cache 301/308 indefinitely and a rollback cannot reach them.
- Edge routing has a test suite in the private infrastructure repo. A routing change is not done until a table case covers it, and after every edge or Enterprise deploy the read-only handoff smoke check must pass.
- The website-to-app sign-in depends on environment variables (`SESSION_COOKIE_DOMAIN`, `OAUTH_BASE_URL`, `APP_BASE_URL`, `USE_HTTPS`) that no workflow sets. Keep the committed environment template in the private infrastructure repo in step with the running configuration.
- Test fixes on a path that is actually registered. A defect reported in a module that is never imported or routed is not live; confirm the route exists in the running app's URL map first.

## Dependency Drift

- Pin every runtime dependency that selects behaviour. On 2026-11-21 an Enterprise deploy took production down: `requirements.txt` pinned Flask-SQLAlchemy but not SQLAlchemy, a fresh build resolved SQLAlchemy 2.1, and 2.1 uses psycopg 3 for `postgresql://` URLs. The image had psycopg 3 without its binary package and no system libpq, so every worker failed at import with "no pq wrapper available". The previous image, built three months earlier from the same file, had SQLAlchemy 2.0 and used psycopg2.
- A green build is not a tested runtime. CI and the image smoke test run on SQLite; nothing exercised PostgreSQL before the deploy. The Enterprise deploy replaces the running container before its health check, so a bad image means an outage, not a failed deploy.
- When a deploy fails its health check, read the service journal for the worker traceback first, and compare `pip list` inside the previous and new images before suspecting the code change.
- A pin on a package does not pin what it installs. SQLAlchemy was never named in `requirements.txt`; it came in through Flask-SQLAlchemy. `requirements.txt` now lists every installed package with an exact version, including gunicorn, and `tests/test_requirements_pins.py` fails in CI when a line is not exact or an installed dependency has no line. Move a pin on purpose, in its own pull request, following the note at the top of the file.
- The private Enterprise requirements were left on ranges, and it cost three days of analytics. The image rebuilt on 2026-11-21 installed posthog 8, which removed an argument the client set-up passed. The set-up catches every exception and logs it, so the app started, the deploy pre-flight and health check passed, and product analytics recorded nothing until the error was read in the start-up log on 2026-11-24. `ee/requirements.txt` is now pinned to exact versions, and `tests/test_analytics_client.py` builds the real client so an incompatible version fails CI.
- An optional integration that swallows its own start-up error fails silently. After a deploy, read the start-up log for `ERROR` lines, not only the health endpoint; and give each such integration one test that constructs the real client with the installed library.

## Database Backends

- SQLite proves nothing about PostgreSQL. It does not load the PostgreSQL driver, enforce foreign keys or keep locks across sessions. CI now runs the fixture-based backend tests against a PostgreSQL service (`TEST_DATABASE_URL`) and starts the built Community image against a PostgreSQL container (`SMOKE_DATABASE=postgres scripts/smoke_test_ce_image.sh <image>`); the release workflow does the same before it logs in to the registry.
- The first PostgreSQL run found two defects that had been invisible: the start-up connection check opened its own psycopg2 connection with `sslmode=require` regardless of the URL, so the PostgreSQL setup in `docs/self-hosting.md` (a stock server without TLS) could never initialise; and a test inserted a row with a dangling foreign key. Check a connection through the engine the application uses, never through a second hand-built one.
- `/api/health` is a liveness route: it answers `{"status": "ok"}` with no database at all. `/health` is the route that reports the database (`"status": "healthy"`, `"database": "connected"`). Anything that decides whether a build or a deploy is good must read `/health`.
- Test fixtures that drop tables must release their session first (`db.session.remove()`); on PostgreSQL an open transaction makes `DROP TABLE` wait forever. `TEST_DATABASE_URL` is refused unless the database name contains "test", because the fixtures drop every table.

## Test Configuration Versus Production

- The app has two shapes, decided when it is imported: with a built frontend (`frontend/dist`, every production installation) it serves the Angular app; without one it registers legacy template routes (`index`, `settings`, `profile`). CI has no build, so it only ever tested the second shape. A redirect built with `url_for('index')` passed every test and answered 500 in production: sign-in through a tenant's own OIDC provider failed after the account had been created or found.
- Never name a view in `url_for()` that is registered conditionally. Redirect to a path. `tests/test_user_limit.py` reads every `url_for()` call in the Python modules and templates and fails when the view does not exist in both shapes.
- `tests/app_test_utils.load_test_app()` loads the app the same way whether or not a build exists in the checkout, and `built_frontend=` loads it as production runs it. A test of a redirect, an error page or anything else that depends on which routes exist should run in that shape too.
- The same mismatch hid a second defect: the browser tests create administrators with the role on their membership only, the way a promoted member has it, while the administrator endpoints looked at an older per-account flag. The settings page loaded and every request on it was refused. A test helper that creates data differently from the sign-up path is worth keeping when the difference is one real users can have.
- In Community Edition the AI endpoints were reachable without the AI module and answered 500, two of them on every load of the organisation settings and profile pages. An endpoint that belongs to an optional module must answer cleanly when the module is absent, and a page that loads on every visit should be opened once in a real Community build while watching the server log for 500s.

## Background Threads And The Test Database

- CI's PostgreSQL job failed with `deadlock detected` in the teardown of a test that had nothing to do with the cause, followed by `duplicate key ... ix_tenants_domain` in the next test's setup. A retention thread started by a test five minutes earlier was still alive. `tests/test_retention_scheduler.py::test_a_new_process_starts_its_own_thread` started two threads and stopped one: `stop_scheduler()` only knew the thread the module state pointed at. The other woke after its 60 seconds, by then without the test's stand-in for the check, and ran the real retention queries against the shared test database once a minute for the rest of the run. Its `SELECT count(users.id)` held locks on some tables while a fixture's `DROP TABLE` held others.
- It had been there since the scheduler was added and stayed hidden because the suite ended before the timing lined up. Adding tests made the run longer and the collision likely. A leak like this shows as a failure somewhere else, later, sometimes: when a fixture's `drop_all()` deadlocks, look for a second connection first, not at the test that failed. PostgreSQL's log names both statements when the server runs with `log_lock_waits=on` and a short `deadlock_timeout`.
- Anything that starts a thread must be able to stop every thread it started. `retention.stop_scheduler()` now stops all of them, and `retention.scheduler_threads()` lists the ones alive.
- A background thread must not be able to start under tests, however the app was loaded. `ensure_scheduler` refuses when `TESTING` is set in the app or the environment, when `FLASK_ENV=testing`, and when `PYTEST_CURRENT_TEST` is set, which pytest does for every test and which child processes inherit. An autouse fixture in `tests/conftest.py` fails the test that leaves a retention thread alive, so the failure is reported where it is caused.
- Fixtures that drop the schema go through `tests.conftest.drop_schema()`, which removes the session and empties the engine's pool before and after. That protects a fixture from its own connections. It is not a defence against a second writer and must not become one: no retries, sleeps or lock timeouts around `drop_all()`.
- A green local run proves little about a timing fault. The same suite passed locally on PostgreSQL several times with the thread leaked. It was found by asking, after every test, which threads were alive, and reproduced by removing the minute's wait.

## Data Retention

- A promise that depends on an operator step is not kept where nobody took the step. The deletion timelines (7, 30 and 90 days, 24 months) ran only when something called `POST /api/admin/execute-gdpr-tasks`, the self-hosting guide left that to a cron job, and nothing in the repository scheduled it. Work the product promises must be started by the product. Retention now runs from a thread in each worker that claims the day's run in the database (`retention.py`).
- The task could not have finished on PostgreSQL even when called. It deleted a decision or a tenant while rows still pointed at it (relationships, space links, audit log entries, role requests), so the first real expired tenant made the request answer 500 and skipped everything after it, every time. The tests of that route repeated the route's queries in the test body and ran on SQLite, which enforces no foreign keys, so they proved nothing. Test a delete on PostgreSQL with a row in every table, and compare the whole database before and after.
- The undo was broken too: restoring a soft-deleted tenant always answered 500 and had no test. Before automating an erasure, test the way back.
- A first automatic run after a long gap is the dangerous one. Count limits alone would let a small backlog through, so a category is also held back when its oldest item is more than a few days overdue. A person looks at the list before a backlog is erased.
- Compare stored dates with naive UTC values. The application writes aware datetimes into `timestamp` columns; on a PostgreSQL session that is not UTC they are stored shifted by the session's offset, and an aware value in a filter is converted the same way. On a server in `Europe/Stockholm` a deadline 30 minutes in the future already counted as passed.
- When hard-deleting, list every table and decide. `retention.TENANT_ERASE_RULES` names each table and a test fails when a model is added without a rule.
- Anonymising a row does not anonymise copies of it. A person's name was also written as text beside the reference (the author on a comment), into JSON (audit details, a stored Teams conversation), and into rows keyed by email address in another letter case. After an anonymisation the person was still named in 15 columns. `retention.ACCOUNT_TEXT_RULES` now names every text, JSON and binary column, and `tests/test_account_anonymise.py` reads every such column of every table after an anonymisation looking for the person. Prove an erasure by searching for the data, not by checking the fields the code is known to clear.
- A published sentence about personal data is a test case. The export was said to include comments and consent preferences and had neither. `data_export.EXPORT_RULES` names every column that references a user, and a test fails when a new one has no rule.

## Enterprise Deploy Safety

- Order matters more than checks. The deploy used to push `latest`, restart production and only then look at health. It now builds the image with the commit tag only, imports and boots that image against PostgreSQL on the runner, and logs in to Azure only after that has passed.
- The VM's systemd unit pulls and runs the `latest` tag on every start. Deploying is therefore "move `latest`, restart", and rolling back is "move `latest` back, restart". `scripts/deploy_enterprise_image.sh` records the image `latest` points to before it changes anything and puts it back when the new image does not report a healthy, connected database. A specific tag cannot be deployed until the unit takes the tag from its environment.
- `az vm run-command invoke` exits 0 when the command it ran on the VM failed. With `docker pull ... && systemctl restart ...` a failed pull leaves the old container running, the health check passes, and the deploy looks successful without deploying anything. The VM command now prints a marker as its last step and the deploy requires it.
- A rolled back deploy is still a failed deploy: the workflow fails and says whether the rollback restored service. The failed image stays in the registry under its commit tag for diagnosis.
- A deploy cannot be judged against a service that was already unhealthy, so the script checks production first and stops unless `deploy_when_unhealthy` is set. Do not cancel the deploy job once it has started publishing; a cancelled run cannot roll back.
- Keep deploy logic that must not be skipped in one script with explicit control flow, and test it with stand-ins for `docker`, `az` and `curl` (`tests/test_deploy_enterprise_script.py`). Separate workflow steps joined by `if: failure()` conditions cannot be run before the day they are needed.

## Sign-In Paths

- A fallback sign-in path must meet the same bar as the main one. Every endpoint that issues a session or a token takes the identity from something the server has verified. The Teams tab had a second provisioning path beside the validated sign-in; it now requires the same validated Teams sign-in token. A path that cannot meet the bar is removed, not kept as a fallback.
- A test that supplies a name the code under test does not define hides the defect it should find. The Teams sign-in endpoint called a function that existed nowhere; its only test patched that name in. Test sign-in endpoints through the real route with tokens signed by a key generated in the test and a stubbed key download (`tests/test_teams_tab_auth.py`), and include the refusals: wrong audience, wrong issuer, expired, unsigned, wrong key, missing claims.
- Check a token's tenant binding on every read, not only when it is issued. Tab routes now resolve the tenant from the token, require the account to still belong to it, and filter every query by it; a record of another tenant is answered like a record that does not exist.

## Errors In The Start-Up Log

- Three errors were printed on every start of the production container for months. Each was true and none was read, because the app came up healthy. Read the first hundred lines of the log after a deploy; an error that is expected must be removed, not learned.
- Log forwarding was set up while `app.py` was imported, before `db.init_app(app)`. Its settings are rows in the database, so the read failed in every worker on every start, the failure was stored as "disabled", and nothing tried again. Switched on, it would have stopped forwarding at the next restart with one `ERROR` line as the only sign, and the settings page showed it as disabled for five minutes after each start. Anything that reads settings from the database is set up after the database is initialised (`setup_log_forwarding_from_settings()`, called from `init_database()`), and a failed read is not cached as an answer. `tests/test_startup_log_errors.py` starts the app in a fresh process and checks both.
- A test that builds its own Flask app with `db.init_app()` first cannot see an ordering fault in `app.py`. Faults of import order need a test that imports `app` in a new interpreter.
- A dependency upgrade can add a feature that is on by default. gunicorn 25.1 added a control socket under `$HOME/.gunicorn`; the image's user has no home directory, so the master logged `Control server error: [Errno 13] Permission denied` on every start. The start script now passes `--no-control-socket`. When raising a pin across a major version, read the changelog for new defaults, not only for removals.
- The start script still wrote a private DNS record that Azure Container Instances needed and the VM does not. The write was refused (`AuthorizationFailed`), which was the lucky outcome: inside Docker the address it would have published is the bridge address. When a permission error comes from a step nothing depends on, remove the step; do not grant the permission. When infrastructure is replaced, remove what served the old one from the start path in the same change.
- The deploy pre-flight starts gunicorn itself and does not run the image's start script, so an argument gunicorn does not know would pass the pre-flight and stop production from starting (the deploy would then roll back). `tests/test_startup_log_errors.py` parses the script's arguments with the installed gunicorn.

## Deployment Rule

Normal production deployments go through GitHub Actions and GitHub Environments. Local Azure CLI deploys are break-glass only and must be documented in the deployment notes for that incident.
