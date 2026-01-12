# VM Migration Progress (ADR-004)

**Status**: ⏸️ Paused - Waiting for Azure quota increase
**Last Updated**: 2026-01-05
**Decision Record**: ADR-004

## Summary

Migrating from Azure Container Instances (~$40/mo) to Azure B-series VM (~$12/mo) to reduce infrastructure costs.

## Current Blocker

**Azure B-series quota not available in EU regions**

- West Europe: B1s unavailable (capacity restrictions), B2ts_v2 quota = 0
- Sweden Central: Same quota issue
- Quota increase requested - waiting for approval

## Completed Steps

- [x] ARM template created: `infra/azure-deploy-vm.json`
- [x] systemd service file created: `deployment/adr-app.service`
- [x] VM setup script created: `scripts/setup-vm.sh`
- [x] VM deployment script created: `ee/scripts/redeploy-vm.sh`
- [x] Documentation updated: `infra/README.md`
- [x] SSH key generated: `~/.ssh/adr-vm-key`
- [x] All changes committed to git

## Pending Steps

1. **Deploy VM** (waiting for quota)
   ```bash
   az deployment group create \
     --resource-group adr-resources-eu \
     --template-file infra/azure-deploy-vm.json \
     --parameters sshPublicKey="$(cat ~/.ssh/adr-vm-key.pub)"
   ```

2. **Run one-time setup**
   ```bash
   ./scripts/setup-vm.sh 10.0.1.100
   ```

3. **Verify application health**
   ```bash
   curl http://10.0.1.100:8000/api/health
   ```

4. **Update Application Gateway**
   ```bash
   az network application-gateway address-pool update \
     --gateway-name adr-appgateway \
     --resource-group adr-resources-eu \
     --name adr-backend-pool \
     --servers 10.0.1.100
   ```

5. **Verify production traffic** at https://decisionrecords.org

6. **Cleanup** (after 24-48h validation)
   - Stop ACI: `az container stop --name adr-app-eu --resource-group adr-resources-eu`
   - Delete ACI after 1 week of stable VM operation

## VM Configuration (for portal creation if ARM fails)

| Setting | Value |
|---------|-------|
| Name | `adr-vm-eu` |
| Region | Sweden Central (or any EU with quota) |
| Image | Ubuntu Server 22.04 LTS - x64 Gen2 |
| Size | Standard_B2ts_v2 (2 vCPU, 1 GB RAM) |
| Username | `azureuser` |
| SSH Key | `~/.ssh/adr-vm-key.pub` |
| VNet | `adr-vnet` |
| Subnet | `container-subnet` |
| Private IP | Static: `10.0.1.100` |
| Public IP | None |
| Managed Identity | System assigned: **On** |

**Post-creation**: Grant "Key Vault Secrets User" role to VM's managed identity on `adr-keyvault-eu`

## Files Created

| File | Purpose |
|------|---------|
| `infra/azure-deploy-vm.json` | ARM template for VM deployment |
| `deployment/adr-app.service` | systemd service for container |
| `scripts/setup-vm.sh` | One-time VM configuration |
| `ee/scripts/redeploy-vm.sh` | Daily deployment script |

## Rollback Plan

If issues occur after cutover:
```bash
az container start --name adr-app-eu --resource-group adr-resources-eu
# Update gateway back to ACI IP
```

## Resume Instructions

When quota is approved:
1. Re-run ARM deployment or create VM in portal
2. Continue from "Run one-time setup" step above
