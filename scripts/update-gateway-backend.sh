#!/bin/bash
# Update Application Gateway backend pool with current container IP
# Run this script after container restart if the IP changes

set -e

RESOURCE_GROUP="adr-resources-eu"
CONTAINER_NAME="adr-app-eu"
GATEWAY_NAME="adr-appgateway"
BACKEND_POOL_NAME="adr-backend-pool"

echo "Getting container IP..."
CONTAINER_IP=$(az container show --name $CONTAINER_NAME --resource-group $RESOURCE_GROUP --query "ipAddress.ip" -o tsv)
echo "Container IP: $CONTAINER_IP"

echo "Getting current backend pool IP..."
BACKEND_IP=$(az network application-gateway address-pool show \
  --gateway-name $GATEWAY_NAME \
  --resource-group $RESOURCE_GROUP \
  --name $BACKEND_POOL_NAME \
  --query "backendAddresses[0].ipAddress" -o tsv)
echo "Backend pool IP: $BACKEND_IP"

if [ "$CONTAINER_IP" == "$BACKEND_IP" ]; then
  echo "IPs match. No update needed."
else
  echo "IPs don't match. Updating backend pool..."
  az network application-gateway address-pool update \
    --gateway-name $GATEWAY_NAME \
    --resource-group $RESOURCE_GROUP \
    --name $BACKEND_POOL_NAME \
    --servers $CONTAINER_IP
  echo "Backend pool updated successfully."
fi

echo "Checking backend health..."
az network application-gateway show-backend-health \
  --name $GATEWAY_NAME \
  --resource-group $RESOURCE_GROUP \
  --query "backendAddressPools[0].backendHttpSettingsCollection[0].servers[0]" -o json
