"""
Tests for MCP (Model Context Protocol) server implementation.

Tests cover:
1. Tool definitions in ai/mcp/tools.py
2. MCP server handler in ai/mcp/server.py
3. MCP API endpoint in app.py
"""
import pytest
import json
from datetime import datetime, timedelta, timezone
from flask import Flask

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    db, User, Tenant, TenantMembership, SystemConfig, GlobalRole, MaturityState,
    AIApiKey, ArchitectureDecision, DecisionHistory
)
from ai import AIConfig, AIApiKeyService
from ai.mcp.tools import get_tools, get_tool_by_name, validate_tool_input, TOOLS
from ai.mcp.server import MCPToolHandler, authenticate_mcp_request, handle_mcp_request


# ============================================================================
# TOOLS.PY TESTS
# ============================================================================

class TestGetTools:
    """Test get_tools() function."""

    def test_get_tools_returns_list(self, app, session):
        """get_tools returns a list."""
        tools = get_tools()
        assert isinstance(tools, list)

    def test_get_tools_returns_correct_number(self, app, session):
        """get_tools returns all 5 tools."""
        tools = get_tools()
        assert len(tools) == 5

    def test_get_tools_returns_expected_tool_names(self, app, session):
        """get_tools returns tools with expected names."""
        tools = get_tools()
        tool_names = [t['name'] for t in tools]
        expected_names = [
            'search_decisions',
            'get_decision',
            'list_decisions',
            'create_decision',
            'get_decision_history'
        ]
        assert tool_names == expected_names

    def test_get_tools_each_tool_has_required_fields(self, app, session):
        """Each tool has name, description, and inputSchema."""
        tools = get_tools()
        for tool in tools:
            assert 'name' in tool
            assert 'description' in tool
            assert 'inputSchema' in tool

    def test_get_tools_input_schemas_are_valid(self, app, session):
        """Each tool's inputSchema has type object and properties."""
        tools = get_tools()
        for tool in tools:
            schema = tool['inputSchema']
            assert schema.get('type') == 'object'
            assert 'properties' in schema


class TestGetToolByName:
    """Test get_tool_by_name() function."""

    def test_get_tool_by_name_returns_correct_tool(self, app, session):
        """get_tool_by_name returns the correct tool for valid name."""
        tool = get_tool_by_name('search_decisions')
        assert tool is not None
        assert tool['name'] == 'search_decisions'

    def test_get_tool_by_name_returns_none_for_invalid(self, app, session):
        """get_tool_by_name returns None for invalid tool name."""
        tool = get_tool_by_name('invalid_tool_name')
        assert tool is None

    def test_get_tool_by_name_returns_none_for_empty(self, app, session):
        """get_tool_by_name returns None for empty string."""
        tool = get_tool_by_name('')
        assert tool is None

    def test_get_tool_by_name_is_case_sensitive(self, app, session):
        """get_tool_by_name is case sensitive."""
        tool = get_tool_by_name('SEARCH_DECISIONS')
        assert tool is None

    def test_get_tool_by_name_all_tools(self, app, session):
        """get_tool_by_name works for all defined tools."""
        for defined_tool in TOOLS:
            tool = get_tool_by_name(defined_tool['name'])
            assert tool is not None
            assert tool['name'] == defined_tool['name']


