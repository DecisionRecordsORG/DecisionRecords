# Deployment Scripts and Configuration

This folder contains deployment scripts, Docker configurations, and documentation for the Architecture Decisions application.

## Files

### `Dockerfile.production`
**Production Docker image** with optimized multi-stage build:
- **Stage 1**: Node.js build environment for Angular frontend
- **Stage 2**: Python runtime with application code
- Features: 
  - Non-root user for security
  - Health checks for container monitoring
  - Optimized for Azure Container Instances
  - x86_64 architecture compatibility

**Build:**
```bash
docker build --platform linux/amd64 -t your-registry/app:latest -f Dockerfile.production .
```

### `deploy.sh`
Automated deployment script for Azure Container Instances:
- Builds and pushes Docker image to Azure Container Registry
- Deploys infrastructure using ARM templates
- Configures environment variables
- Sets up monitoring and logging

**Usage:**
```bash
./deploy.sh
```

### `azure-deploy.yml`
GitHub Actions / Azure DevOps pipeline configuration:
- Automated CI/CD pipeline
- Builds Docker image on code changes
- Deploys to Azure Container Instances
- Environment-based deployments (dev/staging/prod)

### `Dockerfile.azure`
Alternative Docker configuration optimized for Azure:
- Simplified build process
- Azure-specific optimizations
- Basic health checks

### `DEPLOYMENT.md`
Comprehensive deployment documentation:
- Step-by-step deployment guide
- Prerequisites and requirements
- Troubleshooting common issues
- Environment configuration
- Security best practices

## Quick Start

1. **Prerequisites:**
   ```bash
   # Install Azure CLI
   az login
   az account set --subscription "your-subscription-id"
   ```

2. **Deploy:**
   ```bash
   # Make script executable
   chmod +x deploy.sh
   
   # Run deployment
   ./deploy.sh
   ```

3. **Verify:**
   ```bash
   # Check application health
   curl http://your-app-gateway-ip/health
   ```

## Environment Variables

The deployment scripts support these environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `RESOURCE_GROUP` | Azure resource group | `adr-resources-eu` |
| `LOCATION` | Azure region | `westeurope` |
| `ACR_NAME` | Container registry name | `adrregistry2024eu` |
| `APP_NAME` | Application name | `adr-app-eu` |

## Docker Image Variants

- **`Dockerfile.production`**: Full production image with Angular frontend
- **`Dockerfile.azure`**: Simplified Azure-optimized image
- Both support ARM64 and x86_64 architectures

## Health Monitoring

The application includes multiple health check endpoints:
- `/health` - Detailed application and database status
- `/ping` - Simple load balancer health check
- Container-level health checks for Azure monitoring