# Infrastructure Templates

This folder contains Azure Resource Manager (ARM) templates for deploying the Architecture Decisions application infrastructure.

## Files

### `azure-deploy-vnet.json`
**Primary deployment template** - Deploys the application with private networking:
- Azure Container Instance with VNet integration
- Private IP addressing (10.0.1.0/24 subnet)
- Log Analytics integration for container monitoring
- Environment variables for database and application configuration

**Usage:**
```bash
az deployment group create \
  --resource-group adr-resources-eu \
  --template-file azure-deploy-vnet.json \
  --parameters containerName="adr-app-eu" \
               registryLoginServer="yourregistry.azurecr.io" \
               registryUsername="yourregistry" \
               registryPassword="password" \
               postgresHost="your-postgres.postgres.database.azure.com" \
               postgresUser="dbuser" \
               postgresPassword="dbpassword" \
               secretKey="your-secret-key" \
               masterUsername="admin" \
               masterPassword="password"
```

### `azure-deploy.json`
Basic deployment template without VNet integration (for testing):
- Azure Container Instance with public IP
- Simplified networking configuration
- Basic environment variables

### `appgateway-template.json`
Application Gateway template for production deployments:
- Layer 7 load balancer
- Public IP frontend
- Backend pool configuration
- HTTP settings and health probes

## Prerequisites

Before deploying, ensure you have:
1. Azure Resource Group created
2. Azure Virtual Network with subnets (for VNet deployment)
3. Azure Container Registry with pushed application image
4. Azure PostgreSQL Flexible Server with private endpoint
5. Network Security Groups configured

## Network Architecture

```
Internet → Application Gateway (Public IP) → Container Instance (Private IP 10.0.1.4) → PostgreSQL (Private Endpoint)
```

## Security Features

- Private networking with no public container access
- PostgreSQL accessible only via private endpoint
- Network Security Groups controlling traffic flow
- SSL/TLS encryption for database connections
- Secure value parameters for sensitive data