# Decision Records - Codex Notes

Decision Records is a Flask backend with an Angular frontend. The public repository is the Community Edition; proprietary Enterprise Edition modules live behind the `ee/` submodule boundary.

## Repository Shape

- `app.py` is the main Flask application and route surface.
- `models.py` contains SQLAlchemy models and shared persistence logic.
- `auth.py`, `webauthn_auth.py`, `security.py`, `governance.py`, and `notifications.py` hold core backend services.
- `feature_flags.py` controls Community vs Enterprise behavior. Community Edition must work without the `ee/` directory.
- `frontend/` is an Angular 18 app. Community builds use `frontend/tsconfig.ce.json` to remap `@ee/*` imports to stubs.
- `tests/` contains pytest coverage for CE plus EE-gated tests. EE tests should skip cleanly when proprietary modules are absent.

## Local Environment

- Preferred Python setup:
  - `uv venv --python 3.12`
  - `uv pip install -r requirements.txt pytest pytest-cov`
  - With the private `ee/` submodule checked out, also run `uv pip install -r ee/requirements.txt`.
- Run backend tests with `uv run pytest tests/ -q --tb=short`.
- Run Enterprise backend tests with `DECISION_RECORDS_EDITION=enterprise AZURE_KEYVAULT_URL= uv run pytest tests/ -q --tb=short`.
- Install frontend dependencies from `frontend/` with `npm ci`.
- Build the Community frontend with `npm run build -- --configuration=community`.
- For Enterprise frontend typechecks, create the ignored local symlink `ln -sfn ../../frontend/node_modules ee/frontend/node_modules`, then run `npx tsc -p tsconfig.app.json --noEmit` from `frontend/`.
- The private marketing site under `ee/marketing` expects Node 20 (`.nvmrc` / `package.json` engines). Its Angular workspace keeps the persistent disk cache off for local builds and keeps Google Fonts inlining off for production builds so macOS local builds do not crash in LMDB native cache code or depend on live font fetches.
- Run local CE backend with `python run_local.py --community`.
- Run Angular dev server from `frontend/` with `npm start`.
- Check the CE/EE boundary locally with `uv run python scripts/check_ce_boundary.py`.
- Check the open-source artifact boundary with `uv run python scripts/check_public_artifacts.py --mode staged`.
- Run commit QA with `uv run python scripts/qa_check.py --mode commit`.
- Run full release QA with `uv run python scripts/qa_check.py --mode full`.
- Use `git config core.hooksPath .githooks` to enable the versioned pre-commit hook in the public repo.
- Use `git -C ee config core.hooksPath .githooks` to enable the versioned pre-commit hook in the private `ee` repo.
- Verify local hook wiring with `uv run python scripts/verify_git_hooks.py`.
- Configure GitHub branch/environment guardrails with `scripts/configure_github_guardrails.sh` when authenticated as a repo admin.
- Configure GitHub Actions Azure OIDC with `scripts/configure_azure_oidc.sh` when authenticated to Azure and GitHub.

## Project Boundaries

- Keep Community Edition functional without `ee/` checked out.
- Do not add hard imports from `ee.*` in public CE code paths. Guard optional EE imports and provide CE stubs or graceful failures.
- Every public frontend `@ee/*` import must have a matching stub under `frontend/src/stubs/`.
- Private commercial modules should live in the private `ee` repository/submodule, not on long-lived private branches of this public repository.
- Do not commit secrets, local credentials, or generated runtime databases.
- Keep private commercial modules out of the public CE tree unless the licensing and release boundary is intentional.
- Keep production infra snapshots and exact private Azure resource identifiers under `ee/infra`, not the public tree.
- Treat `website` as the commercial marketing site from the private marketing repository, available to operators under `ee/marketing`. Do not deploy the `frontend/` Community app build to `decisionrecords.org` or to the marketing Azure Static Web App.
- The Community Edition is source code and release artifacts only; there is no official `production-public` deployment target for the Community app.
- Do not deploy production from a local Azure CLI session. Normal deployments go through GitHub Actions and GitHub Environments.

## Git Safety Rules

- Treat the public repository and `ee/` as separate Git repositories. Always check both with `git status --short --branch` and `git -C ee status --short --branch` before editing, committing, or summarizing work.
- When marketing changes are involved, treat `ee/marketing` as a third repository. Check all three statuses before editing, committing, or summarizing work: `git status --short --branch`, `git -C ee status --short --branch`, and `git -C ee/marketing status --short --branch`.
- Keep only one open public PR per branch/head SHA. If a retry branch supersedes an earlier PR, close the earlier PR before retriggering CI again so required checks attach to a single live PR.
- Do not treat `workflow_dispatch` CI runs as a substitute for PR-required checks. For PR recovery, re-run the canonical `pull_request` run or push a no-op commit to trigger a fresh `pull_request` synchronize event.
- Never edit a detached `ee` HEAD. If `ee` is detached, create or switch to a named private branch before making or keeping changes, for example `git -C ee switch -c infra/<topic>`.
- Never edit a detached `ee/marketing` HEAD. If `ee/marketing` is detached, create or switch to a named private branch before making or keeping changes there.
- Commit order is strict when nested repos change: commit inside `ee/marketing` first, then commit the `marketing` pointer inside `ee`, then update the public `ee` submodule pointer. Do not commit a parent pointer that refers to dirty child work.
- Merge strategy is strict when a repo is the child side of a submodule pointer. For `ee/marketing` and `ee`, use a commit-preserving merge method so the parent repo can point at a durable child `main` SHA. Do not squash-merge PRs whose commits are meant to be referenced by a parent submodule pointer.
- Keep production infra, snapshots, deployment resource names, and commercial module code in `ee/`; the public parent should contain only generic docs, CE code, stubs, and the submodule pointer.
- Do not stage generated or local-only files such as `ee/infra/aca/main.json`, `ee/frontend/node_modules`, local databases, `.env*`, or Azure credential files.
- Do not use destructive Git commands such as `git reset --hard`, `git checkout -- <path>`, or submodule deinit/reinit to clean up without explicit user approval.
- Before relying on hooks, ensure `git config core.hooksPath .githooks` and `git -C ee config core.hooksPath .githooks` are set, then run `uv run python scripts/verify_git_hooks.py`.

## Operational Memory

- After any CI/CD, deployment, release, or production incident that reveals a new failure mode, record the lesson in `docs/production-lessons-kb.md` in the same change when practical, without waiting for a user prompt.
- When a task adds or changes a marketing route, review the full route surface before calling it done: `ee/marketing/src/app/app.routes.ts`, `ee/marketing/src/app/services/seo.service.ts`, `ee/marketing/scripts/prerender-blog.py`, and `ee/infra/cloudflare-worker.js`.
- If the incident fix leaves meaningful follow-up work, add it to `docs/TODO.md` before ending the session.

## Notes From Claude Artifacts

The root `CLAUDE.md` is a symlink to `ee/docs/CLAUDE.md`. In this checkout the private `ee` submodule is not available, so that file cannot be read. The local `.claude/settings.local.json` allowed workflows included Python pytest, frontend build/start, Playwright, Docker build/push, Azure container logs, GitHub issue lookup, and CE/EE test runs.
