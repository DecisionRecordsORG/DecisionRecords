# Deployment

This repository supports these deployment tracks:

- Commercial website: private marketing site, deployed from the private marketing repository to Azure Static Web Apps.
- Community Edition: public source code and release artifacts only; it is not deployed as a hosted production app.
- Enterprise app/backend: private-module image deployed through the Enterprise workflow.

Normal deployments should be started by GitHub Actions only. Do not use a local Azure CLI session or a coding agent shell to update production containers, restart VMs, or push production images except during an explicit break-glass incident.

## Commercial Website

The public marketing website is not deployed from this public Community repository.

Source of truth:

- Private marketing repository, checked out for operators under `ee/marketing`.

Deployment:

- The marketing repository owns its Azure Static Web Apps workflow and deployment token.
- Do not store the marketing Static Web Apps deployment token in this public repository.
- Do not deploy the `frontend/` Community app build to `decisionrecords.org`.

Content changes for the commercial website, including homepage copy, legal pages, SEO metadata, `robots.txt`, `sitemap.xml`, and marketing assets, should be committed and deployed from the private marketing repository.

The `frontend/` directory in this repository is the Community app UI, not the commercial marketing website.

## Community Release Artifacts

The Community Edition is not deployed as a production service by this repository. It remains open-source code plus release artifacts for users to run themselves.

GitHub workflow:

- `.github/workflows/release.yml`

Trigger:

- Version tags matching `v*.*.*`

Output:

- Community Docker image published to GitHub Container Registry.
- GitHub Release notes for the tag.

Before the registry login, the workflow builds the image and starts it twice with `scripts/smoke_test_ce_image.sh`: on its default SQLite database and, with `SMOKE_DATABASE=postgres`, against a PostgreSQL container using a `postgresql://` `DATABASE_URL`. Nothing is published if either run fails.

## Enterprise App

The existing workflow remains the Enterprise path:

- `.github/workflows/deploy-enterprise.yml`

Required secrets:

- `EE_REPO_TOKEN`
- `CLOUDFLARE_API_TOKEN` if Cloudflare cache purge is enabled

GitHub Environment:

- `production-private`

Required `production-private` environment variables:

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`
- `AZURE_ACR_NAME`
- `AZURE_ACR_LOGIN_SERVER`
- `AZURE_RESOURCE_GROUP`
- `AZURE_VM_NAME`

Optional `production-private` environment variables:

- `AZURE_ENTERPRISE_IMAGE_NAME`
- `ENTERPRISE_HEALTH_URL` (liveness route shown in the deployment summary; default `https://app.decisionrecords.org/api/health`)
- `ENTERPRISE_DB_HEALTH_URL` (route that reports the database and decides whether a deploy is good; default `https://app.decisionrecords.org/health`)
- `CLOUDFLARE_ZONE_ID`

The preflight job checks out the private `ee` submodule, installs public and private Python requirements, runs the open-source artifact guard, compiles public gateway files and private EE Python modules, then runs the backend suite with `DECISION_RECORDS_EDITION=enterprise`.

The deploy job then runs in this order. Nothing is pushed and the VM is not touched before step 3 has passed.

1. Build the Enterprise image, tagged with the commit SHA only.
2. Import check (always runs): run `python -c "import app"` in the image with a `postgresql://` URL. Creating the engine imports the PostgreSQL driver; no database server is needed.
3. Boot check: `SMOKE_PROFILE=enterprise SMOKE_DATABASE=postgres scripts/smoke_test_ce_image.sh <image>` starts a PostgreSQL container on the runner, starts the image against it with Key Vault and the Cloudflare origin check switched off, and requires `/health` to report a connected database, the schema to exist in PostgreSQL, and the image `HEALTHCHECK` to turn healthy.
4. Log in to Azure and the registry.
5. `scripts/deploy_enterprise_image.sh`:
   1. checks that production reports healthy at `ENTERPRISE_DB_HEALTH_URL` (otherwise stops; nothing changed);
   2. pulls `latest` and records its digest as the rollback target (otherwise stops; nothing changed);
   3. pushes the commit tag (on failure stops; `latest` not moved);
   4. moves `latest` to the new image and restarts the service on the VM;
   5. waits for `ENTERPRISE_DB_HEALTH_URL` to report `"status": "healthy"` and `"database": "connected"`;
   6. on any failure in 4 or 5, pushes the recorded image back as `latest`, restarts the VM again and checks health again.

