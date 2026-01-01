"""
Microsoft Teams integration service module.

Handles Bot Framework activities, Adaptive Cards, user linking, and business logic
for the Decision Records Teams app.
"""
import logging
import os
import json
import httpx
from datetime import datetime, timezone

from models import (
    db, TeamsWorkspace, TeamsUserMapping, TeamsConversationReference,
    User, ArchitectureDecision, Tenant, TenantMembership, Space
)
from teams_security import (
    get_teams_bot_app_id, get_teams_bot_app_secret, get_teams_bot_tenant_id,
    generate_teams_link_token
)
from teams_cards import (
    build_menu_card, build_help_card, build_decision_list_card,
    build_decision_detail_card, build_create_decision_form_card,
    build_status_change_form_card, build_link_account_card,
    build_notification_card, build_search_results_card,
    build_success_card, build_error_card, build_welcome_card
)

logger = logging.getLogger(__name__)


class TeamsService:
    """Service for Teams Bot Framework interactions."""

    def __init__(self, workspace: TeamsWorkspace):
        self.workspace = workspace
        self._access_token = None
        self._token_expires_at = None

    async def get_bot_token(self) -> str:
        """
        Acquire access token for Bot Framework API calls.

        Uses client credentials flow to get a token for the Bot Framework API.
        """
        now = datetime.now(timezone.utc)

        # Return cached token if still valid
        if self._access_token and self._token_expires_at and now < self._token_expires_at:
            return self._access_token

        app_id = get_teams_bot_app_id()
        app_secret = get_teams_bot_app_secret()
        tenant_id = get_teams_bot_tenant_id() or 'botframework.com'

        if not app_id or not app_secret:
            logger.error("Teams Bot credentials not configured")
            raise ValueError("Teams Bot credentials not configured")

        try:
            async with httpx.AsyncClient() as client:
                # For Bot Framework, we use the botframework.com tenant
                response = await client.post(
                    f'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token',
                    data={
                        'client_id': app_id,
                        'client_secret': app_secret,
                        'grant_type': 'client_credentials',
                        'scope': 'https://api.botframework.com/.default'
                    }
                )

                if response.status_code != 200:
                    logger.error(f"Failed to get bot token: {response.text}")
                    raise ValueError("Failed to acquire bot token")

                token_data = response.json()
                self._access_token = token_data.get('access_token')

                # Cache token (subtract 5 minutes for safety margin)
                expires_in = token_data.get('expires_in', 3600) - 300
                from datetime import timedelta
                self._token_expires_at = now + timedelta(seconds=expires_in)

                return self._access_token

        except Exception as e:
            logger.error(f"Failed to acquire bot token: {e}")
            raise

    def update_activity(self):
        """Update last activity timestamp."""
        self.workspace.last_activity_at = datetime.now(timezone.utc)
        db.session.commit()

    # =========================================================================
    # USER LINKING
    # =========================================================================

    def get_or_link_user(self, aad_object_id: str, upn: str = None, display_name: str = None):
        """
        Get or create a user mapping for a Teams user.

        Args:
            aad_object_id: Azure AD object ID of the user
            upn: User Principal Name (often the email)
            display_name: User's display name

        Returns tuple: (TeamsUserMapping, User or None, needs_linking: bool)
        """
        # Check for existing mapping
        mapping = TeamsUserMapping.query.filter_by(
            teams_workspace_id=self.workspace.id,
            aad_object_id=aad_object_id
        ).first()

        if mapping and mapping.user_id:
            # Already linked
            user = db.session.get(User, mapping.user_id)
            return mapping, user, False

        # Extract email from UPN (UPN is usually the email for corporate users)
        aad_email = upn if upn and '@' in upn else None

        # Create or update mapping
        if not mapping:
            mapping = TeamsUserMapping(
                teams_workspace_id=self.workspace.id,
                aad_object_id=aad_object_id,
                aad_user_principal_name=upn,
                aad_email=aad_email,
                aad_display_name=display_name
            )
            db.session.add(mapping)
        else:
            if upn and not mapping.aad_user_principal_name:
                mapping.aad_user_principal_name = upn
            if aad_email and not mapping.aad_email:
                mapping.aad_email = aad_email
            if display_name and not mapping.aad_display_name:
                mapping.aad_display_name = display_name

        # Try auto-link by email or UPN
        if aad_email:
            tenant = self.workspace.tenant
            if tenant:
                # Find user with matching email in this tenant
                user = User.query.filter_by(email=aad_email).first()
                if user:
                    # Check if user is member of this tenant
                    membership = TenantMembership.query.filter_by(
                        user_id=user.id,
                        tenant_id=tenant.id
                    ).first()
                    if membership:
                        mapping.user_id = user.id
                        mapping.linked_at = datetime.now(timezone.utc)
                        mapping.link_method = 'auto_email'
                        db.session.commit()
                        return mapping, user, False

        db.session.commit()
        return mapping, None, True

    # =========================================================================
    # MESSAGE HANDLING
    # =========================================================================

    async def handle_message(self, activity: dict) -> dict:
        """
        Handle incoming message activity.

        Messages can be:
        - @mention commands: @DecisionRecords create/list/view/search/help
        - Direct messages to the bot

        Returns an Adaptive Card response.
        """
        text = activity.get('text', '').strip()
        from_user = activity.get('from', {})

        # Remove bot mention from text
        text = self._remove_mention(text, activity)

        # Parse command
        parts = text.split(maxsplit=1)
        command = parts[0].lower() if parts else ''
        args = parts[1] if len(parts) > 1 else ''

        # Check user linking
        mapping, user, needs_linking = self.get_or_link_user(
            from_user.get('aadObjectId', ''),
            from_user.get('userPrincipalName'),
            from_user.get('name')
        )

        # If user needs linking and command requires auth, show link card
        if needs_linking and command not in ['', 'help']:
            return build_link_account_card(
                self.workspace.id,
                from_user.get('aadObjectId', ''),
                from_user.get('userPrincipalName')
            )

        # Route to handler
        handlers = {
            '': self._handle_menu,
            'help': self._handle_help,
            'list': self._handle_list,
            'view': self._handle_view,
            'search': self._handle_search,
            'create': self._handle_create,
        }

        handler = handlers.get(command, self._handle_menu)
        return await handler(args, user, activity)

    def _remove_mention(self, text: str, activity: dict) -> str:
        """Remove bot @mention from message text."""
        entities = activity.get('entities', [])
        for entity in entities:
            if entity.get('type') == 'mention':
                mentioned = entity.get('mentioned', {})
                # Check if this mention is the bot
                bot_id = get_teams_bot_app_id()
                if mentioned.get('id') == bot_id or mentioned.get('name', '').lower() == 'decisionrecords':
                    # Remove the mention text
                    mention_text = entity.get('text', '')
                    text = text.replace(mention_text, '').strip()
        return text

    async def _handle_menu(self, args: str, user, activity: dict) -> dict:
        """Handle empty command - show interactive menu."""
        return build_menu_card()

    async def _handle_help(self, args: str, user, activity: dict) -> dict:
        """Handle help command."""
        return build_help_card()

    async def _handle_list(self, args: str, user, activity: dict) -> dict:
        """Handle list command."""
        tenant = self.workspace.tenant
        if not tenant:
            return build_error_card("Not Configured", "Teams workspace is not connected to a Decision Records organization.")

        # Parse status filter
        status_filter = args.strip().lower() if args else None
        valid_statuses = ['proposed', 'accepted', 'archived', 'superseded']

        query = ArchitectureDecision.query.filter_by(tenant_id=tenant.id)

        if status_filter and status_filter in valid_statuses:
            query = query.filter_by(status=status_filter)
            title = f"{status_filter.capitalize()} Decisions"
        else:
            title = "Recent Decisions"

        decisions = query.order_by(ArchitectureDecision.created_at.desc()).limit(10).all()

        return build_decision_list_card(decisions, title=title)

    async def _handle_view(self, args: str, user, activity: dict) -> dict:
        """Handle view command."""
        tenant = self.workspace.tenant
        if not tenant:
            return build_error_card("Not Configured", "Teams workspace is not connected to a Decision Records organization.")

        if not args:
            return build_error_card("Missing ID", "Please provide a decision ID. Usage: `view <id>`")

        # Parse decision ID (could be number or display ID like "ADR-42")
        decision_id = args.strip()

        # Try to find by decision number
        try:
            decision_number = int(decision_id.replace('ADR-', '').replace('adr-', '').replace('#', ''))
            decision = ArchitectureDecision.query.filter_by(
                tenant_id=tenant.id,
                decision_number=decision_number
            ).first()
        except ValueError:
            decision = None

        if not decision:
            return build_error_card("Not Found", f"Decision '{decision_id}' not found.")

        return build_decision_detail_card(decision)

    async def _handle_search(self, args: str, user, activity: dict) -> dict:
        """Handle search command."""
        tenant = self.workspace.tenant
        if not tenant:
            return build_error_card("Not Configured", "Teams workspace is not connected to a Decision Records organization.")

        if not args:
            return build_error_card("Missing Query", "Please provide a search query. Usage: `search <query>`")

        query = args.strip()

        # Simple search by title and context
        decisions = ArchitectureDecision.query.filter(
            ArchitectureDecision.tenant_id == tenant.id,
            db.or_(
                ArchitectureDecision.title.ilike(f'%{query}%'),
                ArchitectureDecision.context.ilike(f'%{query}%'),
                ArchitectureDecision.decision.ilike(f'%{query}%')
            )
        ).order_by(ArchitectureDecision.created_at.desc()).limit(10).all()

        return build_search_results_card(decisions, query)

    async def _handle_create(self, args: str, user, activity: dict) -> dict:
        """Handle create command - return task module fetch response."""
        # This should trigger a task module, but for direct command,
        # we'll show the create form as an inline card
        return build_create_decision_form_card()

    # =========================================================================
    # INVOKE HANDLING (Task Modules, Card Actions)
    # =========================================================================

    async def handle_invoke(self, activity: dict) -> dict:
        """
        Handle invoke activities (task modules, adaptive card actions).

        Invoke types:
        - task/fetch: Open task module (modal)
        - task/submit: Handle task module submission
        - adaptiveCard/action: Handle Action.Execute from cards
        - composeExtension/fetchTask: Message extension action
        - composeExtension/submitAction: Message extension submission
        """
        invoke_name = activity.get('name', '')
        value = activity.get('value', {})
        from_user = activity.get('from', {})

        if invoke_name == 'task/fetch':
            return await self._handle_task_fetch(value, activity, from_user)
        elif invoke_name == 'task/submit':
            return await self._handle_task_submit(value, activity, from_user)
        elif invoke_name == 'adaptiveCard/action':
            return await self._handle_card_action(value, activity, from_user)
        elif invoke_name.startswith('composeExtension/'):
            return await self._handle_compose_extension(invoke_name, value, activity, from_user)

        return {'status': 200}

    async def _handle_task_fetch(self, value: dict, activity: dict, from_user: dict) -> dict:
        """Return task module (modal) content."""
        data = value.get('data', {})
        action = data.get('action', '')

        if action == 'open_create_modal':
            # Get users for owner selection
            tenant = self.workspace.tenant
            users = []
            if tenant:
                memberships = TenantMembership.query.filter_by(tenant_id=tenant.id).limit(50).all()
                users = [m.user for m in memberships if m.user]

            card = build_create_decision_form_card(users=users)
            return self._wrap_task_module_response("Create Decision", card)

        elif action == 'open_status_modal':
            decision_id = data.get('decision_id')
            if decision_id:
                decision = db.session.get(ArchitectureDecision, decision_id)
                if decision:
                    card = build_status_change_form_card(decision)
                    return self._wrap_task_module_response("Change Status", card)

        return {'status': 200}

    async def _handle_task_submit(self, value: dict, activity: dict, from_user: dict) -> dict:
        """Handle task module form submission."""
        data = value.get('data', {})
        action = data.get('action', '')

        if action == 'submit_decision':
            return await self._create_decision_from_form(data, from_user)
        elif action == 'submit_status_change':
            return await self._change_status_from_form(data, from_user)

        return {'status': 200}

    async def _handle_card_action(self, value: dict, activity: dict, from_user: dict) -> dict:
        """Handle Adaptive Card Action.Submit."""
        action = value.get('action', '')

        # Check user linking for actions that require it
        if action not in ['show_help']:
            mapping, user, needs_linking = self.get_or_link_user(
                from_user.get('aadObjectId', ''),
                from_user.get('userPrincipalName'),
                from_user.get('name')
            )

            if needs_linking:
                card = build_link_account_card(
                    self.workspace.id,
                    from_user.get('aadObjectId', ''),
                    from_user.get('userPrincipalName')
                )
                return self._wrap_card_response(card)

        if action == 'open_create_modal':
            return self._wrap_task_fetch_response()
        elif action == 'list_decisions':
            card = await self._handle_list('', None, activity)
            return self._wrap_card_response(card)
        elif action == 'my_decisions':
            card = await self._handle_my_decisions(from_user, activity)
            return self._wrap_card_response(card)
        elif action == 'show_help':
            card = build_help_card()
            return self._wrap_card_response(card)
        elif action == 'view_decision':
            decision_id = value.get('decision_id')
            if decision_id:
                decision = db.session.get(ArchitectureDecision, decision_id)
                if decision:
                    card = build_decision_detail_card(decision)
                    return self._wrap_card_response(card)
        elif action == 'open_status_modal':
            return self._wrap_task_fetch_response()

        return {'status': 200}

    async def _handle_my_decisions(self, from_user: dict, activity: dict) -> dict:
        """Handle my decisions action."""
        tenant = self.workspace.tenant
        if not tenant:
            return build_error_card("Not Configured", "Teams workspace is not connected to a Decision Records organization.")

        mapping, user, needs_linking = self.get_or_link_user(
            from_user.get('aadObjectId', ''),
            from_user.get('userPrincipalName'),
            from_user.get('name')
        )

        if not user:
            return build_error_card("Not Linked", "Your account is not linked. Please link your account first.")

        decisions = ArchitectureDecision.query.filter(
            ArchitectureDecision.tenant_id == tenant.id,
            db.or_(
                ArchitectureDecision.owner_id == user.id,
                ArchitectureDecision.created_by_id == user.id
            )
        ).order_by(ArchitectureDecision.created_at.desc()).limit(10).all()

        return build_decision_list_card(decisions, title="My Decisions")

    async def _handle_compose_extension(self, invoke_name: str, value: dict, activity: dict, from_user: dict) -> dict:
        """Handle compose extension (message extension) actions."""
        if invoke_name == 'composeExtension/fetchTask':
            # Check if this is from a message context
            message_payload = value.get('messagePayload', {})
            prefill_context = message_payload.get('body', {}).get('content', '')

            card = build_create_decision_form_card(prefill_context=prefill_context)
            return self._wrap_task_module_response("Create Decision from Message", card)

        elif invoke_name == 'composeExtension/submitAction':
            return await self._create_decision_from_form(value.get('data', {}), from_user)

        return {'status': 200}

    async def _create_decision_from_form(self, data: dict, from_user: dict) -> dict:
        """Create a decision from form submission."""
        tenant = self.workspace.tenant
        if not tenant:
            return self._wrap_task_submit_error("Teams workspace is not connected to an organization.")

        # Get linked user
        mapping, user, needs_linking = self.get_or_link_user(
            from_user.get('aadObjectId', ''),
            from_user.get('userPrincipalName'),
            from_user.get('name')
        )

        if needs_linking:
            return self._wrap_task_submit_error("Please link your account first.")

        # Get form data
        title = data.get('title', '').strip()
        if not title:
            return self._wrap_task_submit_error("Title is required.")

        context = data.get('context', '').strip()
        decision_text = data.get('decision', '').strip()
        consequences = data.get('consequences', '').strip()
        status = data.get('status', 'proposed')
        owner_id = data.get('owner_id')

        # Get next decision number
        max_number = db.session.query(db.func.max(ArchitectureDecision.decision_number)).filter_by(
            tenant_id=tenant.id
        ).scalar() or 0

        # Get default space
        default_space = Space.query.filter_by(tenant_id=tenant.id, is_default=True).first()

        # Create decision
        decision = ArchitectureDecision(
            tenant_id=tenant.id,
            space_id=default_space.id if default_space else None,
            decision_number=max_number + 1,
            title=title,
            context=context,
            decision=decision_text,
            consequences=consequences,
            status=status,
            created_by_id=user.id if user else None,
            owner_id=int(owner_id) if owner_id else None
        )

        db.session.add(decision)
        db.session.commit()

        self.update_activity()

        # Build success card
        card = build_success_card(
            "Decision Created",
            f"Your decision has been created successfully.",
            decision=decision
        )

        return self._wrap_task_submit_success(card)

    async def _change_status_from_form(self, data: dict, from_user: dict) -> dict:
        """Change decision status from form submission."""
        decision_id = data.get('decision_id')
        new_status = data.get('new_status')

        if not decision_id or not new_status:
            return self._wrap_task_submit_error("Missing decision ID or status.")

        decision = db.session.get(ArchitectureDecision, decision_id)
        if not decision:
            return self._wrap_task_submit_error("Decision not found.")

        old_status = decision.status
        decision.status = new_status
        db.session.commit()

        self.update_activity()

        card = build_success_card(
            "Status Updated",
            f"Decision status changed from {old_status} to {new_status}.",
            decision=decision
        )

        return self._wrap_task_submit_success(card)

    # =========================================================================
    # CONVERSATION UPDATES
    # =========================================================================

    async def handle_conversation_update(self, activity: dict) -> dict:
        """
        Handle conversation update activities.

        This includes:
        - Bot added to team/conversation
        - Bot removed from team/conversation
        - Members added/removed
        """
        members_added = activity.get('membersAdded', [])
        members_removed = activity.get('membersRemoved', [])
        bot_id = get_teams_bot_app_id()

        for member in members_added:
            if member.get('id') == bot_id or member.get('aadObjectId') == bot_id:
                # Bot was added - store conversation reference and send welcome
                await self._store_conversation_reference(activity)
                return build_welcome_card()

        for member in members_removed:
            if member.get('id') == bot_id or member.get('aadObjectId') == bot_id:
                # Bot was removed - cleanup conversation reference
                await self._remove_conversation_reference(activity)

        return {'status': 200}

    async def _store_conversation_reference(self, activity: dict):
        """Store conversation reference for proactive messaging."""
        conversation = activity.get('conversation', {})
        channel_data = activity.get('channelData', {})

        conversation_id = conversation.get('id', '')
        channel_id = channel_data.get('channel', {}).get('id')
        team_id = channel_data.get('team', {}).get('id')

        # Determine context type
        if team_id:
            context_type = 'channel'
        elif conversation.get('conversationType') == 'groupChat':
            context_type = 'group'
        else:
            context_type = 'personal'

        # Build conversation reference
        reference = {
            'activityId': activity.get('id'),
            'bot': activity.get('recipient'),
            'channelId': activity.get('channelId'),
            'conversation': conversation,
            'serviceUrl': activity.get('serviceUrl'),
            'user': activity.get('from')
        }

        # Check for existing reference
        existing = TeamsConversationReference.query.filter_by(
            teams_workspace_id=self.workspace.id,
            conversation_id=conversation_id
        ).first()

        if existing:
            existing.reference_json = json.dumps(reference)
            existing.updated_at = datetime.now(timezone.utc)
        else:
            conv_ref = TeamsConversationReference(
                teams_workspace_id=self.workspace.id,
                conversation_id=conversation_id,
                channel_id=channel_id,
                team_id=team_id,
                reference_json=json.dumps(reference),
                context_type=context_type
            )
            db.session.add(conv_ref)

        db.session.commit()

    async def _remove_conversation_reference(self, activity: dict):
        """Remove conversation reference when bot is removed."""
        conversation = activity.get('conversation', {})
        conversation_id = conversation.get('id', '')

        TeamsConversationReference.query.filter_by(
            teams_workspace_id=self.workspace.id,
            conversation_id=conversation_id
        ).delete()
        db.session.commit()

    # =========================================================================
    # PROACTIVE MESSAGING (Notifications)
    # =========================================================================

    async def send_notification(self, decision: ArchitectureDecision, event_type: str) -> bool:
        """
        Send proactive notification to configured Teams channel.

        Args:
            decision: The decision to notify about
            event_type: 'created' or 'status_changed'

        Returns:
            True if notification was sent, False otherwise
        """
        if not self.workspace.notifications_enabled:
            return False

        if event_type == 'created' and not self.workspace.notify_on_create:
            return False
        if event_type == 'status_changed' and not self.workspace.notify_on_status_change:
            return False

        # Get conversation reference for default channel
        conv_ref = TeamsConversationReference.query.filter_by(
            teams_workspace_id=self.workspace.id,
            channel_id=self.workspace.default_channel_id
        ).first()

        if not conv_ref:
            logger.warning(f"No conversation reference for channel {self.workspace.default_channel_id}")
            return False

        # Build notification card
        card = build_notification_card(decision, event_type)

        # Send proactive message
        reference = json.loads(conv_ref.reference_json)
        success = await self._send_proactive_message(reference, card)

        if success:
            self.update_activity()

        return success

    async def _send_proactive_message(self, reference: dict, card: dict) -> bool:
        """Send a proactive message using stored conversation reference."""
        try:
            token = await self.get_bot_token()
            service_url = reference.get('serviceUrl', self.workspace.service_url)
            conversation_id = reference.get('conversation', {}).get('id')

            if not service_url or not conversation_id:
                logger.error("Missing service URL or conversation ID for proactive message")
                return False

            url = f"{service_url}v3/conversations/{conversation_id}/activities"

            activity = {
                'type': 'message',
                'attachments': [{
                    'contentType': 'application/vnd.microsoft.card.adaptive',
                    'content': card
                }]
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=activity,
                    headers={
                        'Authorization': f'Bearer {token}',
                        'Content-Type': 'application/json'
                    }
                )

                if response.status_code not in [200, 201]:
                    logger.error(f"Failed to send proactive message: {response.text}")
                    return False

                return True

        except Exception as e:
            logger.error(f"Failed to send proactive message: {e}")
            return False

    # =========================================================================
    # RESPONSE HELPERS
    # =========================================================================

    def _wrap_task_module_response(self, title: str, card: dict) -> dict:
        """Wrap an Adaptive Card as a task module response."""
        return {
            'task': {
                'type': 'continue',
                'value': {
                    'title': title,
                    'card': {
                        'contentType': 'application/vnd.microsoft.card.adaptive',
                        'content': card
                    }
                }
            }
        }

    def _wrap_task_fetch_response(self) -> dict:
        """Return a response that triggers a task/fetch."""
        return {
            'task': {
                'type': 'continue',
                'value': {}
            }
        }

    def _wrap_task_submit_success(self, card: dict) -> dict:
        """Wrap a success card as task module submit response."""
        return {
            'task': {
                'type': 'continue',
                'value': {
                    'title': 'Success',
                    'card': {
                        'contentType': 'application/vnd.microsoft.card.adaptive',
                        'content': card
                    }
                }
            }
        }

    def _wrap_task_submit_error(self, message: str) -> dict:
        """Wrap an error message as task module submit response."""
        card = build_error_card("Error", message)
        return {
            'task': {
                'type': 'continue',
                'value': {
                    'title': 'Error',
                    'card': {
                        'contentType': 'application/vnd.microsoft.card.adaptive',
                        'content': card
                    }
                }
            }
        }

    def _wrap_card_response(self, card: dict) -> dict:
        """Wrap a card as an Adaptive Card action response."""
        return {
            'statusCode': 200,
            'type': 'application/vnd.microsoft.card.adaptive',
            'value': card
        }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_teams_service_for_tenant(tenant_id: int) -> TeamsService:
    """
    Get a TeamsService instance for a tenant.

    Args:
        tenant_id: The Decision Records tenant ID

    Returns:
        TeamsService instance or None if not configured
    """
    workspace = TeamsWorkspace.query.filter_by(
        tenant_id=tenant_id,
        is_active=True,
        status=TeamsWorkspace.STATUS_ACTIVE
    ).first()

    if not workspace:
        return None

    return TeamsService(workspace)


async def notify_decision_created(decision: ArchitectureDecision):
    """
    Send notification when a decision is created.

    Called from the main app when a decision is created.
    """
    service = get_teams_service_for_tenant(decision.tenant_id)
    if service:
        await service.send_notification(decision, 'created')


async def notify_decision_status_changed(decision: ArchitectureDecision):
    """
    Send notification when a decision status changes.

    Called from the main app when a decision status is updated.
    """
    service = get_teams_service_for_tenant(decision.tenant_id)
    if service:
        await service.send_notification(decision, 'status_changed')
