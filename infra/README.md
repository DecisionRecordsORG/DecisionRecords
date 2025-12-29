# Infrastructure Templates

This folder contains Azure Resource Manager (ARM) templates for deploying the Architecture Decisions application infrastructure.

**Production URL**: https://decisionrecords.org

## Files

### `azure-deploy-vnet.json`
**Primary deployment template** - Deploys the application with private networking:
- Azure Container Instance with VNet integration
- **SystemAssigned Managed Identity** for Key Vault access
- **Automatic RBAC role assignment** for Key Vault Secrets User
- Private IP addressing (10.0.1.0/24 subnet)
- Log Analytics integration for container monitoring
- Environment variables for database and application configuration

**Key Features:**
- Secrets (SECRET_KEY, MASTER_PASSWORD) are retrieved from Azure Key Vault
- The container's managed identity is automatically granted "Key Vault Secrets User" role
- No credentials stored in environment variables for sensitive data

**Usage:**
```bash
# Get the database URL from Key Vault
DATABASE_URL=$(az keyvault secret show --vault-name adr-keyvault-eu --name database-url --query value -o tsv)

# Get registry password
REGISTRY_PASSWORD=$(az acr credential show --name adrregistry2024eu --query "passwords[0].value" -o tsv)

# Get Log Analytics workspace info
WORKSPACE_ID=$(az monitor log-analytics workspace show --resource-group adr-resources-eu --workspace-name adr-logs-workspace --query customerId -o tsv)
WORKSPACE_KEY=$(az monitor log-analytics workspace get-shared-keys --resource-group adr-resources-eu --workspace-name adr-logs-workspace --query primarySharedKey -o tsv)

# Deploy
az deployment group create \
  --resource-group adr-resources-eu \
  --template-file azure-deploy-vnet.json \
  --parameters \
    registryPassword="$REGISTRY_PASSWORD" \
    databaseUrl="$DATABASE_URL" \
    logAnalyticsWorkspaceId="$WORKSPACE_ID" \
    logAnalyticsWorkspaceKey="$WORKSPACE_KEY"
```

**Default Parameters:**
| Parameter | Default Value |
|-----------|---------------|
| containerName | adr-app-eu |
| keyVaultName | adr-keyvault-eu |
| registryLoginServer | adrregistry2024eu.azurecr.io |
| registryUsername | adrregistry2024eu |
| masterUsername | admin |
| virtualNetworkName | adr-vnet |
| subnetName | container-subnet |

**Log Analytics Integration (Optional):**
When `logAnalyticsWorkspaceId` and `logAnalyticsWorkspaceKey` are provided, container logs are automatically forwarded to Azure Log Analytics. Get these values with:
```bash
az monitor log-analytics workspace show --resource-group adr-resources-eu --workspace-name adr-logs-workspace --query customerId -o tsv
az monitor log-analytics workspace get-shared-keys --resource-group adr-resources-eu --workspace-name adr-logs-workspace --query primarySharedKey -o tsv
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
Internet → Cloudflare (HTTPS) → Application Gateway (HTTPS:443) → Container Instance (HTTP:8000) → PostgreSQL (Private Endpoint)
                                                    ↓
                                          app.adr.internal (Private DNS)
```

### SSL/TLS Configuration

The application uses Cloudflare for edge SSL with Origin Server certificates:

1. **Edge SSL**: Cloudflare terminates public HTTPS connections
2. **Origin SSL**: Application Gateway has Cloudflare Origin certificate for Cloudflare → Origin encryption
3. **SSL Mode**: Cloudflare SSL/TLS mode set to "Full (strict)"

**Origin Certificate Files** (stored locally, not in repo):
- Certificate: `~/.ssh/decisionrecords.pem`
- Private Key: `~/.ssh/decisionrecords.key`

### Private DNS Auto-Registration

Azure Container Instances in a VNet don't have static private IPs - the IP can change on restart. To handle this automatically:

1. **Private DNS Zone**: `adr.internal` linked to the VNet
2. **A Record**: `app.adr.internal` points to the container's current IP
3. **Startup Script**: Container updates the DNS record on every start using Managed Identity
4. **Application Gateway**: Uses FQDN (`app.adr.internal`) instead of hardcoded IP

**How it works:**

```
Container Start → startup.sh → Get IP → Update DNS A Record → App Gateway resolves new IP
```

The container's Managed Identity has "Private DNS Zone Contributor" role on the `adr.internal` zone.

**Azure Resources:**
| Resource | Name | Purpose |
|----------|------|---------|
| Private DNS Zone | `adr.internal` | Internal DNS resolution |
| VNet Link | `adr-vnet-link` | Links DNS zone to VNet |
| A Record | `app.adr.internal` | Points to container IP |

**Verify DNS is working:**
```bash
# Check DNS record
az network private-dns record-set a show \
  --resource-group adr-resources-eu \
  --zone-name "adr.internal" \
  --name "app"

# Check Application Gateway backend health
az network application-gateway show-backend-health \
  --name adr-appgateway \
  --resource-group adr-resources-eu \
  --query "backendAddressPools[0].backendHttpSettingsCollection[0].servers[0]"
```

## Security Features

- Private networking with no public container access
- PostgreSQL accessible only via private endpoint
- Network Security Groups controlling traffic flow
- SSL/TLS encryption for database connections
- Secure value parameters for sensitive data
- **SystemAssigned Managed Identity** for Key Vault and DNS access (no stored credentials)
- **Key Vault Secrets User** role automatically assigned to container identity
- Secrets (SECRET_KEY, MASTER_PASSWORD, API keys) retrieved from Key Vault at runtime

### Key Vault Integration

The container uses Azure Managed Identity to access secrets from Key Vault:

| Secret | Purpose |
|--------|---------|
| `flask-secret-key` | Flask session signing (persistent across restarts) |
| `smtp-username` | Email SMTP authentication |
| `smtp-password` | Email SMTP authentication |
| `posthog-api-key` | Analytics API key |

The ARM template automatically:
1. Creates a SystemAssigned managed identity for the container
2. Assigns "Key Vault Secrets User" role to the identity on the Key Vault
3. Sets `AZURE_KEYVAULT_URL` environment variable for the application