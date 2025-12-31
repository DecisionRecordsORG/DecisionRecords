"""
AI-specific Slack command handlers.

Handles AI-powered natural language queries for the Slack bot.
All AI features require proper configuration at system, tenant, and user levels.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List

from models import (
    db, User, Tenant, ArchitectureDecision, SlackWorkspace,
    AIChannel, AIAction
)
from ai.config import AIConfig
from ai.interaction_log import AIInteractionLogger
from ai.slack.nl_query import NLQueryParser, QueryIntent, format_search_query, build_search_filters

logger = logging.getLogger(__name__)


class SlackAIHandler:
    """
    Handler for AI-powered Slack commands.

    Integrates with the existing SlackService to provide:
    - Natural language search
    - AI summarization (future - requires LLM)
    - AI explanation (future - requires LLM)
    """

    def __init__(self, workspace: SlackWorkspace, tenant: Tenant):
        self.workspace = workspace
        self.tenant = tenant

    def is_ai_available(self, user: User) -> Tuple[bool, Optional[str]]:
        """
        Check if AI features are available for this user.

        Returns:
            Tuple of (is_available, error_message)
        """
        # Check system-level
        if not AIConfig.get_system_ai_enabled():
            return False, "AI features are not enabled for this system."

        if not AIConfig.get_system_slack_bot_enabled():
            return False, "Slack AI features are not enabled for this system."

        # Check tenant-level
        if not self.tenant.ai_features_enabled:
            return False, "AI features are not enabled for your organization."

        if not self.tenant.ai_slack_queries_enabled:
            return False, "Slack AI queries are not enabled for your organization."

        # Check user-level opt-out
        if AIConfig.get_user_ai_opt_out(user, self.tenant):
            return False, "You have opted out of AI features. Update your preferences to use AI."

        return True, None

    def handle_ai_search(
        self,
        query: str,
        user: User,
        log_interaction: bool = True
    ) -> Tuple[Optional[Dict[str, Any]], bool]:
        """
        Handle an AI-powered natural language search.

        Args:
            query: The natural language search query
            user: The user making the request
            log_interaction: Whether to log this interaction

        Returns:
            Tuple of (response_dict, is_ephemeral)
        """
        start_time = datetime.now(timezone.utc)

        # Check AI availability
        is_available, error_msg = self.is_ai_available(user)
        if not is_available:
            return {
                'response_type': 'ephemeral',
                'text': f":no_entry: {error_msg}"
            }, True

        # Parse the natural language query
        parsed = NLQueryParser.parse(query)

        # Handle different intents
        if parsed['intent'] == QueryIntent.GET and parsed['decision_id']:
            return self._handle_get(parsed, user, start_time, log_interaction)
        elif parsed['intent'] == QueryIntent.SUMMARIZE:
            return self._handle_summarize(parsed, user, start_time, log_interaction)
        elif parsed['intent'] == QueryIntent.EXPLAIN:
            return self._handle_explain(parsed, user, start_time, log_interaction)
        elif parsed['intent'] == QueryIntent.LIST:
            return self._handle_list(parsed, user, start_time, log_interaction)
        else:
            return self._handle_search(parsed, user, start_time, log_interaction)

    def _handle_search(
        self,
        parsed: Dict[str, Any],
        user: User,
        start_time: datetime,
        log_interaction: bool
    ) -> Tuple[Dict[str, Any], bool]:
        """Handle a search intent."""
        # Build the search query
        search_text = format_search_query(parsed)
        filters = build_search_filters(parsed)

        # Build database query
        query = ArchitectureDecision.query.filter(
            ArchitectureDecision.tenant_id == self.tenant.id,
            ArchitectureDecision.deleted_at == None
        )

        # Apply text search
        if search_text:
            search_pattern = f"%{search_text}%"
            query = query.filter(
                db.or_(
                    ArchitectureDecision.title.ilike(search_pattern),
                    ArchitectureDecision.context.ilike(search_pattern),
                    ArchitectureDecision.decision.ilike(search_pattern),
                    ArchitectureDecision.consequences.ilike(search_pattern)
                )
            )

        # Apply filters
        if filters.get('status'):
            query = query.filter(ArchitectureDecision.status == filters['status'])

        if filters.get('created_after'):
            query = query.filter(ArchitectureDecision.created_at >= filters['created_after'])

        if filters.get('created_before'):
            query = query.filter(ArchitectureDecision.created_at <= filters['created_before'])

        # Execute query
        decisions = query.order_by(ArchitectureDecision.created_at.desc()).limit(10).all()

        # Calculate duration
        duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

        # Log interaction
        if log_interaction and self.tenant.ai_log_interactions:
            self._log_interaction(
                action=AIAction.SEARCH,
                user=user,
                query_text=parsed['original_query'],
                decision_ids=[d.id for d in decisions],
                duration_ms=duration_ms
            )

        # Format response
        if not decisions:
            return {
                'response_type': 'ephemeral',
                'text': f':mag: No decisions found matching "{parsed["original_query"]}".\n\n'
                        f'_Try broader terms or check spelling._'
            }, True

        blocks = self._format_search_results(decisions, parsed['original_query'])
        return {'response_type': 'ephemeral', 'blocks': blocks}, True

    def _handle_get(
        self,
        parsed: Dict[str, Any],
        user: User,
        start_time: datetime,
        log_interaction: bool
    ) -> Tuple[Dict[str, Any], bool]:
        """Handle a get intent (retrieve specific decision)."""
        decision_id = parsed['decision_id']

        # Parse the decision number from ADR-XXX format
        import re
        match = re.search(r'\d+', decision_id)
        if not match:
            return {
                'response_type': 'ephemeral',
                'text': f':warning: Could not parse decision ID: {decision_id}'
            }, True

        number = int(match.group())

        # Find the decision
        decision = ArchitectureDecision.query.filter_by(
            tenant_id=self.tenant.id,
            decision_number=number,
            deleted_at=None
        ).first()

        duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

        if not decision:
            return {
                'response_type': 'ephemeral',
                'text': f':warning: Decision {decision_id} not found.'
            }, True

        # Log interaction
        if log_interaction and self.tenant.ai_log_interactions:
            self._log_interaction(
                action=AIAction.READ,
                user=user,
                query_text=parsed['original_query'],
                decision_ids=[decision.id],
                duration_ms=duration_ms
            )

        # Return decision detail - delegate to main service
        return {
            'response_type': 'ephemeral',
            'text': f':page_facing_up: Found decision {decision_id}',
            '_decision_id': decision.id,  # Signal to caller to show detail
            '_show_detail': True
        }, True

    def _handle_summarize(
        self,
        parsed: Dict[str, Any],
        user: User,
        start_time: datetime,
        log_interaction: bool
    ) -> Tuple[Dict[str, Any], bool]:
        """
        Handle a summarize intent.

        Note: Full LLM-powered summarization requires Phase 5.
        For now, returns a structured summary of the decision fields.
        """
        if not parsed['decision_id']:
            return {
                'response_type': 'ephemeral',
                'text': ':warning: Please specify a decision to summarize.\n'
                        '_Example: `/decision ai summarize ADR-42`_'
            }, True

        # Get the decision
        import re
        match = re.search(r'\d+', parsed['decision_id'])
        if not match:
            return {
                'response_type': 'ephemeral',
                'text': f':warning: Could not parse decision ID: {parsed["decision_id"]}'
            }, True

        number = int(match.group())
        decision = ArchitectureDecision.query.filter_by(
            tenant_id=self.tenant.id,
            decision_number=number,
            deleted_at=None
        ).first()

        duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

        if not decision:
            return {
                'response_type': 'ephemeral',
                'text': f':warning: Decision {parsed["decision_id"]} not found.'
            }, True

        # Log interaction
        if log_interaction and self.tenant.ai_log_interactions:
            self._log_interaction(
                action=AIAction.SUMMARIZE,
                user=user,
                query_text=parsed['original_query'],
                decision_ids=[decision.id],
                duration_ms=duration_ms
            )

        # Create a structured summary (non-LLM version)
        display_id = decision.get_display_id() if hasattr(decision, 'get_display_id') else f"ADR-{decision.decision_number}"

        # Truncate fields for summary
        def truncate(text: str, length: int = 200) -> str:
            if not text:
                return "_Not provided_"
            if len(text) <= length:
                return text
            return text[:length] + "..."

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"Summary: {display_id}"}
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{decision.title}*\n_Status: {decision.status.title()}_"
                }
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":clipboard: *Context*\n{truncate(decision.context)}"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":bulb: *Decision*\n{truncate(decision.decision)}"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":warning: *Consequences*\n{truncate(decision.consequences)}"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "_AI-powered summaries will be available in a future update._"
                    }
                ]
            }
        ]

        return {'response_type': 'ephemeral', 'blocks': blocks}, True

    def _handle_explain(
        self,
        parsed: Dict[str, Any],
        user: User,
        start_time: datetime,
        log_interaction: bool
    ) -> Tuple[Dict[str, Any], bool]:
        """
        Handle an explain intent.

        Note: Full LLM-powered explanation requires Phase 5.
        For now, returns the consequences section.
        """
        if not parsed['decision_id']:
            return {
                'response_type': 'ephemeral',
                'text': ':warning: Please specify a decision to explain.\n'
                        '_Example: `/decision ai explain ADR-42`_'
            }, True

        # Get the decision
        import re
        match = re.search(r'\d+', parsed['decision_id'])
        if not match:
            return {
                'response_type': 'ephemeral',
                'text': f':warning: Could not parse decision ID: {parsed["decision_id"]}'
            }, True

        number = int(match.group())
        decision = ArchitectureDecision.query.filter_by(
            tenant_id=self.tenant.id,
            decision_number=number,
            deleted_at=None
        ).first()

        duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

        if not decision:
            return {
                'response_type': 'ephemeral',
                'text': f':warning: Decision {parsed["decision_id"]} not found.'
            }, True

        # Log interaction
        if log_interaction and self.tenant.ai_log_interactions:
            self._log_interaction(
                action=AIAction.SUMMARIZE,  # Explain is similar to summarize
                user=user,
                query_text=parsed['original_query'],
                decision_ids=[decision.id],
                duration_ms=duration_ms
            )

        display_id = decision.get_display_id() if hasattr(decision, 'get_display_id') else f"ADR-{decision.decision_number}"

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"Explanation: {display_id}"}
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{decision.title}*"
                }
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":thought_balloon: *Why this decision was made:*\n{decision.context or '_No context provided_'}"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":warning: *Consequences and impact:*\n{decision.consequences or '_No consequences documented_'}"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "_AI-powered explanations will be available in a future update._"
                    }
                ]
            }
        ]

        return {'response_type': 'ephemeral', 'blocks': blocks}, True

    def _handle_list(
        self,
        parsed: Dict[str, Any],
        user: User,
        start_time: datetime,
        log_interaction: bool
    ) -> Tuple[Dict[str, Any], bool]:
        """Handle a list intent with NL-extracted filters."""
        # Build query with extracted filters
        query = ArchitectureDecision.query.filter(
            ArchitectureDecision.tenant_id == self.tenant.id,
            ArchitectureDecision.deleted_at == None
        )

        filters = build_search_filters(parsed)

        if filters.get('status'):
            query = query.filter(ArchitectureDecision.status == filters['status'])

        if filters.get('created_after'):
            query = query.filter(ArchitectureDecision.created_at >= filters['created_after'])

        decisions = query.order_by(ArchitectureDecision.created_at.desc()).limit(10).all()

        duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

        # Log interaction
        if log_interaction and self.tenant.ai_log_interactions:
            self._log_interaction(
                action=AIAction.SEARCH,
                user=user,
                query_text=parsed['original_query'],
                decision_ids=[d.id for d in decisions],
                duration_ms=duration_ms
            )

        if not decisions:
            return {
                'response_type': 'ephemeral',
                'text': ':mag: No decisions found matching your criteria.'
            }, True

        blocks = self._format_search_results(decisions, parsed['original_query'])
        return {'response_type': 'ephemeral', 'blocks': blocks}, True

    def _format_search_results(
        self,
        decisions: List[ArchitectureDecision],
        query: str
    ) -> List[Dict[str, Any]]:
        """Format search results as Slack blocks."""
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"AI Search Results"}
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f":mag: Query: _{query}_"}
                ]
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

        blocks.append({
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f":robot_face: Powered by AI • Found {len(decisions)} result{'s' if len(decisions) != 1 else ''}"}
            ]
        })

        return blocks

    def _get_status_emoji(self, status: str) -> str:
        """Get emoji for decision status."""
        return {
            'proposed': ':thought_balloon:',
            'accepted': ':large_green_circle:',
            'archived': ':white_circle:',
            'superseded': ':large_orange_circle:'
        }.get(status, ':thought_balloon:')

    def _log_interaction(
        self,
        action: AIAction,
        user: User,
        query_text: str,
        decision_ids: List[int],
        duration_ms: int,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
        tokens_input: Optional[int] = None,
        tokens_output: Optional[int] = None
    ):
        """Log an AI interaction."""
        # Anonymize query if required
        log_query = query_text
        if self.tenant.ai_require_anonymization:
            # Basic anonymization - future: use ai/anonymization module
            log_query = query_text  # TODO: Implement anonymization in Phase 5

        AIInteractionLogger.log_interaction(
            channel=AIChannel.SLACK,
            action=action,
            tenant_id=self.tenant.id,
            user_id=user.id if user else None,
            query_text=log_query,
            decision_ids=decision_ids,
            llm_provider=llm_provider,
            llm_model=llm_model,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            duration_ms=duration_ms
        )


def get_slack_ai_handler(workspace: SlackWorkspace) -> Optional[SlackAIHandler]:
    """
    Get a SlackAIHandler for a workspace, if AI is available.

    Args:
        workspace: The Slack workspace

    Returns:
        SlackAIHandler or None if AI is not available
    """
    if not workspace.tenant_id:
        return None

    tenant = workspace.tenant
    if not tenant:
        return None

    # Check system-level AI availability
    if not AIConfig.get_system_ai_enabled():
        return None

    if not AIConfig.get_system_slack_bot_enabled():
        return None

    # Check tenant-level AI availability
    if not tenant.ai_features_enabled:
        return None

    if not tenant.ai_slack_queries_enabled:
        return None

    return SlackAIHandler(workspace, tenant)
