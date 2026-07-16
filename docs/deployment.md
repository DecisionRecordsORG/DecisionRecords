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
- `ENTERPRISE_HEALTH_URL`
- `CLOUDFLARE_ZONE_ID`

This workflow checks out the private `ee` submodule, runs Enterprise preflight QA, builds the Enterprise Dockerfile, pushes to Azure Container Registry, updates the Azure VM service, and checks `https://app.decisionrecords.org/api/health`.

The preflight installs public and private Python requirements, runs the open-source artifact guard, compiles public gateway files and private EE Python modules, then runs the backend suite with `DECISION_RECORDS_EDITION=enterprise`.

## When To Deploy What

Commercial website only:

- Homepage copy, legal pages, SEO metadata, `robots.txt`, `sitemap.xml`, marketing static assets, and marketing route changes. Deploy from the private marketing repository only.

Community Edition source or release artifacts:

- `app.py`, models, migrations, auth, feature flags, Dockerfile, Python dependencies, or frontend app behavior used by self-hosted users. Run CI and publish releases from tags; do not deploy a hosted Community production app.

Enterprise app:

- Private modules under `ee/`, Enterprise-only frontend components, Slack, Teams, AI, analytics, Key Vault, Cloudflare, or production app infrastructure changes.

## Pre-Deployment Checks

Run locally before releasing Community artifacts or deploying Enterprise:

```bash
uv run python scripts/check_ce_boundary.py
uv run pytest tests/ -q --tb=short
cd frontend
npx tsc -p tsconfig.app.ce.json --noEmit
npm run build -- --configuration=community --progress=false
```

## GitHub and Azure Integration Notes

Azure Static Web Apps deployment for the commercial marketing website belongs to the private marketing repository. This public repository does not deploy a hosted Community app. Keep marketing, open-source release, and Enterprise deployment paths separate: marketing website deployments should not require backend secrets, Community release publishing should not require Azure production access, and backend deployments should not run for copy-only website changes.

The production Enterprise app is currently on the VM path. Exact Enterprise infrastructure plans and snapshots belong in the private `ee/infra` repo boundary; keep the VM workflow available until the ACA deployment has survived one billing cycle.

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

Apply the Phase 1 GitHub repository settings with:

```bash
GITHUB_OWNER=DecisionRecordsORG GITHUB_REPO=DecisionRecords scripts/configure_github_guardrails.sh
```

This configures `main` branch protection to require pull requests and the `Quality Gate` check, without requiring a second approving reviewer. That keeps solo-maintainer deployments unblocked while preventing direct pushes. The script also creates the production GitHub Environments used by public-repo deployment workflows. Add required reviewers to production environments when there is a second maintainer or operator.
