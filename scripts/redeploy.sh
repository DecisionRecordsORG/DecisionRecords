#!/bin/bash
# Quick redeploy script for Architecture Decisions application (Enterprise Edition)
# This script builds, pushes, and redeploys the container with the new image
#
# Usage: ./scripts/redeploy.sh <patch|minor|major|--no-bump>
#
# Arguments (REQUIRED - one of):
#   patch     - Bump patch version (1.0.0 -> 1.0.1) for bug fixes
#   minor     - Bump minor version (1.0.0 -> 1.1.0) for new features
#   major     - Bump major version (1.0.0 -> 2.0.0) for breaking changes
#   --no-bump - Explicitly skip version bump (for hotfixes or config changes)
#
# Prerequisites:
# - Azure CLI installed and logged in (az login)
# - Docker running
# - Git changes committed (enforced by this script)
# - CLOUDFLARE_API_TOKEN environment variable set (optional, for cache purge)
#
# Note: This deploys the Enterprise Edition. For Community Edition builds,
# use Dockerfile.community instead.

set -e

# Configuration - matches CLAUDE.md
RESOURCE_GROUP="adr-resources-eu"
CONTAINER_NAME="adr-app-eu"
REGISTRY_NAME="adrregistry2024eu"
IMAGE_NAME="architecture-decisions"
GATEWAY_NAME="adr-appgateway"

# Cloudflare configuration
CLOUDFLARE_ZONE_ID="592b5c760ee2d37cabc0bcba764693ea"

# Version bump type (REQUIRED argument)
VERSION_BUMP="${1:-}"

# Validate required argument
validate_version_argument() {
    if [[ -z "$VERSION_BUMP" ]]; then
        echo -e "${RED}[ERROR]${NC} Version argument is REQUIRED"
        echo ""
        echo "Usage: ./scripts/redeploy.sh <patch|minor|major|--no-bump>"
        echo ""
        echo "Arguments:"
        echo "  patch     - Bump patch version (1.0.0 -> 1.0.1) for bug fixes"
        echo "  minor     - Bump minor version (1.0.0 -> 1.1.0) for new features"
        echo "  major     - Bump major version (1.0.0 -> 2.0.0) for breaking changes"
        echo "  --no-bump - Explicitly skip version bump (for hotfixes or config changes)"
        echo ""
        exit 1
    fi

    case "$VERSION_BUMP" in
        patch|minor|major|--no-bump)
            # Valid argument
            ;;
        *)
            echo -e "${RED}[ERROR]${NC} Invalid argument: $VERSION_BUMP"
            echo ""
            echo "Valid arguments: patch, minor, major, --no-bump"
            echo ""
            exit 1
            ;;
    esac
}

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

# Bump version if requested
bump_version() {
    case "$VERSION_BUMP" in
        patch|minor|major)
            log "Bumping version ($VERSION_BUMP)..."
            ./scripts/version-bump.sh "$VERSION_BUMP"

            # Commit the version bump
            local new_version=$(grep -o '__version__ = "[^"]*"' version.py | cut -d'"' -f2)
            git add version.py
            git commit -m "Bump version to $new_version"
            success "Version bumped to $new_version"
            ;;
        --no-bump)
            log "Skipping version bump (--no-bump specified)"
            ;;
    esac
}

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

# Generate prerender routes for blog posts (SEO/social sharing)
generate_prerender_routes() {
    log "Generating prerender routes for blog posts..."
    ./scripts/generate-prerender-routes.sh

    # Auto-commit if routes changed
    if git diff --quiet frontend/prerender-routes.txt 2>/dev/null; then
        log "Prerender routes unchanged"
    else
        log "Prerender routes changed, committing..."
        git add frontend/prerender-routes.txt
        git commit -m "Auto-update prerender routes for blog posts"
        success "Prerender routes committed"
    fi
}

# Check for insecure Cloudflare settings in code
check_cloudflare_security() {
    log "Checking Cloudflare security settings..."

    # Check Dockerfile for insecure environment variables
    local dockerfile="deployment/Dockerfile.production"
    if [ -f "$dockerfile" ]; then
        # Check for FLASK_ENV=testing (bypasses Cloudflare check)
        if grep -q "FLASK_ENV.*testing" "$dockerfile"; then
            error "SECURITY: $dockerfile contains FLASK_ENV=testing which bypasses Cloudflare security!"
        fi

        # Check for SKIP_CLOUDFLARE_CHECK=true
        if grep -q "SKIP_CLOUDFLARE_CHECK.*true" "$dockerfile"; then
            error "SECURITY: $dockerfile contains SKIP_CLOUDFLARE_CHECK=true which bypasses Cloudflare security!"
        fi
    fi

    # Check run_local.py isn't accidentally being imported in production code
    if grep -rq "import run_local\|from run_local" app.py models.py 2>/dev/null; then
        error "SECURITY: Production code imports run_local.py which has dev-only settings!"
    fi

    # Check cloudflare_security.py doesn't have hardcoded bypasses (now in ee/backend/cloudflare/)
    local cf_security="ee/backend/cloudflare/cloudflare_security.py"
    if [ -f "$cf_security" ] && grep -q "return True.*# BYPASS\|# DISABLE" "$cf_security" 2>/dev/null; then
        error "SECURITY: $cf_security contains hardcoded bypass!"
    fi

    success "Cloudflare security settings OK"
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

# Purge Cloudflare cache
purge_cloudflare_cache() {
    if [[ -z "$CLOUDFLARE_API_TOKEN" ]]; then
        warn "CLOUDFLARE_API_TOKEN not set. Skipping cache purge."
        warn "Set it with: export CLOUDFLARE_API_TOKEN='your-token'"
        return 0
    fi

    log "Purging Cloudflare cache..."

    local response=$(curl -s -X POST \
        "https://api.cloudflare.com/client/v4/zones/${CLOUDFLARE_ZONE_ID}/purge_cache" \
        -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" \
        -H "Content-Type: application/json" \
        --data '{"purge_everything":true}')

    # Check if successful
    if echo "$response" | grep -q '"success":true'; then
        success "Cloudflare cache purged successfully"
    else
        warn "Failed to purge Cloudflare cache: $response"
    fi
}

# Main
main() {
    echo ""
    log "=== Architecture Decisions Redeploy Script (Enterprise Edition) ==="
    echo ""

    validate_version_argument
    bump_version
    generate_prerender_routes
    check_git_status
    check_cloudflare_security
    check_azure_login
    build_image
    push_image
    redeploy_container
    wait_for_container
    update_gateway
    purge_cloudflare_cache
    show_logs

    echo ""
    success "=== Deployment Complete ==="
    echo ""
    echo "Application URL: https://decisionrecords.org"
    echo ""
    echo "Monitor logs: az container logs --name $CONTAINER_NAME --resource-group $RESOURCE_GROUP --follow"
    echo ""
}

main "$@"
