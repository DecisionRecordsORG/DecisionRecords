# TODO

This file is the standing backlog for work that was identified but not completed in the current session.

Update rules:
- Add deferred work here before ending a session.
- Remove items when done.
- Keep entries short and actionable.
- Prefer linking to the owning workflow, doc, or file when relevant.

## Deployment / CI-CD

- [ ] After the Enterprise deploy that carries `client_address.py`: confirm the start-up log line `Rate limiting enabled, one bucket per visitor address (23 trusted proxy network(s))`, that two networks count down separately on `X-RateLimit-Remaining`, and that login history shows the visitor's address. Steps in `ee/docs/client-address-and-origin.md`.
- [ ] Owner to decide on three production changes that were written up and not made (`ee/docs/client-address-and-origin.md`): publish the container port on the loopback address only; make nginx refuse host names that are not ours and pass the same headers on `/api/health`; Authenticated Origin Pulls with a certificate of our zone. Until the last one, any Cloudflare customer who learns the origin address can reach the application without our zone's rules.
- [ ] The web app's hashed files are sent without a cache lifetime, and they all count against one rate-limit endpoint: about five cold loads a minute from one address (an office) use it up. Send long `Cache-Control` lifetimes for hashed files before raising any limit.
- [ ] Rate limits are counted per gunicorn worker in memory, so a visitor gets up to twice each limit and counts restart on deploy. Accepted for one VM; needs a shared store (and the `redis` package in the image) before running more than one instance. Setting `REDIS_URL` without that package stops the app from starting.
- [ ] `ee/backend/oauth_server/rate_limits.py` (branch `feat/oauth-endpoints`) reads a visitor address for itself; switch it to `client_address.get_client_address()` when that branch is next touched.
- [ ] `validate_cloudflare_origin()` checks for a `CF-Ray` header only. Consider requiring that the address which connected to nginx is in Cloudflare's ranges, once the header chain has been observed in production for a while.
- [ ] Watch the first CI run of the PostgreSQL smoke test and the first Enterprise deploy with the new pre-flight and rollback. Both were written without a Docker daemon or Azure access and have only run against stand-ins. Before that deploy, confirm `https://app.decisionrecords.org/health` answers with `"database": "connected"`; the deploy now depends on it.
- [ ] Decide whether `Deploy Enterprise Edition` should remain manual-only or become gated auto-deploy after `CI` on `main`.
- [ ] Re-run and verify the current enterprise deploy from `main` after the workflow fixes merged.
- [ ] Extract the shared CI job graph into a reusable workflow after revalidating required check names against branch protection on `main`.
- [ ] Decide whether a dedicated `ci-recovery.yml` wrapper is still needed once the reusable workflow split lands.
- [ ] Decide whether manual CI diagnostics should move out of `.github/workflows/ci.yml` into a separate non-required workflow after the PR check recovery fix settles.
- [ ] Collapse duplicated Community CI and release validation steps into a reusable workflow once the tag-release hardening has proven stable.
- [ ] Mirror the delivery-contract system into the private `ee` and `marketing` repositories so private-repo-local work can declare obligations before the public submodule pointer update stage.

- [ ] Make the deploy pre-flight start the Enterprise image with its own command. `scripts/smoke_test_ce_image.sh` starts gunicorn directly for the `enterprise` profile because `ee/deployment/startup.sh` used to call the Azure metadata service; it no longer does (2026-11-25), so the override can go once the `ee` pointer carries the new script. Needs a Docker daemon to try.
- [ ] Log forwarding: saving the settings reconfigures only the gunicorn worker that served the request; the other worker keeps its old state until the next restart. Have each worker notice a changed setting (for example a version row checked with the five-minute cache).
- [ ] Log forwarding attaches its handler to `app.logger` only, which is the logger named `app`. Records from other modules (`ee.backend.*`, `retention`, `migrations`, gunicorn) are not forwarded. Decide whether the handler belongs on the root logger.

## Decision templates

- [ ] First follow-up: make the surfaces outside the web app use the organisation's template headings. Notification emails (`notifications.py`), Slack messages and modals, Teams cards, the external AI REST API (`/api/ai`) and exports still say Context, Decision and Consequences, and none of them shows or accepts the decision type. The Slack, Teams and REST API parts live in `ee/`; all of them can read `decision_templates.get_template(...)`. The MCP tools are done (2026-11-24): `get_decision_template`, `decision_type` in results, on create and as a filter.
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

