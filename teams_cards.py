"""
Adaptive Card builders for Microsoft Teams integration.

Teams uses Adaptive Cards v1.5 for rich interactive content.
This module provides functions to build cards for various scenarios.
"""
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Card version - Teams supports Adaptive Cards 1.5
ADAPTIVE_CARD_VERSION = "1.5"
ADAPTIVE_CARD_SCHEMA = "http://adaptivecards.io/schemas/adaptive-card.json"


def _get_base_url():
    """Get the application base URL."""
    return os.environ.get('APP_BASE_URL', 'https://decisionrecords.org')


def _get_status_emoji(status):
    """Get emoji for decision status."""
    return {
        'proposed': '\U0001F535',   # Blue circle
        'accepted': '\U0001F7E2',   # Green circle
        'archived': '\u26AA',       # White circle
        'superseded': '\U0001F7E0', # Orange circle
    }.get(status, '\U0001F535')


def _get_status_color(status):
    """Get color for decision status."""
    return {
        'proposed': 'accent',
        'accepted': 'good',
        'archived': 'default',
        'superseded': 'warning',
    }.get(status, 'default')


def build_menu_card():
    """
    Build the main menu card (equivalent to Slack's /decision menu).

    Shown when user sends a message to the bot without a specific command.
    """
    return {
        "$schema": ADAPTIVE_CARD_SCHEMA,
        "type": "AdaptiveCard",
        "version": ADAPTIVE_CARD_VERSION,
        "body": [
            {
                "type": "TextBlock",
                "text": "Decision Records",
                "size": "Large",
                "weight": "Bolder",
                "wrap": True
            },
            {
                "type": "TextBlock",
                "text": "What would you like to do?",
                "wrap": True,
                "spacing": "Small"
            }
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "Create Decision",
                "style": "positive",
                "data": {
                    "action": "open_create_modal"
                }
            },
            {
                "type": "Action.Submit",
                "title": "List Decisions",
                "data": {
                    "action": "list_decisions"
                }
            },
            {
                "type": "Action.Submit",
                "title": "My Decisions",
                "data": {
                    "action": "my_decisions"
                }
            },
            {
                "type": "Action.Submit",
                "title": "Help",
                "data": {
                    "action": "show_help"
                }
            }
        ]
    }


def build_help_card():
    """Build the help card showing available commands."""
    base_url = _get_base_url()

    return {
        "$schema": ADAPTIVE_CARD_SCHEMA,
        "type": "AdaptiveCard",
        "version": ADAPTIVE_CARD_VERSION,
        "body": [
            {
                "type": "TextBlock",
                "text": "Decision Records Help",
                "size": "Large",
                "weight": "Bolder",
                "wrap": True
            },
            {
                "type": "TextBlock",
                "text": "Available commands:",
                "weight": "Bolder",
                "spacing": "Medium",
                "wrap": True
            },
            {
                "type": "FactSet",
                "facts": [
                    {"title": "@DecisionRecords", "value": "Show interactive menu"},
                    {"title": "create", "value": "Create a new decision"},
                    {"title": "list", "value": "List recent decisions"},
                    {"title": "list [status]", "value": "List by status (proposed, accepted, archived, superseded)"},
                    {"title": "view [id]", "value": "View a specific decision"},
                    {"title": "search [query]", "value": "Search decisions"},
                    {"title": "help", "value": "Show this help message"}
                ]
            },
            {
                "type": "TextBlock",
                "text": "You can also use the message extension to create decisions from any message.",
                "wrap": True,
                "spacing": "Medium",
                "isSubtle": True
            }
        ],
        "actions": [
            {
                "type": "Action.OpenUrl",
                "title": "Open Decision Records",
                "url": base_url
            }
        ]
    }


