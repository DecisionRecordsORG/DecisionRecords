# Private Module Boundary

Decision Records uses one public repository for the Community Edition and one private `ee` repository for commercial modules. Keep proprietary implementation code in the private repository, not on long-lived private branches of the public repository.

## Recommendation

Use a dedicated private repository for Enterprise Edition modules, mounted as the `ee/` submodule for builds that need it.

Branches are useful for short-lived integration work, release hardening, or hotfixes. They are not the right security boundary for commercial code because the same repository access model, forks, CI logs, and branch protections still apply to all branches.

## Why A Private Repo

- Access control is simpler: only maintainers who need commercial code get access to `DecisionRecordsORG/ee`.
- Public CI never needs private credentials and can validate Community Edition independently.
- Enterprise CI can explicitly opt in by checking out submodules with `EE_REPO_TOKEN`.
- Security reviews are clearer because proprietary code, secrets-adjacent integrations, and deployment assets have a separate audit surface.
- Git operations stay clean: public issues and pull requests remain open-source friendly, while commercial work can use private issues, reviews, and release branches.

## Repository Contract

Public repository:

- Owns shared backend models, migrations, core auth, governance, audit logging, spaces, and the Community Edition UI.
- Provides stable extension points and compatibility gateways in `app.py`, `crypto.py`, and `notifications.py`.
- Must build and test without `ee/` checked out.
- Must provide frontend stubs for every `@ee/*` import used by public routes or components.

Private `ee` repository:

- Owns Slack, Microsoft Teams, Google OAuth, AI, analytics, cloud deployment specializations, and other commercial modules.
- Registers private Flask blueprints and services through `ee.backend.register_all_blueprints()` and `ee.backend.init_ee_services()`.
- Owns private frontend components matched by the public `@ee/*` import paths.
- Owns private tests for commercial behavior.

## CI Guardrails

Run this before opening public PRs:

```bash
uv run python scripts/check_ce_boundary.py
```

The check enforces two high-value rules:

- Frontend `@ee/*` imports must have Community Edition stubs under `frontend/src/stubs/`.
- Backend imports from `ee.*` may only live in the current public compatibility gateway files. New commercial backend behavior should be moved into `ee/`.

## Git Workflow

Use public `main` for Community Edition development. Use private `ee/main` for commercial modules. For a commercial release, checkout the public repository with the `ee` submodule and build through the Enterprise deployment workflow.

Recommended branch pattern:

- Public CE feature: `feature/<name>` in the public repository.
- Private module feature: `feature/<name>` in the private `ee` repository.
- Cross-repo integration: short-lived paired branches with matching names in both repositories.
- Release stabilization: tag the public repository and pin the `ee` submodule SHA used by the Enterprise deployment.

## Security Notes

- Do not store secrets in either repository.
- Keep private CI logs from printing OAuth client secrets, bot tokens, signing secrets, or Azure credentials.
- Protect `main` in both repositories.
- Use a narrow `EE_REPO_TOKEN` only in workflows that need the private submodule.
- Do not accept public pull requests that add proprietary integrations outside the documented extension points.
