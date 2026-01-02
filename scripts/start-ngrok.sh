#!/bin/bash
# Start ngrok tunnel for local integration testing
#
# This script:
# 1. Checks if ngrok is installed
# 2. Starts ngrok tunnel to localhost:5001
# 3. Retrieves and displays the public URL
# 4. Optionally updates Azure Bot messaging endpoint
#
# Usage: ./scripts/start-ngrok.sh [OPTIONS]
#
# Options:
#   --update-bot    Update Azure Bot messaging endpoint with ngrok URL
#   --port PORT     Port to tunnel (default: 5001)
#   --background    Run ngrok in background
#   --help          Show this help message
#
# Prerequisites:
#   - ngrok installed (brew install ngrok)
#   - ngrok authenticated (ngrok config add-authtoken YOUR_TOKEN)
#
# Examples:
#   # Start ngrok and display URL
#   ./scripts/start-ngrok.sh
#
#   # Start in background and update Azure Bot
#   ./scripts/start-ngrok.sh --background --update-bot

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
PORT=5001
UPDATE_BOT=false
BACKGROUND=false
BOT_NAME="adr-teams-bot"
RESOURCE_GROUP="adr-resources-eu"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --update-bot)
            UPDATE_BOT=true
            shift
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --background)
            BACKGROUND=true
            shift
            ;;
        --help|-h)
            echo "Usage: ./scripts/start-ngrok.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --update-bot    Update Azure Bot messaging endpoint"
            echo "  --port PORT     Port to tunnel (default: 5001)"
            echo "  --background    Run ngrok in background"
            echo "  --help          Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Check if ngrok is installed
check_ngrok() {
    if ! command -v ngrok &> /dev/null; then
        echo -e "${RED}[ERROR]${NC} ngrok is not installed"
        echo ""
        echo "Install ngrok:"
        echo "  macOS:   brew install ngrok"
        echo "  Linux:   snap install ngrok"
        echo "  Windows: choco install ngrok"
        echo ""
        echo "Then authenticate:"
        echo "  ngrok config add-authtoken YOUR_TOKEN"
        echo ""
        echo "Get your token at: https://dashboard.ngrok.com/get-started/your-authtoken"
        exit 1
    fi
    echo -e "${GREEN}[OK]${NC} ngrok is installed"
}

# Check if ngrok is already running
check_existing_tunnel() {
    if curl -s http://localhost:4040/api/tunnels > /dev/null 2>&1; then
        EXISTING_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"https://[^"]*' | head -1 | cut -d'"' -f4)
        if [[ -n "$EXISTING_URL" ]]; then
            echo -e "${YELLOW}[INFO]${NC} ngrok is already running"
            echo -e "${GREEN}Public URL: ${EXISTING_URL}${NC}"
            NGROK_URL="$EXISTING_URL"
            return 0
        fi
    fi
    return 1
}

# Start ngrok
start_ngrok() {
    echo -e "${BLUE}Starting ngrok tunnel to localhost:${PORT}...${NC}"

    if [[ "$BACKGROUND" == "true" ]]; then
        # Start in background
        ngrok http $PORT --log=stdout > /tmp/ngrok.log 2>&1 &
        NGROK_PID=$!
        echo "ngrok PID: $NGROK_PID"

        # Wait for tunnel to be established
        echo "Waiting for tunnel..."
        for i in {1..10}; do
            sleep 1
            if curl -s http://localhost:4040/api/tunnels > /dev/null 2>&1; then
                break
            fi
        done
    else
        # Start in foreground (will block)
        echo -e "${YELLOW}Starting ngrok in foreground. Press Ctrl+C to stop.${NC}"
        echo ""
        ngrok http $PORT
        exit 0
    fi
}

# Get ngrok URL
get_ngrok_url() {
    NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"https://[^"]*' | head -1 | cut -d'"' -f4)

    if [[ -z "$NGROK_URL" ]]; then
        echo -e "${RED}[ERROR]${NC} Could not retrieve ngrok URL"
        echo "Check ngrok logs: cat /tmp/ngrok.log"
        exit 1
    fi

    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  ngrok tunnel established${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "Public URL: $NGROK_URL"
    echo "Local URL:  http://localhost:$PORT"
    echo ""
    echo "Teams webhook endpoint:"
    echo "  ${NGROK_URL}/api/teams/webhook"
    echo ""
    echo "ngrok dashboard: http://localhost:4040"
}

# Update Azure Bot endpoint
update_bot_endpoint() {
    if [[ "$UPDATE_BOT" != "true" ]]; then
        return
    fi

    echo -e "${BLUE}Updating Azure Bot messaging endpoint...${NC}"

    # Check if logged into Azure
    if ! az account show &> /dev/null; then
        echo -e "${RED}[ERROR]${NC} Not logged into Azure. Run 'az login' first."
        return 1
    fi

    # Check if bot exists
    if ! az bot show --name "$BOT_NAME" --resource-group "$RESOURCE_GROUP" &> /dev/null; then
        echo -e "${YELLOW}[WARN]${NC} Azure Bot '$BOT_NAME' not found"
        echo "Run ./scripts/deploy-teams-bot.sh --local first"
        return 1
    fi

    # Update endpoint
    ENDPOINT="${NGROK_URL}/api/teams/webhook"
    az bot update \
        --name "$BOT_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --endpoint "$ENDPOINT" \
        --output none

    echo -e "${GREEN}[OK]${NC} Updated bot endpoint to: $ENDPOINT"
}

# Print usage instructions
print_instructions() {
    echo ""
    echo -e "${YELLOW}========================================${NC}"
    echo -e "${YELLOW}  Next Steps${NC}"
    echo -e "${YELLOW}========================================${NC}"
    echo ""
    echo "1. Make sure your local server is running:"
    echo "   python run_local.py"
    echo ""
    echo "2. If testing Teams integration:"
    if [[ "$UPDATE_BOT" == "true" ]]; then
        echo "   Bot endpoint has been updated automatically."
    else
        echo "   Update the Azure Bot endpoint:"
        echo "   az bot update --name $BOT_NAME --resource-group $RESOURCE_GROUP \\"
        echo "     --endpoint '${NGROK_URL}/api/teams/webhook'"
    fi
    echo ""
    echo "3. Test your endpoints:"
    echo "   curl ${NGROK_URL}/api/health"
    echo ""
    echo "4. View request logs at: http://localhost:4040"
    echo ""

    # Save URL to file for other scripts to use
    echo "$NGROK_URL" > /tmp/ngrok_url.txt
    echo "ngrok URL saved to /tmp/ngrok_url.txt"
}

# Main
main() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  ngrok Tunnel Setup${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    check_ngrok

    # Check if already running
    if check_existing_tunnel; then
        update_bot_endpoint
        print_instructions
        exit 0
    fi

    start_ngrok
    get_ngrok_url
    update_bot_endpoint
    print_instructions
}

main "$@"
