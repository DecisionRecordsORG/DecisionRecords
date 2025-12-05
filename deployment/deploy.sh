#!/bin/bash

# Azure Container Instances Deployment Script
# This script automates the deployment of the Architecture Decisions application to Azure

set -e

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Check if required tools are installed
check_prerequisites() {
    log "Checking prerequisites..."
    
    if ! command -v az &> /dev/null; then
        error "Azure CLI is not installed. Please install it first:"
        error "  brew install azure-cli  # On macOS"
        error "  Or visit: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
        exit 1
    fi
    
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    success "Prerequisites check passed"
}

# Check Azure login status
check_azure_login() {
    log "Checking Azure login status..."
    
    if ! az account show &> /dev/null; then
        warn "Not logged into Azure. Please log in:"
        az login
    fi
    
    local subscription=$(az account show --query name -o tsv)
    log "Using Azure subscription: $subscription"
}

# Validate environment variables
validate_env() {
    log "Validating environment variables..."
    
    local required_vars=(
        "AZURE_RESOURCE_GROUP"
        "AZURE_REGISTRY_NAME" 
        "AZURE_CONTAINER_INSTANCE_NAME"
        "AZURE_CONTAINER_INSTANCE_DNS_LABEL"
        "POSTGRES_HOST"
        "POSTGRES_USER"
        "POSTGRES_PASSWORD"
        "POSTGRES_DB"
        "SECRET_KEY"
        "MASTER_USERNAME"
        "MASTER_PASSWORD"
    )
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            error "Required environment variable $var is not set"
            error "Please check your .env file"
            exit 1
        fi
    done
    
    success "Environment variables validated"
}

# Create Azure resources
create_azure_resources() {
    log "Creating Azure resources..."
    
    # Create resource group if it doesn't exist
    if ! az group show --name "$AZURE_RESOURCE_GROUP" &> /dev/null; then
        log "Creating resource group: $AZURE_RESOURCE_GROUP"
        az group create \
            --name "$AZURE_RESOURCE_GROUP" \
            --location "${AZURE_LOCATION:-eastus}"
    else
        log "Resource group $AZURE_RESOURCE_GROUP already exists"
    fi
    
    # Create container registry if it doesn't exist
    if ! az acr show --name "$AZURE_REGISTRY_NAME" &> /dev/null; then
        log "Creating container registry: $AZURE_REGISTRY_NAME"
        az acr create \
            --resource-group "$AZURE_RESOURCE_GROUP" \
            --name "$AZURE_REGISTRY_NAME" \
            --sku Basic \
            --admin-enabled true
    else
        log "Container registry $AZURE_REGISTRY_NAME already exists"
    fi
    
    success "Azure resources created/verified"
}

# Build and push Docker image
build_and_push() {
    log "Building and pushing Docker image..."
    
    # Get registry login server
    local registry_server=$(az acr show --name "$AZURE_REGISTRY_NAME" --query loginServer -o tsv)
    
    # Login to container registry
    az acr login --name "$AZURE_REGISTRY_NAME"
    
    # Build image
    local image_tag="$registry_server/architecture-decisions:latest"
    log "Building Docker image: $image_tag"
    
    docker build -f Dockerfile.production -t "$image_tag" .
    
    # Push image
    log "Pushing image to registry..."
    docker push "$image_tag"
    
    success "Docker image built and pushed: $image_tag"
}

# Deploy to Container Instances
deploy_container() {
    log "Deploying to Azure Container Instances..."
    
    # Get registry credentials
    local registry_server=$(az acr show --name "$AZURE_REGISTRY_NAME" --query loginServer -o tsv)
    local registry_username=$(az acr credential show --name "$AZURE_REGISTRY_NAME" --query username -o tsv)
    local registry_password=$(az acr credential show --name "$AZURE_REGISTRY_NAME" --query passwords[0].value -o tsv)
    
    # Deploy using ARM template
    az deployment group create \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        --template-file azure-deploy.json \
        --parameters \
            containerName="$AZURE_CONTAINER_INSTANCE_NAME" \
            dnsNameLabel="$AZURE_CONTAINER_INSTANCE_DNS_LABEL" \
            registryLoginServer="$registry_server" \
            registryUsername="$registry_username" \
            registryPassword="$registry_password" \
            imageName="architecture-decisions:latest" \
            postgresHost="$POSTGRES_HOST" \
            postgresUser="$POSTGRES_USER" \
            postgresPassword="$POSTGRES_PASSWORD" \
            postgresDb="$POSTGRES_DB" \
            secretKey="$SECRET_KEY" \
            masterUsername="$MASTER_USERNAME" \
            masterPassword="$MASTER_PASSWORD"
    
    success "Container deployed successfully"
}

# Get deployment info
show_deployment_info() {
    log "Getting deployment information..."
    
    local fqdn=$(az container show \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        --name "$AZURE_CONTAINER_INSTANCE_NAME" \
        --query ipAddress.fqdn -o tsv)
    
    local ip=$(az container show \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        --name "$AZURE_CONTAINER_INSTANCE_NAME" \
        --query ipAddress.ip -o tsv)
    
    echo
    success "🚀 Deployment completed successfully!"
    echo
    echo "Application URL: http://$fqdn:8000"
    echo "IP Address: $ip"
    echo "Resource Group: $AZURE_RESOURCE_GROUP"
    echo "Container Instance: $AZURE_CONTAINER_INSTANCE_NAME"
    echo
    log "You can monitor the container with:"
    echo "  az container logs --resource-group $AZURE_RESOURCE_GROUP --name $AZURE_CONTAINER_INSTANCE_NAME"
}

# Main deployment function
main() {
    log "Starting Azure Container Instances deployment..."
    
    check_prerequisites
    check_azure_login
    validate_env
    create_azure_resources
    build_and_push
    deploy_container
    show_deployment_info
    
    success "🎉 Deployment pipeline completed!"
}

# Script options
case "${1:-deploy}" in
    "deploy")
        main
        ;;
    "build")
        check_prerequisites
        validate_env
        build_and_push
        ;;
    "update")
        check_prerequisites
        check_azure_login
        validate_env
        build_and_push
        deploy_container
        show_deployment_info
        ;;
    "logs")
        az container logs --resource-group "$AZURE_RESOURCE_GROUP" --name "$AZURE_CONTAINER_INSTANCE_NAME" --follow
        ;;
    "status")
        az container show --resource-group "$AZURE_RESOURCE_GROUP" --name "$AZURE_CONTAINER_INSTANCE_NAME" --query instanceView.state -o tsv
        ;;
    "delete")
        read -p "Are you sure you want to delete the container instance? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            az container delete --resource-group "$AZURE_RESOURCE_GROUP" --name "$AZURE_CONTAINER_INSTANCE_NAME" --yes
        fi
        ;;
    *)
        echo "Usage: $0 {deploy|build|update|logs|status|delete}"
        echo
        echo "Commands:"
        echo "  deploy - Full deployment (create resources, build, push, deploy)"
        echo "  build  - Build and push Docker image only"
        echo "  update - Rebuild and redeploy existing container"
        echo "  logs   - Show container logs"
        echo "  status - Show container status"
        echo "  delete - Delete the container instance"
        exit 1
        ;;
esac