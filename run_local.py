#!/usr/bin/env python3
"""Run the Flask app locally for development."""
import os
from pathlib import Path

# Get the absolute path to the project root
project_root = Path(__file__).parent.absolute()

# IMPORTANT: Disable Azure Key Vault for local development
# This prevents the app from fetching secrets from prod keyvault
# (which can happen if you're logged into Azure CLI)
os.environ['AZURE_KEYVAULT_URL'] = ''

# Set environment variables for local development
os.environ['DATABASE_URL'] = f'sqlite:///{project_root}/instance/architecture_decisions.db'
os.environ['SECRET_KEY'] = 'local-dev-secret-key-12345'
os.environ['ENVIRONMENT'] = 'development'
os.environ['DEBUG'] = 'true'
os.environ['SKIP_CLOUDFLARE_CHECK'] = 'true'  # Disable Cloudflare origin check for local dev
os.environ['COMMERCIAL_FEATURES_ENABLED'] = 'true'  # Enable Slack/Teams integrations

# Microsoft Teams Integration (for local testing with ngrok)
# Credentials are stored in local_secrets.py (gitignored)
# Run ./scripts/deploy-teams-bot.sh --local to create them
try:
    from local_secrets import TEAMS_BOT_APP_ID, TEAMS_BOT_APP_SECRET, TEAMS_BOT_TENANT_ID
    os.environ['TEAMS_BOT_APP_ID'] = TEAMS_BOT_APP_ID
    os.environ['TEAMS_BOT_APP_SECRET'] = TEAMS_BOT_APP_SECRET
    os.environ['TEAMS_BOT_TENANT_ID'] = TEAMS_BOT_TENANT_ID
    print("Teams credentials loaded from local_secrets.py")
except ImportError:
    print("Teams credentials not found (local_secrets.py missing) - Teams integration disabled")

# Import and run the app
from app import app

if __name__ == '__main__':
    print(f"Database: {os.environ['DATABASE_URL']}")
    print(f"Key Vault: DISABLED (using local SECRET_KEY)")
    print("Starting Flask development server on http://localhost:5001")
    print("NOTE: Access via http://localhost:4200 (Angular) for session cookies to work")
    # use_reloader=False prevents Flask from spawning a child process
    # which would lose our environment variable settings
    app.run(debug=True, host='0.0.0.0', port=5001, use_reloader=False)
