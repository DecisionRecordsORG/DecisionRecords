"""
MCP Tool Definitions for Architecture Decisions.

Defines the tools available through the MCP server for developer tools
like Claude Code, Cursor, and VS Code.
"""

from typing import Dict, List, Any, Optional


# Tool schemas following the MCP specification
TOOLS = [
    {
        "name": "search_decisions",
        "description": "Search architecture decision records using keywords or filters. Returns matching decisions with their titles, status, and brief context.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query - keywords to search for in decision titles, context, and content"
                },
                "status": {
                    "type": "string",
                    "enum": ["proposed", "accepted", "archived", "superseded"],
                    "description": "Filter by decision status"
                },
                "limit": {
                    "type": "integer",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 50,
                    "description": "Maximum number of results to return"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_decision",
        "description": "Get the full details of a specific architecture decision by its ID (e.g., 'ADR-42' or '42'). Returns the complete decision including context, decision text, and consequences.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "Decision ID - can be display ID (ADR-42) or numeric ID (42)"
                }
            },
            "required": ["id"]
        }
    },
    {
        "name": "list_decisions",
        "description": "List architecture decision records with optional filtering. Returns a paginated list of decisions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["proposed", "accepted", "archived", "superseded"],
                    "description": "Filter by decision status"
                },
                "limit": {
                    "type": "integer",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 100,
                    "description": "Maximum number of decisions to return"
                },
                "offset": {
                    "type": "integer",
                    "default": 0,
                    "minimum": 0,
                    "description": "Number of decisions to skip for pagination"
                },
                "order_by": {
                    "type": "string",
                    "enum": ["created_at", "updated_at", "decision_number"],
                    "default": "created_at",
                    "description": "Field to sort by"
                },
                "order": {
                    "type": "string",
                    "enum": ["asc", "desc"],
                    "default": "desc",
                    "description": "Sort order"
                }
            }
        }
    },
    {
        "name": "create_decision",
        "description": "Create a new architecture decision record. Requires write scope in your API key.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Title of the decision - brief description of what was decided",
                    "maxLength": 255
                },
                "context": {
                    "type": "string",
                    "description": "Context and background for the decision - what forces led to this decision?"
                },
                "decision": {
                    "type": "string",
                    "description": "The actual decision that was made"
                },
                "consequences": {
                    "type": "string",
                    "description": "Consequences of this decision - both positive and negative impacts"
                },
                "status": {
                    "type": "string",
                    "enum": ["proposed", "accepted"],
                    "default": "proposed",
                    "description": "Initial status of the decision"
                }
            },
            "required": ["title", "context", "decision", "consequences"]
        }
    },
    {
        "name": "get_decision_history",
        "description": "Get the change history of a specific decision. Shows all changes made to the decision over time.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "Decision ID - can be display ID (ADR-42) or numeric ID (42)"
                },
                "limit": {
                    "type": "integer",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 100,
                    "description": "Maximum number of history entries to return"
                }
            },
            "required": ["id"]
        }
    }
]


def get_tools() -> List[Dict[str, Any]]:
    """Get all available MCP tools."""
    return TOOLS


def get_tool_by_name(name: str) -> Optional[Dict[str, Any]]:
    """Get a specific tool by name."""
    for tool in TOOLS:
        if tool["name"] == name:
            return tool
    return None


def validate_tool_input(tool_name: str, arguments: Dict[str, Any]) -> Optional[str]:
    """
    Validate input arguments for a tool.

    Returns None if valid, or an error message if invalid.
    """
    tool = get_tool_by_name(tool_name)
    if not tool:
        return f"Unknown tool: {tool_name}"

    schema = tool.get("inputSchema", {})
    required = schema.get("required", [])
    properties = schema.get("properties", {})

    # Check required fields
    for field in required:
        if field not in arguments or arguments[field] is None:
            return f"Missing required field: {field}"

    # Validate field types and constraints
    for field, value in arguments.items():
        if field not in properties:
            continue  # Allow extra fields

        prop = properties[field]
        prop_type = prop.get("type")

        if prop_type == "string":
            if not isinstance(value, str):
                return f"Field '{field}' must be a string"
            if "enum" in prop and value not in prop["enum"]:
                return f"Field '{field}' must be one of: {', '.join(prop['enum'])}"
            if "maxLength" in prop and len(value) > prop["maxLength"]:
                return f"Field '{field}' exceeds maximum length of {prop['maxLength']}"

        elif prop_type == "integer":
            if not isinstance(value, int):
                return f"Field '{field}' must be an integer"
            if "minimum" in prop and value < prop["minimum"]:
                return f"Field '{field}' must be at least {prop['minimum']}"
            if "maximum" in prop and value > prop["maximum"]:
                return f"Field '{field}' must be at most {prop['maximum']}"

    return None
