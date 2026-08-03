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

## MCP Validation

- Validate MCP with the protocol behavior real clients use, not only a simple `tools/list` cURL request.
- Test authenticated `GET /api/mcp` probes for older Streamable HTTP clients.
- Test `initialize`, `server/discover`, `tools/list`, and at least one `tools/call`.
- Test missing auth, invalid auth, and valid API-key paths separately.
- Re-check the current official MCP transport docs before claiming compatibility with a protocol version.

## Git And Repository Safety

- Treat the public repo and `ee/` as separate Git repositories.
- Do not stage `ee/` changes into the public repo by accident; only the submodule pointer should change there.
- Do not mix unrelated private infra or marketing changes into an application/MCP commit.
- Run the CE/EE boundary check before public commits.
- Run commit QA before committing: `uv run python scripts/qa_check.py --mode commit`.

## Deployment Rule

Normal production deployments go through GitHub Actions and GitHub Environments. Local Azure CLI deploys are break-glass only and must be documented in the deployment notes for that incident.
