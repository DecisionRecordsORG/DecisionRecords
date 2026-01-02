#!/bin/bash
# Deploy Microsoft Teams Bot infrastructure for Decision Records
#
# This script:
# 1. Creates an Azure AD App Registration (single-tenant)
# 2. Generates a client secret
# 3. Deploys the Azure Bot Service using ARM template
# 4. Stores credentials in Key Vault
# 5. Updates the Teams app manifest
#
# Prerequisites:
# - Azure CLI installed and logged in (az login)
# - Permissions to create App Registrations in Azure AD
# - Access to the resource group and Key Vault
#
# Usage: ./scripts/deploy-teams-bot.sh [OPTIONS]
#
# Options:
#   --skip-app-registration  Use existing App Registration (prompts for credentials)
#   --endpoint URL           Custom messaging endpoint (for local testing with ngrok)
#   --local                  Shortcut for local testing mode (prompts for ngrok URL)
#   --output-env             Output credentials as environment variables (for run_local.py)
#
# Examples:
#   # Production deployment
#   ./scripts/deploy-teams-bot.sh
#
#   # Local testing with ngrok
#   ./scripts/deploy-teams-bot.sh --local
#
#   # Custom endpoint
#   ./scripts/deploy-teams-bot.sh --endpoint https://abc123.ngrok.io/api/teams/webhook

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
RESOURCE_GROUP="adr-resources-eu"
KEY_VAULT_NAME="adr-keyvault-eu"
BOT_NAME="adr-teams-bot"
BOT_DISPLAY_NAME="Decision Records"
MESSAGING_ENDPOINT="https://decisionrecords.org/api/teams/webhook"
APP_DISPLAY_NAME="Decision Records Teams Bot"

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TEMPLATE_FILE="$PROJECT_ROOT/infra/teams-bot-template.json"
MANIFEST_FILE="$PROJECT_ROOT/teams-app-manifest.json"

# Parse arguments
SKIP_APP_REGISTRATION=false
LOCAL_MODE=false
OUTPUT_ENV=false
CUSTOM_ENDPOINT=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-app-registration)
            SKIP_APP_REGISTRATION=true
            shift
            ;;
        --endpoint)
            CUSTOM_ENDPOINT="$2"
            shift 2
            ;;
        --local)
            LOCAL_MODE=true
            shift
            ;;
        --output-env)
            OUTPUT_ENV=true
            shift
            ;;
        --help|-h)
            echo "Usage: ./scripts/deploy-teams-bot.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --skip-app-registration  Use existing App Registration"
            echo "  --endpoint URL           Custom messaging endpoint (for ngrok)"
            echo "  --local                  Local testing mode (prompts for ngrok URL)"
            echo "  --output-env             Output credentials as env vars"
            echo "  --help                   Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Handle local mode
if [[ "$LOCAL_MODE" == "true" ]]; then
    echo -e "${YELLOW}Local Testing Mode${NC}"
    echo ""
    echo "To test Teams integration locally, you need ngrok running."
    echo "Start ngrok with: ngrok http 5001"
    echo ""
    read -p "Enter your ngrok URL (e.g., https://abc123.ngrok.io): " NGROK_URL
    NGROK_URL="${NGROK_URL%/}"  # Remove trailing slash
    CUSTOM_ENDPOINT="${NGROK_URL}/api/teams/webhook"
    echo ""
    echo -e "${GREEN}Using endpoint: ${CUSTOM_ENDPOINT}${NC}"
fi