class TestValidateToolInput:
    """Test validate_tool_input() function."""

    def test_validate_unknown_tool_returns_error(self, app, session):
        """validate_tool_input returns error for unknown tool."""
        error = validate_tool_input('unknown_tool', {})
        assert error is not None
        assert 'Unknown tool' in error

    def test_validate_search_decisions_valid(self, app, session):
        """validate_tool_input returns None for valid search_decisions input."""
        error = validate_tool_input('search_decisions', {'query': 'test'})
        assert error is None

    def test_validate_search_decisions_missing_query(self, app, session):
        """validate_tool_input returns error when query is missing."""
        error = validate_tool_input('search_decisions', {})
        assert error is not None
        assert 'Missing required field: query' in error

    def test_validate_search_decisions_null_query(self, app, session):
        """validate_tool_input returns error when query is None."""
        error = validate_tool_input('search_decisions', {'query': None})
        assert error is not None
        assert 'Missing required field: query' in error

    def test_validate_search_decisions_invalid_query_type(self, app, session):
        """validate_tool_input returns error for non-string query."""
        error = validate_tool_input('search_decisions', {'query': 123})
        assert error is not None
        assert "must be a string" in error

    def test_validate_search_decisions_invalid_status(self, app, session):
        """validate_tool_input returns error for invalid status enum."""
        error = validate_tool_input('search_decisions', {
            'query': 'test',
            'status': 'invalid_status'
        })
        assert error is not None
        assert 'must be one of' in error

    def test_validate_search_decisions_valid_status(self, app, session):
        """validate_tool_input accepts valid status enum values."""
        for status in ['proposed', 'accepted', 'archived', 'superseded']:
            error = validate_tool_input('search_decisions', {
                'query': 'test',
                'status': status
            })
            assert error is None

    def test_validate_search_decisions_limit_below_minimum(self, app, session):
        """validate_tool_input returns error for limit below minimum."""
        error = validate_tool_input('search_decisions', {
            'query': 'test',
            'limit': 0
        })
        assert error is not None
        assert 'at least 1' in error

    def test_validate_search_decisions_limit_above_maximum(self, app, session):
        """validate_tool_input returns error for limit above maximum."""
        error = validate_tool_input('search_decisions', {
            'query': 'test',
            'limit': 100
        })
        assert error is not None
        assert 'at most 50' in error

    def test_validate_get_decision_valid(self, app, session):
        """validate_tool_input returns None for valid get_decision input."""
        error = validate_tool_input('get_decision', {'id': '42'})
        assert error is None

    def test_validate_get_decision_missing_id(self, app, session):
        """validate_tool_input returns error when id is missing."""
        error = validate_tool_input('get_decision', {})
        assert error is not None
        assert 'Missing required field: id' in error

    def test_validate_list_decisions_valid_empty(self, app, session):
        """validate_tool_input returns None for list_decisions with no args."""
        error = validate_tool_input('list_decisions', {})
        assert error is None

    def test_validate_list_decisions_valid_with_all_params(self, app, session):
        """validate_tool_input returns None for list_decisions with all params."""
        error = validate_tool_input('list_decisions', {
            'status': 'accepted',
            'limit': 20,
            'offset': 10,
            'order_by': 'created_at',
            'order': 'desc'
        })
        assert error is None

    def test_validate_list_decisions_invalid_order_by(self, app, session):
        """validate_tool_input returns error for invalid order_by."""
        error = validate_tool_input('list_decisions', {
            'order_by': 'invalid_field'
        })
        assert error is not None
        assert 'must be one of' in error

    def test_validate_list_decisions_invalid_order(self, app, session):
        """validate_tool_input returns error for invalid order."""
        error = validate_tool_input('list_decisions', {
            'order': 'invalid'
        })
        assert error is not None
        assert 'must be one of' in error

    def test_validate_create_decision_valid(self, app, session):
        """validate_tool_input returns None for valid create_decision input."""
        error = validate_tool_input('create_decision', {
            'title': 'Test Decision',
            'context': 'Some context',
            'decision': 'The decision',
            'consequences': 'Expected consequences'
        })
        assert error is None

    def test_validate_create_decision_missing_required_fields(self, app, session):
        """validate_tool_input returns error for missing required fields."""
        for field in ['title', 'context', 'decision', 'consequences']:
            args = {
                'title': 'Test',
                'context': 'Context',
                'decision': 'Decision',
                'consequences': 'Consequences'
            }
            del args[field]
            error = validate_tool_input('create_decision', args)
            assert error is not None
            assert f'Missing required field: {field}' in error

    def test_validate_create_decision_title_max_length(self, app, session):
        """validate_tool_input returns error for title exceeding max length."""
        error = validate_tool_input('create_decision', {
            'title': 'x' * 256,  # maxLength is 255
            'context': 'Context',
            'decision': 'Decision',
            'consequences': 'Consequences'
        })
        assert error is not None
        assert 'exceeds maximum length' in error

    def test_validate_create_decision_valid_status(self, app, session):
        """validate_tool_input accepts valid status for create_decision."""
        for status in ['proposed', 'accepted']:
            error = validate_tool_input('create_decision', {
                'title': 'Test',
                'context': 'Context',
                'decision': 'Decision',
                'consequences': 'Consequences',
                'status': status
            })
            assert error is None

    def test_validate_create_decision_invalid_status(self, app, session):
        """validate_tool_input returns error for invalid status on create."""
        error = validate_tool_input('create_decision', {
            'title': 'Test',
            'context': 'Context',
            'decision': 'Decision',
            'consequences': 'Consequences',
            'status': 'archived'  # Not allowed for creation
        })
        assert error is not None
        assert 'must be one of' in error

    def test_validate_get_decision_history_valid(self, app, session):
        """validate_tool_input returns None for valid get_decision_history input."""
        error = validate_tool_input('get_decision_history', {'id': 'ADR-42'})
        assert error is None

    def test_validate_get_decision_history_missing_id(self, app, session):
        """validate_tool_input returns error when id is missing."""
        error = validate_tool_input('get_decision_history', {})
        assert error is not None
        assert 'Missing required field: id' in error

    def test_validate_get_decision_history_with_limit(self, app, session):
        """validate_tool_input accepts valid limit for get_decision_history."""
        error = validate_tool_input('get_decision_history', {
            'id': '42',
            'limit': 50
        })
        assert error is None

    def test_validate_allows_extra_fields(self, app, session):
        """validate_tool_input allows extra fields (ignores them)."""
        error = validate_tool_input('search_decisions', {
            'query': 'test',
            'extra_field': 'ignored'
        })
        assert error is None


