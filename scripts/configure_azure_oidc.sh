#!/usr/bin/env bash
set -euo pipefail

# Create a GitHub Actions Azure OIDC app registration and configure the
# deployment environments with the variables consumed by azure/login.
#
# Requirements:
# - Azure CLI authenticated to the target tenant/subscription
# - GitHub CLI authenticated as a repository admin
#
# Usage:
#   GITHUB_OWNER=DecisionRecordsORG GITHUB_REPO=DecisionRecords scripts/configure_azure_oidc.sh
#
# Optional role assignment:
#   ASSIGN_AZURE_ROLES=1 AZURE_ACR_NAME=<acr> AZURE_RESOURCE_GROUP=<rg> AZURE_VM_NAME=<vm> scripts/configure_azure_oidc.sh production-private
#   ASSIGN_AZURE_ROLES=1 AZURE_ACR_NAME=<acr> AZURE_RESOURCE_GROUP=<rg> AZURE_CONTAINER_APP_NAME=<app> scripts/configure_azure_oidc.sh production-public
#
# Pass environment names as arguments to override the default app environments:
#   scripts/configure_azure_oidc.sh production-public production-private

OWNER="${GITHUB_OWNER:-DecisionRecordsORG}"
REPO="${GITHUB_REPO:-DecisionRecords}"
APP_NAME="${AZURE_APP_NAME:-decisionrecords-github-actions}"
ASSIGN_ROLES="${ASSIGN_AZURE_ROLES:-0}"

if [[ "$#" -gt 0 ]]; then
  ENVIRONMENTS=("$@")
else
  ENVIRONMENTS=(production-public production-private)
fi

for command in az gh; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "${command} CLI is required"
    exit 1
  fi
done

gh auth status >/dev/null
az account show >/dev/null

if [[ -n "${AZURE_SUBSCRIPTION_ID:-}" ]]; then
  az account set --subscription "$AZURE_SUBSCRIPTION_ID"
fi

TENANT_ID="${AZURE_TENANT_ID:-$(az account show --query tenantId -o tsv)}"
SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID:-$(az account show --query id -o tsv)}"

echo "Configuring Azure OIDC for ${OWNER}/${REPO}"
echo "Azure tenant: ${TENANT_ID}"
echo "Azure subscription: ${SUBSCRIPTION_ID}"

APP_ID="$(az ad app list --display-name "$APP_NAME" --query "[0].appId" -o tsv)"
if [[ -z "$APP_ID" || "$APP_ID" == "None" ]]; then
  echo "Creating Azure app registration: ${APP_NAME}"
  APP_ID="$(az ad app create --display-name "$APP_NAME" --query appId -o tsv)"
else
  echo "Using existing Azure app registration: ${APP_NAME}"
fi

SP_ID="$(az ad sp list --filter "appId eq '${APP_ID}'" --query "[0].id" -o tsv)"
if [[ -z "$SP_ID" || "$SP_ID" == "None" ]]; then
  echo "Creating service principal for app registration"
  SP_ID="$(az ad sp create --id "$APP_ID" --query id -o tsv)"
else
  echo "Using existing service principal"
fi

tmpfile="$(mktemp)"
trap 'rm -f "$tmpfile"' EXIT

for environment in "${ENVIRONMENTS[@]}"; do
  credential_name="github-${environment}"
  subject="repo:${OWNER}/${REPO}:environment:${environment}"
  existing_credential="$(az ad app federated-credential list \
    --id "$APP_ID" \
    --query "[?name=='${credential_name}'].name | [0]" \
    -o tsv)"

  if [[ -z "$existing_credential" || "$existing_credential" == "None" ]]; then
    echo "Creating federated credential for ${environment}"
    cat > "$tmpfile" <<JSON
{
  "name": "${credential_name}",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "${subject}",
  "description": "GitHub Actions OIDC for ${OWNER}/${REPO} ${environment}",
  "audiences": [
    "api://AzureADTokenExchange"
  ]
}
JSON
    az ad app federated-credential create --id "$APP_ID" --parameters "$tmpfile" >/dev/null
  else
    echo "Federated credential already exists for ${environment}"
  fi

  echo "Setting GitHub Environment variables for ${environment}"
  gh variable set AZURE_CLIENT_ID --repo "${OWNER}/${REPO}" --env "$environment" --body "$APP_ID" >/dev/null
  gh variable set AZURE_TENANT_ID --repo "${OWNER}/${REPO}" --env "$environment" --body "$TENANT_ID" >/dev/null
  gh variable set AZURE_SUBSCRIPTION_ID --repo "${OWNER}/${REPO}" --env "$environment" --body "$SUBSCRIPTION_ID" >/dev/null