- [ ] Harden MCP for external listing readiness: stable schemas, auth flow, pagination, error contracts, rate limits, and conformance coverage. Done on 2026-11-24 against specification revision 2026-07-28: version negotiation for both protocol eras, error contracts, pagination of results, tool titles and behaviour hints, conformance tests (`tests/test_mcp_spec_and_templates.py`). Still open: the items below.
- [ ] MCP authorization by OAuth. The server takes an API key as a bearer token, which the specification allows (authorization is optional) but which is not the specification's OAuth model. Clients that only do OAuth cannot connect: claude.ai custom connectors without the "Request headers" beta, and directory listings. Needs an OAuth 2.1 authorization server (authorization code with PKCE, a consent page tied to the signed-in user and tenant, token and refresh endpoints, Client ID Metadata Documents and, for older clients, Dynamic Client Registration), protected resource metadata (RFC 9728) with a `resource_metadata` challenge on 401, audience-bound tokens (RFC 8707), and scopes mapped to read/search/write. The `/.well-known/oauth-*` routes that answer 404 today become the metadata documents.
  - Design agreed on 2026-11-25: Decision Records is its own authorization server (issuer on the app host, resource `https://decisionrecords.org/api/mcp`), public clients identified by Client ID Metadata Documents, PKCE S256 only, opaque hashed tokens (1 hour access, 30 days idle refresh with rotation and reuse detection, 180 days per consent), scopes `decisions:read` and `decisions:write`. Dynamic Client Registration is deferred until a real client needs it.
  - [x] Worker: the apex proxies `/.well-known/oauth-protected-resource`, `/.well-known/oauth-authorization-server` and `/.well-known/openid-configuration` to the app (merged; the worker still has to be deployed).
  - [x] Storage and service without any HTTP surface (2026-11-25): tables and migration `2.7.0`, `ee/backend/oauth_server/` (token and grant service, PKCE, scopes, redirect URI matching, client metadata documents with a fetcher that cannot reach inside the network), housekeeping, erasure and data export. Tests: `tests/test_oauth_storage.py`, `tests/test_oauth_token_service.py`, `tests/test_oauth_client_metadata.py`.
  - [x] Endpoints (2026-11-25): metadata documents, `/oauth/authorize`, consent API, `/oauth/token`, `/oauth/revoke`, connected-applications API for users and organisation administrators, the system switch `oauth_server_enabled` (off by default; with it off everything answers as before), OAuth tokens on `/api/mcp` with the `resource_metadata` challenge and 403 `insufficient_scope`, a per-credential rate limit, `/.well-known/openid-configuration` as 404 JSON, `frame-ancestors 'none'` on the consent paths. Private CI runs the OAuth tests on PostgreSQL too, including tests that race several connections. Reference and threat table: `ee/docs/oauth-server.md`. Tests: `tests/test_oauth_endpoints.py`, `tests/test_oauth_concurrency.py`.
  - [x] Security review of the endpoints (2026-11-25): nothing critical; eight findings fixed with a regression test each (`ee/docs/oauth-server.md`, threat table). The organisation's "External AI access" switch now gates OAuth and is re-checked on every MCP request, also for API keys; the client metadata fetch has one overall deadline; a refresh token replayed inside the grace window is detected; rate limits are never keyed on a caller-supplied client id; anonymous consent requests are capped and purged; a lost membership ends the connection for good.
  - [ ] The switch can only be set from a shell (`ee.backend.oauth_server.config.set_enabled`). It needs a place in the super admin settings page and API.
  - [ ] Consent page, resume after sign-in, connected apps for users and tenant admins.
  - [ ] Super admin switch, website text, tests with real clients (claude.ai, Claude Code, ChatGPT, MCP Inspector), then enabling.
  - [ ] Not verifiable before production: whether the production VM can fetch the client documents of `claude.ai` and `chatgpt.com` (fetched fine from a developer machine on 2026-11-25), and whether Cloudflare lets Anthropic's and OpenAI's servers reach the token endpoint.
- [ ] MCP tools not yet offered: change a decision's text or its decision type (the web app can; there is only `update_decision_status`), and `outputSchema` for the tools (results already carry `structuredContent`).
- [ ] MCP resources and prompts are not offered. Worth it only if clients start preferring them: a `record a decision` prompt built from the tenant's template, and decisions as resources for clients that attach context by URI.
- [x] The MCP endpoint had no per-key rate limit of its own. Done on 2026-11-25 (Enterprise): 300 requests per minute per credential, API key or OAuth token.
- [ ] The app-wide rate limiter counts every visitor in one bucket. It keys on `request.remote_addr`, and behind a reverse proxy that is the proxy's address for everyone (gunicorn has no trusted-proxy setting and the app has no `ProxyFix`), so 200 requests per minute is shared by all visitors of a worker and anyone can use it up. Keying on the visitor's address means trusting a header (`CF-Connecting-IP` in the hosted service), which is only safe when the origin accepts connections from the proxy alone: establish that first, then change the key. Until then, limits that matter should be keyed on a credential or the signed-in user, as the OAuth endpoints do.
- [x] MCP decision results carried the whole user record for `created_by` and `updated_by` (email, `auth_type`, `has_passkey`, `has_seen_admin_onboarding`), because they reused `to_dict`; `owner`, `creator`, history `changed_by` and comment authors fell back to the email address. Done on 2026-11-25: people are `{id, name}`, the name falls back to the part of the address before the "@", and `owner_email`, `tenant_id`, `domain` and `creator` are gone from MCP results (`ee/backend/ai/people.py`, `tests/test_mcp_user_fields_and_stale_keys.py`). `/api/ai` never returned the user record; its `creator`, `owner` and `changed_by` strings fell back to the email address and no longer do.
- [x] API keys outlived their owner's place in the organisation. Done on 2026-11-25: MCP and `/api/ai` refuse a key whose owner is anonymised or deleted, whose organisation is deleted (also during the 30 days before erasure), or whose owner has no membership (`AIApiKeyService.resolve_owner`). Erasing a user already revoked the keys and erasing a tenant already deleted them; nothing in the app removes a single membership yet, so that check guards a future "remove member" action.
- [ ] Before the next Enterprise deploy, count in production the unrevoked API keys whose owner has no `tenant_memberships` row for the key's tenant (expected: none). Such a key stops working with the change above.
- [ ] MCP was tested on 2026-11-24 with MCP Inspector CLI 2.16.0, the Python SDK 2.3.0, the TypeScript SDK 1.32.2 and Claude Code 2.1.331, on localhost. Not yet tested: claude.ai custom connectors, Cursor, VS Code, ChatGPT, and a real browser `Origin` through Cloudflare.
- [ ] Prepare a ChatGPT plugin/app listing package for the MCP once the server contract is stable.
