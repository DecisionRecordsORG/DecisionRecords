# TODO

This file is the standing backlog for work that was identified but not completed in the current session.

Update rules:
- Add deferred work here before ending a session.
- Remove items when done.
- Keep entries short and actionable.
- Prefer linking to the owning workflow, doc, or file when relevant.

## Deployment / CI-CD

- [ ] Decide whether `Deploy Enterprise Edition` should remain manual-only or become gated auto-deploy after `CI` on `main`.
- [ ] Re-run and verify the current enterprise deploy from `main` after the workflow fixes merged.
- [ ] Replace deprecated GitHub Actions dependencies still running on forced Node.js 24 compatibility mode.

## Versioning / Releases

- [ ] Verify the live marketing `/releases` page after the latest deploy finishes.
- [ ] Make the marketing `/releases` page load real GitHub Release data and show the GHCR pull command for each Community Edition release.
- [ ] Add a clearer compatibility note explaining how public Community releases relate to Enterprise deployments.
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
