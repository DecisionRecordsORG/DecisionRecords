#!/usr/bin/env bash
set -euo pipefail

# Configure repository-level Phase 1 CI/CD guardrails.
#
# Requirements:
# - GitHub CLI authenticated as a repository admin
# - Scope/permissions to administer repository settings
#
# Usage:
#   GITHUB_OWNER=DecisionRecordsORG GITHUB_REPO=DecisionRecords scripts/configure_github_guardrails.sh
#   GITHUB_OWNER=DecisionRecordsORG GITHUB_REPO=ee \
#     GITHUB_REQUIRED_CONTEXTS="Enterprise Quality Gate" \
#     GITHUB_REQUIRE_LINEAR_HISTORY=false \
#     GITHUB_ALLOW_MERGE_COMMIT=true \
#     GITHUB_ALLOW_REBASE_MERGE=false \
#     GITHUB_ALLOW_SQUASH_MERGE=false \
#     scripts/configure_github_guardrails.sh

OWNER="${GITHUB_OWNER:-DecisionRecordsORG}"
REPO="${GITHUB_REPO:-DecisionRecords}"
BRANCH="${GITHUB_BRANCH:-main}"
REQUIRED_CONTEXTS="${GITHUB_REQUIRED_CONTEXTS:-Quality Gate}"
REQUIRE_LINEAR_HISTORY="${GITHUB_REQUIRE_LINEAR_HISTORY:-true}"
ENVIRONMENTS="${GITHUB_ENVIRONMENTS-production-private}"
ALLOW_MERGE_COMMIT="${GITHUB_ALLOW_MERGE_COMMIT:-}"
ALLOW_REBASE_MERGE="${GITHUB_ALLOW_REBASE_MERGE:-}"
ALLOW_SQUASH_MERGE="${GITHUB_ALLOW_SQUASH_MERGE:-}"
DELETE_BRANCH_ON_MERGE="${GITHUB_DELETE_BRANCH_ON_MERGE:-}"

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI is required: https://cli.github.com/"
  exit 1
fi

tmpfile="$(mktemp)"
trap 'rm -f "$tmpfile"' EXIT

REQUIRED_CONTEXTS="$REQUIRED_CONTEXTS" REQUIRE_LINEAR_HISTORY="$REQUIRE_LINEAR_HISTORY" python3 - <<'PY' > "$tmpfile"
import json
import os

contexts = [ctx.strip() for ctx in os.environ["REQUIRED_CONTEXTS"].split(",") if ctx.strip()]
payload = {
    "required_status_checks": {
        "strict": True,
        "contexts": contexts,
    },
    "enforce_admins": True,
    "required_pull_request_reviews": {
        "dismiss_stale_reviews": True,
        "require_code_owner_reviews": False,
        "required_approving_review_count": 0,
    },
    "restrictions": None,
    "required_linear_history": os.environ["REQUIRE_LINEAR_HISTORY"].lower() == "true",
    "allow_force_pushes": False,
    "allow_deletions": False,
    "block_creations": False,
    "required_conversation_resolution": True,
    "lock_branch": False,
    "allow_fork_syncing": True,
}
print(json.dumps(payload, indent=2))
PY

echo "Configuring branch protection for ${OWNER}/${REPO}:${BRANCH}"
gh api \
  --method PUT \
  -H "Accept: application/vnd.github+json" \
  "/repos/${OWNER}/${REPO}/branches/${BRANCH}/protection" \
  --input "$tmpfile" >/dev/null

if [[ -n "$ALLOW_MERGE_COMMIT" || -n "$ALLOW_REBASE_MERGE" || -n "$ALLOW_SQUASH_MERGE" || -n "$DELETE_BRANCH_ON_MERGE" ]]; then
  echo "Configuring repository merge settings for ${OWNER}/${REPO}"
  api_args=(
    --method PATCH
    -H "Accept: application/vnd.github+json"
    "/repos/${OWNER}/${REPO}"
  )
  [[ -n "$ALLOW_MERGE_COMMIT" ]] && api_args+=(-F "allow_merge_commit=${ALLOW_MERGE_COMMIT}")
  [[ -n "$ALLOW_REBASE_MERGE" ]] && api_args+=(-F "allow_rebase_merge=${ALLOW_REBASE_MERGE}")
  [[ -n "$ALLOW_SQUASH_MERGE" ]] && api_args+=(-F "allow_squash_merge=${ALLOW_SQUASH_MERGE}")
  [[ -n "$DELETE_BRANCH_ON_MERGE" ]] && api_args+=(-F "delete_branch_on_merge=${DELETE_BRANCH_ON_MERGE}")
  gh api "${api_args[@]}" >/dev/null
fi

if [[ -n "$ENVIRONMENTS" ]]; then
  IFS=',' read -r -a environment_list <<< "$ENVIRONMENTS"
  for environment in "${environment_list[@]}"; do
    environment="${environment//[[:space:]]/}"
    [[ -z "$environment" ]] && continue
    echo "Ensuring GitHub Environment: ${environment}"
    gh api \
      --method PUT \
      -H "Accept: application/vnd.github+json" \
      "/repos/${OWNER}/${REPO}/environments/${environment}" >/dev/null
  done
fi

cat <<EOF
Guardrails configured.

Review these environment settings in GitHub:
- Add required reviewers for production environments when there is a second maintainer or operator.
- Scope deployment secrets/variables to the matching environments.
- Configure Azure OIDC variables with scripts/configure_azure_oidc.sh during Phase 2.
EOF