The job fails unless the new image is serving. After a rollback the error annotation and the job summary say one of:

- `ROLLBACK RESTORED SERVICE`: production is back on the previous image. Diagnose the failed image, which is still in the registry under its commit tag.
- `ROLLBACK DID NOT RESTORE SERVICE`: production is down on the previous image too. Read the service journal on the VM.
- `ROLLBACK FAILED`: `latest` could not be moved back. Re-point it by hand to the digest in the message and restart the service.

Do not cancel the deploy job once step 5 has started; a cancelled run cannot roll back.

Deliberate bypasses, both inputs of the manual run and both off by default:

- `skip_postgres_preflight`: skips step 3 only, for the case where the check itself is broken (for example the PostgreSQL image cannot be pulled). Step 2 and the rollback still run.
- `deploy_when_unhealthy`: lets step 5 proceed although production is not healthy beforehand, for the case where the deploy is the fix. A rollback then returns to the unhealthy image.

Limits to know about:

- The VM's systemd unit pulls and runs the `latest` tag, so the deploy and the rollback both work by moving `latest`. Deploying a specific commit tag needs a unit that reads the tag from its environment file.
- The rollback re-pushes the previous image from the runner with the registry push permission the deploy identity already has. It restores the same image content; it does not undo a schema migration applied by the failed image.
- The boot check starts gunicorn directly instead of the image's start script, because that script calls the Azure instance metadata service first. A defect in the start script itself is caught by the rollback, not by the pre-flight.

## When To Deploy What

Commercial website only:

- Homepage copy, legal pages, SEO metadata, `robots.txt`, `sitemap.xml`, marketing static assets, and marketing route changes. Deploy from the private marketing repository only.

Community Edition source or release artifacts:

- `app.py`, models, migrations, auth, feature flags, Dockerfile, Python dependencies, or frontend app behavior used by self-hosted users. Run CI and publish releases from tags; do not deploy a hosted Community production app.

Shared-core changes should also carry a delivery contract under `.delivery/changes/` so the repository can state, deterministically, whether:

- an enterprise deployment is required
- a Community release is required or only queued as a release candidate
- no deploy/release follow-up is required because the change was ops/docs only

Enterprise app:

- Private modules under `ee/`, Enterprise-only frontend components, Slack, Teams, AI, analytics, Key Vault, Cloudflare, or production app infrastructure changes.

## Pre-Deployment Checks

Run locally before releasing Community artifacts or deploying Enterprise:

```bash
uv run python scripts/check_ce_boundary.py
uv run pytest tests/ -q --tb=short
# Optional: the fixture-based tests against a local PostgreSQL. The database
# name must contain "test"; every table in it is dropped.
TEST_DATABASE_URL=postgresql://user:password@localhost:5432/decisions_test uv run pytest tests/ -q --tb=short
cd frontend
npx tsc -p tsconfig.app.ce.json --noEmit
npm run build -- --configuration=community --progress=false
```

## GitHub and Azure Integration Notes

Azure Static Web Apps deployment for the commercial marketing website belongs to the private marketing repository. This public repository does not deploy a hosted Community app. Keep marketing, open-source release, and Enterprise deployment paths separate: marketing website deployments should not require backend secrets, Community release publishing should not require Azure production access, and backend deployments should not run for copy-only website changes.

The production Enterprise app is currently on the VM path. Exact Enterprise infrastructure plans and snapshots belong in the private `ee/infra` repo boundary; keep the VM workflow available until the ACA deployment has survived one billing cycle.

