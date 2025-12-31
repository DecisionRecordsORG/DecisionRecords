"""
AI/LLM Integration Module for Architecture Decisions.

This module provides AI-powered features including:
- Natural language queries via Slack bot
- MCP server for developer tool integration
- External AI API for Custom GPTs and agents
- LLM-assisted decision creation

All features are opt-in with hierarchical control:
- Super Admin enables globally
- Tenant Admin enables per-tenant
- Users can opt-out individually
"""

from ai.config import AIConfig
from ai.api_keys import AIApiKeyService
from ai.interaction_log import AIInteractionLogger

__all__ = [
    'AIConfig',
    'AIApiKeyService',
    'AIInteractionLogger',
]
