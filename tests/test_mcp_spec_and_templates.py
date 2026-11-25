"""
MCP server: conformance with the specification, tool quality, and decision templates
(Enterprise Edition).

Three parts:

1. The HTTP endpoint against the MCP specification. The server answers two
   protocol eras on one endpoint: revision 2026-07-28, which is stateless and
   carries its version in every request's ``_meta``, and the handshake-based
   revisions up to 2025-11-25, which open with ``initialize``.
2. The tools as an agent uses them: paging, IDs it can chain, tolerant input,
   and errors that say what to do next.
3. Decision templates: an agent can learn the organization's headings and
   decision types, set a type when it creates a decision, and filter by it.

Note: These tests require Enterprise Edition modules from ee/backend/ai/
"""
import base64
import json
import os
import re
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import decision_templates
from models import (
    db, User, Tenant, TenantMembership, TenantSettings, SystemConfig, GlobalRole, MaturityState,
    ArchitectureDecision, DecisionComment, DecisionHistory, save_history,
)

# Enterprise Edition imports - skip tests if not available
try:
    from ee.backend.ai import AIApiKeyService
    from ee.backend.ai.mcp.tools import get_tools, get_tool_by_name, validate_tool_input, coerce_tool_arguments
    from ee.backend.ai.mcp.server import (
        MCPToolHandler, handle_mcp_request, handle_mcp_message,
        MCP_PROTOCOL_VERSION, MCP_LEGACY_PROTOCOL_VERSION, MCP_SUPPORTED_PROTOCOL_VERSIONS,
    )
    EE_AVAILABLE = True
except ImportError:
    EE_AVAILABLE = False

EE_TESTS_ENABLED = EE_AVAILABLE and os.environ.get('DECISION_RECORDS_EDITION', 'community') == 'enterprise'
pytestmark = pytest.mark.skipif(
    not EE_TESTS_ENABLED,
    reason="Enterprise Edition tests require DECISION_RECORDS_EDITION=enterprise and EE modules",
)

META_VERSION = 'io.modelcontextprotocol/protocolVersion'
META_CAPABILITIES = 'io.modelcontextprotocol/clientCapabilities'
META_SERVER_INFO = 'io.modelcontextprotocol/serverInfo'

READ_ONLY_TOOLS = {
    'search_decisions', 'get_decision', 'list_decisions', 'get_decision_history',
    'list_decision_comments', 'get_relationship_catalog', 'get_decision_template',
    'list_decision_relationships',
}
WRITE_TOOLS = {
    'create_decision', 'add_decision_comment', 'link_decisions', 'supersede_decision',
    'update_decision_status',
}


def _ensure_testing_env():
    if os.environ.get('FLASK_ENV') != 'testing':
        os.environ['FLASK_ENV'] = 'testing'
        os.environ['TESTING'] = 'True'


_ensure_testing_env()


def _modern_meta(version='2026-07-28', capabilities=True):
    meta = {META_VERSION: version}
    if capabilities:
        meta[META_CAPABILITIES] = {}
    return meta


def _modern_message(method, params=None, request_id=1, **meta_kwargs):
    params = dict(params or {})
    params['_meta'] = _modern_meta(**meta_kwargs)
    return {'jsonrpc': '2.0', 'id': request_id, 'method': method, 'params': params}


def _modern_headers(api_key, method, name=None, version='2026-07-28'):
    headers = {
        'Authorization': f'Bearer {api_key}',
        'MCP-Protocol-Version': version,
        'Mcp-Method': method,
    }
    if name is not None:
        headers['Mcp-Name'] = name
    return headers


def _make_tenant(domain, name, template_id=None, ai_enabled=True):
    tenant = Tenant(
        domain=domain, name=name, status='active', maturity_state=MaturityState.BOOTSTRAP,
        ai_features_enabled=ai_enabled, ai_external_access_enabled=True, ai_log_interactions=False,
    )
    db.session.add(tenant)
    db.session.flush()
    db.session.add(TenantSettings(tenant_id=tenant.id, decision_template_id=template_id))
    user = User(email=f'member@{domain}', sso_domain=domain, auth_type='local', email_verified=True)
    user.set_name(first_name='Mem', last_name='Ber')
    db.session.add(user)
    db.session.flush()
    db.session.add(TenantMembership(user_id=user.id, tenant_id=tenant.id, global_role=GlobalRole.USER))
    db.session.commit()
    return tenant, user


def _make_decision(tenant, user, number, title, status='proposed', decision_type=None,
                   context='Some context', decision='What was decided', consequences='What follows'):
    record = ArchitectureDecision(
        title=title, context=context, decision=decision, consequences=consequences, status=status,
        decision_type=decision_type, domain=tenant.domain, tenant_id=tenant.id,
        created_by_id=user.id, decision_number=number,
    )
    db.session.add(record)
    db.session.commit()
    return record


def _enable_mcp():
    SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
    SystemConfig.set(SystemConfig.KEY_AI_MCP_SERVER_ENABLED, 'true')
    db.session.commit()


# ============================================================================
# 1. THE HTTP ENDPOINT AGAINST THE SPECIFICATION
# ============================================================================

@pytest.fixture
def real_app():
    _ensure_testing_env()
    import app as flask_app
    flask_app.app.config['TESTING'] = True
    flask_app.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    flask_app.app.config['WTF_CSRF_ENABLED'] = False

    with flask_app.app.app_context():
        db.create_all()
        yield flask_app.app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def http(real_app):
    return real_app.test_client()


@pytest.fixture
def org(real_app):
    """An organization with one decision, a write key and a read key; MCP switched on."""
    _enable_mcp()
    tenant, user = _make_tenant('spec.example', 'Spec Org')
    record = _make_decision(tenant, user, 1, 'Move to quarterly pricing reviews')
    _, write_key = AIApiKeyService.create_key(user, tenant, 'Write', scopes=['read', 'search', 'write'])
    _, read_key = AIApiKeyService.create_key(user, tenant, 'Read', scopes=['read', 'search'])
    return {'tenant': tenant, 'user': user, 'decision': record, 'key': write_key, 'read_key': read_key}


def _legacy_post(http, key, message, headers=None):
    all_headers = {'Authorization': f'Bearer {key}'}
    all_headers.update(headers or {})
    return http.post('/api/mcp', json=message, headers=all_headers)


def _modern_post(http, key, method, params=None, name=None, request_id=1):
    return http.post(
        '/api/mcp',
        json=_modern_message(method, params, request_id=request_id),
        headers=_modern_headers(key, method, name=name),
    )


class TestSupportedRevisions:
    def test_newest_revision_first_and_the_handshake_revisions_kept(self):
        assert MCP_PROTOCOL_VERSION == '2026-07-28'
        assert MCP_LEGACY_PROTOCOL_VERSION == '2025-11-25'
        assert MCP_SUPPORTED_PROTOCOL_VERSIONS == ['2026-07-28', '2025-11-25', '2025-06-18', '2025-03-26']