# ============================================================================
# SERVER.PY - MCPToolHandler TESTS
# ============================================================================

class TestMCPToolHandlerExecuteTool:
    """Test MCPToolHandler.execute_tool() method."""

    @pytest.fixture
    def ai_enabled_tenant(self, session, sample_tenant):
        """Create a tenant with AI features enabled."""
        sample_tenant.ai_features_enabled = True
        sample_tenant.ai_log_interactions = False  # Disable logging for simpler tests
        session.commit()
        return sample_tenant

    @pytest.fixture
    def api_key_with_read_scope(self, session, sample_user, ai_enabled_tenant, sample_membership):
        """Create an API key with read scope."""
        api_key, full_key = AIApiKeyService.create_key(
            sample_user, ai_enabled_tenant, 'Test Key',
            scopes=['read', 'search']
        )
        return api_key, full_key

    @pytest.fixture
    def api_key_with_write_scope(self, session, sample_user, ai_enabled_tenant, sample_membership):
        """Create an API key with write scope."""
        api_key, full_key = AIApiKeyService.create_key(
            sample_user, ai_enabled_tenant, 'Test Key',
            scopes=['read', 'search', 'write']
        )
        return api_key, full_key

    @pytest.fixture
    def handler_read_only(self, api_key_with_read_scope, ai_enabled_tenant, sample_user):
        """Create handler with read-only API key."""
        api_key, _ = api_key_with_read_scope
        return MCPToolHandler(api_key, ai_enabled_tenant, sample_user)

    @pytest.fixture
    def handler_with_write(self, api_key_with_write_scope, ai_enabled_tenant, sample_user):
        """Create handler with write-capable API key."""
        api_key, _ = api_key_with_write_scope
        return MCPToolHandler(api_key, ai_enabled_tenant, sample_user)

    def test_execute_unknown_tool_returns_error(self, app, session, handler_read_only):
        """execute_tool returns error for unknown tool."""
        success, result = handler_read_only.execute_tool('unknown_tool', {})
        assert success is False
        assert 'error' in result
        assert 'Unknown tool' in result['error']

    def test_execute_tool_validates_input(self, app, session, handler_read_only):
        """execute_tool validates input and returns error for invalid."""
        success, result = handler_read_only.execute_tool('search_decisions', {})
        assert success is False
        assert 'error' in result
        assert 'Missing required field' in result['error']

    def test_execute_search_decisions_success(self, app, session, handler_read_only, sample_decision):
        """execute_tool successfully searches decisions."""
        success, result = handler_read_only.execute_tool('search_decisions', {'query': 'Test'})
        assert success is True
        assert 'decisions' in result
        assert 'count' in result

    def test_execute_search_decisions_with_status_filter(self, app, session, handler_read_only, sample_decision):
        """execute_tool filters search by status."""
        success, result = handler_read_only.execute_tool('search_decisions', {
            'query': 'Test',
            'status': 'proposed'
        })
        assert success is True
        assert result['count'] >= 0

    def test_execute_search_decisions_respects_limit(self, app, session, handler_read_only, ai_enabled_tenant, sample_user):
        """execute_tool respects limit parameter."""
        # Create multiple decisions
        for i in range(5):
            decision = ArchitectureDecision(
                title=f'Test Decision {i}',
                context='Context',
                decision='Decision',
                consequences='Consequences',
                status='proposed',
                domain=ai_enabled_tenant.domain,
                tenant_id=ai_enabled_tenant.id,
                created_by_id=sample_user.id,
                decision_number=i + 1
            )
            session.add(decision)
        session.commit()

        success, result = handler_read_only.execute_tool('search_decisions', {
            'query': 'Test',
            'limit': 3
        })
        assert success is True
        assert len(result['decisions']) <= 3

    def test_execute_get_decision_success(self, app, session, handler_read_only, sample_decision):
        """execute_tool successfully gets a decision by ID."""
        success, result = handler_read_only.execute_tool('get_decision', {
            'id': str(sample_decision.id)
        })
        assert success is True
        assert result['id'] == sample_decision.id
        assert result['title'] == sample_decision.title

    def test_execute_get_decision_by_display_id(self, app, session, handler_read_only, sample_decision):
        """execute_tool finds decision by ADR-XXX format."""
        success, result = handler_read_only.execute_tool('get_decision', {
            'id': f'ADR-{sample_decision.decision_number}'
        })
        assert success is True
        assert result['id'] == sample_decision.id

    def test_execute_get_decision_not_found(self, app, session, handler_read_only):
        """execute_tool returns error for non-existent decision."""
        success, result = handler_read_only.execute_tool('get_decision', {
            'id': '99999'
        })
        assert success is True  # Tool succeeded, but decision not found
        assert 'error' in result
        assert 'not found' in result['error']

    def test_execute_list_decisions_success(self, app, session, handler_read_only, sample_decision):
        """execute_tool successfully lists decisions."""
        success, result = handler_read_only.execute_tool('list_decisions', {})
        assert success is True
        assert 'decisions' in result
        assert 'total' in result
        assert 'offset' in result
        assert 'limit' in result

    def test_execute_list_decisions_with_pagination(self, app, session, handler_read_only, sample_decision):
        """execute_tool handles pagination parameters."""
        success, result = handler_read_only.execute_tool('list_decisions', {
            'limit': 10,
            'offset': 0
        })
        assert success is True
        assert result['limit'] == 10
        assert result['offset'] == 0

    def test_execute_list_decisions_with_ordering(self, app, session, handler_read_only, sample_decision):
        """execute_tool handles ordering parameters."""
        success, result = handler_read_only.execute_tool('list_decisions', {
            'order_by': 'created_at',
            'order': 'desc'
        })
        assert success is True

    def test_execute_create_decision_requires_write_scope(self, app, session, handler_read_only):
        """execute_tool returns error when write scope is missing."""
        success, result = handler_read_only.execute_tool('create_decision', {
            'title': 'New Decision',
            'context': 'Context',
            'decision': 'Decision text',
            'consequences': 'Consequences'
        })
        assert success is False
        assert 'error' in result
        assert 'write permission' in result['error']

    def test_execute_create_decision_success(self, app, session, handler_with_write, ai_enabled_tenant):
        """execute_tool successfully creates a decision with write scope."""
        success, result = handler_with_write.execute_tool('create_decision', {
            'title': 'New Decision',
            'context': 'Context for new decision',
            'decision': 'We decided to do X',
            'consequences': 'This will result in Y'
        })
        assert success is True
        assert 'message' in result
        assert 'decision' in result
        assert result['decision']['title'] == 'New Decision'

    def test_execute_create_decision_assigns_number(self, app, session, handler_with_write, ai_enabled_tenant):
        """execute_tool assigns sequential decision number."""
        # Create first decision
        success1, result1 = handler_with_write.execute_tool('create_decision', {
            'title': 'First Decision',
            'context': 'Context',
            'decision': 'Decision',
            'consequences': 'Consequences'
        })
        assert success1 is True

        # Create second decision
        success2, result2 = handler_with_write.execute_tool('create_decision', {
            'title': 'Second Decision',
            'context': 'Context',
            'decision': 'Decision',
            'consequences': 'Consequences'
        })
        assert success2 is True
        assert result2['decision']['decision_number'] == result1['decision']['decision_number'] + 1

    def test_execute_get_decision_history_success(self, app, session, handler_read_only, sample_decision):
        """execute_tool successfully gets decision history."""
        success, result = handler_read_only.execute_tool('get_decision_history', {
            'id': str(sample_decision.id)
        })
        assert success is True
        assert 'decision_id' in result
        assert 'history' in result
        assert isinstance(result['history'], list)

    def test_execute_get_decision_history_not_found(self, app, session, handler_read_only):
        """execute_tool returns error for non-existent decision history."""
        success, result = handler_read_only.execute_tool('get_decision_history', {
            'id': '99999'
        })
        assert success is True  # Tool succeeded
        assert 'error' in result
        assert 'not found' in result['error']


