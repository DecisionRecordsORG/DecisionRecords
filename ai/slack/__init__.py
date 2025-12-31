"""
Slack AI Integration Module.

Provides natural language query processing for Slack bot
interactions.

Components:
- nl_query.py: Natural language query processing
- handlers.py: AI-specific Slack command handlers
"""

from ai.slack.nl_query import NLQueryParser, QueryIntent, format_search_query, build_search_filters
from ai.slack.handlers import SlackAIHandler, get_slack_ai_handler

__all__ = [
    'NLQueryParser',
    'QueryIntent',
    'format_search_query',
    'build_search_filters',
    'SlackAIHandler',
    'get_slack_ai_handler',
]
