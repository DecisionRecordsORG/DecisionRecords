# CI/CD Review and No-Manual-Deploy Plan

This repository should deploy through GitHub Actions connected to Azure. Local Azure CLI commands are for read-only diagnostics and emergency break-glass use only, not normal deployments.

This review covers the public Community repository. The commercial marketing website is intentionally deployed from the private marketing repository, not from this repository's `frontend/` Community app.

## Current State

- `ci.yml` validates the Community Edition boundary, Python syntax, backend tests, frontend build, Docker build, and exposes a single required `Quality Gate`.
- `deploy-enterprise.yml` verifies the private `ee` submodule checkout, runs artifact guards, compiles public and EE Python, runs Enterprise pytest, then deploys through the `production-private` GitHub Environment.
- `release.yml` publishes Community Docker images to GitHub Container Registry for version tags.
- Enterprise Azure login now uses GitHub OIDC variables scoped to the deployment environment.

## Operating Rules

- Keep one live public PR per branch/head SHA. If a retry branch replaces an earlier PR, close the earlier PR before retriggering CI so required checks attach to one PR only.
- Prefer re-running or manually dispatching the existing `CI` workflow over cloning the job graph into ad hoc recovery workflows.
- Treat `workflow_dispatch` as a recovery tool, not a parallel validation lane. Concurrency should collapse duplicate runs on the same branch.

## Gaps

- Enterprise deployment still uses `az vm run-command` and a VM restart instead of immutable Azure app revisions.
- Azure OIDC still needs a one-time app registration/federated credential setup in Azure.
- Enterprise app deployments rebuild from source instead of promoting a CI-created image.
- Style lint is advisory because existing Python lint debt must be cleaned before it can become a quality gate.
- Rollback steps are documented only implicitly through previous images/revisions.
- Version bumping is coupled to Enterprise deployment and pushes from a deployment workflow.
- The CI job graph is still defined directly in `ci.yml`; reusable workflow extraction should happen only after required-check naming is revalidated against branch protection.

## Target Deployment Model

1. Pull requests run CI only.
2. Merges to the private marketing repository deploy the commercial website when marketing paths change.
3. Tags or GitHub Releases publish Community Edition artifacts without deploying a hosted Community app.
4. GitHub Environments protect production deployments with reviewer approval where a second maintainer or operator is available.
5. GitHub Actions authenticates to Azure using OIDC, not stored Azure credential JSON.
6. Azure Container Apps or Azure App Service revisions replace VM run-command restarts.
7. Rollback uses Azure revision/image rollback from GitHub Actions.
8. Local machines do not run `az containerapp update`, `az vm run-command`, or production Docker pushes for normal deployment.
9. Merge queue support uses the `merge_group` event so required checks continue to report when GitHub merge queue is enabled later.

## Migration Plan

### Phase 1: Guardrails

- Run `scripts/configure_github_guardrails.sh` with an authenticated GitHub admin account.
- Require `Quality Gate` before merge.
- Configure GitHub Environments:
  - `production-private`
- Add required reviewers for the Enterprise production environment when there is a second maintainer or operator.
- Keep local pre-commit QA enabled with `.githooks/pre-commit`.

Repository-side Phase 1 guardrails are implemented. Apply the GitHub repository settings with:

```bash
GITHUB_OWNER=DecisionRecordsORG GITHUB_REPO=DecisionRecords scripts/configure_github_guardrails.sh
```

After running the script, manually confirm required reviewers on `production-private` only when the project has a separate approver. A solo-maintainer repo should rely on PR plus `Quality Gate` for branch protection and use environment reviewers later when a second operator exists.

### Phase 2: Azure OIDC

- Create Azure federated credentials for the GitHub repository and environments.
- Replace `AZURE_CREDENTIALS` usage with `azure/login@v2` using `client-id`, `tenant-id`, and `subscription-id`.
- Store Azure IDs as GitHub Environment variables, not repository-wide secrets.

Repository-side Phase 2 workflow changes are implemented. Complete the Azure/GitHub identity setup with:

```bash
GITHUB_OWNER=DecisionRecordsORG GITHUB_REPO=DecisionRecords scripts/configure_azure_oidc.sh
```

If the service principal needs Azure RBAC assignments, run the same script with `ASSIGN_AZURE_ROLES=1`, `AZURE_ACR_NAME`, and the target-specific private app resource name (`AZURE_VM_NAME` or `AZURE_CONTAINER_APP_NAME`). Remove any legacy `AZURE_CREDENTIALS` secret after one successful OIDC deployment.

### Phase 3: Artifact Promotion

- Publish Community images once per release tag to GitHub Container Registry.
- Build Enterprise images once per deployment tag.
- Push immutable Enterprise SHA/tag images to Azure Container Registry.
- Deploy the exact Enterprise image digest from the build job.
- Keep `latest` as a convenience tag, not the deployment source of truth.

### Phase 4: Enterprise VM Exit

- Move Enterprise hosting from VM restart to Azure Container Apps or Azure App Service for Containers.
- Deploy Enterprise as a new revision.
- Health check the new revision before routing production traffic.
- Roll back by reactivating the previous revision if health fails.

### Phase 5: Release Discipline

- Split version bumping from deployment.
- Use a release PR or tag workflow for version changes.
- Deploy Enterprise from tags/releases after CI passes.
- Keep deployment workflows idempotent and source-code read-only.

## Commit-Time QA

Install the versioned Git hook once per checkout:

```bash
git config core.hooksPath .githooks
```

Verify the local hook path and guard behavior:

```bash
uv run python scripts/verify_git_hooks.py
```

The pre-commit hook runs:

- open-source artifact boundary check
- staged whitespace checks
- forbidden generated/local file checks
- Community/Enterprise boundary check
- Python syntax compile for staged Python files
- Community frontend typecheck when frontend source/config changed

For full release readiness:

```bash
uv run python scripts/qa_check.py --mode full
```

Temporary local bypass, for emergencies only:

```bash
SKIP_COMMIT_QA=1 git commit
```