done

if [[ "$ASSIGN_ROLES" == "1" ]]; then
  if [[ -z "${AZURE_ACR_NAME:-}" ]]; then
    echo "ASSIGN_AZURE_ROLES=1 requires AZURE_ACR_NAME"
    exit 1
  fi

  acr_scope="$(az acr show --name "$AZURE_ACR_NAME" --query id -o tsv)"

  ensure_role_assignment() {
    local role="$1"
    local scope="$2"
    local target="$3"
    local existing_assignment

    existing_assignment="$(az role assignment list \
      --assignee "$SP_ID" \
      --role "$role" \
      --scope "$scope" \
      --query "[0].id" \
      -o tsv)"

    if [[ -z "$existing_assignment" || "$existing_assignment" == "None" ]]; then
      echo "Assigning ${role} on ${target}"
      az role assignment create \
        --assignee-object-id "$SP_ID" \
        --assignee-principal-type ServicePrincipal \
        --role "$role" \
        --scope "$scope" >/dev/null
    else
      echo "${role} already assigned on ${target}"
    fi
  }

  ensure_role_assignment "AcrPush" "$acr_scope" "ACR ${AZURE_ACR_NAME}"

  if [[ -n "${AZURE_VM_NAME:-}" ]]; then
    if [[ -z "${AZURE_RESOURCE_GROUP:-}" ]]; then
      echo "AZURE_VM_NAME role assignment requires AZURE_RESOURCE_GROUP"
      exit 1
    fi

    vm_scope="$(az vm show \
      --resource-group "$AZURE_RESOURCE_GROUP" \
      --name "$AZURE_VM_NAME" \
      --query id \
      -o tsv)"
    ensure_role_assignment "Virtual Machine Contributor" "$vm_scope" "VM ${AZURE_VM_NAME}"
  fi

  if [[ -n "${AZURE_CONTAINER_APP_NAME:-}" ]]; then
    if [[ -z "${AZURE_RESOURCE_GROUP:-}" ]]; then
      echo "AZURE_CONTAINER_APP_NAME role assignment requires AZURE_RESOURCE_GROUP"
      exit 1
    fi

    container_app_scope="$(az resource show \
      --resource-group "$AZURE_RESOURCE_GROUP" \
      --resource-type Microsoft.App/containerApps \
      --name "$AZURE_CONTAINER_APP_NAME" \
      --query id \
      -o tsv)"
    ensure_role_assignment "Azure Container Apps Contributor" "$container_app_scope" "Container App ${AZURE_CONTAINER_APP_NAME}"
  fi

  if [[ -z "${AZURE_VM_NAME:-}" && -z "${AZURE_CONTAINER_APP_NAME:-}" ]]; then
    echo "No AZURE_VM_NAME or AZURE_CONTAINER_APP_NAME provided; only ACR push was assigned."
  fi
fi

cat <<EOF
Azure OIDC configured.

GitHub Environment variables updated for:
$(printf -- '- %s\n' "${ENVIRONMENTS[@]}")

Azure client ID:
${APP_ID}

Next steps:
- Ensure each deployment environment also has the app-specific Azure variables documented in docs/deployment.md.
- Remove the legacy AZURE_CREDENTIALS secret after one successful OIDC deployment.
EOF
