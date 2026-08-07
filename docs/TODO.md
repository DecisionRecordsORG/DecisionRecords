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
- [ ] Define a canonical GitHub PR CI path for the private `ee` repository; today EE-only branches do not report hosted PR checks on GitHub.
- [ ] Extract the shared CI job graph into a reusable workflow after revalidating required check names against branch protection on `main`.
- [ ] Decide whether a dedicated `ci-recovery.yml` wrapper is still needed once the reusable workflow split lands.
- [ ] Decide whether manual CI diagnostics should move out of `.github/workflows/ci.yml` into a separate non-required workflow after the PR check recovery fix settles.
- [ ] Collapse duplicated Community CI and release validation steps into a reusable workflow once the tag-release hardening has proven stable.

## Versioning / Releases

- [ ] Verify the live marketing `/releases` page after the latest deploy finishes.
- [ ] Decide whether the marketing `/releases` page should keep using the runtime GitHub Releases API or switch to a build-time release snapshot for stronger SEO and lower runtime dependency.
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