class TestHandshakeRevisions:
    """Revisions up to 2025-11-25: initialize, ping, notifications."""

    def _initialize(self, http, key, version):
        return _legacy_post(http, key, {
            'jsonrpc': '2.0', 'id': 'init-1', 'method': 'initialize',
            'params': {'protocolVersion': version, 'capabilities': {}, 'clientInfo': {'name': 't', 'version': '0'}},
        })

    @pytest.mark.parametrize('version', ['2025-11-25', '2025-06-18', '2025-03-26'])
    def test_initialize_agrees_to_a_supported_revision(self, http, org, version):
        response = self._initialize(http, org['key'], version)
        assert response.status_code == 200
        data = response.get_json()
        assert data['id'] == 'init-1'
        assert data['result']['protocolVersion'] == version

    @pytest.mark.parametrize('version', ['2024-11-05', '2099-01-01', '2026-07-28', None])
    def test_initialize_offers_its_newest_handshake_revision_otherwise(self, http, org, version):
        """The handshake rule: answer with a revision the server speaks, never an error.

        2026-07-28 has no handshake, so a client that opens with initialize is
        offered 2025-11-25 even when it names the newer revision.
        """
        response = self._initialize(http, org['key'], version)
        assert response.status_code == 200
        assert response.get_json()['result']['protocolVersion'] == '2025-11-25'

    def test_initialize_result_describes_the_server(self, http, org):
        import version as app_version
        result = self._initialize(http, org['key'], '2025-11-25').get_json()['result']
        assert result['capabilities'] == {'tools': {'listChanged': False}}
        assert result['serverInfo'] == {
            'name': 'decision-records', 'title': 'Decision Records', 'version': app_version.__version__,
        }
        assert 'get_decision_template' in result['instructions']
        assert 'resultType' not in result

    def test_initialize_hands_out_no_session(self, http, org):
        response = self._initialize(http, org['key'], '2025-11-25')
        assert 'Mcp-Session-Id' not in response.headers

    def test_initialize_with_a_wrong_key_is_401(self, http, org):
        response = self._initialize(http, 'adr_wrong', '2025-11-25')
        assert response.status_code == 401
        assert response.headers['WWW-Authenticate'].startswith('Bearer')
        assert response.get_json()['id'] == 'init-1'

    def test_ping_answers_with_an_empty_result(self, http, org):
        response = _legacy_post(http, org['key'], {'jsonrpc': '2.0', 'id': 5, 'method': 'ping'})
        assert response.status_code == 200
        assert response.get_json() == {'jsonrpc': '2.0', 'id': 5, 'result': {}}

    @pytest.mark.parametrize('method', ['notifications/initialized', 'notifications/cancelled'])
    def test_a_notification_is_accepted_with_202_and_no_body(self, http, org, method):
        response = _legacy_post(http, org['key'], {'jsonrpc': '2.0', 'method': method})
        assert response.status_code == 202
        assert response.data == b''

    def test_a_notification_with_a_wrong_key_is_refused(self, http, org):
        response = _legacy_post(http, 'adr_wrong', {'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        assert response.status_code == 401

    def test_a_response_sent_by_the_client_is_accepted_and_ignored(self, http, org):
        response = _legacy_post(http, org['key'], {'jsonrpc': '2.0', 'id': 9, 'result': {}})
        assert response.status_code == 202
        assert response.data == b''

    @pytest.mark.parametrize('version', ['2025-11-25', '2025-06-18', '2025-03-26'])
    def test_a_handshake_revision_in_the_header_is_served(self, http, org, version):
        response = _legacy_post(
            http, org['key'], {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'},
            headers={'MCP-Protocol-Version': version},
        )
        assert response.status_code == 200
        result = response.get_json()['result']
        assert len(result['tools']) == 13
        # Fields of the newer revision are not pushed on older clients.
        assert 'resultType' not in result and 'ttlMs' not in result

    def test_an_unknown_revision_in_the_header_is_400_and_lists_what_is_supported(self, http, org):
        response = _legacy_post(
            http, org['key'], {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'},
            headers={'MCP-Protocol-Version': '2024-11-05'},
        )
        assert response.status_code == 400
        error = response.get_json()['error']
        assert error['code'] == -32022
        assert error['data'] == {'supported': MCP_SUPPORTED_PROTOCOL_VERSIONS, 'requested': '2024-11-05'}

    def test_ping_does_not_exist_in_the_current_revision(self, http, org):
        response = _modern_post(http, org['key'], 'ping')
        assert response.status_code == 404
        assert response.get_json()['error']['code'] == -32601


class TestCurrentRevision:
    """Revision 2026-07-28: no handshake, version and capabilities on every request."""

    def test_tools_list_without_any_handshake(self, http, org):
        response = _modern_post(http, org['key'], 'tools/list')
        assert response.status_code == 200
        assert response.content_type == 'application/json'
        result = response.get_json()['result']
        assert result['resultType'] == 'complete'
        assert len(result['tools']) == 13
        assert result['ttlMs'] > 0
        assert result['cacheScope'] == 'public'
        assert 'nextCursor' not in result
        assert result['_meta'][META_SERVER_INFO]['name'] == 'decision-records'

    def test_tools_call_result(self, http, org):
        response = _modern_post(
            http, org['key'], 'tools/call',
            {'name': 'get_decision', 'arguments': {'id': 'ADR-1'}}, name='get_decision',
        )
        assert response.status_code == 200
        result = response.get_json()['result']
        assert result['resultType'] == 'complete'
        assert result['isError'] is False
        assert result['_meta'][META_SERVER_INFO]['name'] == 'decision-records'
        # Tool results are not cacheable results.
        assert 'ttlMs' not in result
        # The same data twice: structured, and as JSON text for clients that read only text.
        assert result['content'][0]['type'] == 'text'
        assert json.loads(result['content'][0]['text']) == result['structuredContent']
        assert result['structuredContent']['title'] == 'Move to quarterly pricing reviews'

    def test_discover_names_every_supported_revision(self, http, org):
        result = _modern_post(http, org['key'], 'server/discover').get_json()['result']
        assert result['supportedVersions'] == MCP_SUPPORTED_PROTOCOL_VERSIONS
        assert result['resultType'] == 'complete'
        assert result['instructions']

    def test_discover_without_protocol_metadata_is_invalid_params(self, http, org):
        response = _legacy_post(http, org['key'], {'jsonrpc': '2.0', 'id': 1, 'method': 'server/discover'})
        assert response.status_code == 400
        assert response.get_json()['error']['code'] == -32602

    def test_an_unsupported_revision_is_400_with_the_supported_list(self, http, org):
        response = http.post(
            '/api/mcp',
            json=_modern_message('tools/list', version='2030-01-01'),
            headers=_modern_headers(org['key'], 'tools/list', version='2030-01-01'),
        )
        assert response.status_code == 400
        body = response.get_json()
        assert body['id'] == 1
        assert body['error']['code'] == -32022
        assert body['error']['data'] == {'supported': MCP_SUPPORTED_PROTOCOL_VERSIONS, 'requested': '2030-01-01'}

    def test_a_handshake_revision_in_meta_is_not_a_stateless_revision(self, http, org):
        response = http.post(
            '/api/mcp',
            json=_modern_message('tools/list', version='2025-11-25'),
            headers=_modern_headers(org['key'], 'tools/list', version='2025-11-25'),
        )
        assert response.status_code == 400
        assert response.get_json()['error']['code'] == -32022

    def test_missing_client_capabilities_is_invalid_params(self, http, org):
        response = http.post(
            '/api/mcp',
            json=_modern_message('tools/list', capabilities=False),
            headers=_modern_headers(org['key'], 'tools/list'),
        )
        assert response.status_code == 400
        assert response.get_json()['error']['code'] == -32602

    def test_the_current_revision_in_the_header_alone_is_invalid_params(self, http, org):
        """The header mirrors the body; it does not replace the required _meta."""
        response = _legacy_post(
            http, org['key'], {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'},
            headers={'MCP-Protocol-Version': '2026-07-28', 'Mcp-Method': 'tools/list'},
        )
        assert response.status_code == 400
        assert response.get_json()['error']['code'] == -32602

    @pytest.mark.parametrize('drop, change', [
        ('MCP-Protocol-Version', None),
        ('Mcp-Method', None),
        ('Mcp-Name', None),
        (None, ('Mcp-Method', 'tools/list')),
        (None, ('Mcp-Name', 'create_decision')),
    ])
    def test_headers_that_do_not_mirror_the_body_are_a_header_mismatch(self, http, org, drop, change):
        headers = _modern_headers(org['key'], 'tools/call', name='get_decision')
        if drop:
            del headers[drop]
        if change:
            headers[change[0]] = change[1]
        response = http.post(
            '/api/mcp',
            json=_modern_message('tools/call', {'name': 'get_decision', 'arguments': {'id': 'ADR-1'}}),
            headers=headers,
        )
        assert response.status_code == 400
        error = response.get_json()['error']
        assert error['code'] == -32020
        assert error['message'].startswith('Header mismatch')

    def test_a_version_header_that_differs_from_the_body_is_a_header_mismatch(self, http, org):
        response = http.post(
            '/api/mcp',
            json=_modern_message('tools/list'),
            headers=_modern_headers(org['key'], 'tools/list', version='2025-11-25'),
        )
        assert response.status_code == 400
        assert response.get_json()['error']['code'] == -32020

    def test_a_base64_encoded_name_header_is_decoded_before_comparing(self, http, org):
        encoded = '=?base64?' + base64.b64encode(b'get_decision').decode() + '?='
        response = _modern_post(
            http, org['key'], 'tools/call', {'name': 'get_decision', 'arguments': {'id': 'ADR-1'}}, name=encoded,
        )
        assert response.status_code == 200
        assert response.get_json()['result']['isError'] is False

    def test_header_names_are_case_insensitive(self, http, org):
        response = http.post('/api/mcp', json=_modern_message('tools/list'), headers={
            'authorization': f"Bearer {org['key']}",
            'mcp-protocol-version': '2026-07-28',
            'MCP-METHOD': 'tools/list',
        })
        assert response.status_code == 200

    def test_no_session_is_minted_or_echoed(self, http, org):
        headers = _modern_headers(org['key'], 'tools/list')
        headers['Mcp-Session-Id'] = 'abc'
        headers['Last-Event-ID'] = '7'
        response = http.post('/api/mcp', json=_modern_message('tools/list'), headers=headers)
        assert response.status_code == 200
        assert 'Mcp-Session-Id' not in response.headers

    def test_a_notification_is_accepted_with_202(self, http, org):
        message = _modern_message('notifications/cancelled')
        del message['id']
        for headers in (
            _modern_headers(org['key'], 'notifications/cancelled'),
            # The specification does not define the mirrored headers for notification POSTs.
            {'Authorization': f"Bearer {org['key']}"},
        ):
            response = http.post('/api/mcp', json=message, headers=headers)
            assert response.status_code == 202
            assert response.data == b''

    def test_handle_mcp_message_skips_header_rules_outside_http(self, real_app, org):
        payload, status = handle_mcp_message(_modern_message('tools/list'), org['key'], headers=None)
        assert status == 200
        assert payload['result']['resultType'] == 'complete'


class TestJsonRpcAndTransportRules:
    def test_tools_list_unknown_cursor_is_invalid_params(self, http, org):
        response = _legacy_post(http, org['key'], {
            'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list', 'params': {'cursor': 'page-2'},
        })
        assert response.get_json()['error']['code'] == -32602

    def test_unknown_tool_is_a_protocol_error(self, http, org):
        response = _legacy_post(http, org['key'], {
            'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'drop_everything', 'arguments': {}},
        })
        assert response.status_code == 200
        assert response.get_json() == {
            'jsonrpc': '2.0', 'id': 3, 'error': {'code': -32602, 'message': 'Unknown tool: drop_everything'},
        }

    @pytest.mark.parametrize('params', [
        {'arguments': {}},
        {'name': 7, 'arguments': {}},
        {'name': 'get_decision', 'arguments': ['ADR-1']},
        {'name': 'get_decision', 'arguments': 'ADR-1'},
    ])
    def test_a_malformed_tools_call_is_a_protocol_error(self, http, org, params):
        response = _legacy_post(http, org['key'], {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': params})
        assert response.get_json()['error']['code'] == -32602

    def test_tools_call_without_arguments_uses_an_empty_object(self, http, org):
        response = _legacy_post(http, org['key'], {
            'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'get_decision_template'},
        })
        assert response.get_json()['result']['isError'] is False

    def test_a_server_fault_is_an_internal_error_that_leaks_nothing(self, http, org):
        with patch.object(MCPToolHandler, '_get_decision', side_effect=RuntimeError('secret table name')):
            response = _legacy_post(http, org['key'], {
                'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call',
                'params': {'name': 'get_decision', 'arguments': {'id': 'ADR-1'}},
            })
        error = response.get_json()['error']
        assert error['code'] == -32603
        assert 'secret' not in json.dumps(error)

    def test_no_code_from_the_ranges_the_specification_reserves_for_others(self, http, org):
        """-32000..-32019 is closed to new use; -32020..-32099 only as the specification defines."""
        responses = [
            _legacy_post(http, org['key'], {'jsonrpc': '2.0', 'id': 1, 'method': 'nope'}),
            _legacy_post(http, org['read_key'], {
                'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                'params': {'name': 'create_decision', 'arguments': {}},
            }),
            _legacy_post(http, 'adr_wrong', {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'}),
            http.post('/api/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'}),
        ]
        for response in responses:
            error = response.get_json().get('error')
            if error:
                assert not (-32019 <= error['code'] <= -32000), error
                assert not (-32099 <= error['code'] <= -32023), error

    @pytest.mark.parametrize('bad_id', [None, True, 1.5, {'a': 1}, [1]])
    def test_a_request_id_must_be_a_string_or_an_integer(self, http, org, bad_id):
        response = _legacy_post(http, org['key'], {'jsonrpc': '2.0', 'id': bad_id, 'method': 'tools/list'})
        assert response.status_code == 400
        body = response.get_json()
        assert body['error']['code'] == -32600
        assert body['id'] is None

    def test_params_must_be_an_object(self, http, org):
        response = _legacy_post(http, org['key'], {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list', 'params': [1]})
        assert response.status_code == 400
        assert response.get_json()['error']['code'] == -32600

    def test_a_body_that_is_not_an_object_is_an_invalid_request(self, http, org):
        response = _legacy_post(http, org['key'], 'tools/list')
        assert response.status_code == 400
        assert response.get_json()['error']['code'] == -32600

    def test_a_body_that_is_not_json_is_a_parse_error(self, http, org):
        response = http.post(
            '/api/mcp', data='{not json', content_type='application/json',
            headers={'Authorization': f"Bearer {org['key']}"},
        )
        assert response.status_code == 400
        assert response.get_json()['error']['code'] == -32700

    def test_a_batch_is_served_only_for_the_one_revision_that_had_batches(self, http, org):
        batch = [
            {'jsonrpc': '2.0', 'id': 1, 'method': 'ping'},
            {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
            {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
        ]
        for headers in ({}, {'MCP-Protocol-Version': '2025-03-26'}):
            response = _legacy_post(http, org['key'], batch, headers=headers)
            assert response.status_code == 200
            assert [item['id'] for item in response.get_json()] == [1, 2]

        for version in ('2025-06-18', '2025-11-25', '2026-07-28'):
            response = _legacy_post(http, org['key'], batch, headers={'MCP-Protocol-Version': version})
            assert response.status_code == 400
            assert response.get_json()['error']['code'] == -32600

    def test_an_empty_batch_is_an_invalid_request(self, http, org):
        response = _legacy_post(http, org['key'], [])
        assert response.status_code == 400

    def test_a_batch_of_notifications_only_is_202(self, http, org):
        response = _legacy_post(http, org['key'], [{'jsonrpc': '2.0', 'method': 'notifications/initialized'}])
        assert response.status_code == 202


class TestOriginAndAuthorization:
    def test_no_origin_header_is_a_non_browser_client(self, http, org):
        assert _legacy_post(http, org['key'], {'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}).status_code == 200

    @pytest.mark.parametrize('origin', ['https://evil.example', 'null', 'http://localhost:9999'])
    def test_a_foreign_origin_is_403(self, http, org, origin):
        for call in (http.post, http.get):
            response = call('/api/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'},
                            headers={'Authorization': f"Bearer {org['key']}", 'Origin': origin})
            assert response.status_code == 403
            assert response.get_json()['error']['message'] == 'Origin not allowed'

    def test_the_apps_own_origin_and_the_website_are_allowed(self, http, org):
        for origin in ('http://localhost', 'https://decisionrecords.org'):
            response = _legacy_post(
                http, org['key'], {'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}, headers={'Origin': origin},
            )
            assert response.status_code == 200, origin

    def test_an_origin_named_in_the_environment_is_allowed(self, http, org, monkeypatch):
        monkeypatch.setenv('MCP_ALLOWED_ORIGINS', 'https://tools.example , https://other.example/')
        for origin, expected in (('https://tools.example', 200), ('https://other.example', 200),
                                 ('https://third.example', 403)):
            response = _legacy_post(
                http, org['key'], {'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}, headers={'Origin': origin},
            )
            assert response.status_code == expected, origin

    def test_no_key_is_401_with_a_bearer_challenge(self, http, org):
        response = http.post('/api/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'})
        assert response.status_code == 401
        assert response.headers['WWW-Authenticate'].startswith('Bearer')
        # No OAuth is offered, so the challenge must not point at resource metadata.
        assert 'resource_metadata' not in response.headers['WWW-Authenticate']

    def test_a_key_in_the_query_string_is_not_read(self, http, org):
        response = http.post(f"/api/mcp?api_key={org['key']}&access_token={org['key']}",
                             json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'})
        assert response.status_code == 401

    def test_an_organization_with_ai_switched_off_is_403(self, http, org):
        org['tenant'].ai_features_enabled = False
        db.session.commit()
        response = _legacy_post(http, org['key'], {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/list'})
        assert response.status_code == 403
        body = response.get_json()
        assert body['id'] == 4
        assert body['error']['code'] == 403
        assert 'not enabled for this organization' in body['error']['message']
        assert 'WWW-Authenticate' not in response.headers

    def test_the_system_switch_is_403_and_echoes_the_request_id(self, http, org):
        SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'false')
        db.session.commit()
        response = _modern_post(http, org['key'], 'tools/list', request_id='abc')
        assert response.status_code == 403
        body = response.get_json()
        assert body['id'] == 'abc'
        assert 'Enable AI Features (Master Switch)' in body['error']['message']

    @pytest.mark.parametrize('path', [
        '/.well-known/oauth-protected-resource',
        '/.well-known/oauth-protected-resource/api/mcp',
        '/.well-known/oauth-authorization-server',
        '/.well-known/oauth-authorization-server/api/mcp',
    ])
    def test_oauth_metadata_is_an_honest_404_not_the_web_apps_html(self, http, org, path):
        response = http.get(path)
        assert response.status_code == 404
        assert response.content_type == 'application/json'
        assert 'API key' in response.get_json()['error_description']


class TestToolDefinitions:
    def test_every_tool_has_a_title_and_behaviour_hints(self):
        for tool in get_tools():
            assert tool['title'] and len(tool['title']) < 40, tool['name']
            hints = tool['annotations']
            assert isinstance(hints['readOnlyHint'], bool), tool['name']
            assert hints['openWorldHint'] is False, tool['name']

    def test_read_and_write_tools_are_marked_as_such(self):
        tools = {tool['name']: tool for tool in get_tools()}
        assert set(tools) == READ_ONLY_TOOLS | WRITE_TOOLS
        for name in READ_ONLY_TOOLS:
            assert tools[name]['annotations']['readOnlyHint'] is True, name
        for name in WRITE_TOOLS:
            hints = tools[name]['annotations']
            assert hints['readOnlyHint'] is False, name
            # Nothing is erased: history keeps what a change replaces.
            assert hints['destructiveHint'] is False, name
        assert tools['create_decision']['annotations']['idempotentHint'] is False
        assert tools['add_decision_comment']['annotations']['idempotentHint'] is False
        assert tools['update_decision_status']['annotations']['idempotentHint'] is True

    def test_the_write_tools_the_server_enforces_are_the_ones_it_marks(self):
        from ee.backend.ai.mcp import server
        assert set(server.WRITE_TOOLS) == WRITE_TOOLS

    def test_tool_names_use_the_characters_the_specification_allows(self):
        names = [tool['name'] for tool in get_tools()]
        assert len(names) == len(set(names))
        for name in names:
            assert re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', name)

    def test_the_list_is_in_the_same_order_every_time(self):
        assert [t['name'] for t in get_tools()] == [t['name'] for t in get_tools()]

    def test_input_schemas_are_objects_whose_required_fields_exist(self):
        for tool in get_tools():
            schema = tool['inputSchema']
            assert schema['type'] == 'object'
            for field in schema.get('required', []):
                assert field in schema['properties'], (tool['name'], field)

    def test_the_tool_list_is_json_serialisable(self):
        assert json.loads(json.dumps(get_tools())) == get_tools()

    def test_statuses_offered_are_the_products_statuses(self):
        for name in ('search_decisions', 'list_decisions'):
            enum = get_tool_by_name(name)['inputSchema']['properties']['status']['enum']
            assert enum == ['proposed', 'accepted', 'archived', 'superseded']
            assert 'deprecated' not in enum


# ============================================================================
# 2. THE TOOLS AS AN AGENT USES THEM
# ============================================================================

@pytest.fixture
def workspace(app, session):
    """Two organizations. The first has five decisions; handlers with and without write scope."""
    _enable_mcp()
    tenant, user = _make_tenant('first.example', 'First Org')
    other_tenant, other_user = _make_tenant('second.example', 'Second Org', template_id='governance')

    decisions = [
        _make_decision(tenant, user, 1, 'Move to quarterly pricing reviews', decision_type='Pricing and commercial terms',
                       context='Prices were reviewed yearly. Margins fell 100% behind plan.'),
        _make_decision(tenant, user, 2, 'Appoint a second packaging supplier', status='accepted',
                       decision_type='Supplier or partner', context='One supplier is a risk for the autumn range.'),
        _make_decision(tenant, user, 3, 'Use PostgreSQL for the order database', status='accepted',
                       context='We need transactions and a managed service.'),
        _make_decision(tenant, user, 4, 'Hire a second support agent', decision_type='People and hiring'),
        _make_decision(tenant, user, 5, 'Keep the legacy_api until June', decision_type='Kept from an older template'),
    ]
    foreign = _make_decision(other_tenant, other_user, 1, 'Second org pricing decision', status='accepted',
                             decision_type='Appointment')

    write_key, _ = AIApiKeyService.create_key(user, tenant, 'Write', scopes=['read', 'search', 'write'])
    read_key, _ = AIApiKeyService.create_key(user, tenant, 'Read', scopes=['read', 'search'])
    other_key, _ = AIApiKeyService.create_key(other_user, other_tenant, 'Other', scopes=['read', 'search', 'write'])
    return {
        'tenant': tenant, 'user': user, 'decisions': decisions, 'foreign': foreign,
        'other_tenant': other_tenant,
        'write': MCPToolHandler(write_key, tenant, user),
        'read': MCPToolHandler(read_key, tenant, user),
        'other': MCPToolHandler(other_key, other_tenant, other_user),
    }


def _ok(outcome):
    success, result = outcome
    assert success is True, result
    return result


def _refused(outcome):
    success, result = outcome
    assert success is False, result
    assert set(result) == {'error'}
    return result['error']


class TestSearchAndList:
    def test_every_word_must_match_in_any_order_and_any_field(self, workspace):
        result = _ok(workspace['read'].execute_tool('search_decisions', {'query': 'supplier autumn'}))
        assert [d['display_id'] for d in result['decisions']] == ['ADR-002']
        # 'supplier' is in the title, 'autumn' only in the context; the reverse order finds it too.
        assert _ok(workspace['read'].execute_tool('search_decisions', {'query': 'AUTUMN Supplier'}))['total'] == 1

    def test_a_word_that_is_nowhere_gives_nothing_and_a_hint(self, workspace):
        result = _ok(workspace['read'].execute_tool('search_decisions', {'query': 'supplier kubernetes'}))
        assert result['total'] == 0 and result['decisions'] == []
        assert 'list_decisions' in result['hint']

    def test_percent_and_underscore_are_literal(self, workspace):
        assert _ok(workspace['read'].execute_tool('search_decisions', {'query': '100%'}))['total'] == 1
        assert _ok(workspace['read'].execute_tool('search_decisions', {'query': 'legacy_api'}))['total'] == 1
        # As wildcards these would match every decision.
        assert _ok(workspace['read'].execute_tool('search_decisions', {'query': '%'}))['total'] == 1
        assert _ok(workspace['read'].execute_tool('search_decisions', {'query': 'legacyXapi'}))['total'] == 0
        assert _ok(workspace['read'].execute_tool('search_decisions', {'query': '_'}))['total'] == 1

    def test_search_never_returns_another_organizations_decision(self, workspace):
        result = _ok(workspace['read'].execute_tool('search_decisions', {'query': 'pricing'}))
        assert [d['title'] for d in result['decisions']] == ['Move to quarterly pricing reviews']
        assert _ok(workspace['read'].execute_tool('search_decisions', {'query': 'Second org'}))['total'] == 0
        own = _ok(workspace['other'].execute_tool('search_decisions', {'query': 'pricing'}))
        assert [d['title'] for d in own['decisions']] == ['Second org pricing decision']

    def test_search_pages_with_total_has_more_and_next_offset(self, workspace):
        first = _ok(workspace['read'].execute_tool('search_decisions', {'query': 'a', 'limit': 2}))
        assert first['total'] == 5 and first['count'] == 2
        assert first['has_more'] is True and first['next_offset'] == 2
        seen = [d['id'] for d in first['decisions']]

        second = _ok(workspace['read'].execute_tool('search_decisions', {'query': 'a', 'limit': 2, 'offset': 2}))
        third = _ok(workspace['read'].execute_tool('search_decisions', {'query': 'a', 'limit': 2, 'offset': 4}))
        seen += [d['id'] for d in second['decisions']] + [d['id'] for d in third['decisions']]
        assert third['has_more'] is False and third['next_offset'] is None
        assert sorted(seen) == sorted(d.id for d in workspace['decisions'])

    def test_list_pages_and_orders(self, workspace):
        result = _ok(workspace['read'].execute_tool(
            'list_decisions', {'limit': 2, 'order_by': 'decision_number', 'order': 'asc'}
        ))
        assert [d['display_id'] for d in result['decisions']] == ['ADR-001', 'ADR-002']
        assert (result['total'], result['count'], result['offset'], result['limit']) == (5, 2, 0, 2)
        assert result['has_more'] is True and result['next_offset'] == 2

        last = _ok(workspace['read'].execute_tool(
            'list_decisions', {'limit': 2, 'offset': 4, 'order_by': 'decision_number', 'order': 'asc'}
        ))
        assert [d['display_id'] for d in last['decisions']] == ['ADR-005']
        assert last['has_more'] is False and last['next_offset'] is None

    def test_list_excludes_deleted_and_other_organizations(self, workspace):
        from datetime import datetime, timezone
        workspace['decisions'][0].deleted_at = datetime.now(timezone.utc)
        db.session.commit()
        result = _ok(workspace['read'].execute_tool('list_decisions', {}))
        assert result['total'] == 4
        assert 'Second org pricing decision' not in [d['title'] for d in result['decisions']]

    def test_a_summary_carries_ids_an_agent_can_chain(self, workspace):
        summary = _ok(workspace['read'].execute_tool('search_decisions', {'query': 'PostgreSQL'}))['decisions'][0]
        assert set(summary) == {
            'id', 'display_id', 'title', 'status', 'decision_type', 'created_at', 'updated_at',
            'comment_count', 'context_preview',
        }
        by_number = _ok(workspace['read'].execute_tool('get_decision', {'id': str(summary['id'])}))
        by_display = _ok(workspace['read'].execute_tool('get_decision', {'id': summary['display_id']}))
        assert by_number['id'] == by_display['id'] == summary['id']

    def test_a_long_context_is_cut_to_a_preview(self, workspace):
        workspace['decisions'][2].context = 'x' * 500
        db.session.commit()
        summary = _ok(workspace['read'].execute_tool('search_decisions', {'query': 'PostgreSQL'}))['decisions'][0]
        assert summary['context_preview'] == 'x' * 200 + '...'


class TestTolerantInputAndClearErrors:
    def test_an_id_given_as_a_number_is_accepted(self, workspace):
        record = workspace['decisions'][2]
        assert _ok(workspace['read'].execute_tool('get_decision', {'id': record.id}))['title'] == record.title

    def test_a_whole_number_given_as_text_is_accepted_for_a_limit(self, workspace):
        assert _ok(workspace['read'].execute_tool('list_decisions', {'limit': '2'}))['count'] == 2

    def test_an_optional_field_sent_as_null_is_the_same_as_leaving_it_out(self, workspace):
        result = _ok(workspace['read'].execute_tool('list_decisions', {'status': None, 'limit': None, 'offset': None}))
        assert result['total'] == 5 and result['limit'] == 20

    def test_coercion_leaves_everything_else_alone(self):
        assert coerce_tool_arguments('get_decision', {'id': 42}) == {'id': '42'}
        assert coerce_tool_arguments('get_decision', {'id': True}) == {'id': True}
        assert coerce_tool_arguments('list_decisions', {'limit': ' 5 '}) == {'limit': 5}
        assert coerce_tool_arguments('list_decisions', {'limit': 'five'}) == {'limit': 'five'}
        assert coerce_tool_arguments('create_decision', {'title': 7}) == {'title': 7}
        assert coerce_tool_arguments('no_such_tool', {'id': 1}) == {'id': 1}

    def test_true_is_not_an_integer(self):
        assert validate_tool_input('list_decisions', {'limit': True}) == "Field 'limit' must be an integer"

    def test_arguments_must_be_an_object(self, workspace):
        assert validate_tool_input('list_decisions', ['x']) == 'Tool arguments must be a JSON object'
        assert _refused(workspace['read'].execute_tool('list_decisions', ['x'])) == 'Tool arguments must be a JSON object'

    @pytest.mark.parametrize('arguments, message', [
        ({'limit': 0}, "Field 'limit' must be at least 1"),
        ({'limit': 101}, "Field 'limit' must be at most 100"),
        ({'offset': -1}, "Field 'offset' must be at least 0"),
        ({'status': 'deprecated'}, "Field 'status' must be one of: proposed, accepted, archived, superseded"),
        ({'order_by': 'title; DROP TABLE'}, "Field 'order_by' must be one of: created_at, updated_at, decision_number"),
    ])
    def test_validation_names_the_field_and_what_it_accepts(self, workspace, arguments, message):
        assert _refused(workspace['read'].execute_tool('list_decisions', arguments)) == message

    @pytest.mark.parametrize('tool, arguments', [
        ('get_decision', {'id': '99999'}),
        ('get_decision_history', {'id': 'ADR-77'}),
        ('list_decision_comments', {'id': 'the pricing one'}),
        ('list_decision_relationships', {'id': ''}),
    ])
    def test_not_found_is_an_error_that_says_how_to_find_the_id(self, workspace, tool, arguments):
        message = _refused(workspace['read'].execute_tool(tool, arguments))
        assert message.startswith(f"Decision not found: {arguments['id']}. ")
        assert 'search_decisions' in message

    def test_another_organizations_decision_is_not_found(self, workspace):
        foreign = workspace['foreign']
        message = _refused(workspace['read'].execute_tool('get_decision', {'id': str(foreign.id)}))
        assert message.startswith(f'Decision not found: {foreign.id}. ')
        assert 'Second org' not in message

    @pytest.mark.parametrize('tool, arguments', [
        ('create_decision', {'title': 'T', 'context': 'c', 'decision': 'd', 'consequences': 'q'}),
        ('add_decision_comment', {'id': 'ADR-1', 'body': 'Hello'}),
        ('link_decisions', {'source_decision_id': 'ADR-1', 'target_decision_id': 'ADR-2', 'relationship_type': 'supersedes'}),
        ('supersede_decision', {'source_decision_id': 'ADR-1', 'target_decision_id': 'ADR-2'}),
        ('update_decision_status', {'id': 'ADR-1', 'status': 'accepted'}),
    ])
    def test_a_read_only_key_cannot_write_and_is_told_what_is_missing(self, workspace, tool, arguments):
        before = (ArchitectureDecision.query.count(), DecisionComment.query.count(), DecisionHistory.query.count())
        message = _refused(workspace['read'].execute_tool(tool, arguments))
        assert message.startswith('This API key does not have write permission')
        assert 'write scope' in message
        assert before == (
            ArchitectureDecision.query.count(), DecisionComment.query.count(), DecisionHistory.query.count()
        )
        assert workspace['decisions'][0].status == 'proposed'

    def test_an_unknown_relationship_type_points_at_the_catalog(self, workspace):
        message = _refused(workspace['write'].execute_tool('link_decisions', {
            'source_decision_id': 'ADR-1', 'target_decision_id': 'ADR-2', 'relationship_type': 'is nicer than',
        }))
        assert 'get_relationship_catalog' in message
        assert DecisionHistory.query.count() == 0

    def test_an_empty_comment_is_refused(self, workspace):
        message = _refused(workspace['write'].execute_tool('add_decision_comment', {'id': 'ADR-1', 'body': '   '}))
        assert message.startswith('Comment body is required')
        assert DecisionComment.query.count() == 0

    def test_a_server_fault_rolls_back_and_hides_the_cause(self, workspace):
        with patch.object(MCPToolHandler, '_format_decision_full', side_effect=RuntimeError('column xyz missing')):
            success, result = workspace['write'].execute_tool('create_decision', {
                'title': 'Will not be kept', 'context': 'c', 'decision': 'd', 'consequences': 'q',
            })
        assert success is False
        assert 'xyz' not in result['error'] and 'server error' in result['error']
        assert result['internal'] is True

    def test_a_failing_interaction_log_does_not_fail_the_call(self, workspace):
        workspace['tenant'].ai_log_interactions = True
        db.session.commit()
        with patch('ee.backend.ai.mcp.server.AIInteractionLogger.log_interaction', side_effect=RuntimeError('log down')):
            result = _ok(workspace['read'].execute_tool('get_decision', {'id': 'ADR-3'}))
        assert result['title'] == 'Use PostgreSQL for the order database'


class TestCommentsAndHistoryPaging:
    def test_comments_page(self, workspace):
        for number in range(1, 4):
            _ok(workspace['write'].execute_tool('add_decision_comment', {'id': 'ADR-1', 'body': f'Comment {number}'}))

        first = _ok(workspace['read'].execute_tool('list_decision_comments', {'id': 'ADR-1', 'limit': 2}))
        assert [c['body'] for c in first['comments']] == ['Comment 1', 'Comment 2']
        assert (first['total'], first['count'], first['has_more'], first['next_offset']) == (3, 2, True, 2)

        rest = _ok(workspace['read'].execute_tool('list_decision_comments', {'id': 'ADR-1', 'limit': 2, 'offset': 2}))
        assert [c['body'] for c in rest['comments']] == ['Comment 3']
        assert rest['has_more'] is False

    def test_history_pages(self, workspace):
        record = workspace['decisions'][0]
        for number in range(1, 4):
            save_history(record, f'Change {number}', workspace['user'])
            db.session.commit()

        first = _ok(workspace['read'].execute_tool('get_decision_history', {'id': 'ADR-1', 'limit': 2}))
        assert (first['total'], first['count'], first['has_more'], first['next_offset']) == (3, 2, True, 2)
        rest = _ok(workspace['read'].execute_tool('get_decision_history', {'id': 'ADR-1', 'limit': 2, 'offset': 2}))
        assert rest['count'] == 1 and rest['has_more'] is False
        reasons = [h['change_reason'] for h in first['history'] + rest['history']]
        assert sorted(reasons) == ['Change 1', 'Change 2', 'Change 3']


class TestCreateDecision:
    ARGUMENTS = {'title': 'Close the Leeds warehouse', 'context': 'c', 'decision': 'd', 'consequences': 'q'}

    def test_create_returns_ids_to_chain_and_writes_as_the_keys_user(self, workspace):
        result = _ok(workspace['write'].execute_tool('create_decision', dict(self.ARGUMENTS)))
        created = result['decision']
        assert created['display_id'] == 'ADR-006'
        assert result['message'] == 'Decision created successfully as ADR-006'
        stored = db.session.get(ArchitectureDecision, created['id'])
        assert stored.tenant_id == workspace['tenant'].id
        assert stored.created_by_id == workspace['user'].id
        assert stored.status == 'proposed' and stored.decision_type is None

    def test_text_is_cleaned_the_way_the_web_app_cleans_it(self, workspace):
        arguments = dict(self.ARGUMENTS, title='<b>Close</b> the <script>alert(1)</script>warehouse',
                         context='Keep <strong>this</strong><script>alert(1)</script>')
        created = _ok(workspace['write'].execute_tool('create_decision', arguments))['decision']
        assert '<' not in created['title']
        assert '<script>' not in created['context'] and '<strong>this</strong>' in created['context']

    def test_a_title_of_only_markup_is_refused(self, workspace):
        message = _refused(workspace['write'].execute_tool('create_decision', dict(self.ARGUMENTS, title='<p> </p>')))
        assert message.startswith('Title is required')
        assert ArchitectureDecision.query.count() == 6

    def test_text_over_the_web_apps_limit_is_refused(self, workspace):
        message = _refused(workspace['write'].execute_tool(
            'create_decision', dict(self.ARGUMENTS, context='x' * 50001)
        ))
        assert message == "Field 'context' exceeds maximum length of 50000"

    def test_an_unknown_decision_to_supersede_creates_nothing(self, workspace):
        message = _refused(workspace['write'].execute_tool(
            'create_decision', dict(self.ARGUMENTS, supersedes_id='ADR-404')
        ))
        assert message.startswith('Decision not found: ADR-404. ')
        assert ArchitectureDecision.query.count() == 6

    def test_superseding_marks_the_older_decision(self, workspace):
        created = _ok(workspace['write'].execute_tool(
            'create_decision', dict(self.ARGUMENTS, supersedes_id='ADR-2')
        ))['decision']
        assert created['outgoing_relationships'][0]['relationship_type'] == 'supersedes'
        assert db.session.get(ArchitectureDecision, workspace['decisions'][1].id).status == 'superseded'

    def test_another_organizations_decision_cannot_be_superseded(self, workspace):
        foreign = workspace['foreign']
        _refused(workspace['write'].execute_tool(
            'create_decision', dict(self.ARGUMENTS, supersedes_id=str(foreign.id))
        ))
        assert db.session.get(ArchitectureDecision, foreign.id).status == 'accepted'
        assert ArchitectureDecision.query.filter_by(tenant_id=workspace['tenant'].id).count() == 5


# ============================================================================
# 3. DECISION TEMPLATES
# ============================================================================

class TestGetDecisionTemplate:
    def test_the_default_template_for_an_organization_that_has_not_chosen(self, workspace):
        result = _ok(workspace['read'].execute_tool('get_decision_template', {}))
        general = decision_templates.get_template(None)
        assert result['template_id'] == 'general'
        assert result['chosen_by_organization'] is False
        assert result['decision_types'] == general['decision_types']
        assert result['example_titles'] == general['example_titles']
        assert set(result['fields']) == {'title', 'context', 'decision', 'consequences'}

    def test_the_chosen_template_gives_its_own_headings_prompts_and_types(self, workspace):
        result = _ok(workspace['other'].execute_tool('get_decision_template', {}))
        governance = decision_templates.get_template('governance')
        assert result['template_id'] == 'governance'
        assert result['template_name'] == governance['label']
        assert result['chosen_by_organization'] is True
        for key in ('context', 'decision', 'consequences'):
            assert result['fields'][key] == {
                'heading': governance['sections'][key]['label'],
                'hint': governance['sections'][key]['hint'],
                'prompt': governance['sections'][key]['placeholder'],
            }
        assert result['fields']['context']['heading'] == 'Matter and background'
        assert result['fields']['title'] == governance['title']
        assert result['decision_types'] == governance['decision_types']
        assert result['caution'] == governance['caution']

    @pytest.mark.parametrize('template_id', [t['id'] for t in decision_templates.DECISION_TEMPLATES])
    def test_every_template_of_the_core_module_can_be_served(self, workspace, template_id):
        workspace['tenant'].settings.decision_template_id = template_id
        db.session.commit()
        result = _ok(workspace['read'].execute_tool('get_decision_template', {}))
        assert result['template_id'] == template_id
        assert result['decision_types'] == decision_templates.get_decision_types(template_id)
        json.dumps(result)

    def test_a_template_id_that_no_longer_exists_falls_back_to_the_default(self, workspace):
        workspace['tenant'].settings.decision_template_id = 'retired_template'
        db.session.commit()
        result = _ok(workspace['read'].execute_tool('get_decision_template', {}))
        assert result['template_id'] == 'general' and result['chosen_by_organization'] is False

    def test_an_organization_without_a_settings_row_gets_the_default(self, workspace):
        db.session.delete(workspace['tenant'].settings)
        db.session.commit()
        db.session.refresh(workspace['tenant'])
        assert _ok(workspace['read'].execute_tool('get_decision_template', {}))['template_id'] == 'general'

    def test_a_read_only_key_may_read_the_template(self, workspace):
        assert get_tool_by_name('get_decision_template')['annotations']['readOnlyHint'] is True
        _ok(workspace['read'].execute_tool('get_decision_template', {}))

    def test_the_field_names_stay_context_decision_consequences(self, workspace):
        note = _ok(workspace['other'].execute_tool('get_decision_template', {}))['note']
        assert 'context, decision and consequences' in note
        properties = get_tool_by_name('create_decision')['inputSchema']['properties']
        assert {'context', 'decision', 'consequences'} <= set(properties)

    def test_through_json_rpc(self, workspace):
        _, key = AIApiKeyService.create_key(workspace['user'], workspace['tenant'], 'K', scopes=['read'])
        response = handle_mcp_request({
            'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
            'params': {'name': 'get_decision_template', 'arguments': {}},
        }, key)
        assert response['result']['isError'] is False
        assert response['result']['structuredContent']['template_id'] == 'general'


class TestDecisionTypeOnCreate:
    ARGUMENTS = {'title': 'Raise list prices by 4%', 'context': 'c', 'decision': 'd', 'consequences': 'q'}

    def test_a_type_of_the_organizations_template_is_stored(self, workspace):
        created = _ok(workspace['write'].execute_tool(
            'create_decision', dict(self.ARGUMENTS, decision_type='Pricing and commercial terms')
        ))['decision']
        assert created['decision_type'] == 'Pricing and commercial terms'
        assert db.session.get(ArchitectureDecision, created['id']).decision_type == 'Pricing and commercial terms'

    def test_surrounding_spaces_are_ignored(self, workspace):
        created = _ok(workspace['write'].execute_tool(
            'create_decision', dict(self.ARGUMENTS, decision_type='  Policy ')
        ))['decision']
        assert created['decision_type'] == 'Policy'

    @pytest.mark.parametrize('value', ['', '   ', None])
    def test_no_type_is_allowed(self, workspace, value):
        created = _ok(workspace['write'].execute_tool(
            'create_decision', dict(self.ARGUMENTS, decision_type=value)
        ))['decision']
        assert created['decision_type'] is None

    @pytest.mark.parametrize('value', ['Appointment', 'policy', 'Made up type', 'x' * 100])
    def test_a_type_outside_the_template_is_refused_with_the_allowed_list(self, workspace, value):
        """'Appointment' belongs to the governance template, not to this organization's general one."""
        message = _refused(workspace['write'].execute_tool(
            'create_decision', dict(self.ARGUMENTS, decision_type=value)
        ))
        assert message.startswith('Decision type is not one of the types of the current decision template')
        for allowed in decision_templates.get_decision_types(None):
            assert allowed in message
        assert ArchitectureDecision.query.filter_by(title=self.ARGUMENTS['title']).count() == 0

    def test_the_rule_is_the_web_apps_rule(self, workspace):
        """Same function, same verdicts: the MCP tool accepts exactly what the core module accepts."""
        template_id = workspace['other_tenant'].settings.decision_template_id
        for candidate in ['Appointment', 'Policy', 'Service change', 'appointment', ' Appointment ']:
            try:
                expected = decision_templates.normalize_decision_type(candidate, template_id)
                expected_ok = True
            except ValueError:
                expected_ok = False
            success, result = workspace['other'].execute_tool(
                'create_decision', dict(self.ARGUMENTS, decision_type=candidate)
            )
            assert success is expected_ok, candidate
            if expected_ok:
                assert result['decision']['decision_type'] == expected

    def test_a_type_that_is_not_text_is_refused(self, workspace):
        message = _refused(workspace['write'].execute_tool(
            'create_decision', dict(self.ARGUMENTS, decision_type=['Policy'])
        ))
        assert message == "Field 'decision_type' must be a string"

    def test_a_type_longer_than_the_column_is_refused(self, workspace):
        message = _refused(workspace['write'].execute_tool(
            'create_decision', dict(self.ARGUMENTS, decision_type='x' * 101)
        ))
        assert message == "Field 'decision_type' exceeds maximum length of 100"

    def test_create_without_a_type_still_works_as_before(self, workspace):
        created = _ok(workspace['write'].execute_tool('create_decision', dict(self.ARGUMENTS)))['decision']
        assert created['decision_type'] is None


class TestDecisionTypeInResultsAndFilters:
    def test_results_expose_the_type(self, workspace):
        full = _ok(workspace['read'].execute_tool('get_decision', {'id': 'ADR-1'}))
        assert full['decision_type'] == 'Pricing and commercial terms'
        listed = _ok(workspace['read'].execute_tool('list_decisions', {'order_by': 'decision_number', 'order': 'asc'}))
        assert [d['decision_type'] for d in listed['decisions']] == [
            'Pricing and commercial terms', 'Supplier or partner', None, 'People and hiring',
            'Kept from an older template',
        ]
        found = _ok(workspace['read'].execute_tool('search_decisions', {'query': 'supplier'}))
        assert found['decisions'][0]['decision_type'] == 'Supplier or partner'

    def test_a_full_decision_names_the_headings_of_its_organizations_template(self, workspace):
        general = decision_templates.get_template(None)['sections']
        full = _ok(workspace['read'].execute_tool('get_decision', {'id': 'ADR-1'}))
        assert full['section_headings'] == {key: general[key]['label'] for key in decision_templates.SECTION_KEYS}
        # The stored fields keep their names whatever the headings are.
        assert {'context', 'decision', 'consequences'} <= set(full)

        other = _ok(workspace['other'].execute_tool('get_decision', {'id': 'ADR-1'}))
        assert other['section_headings'] == {
            'context': 'Matter and background',
            'decision': 'Decision and reasons',
            'consequences': 'Alternatives, interests and implications',
        }
        assert other['decision_type'] == 'Appointment'

    def test_list_filters_by_type(self, workspace):
        result = _ok(workspace['read'].execute_tool('list_decisions', {'decision_type': 'People and hiring'}))
        assert [d['title'] for d in result['decisions']] == ['Hire a second support agent']
        assert result['total'] == 1

    def test_list_filters_by_type_and_status_together(self, workspace):
        assert _ok(workspace['read'].execute_tool(
            'list_decisions', {'decision_type': 'Supplier or partner', 'status': 'accepted'}
        ))['total'] == 1
        assert _ok(workspace['read'].execute_tool(
            'list_decisions', {'decision_type': 'Supplier or partner', 'status': 'proposed'}
        ))['total'] == 0

    def test_search_filters_by_type(self, workspace):
        assert _ok(workspace['read'].execute_tool('search_decisions', {'query': 'a'}))['total'] == 5
        result = _ok(workspace['read'].execute_tool(
            'search_decisions', {'query': 'a', 'decision_type': 'Pricing and commercial terms'}
        ))
        assert [d['display_id'] for d in result['decisions']] == ['ADR-001']

    def test_a_type_kept_from_an_earlier_template_can_still_be_filtered_on(self, workspace):
        result = _ok(workspace['read'].execute_tool(
            'list_decisions', {'decision_type': 'Kept from an older template'}
        ))
        assert [d['display_id'] for d in result['decisions']] == ['ADR-005']

    def test_an_unused_type_gives_an_empty_list_not_an_error(self, workspace):
        result = _ok(workspace['read'].execute_tool('list_decisions', {'decision_type': 'Spending'}))
        assert result['total'] == 0 and result['decisions'] == []

    def test_the_type_filter_stays_inside_the_organization(self, workspace):
        """The other organization has an 'Appointment' decision; this one must not see it."""
        assert _ok(workspace['read'].execute_tool('list_decisions', {'decision_type': 'Appointment'}))['total'] == 0
        assert _ok(workspace['other'].execute_tool('list_decisions', {'decision_type': 'Appointment'}))['total'] == 1

    def test_an_empty_type_filter_is_no_filter(self, workspace):
        assert _ok(workspace['read'].execute_tool('list_decisions', {'decision_type': ''}))['total'] == 5

    def test_a_type_filter_that_is_not_text_is_refused(self, workspace):
        message = _refused(workspace['read'].execute_tool('list_decisions', {'decision_type': 5}))
        assert message == "Field 'decision_type' must be a string"

    def test_descriptions_tell_an_agent_where_the_types_come_from(self):
        for name in ('search_decisions', 'list_decisions', 'create_decision'):
            description = get_tool_by_name(name)['inputSchema']['properties']['decision_type']['description']
            assert 'get_decision_template' in description, name
        assert 'get_decision_template' in get_tool_by_name('create_decision')['description']
