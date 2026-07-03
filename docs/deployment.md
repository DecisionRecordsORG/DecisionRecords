# Deployment

This repository supports two deployment tracks:

- Public website: static Angular output deployed to Azure Static Web Apps.
- Application/backend: Docker image deployed to Azure Container Apps or the existing Enterprise VM workflow.

Normal deployments should be started by GitHub Actions only. Do not use a local Azure CLI session or a coding agent shell to update production containers, restart VMs, or push production images except during an explicit break-glass incident.

## Public Website

The public website should use the Community Edition frontend build and deploy only the static browser output.

GitHub workflow:

- `.github/workflows/deploy-public-website.yml`

Required secret:

- `AZURE_STATIC_WEB_APPS_API_TOKEN`

GitHub Environment:

- `production-website`

Recommended Azure setup:

- Create an Azure Static Web Apps resource.
- Connect it to this GitHub repository, or copy its deployment token into the repository secret above.
- Set the production hostname to `decisionrecords.org`.

The workflow builds:

```bash
cd frontend
npm ci
npm run build -- --configuration=community --progress=false
```

Then uploads:

```text
frontend/dist/frontend/browser
```

## Community App and Backend

Use the Docker workflow when backend code, API behavior, database behavior, or the self-hosted app changes.

GitHub workflow:

- `.github/workflows/deploy-community-app-azure.yml`

Required secret:

- none for Azure login; this workflow uses GitHub OIDC

GitHub Environment:

- `production-public`

Required `production-public` environment variables:

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`
- `AZURE_ACR_NAME`
- `AZURE_ACR_LOGIN_SERVER`
- `AZURE_RESOURCE_GROUP`
- `AZURE_CONTAINER_APP_NAME`

Optional `production-public` environment variable:

- `PUBLIC_APP_HEALTH_URL`

The workflow builds `Dockerfile.community`, pushes the image to Azure Container Registry, and updates the configured Azure Container App.

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

Public website only:

- Homepage copy, legal pages, SEO metadata, robots.txt, sitemap.xml, static assets, public route changes.

Community app/backend:

- `app.py`, models, migrations, auth, feature flags, Dockerfile, Python dependencies, or frontend app behavior used by self-hosted users.

Enterprise app:

- Private modules under `ee/`, Enterprise-only frontend components, Slack, Teams, AI, analytics, Key Vault, Cloudflare, or production app infrastructure changes.

## Pre-Deployment Checks

Run locally before deploying:

```bash
uv run python scripts/check_ce_boundary.py
uv run pytest tests/ -q --tb=short
cd frontend
npx tsc -p tsconfig.app.ce.json --noEmit
npm run build -- --configuration=community --progress=false
```

## GitHub and Azure Integration Notes

Azure Static Web Apps can deploy from GitHub Actions by uploading a built static output folder. Azure Container Apps can deploy new revisions when a workflow pushes a container image and updates the container app. Keep those paths separate: static website deployments should not require backend secrets, and backend deployments should not run for copy-only website changes.

The production Enterprise app is currently on the VM path. Exact Enterprise infrastructure plans and snapshots belong in the private `ee/infra` repo boundary; keep the VM workflow available until the ACA deployment has survived one billing cycle.

## Azure OIDC Setup

Application and Enterprise deployments use GitHub OIDC instead of a long-lived `AZURE_CREDENTIALS` JSON secret. Configure the Azure app registration, federated credentials, and GitHub Environment variables with:

```bash
GITHUB_OWNER=DecisionRecordsORG GITHUB_REPO=DecisionRecords scripts/configure_azure_oidc.sh
```

The script updates these variables on `production-public` and `production-private`:

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

For Community Container App deployment this grants `AcrPush` on the registry and `Azure Container Apps Contributor` on the Container App:

```bash
ASSIGN_AZURE_ROLES=1 \
AZURE_RESOURCE_GROUP=<resource-group> \
AZURE_ACR_NAME=<acr-name> \
AZURE_CONTAINER_APP_NAME=<container-app-name> \
GITHUB_OWNER=DecisionRecordsORG \
GITHUB_REPO=DecisionRecords \
scripts/configure_azure_oidc.sh production-public
```

After one successful OIDC deployment, remove the legacy `AZURE_CREDENTIALS` secret if it exists.

## Repository Guardrails

Apply the Phase 1 GitHub repository settings with:

```bash
GITHUB_OWNER=DecisionRecordsORG GITHUB_REPO=DecisionRecords scripts/configure_github_guardrails.sh
```

This configures `main` branch protection to require pull requests and the `Quality Gate` check, without requiring a second approving reviewer. That keeps solo-maintainer deployments unblocked while preventing direct pushes. The script also creates the production GitHub Environments used by deployment workflows. Add required reviewers to production environments when there is a second maintainer or operator.
