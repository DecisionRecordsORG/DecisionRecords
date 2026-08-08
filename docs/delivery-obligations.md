# Delivery Obligations

Decision Records now uses repo-owned delivery contracts to decide what must happen after a merge.

This closes the gap between:

- "CI passed"
- "enterprise production was deployed"
- "Community Edition was actually released"

## Why This Exists

The shared core serves both Community Edition and Enterprise Edition. A merged shared-core fix can therefore create multiple obligations:

- deploy `production-private`
- publish a Community release

CI alone does not tell us whether those follow-up actions still need to happen. Delivery contracts do.

## Model

Contracts live under:

```text
.delivery/changes/*.toml
```

Each contract declares:

- `change_type`
- `surfaces`
- artifact obligations for:
  - `enterprise_app`
  - `community_release`
  - `marketing_website`

Outstanding obligations are then derived from:

- successful `Deploy Enterprise Edition` runs
- Community release tags
- successful marketing deploy runs

## Required Rules

- One current contract per PR for the current changes.
- Backfill contracts may be added with `tracked_commit` for already-merged work.
- Shared-core changes must require `enterprise_app`.
- Shared-core changes must also declare a Community release requirement or candidate.
- Shared-core security fixes must require a Community patch-or-higher release.
- Enterprise-only changes must not create Community release obligations.
- Marketing-only changes must carry a marketing target SHA so the website deploy can be resolved deterministically.

## Local Commands

Validate the staged contract:

```bash
uv run python scripts/check_delivery_contract.py --mode staged
```

List open obligations:

```bash
uv run python scripts/list_open_obligations.py --format markdown
```

## Automation

- PR CI runs `Delivery Contract` as a required check.
- Commit QA runs the staged delivery contract validator.
- `Delivery Obligations` runs on `main` and publishes a JSON artifact plus a markdown summary.

## Current Backfill

The merged superadmin security hardening change is backfilled in:

```text
.delivery/changes/2026-08-08-superadmin-security.toml
```

That lets the repository answer, deterministically, whether:

- enterprise deployment is done
- a Community patch release is still outstanding