def build_decision_list_card(decisions, title="Recent Decisions", show_view_all=True):
    """
    Build a card showing a list of decisions.

    Args:
        decisions: List of ArchitectureDecision objects
        title: Title for the card
        show_view_all: Whether to show "View All" button
    """
    base_url = _get_base_url()

    body = [
        {
            "type": "TextBlock",
            "text": title,
            "size": "Large",
            "weight": "Bolder",
            "wrap": True
        }
    ]

    if not decisions:
        body.append({
            "type": "TextBlock",
            "text": "No decisions found.",
            "wrap": True,
            "isSubtle": True
        })
    else:
        for decision in decisions[:10]:  # Limit to 10 items
            status_emoji = _get_status_emoji(decision.status)
            display_id = decision.get_display_id() if hasattr(decision, 'get_display_id') else f"ADR-{decision.decision_number}"

            decision_container = {
                "type": "Container",
                "items": [
                    {
                        "type": "ColumnSet",
                        "columns": [
                            {
                                "type": "Column",
                                "width": "stretch",
                                "items": [
                                    {
                                        "type": "TextBlock",
                                        "text": f"{status_emoji} **{display_id}**: {decision.title}",
                                        "wrap": True,
                                        "maxLines": 2
                                    },
                                    {
                                        "type": "TextBlock",
                                        "text": f"Status: {decision.status.capitalize()}",
                                        "isSubtle": True,
                                        "size": "Small",
                                        "spacing": "None"
                                    }
                                ]
                            },
                            {
                                "type": "Column",
                                "width": "auto",
                                "verticalContentAlignment": "Center",
                                "items": [
                                    {
                                        "type": "ActionSet",
                                        "actions": [
                                            {
                                                "type": "Action.Submit",
                                                "title": "View",
                                                "data": {
                                                    "action": "view_decision",
                                                    "decision_id": decision.id
                                                }
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                ],
                "separator": True,
                "spacing": "Medium"
            }
            body.append(decision_container)

    actions = []
    if show_view_all and decisions:
        actions.append({
            "type": "Action.OpenUrl",
            "title": "View All in Browser",
            "url": f"{base_url}/decisions"
        })

    return {
        "$schema": ADAPTIVE_CARD_SCHEMA,
        "type": "AdaptiveCard",
        "version": ADAPTIVE_CARD_VERSION,
        "body": body,
        "actions": actions
    }


def build_decision_detail_card(decision, show_actions=True):
    """
    Build a card showing detailed decision information.

    Args:
        decision: ArchitectureDecision object
        show_actions: Whether to show action buttons
    """
    base_url = _get_base_url()
    status_emoji = _get_status_emoji(decision.status)
    display_id = decision.get_display_id() if hasattr(decision, 'get_display_id') else f"ADR-{decision.decision_number}"

    # Get tenant domain for URL
    tenant_domain = decision.tenant.domain if decision.tenant else ''
    decision_url = f"{base_url}/{tenant_domain}/decisions/{decision.decision_number}"

    body = [
        {
            "type": "TextBlock",
            "text": f"{status_emoji} {display_id}: {decision.title}",
            "size": "Large",
            "weight": "Bolder",
            "wrap": True
        },
        {
            "type": "FactSet",
            "facts": [
                {"title": "Status", "value": decision.status.capitalize()},
                {"title": "Created", "value": decision.created_at.strftime('%Y-%m-%d') if decision.created_at else 'N/A'},
            ]
        }
    ]

    # Add owner if exists
    if hasattr(decision, 'owner') and decision.owner:
        body[1]["facts"].append({
            "title": "Owner",
            "value": decision.owner.display_name or decision.owner.email
        })

    # Add context if exists
    if decision.context:
        body.append({
            "type": "TextBlock",
            "text": "**Context**",
            "wrap": True,
            "spacing": "Medium"
        })
        body.append({
            "type": "TextBlock",
            "text": decision.context[:500] + ('...' if len(decision.context) > 500 else ''),
            "wrap": True,
            "isSubtle": True
        })

    # Add decision content if exists
    if decision.decision:
        body.append({
            "type": "TextBlock",
            "text": "**Decision**",
            "wrap": True,
            "spacing": "Medium"
        })
        body.append({
            "type": "TextBlock",
            "text": decision.decision[:500] + ('...' if len(decision.decision) > 500 else ''),
            "wrap": True,
            "isSubtle": True
        })

    # Add consequences if exists
    if decision.consequences:
        body.append({
            "type": "TextBlock",
            "text": "**Consequences**",
            "wrap": True,
            "spacing": "Medium"
        })
        body.append({
            "type": "TextBlock",
            "text": decision.consequences[:500] + ('...' if len(decision.consequences) > 500 else ''),
            "wrap": True,
            "isSubtle": True
        })

    actions = []
    if show_actions:
        actions = [
            {
                "type": "Action.OpenUrl",
                "title": "View Full Decision",
                "url": decision_url
            },
            {
                "type": "Action.Submit",
                "title": "Change Status",
                "data": {
                    "action": "open_status_modal",
                    "decision_id": decision.id
                }
            }
        ]

    return {
        "$schema": ADAPTIVE_CARD_SCHEMA,
        "type": "AdaptiveCard",
        "version": ADAPTIVE_CARD_VERSION,
        "body": body,
        "actions": actions
    }


def build_create_decision_form_card(prefill_context=None, users=None):
    """
    Build the create decision form card for task module.

    Args:
        prefill_context: Optional context text to pre-fill (e.g., from message)
        users: Optional list of users for owner selection
    """
    body = [
        {
            "type": "TextBlock",
            "text": "Create New Decision",
            "size": "Large",
            "weight": "Bolder",
            "wrap": True
        },
        {
            "type": "Input.Text",
            "id": "title",
            "label": "Title *",
            "placeholder": "What is this decision about?",
            "isRequired": True,
            "maxLength": 255
        },
        {
            "type": "Input.Text",
            "id": "context",
            "label": "Context",
            "placeholder": "What is the context for this decision? What forces are at play?",
            "isMultiline": True,
            "value": prefill_context or ""
        },
        {
            "type": "Input.Text",
            "id": "decision",
            "label": "Decision",
            "placeholder": "What was decided?",
            "isMultiline": True
        },
        {
            "type": "Input.Text",
            "id": "consequences",
            "label": "Consequences",
            "placeholder": "What are the consequences of this decision?",
            "isMultiline": True
        },
        {
            "type": "Input.ChoiceSet",
            "id": "status",
            "label": "Status",
            "value": "proposed",
            "choices": [
                {"title": "Proposed", "value": "proposed"},
                {"title": "Accepted", "value": "accepted"},
                {"title": "Archived", "value": "archived"},
                {"title": "Superseded", "value": "superseded"}
            ]
        }
    ]

    # Add owner selection if users provided
    if users:
        owner_choices = [{"title": "-- No owner --", "value": ""}]
        for user in users:
            display_name = user.display_name or user.email
            owner_choices.append({
                "title": display_name,
                "value": str(user.id)
            })

        body.append({
            "type": "Input.ChoiceSet",
            "id": "owner_id",
            "label": "Decision Owner",
            "value": "",
            "choices": owner_choices
        })

    return {
        "$schema": ADAPTIVE_CARD_SCHEMA,
        "type": "AdaptiveCard",
        "version": ADAPTIVE_CARD_VERSION,
        "body": body,
        "actions": [
            {
                "type": "Action.Submit",
                "title": "Create",
                "style": "positive",
                "data": {
                    "action": "submit_decision"
                }
            }
        ]
    }


def build_status_change_form_card(decision):
    """
    Build the status change form card for task module.

    Args:
        decision: The decision to change status for
    """
    display_id = decision.get_display_id() if hasattr(decision, 'get_display_id') else f"ADR-{decision.decision_number}"

    return {
        "$schema": ADAPTIVE_CARD_SCHEMA,
        "type": "AdaptiveCard",
        "version": ADAPTIVE_CARD_VERSION,
        "body": [
            {
                "type": "TextBlock",
                "text": "Change Decision Status",
                "size": "Large",
                "weight": "Bolder",
                "wrap": True
            },
            {
                "type": "TextBlock",
                "text": f"{display_id}: {decision.title}",
                "wrap": True
            },
            {
                "type": "TextBlock",
                "text": f"Current status: **{decision.status.capitalize()}**",
                "wrap": True,
                "spacing": "Medium"
            },
            {
                "type": "Input.ChoiceSet",
                "id": "new_status",
                "label": "New Status",
                "value": decision.status,
                "choices": [
                    {"title": "Proposed", "value": "proposed"},
                    {"title": "Accepted", "value": "accepted"},
                    {"title": "Archived", "value": "archived"},
                    {"title": "Superseded", "value": "superseded"}
                ]
            }
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "Update Status",
                "style": "positive",
                "data": {
                    "action": "submit_status_change",
                    "decision_id": decision.id
                }
            }
        ]
    }


def build_link_account_card(workspace_id, aad_object_id, email=None):
    """
    Build the account linking card.

    Shown when a user needs to link their Teams account to Decision Records.
    """
    from teams_security import generate_teams_link_token

    link_token = generate_teams_link_token(workspace_id, aad_object_id, email)
    base_url = _get_base_url()
    link_url = f"{base_url}/teams/link?token={link_token}"

    return {
        "$schema": ADAPTIVE_CARD_SCHEMA,
        "type": "AdaptiveCard",
        "version": ADAPTIVE_CARD_VERSION,
        "body": [
            {
                "type": "TextBlock",
                "text": "Link Your Decision Records Account",
                "size": "Large",
                "weight": "Bolder",
                "wrap": True
            },
            {
                "type": "TextBlock",
                "text": "To use Decision Records commands, you need to link your Teams account to your Decision Records account.",
                "wrap": True
            },
            {
                "type": "TextBlock",
                "text": "**What happens when you click the button:**",
                "wrap": True,
                "spacing": "Medium"
            },
            {
                "type": "TextBlock",
                "text": "1. A browser window will open\n2. Sign in to Decision Records if needed\n3. Your accounts will be linked automatically",
                "wrap": True,
                "spacing": "Small"
            }
        ],
        "actions": [
            {
                "type": "Action.OpenUrl",
                "title": "Link My Account",
                "url": link_url,
                "style": "positive"
            }
        ]
    }


def build_notification_card(decision, event_type):
    """
    Build a notification card for channel notifications.

    Args:
        decision: ArchitectureDecision object
        event_type: 'created' or 'status_changed'
    """
    base_url = _get_base_url()
    status_emoji = _get_status_emoji(decision.status)
    display_id = decision.get_display_id() if hasattr(decision, 'get_display_id') else f"ADR-{decision.decision_number}"

    # Get tenant domain for URL
    tenant_domain = decision.tenant.domain if decision.tenant else ''
    decision_url = f"{base_url}/{tenant_domain}/decisions/{decision.decision_number}"

    if event_type == 'created':
        title = "\u2728 New Decision Record Created"
        subtitle = f"{display_id}: {decision.title}"
    elif event_type == 'status_changed':
        title = "\U0001F504 Decision Status Changed"
        subtitle = f"{display_id}: {decision.title}"
    else:
        title = "Decision Record Update"
        subtitle = f"{display_id}: {decision.title}"

    body = [
        {
            "type": "TextBlock",
            "text": title,
            "size": "Medium",
            "weight": "Bolder",
            "wrap": True
        },
        {
            "type": "TextBlock",
            "text": subtitle,
            "wrap": True
        },
        {
            "type": "FactSet",
            "facts": [
                {"title": "Status", "value": f"{status_emoji} {decision.status.capitalize()}"}
            ]
        }
    ]

    # Add creator/updater info if available
    if hasattr(decision, 'created_by') and decision.created_by and event_type == 'created':
        body[2]["facts"].append({
            "title": "By",
            "value": decision.created_by.display_name or decision.created_by.email
        })

    # Add context preview if exists
    if decision.context and event_type == 'created':
        body.append({
            "type": "TextBlock",
            "text": decision.context[:200] + ('...' if len(decision.context) > 200 else ''),
            "wrap": True,
            "isSubtle": True,
            "spacing": "Medium"
        })

    return {
        "$schema": ADAPTIVE_CARD_SCHEMA,
        "type": "AdaptiveCard",
        "version": ADAPTIVE_CARD_VERSION,
        "body": body,
        "actions": [
            {
                "type": "Action.OpenUrl",
                "title": "View Decision",
                "url": decision_url
            }
        ]
    }


def build_search_results_card(decisions, query):
    """
    Build a card showing search results.

    Args:
        decisions: List of matching decisions
        query: The search query used
    """
    return build_decision_list_card(
        decisions,
        title=f"Search Results for \"{query}\"",
        show_view_all=False
    )


def build_success_card(title, message, decision=None):
    """
    Build a success confirmation card.

    Args:
        title: Success title
        message: Success message
        decision: Optional decision that was created/modified
    """
    base_url = _get_base_url()

    body = [
        {
            "type": "TextBlock",
            "text": f"\u2705 {title}",
            "size": "Medium",
            "weight": "Bolder",
            "wrap": True,
            "color": "Good"
        },
        {
            "type": "TextBlock",
            "text": message,
            "wrap": True
        }
    ]

    actions = []

    if decision:
        display_id = decision.get_display_id() if hasattr(decision, 'get_display_id') else f"ADR-{decision.decision_number}"
        tenant_domain = decision.tenant.domain if decision.tenant else ''
        decision_url = f"{base_url}/{tenant_domain}/decisions/{decision.decision_number}"

        body.append({
            "type": "FactSet",
            "facts": [
                {"title": "ID", "value": display_id},
                {"title": "Title", "value": decision.title},
                {"title": "Status", "value": decision.status.capitalize()}
            ],
            "spacing": "Medium"
        })

        actions.append({
            "type": "Action.OpenUrl",
            "title": "View Decision",
            "url": decision_url
        })

    return {
        "$schema": ADAPTIVE_CARD_SCHEMA,
        "type": "AdaptiveCard",
        "version": ADAPTIVE_CARD_VERSION,
        "body": body,
        "actions": actions
    }


def build_error_card(title, message):
    """
    Build an error card.

    Args:
        title: Error title
        message: Error message
    """
    return {
        "$schema": ADAPTIVE_CARD_SCHEMA,
        "type": "AdaptiveCard",
        "version": ADAPTIVE_CARD_VERSION,
        "body": [
            {
                "type": "TextBlock",
                "text": f"\u274C {title}",
                "size": "Medium",
                "weight": "Bolder",
                "wrap": True,
                "color": "Attention"
            },
            {
                "type": "TextBlock",
                "text": message,
                "wrap": True
            }
        ]
    }


def build_welcome_card():
    """
    Build a welcome card for new bot installations.

    Shown when the bot is added to a team or conversation.
    """
    base_url = _get_base_url()

    return {
        "$schema": ADAPTIVE_CARD_SCHEMA,
        "type": "AdaptiveCard",
        "version": ADAPTIVE_CARD_VERSION,
        "body": [
            {
                "type": "TextBlock",
                "text": "Welcome to Decision Records!",
                "size": "Large",
                "weight": "Bolder",
                "wrap": True
            },
            {
                "type": "TextBlock",
                "text": "Decision Records helps your team capture and manage Architecture Decision Records (ADRs) directly in Microsoft Teams.",
                "wrap": True
            },
            {
                "type": "TextBlock",
                "text": "**Getting Started**",
                "weight": "Bolder",
                "spacing": "Medium",
                "wrap": True
            },
            {
                "type": "TextBlock",
                "text": "1. Mention @DecisionRecords to see the interactive menu\n2. Use commands like `create`, `list`, or `search`\n3. Use the message extension to create decisions from any message",
                "wrap": True
            },
            {
                "type": "TextBlock",
                "text": "**Configuration**",
                "weight": "Bolder",
                "spacing": "Medium",
                "wrap": True
            },
            {
                "type": "TextBlock",
                "text": "An admin needs to connect this Teams workspace to your Decision Records organization. Go to Settings in the web app to complete setup.",
                "wrap": True,
                "isSubtle": True
            }
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "Show Commands",
                "data": {
                    "action": "show_help"
                }
            },
            {
                "type": "Action.OpenUrl",
                "title": "Open Decision Records",
                "url": base_url
            }
        ]
    }
