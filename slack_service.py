"""
Slack integration service module.

Handles Slack API calls, message formatting, user linking, and business logic
for the Decision Records Slack app.
"""
import logging
import os
from datetime import datetime
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from models import (
    db, SlackWorkspace, SlackUserMapping, User, ArchitectureDecision,
    Tenant, TenantMembership
)
from slack_security import encrypt_token, decrypt_token, generate_link_token

logger = logging.getLogger(__name__)


class SlackService:
    """Service for Slack API interactions."""

    def __init__(self, workspace: SlackWorkspace):
        self.workspace = workspace
        self._client = None

    @property
    def client(self) -> WebClient:
        """Lazy-loaded Slack WebClient."""
        if self._client is None:
            token = decrypt_token(self.workspace.bot_token_encrypted)
            self._client = WebClient(token=token)
        return self._client

    def update_activity(self):
        """Update last activity timestamp."""
        self.workspace.last_activity_at = datetime.utcnow()
        db.session.commit()

    def get_channels(self):
        """Get list of public channels the bot can post to."""
        channels = []
        try:
            # Get public channels the bot is a member of or can join
            result = self.client.conversations_list(
                types="public_channel",
                exclude_archived=True,
                limit=200
            )
            if result.get('ok'):
                for channel in result.get('channels', []):
                    channels.append({
                        'id': channel.get('id'),
                        'name': channel.get('name'),
                        'is_member': channel.get('is_member', False)
                    })
        except SlackApiError as e:
            logger.error(f"Failed to get Slack channels: {e}")
            raise
        return channels

    # =========================================================================
    # USER LINKING
    # =========================================================================

    def get_or_link_user(self, slack_user_id: str):
        """
        Get or create a user mapping for a Slack user.

        Returns tuple: (SlackUserMapping, User or None, needs_linking: bool)
        """
        # Check for existing mapping
        mapping = SlackUserMapping.query.filter_by(
            slack_workspace_id=self.workspace.id,
            slack_user_id=slack_user_id
        ).first()

        if mapping and mapping.user_id:
            # Already linked
            user = User.query.get(mapping.user_id)
            return mapping, user, False

        # Get Slack user info
        slack_email = None
        try:
            user_info = self.client.users_info(user=slack_user_id)
            if user_info.get('ok'):
                slack_email = user_info.get('user', {}).get('profile', {}).get('email')
        except SlackApiError as e:
            logger.warning(f"Failed to get Slack user info: {e}")

        # Create or update mapping
        if not mapping:
            mapping = SlackUserMapping(
                slack_workspace_id=self.workspace.id,
                slack_user_id=slack_user_id,
                slack_email=slack_email
            )
            db.session.add(mapping)
        elif slack_email and not mapping.slack_email:
            mapping.slack_email = slack_email

        # Try auto-link by email
        if slack_email:
            # Get tenant domain
            tenant = self.workspace.tenant
            if tenant:
                # Find user with matching email in this tenant
                user = User.query.filter_by(email=slack_email).first()
                if user:
                    # Check if user is member of this tenant
                    membership = TenantMembership.query.filter_by(
                        user_id=user.id,
                        tenant_id=tenant.id
                    ).first()
                    if membership:
                        mapping.user_id = user.id
                        mapping.linked_at = datetime.utcnow()
                        mapping.link_method = 'auto_email'
                        db.session.commit()
                        return mapping, user, False

        db.session.commit()
        return mapping, None, True

    def get_link_message_blocks(self, slack_user_id: str, slack_email: str = None):
        """Generate Block Kit blocks for account linking message."""
        # Generate link token
        link_token = generate_link_token(
            self.workspace.id,
            slack_user_id,
            slack_email
        )

        # Build the link URL
        base_url = os.environ.get('APP_BASE_URL', 'https://decisionrecords.org')
        link_url = f"{base_url}/api/slack/link/initiate?token={link_token}"

        # Get tenant info for context
        tenant = self.workspace.tenant
        tenant_name = tenant.name if tenant and tenant.name else tenant.domain if tenant else 'your organization'

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "Link Your Decision Records Account"}
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":wave: Welcome! To use Decision Records commands in this workspace, you need to link your Slack account to your Decision Records account."
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*This workspace is connected to:* {tenant_name}"
                }
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*What happens when you click the button:*\n" +
                            "1. A new browser window will open\n" +
                            "2. If you're not logged in, you'll sign in to Decision Records\n" +
                            "3. Your accounts will be linked automatically\n" +
                            "4. You can then use all /adr commands in Slack"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Link My Account"},
                        "url": link_url,
                        "style": "primary",
                        "action_id": "link_account"
                    }
                ]
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f":email: Your Slack email: {slack_email or 'Not available'}"
                    }
                ]
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": ":question: Don't have an account? The link above will help you create one or contact your organization admin for an invite."
                    }
                ]
            }
        ]
        return blocks

    # =========================================================================
    # SLASH COMMAND HANDLERS
    # =========================================================================

    def handle_command(self, command_text: str, slack_user_id: str, trigger_id: str, response_url: str):
        """
        Handle a slash command.

        Returns (response_dict, is_ephemeral)
        """
        parts = command_text.strip().split(maxsplit=1)
        subcommand = parts[0].lower() if parts else 'help'
        args = parts[1] if len(parts) > 1 else ''

        # Check user linking first
        mapping, user, needs_linking = self.get_or_link_user(slack_user_id)

        if needs_linking and subcommand != 'help':
            return {
                'response_type': 'ephemeral',
                'blocks': self.get_link_message_blocks(slack_user_id, mapping.slack_email)
            }, True

        handlers = {
            'help': self._handle_help,
            'list': self._handle_list,
            'view': self._handle_view,
            'search': self._handle_search,
            'create': self._handle_create,
        }

        handler = handlers.get(subcommand, self._handle_help)
        return handler(args, user, trigger_id)

    def _handle_help(self, args: str, user: User, trigger_id: str):
        """Show help message."""
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "Decision Records - Help"}
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Available commands:*"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "`/adr create` - Create a new decision record\n"
                        "`/adr list` - List recent decisions\n"
                        "`/adr list mine` - List your decisions\n"
                        "`/adr list [status]` - List by status\n"
                        "`/adr list space:[name]` - List by space\n"
                        "`/adr view <id>` - View a specific decision\n"
                        "`/adr search <query>` - Search decisions\n"
                        "`/adr help` - Show this help message"
                    )
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "_Statuses: proposed, accepted, archived, superseded | Combine filters: `/adr list mine accepted`_"
                    }
                ]
            }
        ]
        return {'response_type': 'ephemeral', 'blocks': blocks}, True

    def _handle_list(self, args: str, user: User, trigger_id: str):
        """
        List recent decisions with filtering options.

        Usage:
          /adr list              - List recent decisions
          /adr list mine         - List my decisions (created by me or owned by me)
          /adr list [status]     - List by status (proposed, accepted, archived, superseded)
          /adr list space:[name] - List decisions in a specific space
          /adr list mine [status] - Combine filters
        """
        from models import Space

        tenant = self.workspace.tenant
        if not tenant:
            return {'response_type': 'ephemeral', 'text': 'Workspace not configured properly.'}, True

        # Parse arguments
        parts = args.strip().lower().split() if args else []
        valid_statuses = ['proposed', 'accepted', 'archived', 'superseded']

        show_mine = False
        status_filter = None
        space_filter = None
        filter_description = []

        for part in parts:
            if part == 'mine':
                show_mine = True
                filter_description.append('my decisions')
            elif part in valid_statuses:
                status_filter = part
                filter_description.append(part)
            elif part.startswith('space:'):
                space_name = part[6:]  # Remove 'space:' prefix
                space_filter = space_name
                filter_description.append(f'space: {space_name}')

        # Build query
        query = ArchitectureDecision.query.filter_by(
            tenant_id=tenant.id,
            deleted_at=None
        )

        # Apply filters
        if show_mine and user:
            # Show decisions created by user OR owned by user
            from sqlalchemy import or_
            query = query.filter(
                or_(
                    ArchitectureDecision.created_by == user.id,
                    ArchitectureDecision.owner_id == user.id
                )
            )

        if status_filter:
            query = query.filter_by(status=status_filter)

        if space_filter:
            # Find space by name (case-insensitive)
            space = Space.query.filter(
                Space.tenant_id == tenant.id,
                db.func.lower(Space.name) == space_filter.lower()
            ).first()
            if space:
                query = query.filter_by(space_id=space.id)
            else:
                # Show available spaces if not found
                spaces = Space.query.filter_by(tenant_id=tenant.id).all()
                space_names = [s.name for s in spaces] if spaces else ['(none)']
                return {
                    'response_type': 'ephemeral',
                    'text': f"Space '{space_filter}' not found. Available spaces: {', '.join(space_names)}"
                }, True

        query = query.order_by(ArchitectureDecision.created_at.desc())
        decisions = query.limit(10).all()

        # Build title
        title = "Recent Decisions"
        if filter_description:
            title += f" ({', '.join(filter_description)})"

        if not decisions:
            help_text = (
                "\n\n*Filter options:*\n"
                "`/adr list mine` - Your decisions\n"
                "`/adr list [status]` - By status\n"
                "`/adr list space:[name]` - By space"
            )
            return {
                'response_type': 'ephemeral',
                'text': f"No decisions found{' matching your filters' if filter_description else ''}." + help_text
            }, True

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": title}
            }
        ]

        for decision in decisions:
            status_emoji = self._get_status_emoji(decision.status)
            display_id = decision.get_display_id() if hasattr(decision, 'get_display_id') else f"ADR-{decision.decision_number}"

            # Include space name if showing all decisions (not filtered by space)
            space_info = ""
            # Show first space if decision belongs to any spaces
            if not space_filter and decision.spaces:
                space_info = f" | Space: {decision.spaces[0].name}"

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{status_emoji} *{display_id}*: {decision.title}\n_Status: {decision.status}{space_info}_"
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View"},
                    "action_id": f"view_decision_{decision.id}",
                    "value": str(decision.id)
                }
            })

        # Add filter hint if no filters used
        if not filter_description:
            blocks.append({
                "type": "context",
                "elements": [{
                    "type": "mrkdwn",
                    "text": "_Tip: Use `/adr list mine` to see your decisions, or `/adr list space:[name]` for a specific space_"
                }]
            })

        return {'response_type': 'ephemeral', 'blocks': blocks}, True

    def _handle_view(self, args: str, user: User, trigger_id: str):
        """View a specific decision."""
        tenant = self.workspace.tenant
        if not tenant:
            return {'response_type': 'ephemeral', 'text': 'Workspace not configured properly.'}, True

        decision_id = args.strip()
        if not decision_id:
            return {'response_type': 'ephemeral', 'text': 'Please provide a decision ID. Usage: `/adr view <id>`'}, True

        # Try to find by display ID or numeric ID
        decision = None
        if decision_id.isdigit():
            decision = ArchitectureDecision.query.filter_by(
                id=int(decision_id),
                tenant_id=tenant.id,
                deleted_at=None
            ).first()
        else:
            # Try by decision number (e.g., "42" or "PREFIX-42")
            parts = decision_id.upper().split('-')
            if len(parts) == 2 and parts[1].isdigit():
                number = int(parts[1])
            elif decision_id.isdigit():
                number = int(decision_id)
            else:
                number = None

            if number:
                decision = ArchitectureDecision.query.filter_by(
                    decision_number=number,
                    tenant_id=tenant.id,
                    deleted_at=None
                ).first()

        if not decision:
            return {'response_type': 'ephemeral', 'text': f'Decision "{decision_id}" not found.'}, True

        blocks = self._format_decision_detail_blocks(decision)
        return {'response_type': 'ephemeral', 'blocks': blocks}, True

    def _handle_search(self, args: str, user: User, trigger_id: str):
        """Search decisions."""
        tenant = self.workspace.tenant
        if not tenant:
            return {'response_type': 'ephemeral', 'text': 'Workspace not configured properly.'}, True

        query_text = args.strip()
        if not query_text:
            return {'response_type': 'ephemeral', 'text': 'Please provide a search query. Usage: `/adr search <query>`'}, True

        # Simple search in title and context
        search_pattern = f"%{query_text}%"
        decisions = ArchitectureDecision.query.filter(
            ArchitectureDecision.tenant_id == tenant.id,
            ArchitectureDecision.deleted_at == None,
            db.or_(
                ArchitectureDecision.title.ilike(search_pattern),
                ArchitectureDecision.context.ilike(search_pattern),
                ArchitectureDecision.decision.ilike(search_pattern)
            )
        ).order_by(ArchitectureDecision.created_at.desc()).limit(10).all()

        if not decisions:
            return {'response_type': 'ephemeral', 'text': f'No decisions found matching "{query_text}".'}, True

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"Search Results: \"{query_text}\""}
            }
        ]

        for decision in decisions:
            status_emoji = self._get_status_emoji(decision.status)
            display_id = decision.get_display_id() if hasattr(decision, 'get_display_id') else f"ADR-{decision.decision_number}"
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{status_emoji} *{display_id}*: {decision.title}\n_Status: {decision.status}_"
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View"},
                    "action_id": f"view_decision_{decision.id}",
                    "value": str(decision.id)
                }
            })

        return {'response_type': 'ephemeral', 'blocks': blocks}, True

    def _handle_create(self, args: str, user: User, trigger_id: str):
        """Open modal to create a new decision."""
        if not user:
            return {
                'response_type': 'ephemeral',
                'text': 'You need to link your account before creating decisions.'
            }, True

        try:
            self._open_create_modal(trigger_id, user)
            return None, True  # No response needed, modal opens
        except SlackApiError as e:
            logger.error(f"Failed to open create modal: {e}")
            return {'response_type': 'ephemeral', 'text': 'Failed to open creation form. Please try again.'}, True

    def _open_create_modal(self, trigger_id: str, user: User):
        """Open the create decision modal."""
        view = {
            "type": "modal",
            "callback_id": "create_decision",
            "title": {"type": "plain_text", "text": "Create Decision"},
            "submit": {"type": "plain_text", "text": "Create"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "private_metadata": str(user.id),
            "blocks": [
                {
                    "type": "input",
                    "block_id": "title_block",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "title",
                        "placeholder": {"type": "plain_text", "text": "What is this decision about?"},
                        "max_length": 255
                    },
                    "label": {"type": "plain_text", "text": "Title"}
                },
                {
                    "type": "input",
                    "block_id": "context_block",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "context",
                        "multiline": True,
                        "placeholder": {"type": "plain_text", "text": "What is the context for this decision? What forces are at play?"},
                        "max_length": 3000
                    },
                    "label": {"type": "plain_text", "text": "Context"}
                },
                {
                    "type": "input",
                    "block_id": "decision_block",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "decision",
                        "multiline": True,
                        "placeholder": {"type": "plain_text", "text": "What is the decision that was made?"},
                        "max_length": 3000
                    },
                    "label": {"type": "plain_text", "text": "Decision"}
                },
                {
                    "type": "input",
                    "block_id": "consequences_block",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "consequences",
                        "multiline": True,
                        "placeholder": {"type": "plain_text", "text": "What are the consequences of this decision?"},
                        "max_length": 3000
                    },
                    "label": {"type": "plain_text", "text": "Consequences"}
                },
                {
                    "type": "input",
                    "block_id": "status_block",
                    "optional": True,
                    "element": {
                        "type": "static_select",
                        "action_id": "status",
                        "placeholder": {"type": "plain_text", "text": "Select status"},
                        "initial_option": {
                            "text": {"type": "plain_text", "text": "Proposed"},
                            "value": "proposed"
                        },
                        "options": [
                            {"text": {"type": "plain_text", "text": "Proposed"}, "value": "proposed"},
                            {"text": {"type": "plain_text", "text": "Accepted"}, "value": "accepted"},
                            {"text": {"type": "plain_text", "text": "Archived"}, "value": "archived"},
                            {"text": {"type": "plain_text", "text": "Superseded"}, "value": "superseded"}
                        ]
                    },
                    "label": {"type": "plain_text", "text": "Status"}
                },
                {
                    "type": "input",
                    "block_id": "owner_block",
                    "optional": True,
                    "element": {
                        "type": "users_select",
                        "action_id": "owner",
                        "placeholder": {"type": "plain_text", "text": "Select decision owner"}
                    },
                    "label": {"type": "plain_text", "text": "Decision Owner"},
                    "hint": {"type": "plain_text", "text": "The person responsible for this decision. They will be notified."}
                }
            ]
        }
        self.client.views_open(trigger_id=trigger_id, view=view)

    # =========================================================================
    # INTERACTION HANDLERS
    # =========================================================================

    def handle_interaction(self, payload: dict):
        """
        Handle an interactive component payload.

        Returns response dict or None.
        """
        interaction_type = payload.get('type')

        if interaction_type == 'view_submission':
            return self._handle_view_submission(payload)
        elif interaction_type == 'block_actions':
            return self._handle_block_actions(payload)
        elif interaction_type == 'shortcut' or interaction_type == 'message_action':
            return self._handle_message_action(payload)

        return None

    def handle_modal_submission(self, payload: dict):
        """Public wrapper for modal submission handling."""
        return self._handle_view_submission(payload)

    def handle_block_action(self, payload: dict):
        """Public wrapper for block action handling."""
        return self._handle_block_actions(payload)

    def handle_message_action(self, payload: dict):
        """Public wrapper for message action handling."""
        return self._handle_message_action(payload)

    # =========================================================================
    # EVENT HANDLERS
    # =========================================================================

    def handle_event(self, event: dict):
        """
        Handle a Slack event.

        Returns response dict or None.
        """
        event_type = event.get('type')

        if event_type == 'app_home_opened':
            return self._handle_app_home_opened(event)

        return None

    def _handle_app_home_opened(self, event: dict):
        """
        Handle app_home_opened event - render the App Home tab.

        This is where we show upgrade prompts if new scopes are available.
        """
        from slack_upgrade import get_app_home_blocks, get_workspace_scopes

        user_id = event.get('user')

        try:
            # Get user info for personalization
            user_info = self.client.users_info(user=user_id)
            user_name = user_info.get('user', {}).get('real_name', '')
        except SlackApiError:
            user_name = None

        # Get workspace scopes to check for upgrade
        installed_scopes = get_workspace_scopes(self.workspace)

        # Build App Home view
        blocks = get_app_home_blocks(installed_scopes, user_name)

        try:
            self.client.views_publish(
                user_id=user_id,
                view={
                    "type": "home",
                    "blocks": blocks
                }
            )
            logger.info(f"Published App Home for user {user_id}")
        except SlackApiError as e:
            logger.error(f"Failed to publish App Home: {e}")

        self.update_activity()
        return None

    def _handle_view_submission(self, payload: dict):
        """Handle modal form submission."""
        callback_id = payload.get('view', {}).get('callback_id')

        if callback_id == 'create_decision':
            return self._create_decision_from_modal(payload)

        return None

    def _create_decision_from_modal(self, payload: dict):
        """Create a decision from modal submission."""
        view = payload.get('view', {})
        values = view.get('state', {}).get('values', {})
        user_id = view.get('private_metadata')

        try:
            user_id = int(user_id)
            user = User.query.get(user_id)
            if not user:
                return {"response_action": "errors", "errors": {"title_block": "User not found"}}
        except (ValueError, TypeError):
            return {"response_action": "errors", "errors": {"title_block": "Invalid user"}}

        # Extract values
        title = values.get('title_block', {}).get('title', {}).get('value', '').strip()
        context = values.get('context_block', {}).get('context', {}).get('value', '').strip()
        decision_text = values.get('decision_block', {}).get('decision', {}).get('value', '').strip()
        consequences = values.get('consequences_block', {}).get('consequences', {}).get('value', '').strip()
        status = values.get('status_block', {}).get('status', {}).get('selected_option', {}).get('value', 'proposed')

        # Extract owner (Slack user ID)
        owner_slack_id = values.get('owner_block', {}).get('owner', {}).get('selected_user')

        # Validate - only title is required
        errors = {}
        if not title:
            errors['title_block'] = 'Title is required'

        if errors:
            return {"response_action": "errors", "errors": errors}

        # Create the decision
        tenant = self.workspace.tenant
        domain = tenant.domain if tenant else user.sso_domain

        # Get next decision number
        max_number = db.session.query(db.func.max(ArchitectureDecision.decision_number)).filter(
            ArchitectureDecision.domain == domain
        ).scalar() or 0
        next_number = max_number + 1

        decision = ArchitectureDecision(
            title=title,
            context=context,
            decision=decision_text,
            consequences=consequences,
            status=status,
            decision_number=next_number,
            domain=domain,
            tenant_id=tenant.id if tenant else None,
            created_by_id=user.id,
            updated_by_id=user.id
        )

        # Handle decision owner
        owner_platform_user = None
        owner_slack_email = None
        if owner_slack_id:
            # Try to find the owner in our platform via Slack mapping or email
            owner_mapping = SlackUserMapping.query.filter_by(
                slack_workspace_id=self.workspace.id,
                slack_user_id=owner_slack_id
            ).first()

            if owner_mapping and owner_mapping.user_id:
                # Owner is already linked to platform
                owner_platform_user = owner_mapping.user
                decision.owner_id = owner_platform_user.id
            else:
                # Try to get owner's email from Slack
                try:
                    owner_info = self.client.users_info(user=owner_slack_id)
                    if owner_info['ok']:
                        owner_slack_email = owner_info['user'].get('profile', {}).get('email')
                        if owner_slack_email:
                            # Check if this email exists in our platform
                            existing_user = User.query.filter_by(email=owner_slack_email).first()
                            if existing_user:
                                decision.owner_id = existing_user.id
                                owner_platform_user = existing_user
                            else:
                                # Store email for external owner
                                decision.owner_email = owner_slack_email
                except SlackApiError as e:
                    logger.warning(f"Could not fetch owner info from Slack: {e}")

        db.session.add(decision)
        db.session.commit()

        # Get the display ID and build the decision URL
        display_id = decision.get_display_id() if hasattr(decision, 'get_display_id') else f'ADR-{decision.decision_number}'
        # Build decision URL - we need to construct this from the domain
        decision_url = f"https://decisionrecords.org/{domain}/decisions/{decision.id}"

        # Post notification to channel if enabled
        self._send_creation_notification(decision)

        # Send confirmation to the creator
        slack_user = payload.get('user', {})
        creator_slack_id = slack_user.get('id')

        try:
            owner_text = ""
            if owner_slack_id:
                owner_text = f"\n:bust_in_silhouette: Owner: <@{owner_slack_id}>"

            # Open DM channel first to ensure we can send
            dm_channel = self._open_dm_channel(creator_slack_id)
            if not dm_channel:
                logger.warning(f"Could not open DM channel with {creator_slack_id}")
            else:
                self.client.chat_postMessage(
                    channel=dm_channel,
                    text=f"Decision {display_id} created successfully!",
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f":white_check_mark: *Decision Created Successfully*\n\n*{display_id}*: {decision.title}{owner_text}"
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {"type": "mrkdwn", "text": f"*Status:*\n{status.title()}"},
                            {"type": "mrkdwn", "text": f"*Created by:*\n<@{creator_slack_id}>"}
                        ]
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "View Decision"},
                                "url": decision_url,
                                "action_id": "view_decision_url"
                            }
                        ]
                    }
                ]
            )
        except SlackApiError as e:
            logger.warning(f"Failed to send confirmation DM to creator: {e}")

        # Send notification to owner if different from creator
        if owner_slack_id and owner_slack_id != creator_slack_id:
            try:
                # Open DM channel with owner
                owner_dm_channel = self._open_dm_channel(owner_slack_id)
                if not owner_dm_channel:
                    logger.warning(f"Could not open DM channel with owner {owner_slack_id}")
                else:
                    self.client.chat_postMessage(
                        channel=owner_dm_channel,
                        text=f"You have been assigned as the owner of decision {display_id}",
                    blocks=[
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f":clipboard: *You've Been Assigned a Decision*\n\n<@{creator_slack_id}> has assigned you as the owner of a new decision."
                            }
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"*{display_id}*: {decision.title}"
                            }
                        },
                        {
                            "type": "section",
                            "fields": [
                                {"type": "mrkdwn", "text": f"*Status:*\n{status.title()}"},
                                {"type": "mrkdwn", "text": f"*Context:*\n{context[:100] + '...' if len(context) > 100 else context or 'Not provided'}"}
                            ]
                        },
                        {
                            "type": "actions",
                            "elements": [
                                {
                                    "type": "button",
                                    "text": {"type": "plain_text", "text": "View Decision"},
                                    "url": decision_url,
                                    "style": "primary",
                                    "action_id": "view_decision_url"
                                }
                            ]
                        }
                    ]
                )
            except SlackApiError as e:
                logger.warning(f"Failed to send owner notification DM: {e}")

        return {}  # Empty response closes the modal

    def _handle_block_actions(self, payload: dict):
        """Handle button clicks and other block actions."""
        actions = payload.get('actions', [])
        trigger_id = payload.get('trigger_id')
        slack_user_id = payload.get('user', {}).get('id')

        for action in actions:
            action_id = action.get('action_id', '')

            if action_id.startswith('view_decision_'):
                decision_id = action.get('value')
                if decision_id:
                    return self._send_decision_detail(payload, int(decision_id))

            elif action_id == 'create_decision_home':
                # Create Decision button from App Home
                mapping, user, needs_linking = self.get_or_link_user(slack_user_id)
                if needs_linking or not user:
                    self._send_ephemeral_link_prompt(payload, slack_user_id)
                    return None
                try:
                    self._open_create_modal(trigger_id, user)
                except SlackApiError as e:
                    logger.error(f"Failed to open create modal from App Home: {e}")
                return None

            elif action_id == 'list_decisions_home':
                # List Decisions button from App Home
                mapping, user, needs_linking = self.get_or_link_user(slack_user_id)
                if needs_linking or not user:
                    self._send_ephemeral_link_prompt(payload, slack_user_id)
                    return None
                self._send_decisions_list(payload, user)
                return None

            elif action_id == 'link_account':
                # Link account button opens a URL - just acknowledge the action
                return None

            elif action_id == 'upgrade_app':
                # Upgrade button opens OAuth URL - just acknowledge
                return None

        return None

    def _send_ephemeral_link_prompt(self, payload: dict, slack_user_id: str):
        """Send an ephemeral message prompting user to link their account."""
        response_url = payload.get('response_url')
        if not response_url:
            return

        mapping = SlackUserMapping.query.filter_by(
            slack_workspace_id=self.workspace.id,
            slack_user_id=slack_user_id
        ).first()

        slack_email = mapping.slack_email if mapping else None

        import requests
        requests.post(response_url, json={
            'response_type': 'ephemeral',
            'replace_original': False,
            'blocks': self.get_link_message_blocks(slack_user_id, slack_email)
        })

    def _send_decisions_list(self, payload: dict, user: User):
        """Send a list of recent decisions as an ephemeral message."""
        slack_user_id = payload.get('user', {}).get('id')

        tenant = self.workspace.tenant
        if not tenant:
            return

        decisions = ArchitectureDecision.query.filter_by(
            tenant_id=tenant.id,
            deleted_at=None
        ).order_by(ArchitectureDecision.created_at.desc()).limit(10).all()

        if not decisions:
            blocks = [{
                "type": "section",
                "text": {"type": "mrkdwn", "text": "No decisions found. Create your first one!"}
            }]
        else:
            blocks = [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "Recent Decisions"}
                }
            ]
            for decision in decisions:
                status_emoji = self._get_status_emoji(decision.status)
                display_id = decision.get_display_id() if hasattr(decision, 'get_display_id') else f"ADR-{decision.decision_number}"

                # Include space name if available
                space_info = ""
                # Show first space if decision belongs to any spaces
                if decision.spaces:
                    space_info = f" | Space: {decision.spaces[0].name}"

                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{status_emoji} *{display_id}*: {decision.title}\n_Status: {decision.status}{space_info}_"
                    },
                    "accessory": {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View"},
                        "action_id": f"view_decision_{decision.id}",
                        "value": str(decision.id)
                    }
                })

            # Add tip for filtering
            blocks.append({
                "type": "context",
                "elements": [{
                    "type": "mrkdwn",
                    "text": "_Tip: Use `/adr list mine` for your decisions or `/adr list space:[name]` for a specific space_"
                }]
            })

        # Try response_url first (for slash commands), fall back to chat.postEphemeral (for App Home)
        response_url = payload.get('response_url')
        if response_url:
            import requests
            requests.post(response_url, json={
                'response_type': 'ephemeral',
                'replace_original': False,
                'blocks': blocks
            })
        else:
            # App Home button clicks don't have response_url
            # Send as regular message to DM (ephemeral doesn't work in DMs)
            try:
                # Open DM channel with user
                dm_response = self.client.conversations_open(users=[slack_user_id])
                if dm_response.get('ok'):
                    channel_id = dm_response.get('channel', {}).get('id')
                    self.client.chat_postMessage(
                        channel=channel_id,
                        blocks=blocks,
                        text="Recent Decisions"
                    )
            except SlackApiError as e:
                logger.error(f"Failed to send decisions list: {e}")

    def _send_decision_detail(self, payload: dict, decision_id: int):
        """Send decision detail as a response."""
        decision = ArchitectureDecision.query.get(decision_id)
        if not decision:
            return None

        blocks = self._format_decision_detail_blocks(decision)
        slack_user_id = payload.get('user', {}).get('id')

        response_url = payload.get('response_url')
        if response_url:
            import requests
            requests.post(response_url, json={
                'response_type': 'ephemeral',
                'replace_original': False,
                'blocks': blocks
            })
        elif slack_user_id:
            # No response_url (e.g., from App Home View buttons)
            # Send as regular message to DM
            try:
                dm_response = self.client.conversations_open(users=[slack_user_id])
                if dm_response.get('ok'):
                    channel_id = dm_response.get('channel', {}).get('id')
                    self.client.chat_postMessage(
                        channel=channel_id,
                        blocks=blocks,
                        text=f"Decision: {decision.title}"
                    )
            except SlackApiError as e:
                logger.error(f"Failed to send decision detail: {e}")
        return None

    def _handle_message_action(self, payload: dict):
        """Handle message shortcuts (save as decision)."""
        callback_id = payload.get('callback_id')
        if callback_id == 'save_as_decision':
            return self._open_save_as_decision_modal(payload)
        return None

    def _open_save_as_decision_modal(self, payload: dict):
        """Open modal to save a message as a decision."""
        trigger_id = payload.get('trigger_id')
        message = payload.get('message', {})
        message_text = message.get('text', '')

        # Get user from mapping
        slack_user_id = payload.get('user', {}).get('id')
        mapping, user, needs_linking = self.get_or_link_user(slack_user_id)

        if needs_linking or not user:
            # Can't open modal for unlinked users
            return None

        view = {
            "type": "modal",
            "callback_id": "create_decision",
            "title": {"type": "plain_text", "text": "Save as Decision"},
            "submit": {"type": "plain_text", "text": "Create"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "private_metadata": str(user.id),
            "blocks": [
                {
                    "type": "input",
                    "block_id": "title_block",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "title",
                        "placeholder": {"type": "plain_text", "text": "What is this decision about?"},
                        "max_length": 255
                    },
                    "label": {"type": "plain_text", "text": "Title"}
                },
                {
                    "type": "input",
                    "block_id": "context_block",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "context",
                        "multiline": True,
                        "initial_value": message_text[:3000] if message_text else "",
                        "placeholder": {"type": "plain_text", "text": "What is the context?"},
                        "max_length": 3000
                    },
                    "label": {"type": "plain_text", "text": "Context"}
                },
                {
                    "type": "input",
                    "block_id": "decision_block",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "decision",
                        "multiline": True,
                        "placeholder": {"type": "plain_text", "text": "What is the decision?"},
                        "max_length": 3000
                    },
                    "label": {"type": "plain_text", "text": "Decision"}
                },
                {
                    "type": "input",
                    "block_id": "consequences_block",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "consequences",
                        "multiline": True,
                        "placeholder": {"type": "plain_text", "text": "What are the consequences?"},
                        "max_length": 3000
                    },
                    "label": {"type": "plain_text", "text": "Consequences"}
                },
                {
                    "type": "input",
                    "block_id": "status_block",
                    "optional": True,
                    "element": {
                        "type": "static_select",
                        "action_id": "status",
                        "initial_option": {
                            "text": {"type": "plain_text", "text": "Proposed"},
                            "value": "proposed"
                        },
                        "options": [
                            {"text": {"type": "plain_text", "text": "Proposed"}, "value": "proposed"},
                            {"text": {"type": "plain_text", "text": "Accepted"}, "value": "accepted"}
                        ]
                    },
                    "label": {"type": "plain_text", "text": "Status"}
                }
            ]
        }

        try:
            self.client.views_open(trigger_id=trigger_id, view=view)
        except SlackApiError as e:
            logger.error(f"Failed to open save as decision modal: {e}")

        return None

    # =========================================================================
    # NOTIFICATIONS
    # =========================================================================

    def post_decision_notification(self, decision: ArchitectureDecision, event_type: str):
        """Post a notification about a decision to the default channel."""
        if not self.workspace.notifications_enabled:
            return False

        if event_type == 'created' and not self.workspace.notify_on_create:
            return False

        if event_type == 'status_changed' and not self.workspace.notify_on_status_change:
            return False

        channel = self.workspace.default_channel_id
        if not channel:
            logger.debug(f"No default channel configured for workspace {self.workspace.workspace_id}")
            return False

        blocks = self._format_notification_blocks(decision, event_type)

        try:
            self.client.chat_postMessage(
                channel=channel,
                blocks=blocks,
                text=f"Decision {decision.get_display_id() if hasattr(decision, 'get_display_id') else 'ADR-' + str(decision.decision_number)}: {decision.title}"
            )
            self.update_activity()
            return True
        except SlackApiError as e:
            logger.error(f"Failed to post Slack notification: {e}")
            return False

    def _send_creation_notification(self, decision: ArchitectureDecision):
        """Send notification for a newly created decision."""
        if self.workspace.notifications_enabled and self.workspace.notify_on_create:
            self.post_decision_notification(decision, 'created')

    def send_test_notification(self):
        """Send a test notification to verify configuration."""
        channel = self.workspace.default_channel_id
        if not channel:
            raise ValueError("No default channel configured")

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": ":white_check_mark: *Test Notification*\n\nSlack integration is working correctly!"
                }
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"Sent from Decision Records at {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"}
                ]
            }
        ]

        self.client.chat_postMessage(
            channel=channel,
            blocks=blocks,
            text="Test notification from Decision Records"
        )
        self.update_activity()

    # =========================================================================
    # DM HELPERS
    # =========================================================================

    def _open_dm_channel(self, user_id: str) -> str:
        """Open a DM channel with a user and return the channel ID.

        Args:
            user_id: The Slack user ID to open a DM with

        Returns:
            The DM channel ID, or None if failed
        """
        try:
            result = self.client.conversations_open(users=[user_id])
            if result.get('ok'):
                return result.get('channel', {}).get('id')
            else:
                logger.warning(f"conversations.open failed: {result.get('error')}")
                return None
        except SlackApiError as e:
            logger.warning(f"Failed to open DM channel with {user_id}: {e}")
            return None

    # =========================================================================
    # FORMATTING HELPERS
    # =========================================================================

    def _get_status_emoji(self, status: str) -> str:
        """Get emoji for decision status."""
        return {
            'proposed': ':memo:',
            'accepted': ':white_check_mark:',
            'archived': ':file_folder:',
            'superseded': ':arrows_counterclockwise:'
        }.get(status, ':memo:')

    def _format_decision_detail_blocks(self, decision: ArchitectureDecision) -> list:
        """Format a decision as detailed Block Kit blocks."""
        status_emoji = self._get_status_emoji(decision.status)
        display_id = decision.get_display_id() if hasattr(decision, 'get_display_id') else f"ADR-{decision.decision_number}"

        base_url = os.environ.get('APP_BASE_URL', 'https://decisionrecords.org')
        tenant = self.workspace.tenant
        decision_url = f"{base_url}/{tenant.domain if tenant else ''}/decisions/{decision.id}"

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{display_id}: {decision.title[:100]}"}
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Status:* {status_emoji} {decision.status.title()}"},
                    {"type": "mrkdwn", "text": f"*Created:* {decision.created_at.strftime('%Y-%m-%d')}"}
                ]
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Context:*\n{decision.context[:500]}{'...' if len(decision.context) > 500 else ''}"}
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Decision:*\n{decision.decision[:500]}{'...' if len(decision.decision) > 500 else ''}"}
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Consequences:*\n{decision.consequences[:500]}{'...' if len(decision.consequences) > 500 else ''}"}
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View in Browser"},
                        "url": decision_url,
                        "action_id": "open_in_browser"
                    }
                ]
            }
        ]
        return blocks

    def _format_notification_blocks(self, decision: ArchitectureDecision, event_type: str) -> list:
        """Format decision notification as Block Kit blocks."""
        status_emoji = self._get_status_emoji(decision.status)
        display_id = decision.get_display_id() if hasattr(decision, 'get_display_id') else f"ADR-{decision.decision_number}"

        event_text = {
            'created': ':sparkles: New decision record created',
            'updated': ':pencil2: Decision record updated',
            'status_changed': ':arrows_counterclockwise: Decision status changed'
        }.get(event_type, 'Decision updated')

        base_url = os.environ.get('APP_BASE_URL', 'https://decisionrecords.org')
        tenant = self.workspace.tenant
        decision_url = f"{base_url}/{tenant.domain if tenant else ''}/decisions/{decision.id}"

        creator_name = decision.creator.name if hasattr(decision, 'creator') and decision.creator else 'Unknown'

        return [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": event_text}
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*<{decision_url}|{display_id}: {decision.title}>*"
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Status:* {status_emoji} {decision.status.title()}"},
                    {"type": "mrkdwn", "text": f"*By:* {creator_name}"}
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Context:*\n{decision.context[:200]}{'...' if len(decision.context) > 200 else ''}"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View Decision"},
                        "url": decision_url,
                        "action_id": "view_decision_web"
                    }
                ]
            }
        ]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_slack_service_for_tenant(tenant_id: int) -> SlackService:
    """Get SlackService for a tenant, or None if not configured."""
    workspace = SlackWorkspace.query.filter_by(
        tenant_id=tenant_id,
        is_active=True
    ).first()
    if workspace:
        return SlackService(workspace)
    return None


def notify_decision_created(decision: ArchitectureDecision):
    """Notify Slack about a new decision (called from app.py)."""
    if not decision.tenant_id:
        return
    service = get_slack_service_for_tenant(decision.tenant_id)
    if service:
        try:
            service.post_decision_notification(decision, 'created')
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")


def notify_decision_status_changed(decision: ArchitectureDecision):
    """Notify Slack about a decision status change (called from app.py)."""
    if not decision.tenant_id:
        return
    service = get_slack_service_for_tenant(decision.tenant_id)
    if service:
        try:
            service.post_decision_notification(decision, 'status_changed')
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
