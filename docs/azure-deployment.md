# Azure Deployment Guide

This guide provides comprehensive instructions for deploying the Architecture Decisions application to Azure Container Instances.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Infrastructure Components](#infrastructure-components)
- [Deployment Steps](#deployment-steps)
- [Configuration](#configuration)
- [Monitoring & Maintenance](#monitoring--maintenance)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Tools
- Azure CLI (`az`) - [Install Guide](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli)
- Docker Desktop - [Download](https://www.docker.com/products/docker-desktop)
- Git - [Download](https://git-scm.com/downloads)

### Azure Resources
- Active Azure subscription
- Resource group (e.g., `adr-resources-eu`)
- Azure Container Registry
- Azure Database for PostgreSQL
- Azure Key Vault (for secure credentials)

## Infrastructure Components

### Current Production Setup

```yaml
Resource Group: adr-resources-eu
Location: West Europe
Container Instance: adr-app-eu
Container Registry: adrregistry2024eu
PostgreSQL Server: adr-postgres-eu
Key Vault: adr-keyvault-eu
Application Gateway: adr-appgateway
Virtual Network: adr-vnet
```

### Architecture Diagram

```
Internet
    │
    ▼
[Application Gateway] (52.232.79.3)
    │
    ▼
[Virtual Network - adr-vnet]
    │
    ├── [Container Subnet] (10.0.1.0/24)
    │       └── Container Instance (10.0.1.4)
    │
    └── [Gateway Subnet] (10.0.0.0/24)
            └── Application Gateway
```

## Deployment Steps

### 1. Initial Setup

```bash
# Login to Azure
az login

# Set subscription
az account set --subscription "YOUR_SUBSCRIPTION_ID"

# Create resource group
az group create --name adr-resources-eu --location westeurope
```

### 2. Create Container Registry

```bash
# Create ACR
az acr create \
  --resource-group adr-resources-eu \
  --name adrregistry2024eu \
  --sku Basic \
  --location westeurope

# Enable admin user
az acr update --name adrregistry2024eu --admin-enabled true
```

### 3. Setup PostgreSQL Database

```bash
# Create PostgreSQL server
az postgres flexible-server create \
  --resource-group adr-resources-eu \
  --name adr-postgres-eu \
  --location westeurope \
  --admin-user adruser \
  --admin-password "SecurePass123" \
  --sku-name Standard_B1ms \
  --tier Burstable \
  --storage-size 32 \
  --version 13

# Configure firewall for Azure services
az postgres flexible-server firewall-rule create \
  --resource-group adr-resources-eu \
  --name adr-postgres-eu \
  --rule-name AllowAzureServices \
  --start-ip-address 0.0.0.0 \
  --end-ip-address 0.0.0.0
```

### 4. Create Virtual Network

```bash
# Create VNet
az network vnet create \
  --resource-group adr-resources-eu \
  --name adr-vnet \
  --address-prefix 10.0.0.0/16 \
  --subnet-name gateway-subnet \
  --subnet-prefix 10.0.0.0/24

# Add container subnet
az network vnet subnet create \
  --resource-group adr-resources-eu \
  --vnet-name adr-vnet \
  --name container-subnet \
  --address-prefix 10.0.1.0/24 \
  --delegations Microsoft.ContainerInstance/containerGroups
```

### 5. Setup Application Gateway

```bash
# Create public IP
az network public-ip create \
  --resource-group adr-resources-eu \
  --name adr-appgateway-ip \
  --sku Standard \
  --allocation-method Static

# Create Application Gateway
az network application-gateway create \
  --resource-group adr-resources-eu \
  --name adr-appgateway \
  --location westeurope \
  --vnet-name adr-vnet \
  --subnet gateway-subnet \
  --public-ip-address adr-appgateway-ip \
  --sku Standard_v2 \
  --capacity 1 \
  --http-settings-port 8000 \
  --http-settings-protocol Http \
  --frontend-port 80 \
  --routing-rule-type Basic
```

### 6. Deploy Container Instance

```bash
# Build Docker image
docker build --platform linux/amd64 \
  -t adrregistry2024eu.azurecr.io/architecture-decisions:latest \
  -f deployment/Dockerfile.production .

# Push to registry
az acr login --name adrregistry2024eu
docker push adrregistry2024eu.azurecr.io/architecture-decisions:latest

# Create container instance with managed identity
az container create \
  --resource-group adr-resources-eu \
  --name adr-app-eu \
  --image adrregistry2024eu.azurecr.io/architecture-decisions:latest \
  --registry-login-server adrregistry2024eu.azurecr.io \
  --registry-username $(az acr credential show --name adrregistry2024eu --query username -o tsv) \
  --registry-password $(az acr credential show --name adrregistry2024eu --query passwords[0].value -o tsv) \
  --subnet /subscriptions/YOUR_SUB_ID/resourceGroups/adr-resources-eu/providers/Microsoft.Network/virtualNetworks/adr-vnet/subnets/container-subnet \
  --cpu 0.5 \
  --memory 1.0 \
  --ports 8000 \
  --os-type Linux \
  --assign-identity \
  --environment-variables \
    DATABASE_URL="postgresql://adruser:SecurePass123@adr-postgres-eu.postgres.database.azure.com:5432/postgres?sslmode=require" \
    ENVIRONMENT="production" \
    DEBUG="false"
```

### 7. Configure Application Gateway Backend

```bash
# Update backend pool with container IP
CONTAINER_IP=$(az container show --resource-group adr-resources-eu --name adr-app-eu --query ipAddress.ip -o tsv)

az network application-gateway address-pool update \
  --gateway-name adr-appgateway \
  --resource-group adr-resources-eu \
  --name adr-backend-pool \
  --servers $CONTAINER_IP
```

## Configuration

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:5432/db?sslmode=require` |
| `ENVIRONMENT` | Deployment environment | `production` |
| `DEBUG` | Debug mode flag | `false` |
| `SECRET_KEY` | Flask secret key | (auto-generated) |

### DNS Configuration

For custom domain (e.g., decisionrecords.org):

1. Get Application Gateway public IP:
```bash
az network public-ip show \
  --resource-group adr-resources-eu \
  --name adr-appgateway-ip \
  --query ipAddress -o tsv
```

2. Create DNS A record pointing to the IP address

### SSL/TLS Configuration

To enable HTTPS:

```bash
# Create self-signed certificate (for testing)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout privateKey.key \
  -out appgatewaycert.crt

# Upload certificate to Application Gateway
az network application-gateway ssl-cert create \
  --resource-group adr-resources-eu \
  --gateway-name adr-appgateway \
  --name appgatewaycert \
  --cert-file appgatewaycert.crt \
  --cert-password ""
```

## Monitoring & Maintenance

### View Container Logs

```bash
# Stream logs
az container logs \
  --resource-group adr-resources-eu \
  --name adr-app-eu \
  --follow

# Get last 50 lines
az container logs \
  --resource-group adr-resources-eu \
  --name adr-app-eu \
  --tail 50
```

### Check Container Status

```bash
# Get container details
az container show \
  --resource-group adr-resources-eu \
  --name adr-app-eu \
  --query '{state: instanceView.state, ip: ipAddress.ip}'
```

### Restart Container

```bash
az container restart \
  --resource-group adr-resources-eu \
  --name adr-app-eu
```

### Update Deployment

```bash
# 1. Build new image
docker build --platform linux/amd64 \
  -t adrregistry2024eu.azurecr.io/architecture-decisions:latest \
  -f deployment/Dockerfile.production .

# 2. Push to registry
docker push adrregistry2024eu.azurecr.io/architecture-decisions:latest

# 3. Restart container to pull new image
az container restart \
  --resource-group adr-resources-eu \
  --name adr-app-eu
```

## Troubleshooting

### Container Won't Start

1. Check logs for errors:
```bash
az container logs --resource-group adr-resources-eu --name adr-app-eu
```

2. Verify database connectivity:
```bash
# Test from container
az container exec \
  --resource-group adr-resources-eu \
  --name adr-app-eu \
  --exec-command "nc -zv adr-postgres-eu.postgres.database.azure.com 5432"
```

### Application Gateway Issues

1. Check backend health:
```bash
az network application-gateway show-backend-health \
  --name adr-appgateway \
  --resource-group adr-resources-eu
```

2. Verify backend pool configuration:
```bash
az network application-gateway address-pool show \
  --gateway-name adr-appgateway \
  --resource-group adr-resources-eu \
  --name adr-backend-pool
```

### Database Connection Issues

1. Check firewall rules:
```bash
az postgres flexible-server firewall-rule list \
  --resource-group adr-resources-eu \
  --name adr-postgres-eu
```

2. Verify connection string format:
- Ensure `sslmode=require` is included
- Check username format (just username, not username@server)

### Container IP Changes After Restart

The container gets a new IP after restart. Update Application Gateway:

```bash
# Get new IP
NEW_IP=$(az container show --resource-group adr-resources-eu --name adr-app-eu --query ipAddress.ip -o tsv)

# Update backend pool
az network application-gateway address-pool update \
  --gateway-name adr-appgateway \
  --resource-group adr-resources-eu \
  --name adr-backend-pool \
  --servers $NEW_IP
```

## Cost Optimization

### Estimated Monthly Costs (EUR)
- Container Instance (0.5 vCPU, 1GB): ~€15
- PostgreSQL (B1ms): ~€12
- Application Gateway: ~€15
- Storage & Network: ~€5
- **Total**: ~€47/month

### Cost Saving Tips
1. Use spot instances for dev/test environments
2. Stop containers during non-business hours
3. Right-size container resources based on actual usage
4. Use Azure Database Basic tier for development

## Security Best Practices

1. **Never commit secrets** - Use Azure Key Vault
2. **Enable firewall rules** - Restrict database access
3. **Use managed identities** - Avoid storing credentials
4. **Regular updates** - Keep dependencies current
5. **Monitor logs** - Set up alerts for anomalies

## Backup and Recovery

### Database Backup

```bash
# Manual backup
az postgres flexible-server backup create \
  --resource-group adr-resources-eu \
  --name adr-postgres-eu \
  --backup-name manual-backup-$(date +%Y%m%d)

# List backups
az postgres flexible-server backup list \
  --resource-group adr-resources-eu \
  --name adr-postgres-eu
```

### Container Image Backup

Images are automatically stored in Azure Container Registry with tags for versioning:

```bash
# Tag with version
docker tag adrregistry2024eu.azurecr.io/architecture-decisions:latest \
  adrregistry2024eu.azurecr.io/architecture-decisions:v1.0.0

# Push versioned image
docker push adrregistry2024eu.azurecr.io/architecture-decisions:v1.0.0
```

---

*Last Updated: December 2024*