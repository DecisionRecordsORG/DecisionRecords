#!/bin/bash
# setup-vm.sh - One-time setup for Azure B1s VM
#
# This script configures a freshly deployed VM with:
# - Docker authentication to Azure Container Registry
# - Environment file with database URL and other config
# - systemd service for container auto-restart
# - Initial container pull and start
#
# Usage: ./scripts/setup-vm.sh [VM_IP]
#
# Prerequisites:
# - VM deployed via azure-deploy-vm.json
# - SSH key at ~/.ssh/adr-vm-key
# - Azure CLI logged in (az login)
# - Cloud-init has completed (Docker installed)

set -e

# Configuration
VM_IP="${1:-10.0.1.100}"
VM_USER="azureuser"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/adr-vm-key}"
REGISTRY_NAME="adrregistry2024eu"
RESOURCE_GROUP="adr-resources-eu"
KEYVAULT_NAME="adr-keyvault-eu"

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

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."

    if [[ ! -f "$SSH_KEY" ]]; then
        error "SSH key not found at $SSH_KEY. Generate with: ssh-keygen -t rsa -b 4096 -f $SSH_KEY -N ''"
    fi

    if ! az account show &> /dev/null; then
        error "Not logged into Azure. Run: az login"
    fi

    success "Prerequisites OK"
}

# Get secrets from Azure
get_azure_secrets() {
    log "Getting ACR credentials..."
    ACR_USERNAME=$(az acr credential show --name "$REGISTRY_NAME" --query username -o tsv)
    ACR_PASSWORD=$(az acr credential show --name "$REGISTRY_NAME" --query "passwords[0].value" -o tsv)

    log "Getting database URL from Key Vault..."
    DATABASE_URL=$(az keyvault secret show --vault-name "$KEYVAULT_NAME" --name database-url --query value -o tsv 2>/dev/null || echo "")

    if [[ -z "$DATABASE_URL" ]]; then
        warn "Database URL not found in Key Vault. You'll need to set it manually in /etc/adr-app/env"
        DATABASE_URL="postgresql://user:password@host:5432/database?sslmode=require"
    fi

    success "Azure secrets retrieved"
}

# Wait for VM to be ready
wait_for_vm() {
    log "Waiting for VM to be ready at $VM_IP..."
    local max_attempts=30
    local attempt=1

    while [[ $attempt -le $max_attempts ]]; do
        if ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o ConnectTimeout=5 "$VM_USER@$VM_IP" "echo 'VM ready'" &>/dev/null; then
            success "VM is accessible"
            return 0
        fi
        log "Attempt $attempt/$max_attempts: Waiting for VM..."
        sleep 10
        attempt=$((attempt + 1))
    done

    error "VM not accessible after $max_attempts attempts"
}

# Wait for cloud-init to complete
wait_for_cloud_init() {
    log "Waiting for cloud-init to complete (Docker installation)..."

    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$VM_USER@$VM_IP" bash <<'EOF'
        max_wait=300
        elapsed=0
        while [[ $elapsed -lt $max_wait ]]; do
            if [[ -f /var/lib/cloud/instance/boot-finished ]]; then
                echo "Cloud-init completed"
                exit 0
            fi
            echo "Waiting for cloud-init... ($elapsed seconds)"
            sleep 10
            elapsed=$((elapsed + 10))
        done
        echo "Warning: cloud-init did not complete in time"
        exit 1
EOF

    success "Cloud-init completed"
}

