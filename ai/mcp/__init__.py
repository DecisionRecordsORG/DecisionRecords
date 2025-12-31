"""
MCP (Model Context Protocol) Server Module.

Provides MCP server for integration with developer tools
like Claude Code, Cursor, and VS Code.

Components:
- server.py: MCP server implementation and request handling
- tools.py: Tool definitions for search, get, list, create, history operations
"""

from ai.mcp.tools import get_tools, get_tool_by_name, validate_tool_input, TOOLS
from ai.mcp.server import (
    MCPToolHandler,
    authenticate_mcp_request,
    handle_mcp_request,
)

__all__ = [
    'TOOLS',
    'get_tools',
    'get_tool_by_name',
    'validate_tool_input',
    'MCPToolHandler',
    'authenticate_mcp_request',
    'handle_mcp_request',
]