# Apply custom endpoint if provided
if [[ -n "$CUSTOM_ENDPOINT" ]]; then
    MESSAGING_ENDPOINT="$CUSTOM_ENDPOINT"
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Teams Bot Deployment Script${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check prerequisites
check_prerequisites() {
    echo -e "${YELLOW}[1/6]${NC} Checking prerequisites..."

    # Check Azure CLI
    if ! command -v az &> /dev/null; then
        echo -e "${RED}[ERROR]${NC} Azure CLI not found. Please install it first."
        exit 1
    fi

    # Check logged in
    if ! az account show &> /dev/null; then
        echo -e "${RED}[ERROR]${NC} Not logged into Azure. Run 'az login' first."
        exit 1
    fi

    # Check template file exists
    if [[ ! -f "$TEMPLATE_FILE" ]]; then
        echo -e "${RED}[ERROR]${NC} ARM template not found: $TEMPLATE_FILE"
        exit 1
    fi

    # Get current subscription
    SUBSCRIPTION=$(az account show --query name -o tsv)
    TENANT_ID=$(az account show --query tenantId -o tsv)
    echo -e "${GREEN}[OK]${NC} Logged into Azure"
    echo "     Subscription: $SUBSCRIPTION"
    echo "     Tenant ID: $TENANT_ID"
}

# Create Azure AD App Registration
create_app_registration() {
    echo ""
    echo -e "${YELLOW}[2/6]${NC} Creating Azure AD App Registration..."

    if [[ "$SKIP_APP_REGISTRATION" == "true" ]]; then
        echo "Skipping app registration creation (--skip-app-registration flag)"
        echo ""
        read -p "Enter existing App ID (client ID): " APP_ID
        read -p "Enter Azure AD Tenant ID: " APP_TENANT_ID
        read -s -p "Enter App Secret: " APP_SECRET
        echo ""
        return
    fi

    # Check if app already exists
    EXISTING_APP=$(az ad app list --display-name "$APP_DISPLAY_NAME" --query "[0].appId" -o tsv 2>/dev/null || echo "")

    if [[ -n "$EXISTING_APP" && "$EXISTING_APP" != "None" ]]; then
        echo -e "${YELLOW}[WARN]${NC} App Registration '$APP_DISPLAY_NAME' already exists"
        read -p "Use existing app? (y/n): " USE_EXISTING
        if [[ "$USE_EXISTING" == "y" || "$USE_EXISTING" == "Y" ]]; then
            APP_ID="$EXISTING_APP"
            APP_TENANT_ID="$TENANT_ID"
            echo "Creating new client secret for existing app..."
            APP_SECRET=$(az ad app credential reset --id "$APP_ID" --display-name "Teams Bot Secret" --years 2 --query password -o tsv)
            echo -e "${GREEN}[OK]${NC} Using existing App Registration: $APP_ID"
            return
        fi
    fi

    # Create new app registration
    echo "Creating new App Registration: $APP_DISPLAY_NAME"

    # Create the app with required settings for Bot Framework
    APP_ID=$(az ad app create \
        --display-name "$APP_DISPLAY_NAME" \
        --sign-in-audience "AzureADMyOrg" \
        --web-redirect-uris \
            "https://decisionrecords.org/api/teams/oauth/callback" \
            "https://decisionrecords.org/auth/teams/oidc/callback" \
            "https://token.botframework.com/.auth/web/redirect" \
        --query appId -o tsv)

    APP_TENANT_ID="$TENANT_ID"

    echo -e "${GREEN}[OK]${NC} Created App Registration: $APP_ID"

    # Create client secret
    echo "Creating client secret..."
    APP_SECRET=$(az ad app credential reset --id "$APP_ID" --display-name "Teams Bot Secret" --years 2 --query password -o tsv)

    echo -e "${GREEN}[OK]${NC} Created client secret (valid for 2 years)"

    # Add API permissions (User.Read for OIDC)
    echo "Adding API permissions..."
    az ad app permission add \
        --id "$APP_ID" \
        --api 00000003-0000-0000-c000-000000000000 \
        --api-permissions e1fe6dd8-ba31-4d61-89e7-88639da4683d=Scope \
        2>/dev/null || echo "Permission may already exist"

    echo -e "${GREEN}[OK]${NC} Added User.Read permission"
}

# Deploy ARM template
deploy_bot_infrastructure() {
    echo ""
    echo -e "${YELLOW}[3/6]${NC} Deploying Azure Bot infrastructure..."

    # Check if bot already exists
    EXISTING_BOT=$(az bot show --name "$BOT_NAME" --resource-group "$RESOURCE_GROUP" --query name -o tsv 2>/dev/null || echo "")

    if [[ -n "$EXISTING_BOT" ]]; then
        echo -e "${YELLOW}[WARN]${NC} Bot '$BOT_NAME' already exists"
        read -p "Update existing bot? (y/n): " UPDATE_BOT
        if [[ "$UPDATE_BOT" != "y" && "$UPDATE_BOT" != "Y" ]]; then
            echo "Skipping bot deployment"
            return
        fi
    fi

    # Deploy using ARM template
    echo "Deploying ARM template..."
    az deployment group create \
        --resource-group "$RESOURCE_GROUP" \
        --template-file "$TEMPLATE_FILE" \
        --parameters \
            botName="$BOT_NAME" \
            botDisplayName="$BOT_DISPLAY_NAME" \
            appId="$APP_ID" \
            appTenantId="$APP_TENANT_ID" \
            botAppSecret="$APP_SECRET" \
            messagingEndpoint="$MESSAGING_ENDPOINT" \
            keyVaultName="$KEY_VAULT_NAME" \
        --output none

    echo -e "${GREEN}[OK]${NC} Deployed Azure Bot: $BOT_NAME"
}

# Verify Key Vault secrets
verify_secrets() {
    echo ""
    echo -e "${YELLOW}[4/6]${NC} Verifying Key Vault secrets..."

    # Check each secret
    for SECRET_NAME in "teams-bot-app-id" "teams-bot-app-secret" "teams-bot-tenant-id"; do
        SECRET_VALUE=$(az keyvault secret show --vault-name "$KEY_VAULT_NAME" --name "$SECRET_NAME" --query value -o tsv 2>/dev/null || echo "")
        if [[ -n "$SECRET_VALUE" ]]; then
            echo -e "${GREEN}[OK]${NC} $SECRET_NAME is set"
        else
            echo -e "${RED}[ERROR]${NC} $SECRET_NAME is missing"
        fi
    done
}

# Update Teams app manifest
update_manifest() {
    echo ""
    echo -e "${YELLOW}[5/6]${NC} Updating Teams app manifest..."

    if [[ ! -f "$MANIFEST_FILE" ]]; then
        echo -e "${YELLOW}[WARN]${NC} Manifest file not found: $MANIFEST_FILE"
        echo "Skipping manifest update"
        return
    fi

    # Check if manifest has placeholder
    if grep -q "{{BOT_APP_ID}}" "$MANIFEST_FILE"; then
        echo "Replacing {{BOT_APP_ID}} with $APP_ID..."
        sed -i.bak "s/{{BOT_APP_ID}}/$APP_ID/g" "$MANIFEST_FILE"
        rm -f "$MANIFEST_FILE.bak"
        echo -e "${GREEN}[OK]${NC} Updated manifest with App ID"
    else
        echo "Manifest already has App ID configured"
    fi
}

# Print summary
print_summary() {
    echo ""
    echo -e "${YELLOW}[6/6]${NC} Deployment Summary"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    echo "Azure Bot Service:"
    echo "  Name: $BOT_NAME"
    echo "  Display Name: $BOT_DISPLAY_NAME"
    echo "  Messaging Endpoint: $MESSAGING_ENDPOINT"
    echo ""
    echo "Azure AD App Registration:"
    echo "  App ID: $APP_ID"
    echo "  Tenant ID: $APP_TENANT_ID"
    echo ""
    echo "Key Vault Secrets (in $KEY_VAULT_NAME):"
    echo "  teams-bot-app-id"
    echo "  teams-bot-app-secret"
    echo "  teams-bot-tenant-id"
    echo ""

    # Output environment variables for local testing
    if [[ "$OUTPUT_ENV" == "true" || "$LOCAL_MODE" == "true" ]]; then
        echo -e "${YELLOW}========================================${NC}"
        echo -e "${YELLOW}  Environment Variables for run_local.py${NC}"
        echo -e "${YELLOW}========================================${NC}"
        echo ""
        echo "Add these to your run_local.py file:"
        echo ""
        echo "os.environ['TEAMS_BOT_APP_ID'] = '$APP_ID'"
        echo "os.environ['TEAMS_BOT_APP_SECRET'] = '$APP_SECRET'"
        echo "os.environ['TEAMS_BOT_TENANT_ID'] = '$APP_TENANT_ID'"
        echo ""
        echo "Or export them in your shell:"
        echo ""
        echo "export TEAMS_BOT_APP_ID='$APP_ID'"
        echo "export TEAMS_BOT_APP_SECRET='$APP_SECRET'"
        echo "export TEAMS_BOT_TENANT_ID='$APP_TENANT_ID'"
        echo ""
    fi

    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Teams Bot deployment complete!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""

    if [[ "$LOCAL_MODE" == "true" ]]; then
        echo "Next steps for local testing:"
        echo ""
        echo "1. Add the environment variables above to run_local.py"
        echo ""
        echo "2. Make sure ngrok is still running on port 5001"
        echo ""
        echo "3. Start your local server:"
        echo "   python run_local.py"
        echo ""
        echo "4. Test the bot in Teams (you may need to sideload the app)"
        echo ""
        echo -e "${YELLOW}Note: The ngrok URL changes each session. You'll need to${NC}"
        echo -e "${YELLOW}update the bot's messaging endpoint when you restart ngrok:${NC}"
        echo "   az bot update --name $BOT_NAME --resource-group $RESOURCE_GROUP \\"
        echo "     --endpoint 'https://NEW-URL.ngrok.io/api/teams/webhook'"
    else
        echo "Next steps:"
        echo "1. Redeploy the application to pick up new secrets:"
        echo "   ./scripts/redeploy.sh patch"
        echo ""
        echo "2. Create Teams app package:"
        echo "   cd $PROJECT_ROOT"
        echo "   zip teams-app.zip teams-app-manifest.json frontend/src/assets/icon-*.png"
        echo ""
        echo "3. Upload to Teams Admin Center or sideload for testing"
        echo ""
        echo "4. Test the integration at:"
        echo "   https://decisionrecords.org/settings (Teams tab)"
    fi
}

# Main execution
main() {
    check_prerequisites
    create_app_registration
    deploy_bot_infrastructure
    verify_secrets
    update_manifest
    print_summary
}

main "$@"
