# Azure Deployment Guide

This guide explains how to deploy the Architecture Decisions application to Azure Container Instances.

## Prerequisites

1. **Azure Account**: Sign up at [portal.azure.com](https://portal.azure.com)
2. **Azure CLI**: Install from [docs.microsoft.com/cli/azure](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli)
3. **Docker**: Install from [docker.com](https://www.docker.com)
4. **PostgreSQL Database**: Azure Database for PostgreSQL or existing database

## Quick Start

1. **Configure Environment Variables**
   ```bash
   cp .env.example .env
   # Edit .env with your Azure and database credentials
   ```

2. **Login to Azure**
   ```bash
   az login
   ```

3. **Run Deployment**
   ```bash
   ./deploy.sh deploy
   ```

## Configuration

### Required Environment Variables

Edit `.env` file with the following:

#### Azure Configuration
- `AZURE_RESOURCE_GROUP` - Resource group name (e.g., "adr-resources")
- `AZURE_REGISTRY_NAME` - Container registry name (e.g., "adrregistry")
- `AZURE_CONTAINER_INSTANCE_NAME` - Container instance name (e.g., "adr-app")
- `AZURE_CONTAINER_INSTANCE_DNS_LABEL` - DNS label (e.g., "mycompany-adr")
- `AZURE_LOCATION` - Azure region (default: "eastus")

#### Database Configuration
- `POSTGRES_HOST` - PostgreSQL server hostname
- `POSTGRES_PORT` - PostgreSQL port (default: 5432)
- `POSTGRES_DB` - Database name (default: "architecture_decisions")
- `POSTGRES_USER` - Database username
- `POSTGRES_PASSWORD` - Database password

#### Application Configuration
- `SECRET_KEY` - Flask secret key (generate with: `python -c "import secrets; print(secrets.token_hex(32))"`)
- `MASTER_USERNAME` - Initial master account username
- `MASTER_PASSWORD` - Initial master account password

## Deployment Commands

### Full Deployment
Deploy everything from scratch:
```bash
./deploy.sh deploy
```

### Build and Push Only
Build Docker image and push to registry:
```bash
./deploy.sh build
```

### Update Existing Deployment
Rebuild and redeploy container:
```bash
./deploy.sh update
```

### View Logs
Stream container logs:
```bash
./deploy.sh logs
```

### Check Status
Get container status:
```bash
./deploy.sh status
```

### Delete Deployment
Remove container instance:
```bash
./deploy.sh delete
```

## Azure Resources Created

The deployment script will create:
1. **Resource Group** - Container for all resources
2. **Container Registry** - Docker image storage
3. **Container Instance** - Running application

## Setting up PostgreSQL

### Option 1: Azure Database for PostgreSQL

1. Create PostgreSQL server:
   ```bash
   az postgres flexible-server create \
     --resource-group $AZURE_RESOURCE_GROUP \
     --name mypostgresserver \
     --location eastus \
     --admin-user $POSTGRES_USER \
     --admin-password $POSTGRES_PASSWORD \
     --sku-name Standard_B1ms \
     --tier Burstable \
     --public-access 0.0.0.0
   ```

2. Create database:
   ```bash
   az postgres flexible-server db create \
     --resource-group $AZURE_RESOURCE_GROUP \
     --server-name mypostgresserver \
     --database-name $POSTGRES_DB
   ```

3. Configure firewall for Azure services:
   ```bash
   az postgres flexible-server firewall-rule create \
     --resource-group $AZURE_RESOURCE_GROUP \
     --name mypostgresserver \
     --rule-name AllowAzureServices \
     --start-ip-address 0.0.0.0 \
     --end-ip-address 0.0.0.0
   ```

### Option 2: External PostgreSQL

Ensure your PostgreSQL server:
- Accepts connections from Azure IP ranges
- Has SSL enabled (recommended)
- Has the database created

## Post-Deployment Steps

1. **Access the Application**
   - URL will be displayed after deployment
   - Format: `http://<dns-label>.<region>.azurecontainer.io:8000`

2. **Login as Master**
   - Navigate to `/superadmin`
   - Use credentials from `.env`

3. **Configure SSO (Optional)**
   - Login as master account
   - Go to System Settings
   - Add SSO provider configuration

4. **Configure Email (Optional)**
   - Login as master account
   - Go to System Settings
   - Add SMTP configuration

## Monitoring

### View Container Logs
```bash
az container logs \
  --resource-group $AZURE_RESOURCE_GROUP \
  --name $AZURE_CONTAINER_INSTANCE_NAME \
  --follow
```

### Check Container Metrics
```bash
az monitor metrics list \
  --resource "Microsoft.ContainerInstance/containerGroups/$AZURE_CONTAINER_INSTANCE_NAME" \
  --resource-group $AZURE_RESOURCE_GROUP \
  --metric CPUUsage \
  --aggregation Average
```

## Troubleshooting

### Container Won't Start
- Check logs: `./deploy.sh logs`
- Verify database connectivity
- Ensure all environment variables are set

### Database Connection Failed
- Verify PostgreSQL firewall rules
- Check connection string format
- Ensure database exists

### Image Push Failed
- Login to registry: `az acr login --name $AZURE_REGISTRY_NAME`
- Check registry exists: `az acr show --name $AZURE_REGISTRY_NAME`

### DNS Not Resolving
- Wait 5-10 minutes after deployment
- Check DNS label is unique
- Verify container is running: `./deploy.sh status`

## Cost Optimization

### Container Instances Pricing
- CPU: ~$0.04/vCPU/hour
- Memory: ~$0.004/GB/hour
- Estimate: ~$30-50/month for basic configuration

### Cost Saving Tips
1. Use spot instances for dev/test
2. Stop container when not in use
3. Right-size CPU/memory allocation
4. Use Azure Database Basic tier for dev

## Security Considerations

1. **Secrets Management**
   - Never commit `.env` file
   - Use Azure Key Vault for production
   - Rotate credentials regularly

2. **Network Security**
   - Consider using Azure Virtual Network
   - Implement Web Application Firewall
   - Use HTTPS with SSL certificate

3. **Database Security**
   - Enable SSL for PostgreSQL
   - Use firewall rules
   - Regular backups

## Production Recommendations

1. **High Availability**
   - Use Azure Application Gateway for load balancing
   - Deploy to multiple regions
   - Set up database replication

2. **Scaling**
   - Consider Azure Kubernetes Service (AKS) for auto-scaling
   - Use Azure CDN for static assets
   - Implement caching with Redis

3. **Monitoring**
   - Enable Application Insights
   - Set up alerts for critical metrics
   - Implement health checks

## Support

For issues or questions:
- Check logs: `./deploy.sh logs`
- Review Azure documentation: [docs.microsoft.com/azure](https://docs.microsoft.com/azure)
- File issues: [GitHub Issues](https://github.com/lawrencepn/architecture-decisions/issues)