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

OWNER="${GITHUB_OWNER:-DecisionRecordsORG}"
REPO="${GITHUB_REPO:-DecisionRecords}"
BRANCH="${GITHUB_BRANCH:-main}"

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI is required: https://cli.github.com/"
  exit 1
fi

tmpfile="$(mktemp)"
trap 'rm -f "$tmpfile"' EXIT

cat > "$tmpfile" <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "Quality Gate"
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false,
    "required_approving_review_count": 0
  },
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "block_creations": false,
  "required_conversation_resolution": true,
  "lock_branch": false,
  "allow_fork_syncing": true
}
JSON

echo "Configuring branch protection for ${OWNER}/${REPO}:${BRANCH}"
gh api \
  --method PUT \
  -H "Accept: application/vnd.github+json" \
  "/repos/${OWNER}/${REPO}/branches/${BRANCH}/protection" \
  --input "$tmpfile" >/dev/null

for environment in production-website production-public production-private; do
  echo "Ensuring GitHub Environment: ${environment}"
  gh api \
    --method PUT \
    -H "Accept: application/vnd.github+json" \
    "/repos/${OWNER}/${REPO}/environments/${environment}" \
    -F wait_timer=0 >/dev/null
done

cat <<EOF
Guardrails configured.

Review these environment settings in GitHub:
- Add required reviewers for production environments when there is a second maintainer or operator.
- Scope deployment secrets/variables to the matching environments.
- Configure Azure OIDC variables with scripts/configure_azure_oidc.sh during Phase 2.
EOF