class TestAuthenticateMCPRequest:
    """Test authenticate_mcp_request() function."""

    @pytest.fixture
    def enable_mcp(self, session):
        """Enable MCP at system level."""
        SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
        SystemConfig.set(SystemConfig.KEY_AI_MCP_SERVER_ENABLED, 'true')
        session.commit()

    @pytest.fixture
    def ai_enabled_tenant(self, session, sample_tenant):
        """Create a tenant with AI features enabled."""
        sample_tenant.ai_features_enabled = True
        session.commit()
        return sample_tenant

    def test_authenticate_returns_error_when_ai_disabled(self, app, session):
        """authenticate_mcp_request returns error when AI is disabled."""
        success, handler, error = authenticate_mcp_request('adr_test_key')
        assert success is False
        assert handler is None
        assert 'AI features are not enabled' in error

    def test_authenticate_returns_error_when_mcp_disabled(self, app, session):
        """authenticate_mcp_request returns error when MCP is disabled."""
        SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
        session.commit()

        success, handler, error = authenticate_mcp_request('adr_test_key')
        assert success is False
        assert handler is None
        assert 'MCP server is not enabled' in error

    def test_authenticate_returns_error_for_invalid_key(self, app, session, enable_mcp):
        """authenticate_mcp_request returns error for invalid API key."""
        success, handler, error = authenticate_mcp_request('adr_invalid_key')
        assert success is False
        assert handler is None
        assert 'Invalid or expired API key' in error

    def test_authenticate_returns_error_when_tenant_ai_disabled(
        self, app, session, enable_mcp, sample_user, sample_tenant, sample_membership
    ):
        """authenticate_mcp_request returns error when tenant AI is disabled."""
        api_key, full_key = AIApiKeyService.create_key(
            sample_user, sample_tenant, 'Test Key'
        )
        success, handler, error = authenticate_mcp_request(full_key)
        assert success is False
        assert handler is None
        assert 'AI features are not enabled for this organization' in error

    def test_authenticate_returns_error_when_user_opted_out(
        self, app, session, enable_mcp, sample_user, ai_enabled_tenant, sample_membership
    ):
        """authenticate_mcp_request returns error when user opted out."""
        sample_membership.ai_opt_out = True
        session.commit()

        api_key, full_key = AIApiKeyService.create_key(
            sample_user, ai_enabled_tenant, 'Test Key'
        )
        success, handler, error = authenticate_mcp_request(full_key)
        assert success is False
        assert handler is None
        assert 'opted out' in error

    def test_authenticate_success(
        self, app, session, enable_mcp, sample_user, ai_enabled_tenant, sample_membership
    ):
        """authenticate_mcp_request succeeds with valid key and config."""
        api_key, full_key = AIApiKeyService.create_key(
            sample_user, ai_enabled_tenant, 'Test Key'
        )
        success, handler, error = authenticate_mcp_request(full_key)
        assert success is True
        assert handler is not None
        assert error is None
        assert isinstance(handler, MCPToolHandler)


