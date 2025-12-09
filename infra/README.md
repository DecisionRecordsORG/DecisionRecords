# Infrastructure Templates

This folder contains Azure Resource Manager (ARM) templates for deploying the Architecture Decisions application infrastructure.

**Production URL**: https://architecture-decisions.org

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
- Certificate: `~/.ssh/architecture-decisions.pem`
- Private Key: `~/.ssh/architecture-decisions.key`

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
- Managed Identity for DNS updates (no stored credentials)