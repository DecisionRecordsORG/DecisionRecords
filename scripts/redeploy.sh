#!/bin/bash
# Quick redeploy script for Architecture Decisions application
# This script builds, pushes, and redeploys the container with the new image
#
# Usage: ./scripts/redeploy.sh
#
# Prerequisites:
# - Azure CLI installed and logged in (az login)
# - Docker running
# - Git changes committed (enforced by this script)

set -e

# Configuration - matches CLAUDE.md
RESOURCE_GROUP="adr-resources-eu"
CONTAINER_NAME="adr-app-eu"
REGISTRY_NAME="adrregistry2024eu"
IMAGE_NAME="architecture-decisions"
GATEWAY_NAME="adr-appgateway"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${BLUE}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }

# Check for uncommitted changes (excluding local settings)
check_git_status() {
    log "Checking git status..."
    # Exclude .claude/settings.local.json from check as it's machine-specific
    local changes=$(git status --porcelain | grep -v ".claude/settings.local.json" || true)
    if [[ -n "$changes" ]]; then
        echo "$changes"
        error "Uncommitted changes detected. Please commit before deploying.\nRun: git add . && git commit -m 'your message'"
    fi
    success "Git status clean"
}

# Check Azure login
check_azure_login() {
    log "Checking Azure login..."
    if ! az account show &> /dev/null; then
        error "Not logged into Azure. Run: az login"
    fi
    success "Azure login OK"
}

# Build Docker image
build_image() {
    log "Building Docker image..."
    local registry_server="${REGISTRY_NAME}.azurecr.io"
    local image_tag="${registry_server}/${IMAGE_NAME}:latest"

    docker build --platform linux/amd64 \
        -f deployment/Dockerfile.production \
        -t "$image_tag" .

    success "Image built: $image_tag"
}

# Push to ACR
push_image() {
    log "Logging into Azure Container Registry..."
    az acr login --name "$REGISTRY_NAME"

    log "Pushing image to registry..."
    local registry_server="${REGISTRY_NAME}.azurecr.io"
    local image_tag="${registry_server}/${IMAGE_NAME}:latest"

    docker push "$image_tag"
    success "Image pushed: $image_tag"
}

# Force container to pull new image by recreating it
redeploy_container() {
    log "Getting current container configuration..."

    # Get the current container's ARM template
    local registry_server="${REGISTRY_NAME}.azurecr.io"
    local registry_username=$(az acr credential show --name "$REGISTRY_NAME" --query username -o tsv)
    local registry_password=$(az acr credential show --name "$REGISTRY_NAME" --query "passwords[0].value" -o tsv)

    log "Stopping current container..."
    az container stop --name "$CONTAINER_NAME" --resource-group "$RESOURCE_GROUP" 2>/dev/null || true

    log "Waiting for container to stop..."
    sleep 10

    log "Starting container with new image..."
    # Use the existing ARM template to redeploy
    # This forces a new image pull because we're doing a deployment
    az container start --name "$CONTAINER_NAME" --resource-group "$RESOURCE_GROUP"

    success "Container redeployed"
}

# Wait for container to be ready
wait_for_container() {
    log "Waiting for container to be ready..."
    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        local state=$(az container show --name "$CONTAINER_NAME" --resource-group "$RESOURCE_GROUP" --query "instanceView.state" -o tsv 2>/dev/null || echo "Unknown")

        if [ "$state" == "Running" ]; then
            success "Container is running"
            return 0
        fi

        log "Attempt $attempt/$max_attempts: Container state is '$state', waiting..."
        sleep 10
        attempt=$((attempt + 1))
    done

    error "Container did not start within expected time. Check logs with: az container logs --name $CONTAINER_NAME --resource-group $RESOURCE_GROUP"
}

# Update Application Gateway if needed
update_gateway() {
    log "Checking Application Gateway backend health..."

    # Get container IP
    local container_ip=$(az container show --name "$CONTAINER_NAME" --resource-group "$RESOURCE_GROUP" --query "ipAddress.ip" -o tsv)
    log "Container IP: $container_ip"

    # Get backend pool IP
    local backend_ip=$(az network application-gateway address-pool show \
        --gateway-name "$GATEWAY_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --name "adr-backend-pool" \
        --query "backendAddresses[0].ipAddress" -o tsv 2>/dev/null || echo "")

    if [ -n "$backend_ip" ] && [ "$container_ip" != "$backend_ip" ]; then
        log "Updating Application Gateway backend pool..."
        az network application-gateway address-pool update \
            --gateway-name "$GATEWAY_NAME" \
            --resource-group "$RESOURCE_GROUP" \
            --name "adr-backend-pool" \
            --servers "$container_ip"
        success "Gateway backend updated"
    else
        log "Gateway backend IP matches container IP"
    fi
}

# Show container logs
show_logs() {
    log "Recent container logs:"
    echo "---"
    az container logs --name "$CONTAINER_NAME" --resource-group "$RESOURCE_GROUP" --tail 20 2>/dev/null || warn "Could not fetch logs yet"
    echo "---"
}

# Main
main() {
    echo ""
    log "=== Architecture Decisions Redeploy Script ==="
    echo ""

    check_git_status
    check_azure_login
    build_image
    push_image
    redeploy_container
    wait_for_container
    update_gateway
    show_logs

    echo ""
    success "=== Deployment Complete ==="
    echo ""
    echo "Application URL: https://architecture-decisions.org"
    echo ""
    echo "Monitor logs: az container logs --name $CONTAINER_NAME --resource-group $RESOURCE_GROUP --follow"
    echo ""
}

main "$@"
