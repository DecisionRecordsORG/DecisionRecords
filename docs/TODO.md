# TODO

This file is the standing backlog for work that was identified but not completed in the current session.

Update rules:
- Add deferred work here before ending a session.
- Remove items when done.
- Keep entries short and actionable.
- Prefer linking to the owning workflow, doc, or file when relevant.

## Deployment / CI-CD

- [ ] Watch the first CI run of the PostgreSQL smoke test and the first Enterprise deploy with the new pre-flight and rollback. Both were written without a Docker daemon or Azure access and have only run against stand-ins. Before that deploy, confirm `https://app.decisionrecords.org/health` answers with `"database": "connected"`; the deploy now depends on it.
- [ ] Decide whether `Deploy Enterprise Edition` should remain manual-only or become gated auto-deploy after `CI` on `main`.
- [ ] Re-run and verify the current enterprise deploy from `main` after the workflow fixes merged.
- [ ] Extract the shared CI job graph into a reusable workflow after revalidating required check names against branch protection on `main`.
- [ ] Decide whether a dedicated `ci-recovery.yml` wrapper is still needed once the reusable workflow split lands.
- [ ] Decide whether manual CI diagnostics should move out of `.github/workflows/ci.yml` into a separate non-required workflow after the PR check recovery fix settles.
- [ ] Collapse duplicated Community CI and release validation steps into a reusable workflow once the tag-release hardening has proven stable.
- [ ] Mirror the delivery-contract system into the private `ee` and `marketing` repositories so private-repo-local work can declare obligations before the public submodule pointer update stage.

## Versioning / Releases

- [ ] Publish Community `v2.1.1` to replace the broken `2.1.0` and `latest` images (missing `decision_relationships.py`), then pull the published image and run `scripts/smoke_test_ce_image.sh` against it.
- [ ] Watch the first CI and release runs of the new image smoke test; it was written without a local Docker daemon and has only been exercised against a stand-in.
- [ ] Confirm the published image manifest really contains `linux/arm64` and decide whether to smoke test it under emulation; the release gate only boots `linux/amd64`.
- [ ] Pin every package in the private `ee/requirements.txt` exactly, from `pip freeze` in the running production image. It still uses ranges, so each Enterprise image build resolves new versions.
- [ ] Make the VM's systemd unit read the image tag from its environment file, so a deploy and a rollback can name a commit tag instead of moving `latest`.
- [ ] Bake the commit into the Enterprise image (`GIT_COMMIT`) so the deploy can confirm from `/api/version` which build is serving.
- [ ] Move the tests that load the real app module onto `TEST_DATABASE_URL` as well; today only the fixture-based tests run on PostgreSQL in CI.
- [ ] Make `docker-compose.yml` usable for self-hosters: the `postgres` profile starts a database the app is not pointed at, and the file builds from source so it cannot be used standalone.
- [ ] Reconcile self-hosting docs with the shipped defaults: docs use `/data/decisions.db` and a `decision-records` container name, the image and compose file use `/data/architecture_decisions.db` and compose-generated names. Changing a default can orphan existing SQLite data, so decide deliberately.
- [ ] Decide whether the default Angular build and serve configurations should be Community, so `npm start` and `npm run build` work in a public checkout without `--configuration=community`.
- [ ] Verify the live marketing `/releases` page after the latest deploy finishes.
- [ ] Decide whether the marketing `/releases` page should keep using the runtime GitHub Releases API or switch to a build-time release snapshot for stronger SEO and lower runtime dependency.
- [ ] Decide whether release notes should stay GitHub-driven only or also be curated in-site.

## Product / UX

- [ ] Add a visible comments UI flow for ADR comments in the main app, now that MCP comment support exists.
- [ ] Review whether OAuth error states on the marketing site should also be surfaced as inline banners on first load.

## Infrastructure

- [ ] Continue the ACA migration evaluation and compare one month of ACA cost against the VM baseline.
- [ ] Capture current production infrastructure state in committed infra definitions where still missing.

## Security / Repo Hygiene

- [ ] Audit the current git hooks and project rules periodically to ensure public/private artifact checks still cover new files and workflows.
- [ ] Continue trimming public CE docs and examples so they do not carry Enterprise-only operational guidance.

## MCP / Ecosystem

- [ ] Harden MCP for external listing readiness: stable schemas, auth flow, pagination, error contracts, rate limits, and conformance coverage.
- [ ] Prepare a ChatGPT plugin/app listing package for the MCP once the server contract is stable.