class TestHandleMCPRequest:
    """Test handle_mcp_request() function."""

    @pytest.fixture
    def enable_mcp(self, session):
        """Enable MCP at system level."""
        SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
        SystemConfig.set(SystemConfig.KEY_AI_MCP_SERVER_ENABLED, 'true')
        session.commit()

    @pytest.fixture
    def ai_enabled_tenant(self, session, sample_tenant):
        """Create a tenant with AI features enabled."""
        sample_tenant.ai_features_enabled = True
        sample_tenant.ai_log_interactions = False
        session.commit()
        return sample_tenant

    @pytest.fixture
    def valid_api_key(self, session, sample_user, ai_enabled_tenant, sample_membership):
        """Create a valid API key."""
        api_key, full_key = AIApiKeyService.create_key(
            sample_user, ai_enabled_tenant, 'Test Key',
            scopes=['read', 'search', 'write']
        )
        return full_key

    def test_handle_request_auth_error(self, app, session, enable_mcp):
        """handle_mcp_request returns error for invalid API key."""
        response = handle_mcp_request(
            {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'},
            'adr_invalid_key'
        )
        assert response['jsonrpc'] == '2.0'
        assert response['id'] == 1
        assert 'error' in response

    def test_handle_request_tools_list(
        self, app, session, enable_mcp, valid_api_key
    ):
        """handle_mcp_request returns tools list for tools/list method."""
        response = handle_mcp_request(
            {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'},
            valid_api_key
        )
        assert response['jsonrpc'] == '2.0'
        assert response['id'] == 1
        assert 'result' in response
        assert 'tools' in response['result']
        assert len(response['result']['tools']) == 5

    def test_handle_request_tools_call_success(
        self, app, session, enable_mcp, valid_api_key, sample_decision
    ):
        """handle_mcp_request executes tool for tools/call method."""
        response = handle_mcp_request(
            {
                'jsonrpc': '2.0',
                'id': 1,
                'method': 'tools/call',
                'params': {
                    'name': 'search_decisions',
                    'arguments': {'query': 'Test'}
                }
            },
            valid_api_key
        )
        assert response['jsonrpc'] == '2.0'
        assert response['id'] == 1
        assert 'result' in response
        assert 'content' in response['result']
        assert response['result']['content'][0]['type'] == 'text'

    def test_handle_request_tools_call_error(
        self, app, session, enable_mcp, valid_api_key
    ):
        """handle_mcp_request returns error for invalid tool call."""
        response = handle_mcp_request(
            {
                'jsonrpc': '2.0',
                'id': 1,
                'method': 'tools/call',
                'params': {
                    'name': 'unknown_tool',
                    'arguments': {}
                }
            },
            valid_api_key
        )
        assert response['jsonrpc'] == '2.0'
        assert response['id'] == 1
        assert 'error' in response
        assert response['error']['code'] == -32000

    def test_handle_request_unknown_method(
        self, app, session, enable_mcp, valid_api_key
    ):
        """handle_mcp_request returns error for unknown method."""
        response = handle_mcp_request(
            {'jsonrpc': '2.0', 'id': 1, 'method': 'unknown/method'},
            valid_api_key
        )
        assert response['jsonrpc'] == '2.0'
        assert response['id'] == 1
        assert 'error' in response
        assert response['error']['code'] == -32601
        assert 'Method not found' in response['error']['message']

    def test_handle_request_preserves_request_id(
        self, app, session, enable_mcp, valid_api_key
    ):
        """handle_mcp_request preserves request ID in response."""
        for request_id in [1, 'abc', 123, None]:
            response = handle_mcp_request(
                {'jsonrpc': '2.0', 'id': request_id, 'method': 'tools/list'},
                valid_api_key
            )
            assert response['id'] == request_id


# ============================================================================
# APP.PY - MCP API ENDPOINT TESTS
# ============================================================================

# NOTE: These tests require FLASK_ENV=testing to be set before the app module
# is first imported to bypass Cloudflare security middleware. We use a module-level
# setup to ensure the environment is configured correctly.


def _ensure_testing_env():
    """Ensure testing environment is set before app import."""
    if os.environ.get('FLASK_ENV') != 'testing':
        os.environ['FLASK_ENV'] = 'testing'
        os.environ['TESTING'] = 'True'


# Set testing environment at module load time
_ensure_testing_env()


class TestMCPAPIEndpoint:
    """Test the /api/mcp endpoint in app.py.

    These tests verify the HTTP layer of the MCP endpoint including:
    - Authorization header validation
    - JSON parsing
    - System configuration checks
    - Proper HTTP status codes
    """

    @pytest.fixture
    def mcp_app(self):
        """Create app with MCP endpoint."""
        _ensure_testing_env()

        # Import the full app to test the actual endpoint
        import app as flask_app
        flask_app.app.config['TESTING'] = True
        flask_app.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        flask_app.app.config['WTF_CSRF_ENABLED'] = False

        with flask_app.app.app_context():
            db.create_all()
            yield flask_app.app
            db.drop_all()

    @pytest.fixture
    def mcp_client(self, mcp_app):
        """Create test client."""
        return mcp_app.test_client()

    @pytest.fixture
    def enable_mcp_system(self, mcp_app):
        """Enable MCP at system level."""
        with mcp_app.app_context():
            SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
            SystemConfig.set(SystemConfig.KEY_AI_MCP_SERVER_ENABLED, 'true')
            db.session.commit()

    @pytest.fixture
    def mcp_tenant_and_key(self, mcp_app, enable_mcp_system):
        """Create tenant with AI enabled and API key."""
        with mcp_app.app_context():
            tenant = Tenant(
                domain='test.com',
                name='Test Corp',
                status='active',
                maturity_state=MaturityState.BOOTSTRAP,
                ai_features_enabled=True,
                ai_log_interactions=False
            )
            db.session.add(tenant)
            db.session.flush()

            user = User(
                email='test@test.com',
                sso_domain='test.com',
                auth_type='local',
                email_verified=True
            )
            user.set_name(first_name='Test', last_name='User')
            db.session.add(user)
            db.session.flush()

            membership = TenantMembership(
                user_id=user.id,
                tenant_id=tenant.id,
                global_role=GlobalRole.USER
            )
            db.session.add(membership)
            db.session.commit()

            api_key, full_key = AIApiKeyService.create_key(
                user, tenant, 'Test Key',
                scopes=['read', 'search', 'write']
            )

            # Create a sample decision
            decision = ArchitectureDecision(
                title='Test Decision',
                context='Test context',
                decision='Test decision',
                consequences='Test consequences',
                status='proposed',
                domain=tenant.domain,
                tenant_id=tenant.id,
                created_by_id=user.id,
                decision_number=1
            )
            db.session.add(decision)
            db.session.commit()

            return tenant, user, full_key

    def test_missing_authorization_header(self, mcp_client, enable_mcp_system):
        """Returns 401 when Authorization header is missing."""
        response = mcp_client.post(
            '/api/mcp',
            json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'}
        )
        assert response.status_code == 401
        data = response.get_json()
        assert 'error' in data
        assert 'Authorization header' in data['error']['message']

    def test_invalid_authorization_header_format(self, mcp_client, enable_mcp_system):
        """Returns 401 when Authorization header format is wrong."""
        response = mcp_client.post(
            '/api/mcp',
            json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'},
            headers={'Authorization': 'Basic abc123'}
        )
        assert response.status_code == 401
        data = response.get_json()
        assert 'error' in data
        assert 'Authorization header' in data['error']['message']

    def test_invalid_api_key(self, mcp_client, enable_mcp_system):
        """Returns error when API key is invalid."""
        response = mcp_client.post(
            '/api/mcp',
            json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'},
            headers={'Authorization': 'Bearer adr_invalid_key_12345'}
        )
        # The endpoint returns 200 with JSON-RPC error for auth failures
        data = response.get_json()
        assert 'error' in data
        assert 'Invalid' in data['error']['message'] or 'expired' in data['error']['message']

    def test_invalid_json_body(self, mcp_client, enable_mcp_system, mcp_tenant_and_key):
        """Returns 400 when request body is not valid JSON."""
        _, _, api_key = mcp_tenant_and_key
        response = mcp_client.post(
            '/api/mcp',
            data='not valid json',
            content_type='application/json',
            headers={'Authorization': f'Bearer {api_key}'}
        )
        assert response.status_code == 400
        data = response.get_json()
        # Flask's built-in error handler returns a simple error message
        # when JSON parsing fails before reaching our endpoint
        assert 'error' in data

    def test_ai_features_disabled(self, mcp_client, mcp_app):
        """Returns 400 when AI features are disabled."""
        with mcp_app.app_context():
            # Make sure AI is disabled
            SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'false')
            db.session.commit()

        response = mcp_client.post(
            '/api/mcp',
            json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'},
            headers={'Authorization': 'Bearer adr_test_key'}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'AI features are not enabled' in data['error']['message']

    def test_mcp_server_disabled(self, mcp_client, mcp_app):
        """Returns 400 when MCP server is disabled."""
        with mcp_app.app_context():
            SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
            SystemConfig.set(SystemConfig.KEY_AI_MCP_SERVER_ENABLED, 'false')
            db.session.commit()

        response = mcp_client.post(
            '/api/mcp',
            json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'},
            headers={'Authorization': 'Bearer adr_test_key'}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'MCP server is not enabled' in data['error']['message']

    def test_tools_list_request_success(self, mcp_client, mcp_tenant_and_key):
        """Successfully returns tools list."""
        _, _, api_key = mcp_tenant_and_key
        response = mcp_client.post(
            '/api/mcp',
            json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'},
            headers={'Authorization': f'Bearer {api_key}'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert 'result' in data
        assert 'tools' in data['result']
        assert len(data['result']['tools']) == 5

    def test_tools_call_search_decisions(self, mcp_client, mcp_tenant_and_key):
        """Successfully calls search_decisions tool."""
        _, _, api_key = mcp_tenant_and_key
        response = mcp_client.post(
            '/api/mcp',
            json={
                'jsonrpc': '2.0',
                'id': 1,
                'method': 'tools/call',
                'params': {
                    'name': 'search_decisions',
                    'arguments': {'query': 'Test'}
                }
            },
            headers={'Authorization': f'Bearer {api_key}'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert 'result' in data
        content = json.loads(data['result']['content'][0]['text'])
        assert 'decisions' in content

    def test_tools_call_get_decision(self, mcp_client, mcp_tenant_and_key):
        """Successfully calls get_decision tool."""
        _, _, api_key = mcp_tenant_and_key
        response = mcp_client.post(
            '/api/mcp',
            json={
                'jsonrpc': '2.0',
                'id': 1,
                'method': 'tools/call',
                'params': {
                    'name': 'get_decision',
                    'arguments': {'id': '1'}
                }
            },
            headers={'Authorization': f'Bearer {api_key}'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert 'result' in data
        content = json.loads(data['result']['content'][0]['text'])
        assert 'title' in content or 'error' in content

    def test_tools_call_list_decisions(self, mcp_client, mcp_tenant_and_key):
        """Successfully calls list_decisions tool."""
        _, _, api_key = mcp_tenant_and_key
        response = mcp_client.post(
            '/api/mcp',
            json={
                'jsonrpc': '2.0',
                'id': 1,
                'method': 'tools/call',
                'params': {
                    'name': 'list_decisions',
                    'arguments': {}
                }
            },
            headers={'Authorization': f'Bearer {api_key}'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert 'result' in data
        content = json.loads(data['result']['content'][0]['text'])
        assert 'decisions' in content
        assert 'total' in content

    def test_tools_call_create_decision(self, mcp_client, mcp_tenant_and_key):
        """Successfully calls create_decision tool."""
        _, _, api_key = mcp_tenant_and_key
        response = mcp_client.post(
            '/api/mcp',
            json={
                'jsonrpc': '2.0',
                'id': 1,
                'method': 'tools/call',
                'params': {
                    'name': 'create_decision',
                    'arguments': {
                        'title': 'New Decision via MCP',
                        'context': 'Created during test',
                        'decision': 'Test decision text',
                        'consequences': 'Test consequences'
                    }
                }
            },
            headers={'Authorization': f'Bearer {api_key}'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert 'result' in data
        content = json.loads(data['result']['content'][0]['text'])
        assert 'decision' in content
        assert content['decision']['title'] == 'New Decision via MCP'

    def test_tools_call_get_decision_history(self, mcp_client, mcp_tenant_and_key):
        """Successfully calls get_decision_history tool."""
        _, _, api_key = mcp_tenant_and_key
        response = mcp_client.post(
            '/api/mcp',
            json={
                'jsonrpc': '2.0',
                'id': 1,
                'method': 'tools/call',
                'params': {
                    'name': 'get_decision_history',
                    'arguments': {'id': '1'}
                }
            },
            headers={'Authorization': f'Bearer {api_key}'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert 'result' in data
        content = json.loads(data['result']['content'][0]['text'])
        assert 'history' in content or 'error' in content

    def test_unknown_method_returns_404(self, mcp_client, mcp_tenant_and_key):
        """Returns 404 for unknown MCP method."""
        _, _, api_key = mcp_tenant_and_key
        response = mcp_client.post(
            '/api/mcp',
            json={'jsonrpc': '2.0', 'id': 1, 'method': 'unknown/method'},
            headers={'Authorization': f'Bearer {api_key}'}
        )
        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data
        assert data['error']['code'] == -32601
        assert 'Method not found' in data['error']['message']

    def test_tool_validation_error_returns_200_with_error(self, mcp_client, mcp_tenant_and_key):
        """Tool validation errors return 200 with JSON-RPC error."""
        _, _, api_key = mcp_tenant_and_key
        response = mcp_client.post(
            '/api/mcp',
            json={
                'jsonrpc': '2.0',
                'id': 1,
                'method': 'tools/call',
                'params': {
                    'name': 'search_decisions',
                    'arguments': {}  # Missing required 'query'
                }
            },
            headers={'Authorization': f'Bearer {api_key}'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert 'error' in data
        assert 'Missing required field' in data['error']['message']
