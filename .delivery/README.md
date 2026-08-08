# Delivery Contracts

Delivery contracts make release and deploy obligations explicit.

The problem they solve is simple: CI can prove that a change passes tests, but it does not answer what must happen next for:

- `community-release`
- `enterprise-app`
- `marketing-website`

Every mergeable PR should carry one current contract under `.delivery/changes/`. The contract states:

- what kind of change this is
- which code surface it affects
- which artifacts must be released or deployed afterward

The repository then derives open obligations from:

- merged contracts
- Community release tags
- successful enterprise deploy workflow runs
- successful marketing deploy workflow runs

That keeps the state deterministic for future sessions:

- no hand-maintained checklist
- no hidden operator memory
- no guessing from file paths alone

## Contract Rules

- Current PR work should update exactly one contract without `tracked_commit`.
- Historical backfills may add additional contracts with `tracked_commit`.
- `shared_core` changes must require `enterprise_app`.
- `shared_core` changes must also require a non-`none` `community_release`.
- `shared_core` `security_fix` changes must require a Community patch-or-higher release.
- `enterprise_only` changes must require `enterprise_app` and must not require `community_release`.
- `marketing_only` changes must require `marketing_website` and must not require `community_release`.
- `ops_docs_only` changes should not create release or deploy obligations.

## Commands

Validate the staged contract for a local commit:

```bash
uv run python scripts/check_delivery_contract.py --mode staged
```

Validate a PR diff locally:

```bash
uv run python scripts/check_delivery_contract.py --mode pr --base-ref refs/remotes/origin/main --head-ref HEAD
```

List currently open obligations:

```bash
uv run python scripts/list_open_obligations.py --format markdown
```

## Backfills

If a release or deployment rule is being introduced after a change already merged, add a backfill contract with:

- `tracked_commit` set to the already-merged public commit SHA
- the artifact obligations that should have been tracked

That lets the system immediately surface unresolved follow-up work without rewriting history.