## Delivery Obligation Tracking

Use the repo-owned delivery contracts to answer "what still needs to happen after this merge?":

```bash
uv run python scripts/list_open_obligations.py --format markdown
```

For example, a shared-core security fix should normally show:

- `enterprise_app: required`
- `community_release: required (patch)`

until both the successful enterprise deploy and the Community release tag exist.

## Azure OIDC Setup

Enterprise deployments use GitHub OIDC instead of a long-lived `AZURE_CREDENTIALS` JSON secret. Configure the Azure app registration, federated credentials, and GitHub Environment variables with:

```bash
GITHUB_OWNER=DecisionRecordsORG GITHUB_REPO=DecisionRecords scripts/configure_azure_oidc.sh
```

The script updates these variables on `production-private`:

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`

If the Azure service principal still needs permissions, assign them explicitly. For Enterprise VM deployment this grants `AcrPush` on the registry and `Virtual Machine Contributor` on the VM:

```bash
ASSIGN_AZURE_ROLES=1 \
AZURE_RESOURCE_GROUP=<resource-group> \
AZURE_ACR_NAME=<acr-name> \
AZURE_VM_NAME=<vm-name> \
GITHUB_OWNER=DecisionRecordsORG \
GITHUB_REPO=DecisionRecords \
scripts/configure_azure_oidc.sh production-private
```

For a future Enterprise Container App deployment this grants `AcrPush` on the registry and `Azure Container Apps Contributor` on the Container App:

```bash
ASSIGN_AZURE_ROLES=1 \
AZURE_RESOURCE_GROUP=<resource-group> \
AZURE_ACR_NAME=<acr-name> \
AZURE_CONTAINER_APP_NAME=<container-app-name> \
GITHUB_OWNER=DecisionRecordsORG \
GITHUB_REPO=DecisionRecords \
scripts/configure_azure_oidc.sh production-private
```

After one successful OIDC deployment, remove the legacy `AZURE_CREDENTIALS` secret if it exists.

## Repository Guardrails

Apply the Phase 1 GitHub repository settings for the public repo with:

```bash
GITHUB_OWNER=DecisionRecordsORG GITHUB_REPO=DecisionRecords scripts/configure_github_guardrails.sh
```

This configures `main` branch protection to require pull requests and the `Quality Gate` check, without requiring a second approving reviewer. That keeps solo-maintainer deployments unblocked while preventing direct pushes. The script also creates the production GitHub Environments used by public-repo deployment workflows. Add required reviewers to production environments when there is a second maintainer or operator.

For child repos referenced by submodule pointers, use the same script with child-safe settings. Those repos must allow merge commits, disable rebase and squash merges, and disable linear-history enforcement so the parent gitlink can keep pointing at an unchanged child SHA:

```bash
GITHUB_OWNER=DecisionRecordsORG \
GITHUB_REPO=ee \
GITHUB_REQUIRED_CONTEXTS="Enterprise Quality Gate" \
GITHUB_REQUIRE_LINEAR_HISTORY=false \
GITHUB_ALLOW_MERGE_COMMIT=true \
GITHUB_ALLOW_REBASE_MERGE=false \
GITHUB_ALLOW_SQUASH_MERGE=false \
GITHUB_DELETE_BRANCH_ON_MERGE=true \
scripts/configure_github_guardrails.sh

GITHUB_OWNER=DecisionRecordsORG \
GITHUB_REPO=marketing \
GITHUB_REQUIRED_CONTEXTS="Build and Deploy" \
GITHUB_REQUIRE_LINEAR_HISTORY=false \
GITHUB_ALLOW_MERGE_COMMIT=true \
GITHUB_ALLOW_REBASE_MERGE=false \
GITHUB_ALLOW_SQUASH_MERGE=false \
GITHUB_DELETE_BRANCH_ON_MERGE=true \
GITHUB_ENVIRONMENTS= \
scripts/configure_github_guardrails.sh
```
