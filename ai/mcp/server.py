"""
MCP Server Implementation for Architecture Decisions.

Provides an MCP server that can be used with developer tools like
Claude Code, Cursor, and VS Code to interact with decision records.

This module can be run as a standalone server or integrated into the main app.
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple

from models import (
    db, ArchitectureDecision, DecisionHistory, User, Tenant,
    AIApiKey, AIChannel, AIAction
)
from ai.config import AIConfig
from ai.api_keys import AIApiKeyService
from ai.interaction_log import AIInteractionLogger
from ai.mcp.tools import get_tools, get_tool_by_name, validate_tool_input

logger = logging.getLogger(__name__)


class MCPToolHandler:
    """
    Handles MCP tool calls for architecture decisions.

    This handler authenticates via API key and executes tool calls
    within the context of a tenant.
    """

    def __init__(self, api_key: AIApiKey, tenant: Tenant, user: User):
        self.api_key = api_key
        self.tenant = tenant
        self.user = user

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Tuple[bool, Any]:
        """
        Execute an MCP tool.

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            Tuple of (success, result_or_error)
        """
        start_time = datetime.now(timezone.utc)

        # Validate tool exists
        tool = get_tool_by_name(tool_name)
        if not tool:
            return False, {"error": f"Unknown tool: {tool_name}"}

        # Validate input
        validation_error = validate_tool_input(tool_name, arguments)
        if validation_error:
            return False, {"error": validation_error}

        # Check scope requirements
        write_tools = {"create_decision"}
        if tool_name in write_tools:
            if not AIApiKeyService.has_scope(self.api_key, 'write'):
                return False, {"error": "This API key does not have write permission"}

        # Execute the tool
        handlers = {
            "search_decisions": self._search_decisions,
            "get_decision": self._get_decision,
            "list_decisions": self._list_decisions,
            "create_decision": self._create_decision,
            "get_decision_history": self._get_decision_history,
        }

        handler = handlers.get(tool_name)
        if not handler:
            return False, {"error": f"Tool not implemented: {tool_name}"}

        try:
            result = handler(arguments)
            duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

            # Log interaction
            if self.tenant.ai_log_interactions:
                action = self._get_action_for_tool(tool_name)
                decision_ids = self._extract_decision_ids(result)
                AIInteractionLogger.log_interaction(
                    channel=AIChannel.MCP,
                    action=action,
                    tenant_id=self.tenant.id,
                    user_id=self.user.id if self.user else None,
                    query_text=json.dumps(arguments)[:500],  # Truncate for logging
                    decision_ids=decision_ids,
                    duration_ms=duration_ms
                )

            return True, result
        except Exception as e:
            logger.error(f"MCP tool error: {tool_name} - {e}")
            return False, {"error": str(e)}

    def _get_action_for_tool(self, tool_name: str) -> AIAction:
        """Map tool name to action type."""
        mapping = {
            "search_decisions": AIAction.SEARCH,
            "get_decision": AIAction.READ,
            "list_decisions": AIAction.SEARCH,
            "create_decision": AIAction.CREATE,
            "get_decision_history": AIAction.READ,
        }
        return mapping.get(tool_name, AIAction.READ)

    def _extract_decision_ids(self, result: Any) -> List[int]:
        """Extract decision IDs from a result for logging."""
        if isinstance(result, dict):
            if "id" in result:
                return [result["id"]]
            if "decisions" in result:
                return [d.get("id") for d in result["decisions"] if d.get("id")]
        if isinstance(result, list):
            return [d.get("id") for d in result if isinstance(d, dict) and d.get("id")]
        return []

    def _search_decisions(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Search for decisions."""
        query_text = args.get("query", "")
        status = args.get("status")
        limit = args.get("limit", 10)

        # Build query
        query = ArchitectureDecision.query.filter(
            ArchitectureDecision.tenant_id == self.tenant.id,
            ArchitectureDecision.deleted_at == None
        )

        # Apply text search
        if query_text:
            pattern = f"%{query_text}%"
            query = query.filter(
                db.or_(
                    ArchitectureDecision.title.ilike(pattern),
                    ArchitectureDecision.context.ilike(pattern),
                    ArchitectureDecision.decision.ilike(pattern),
                    ArchitectureDecision.consequences.ilike(pattern)
                )
            )

        # Apply status filter
        if status:
            query = query.filter(ArchitectureDecision.status == status)

        # Execute
        decisions = query.order_by(
            ArchitectureDecision.created_at.desc()
        ).limit(limit).all()

        return {
            "query": query_text,
            "count": len(decisions),
            "decisions": [self._format_decision_summary(d) for d in decisions]
        }

    def _get_decision(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get a specific decision."""
        decision_id = args.get("id", "")

        # Parse ID
        decision = self._find_decision_by_id(decision_id)
        if not decision:
            return {"error": f"Decision not found: {decision_id}"}

        return self._format_decision_full(decision)

    def _list_decisions(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List decisions with pagination."""
        status = args.get("status")
        limit = args.get("limit", 20)
        offset = args.get("offset", 0)
        order_by = args.get("order_by", "created_at")
        order = args.get("order", "desc")

        # Build query
        query = ArchitectureDecision.query.filter(
            ArchitectureDecision.tenant_id == self.tenant.id,
            ArchitectureDecision.deleted_at == None
        )

        if status:
            query = query.filter(ArchitectureDecision.status == status)

        # Apply ordering
        order_column = getattr(ArchitectureDecision, order_by, ArchitectureDecision.created_at)
        if order == "asc":
            query = query.order_by(order_column.asc())
        else:
            query = query.order_by(order_column.desc())

        # Get total count
        total = query.count()

        # Apply pagination
        decisions = query.offset(offset).limit(limit).all()

        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "count": len(decisions),
            "decisions": [self._format_decision_summary(d) for d in decisions]
        }

    def _create_decision(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new decision."""
        title = args.get("title", "").strip()
        context = args.get("context", "").strip()
        decision_text = args.get("decision", "").strip()
        consequences = args.get("consequences", "").strip()
        status = args.get("status", "proposed")

        if not title:
            return {"error": "Title is required"}

        # Get next decision number
        max_number = db.session.query(db.func.max(ArchitectureDecision.decision_number)).filter(
            ArchitectureDecision.tenant_id == self.tenant.id
        ).scalar() or 0
        next_number = max_number + 1

        # Create decision
        decision = ArchitectureDecision(
            title=title,
            context=context,
            decision=decision_text,
            consequences=consequences,
            status=status,
            decision_number=next_number,
            domain=self.tenant.domain,
            tenant_id=self.tenant.id,
            created_by_id=self.user.id if self.user else None,
            updated_by_id=self.user.id if self.user else None
        )

        db.session.add(decision)
        db.session.commit()

        return {
            "message": "Decision created successfully",
            "decision": self._format_decision_full(decision)
        }

    def _get_decision_history(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get decision change history."""
        decision_id = args.get("id", "")
        limit = args.get("limit", 20)

        decision = self._find_decision_by_id(decision_id)
        if not decision:
            return {"error": f"Decision not found: {decision_id}"}

        # Get history
        history = DecisionHistory.query.filter_by(
            decision_id=decision.id
        ).order_by(DecisionHistory.changed_at.desc()).limit(limit).all()

        return {
            "decision_id": decision.id,
            "display_id": decision.get_display_id() if hasattr(decision, 'get_display_id') else f"ADR-{decision.decision_number}",
            "history": [self._format_history_entry(h) for h in history]
        }

    def _find_decision_by_id(self, decision_id: str) -> Optional[ArchitectureDecision]:
        """Find a decision by ID (supports ADR-XXX or numeric format)."""
        # Try as numeric ID first
        if decision_id.isdigit():
            return ArchitectureDecision.query.filter_by(
                id=int(decision_id),
                tenant_id=self.tenant.id,
                deleted_at=None
            ).first()

        # Try to parse ADR-XXX format
        match = re.search(r'\d+', decision_id)
        if match:
            number = int(match.group())
            return ArchitectureDecision.query.filter_by(
                decision_number=number,
                tenant_id=self.tenant.id,
                deleted_at=None
            ).first()

        return None

    def _format_decision_summary(self, decision: ArchitectureDecision) -> Dict[str, Any]:
        """Format a decision for list/search results."""
        display_id = decision.get_display_id() if hasattr(decision, 'get_display_id') else f"ADR-{decision.decision_number}"
        return {
            "id": decision.id,
            "display_id": display_id,
            "title": decision.title,
            "status": decision.status,
            "created_at": decision.created_at.isoformat() if decision.created_at else None,
            "context_preview": (decision.context[:200] + "...") if decision.context and len(decision.context) > 200 else decision.context
        }

    def _format_decision_full(self, decision: ArchitectureDecision) -> Dict[str, Any]:
        """Format a decision with full details."""
        display_id = decision.get_display_id() if hasattr(decision, 'get_display_id') else f"ADR-{decision.decision_number}"

        creator_name = None
        if decision.creator:
            creator_name = decision.creator.name or decision.creator.email

        owner_name = None
        if decision.owner:
            owner_name = decision.owner.name or decision.owner.email
        elif decision.owner_email:
            owner_name = decision.owner_email

        return {
            "id": decision.id,
            "display_id": display_id,
            "decision_number": decision.decision_number,
            "title": decision.title,
            "status": decision.status,
            "context": decision.context,
            "decision": decision.decision,
            "consequences": decision.consequences,
            "created_at": decision.created_at.isoformat() if decision.created_at else None,
            "updated_at": decision.updated_at.isoformat() if decision.updated_at else None,
            "creator": creator_name,
            "owner": owner_name,
        }

    def _format_history_entry(self, history: DecisionHistory) -> Dict[str, Any]:
        """Format a history entry."""
        changed_by = None
        if history.changed_by:
            changed_by = history.changed_by.name or history.changed_by.email

        return {
            "changed_at": history.changed_at.isoformat() if history.changed_at else None,
            "changed_by": changed_by,
            "field_changed": history.field_changed,
            "old_value": history.old_value[:500] if history.old_value else None,
            "new_value": history.new_value[:500] if history.new_value else None,
        }


def authenticate_mcp_request(api_key: str) -> Tuple[bool, Optional[MCPToolHandler], Optional[str]]:
    """
    Authenticate an MCP request using an API key.

    Args:
        api_key: The API key from the request

    Returns:
        Tuple of (success, handler, error_message)
    """
    # Check system-level MCP availability
    if not AIConfig.get_system_ai_enabled():
        return False, None, "AI features are not enabled"

    if not AIConfig.get_system_mcp_server_enabled():
        return False, None, "MCP server is not enabled"

    # Validate API key
    key_record = AIApiKeyService.validate_key(api_key)
    if not key_record:
        return False, None, "Invalid or expired API key"

    # Get user and tenant
    user = User.query.get(key_record.user_id)
    tenant = Tenant.query.get(key_record.tenant_id)

    if not user or not tenant:
        return False, None, "User or tenant not found"

    # Check tenant AI settings
    if not tenant.ai_features_enabled:
        return False, None, "AI features are not enabled for this organization"

    # Check user opt-out
    if AIConfig.get_user_ai_opt_out(user, tenant):
        return False, None, "User has opted out of AI features"

    handler = MCPToolHandler(key_record, tenant, user)
    return True, handler, None


def handle_mcp_request(request_data: Dict[str, Any], api_key: str) -> Dict[str, Any]:
    """
    Handle an incoming MCP request.

    Args:
        request_data: The MCP request data
        api_key: The API key for authentication

    Returns:
        MCP response data
    """
    # Authenticate
    success, handler, error = authenticate_mcp_request(api_key)
    if not success:
        return {
            "jsonrpc": "2.0",
            "id": request_data.get("id"),
            "error": {
                "code": -32600,
                "message": error
            }
        }

    # Handle different MCP methods
    method = request_data.get("method", "")
    params = request_data.get("params", {})
    request_id = request_data.get("id")

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": get_tools()
            }
        }

    elif method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        success, result = handler.execute_tool(tool_name, arguments)

        if success:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2)
                        }
                    ]
                }
            }
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32000,
                    "message": result.get("error", "Unknown error")
                }
            }

    else:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}"
            }
        }
