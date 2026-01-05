#!/bin/bash
# redeploy-vm.sh - Deploy latest image to Azure B1s VM
#
# This script builds, pushes, and redeploys the container to the VM.
# It mirrors the functionality of redeploy.sh but uses SSH instead of ACI commands.
#
# Usage: ./scripts/redeploy-vm.sh <patch|minor|major|--no-bump>
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
# - SSH key at ~/.ssh/adr-vm-key (or set SSH_KEY env var)
# - VM set up via setup-vm.sh

set -e

# Configuration
VM_IP="${VM_IP:-10.0.1.100}"
VM_USER="${VM_USER:-azureuser}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/adr-vm-key}"
REGISTRY_NAME="adrregistry2024eu"
IMAGE_NAME="architecture-decisions"
RESOURCE_GROUP="adr-resources-eu"

# Cloudflare configuration
CLOUDFLARE_ZONE_ID="592b5c760ee2d37cabc0bcba764693ea"

# Version bump type (REQUIRED argument)
VERSION_BUMP="${1:-}"

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

# Validate required argument
validate_version_argument() {
    if [[ -z "$VERSION_BUMP" ]]; then
        echo -e "${RED}[ERROR]${NC} Version argument is REQUIRED"
        echo ""
        echo "Usage: ./scripts/redeploy-vm.sh <patch|minor|major|--no-bump>"
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

# Check for uncommitted changes
check_git_status() {
    log "Checking git status..."
    local changes=$(git status --porcelain | grep -v ".claude/settings.local.json" || true)
    if [[ -n "$changes" ]]; then
        echo "$changes"
        error "Uncommitted changes detected. Please commit before deploying.\nRun: git add . && git commit -m 'your message'"
    fi
    success "Git status clean"
}

# Generate prerender routes for blog posts
generate_prerender_routes() {
    log "Generating prerender routes for blog posts..."
    ./scripts/generate-prerender-routes.sh

    if git diff --quiet frontend/prerender-routes.txt 2>/dev/null; then
        log "Prerender routes unchanged"
    else
        log "Prerender routes changed, committing..."
        git add frontend/prerender-routes.txt
        git commit -m "Auto-update prerender routes for blog posts"
        success "Prerender routes committed"
    fi
}

# Check for insecure Cloudflare settings
check_cloudflare_security() {
    log "Checking Cloudflare security settings..."

    local dockerfile="deployment/Dockerfile.production"
    if [ -f "$dockerfile" ]; then
        if grep -q "FLASK_ENV.*testing" "$dockerfile"; then
            error "SECURITY: $dockerfile contains FLASK_ENV=testing which bypasses Cloudflare security!"
        fi
        if grep -q "SKIP_CLOUDFLARE_CHECK.*true" "$dockerfile"; then
            error "SECURITY: $dockerfile contains SKIP_CLOUDFLARE_CHECK=true which bypasses Cloudflare security!"
        fi
    fi

    if grep -rq "import run_local\|from run_local" app.py models.py 2>/dev/null; then
        error "SECURITY: Production code imports run_local.py which has dev-only settings!"
    fi

    if grep -q "return True.*# BYPASS\|# DISABLE" cloudflare_security.py 2>/dev/null; then
        error "SECURITY: cloudflare_security.py contains hardcoded bypass!"
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

# Check SSH key exists
check_ssh_key() {
    log "Checking SSH key..."
    if [[ ! -f "$SSH_KEY" ]]; then
        error "SSH key not found at $SSH_KEY. Generate with: ssh-keygen -t rsa -b 4096 -f $SSH_KEY -N ''"
    fi
    success "SSH key OK"
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

# Deploy to VM via SSH
redeploy_vm() {
    log "Deploying to VM at $VM_IP..."

    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o ConnectTimeout=30 "$VM_USER@$VM_IP" bash <<'DEPLOY_EOF'
set -e

echo "Pulling latest image..."
sudo docker pull adrregistry2024eu.azurecr.io/architecture-decisions:latest

echo "Restarting service..."
sudo systemctl restart adr-app

echo "Waiting for container to start..."
sleep 10

echo "Service status:"
sudo systemctl status adr-app --no-pager || true
DEPLOY_EOF

    success "VM deployment complete"
}

# Wait for application to be healthy
wait_for_healthy() {
    log "Waiting for application to be healthy..."
    local max_attempts=30
    local attempt=1

    while [[ $attempt -le $max_attempts ]]; do
        if ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$VM_USER@$VM_IP" \
            "curl -sf http://localhost:8000/api/health > /dev/null 2>&1"; then
            success "Application is healthy"
            return 0
        fi
        log "Attempt $attempt/$max_attempts: Waiting for application..."
        sleep 10
        attempt=$((attempt + 1))
    done

    error "Application did not become healthy within expected time. Check logs with:\n  ssh -i $SSH_KEY $VM_USER@$VM_IP 'sudo docker logs adr-app'"
}

# Show logs from VM
show_logs() {
    log "Recent container logs:"
    echo "---"
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$VM_USER@$VM_IP" \
        "sudo docker logs adr-app --tail 20 2>/dev/null" || warn "Could not fetch logs"
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

    if echo "$response" | grep -q '"success":true'; then
        success "Cloudflare cache purged successfully"
    else
        warn "Failed to purge Cloudflare cache: $response"
    fi
}

# Main
main() {
    echo ""
    log "=== Architecture Decisions VM Redeploy Script ==="
    log "Target VM: $VM_IP"
    echo ""

    validate_version_argument
    bump_version
    generate_prerender_routes
    check_git_status
    check_cloudflare_security
    check_azure_login
    check_ssh_key
    build_image
    push_image
    redeploy_vm
    wait_for_healthy
    purge_cloudflare_cache
    show_logs

    echo ""
    success "=== Deployment Complete ==="
    echo ""
    echo "Application URL: https://decisionrecords.org"
    echo ""
    echo "Monitor logs: ssh -i $SSH_KEY $VM_USER@$VM_IP 'sudo docker logs -f adr-app'"
    echo ""
}

main "$@"
