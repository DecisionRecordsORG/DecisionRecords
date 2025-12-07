#!/bin/bash
# Startup script for Azure Container Instance
# Updates Private DNS record with container's IP address

set -e

# Configuration
SUBSCRIPTION_ID="36372322-9b59-491a-a273-31fcb1efad85"
RESOURCE_GROUP="adr-resources-eu"
DNS_ZONE="adr.internal"
RECORD_NAME="app"

echo "Starting DNS registration..."

# Get access token using Managed Identity
echo "Getting access token from Managed Identity..."
TOKEN_RESPONSE=$(curl -s -H "Metadata: true" \
  "http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https://management.azure.com/")

ACCESS_TOKEN=$(echo $TOKEN_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))")

if [ -z "$ACCESS_TOKEN" ]; then
  echo "Warning: Could not get access token. DNS update skipped."
  echo "Response: $TOKEN_RESPONSE"
else
  # Get container's private IP
  CONTAINER_IP=$(hostname -I | awk '{print $1}')
  echo "Container IP: $CONTAINER_IP"

  # Update the A record
  echo "Updating DNS record $RECORD_NAME.$DNS_ZONE -> $CONTAINER_IP"

  DNS_UPDATE_RESPONSE=$(curl -s -X PUT \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
      \"properties\": {
        \"ttl\": 60,
        \"aRecords\": [{\"ipv4Address\": \"$CONTAINER_IP\"}]
      }
    }" \
    "https://management.azure.com/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Network/privateDnsZones/$DNS_ZONE/A/$RECORD_NAME?api-version=2018-09-01")

  if echo "$DNS_UPDATE_RESPONSE" | grep -q "error"; then
    echo "Warning: DNS update may have failed: $DNS_UPDATE_RESPONSE"
  else
    echo "DNS record updated successfully"
  fi
fi

echo "Starting application..."
exec gunicorn --bind 0.0.0.0:8000 --workers 2 --worker-class gthread --threads 4 --timeout 60 --keep-alive 2 app:app
