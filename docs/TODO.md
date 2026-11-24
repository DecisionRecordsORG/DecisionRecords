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

## Decision templates

- [ ] First follow-up: make the surfaces outside the web app use the organisation's template headings. Notification emails (`notifications.py`), Slack messages and modals, Teams cards, the MCP tool descriptions and exports still say Context, Decision and Consequences, and none of them shows or accepts the decision type. The Slack, Teams and MCP parts live in `ee/`; all of them can read `decision_templates.get_template(...)`.
- [ ] `GET /api/decisions` returns no spaces, so neither the decision list nor the bulk type list can filter by space (the list's "Filter by Space" select has never matched anything). Return spaces in the list, then add the space filter to the bulk type card.
- [ ] Bulk type changes are written to the audit log only, not to each decision's change history. Decide whether the history of a decision should show them.
- [ ] Decide whether the super admin should see a tenant's industry and template (as with the team profile). Today they are visible to the tenant only and are not sent to analytics; the privacy wording that covers the team profile does not mention the industry answer.
- [ ] Not built, by decision: per-space templates, custom templates, translated templates, a guided rewrite of old decisions, example decisions created as records.

## Data Retention

- [ ] After the first Enterprise deploy with automatic retention, open Super Admin > Data retention on production, read what is waiting and what was held back, take a database backup, and release the held back categories deliberately. Nothing has run there before.
- [ ] Give super admins a way to see and restore soft-deleted tenants in the tenants page. The tenant list hides them and `POST /api/tenants/<domain>/restore` has no button; the retention page only lists tenants whose 30 days are already over.
- [ ] Decide whether a held back category should also send an email to the super admin notification address. Today it is shown on the Data retention page and the dashboard and written to the log.
- [ ] Set the PostgreSQL session time zone to UTC for every connection (or stop writing aware datetimes). Retention waits out the offset, but every other date comparison in the application is still off by the offset on a server that is not UTC.
- [ ] Decide how long `retention_runs` and `retention_erasures` rows are kept. They hold ids and counts only and are never deleted.
- [ ] Restoring a tenant restores every soft-deleted decision in it, including ones a member deleted before the tenant was deleted.

## Accounts / Privacy

- [ ] Decide whether stewards may use the tenant administrator endpoints (`@admin_required` in `auth.py`). The app shows a steward the organisation settings page, `TenantMembership.can_approve_requests` says a steward can approve access requests, and the sign-in page counts stewards as approvers, but every administrator endpoint refuses them. A tenant whose only approvers are stewards holds access requests nobody can approve. Not changed: which of the 34 routes a steward should reach (users, SSO, email, Slack, Teams) is a product decision.
- [ ] Decide what a decision shows after its author's account is deleted. Published text says contributions are attributed to "Former Member". Comments and the change history are; a decision loses its author and owner and shows nobody. Either keep the author reference (it then shows "Former Member") or change the published wording.
- [ ] Decide whether rejecting an access request should email the requester. Nothing is sent and the product has no wording for it; the sign-in page does not promise one.
- [ ] `PUT /api/admin/users/<id>/admin` only changes the old `users.is_admin` flag. Nothing in the app calls it. Remove it, or make it change the membership role, so that it cannot disagree with the role.
- [ ] The website pages that describe the export and account deletion (FAQ, data processing, security policy) should be read against `data_export.py` and `retention.ACCOUNT_TEXT_RULES` when they are next edited. The export sentence is now accurate; the "Former Member" sentences are accurate for comments and not for decisions.
- [ ] Account recovery says "a recovery link has been sent" even when email is not configured, to avoid revealing which addresses have accounts. On an installation without email nothing can be sent. Consider hiding the recovery option when `email_available` is false.
- [ ] Several older browser tests cannot pass against a Community build served by Flask: they use fixed addresses (`localhost:4200`, `localhost:5001`), expect Enterprise-only cards (licensing, cookie consent), or look for a checkbox inside a slide toggle. They need the dev-server setup or an update.

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

## Microsoft Teams

- [ ] The Teams integration's state, its open security items and the work needed before a Teams store submission are tracked in the private repository at `docs/plans/teams-store-readiness.md`. Keep that document current; do not track Teams work here.
- [ ] After the next Enterprise deploy, send one real message to the Teams bot to confirm the stricter webhook token check accepts Microsoft's tokens.

## MCP / Ecosystem

- [ ] Harden MCP for external listing readiness: stable schemas, auth flow, pagination, error contracts, rate limits, and conformance coverage.
- [ ] Prepare a ChatGPT plugin/app listing package for the MCP once the server contract is stable.
