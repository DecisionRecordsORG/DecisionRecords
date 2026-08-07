# Production Lessons KB

This note captures operational lessons that must be applied before future deployments or agent-led changes.

## Artifact Boundaries

Decision Records has three separate artifacts:

- `website`: the private commercial marketing website in `ee/marketing`.
- `production-private`: hosted app instances that include private EE modules.
- `production-public`: the open-source Community Edition app source and release artifacts. It is not deployed as a live hosted app.

Before building, deploying, or validating anything, identify which artifact is being changed. Do not deploy the Community frontend as the commercial website.

## Website Deployments

- Validate the built site with a real browser, not only `curl`.
- Capture the production page title, `h1`, console errors, and a screenshot after deployment.
- Check the actual production URL, not only a local dev server.
- Verify local port ownership before trusting a local screenshot. Use `lsof -i :<port>` or equivalent when a port was already in use.
- Keep Angular HTML/app-shell responses on `no-cache`/`no-store`; hashed JavaScript assets can otherwise strand stale app shells.
- A successful asset upload is not a successful deployment. The acceptance check is a nonblank production page with the expected commercial homepage content.
- For the commercial marketing site in `ee/marketing`, a new route is not deployable until three surfaces are kept in sync: `src/app/app.routes.ts`, `src/app/services/seo.service.ts`, and `scripts/prerender-blog.py`. Missing the prerender entry causes direct URL requests like `/releases` to fall back to the generic SPA shell in production.
- The marketing Angular build must stay independent of local machine quirks and live internet fetches. Keep Angular CLI disk cache disabled for local builds and keep production font inlining disabled; on macOS, Angular 18 + LMDB cache can abort under Node 20, and Google Fonts inlining makes builds fail in restricted-network environments.

## MCP Validation

- Validate MCP with the protocol behavior real clients use, not only a simple `tools/list` cURL request.
- Test authenticated `GET /api/mcp` probes for older Streamable HTTP clients.
- Test `initialize`, `server/discover`, `tools/list`, and at least one `tools/call`.
- Test missing auth, invalid auth, and valid API-key paths separately.
- Re-check the current official MCP transport docs before claiming compatibility with a protocol version.

## CI And PR Checks

- Required PR checks must come from the `pull_request` or `merge_group` lane. Do not assume a green `workflow_dispatch` run will satisfy GitHub branch protection for a PR.
- Do not share a concurrency group between `pull_request` and `workflow_dispatch`. Include the event type in the concurrency key so manual diagnostics cannot cancel the canonical PR run.
- Keep the required check name reserved for the canonical lane. Manual diagnostics should publish a distinct check name such as `Quality Gate (Manual)`.
- When GitHub shows a PR as blocked with missing checks, inspect all three views before changing code: `gh pr checks <number>`, `gh run view <run-id>`, and `gh api repos/<owner>/<repo>/commits/<sha>/check-runs`.
- Recovery order for stuck PR checks:
  1. Re-run the existing `pull_request` job graph.
  2. If that lane was cancelled or never attached, push a no-op commit to trigger a fresh `pull_request` synchronize event.
  3. Use `workflow_dispatch` only to diagnose the branch outside the required-check path.

## Community Release Publishing

- A release tag is not just a packaging event. It must re-run enough Community validation to stand on its own before publishing public artifacts.
- Do not assume prior PR CI is a sufficient release gate. Tagging the wrong commit or tagging after drift on `main` can still publish a broken public image if release-time validation is too shallow.
- Release metadata checks must cover the public version surface, not only `version.py`. Pinned version examples in release-facing docs should match the current Community version.

## Git And Repository Safety

- Treat the public repo and `ee/` as separate Git repositories.
- Treat `ee/marketing` as a third repository whenever the commercial website changes.
- Do not stage `ee/` changes into the public repo by accident; only the submodule pointer should change there.
- Do not mix unrelated private infra or marketing changes into an application/MCP commit.
- Commit order for nested repo work is strict: `ee/marketing` first, then `ee`, then the public repo. A parent pointer update must never reference dirty child work.
- Nested Git checks launched from hooks must clear inherited `GIT_*` environment variables before inspecting child repositories, or staged parent commits can be misread as dirty nested submodules.
- Run the CE/EE boundary check before public commits.
- Run commit QA before committing: `uv run python scripts/qa_check.py --mode commit`.
- Enable hooks in both the public repo and `ee`, then verify them with `uv run python scripts/verify_git_hooks.py`.

## Deployment Rule

Normal production deployments go through GitHub Actions and GitHub Environments. Local Azure CLI deploys are break-glass only and must be documented in the deployment notes for that incident.
