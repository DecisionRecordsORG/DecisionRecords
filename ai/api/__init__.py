"""
External AI API Module.

Provides REST API endpoints for external AI tools like Custom GPTs
and AI agents.

Components:
- routes.py: Flask Blueprint with REST API endpoints
"""

from ai.api.routes import (
    ai_api,
    require_ai_api_key,
)

__all__ = [
    'ai_api',
    'require_ai_api_key',
]
