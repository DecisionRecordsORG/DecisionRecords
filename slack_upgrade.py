"""
Slack App Upgrade Management.

This module handles tracking Slack app versions and scopes, enabling
graceful upgrades when new features require additional permissions.

Based on patterns from: https://github.com/slack-samples/bolt-js-upgrade-app

Key concepts:
- Slack doesn't notify users about app updates - we must do it ourselves
- Scopes can only be appended to existing tokens, not removed
- Users must re-authorize to grant new scopes
- App Home and slash commands are ideal places to show upgrade prompts
"""
import os
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

# ============================================================================
# APP VERSION CONFIGURATION
# ============================================================================

@dataclass
class SlackAppVersion:
    """Represents a version of the Slack app with its required scopes."""
    version: str
    release_date: str
    scopes: List[str]
    features: List[str]
    changelog: str


# Define app versions with their required scopes
# When adding new features, create a new version entry
APP_VERSIONS = {
    "1.0.0": SlackAppVersion(
        version="1.0.0",
        release_date="2024-12-01",
        scopes=["chat:write", "commands", "users:read", "users:read.email"],
        features=[
            "Slash commands (/adr create, list, view, search)",
            "Channel notifications for new decisions",
            "User auto-linking by email"
        ],
        changelog="Initial release with core decision management features."
    ),
    "1.1.0": SlackAppVersion(
        version="1.1.0",
        release_date="2024-12-17",
        scopes=["chat:write", "commands", "users:read", "users:read.email", "im:write"],
        features=[
            "Slash commands (/adr create, list, view, search)",
            "Channel notifications for new decisions",
            "User auto-linking by email",
            "Direct message confirmations after creating decisions",
            "Owner assignment notifications via DM"
        ],
        changelog="Added DM notifications for decision creation and owner assignments."
    ),
}

# Current version - update this when releasing new versions
CURRENT_APP_VERSION = "1.1.0"

# Scopes required for full functionality
REQUIRED_SCOPES = APP_VERSIONS[CURRENT_APP_VERSION].scopes


# ============================================================================
# SCOPE COMPARISON
# ============================================================================

def get_missing_scopes(installed_scopes: List[str]) -> List[str]:
    """
    Compare installed scopes against required scopes.

    Args:
        installed_scopes: List of scopes the workspace has granted

    Returns:
        List of scopes that are missing (need upgrade)
    """
    return [scope for scope in REQUIRED_SCOPES if scope not in installed_scopes]


def needs_upgrade(installed_scopes: List[str]) -> bool:
    """
    Check if a workspace needs to upgrade their app installation.

    Args:
        installed_scopes: List of scopes the workspace has granted

    Returns:
        True if missing required scopes
    """
    return len(get_missing_scopes(installed_scopes)) > 0


def get_upgrade_info(installed_scopes: List[str]) -> Dict:
    """
    Get detailed information about a needed upgrade.

    Args:
        installed_scopes: List of scopes the workspace has granted

    Returns:
        Dictionary with upgrade details
    """
    missing = get_missing_scopes(installed_scopes)
    current_version = APP_VERSIONS.get(CURRENT_APP_VERSION)

    # Find what version they're effectively running based on scopes
    effective_version = "1.0.0"
    for version_str, version_info in sorted(APP_VERSIONS.items()):
        version_missing = [s for s in version_info.scopes if s not in installed_scopes]
        if not version_missing:
            effective_version = version_str

    # Get features they're missing
    missing_features = []
    if "im:write" in missing:
        missing_features.extend([
            "Direct message confirmations after creating decisions",
            "Owner assignment notifications via DM"
        ])

    return {
        "needs_upgrade": len(missing) > 0,
        "current_app_version": CURRENT_APP_VERSION,
        "effective_version": effective_version,
        "missing_scopes": missing,
        "missing_features": missing_features,
        "changelog": current_version.changelog if current_version else "",
        "installed_scopes": installed_scopes,
        "required_scopes": REQUIRED_SCOPES
    }


# ============================================================================
# UPGRADE URL GENERATION
# ============================================================================

def get_upgrade_url(workspace_id: str, team_id: str = None) -> str:
    """
    Generate the OAuth URL for upgrading an app installation.

    This URL will prompt the user to re-authorize with the new scopes.
    The existing bot token remains the same, but Slack appends new scopes.

    Args:
        workspace_id: Our internal workspace ID
        team_id: The Slack team ID (if available)

    Returns:
        OAuth authorization URL with required scopes
    """
    from slack_security import get_slack_client_id

    client_id = get_slack_client_id()
    if not client_id:
        return None

    base_url = os.environ.get('APP_BASE_URL', 'https://decisionrecords.org')
    redirect_uri = f"{base_url}/api/slack/oauth/callback"
    scopes = ",".join(REQUIRED_SCOPES)

    url = f"https://slack.com/oauth/v2/authorize?client_id={client_id}&scope={scopes}&redirect_uri={redirect_uri}"

    # Add team_id to pre-select the workspace
    if team_id:
        url += f"&team={team_id}"

    return url