# Configure VM
configure_vm() {
    log "Configuring VM..."

    # Copy systemd service file
    log "Copying systemd service file..."
    scp -i "$SSH_KEY" -o StrictHostKeyChecking=no \
        "$(dirname "$0")/../deployment/adr-app.service" \
        "$VM_USER@$VM_IP:/tmp/adr-app.service"

    # Run configuration on VM
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$VM_USER@$VM_IP" bash -s -- \
        "$ACR_USERNAME" "$ACR_PASSWORD" "$DATABASE_URL" <<'REMOTE_SETUP'
#!/bin/bash
set -e

ACR_USERNAME="$1"
ACR_PASSWORD="$2"
DATABASE_URL="$3"

echo "=== Configuring Azure B1s VM for Architecture Decisions ==="

# Ensure Docker is running
echo "Verifying Docker..."
sudo systemctl enable docker
sudo systemctl start docker

# Login to ACR
echo "Logging into Azure Container Registry..."
echo "$ACR_PASSWORD" | sudo docker login adrregistry2024eu.azurecr.io -u "$ACR_USERNAME" --password-stdin

# Create environment directory
echo "Creating environment directory..."
sudo mkdir -p /etc/adr-app
sudo chmod 700 /etc/adr-app

# Create environment file
echo "Creating environment file..."
sudo tee /etc/adr-app/env > /dev/null <<ENV_FILE
DATABASE_URL=$DATABASE_URL
ENVIRONMENT=production
DEBUG=false
MASTER_USERNAME=admin
EMAIL_VERIFICATION_REQUIRED=true
USE_HTTPS=true
AZURE_KEYVAULT_URL=https://adr-keyvault-eu.vault.azure.net/
ENV_FILE
sudo chmod 600 /etc/adr-app/env

# Install systemd service
echo "Installing systemd service..."
sudo mv /tmp/adr-app.service /etc/systemd/system/adr-app.service
sudo chmod 644 /etc/systemd/system/adr-app.service
sudo systemctl daemon-reload

# Pull Docker image
echo "Pulling Docker image (this may take a few minutes)..."
sudo docker pull adrregistry2024eu.azurecr.io/architecture-decisions:latest

# Enable and start service
echo "Enabling and starting service..."
sudo systemctl enable adr-app
sudo systemctl start adr-app

# Wait for container to start
echo "Waiting for container to start..."
sleep 15

# Show status
echo ""
echo "=== Service Status ==="
sudo systemctl status adr-app --no-pager || true

echo ""
echo "=== Container Logs (last 10 lines) ==="
sudo docker logs adr-app --tail 10 2>/dev/null || echo "Container may still be starting..."

echo ""
echo "=== Setup Complete ==="
REMOTE_SETUP

    success "VM configuration complete"
}

# Verify application is running
verify_application() {
    log "Verifying application health..."

    local max_attempts=12
    local attempt=1

    while [[ $attempt -le $max_attempts ]]; do
        if ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$VM_USER@$VM_IP" \
            "curl -sf http://localhost:8000/api/health" &>/dev/null; then
            success "Application is healthy!"
            return 0
        fi
        log "Attempt $attempt/$max_attempts: Waiting for application..."
        sleep 10
        attempt=$((attempt + 1))
    done

    warn "Application health check failed. Check logs with:"
    echo "  ssh -i $SSH_KEY $VM_USER@$VM_IP 'sudo docker logs adr-app'"
}

# Print next steps
print_next_steps() {
    echo ""
    log "=== Next Steps ==="
    echo ""
    echo "1. Verify application is accessible:"
    echo "   curl http://$VM_IP:8000/api/health"
    echo ""
    echo "2. Update Application Gateway to point to VM:"
    echo "   az network application-gateway address-pool update \\"
    echo "     --gateway-name adr-appgateway \\"
    echo "     --resource-group $RESOURCE_GROUP \\"
    echo "     --name adr-backend-pool \\"
    echo "     --servers $VM_IP"
    echo ""
    echo "3. Monitor logs:"
    echo "   ssh -i $SSH_KEY $VM_USER@$VM_IP 'sudo docker logs -f adr-app'"
    echo ""
    echo "4. Deploy new versions with:"
    echo "   ./scripts/redeploy-vm.sh patch"
    echo ""
}

# Main
main() {
    echo ""
    log "=== Architecture Decisions VM Setup Script ==="
    log "VM IP: $VM_IP"
    echo ""

    check_prerequisites
    get_azure_secrets
    wait_for_vm
    wait_for_cloud_init
    configure_vm
    verify_application
    print_next_steps

    echo ""
    success "=== VM Setup Complete ==="
    echo ""
}

main "$@"
