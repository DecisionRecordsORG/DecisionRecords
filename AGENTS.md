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
- Run local CE backend with `python run_local.py --community`.
- Run Angular dev server from `frontend/` with `npm start`.
- Check the CE/EE boundary locally with `uv run python scripts/check_ce_boundary.py`.
- Check the open-source artifact boundary with `uv run python scripts/check_public_artifacts.py --mode staged`.
- Run commit QA with `uv run python scripts/qa_check.py --mode commit`.
- Run full release QA with `uv run python scripts/qa_check.py --mode full`.
- Use `git config core.hooksPath .githooks` to enable the versioned pre-commit hook.
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
- Keep only one open public PR per branch/head SHA. If a retry branch supersedes an earlier PR, close the earlier PR before retriggering CI again so required checks attach to a single live PR.
- Never edit a detached `ee` HEAD. If `ee` is detached, create or switch to a named private branch before making or keeping changes, for example `git -C ee switch -c infra/<topic>`.
- Commit private `ee` changes inside `ee` first, push that private branch, then update the public parent submodule pointer. Do not commit a public parent submodule pointer that refers to uncommitted private `ee` work.
- Keep production infra, snapshots, deployment resource names, and commercial module code in `ee/`; the public parent should contain only generic docs, CE code, stubs, and the submodule pointer.
- Do not stage generated or local-only files such as `ee/infra/aca/main.json`, `ee/frontend/node_modules`, local databases, `.env*`, or Azure credential files.
- Do not use destructive Git commands such as `git reset --hard`, `git checkout -- <path>`, or submodule deinit/reinit to clean up without explicit user approval.
- Before relying on hooks, ensure `git config core.hooksPath .githooks` is set and run `uv run python scripts/verify_git_hooks.py`.

## Notes From Claude Artifacts

The root `CLAUDE.md` is a symlink to `ee/docs/CLAUDE.md`. In this checkout the private `ee` submodule is not available, so that file cannot be read. The local `.claude/settings.local.json` allowed workflows included Python pytest, frontend build/start, Playwright, Docker build/push, Azure container logs, GitHub issue lookup, and CE/EE test runs.