# ============================================================================
# APP HOME BLOCKS
# ============================================================================

def get_app_home_blocks(installed_scopes: List[str], user_name: str = None) -> List[Dict]:
    """
    Generate Block Kit blocks for the App Home tab.

    Shows current status and upgrade prompt if needed.

    Args:
        installed_scopes: List of scopes the workspace has granted
        user_name: Name of the user viewing the App Home

    Returns:
        List of Block Kit block dictionaries
    """
    upgrade_info = get_upgrade_info(installed_scopes)

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "Decision Records"}
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"Welcome{' ' + user_name if user_name else ''}! Decision Records helps your team capture and preserve the reasoning behind important decisions."
            }
        },
        {"type": "divider"}
    ]

    # Show upgrade banner if needed
    if upgrade_info["needs_upgrade"]:
        blocks.extend([
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": ":sparkles: *A new version of Decision Records is available!*"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*What's new in v{CURRENT_APP_VERSION}:*\n" +
                            "\n".join([f"• {f}" for f in upgrade_info["missing_features"]])
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Upgrade App"},
                        "style": "primary",
                        "action_id": "upgrade_app",
                        "url": get_upgrade_url(None)  # Will be replaced with proper URL
                    }
                ]
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"_Your installation: v{upgrade_info['effective_version']} | Latest: v{CURRENT_APP_VERSION}_"
                    }
                ]
            },
            {"type": "divider"}
        ])

    # Quick actions section
    blocks.extend([
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Quick Actions*"
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Create Decision"},
                    "action_id": "create_decision_home"
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "List Decisions"},
                    "action_id": "list_decisions_home"
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Open Web App"},
                    "action_id": "open_web_app",
                    "url": os.environ.get('APP_BASE_URL', 'https://decisionrecords.org')
                }
            ]
        }
    ])

    # Available commands section
    blocks.extend([
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Available Commands*\n" +
                        "`/adr create` - Create a new decision\n" +
                        "`/adr list [status]` - List recent decisions\n" +
                        "`/adr view <id>` - View a specific decision\n" +
                        "`/adr search <query>` - Search decisions\n" +
                        "`/adr help` - Show help"
            }
        }
    ])

    # Status section
    status_text = ":white_check_mark: All features enabled" if not upgrade_info["needs_upgrade"] else \
                  f":warning: {len(upgrade_info['missing_scopes'])} permission(s) missing - some features unavailable"

    blocks.extend([
        {"type": "divider"},
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Status: {status_text} | App version: {CURRENT_APP_VERSION}"
                }
            ]
        }
    ])

    return blocks


# ============================================================================
# UPGRADE PROMPT FOR SLASH COMMANDS
# ============================================================================

def get_upgrade_prompt_blocks(installed_scopes: List[str], team_id: str = None) -> List[Dict]:
    """
    Generate a compact upgrade prompt to include in slash command responses.

    Args:
        installed_scopes: List of scopes the workspace has granted
        team_id: The Slack team ID for the upgrade URL

    Returns:
        List of Block Kit blocks for the upgrade prompt, or empty list if no upgrade needed
    """
    if not needs_upgrade(installed_scopes):
        return []

    upgrade_url = get_upgrade_url(None, team_id)

    return [
        {"type": "divider"},
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f":sparkles: *New version available!* <{upgrade_url}|Upgrade now> to get DM confirmations and owner notifications."
                }
            ]
        }
    ]


# ============================================================================
# WORKSPACE SCOPE STORAGE
# ============================================================================

def get_workspace_scopes(workspace) -> List[str]:
    """
    Get the scopes granted to a workspace.

    We store the granted scopes when OAuth completes.
    If not stored, assume minimal scopes from v1.0.0.

    Args:
        workspace: SlackWorkspace model instance

    Returns:
        List of scope strings
    """
    if hasattr(workspace, 'granted_scopes') and workspace.granted_scopes:
        return workspace.granted_scopes.split(',')

    # Default to base scopes if not tracked
    return APP_VERSIONS["1.0.0"].scopes


def update_workspace_scopes(workspace, scopes: List[str]):
    """
    Update the stored scopes for a workspace after OAuth.

    Args:
        workspace: SlackWorkspace model instance
        scopes: List of scope strings from OAuth response
    """
    from models import db

    workspace.granted_scopes = ','.join(scopes) if scopes else None
    workspace.scopes_updated_at = datetime.utcnow()
    db.session.commit()

    logger.info(f"Updated scopes for workspace {workspace.workspace_id}: {scopes}")
