"""
Tests for the OAuth authorization server over HTTP (Enterprise Edition), through
the real app: ee/backend/oauth_server/endpoints.py, the metadata routes and the
MCP endpoint in app.py, and ee/backend/ai/mcp/server.py.

What is pinned here:

 1. Switched off (the default), everything answers exactly as before OAuth existed.
 2. The metadata documents.
 3. /oauth/authorize never redirects to an address it has not validated.
 4. The consent API: who may see and answer a request, for which organisation.
 5. /oauth/token and /oauth/revoke: every way a request can be wrong.
 6. /api/mcp with an OAuth token: every gate an API key passes, the audience
    check, tenant isolation, the challenges, step-up.
 7. Connected applications: a user's own, and an administrator's organisation.
 8. Framing, CSRF and CORS.
 9. Rate limits.

The application's metadata document is never fetched from the network: the
fetcher is stood in for.

Note: These tests require Enterprise Edition modules from ee/backend/oauth_server/
"""
import base64
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    db, ArchitectureDecision, AuditLog, GlobalRole, MasterAccount, MaturityState, OAuthAuthorizationRequest,
    OAuthClient, OAuthGrant, OAuthToken, SystemConfig, Tenant, TenantMembership, User,
)
from tests.app_test_utils import load_test_app

try:
    from ee.backend.ai import AIApiKeyService
    from ee.backend.ai.mcp import server as mcp_server
    from ee.backend.oauth_server import client_metadata, config as oauth_config, endpoints, rate_limits, service
    from ee.backend.oauth_server.safe_fetch import FetchError, FetchResult
    EE_AVAILABLE = True
except ImportError:
    EE_AVAILABLE = False
    AIApiKeyService = mcp_server = client_metadata = oauth_config = endpoints = rate_limits = service = None
    FetchError = Exception
    FetchResult = None

EE_TESTS_ENABLED = EE_AVAILABLE and os.environ.get('DECISION_RECORDS_EDITION', 'community') == 'enterprise'
pytestmark = pytest.mark.skipif(
    not EE_TESTS_ENABLED,
    reason="Enterprise Edition tests require DECISION_RECORDS_EDITION=enterprise and EE modules",
)

RESOURCE = 'https://decisions.example.org/api/mcp'
ISSUER = 'https://app.decisions.example.org'
RESOURCE_METADATA = 'https://decisions.example.org/.well-known/oauth-protected-resource/api/mcp'
CLIENT_ID = 'https://client.example.org/oauth/client.json'
REDIRECT = 'https://client.example.org/callback'
VERIFIER = 'v' * 64
CHALLENGE = base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).rstrip(b'=').decode()
CSRF = 'test-csrf-token'

LEGACY_CHALLENGE = 'Bearer realm="Decision Records MCP"'
LEGACY_NO_METADATA = {
    'error': 'not_found',
    'error_description': (
        'This server publishes no OAuth metadata. Its MCP endpoint takes a Decision Records API key: '
        'Authorization: Bearer <api_key>'
    ),
}
FULL_CHALLENGE = (
    'Bearer realm="Decision Records MCP", '
    f'resource_metadata="{RESOURCE_METADATA}", scope="decisions:read decisions:write"'
)
INVALID_TOKEN_CHALLENGE = (
    'Bearer realm="Decision Records MCP", error="invalid_token", '
    'error_description="The access token or API key is invalid or has expired", '
    f'resource_metadata="{RESOURCE_METADATA}", scope="decisions:read decisions:write"'
)
INSUFFICIENT_SCOPE_CHALLENGE = (
    'Bearer error="insufficient_scope", scope="decisions:read decisions:write", '
    f'resource_metadata="{RESOURCE_METADATA}", '
    'error_description="Creating or changing decision records needs the decisions:write permission"'
)
TEAMS_ANCESTOR = 'https://teams.microsoft.com'


def _document(**changes):
    document = {
        'client_id': CLIENT_ID, 'client_name': 'Example Client', 'client_uri': 'https://client.example.org',
        'redirect_uris': [REDIRECT, 'http://localhost/callback'], 'token_endpoint_auth_method': 'none',
    }
    document.update(changes)
    return document


class World:
    """One app, two organisations, and the helpers that walk the OAuth flow."""

    def __init__(self, app_module, app, monkeypatch):
        self.app_module = app_module
        self.app = app
        self.monkeypatch = monkeypatch
        self.fetches = []
        self.document = _document()
        self.fetch_error = None

        def fetch(url):
            self.fetches.append(url)
            if self.fetch_error is not None:
                raise self.fetch_error
            return FetchResult(self.document, {})
        monkeypatch.setattr(client_metadata, 'fetch_json', fetch)

        self.tenant = self._tenant('example.com')
        self.other_tenant = self._tenant('other.org')
        self.user = self._user('person@example.com', self.tenant, 'Pat', 'Person')
        self.admin = self._user('admin@example.com', self.tenant, 'Ada', 'Admin', role=GlobalRole.ADMIN)
        self.colleague = self._user('colleague@example.com', self.tenant, 'Col', 'League')
        self.outsider = self._user('someone@other.org', self.other_tenant, 'Out', 'Sider', role=GlobalRole.ADMIN)
        self.decision = self._decision(self.tenant, self.user, 'Use PostgreSQL')
        self.other_decision = self._decision(self.other_tenant, self.outsider, 'Other organisation secret')
        db.session.commit()

    # --- data -----------------------------------------------------------------

    def _tenant(self, domain):
        tenant = Tenant(domain=domain, name=domain.split('.')[0].title(), status='active',
                        maturity_state=MaturityState.BOOTSTRAP, ai_features_enabled=True,
                        ai_external_access_enabled=True, ai_log_interactions=False)
        db.session.add(tenant)
        db.session.flush()
        return tenant

    def _user(self, email, tenant, first, last, role=GlobalRole.USER):
        user = User(email=email, sso_domain=tenant.domain, auth_type='local', email_verified=True)
        user.set_name(first_name=first, last_name=last)
        user.set_password('a-Long-enough-passw0rd!')
        db.session.add(user)
        db.session.flush()
        db.session.add(TenantMembership(user_id=user.id, tenant_id=tenant.id, global_role=role))
        db.session.flush()
        return user

    def _decision(self, tenant, user, title):
        decision = ArchitectureDecision(
            title=title, context='Context', decision='Decided', consequences='Consequences', status='accepted',
            domain=tenant.domain, tenant_id=tenant.id, created_by_id=user.id, decision_number=1)
        db.session.add(decision)
        db.session.flush()
        return decision

    def membership(self, user, tenant=None):
        return TenantMembership.query.filter_by(user_id=user.id, tenant_id=(tenant or self.tenant).id).one()

    def join(self, user, tenant):
        db.session.add(TenantMembership(user_id=user.id, tenant_id=tenant.id, global_role=GlobalRole.USER))
        db.session.commit()

    # --- switches -------------------------------------------------------------

    def enable(self):
        SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
        SystemConfig.set(SystemConfig.KEY_AI_MCP_SERVER_ENABLED, 'true')
        SystemConfig.set(SystemConfig.KEY_AI_EXTERNAL_API_ENABLED, 'true')
        oauth_config.set_enabled(True)

    # --- clients --------------------------------------------------------------

    def anonymous(self):
        return self.app.test_client()

    def signed_in(self, user, csrf=True):
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess['user_id'] = user.id
            sess['_csrf_token'] = CSRF
            sess['_expires_at'] = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        if csrf:
            client.environ_base['HTTP_X_CSRF_TOKEN'] = CSRF
        return client

    def master(self):
        account = MasterAccount(username='root')
        account.set_password('a-Long-enough-passw0rd!')
        db.session.add(account)
        db.session.commit()
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess['is_master'] = True
            sess['master_id'] = account.id
            sess['_csrf_token'] = CSRF
            sess['_expires_at'] = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        client.environ_base['HTTP_X_CSRF_TOKEN'] = CSRF
        return client

    # --- the flow -------------------------------------------------------------

    def authorize_params(self, **changes):
        params = {
            'response_type': 'code', 'client_id': CLIENT_ID, 'redirect_uri': REDIRECT,
            'code_challenge': CHALLENGE, 'code_challenge_method': 'S256', 'resource': RESOURCE,
            'scope': 'decisions:read decisions:write', 'state': 'state-123',
        }
        for name, value in changes.items():
            if value is None:
                params.pop(name, None)
            else:
                params[name] = value
        return params

    def authorize(self, client=None, **changes):
        client = client or self.anonymous()
        return client.get('/oauth/authorize?' + urlencode(self.authorize_params(**changes), doseq=True))

    def start(self, client=None, **changes):
        """An accepted authorization request: its public id."""
        response = self.authorize(client, **changes)
        assert response.status_code == 302, response.get_data(as_text=True)
        location = urlsplit(response.headers['Location'])
        assert f'{location.scheme}://{location.netloc}{location.path}' == ISSUER + '/oauth/consent'
        return parse_qs(location.query)['request'][0]

    def view(self, client, public_id):
        return client.get(f'/api/oauth/requests/{public_id}')

    def decide(self, client, public_id, **body):
        return client.post(f'/api/oauth/requests/{public_id}/decision', json=body)

    def code(self, user=None, tenant=None, scopes=None, **changes):
        """Walk authorize, consent page and approval: the authorization code."""
        user = user or self.user
        client = self.signed_in(user)
        public_id = self.start(**changes)
        assert self.view(client, public_id).status_code == 200
        body = {'decision': 'approve', 'tenant_id': (tenant or self.tenant).id}
        if scopes is not None:
            body['scopes'] = scopes
        response = self.decide(client, public_id, **body)
        assert response.status_code == 200, response.get_data(as_text=True)
        query = parse_qs(urlsplit(response.get_json()['redirect_to']).query)
        return query['code'][0]

    def token_request(self, client=None, **form):
        client = client or self.anonymous()
        return client.post('/oauth/token', data=form)

    def exchange(self, code_value, client=None, **changes):
        form = {'grant_type': 'authorization_code', 'code': code_value, 'client_id': CLIENT_ID,
                'redirect_uri': REDIRECT, 'code_verifier': VERIFIER, 'resource': RESOURCE}
        for name, value in changes.items():
            if value is None:
                form.pop(name, None)
            else:
                form[name] = value
        return self.token_request(client, **form)

    def tokens(self, user=None, tenant=None, scopes=None):
        response = self.exchange(self.code(user=user, tenant=tenant, scopes=scopes))
        assert response.status_code == 200, response.get_data(as_text=True)
        return response.get_json()

    def refresh(self, refresh_token, **changes):
        form = {'grant_type': 'refresh_token', 'refresh_token': refresh_token, 'client_id': CLIENT_ID}
        form.update(changes)
        return self.token_request(**form)

    # --- MCP ------------------------------------------------------------------

    def mcp(self, bearer=None, method='tools/list', params=None, body=None, headers=None):
        send = dict(headers or {})
        if bearer is not None:
            send['Authorization'] = f'Bearer {bearer}'
        message = body if body is not None else {'jsonrpc': '2.0', 'id': 1, 'method': method}
        if params is not None and body is None:
            message['params'] = params
        return self.anonymous().post('/api/mcp', json=message, headers=send)

    def call(self, bearer, tool, arguments=None):
        return self.mcp(bearer, 'tools/call', {'name': tool, 'arguments': arguments or {}})

    def api_key(self, user=None, scopes=('read', 'search')):
        _record, key = AIApiKeyService.create_key(user or self.user, self.tenant, 'Key', scopes=list(scopes))
        return key


@pytest.fixture
def world(monkeypatch):
    monkeypatch.setenv('MCP_RESOURCE_URL', RESOURCE)
    monkeypatch.setenv('OAUTH_ISSUER', ISSUER)
    app_module, app = load_test_app(secret_key='test-secret-key-oauth-endpoints')
    rate_limits.reset()
    with app.app_context():
        db.create_all()
        app_module.init_database()
        yield World(app_module, app, monkeypatch)
        db.session.remove()
        db.drop_all()
        app_module._db_initialized = False
    rate_limits.reset()


@pytest.fixture
def on(world):
    world.enable()
    return world


def _structured(response):
    result = response.get_json()['result']
    assert result.get('isError') is not True, result
    return result['structuredContent']


# ============================================================================
# 1. SWITCHED OFF: EXACTLY AS BEFORE
# ============================================================================

class TestSwitchedOff:
    """With the switch off, every response is byte for byte what it was before OAuth existed."""

    @pytest.fixture(params=['never switched on', 'switched off again'])
    def off(self, world, request):
        SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
        SystemConfig.set(SystemConfig.KEY_AI_MCP_SERVER_ENABLED, 'true')
        if request.param == 'switched off again':
            oauth_config.set_enabled(True)
            oauth_config.set_enabled(False)
        return world

    def test_the_switch_defaults_to_off(self, world):
        assert SystemConfig.get(oauth_config.SWITCH_KEY) is None
        assert oauth_config.is_enabled() is False

    def test_mcp_without_a_credential(self, off):
        response = off.mcp()
        assert response.status_code == 401
        assert response.headers['WWW-Authenticate'] == LEGACY_CHALLENGE
        assert response.get_data() == (
            b'{"error":{"code":401,"message":"Missing or invalid Authorization header. Use: Bearer <api_key>"},'
            b'"id":null,"jsonrpc":"2.0"}\n')

    @pytest.mark.parametrize('bearer', ['adr_not-a-real-key', 'dro_at_looks-like-an-oauth-token', 'anything'])
    def test_mcp_with_an_unknown_credential(self, off, bearer):
        response = off.mcp(bearer)
        assert response.status_code == 401
        assert response.headers['WWW-Authenticate'] == LEGACY_CHALLENGE
        assert response.get_json() == {
            'jsonrpc': '2.0', 'id': 1,
            'error': {'code': 401, 'message': (
                "Invalid or expired API key. Create a new API key in Decision Records and send it as "
                "'Authorization: Bearer <api_key>'.")},
        }

    def test_a_real_oauth_token_is_not_accepted_while_off(self, world):
        world.enable()
        access = world.tokens()['access_token']
        assert world.mcp(access).status_code == 200
        oauth_config.set_enabled(False)

        response = world.mcp(access)
        assert response.status_code == 401
        assert response.headers['WWW-Authenticate'] == LEGACY_CHALLENGE

    def test_api_keys_work_as_before(self, off):
        read_key = off.api_key()
        response = off.mcp(read_key)
        assert response.status_code == 200
        assert 'WWW-Authenticate' not in response.headers

        # A key without the write scope is told so inside the tool result, with 200
        response = off.call(read_key, 'create_decision', {
            'title': 'T', 'context': 'c', 'decision': 'd', 'consequences': 'q'})
        assert response.status_code == 200
        assert 'WWW-Authenticate' not in response.headers
        result = response.get_json()['result']
        assert result['isError'] is True
        assert 'does not have write permission' in result['content'][0]['text']

    def test_a_batch_with_an_unknown_key_is_answered_as_before(self, off):
        response = off.mcp('adr_not-a-real-key', body=[
            {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'},
            {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
        ], headers={'MCP-Protocol-Version': '2025-03-26'})
        assert response.status_code == 200
        assert 'WWW-Authenticate' not in response.headers
        assert [item['error']['code'] for item in response.get_json()] == [401, 401]

    @pytest.mark.parametrize('path', [
        '/.well-known/oauth-protected-resource',
        '/.well-known/oauth-protected-resource/api/mcp',
        '/.well-known/oauth-authorization-server',
        '/.well-known/oauth-authorization-server/api/mcp',
    ])
    def test_metadata_addresses_answer_the_plain_404(self, off, path):
        response = off.anonymous().get(path)
        assert response.status_code == 404
        assert response.mimetype == 'application/json'
        assert response.get_json() == LEGACY_NO_METADATA
        assert 'Access-Control-Allow-Origin' not in response.headers

    @pytest.mark.parametrize('path', ['/.well-known/openid-configuration',
                                      '/.well-known/openid-configuration/api/mcp'])
    def test_openid_configuration_is_a_json_404(self, off, path):
        response = off.anonymous().get(path)
        assert response.status_code == 404
        assert response.get_json() == LEGACY_NO_METADATA

    @pytest.mark.parametrize('method,path', [
        ('get', '/oauth/authorize'),
        ('post', '/oauth/token'),
        ('post', '/oauth/revoke'),
        ('get', '/api/oauth/pending'),
        ('get', '/api/oauth/requests/abc'),
        ('post', '/api/oauth/requests/abc/decision'),
        ('get', '/api/user/oauth/grants'),
        ('delete', '/api/user/oauth/grants/abc'),
        ('get', '/api/tenant/oauth/grants'),
        ('delete', '/api/tenant/oauth/grants/abc'),
    ])
    def test_every_oauth_route_is_404(self, off, method, path):
        for client in (off.anonymous(), off.signed_in(off.admin)):
            response = getattr(client, method)(path)
            assert response.status_code == 404, (method, path)
            if path != '/oauth/authorize':
                assert response.get_json() == {'error': 'Not found'}
        assert OAuthAuthorizationRequest.query.count() == 0

    @pytest.mark.parametrize('ai,mcp', [('false', 'true'), ('true', 'false'), ('false', 'false')])
    def test_the_switch_alone_is_not_enough_without_ai_and_mcp(self, world, ai, mcp):
        """With AI or the MCP server off there is nothing to authorize access to."""
        world.enable()
        SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, ai)
        SystemConfig.set(SystemConfig.KEY_AI_MCP_SERVER_ENABLED, mcp)

        assert oauth_config.is_enabled() is False
        assert world.anonymous().get('/.well-known/oauth-protected-resource').get_json() == LEGACY_NO_METADATA
        assert world.authorize().status_code == 404
        assert world.token_request(grant_type='authorization_code').status_code == 404
        response = world.mcp()
        assert response.headers['WWW-Authenticate'] == LEGACY_CHALLENGE

    def test_the_legacy_enterprise_interface_still_answers(self, off):
        """app.py falls back to handle_mcp_message when the Enterprise module has no handle_mcp_http."""
        off.monkeypatch.delattr(mcp_server, 'handle_mcp_http')
        off.monkeypatch.delattr(mcp_server, 'bearer_challenge')

        response = off.mcp()
        assert response.status_code == 401 and response.headers['WWW-Authenticate'] == LEGACY_CHALLENGE
        response = off.mcp('adr_not-a-real-key')
        assert response.status_code == 401 and response.headers['WWW-Authenticate'] == LEGACY_CHALLENGE
        assert off.mcp(off.api_key()).status_code == 200


# ============================================================================
# 2. METADATA
# ============================================================================

class TestMetadata:

    @pytest.mark.parametrize('path', ['/.well-known/oauth-protected-resource',
                                      '/.well-known/oauth-protected-resource/api/mcp'])
    def test_protected_resource_metadata(self, on, path):
        response = on.anonymous().get(path)
        assert response.status_code == 200
        assert response.mimetype == 'application/json'
        assert response.get_json() == {
            'resource': RESOURCE,
            'authorization_servers': [ISSUER],
            'scopes_supported': ['decisions:read', 'decisions:write'],
            'bearer_methods_supported': ['header'],
            'resource_name': 'Decision Records',
            'resource_documentation': 'https://decisionrecords.org/integrations/mcp',
        }
        assert response.headers['Access-Control-Allow-Origin'] == '*'
        assert 'Access-Control-Allow-Credentials' not in response.headers
        assert response.headers['Cache-Control'] == 'private, max-age=300'

    def test_authorization_server_metadata(self, on):
        response = on.anonymous().get('/.well-known/oauth-authorization-server')
        assert response.status_code == 200
        assert response.get_json() == {
            'issuer': ISSUER,
            'authorization_endpoint': ISSUER + '/oauth/authorize',
            'token_endpoint': ISSUER + '/oauth/token',
            'revocation_endpoint': ISSUER + '/oauth/revoke',
            'response_types_supported': ['code'],
            'response_modes_supported': ['query'],
            'grant_types_supported': ['authorization_code', 'refresh_token'],
            'code_challenge_methods_supported': ['S256'],
            'token_endpoint_auth_methods_supported': ['none'],
            'revocation_endpoint_auth_methods_supported': ['none'],
            'scopes_supported': ['decisions:read', 'decisions:write', 'offline_access'],
            'client_id_metadata_document_supported': True,
            'authorization_response_iss_parameter_supported': True,
            'service_documentation': 'https://decisionrecords.org/integrations/mcp',
        }
        assert 'registration_endpoint' not in response.get_json()
        assert response.headers['Access-Control-Allow-Origin'] == '*'

    @pytest.mark.parametrize('path', [
        '/.well-known/oauth-protected-resource/api/ai',
        '/.well-known/oauth-protected-resource/api/mcp/extra',
        '/.well-known/oauth-protected-resource/other',
        '/.well-known/oauth-authorization-server/api/mcp',
        '/.well-known/oauth-authorization-server/tenant1',
        '/.well-known/openid-configuration',
        '/.well-known/openid-configuration/api/mcp',
    ])
    def test_other_metadata_addresses_are_json_404(self, on, path):
        response = on.anonymous().get(path)
        assert response.status_code == 404
        assert response.mimetype == 'application/json'
        body = response.get_json()
        assert body['error'] == 'not_found'
        assert RESOURCE_METADATA in body['error_description']

    def test_addresses_come_from_the_existing_settings_when_the_specific_ones_are_unset(self, on):
        on.monkeypatch.delenv('MCP_RESOURCE_URL')
        on.monkeypatch.delenv('OAUTH_ISSUER')
        on.monkeypatch.setenv('OAUTH_BASE_URL', 'https://public.example.net/')
        on.monkeypatch.setenv('APP_BASE_URL', 'https://app.example.net')

        resource = on.anonymous().get('/.well-known/oauth-protected-resource').get_json()
        assert resource['resource'] == 'https://public.example.net/api/mcp'
        assert resource['authorization_servers'] == ['https://app.example.net']
        challenge = on.mcp().headers['WWW-Authenticate']
        assert 'resource_metadata="https://public.example.net/.well-known/oauth-protected-resource/api/mcp"' in challenge

    def test_the_metadata_is_what_the_endpoints_enforce(self, on):
        """The documented endpoints exist, and a token from the flow is valid for the documented resource."""
        metadata = on.anonymous().get('/.well-known/oauth-authorization-server').get_json()
        for name in ('authorization_endpoint', 'token_endpoint', 'revocation_endpoint'):
            path = urlsplit(metadata[name]).path
            assert any(rule.rule == path for rule in on.app.url_map.iter_rules()), name
        tokens = on.tokens()
        assert OAuthGrant.query.one().resource == on.anonymous().get(
            '/.well-known/oauth-protected-resource').get_json()['resource']
        assert on.mcp(tokens['access_token']).status_code == 200


# ============================================================================
# 3. GET /oauth/authorize
# ============================================================================

class TestAuthorize:

    def test_an_accepted_request_goes_to_the_consent_page_and_fetches_nothing(self, on):
        response = on.authorize()

        assert response.status_code == 302
        public_id = parse_qs(urlsplit(response.headers['Location']).query)['request'][0]
        assert response.headers['Location'] == f'{ISSUER}/oauth/consent?request={public_id}'
        assert response.headers['Cache-Control'] == 'no-store'
        stored = OAuthAuthorizationRequest.query.one()
        assert stored.public_id == public_id
        assert stored.client_identifier == CLIENT_ID and stored.oauth_client_id is None
        assert stored.redirect_uri == REDIRECT and stored.state == 'state-123'
        assert stored.resource == RESOURCE
        assert stored.requested_scopes == ['decisions:read', 'decisions:write']
        assert stored.user_id is None and stored.code_hash is None
        # Nothing was fetched for an anonymous visitor, and nothing was granted
        assert on.fetches == []
        assert OAuthClient.query.count() == 0 and OAuthGrant.query.count() == 0

    def test_the_pending_cookie(self, on):
        response = on.authorize()
        cookie = [value for value in response.headers.getlist('Set-Cookie')
                  if value.startswith(endpoints.PENDING_COOKIE + '=')][0]
        public_id = parse_qs(urlsplit(response.headers['Location']).query)['request'][0]
        assert cookie.startswith(f'{endpoints.PENDING_COOKIE}={public_id};')
        assert 'HttpOnly' in cookie and 'SameSite=Lax' in cookie and 'Max-Age=600' in cookie

    def test_resource_may_be_left_out_and_unknown_scopes_are_dropped(self, on):
        on.start(resource=None, scope='openid email decisions:read offline_access')
        stored = OAuthAuthorizationRequest.query.one()
        assert stored.resource == RESOURCE
        assert stored.requested_scopes == ['decisions:read']

    def test_no_scope_means_reading(self, on):
        on.start(scope=None)
        assert OAuthAuthorizationRequest.query.one().requested_scopes == ['decisions:read']

    @pytest.mark.parametrize('changes,error', [
        ({'response_type': None}, 'unsupported_response_type'),
        ({'response_type': 'token'}, 'unsupported_response_type'),
        ({'response_type': 'code token'}, 'unsupported_response_type'),
        ({'client_id': None}, 'invalid_client'),
        ({'client_id': 'client-123'}, 'invalid_client'),
        ({'client_id': 'http://client.example.org/oauth/client.json'}, 'invalid_client'),
        ({'client_id': 'https://client.example.org/'}, 'invalid_client'),
        ({'client_id': 'https://client.example.org/client.json?x=1'}, 'invalid_client'),
        ({'client_id': 'https://127.0.0.1/client.json'}, 'invalid_client'),
        ({'client_id': 'https://169.254.169.254/latest/meta-data'}, 'invalid_client'),
        ({'client_id': 'https://localhost/client.json'}, 'invalid_client'),
        ({'client_id': 'https://database.internal/client.json'}, 'invalid_client'),
        ({'client_id': 'https://user:pw@client.example.org/client.json'}, 'invalid_client'),
        ({'client_id': 'https://client.example.org/"><script>alert(1)</script>'}, 'invalid_client'),
        ({'redirect_uri': None}, 'invalid_request'),
        ({'redirect_uri': 'http://client.example.org/callback'}, 'invalid_request'),
        ({'redirect_uri': 'javascript:alert(1)'}, 'invalid_request'),
        ({'redirect_uri': 'cursor://callback'}, 'invalid_request'),
        ({'redirect_uri': 'https://client.example.org/callback#frag'}, 'invalid_request'),
        ({'redirect_uri': 'https://user@client.example.org/callback'}, 'invalid_request'),
        ({'redirect_uri': '//evil.example.net/callback'}, 'invalid_request'),
        ({'code_challenge': None}, 'invalid_request'),
        ({'code_challenge': 'short'}, 'invalid_request'),
        ({'code_challenge': VERIFIER}, 'invalid_request'),
        ({'code_challenge_method': None}, 'invalid_request'),
        ({'code_challenge_method': 'plain'}, 'invalid_request'),
        ({'code_challenge_method': 's256'}, 'invalid_request'),
        ({'resource': 'https://evil.example.net/api/mcp'}, 'invalid_target'),
        ({'resource': 'https://decisions.example.org/api/ai'}, 'invalid_target'),
        ({'resource': 'https://decisions.example.org'}, 'invalid_target'),
        ({'state': 's' * 1025}, 'invalid_request'),
        # A parameter given twice
        ({'redirect_uri': [REDIRECT, 'https://evil.example.net/callback']}, 'invalid_request'),
        ({'client_id': [CLIENT_ID, 'https://evil.example.net/client.json']}, 'invalid_request'),
        ({'response_type': ['code', 'code']}, 'invalid_request'),
        ({'state': ['a', 'b']}, 'invalid_request'),
        ({'resource': [RESOURCE, 'https://evil.example.net/api/mcp']}, 'invalid_request'),
        ({'code_challenge': [CHALLENGE, CHALLENGE]}, 'invalid_request'),
        ({'scope': ['decisions:read', 'decisions:write']}, 'invalid_request'),
    ])
    def test_a_bad_request_is_answered_here_and_never_redirected(self, on, changes, error):
        response = on.authorize(**changes)

        assert response.status_code == 400
        assert 'Location' not in response.headers
        assert response.mimetype == 'text/html'
        page = response.get_data(as_text=True)
        assert f'Error: {error}' in page
        assert '<script>' not in page and 'evil.example.net' not in page
        assert endpoints.PENDING_COOKIE not in ' '.join(response.headers.getlist('Set-Cookie'))
        assert response.headers['Cache-Control'] == 'no-store'
        assert OAuthAuthorizationRequest.query.count() == 0
        assert on.fetches == []

    def test_only_get_is_accepted(self, on):
        assert on.anonymous().post('/oauth/authorize', data=on.authorize_params()).status_code == 405

    def test_a_signed_in_visitor_is_treated_the_same(self, on):
        """Being signed in does not skip the consent page or fetch anything at this step."""
        public_id = on.start(on.signed_in(on.user))
        stored = OAuthAuthorizationRequest.query.filter_by(public_id=public_id).one()
        assert stored.user_id is None and stored.decision is None
        assert on.fetches == []


# ============================================================================
# 4. THE CONSENT API
# ============================================================================

class TestConsentView:

    def test_what_the_consent_page_is_given(self, on):
        on.join(on.user, on.other_tenant)
        on.other_tenant.ai_features_enabled = False
        db.session.commit()
        public_id = on.start()

        response = on.view(on.signed_in(on.user), public_id)

        assert response.status_code == 200
        body = response.get_json()
        assert body['request'] == public_id
        assert body['application'] == {
            'host': 'client.example.org', 'claimed_name': 'Example Client',
            'client_id': CLIENT_ID, 'client_uri': 'https://client.example.org',
        }
        assert body['redirect'] == {'host': 'client.example.org', 'is_loopback': False,
                                    'loopback_only_client': False}
        assert [scope['name'] for scope in body['scopes']] == ['decisions:read', 'decisions:write']
        assert [scope['optional'] for scope in body['scopes']] == [False, True]
        assert body['user'] == {'id': on.user.id, 'name': 'Pat Person', 'email': 'person@example.com'}
        assert body['organisations'] == [
            {'id': on.tenant.id, 'name': 'Example', 'domain': 'example.com', 'eligible': True, 'reason': None,
             'is_default': True},
            {'id': on.other_tenant.id, 'name': 'Other', 'domain': 'other.org', 'eligible': False,
             'reason': 'ai_disabled', 'is_default': False},
        ]
        assert response.headers['Cache-Control'] == 'no-store'
        # This is where the application's document was fetched, once, and the request tied to it and the user
        assert on.fetches == [CLIENT_ID]
        stored = OAuthAuthorizationRequest.query.one()
        assert stored.user_id == on.user.id
        assert stored.oauth_client_id == OAuthClient.query.one().id

    def test_looking_again_does_not_fetch_again(self, on):
        public_id = on.start()
        client = on.signed_in(on.user)
        on.view(client, public_id)
        assert on.view(client, public_id).status_code == 200
        assert on.fetches == [CLIENT_ID]

    def test_a_loopback_application_is_flagged_for_the_warning(self, on):
        on.document = _document(redirect_uris=['http://localhost/callback', 'http://127.0.0.1/callback'])
        public_id = on.start(redirect_uri='http://localhost:49152/callback')
        body = on.view(on.signed_in(on.user), public_id).get_json()
        assert body['redirect'] == {'host': 'localhost', 'is_loopback': True, 'loopback_only_client': True}

    def test_an_opted_out_member_sees_why(self, on):
        on.membership(on.user).ai_opt_out = True
        db.session.commit()
        body = on.view(on.signed_in(on.user), on.start()).get_json()
        assert body['organisations'][0]['eligible'] is False
        assert body['organisations'][0]['reason'] == 'opted_out'

    def test_a_deleted_organisation_is_not_offered(self, on):
        on.join(on.user, on.other_tenant)
        on.other_tenant.deleted_at = datetime.now(timezone.utc)
        db.session.commit()
        body = on.view(on.signed_in(on.user), on.start()).get_json()
        assert [org['domain'] for org in body['organisations']] == ['example.com']

    def test_it_needs_a_signed_in_organisation_account(self, on):
        public_id = on.start()
        response = on.view(on.anonymous(), public_id)
        assert response.status_code == 401
        assert on.fetches == []                      # an anonymous visitor cannot cause a fetch

        response = on.view(on.master(), public_id)
        assert response.status_code == 403
        assert on.fetches == []
        assert OAuthAuthorizationRequest.query.one().user_id is None

    def test_unknown_and_expired_requests(self, on):
        client = on.signed_in(on.user)
        assert on.view(client, 'no-such-request').status_code == 404
        public_id = on.start()
        OAuthAuthorizationRequest.query.one().expires_at = datetime(2020, 1, 1)
        db.session.commit()
        response = on.view(client, public_id)
        assert response.status_code == 404 and response.get_json()['code'] == 'request_gone'
        assert on.fetches == []

    def test_a_request_belongs_to_the_first_account_that_opens_it(self, on):
        public_id = on.start()
        assert on.view(on.signed_in(on.user), public_id).status_code == 200

        response = on.view(on.signed_in(on.colleague), public_id)
        assert response.status_code == 403 and response.get_json()['code'] == 'other_account'
        response = on.decide(on.signed_in(on.colleague), public_id, decision='approve', tenant_id=on.tenant.id)
        assert response.status_code == 409
        assert OAuthAuthorizationRequest.query.one().decision is None

    @pytest.mark.parametrize('document', [
        _document(client_id='https://other.example.org/client.json'),
        _document(client_name=''),
        _document(client_secret='s3cret'),
        _document(token_endpoint_auth_method='client_secret_basic'),
        _document(redirect_uris=['cursor://callback']),
        _document(redirect_uris=['https://client.example.org/another-callback']),   # not the one in the request
        _document(redirect_uris=['https://client.example.org/callback/']),
        _document(redirect_uris=['https://client.example.org:8443/callback']),
    ])
    def test_an_unacceptable_application_cannot_be_approved_and_is_never_redirected_to(self, on, document):
        on.document = document
        public_id = on.start()
        client = on.signed_in(on.user)

        response = on.view(client, public_id)

        assert response.status_code == 400
        assert response.get_json()['code'] == 'client_invalid'
        assert 'redirect_to' not in response.get_json() and 'Location' not in response.headers
        assert OAuthAuthorizationRequest.query.one().oauth_client_id is None
        for decision in ('approve', 'deny'):
            answer = on.decide(client, public_id, decision=decision, tenant_id=on.tenant.id)
            assert answer.status_code == 409
            assert 'redirect_to' not in answer.get_json()
        assert OAuthAuthorizationRequest.query.one().code_hash is None

    def test_an_unreachable_application(self, on):
        on.fetch_error = FetchError('The server answered 503', transient=True)
        response = on.view(on.signed_in(on.user), on.start())
        assert response.status_code == 503 and response.get_json()['code'] == 'client_unavailable'

        on.fetch_error = FetchError('The host resolves to an address that is not on the public internet')
        response = on.view(on.signed_in(on.user), on.start())
        assert response.status_code == 400 and response.get_json()['code'] == 'client_invalid'
        assert OAuthClient.query.count() == 0

    def test_a_blocked_application(self, on):
        client = on.signed_in(on.user)
        on.view(client, on.start())
        OAuthClient.query.one().disabled_at = datetime.now(timezone.utc)
        db.session.commit()
        response = on.view(client, on.start())
        assert response.status_code == 400
        assert 'blocked' in response.get_json()['error']


class TestPendingRequest:

    def test_the_browser_that_started_is_led_back_after_sign_in(self, on):
        browser = on.signed_in(on.user)
        public_id = on.start(browser)
        assert browser.get('/api/oauth/pending').get_json() == {'request': public_id}

    def test_another_browser_has_nothing_pending(self, on):
        on.start()
        assert on.signed_in(on.user).get('/api/oauth/pending').get_json() == {'request': None}

    def test_nothing_is_pending_after_the_decision(self, on):
        browser = on.signed_in(on.user)
        public_id = on.start(browser)
        on.view(browser, public_id)
        response = on.decide(browser, public_id, decision='deny')
        assert any(value.startswith(endpoints.PENDING_COOKIE + '=;') for value in response.headers.getlist('Set-Cookie'))
        assert browser.get('/api/oauth/pending').get_json() == {'request': None}

    def test_a_request_opened_by_someone_else_is_not_handed_over(self, on):
        browser = on.anonymous()
        public_id = on.start(browser)
        on.view(on.signed_in(on.user), public_id)
        # The same browser, now signed in as a colleague
        with browser.session_transaction() as sess:
            sess['user_id'] = on.colleague.id
            sess['_csrf_token'] = CSRF
            sess['_expires_at'] = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        assert browser.get('/api/oauth/pending').get_json() == {'request': None}

    def test_it_needs_a_session(self, on):
        assert on.anonymous().get('/api/oauth/pending').status_code == 401


class TestDecision:

    def _viewed(self, on, user=None, **changes):
        client = on.signed_in(user or on.user)
        public_id = on.start(**changes)
        assert on.view(client, public_id).status_code == 200
        return client, public_id

    def test_approval_sends_the_browser_back_with_code_state_and_issuer(self, on):
        client, public_id = self._viewed(on)

        response = on.decide(client, public_id, decision='approve', tenant_id=on.tenant.id)

        assert response.status_code == 200
        target = urlsplit(response.get_json()['redirect_to'])
        assert f'{target.scheme}://{target.netloc}{target.path}' == REDIRECT
        query = parse_qs(target.query)
        assert set(query) == {'code', 'state', 'iss'}
        assert query['state'] == ['state-123'] and query['iss'] == [ISSUER]
        assert query['code'][0].startswith('dro_ac_')
        stored = OAuthAuthorizationRequest.query.one()
        assert stored.tenant_id == on.tenant.id and stored.user_id == on.user.id
        assert stored.code_hash == hashlib.sha256(query['code'][0].encode()).hexdigest()
        assert response.headers['Cache-Control'] == 'no-store'
        assert OAuthGrant.query.count() == 0     # no grant until the code is exchanged

    def test_the_redirect_keeps_the_query_the_application_registered_and_encodes_state(self, on):
        registered = 'https://client.example.org/callback?tenant=a&x=1'
        on.document = _document(redirect_uris=[registered])
        state = 'a b&c=d#e/é"<>'
        client, public_id = self._viewed(on, redirect_uri=registered, state=state)

        target = on.decide(client, public_id, decision='approve', tenant_id=on.tenant.id).get_json()['redirect_to']

        assert target.startswith('https://client.example.org/callback?tenant=a&x=1&code=')
        assert '#' not in target and '<' not in target and ' ' not in target
        query = parse_qs(urlsplit(target).query)
        assert query['tenant'] == ['a'] and query['x'] == ['1'] and query['state'] == [state]

    def test_refusal_sends_the_browser_back_with_an_error_and_no_code(self, on):
        client, public_id = self._viewed(on)

        response = on.decide(client, public_id, decision='deny')

        query = parse_qs(urlsplit(response.get_json()['redirect_to']).query)
        assert query['error'] == ['access_denied'] and query['state'] == ['state-123'] and query['iss'] == [ISSUER]
        assert 'code' not in query
        assert OAuthAuthorizationRequest.query.one().code_hash is None

    def test_a_loopback_redirect_goes_to_the_port_the_application_asked_for(self, on):
        client, public_id = self._viewed(on, redirect_uri='http://localhost:49152/callback')
        target = on.decide(client, public_id, decision='approve', tenant_id=on.tenant.id).get_json()['redirect_to']
        assert target.startswith('http://localhost:49152/callback?code=')

    def test_the_csrf_token_is_required(self, on):
        _client, public_id = self._viewed(on)
        without_token = on.signed_in(on.user, csrf=False)

        response = on.decide(without_token, public_id, decision='approve', tenant_id=on.tenant.id)
        assert response.status_code == 403
        assert response.get_json() == {'error': 'CSRF token missing or invalid'}

        without_token.environ_base['HTTP_X_CSRF_TOKEN'] = 'a-guess'
        response = on.decide(without_token, public_id, decision='approve', tenant_id=on.tenant.id)
        assert response.status_code == 403
        assert OAuthAuthorizationRequest.query.one().decision is None

    @pytest.mark.parametrize('origin', ['https://evil.example.net', 'https://client.example.org', 'null'])
    def test_a_cross_site_request_is_refused_even_with_the_token(self, on, origin):
        client, public_id = self._viewed(on)
        response = client.post(f'/api/oauth/requests/{public_id}/decision',
                               json={'decision': 'approve', 'tenant_id': on.tenant.id},
                               headers={'Origin': origin})
        assert response.status_code == 403
        assert OAuthAuthorizationRequest.query.one().decision is None

    def test_the_apps_own_origin_is_accepted(self, on):
        client, public_id = self._viewed(on)
        response = client.post(f'/api/oauth/requests/{public_id}/decision',
                               json={'decision': 'approve', 'tenant_id': on.tenant.id},
                               headers={'Origin': ISSUER})
        assert response.status_code == 200

    def test_the_consent_page_must_have_been_opened_first(self, on):
        public_id = on.start()
        response = on.decide(on.signed_in(on.user), public_id, decision='approve', tenant_id=on.tenant.id)
        assert response.status_code == 409 and response.get_json()['code'] == 'not_viewed'
        assert on.fetches == []

    def test_only_for_an_organisation_the_user_belongs_to(self, on):
        client, public_id = self._viewed(on)
        for tenant_id in (on.other_tenant.id, 999999):
            response = on.decide(client, public_id, decision='approve', tenant_id=tenant_id)
            assert response.status_code == 403 and response.get_json()['code'] == 'not_a_member'
        assert OAuthAuthorizationRequest.query.one().decision is None

    def test_not_for_an_organisation_with_ai_switched_off(self, on):
        client, public_id = self._viewed(on)
        on.tenant.ai_features_enabled = False
        db.session.commit()

        response = on.decide(client, public_id, decision='approve', tenant_id=on.tenant.id)

        assert response.status_code == 403 and response.get_json()['code'] == 'ai_disabled'
        assert 'redirect_to' not in response.get_json()
        assert OAuthAuthorizationRequest.query.one().code_hash is None
        # The user can still refuse, which tells the application
        assert on.decide(client, public_id, decision='deny').status_code == 200

    def test_not_for_a_member_who_opted_out_of_ai(self, on):
        client, public_id = self._viewed(on)
        on.membership(on.user).ai_opt_out = True
        db.session.commit()
        response = on.decide(client, public_id, decision='approve', tenant_id=on.tenant.id)
        assert response.status_code == 403 and response.get_json()['code'] == 'opted_out'

    def test_not_for_a_deleted_organisation(self, on):
        client, public_id = self._viewed(on)
        on.tenant.deleted_at = datetime.now(timezone.utc)
        db.session.commit()
        response = on.decide(client, public_id, decision='approve', tenant_id=on.tenant.id)
        assert response.status_code == 403

    def test_the_user_chooses_the_organisation(self, on):
        on.join(on.user, on.other_tenant)
        access = on.tokens(tenant=on.other_tenant)['access_token']
        titles = [d['title'] for d in _structured(on.call(access, 'list_decisions'))['decisions']]
        assert titles == ['Other organisation secret']

    @pytest.mark.parametrize('body', [
        {}, {'decision': 'maybe'}, {'decision': 'approve'}, {'decision': 'approve', 'tenant_id': 'one'},
        {'decision': 'approve', 'tenant_id': True}, {'decision': 'approve', 'tenant_id': None},
        {'decision': ['approve']},
    ])
    def test_malformed_decisions(self, on, body):
        client, public_id = self._viewed(on)
        assert on.decide(client, public_id, **body).status_code == 400
        assert OAuthAuthorizationRequest.query.one().decision is None

    def test_malformed_scopes(self, on):
        client, public_id = self._viewed(on)
        response = on.decide(client, public_id, decision='approve', tenant_id=on.tenant.id, scopes='decisions:read')
        assert response.status_code == 400

    def test_a_request_is_answered_once(self, on):
        client, public_id = self._viewed(on)
        assert on.decide(client, public_id, decision='approve', tenant_id=on.tenant.id).status_code == 200
        for decision in ('approve', 'deny'):
            response = on.decide(client, public_id, decision=decision, tenant_id=on.tenant.id)
            assert response.status_code == 404
            assert 'redirect_to' not in response.get_json()

    def test_an_expired_request_cannot_be_answered(self, on):
        client, public_id = self._viewed(on)
        OAuthAuthorizationRequest.query.one().expires_at = datetime(2020, 1, 1)
        db.session.commit()
        assert on.decide(client, public_id, decision='approve', tenant_id=on.tenant.id).status_code == 404

    def test_it_needs_a_signed_in_organisation_account(self, on):
        _client, public_id = self._viewed(on)
        assert on.decide(on.anonymous(), public_id, decision='approve', tenant_id=on.tenant.id).status_code == 401
        assert on.decide(on.master(), public_id, decision='approve', tenant_id=on.tenant.id).status_code == 403


# ============================================================================
# 5. /oauth/token AND /oauth/revoke
# ============================================================================

class TestTokenEndpoint:

    def test_a_code_is_exchanged_for_tokens(self, on):
        response = on.exchange(on.code())

        assert response.status_code == 200
        body = response.get_json()
        assert set(body) == {'access_token', 'token_type', 'expires_in', 'refresh_token', 'scope'}
        assert body['token_type'] == 'Bearer' and body['expires_in'] == 3600
        assert body['scope'] == 'decisions:read decisions:write'
        assert response.headers['Cache-Control'] == 'no-store' and response.headers['Pragma'] == 'no-cache'
        assert response.headers['Access-Control-Allow-Origin'] == '*'
        grant = OAuthGrant.query.one()
        assert (grant.user_id, grant.tenant_id, grant.resource) == (on.user.id, on.tenant.id, RESOURCE)
        entry = AuditLog.query.filter_by(action_type=service.AUDIT_GRANT_CREATED).one()
        assert entry.tenant_id == on.tenant.id and entry.actor_user_id == on.user.id
        assert body['access_token'] not in json.dumps(entry.details)

    def test_what_the_user_switched_off_is_not_granted(self, on):
        body = on.tokens(scopes=['decisions:read'])
        assert body['scope'] == 'decisions:read'

    def test_the_user_cannot_be_given_more_than_the_application_asked_for(self, on):
        client = on.signed_in(on.user)
        public_id = on.start(scope='decisions:read')
        on.view(client, public_id)
        target = on.decide(client, public_id, decision='approve', tenant_id=on.tenant.id,
                           scopes=['decisions:read', 'decisions:write']).get_json()['redirect_to']
        body = on.exchange(parse_qs(urlsplit(target).query)['code'][0]).get_json()
        assert body['scope'] == 'decisions:read'

    @pytest.mark.parametrize('changes,status,error', [
        ({'code_verifier': 'w' * 64}, 400, 'invalid_grant'),
        ({'code_verifier': None}, 400, 'invalid_grant'),
        ({'code_verifier': CHALLENGE}, 400, 'invalid_grant'),
        ({'client_id': 'https://other.example.org/client.json'}, 400, 'invalid_grant'),
        ({'client_id': None}, 400, 'invalid_request'),
        ({'redirect_uri': 'https://client.example.org/callback/'}, 400, 'invalid_grant'),
        ({'redirect_uri': 'https://evil.example.net/callback'}, 400, 'invalid_grant'),
        ({'redirect_uri': None}, 400, 'invalid_grant'),
        ({'resource': 'https://evil.example.net/api/mcp'}, 400, 'invalid_target'),
        ({'resource': 'https://decisions.example.org/api/ai'}, 400, 'invalid_target'),
        ({'code': None}, 400, 'invalid_grant'),
        ({'code': 'dro_ac_not-a-code'}, 400, 'invalid_grant'),
        ({'grant_type': None}, 400, 'unsupported_grant_type'),
        ({'grant_type': 'client_credentials'}, 400, 'unsupported_grant_type'),
        ({'grant_type': 'password'}, 400, 'unsupported_grant_type'),
        ({'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer'}, 400, 'unsupported_grant_type'),
        ({'client_secret': 'anything'}, 401, 'invalid_client'),
        ({'client_assertion': 'eyJ...'}, 401, 'invalid_client'),
        ({'client_id': 'x' * 600}, 401, 'invalid_client'),
    ])
    def test_a_wrong_request_gets_no_tokens_and_the_right_one_still_works(self, on, changes, status, error):
        code = on.code()

        response = on.exchange(code, **changes)

        assert response.status_code == status
        assert response.get_json()['error'] == error
        assert response.headers['Cache-Control'] == 'no-store'
        assert OAuthGrant.query.count() == 0 and OAuthToken.query.count() == 0
        # Someone else's wrong attempt does not use up the real application's code
        assert on.exchange(code).status_code == 200

    def test_a_code_works_once_and_using_it_again_ends_the_connection(self, on):
        code = on.code()
        first = on.exchange(code).get_json()
        assert on.mcp(first['access_token']).status_code == 200

        response = on.exchange(code)

        assert response.status_code == 400 and response.get_json()['error'] == 'invalid_grant'
        assert on.mcp(first['access_token']).status_code == 401
        assert on.refresh(first['refresh_token']).status_code == 400
        assert OAuthGrant.query.one().revoke_reason == 'code_reuse'

    def test_an_expired_code(self, on):
        code = on.code()
        OAuthAuthorizationRequest.query.one().code_expires_at = datetime(2020, 1, 1)
        db.session.commit()
        response = on.exchange(code)
        assert response.status_code == 400 and response.get_json()['error'] == 'invalid_grant'
        assert OAuthGrant.query.count() == 0

    def test_only_form_encoding_is_accepted(self, on):
        code = on.code()
        response = on.anonymous().post('/oauth/token', json={
            'grant_type': 'authorization_code', 'code': code, 'client_id': CLIENT_ID,
            'redirect_uri': REDIRECT, 'code_verifier': VERIFIER})
        assert response.status_code == 400 and response.get_json()['error'] == 'invalid_request'
        assert on.exchange(code).status_code == 200

    def test_a_repeated_parameter_is_refused(self, on):
        code = on.code()
        response = on.anonymous().post('/oauth/token', data={
            'grant_type': 'authorization_code', 'code': code, 'client_id': CLIENT_ID,
            'redirect_uri': [REDIRECT, 'https://evil.example.net/callback'], 'code_verifier': VERIFIER})
        assert response.status_code == 400 and response.get_json()['error'] == 'invalid_request'

    def test_client_authentication_is_refused_not_ignored(self, on):
        code = on.code()
        for header in ('Basic Y2xpZW50OnNlY3JldA==', 'Bearer dro_at_something'):
            response = on.anonymous().post('/oauth/token', headers={'Authorization': header}, data={
                'grant_type': 'authorization_code', 'code': code, 'client_id': CLIENT_ID,
                'redirect_uri': REDIRECT, 'code_verifier': VERIFIER})
            assert response.status_code == 401 and response.get_json()['error'] == 'invalid_client'

    def test_an_api_key_is_worth_nothing_here(self, on):
        key = on.api_key(scopes=('read', 'search', 'write'))
        assert on.exchange(key).get_json()['error'] == 'invalid_grant'
        assert on.refresh(key).get_json()['error'] == 'invalid_grant'
        response = on.anonymous().post('/oauth/token', headers={'Authorization': f'Bearer {key}'},
                                       data={'grant_type': 'refresh_token', 'client_id': CLIENT_ID})
        assert response.status_code == 401
        assert OAuthGrant.query.count() == 0

    def test_tokens_are_not_codes_and_codes_are_not_tokens(self, on):
        tokens = on.tokens()
        assert on.exchange(tokens['access_token']).status_code == 400
        assert on.exchange(tokens['refresh_token']).status_code == 400
        assert on.refresh(tokens['access_token']).status_code == 400
        assert on.mcp(tokens['refresh_token']).status_code == 401
        code = on.code()
        assert on.mcp(code).status_code == 401
        assert on.refresh(code).status_code == 400

    def test_the_session_plays_no_part(self, on):
        """Called from a browser that is signed in, without a CSRF token: accepted on the body alone."""
        code = on.code()
        browser = on.signed_in(on.colleague, csrf=False)
        response = on.exchange(code, client=browser)
        assert response.status_code == 200
        # ... and the tokens are the consenting user's, not the browser's
        assert OAuthGrant.query.one().user_id == on.user.id

    def test_get_is_not_accepted_and_preflight_is_answered(self, on):
        assert on.anonymous().get('/oauth/token').status_code == 405
        response = on.anonymous().options('/oauth/token', headers={
            'Origin': 'http://127.0.0.1:6274', 'Access-Control-Request-Method': 'POST'})
        assert response.status_code == 204
        assert response.headers['Access-Control-Allow-Origin'] == '*'
        assert 'Access-Control-Allow-Credentials' not in response.headers

    def test_nothing_secret_is_logged(self, on, caplog):
        """The whole flow, with every log line captured: no code, token or verifier appears in any of them."""
        import logging
        caplog.set_level(logging.DEBUG)
        code = on.code()
        on.exchange(code, code_verifier='w' * 64)                 # a refused attempt is logged too
        tokens = on.exchange(code).get_json()
        refreshed = on.refresh(tokens['refresh_token']).get_json()
        on.refresh(tokens['refresh_token'])                       # reuse: refused, grant ended, logged
        on.mcp(refreshed['access_token'])
        on.anonymous().post('/oauth/revoke', data={'token': refreshed['access_token'], 'client_id': CLIENT_ID})

        logged = '\n'.join(record.getMessage() for record in caplog.records)
        assert 'Token request refused' in logged                  # the capture works
        for secret in (code, VERIFIER, tokens['access_token'], tokens['refresh_token'],
                       refreshed['access_token'], refreshed['refresh_token']):
            assert secret not in logged
            assert secret[len('dro_xx_'):] not in logged

    def test_no_tokens_when_the_user_left_after_consenting(self, on):
        code = on.code()
        db.session.delete(on.membership(on.user))
        db.session.commit()
        assert on.exchange(code).get_json()['error'] == 'invalid_grant'
        assert OAuthGrant.query.count() == 0


class TestRefreshOverHttp:

    def test_refresh_replaces_both_tokens(self, on):
        first = on.tokens()

        response = on.refresh(first['refresh_token'], resource=RESOURCE)

        assert response.status_code == 200
        second = response.get_json()
        assert second['access_token'] != first['access_token']
        assert second['refresh_token'] != first['refresh_token']
        assert response.headers['Cache-Control'] == 'no-store'
        assert on.mcp(second['access_token']).status_code == 200

    def test_a_used_refresh_token_ends_the_connection(self, on):
        first = on.tokens()
        second = on.refresh(first['refresh_token']).get_json()
        assert on.mcp(second['access_token']).status_code == 200     # the real application carries on

        response = on.refresh(first['refresh_token'])

        assert response.status_code == 400 and response.get_json()['error'] == 'invalid_grant'
        assert on.mcp(second['access_token']).status_code == 401
        assert on.refresh(second['refresh_token']).status_code == 400
        assert OAuthGrant.query.one().revoke_reason == 'refresh_reuse'
        assert AuditLog.query.filter_by(action_type=service.AUDIT_REFRESH_REUSE).count() == 1

    def test_a_removed_member_cannot_refresh(self, on):
        tokens = on.tokens()
        db.session.delete(on.membership(on.user))
        db.session.commit()
        response = on.refresh(tokens['refresh_token'])
        assert response.status_code == 400 and response.get_json()['error'] == 'invalid_grant'
        assert OAuthGrant.query.one().revoke_reason == 'owner_gone'

    def test_scope_can_be_repeated_or_narrowed_but_not_widened(self, on):
        tokens = on.tokens(scopes=['decisions:read'])

        widened = on.refresh(tokens['refresh_token'], scope='decisions:read decisions:write')
        assert widened.status_code == 400 and widened.get_json()['error'] == 'invalid_scope'

        same = on.refresh(tokens['refresh_token'], scope='decisions:read offline_access')
        assert same.status_code == 200 and same.get_json()['scope'] == 'decisions:read'
        # Still read only after the refresh
        response = on.call(same.get_json()['access_token'], 'create_decision', {
            'title': 'T', 'context': 'c', 'decision': 'd', 'consequences': 'q'})
        assert response.status_code == 403

    def test_asking_for_less_on_refresh_does_not_add_anything(self, on):
        tokens = on.tokens()
        narrowed = on.refresh(tokens['refresh_token'], scope='decisions:read')
        assert narrowed.status_code == 200
        # The answer states what the token really carries
        assert narrowed.get_json()['scope'] == 'decisions:read decisions:write'

    def test_another_client_or_resource(self, on):
        tokens = on.tokens()
        other = on.refresh(tokens['refresh_token'], client_id='https://other.example.org/client.json')
        assert other.get_json()['error'] == 'invalid_grant'
        elsewhere = on.refresh(tokens['refresh_token'], resource='https://evil.example.net/api/mcp')
        assert elsewhere.get_json()['error'] == 'invalid_target'
        # Neither attempt used the token up or ended the connection
        assert on.refresh(tokens['refresh_token']).status_code == 200

    def test_no_refresh_while_the_switch_is_off(self, on):
        tokens = on.tokens()
        oauth_config.set_enabled(False)
        assert on.refresh(tokens['refresh_token']).status_code == 404
        oauth_config.set_enabled(True)
        assert on.refresh(tokens['refresh_token']).status_code == 200


class TestRevokeEndpoint:

    @pytest.mark.parametrize('which', ['access_token', 'refresh_token'])
    def test_an_application_gives_up_a_token(self, on, which):
        tokens = on.tokens()

        response = on.anonymous().post('/oauth/revoke', data={'token': tokens[which], 'client_id': CLIENT_ID})

        assert response.status_code == 200 and response.get_data() == b''
        assert response.headers['Access-Control-Allow-Origin'] == '*'
        assert on.mcp(tokens['access_token']).status_code == 401
        assert on.refresh(tokens['refresh_token']).status_code == 400
        assert OAuthGrant.query.one().revoke_reason == 'client'

    def test_the_answer_does_not_say_whether_the_token_existed(self, on):
        tokens = on.tokens()
        for form in (
            {'token': 'dro_at_unknown', 'client_id': CLIENT_ID},
            {'token': tokens['access_token'], 'client_id': 'https://other.example.org/client.json'},
            {'token': on.api_key(), 'client_id': CLIENT_ID},
        ):
            response = on.anonymous().post('/oauth/revoke', data=form)
            assert response.status_code == 200 and response.get_data() == b''
        # Nothing was ended, and the API key still works
        assert on.mcp(tokens['access_token']).status_code == 200

    @pytest.mark.parametrize('form,status', [
        ({'client_id': CLIENT_ID}, 400),
        ({'token': 'dro_at_x'}, 400),
        ({'token': 'dro_at_x', 'client_id': CLIENT_ID, 'client_secret': 's'}, 401),
    ])
    def test_malformed_requests(self, on, form, status):
        assert on.anonymous().post('/oauth/revoke', data=form).status_code == status

    def test_json_bodies_and_get_are_refused(self, on):
        tokens = on.tokens()
        response = on.anonymous().post('/oauth/revoke', json={'token': tokens['access_token'], 'client_id': CLIENT_ID})
        assert response.status_code == 400
        assert on.anonymous().get('/oauth/revoke').status_code == 405
        assert on.mcp(tokens['access_token']).status_code == 200


# ============================================================================
# 6. /api/mcp WITH AN OAUTH TOKEN
# ============================================================================

class TestMcpChallenges:

    def test_no_credential(self, on):
        response = on.mcp()
        assert response.status_code == 401
        assert response.headers['WWW-Authenticate'] == FULL_CHALLENGE

    @pytest.mark.parametrize('bearer', ['dro_at_unknown', 'adr_not-a-real-key', 'anything'])
    def test_an_unknown_credential(self, on, bearer):
        response = on.mcp(bearer)
        assert response.status_code == 401
        assert response.headers['WWW-Authenticate'] == INVALID_TOKEN_CHALLENGE
        assert response.get_json()['error']['code'] == 401

    def test_the_challenge_leads_to_metadata_that_exists(self, on):
        challenge = on.mcp().headers['WWW-Authenticate']
        url = challenge.split('resource_metadata="')[1].split('"')[0]
        document = on.anonymous().get(urlsplit(url).path).get_json()
        assert document['resource'] == RESOURCE and document['authorization_servers'] == [ISSUER]


class TestMcpWithOAuthToken:

    def test_reading(self, on):
        access = on.tokens(scopes=['decisions:read'])['access_token']

        response = on.mcp(access)
        assert response.status_code == 200
        assert 'WWW-Authenticate' not in response.headers
        assert len(response.get_json()['result']['tools']) > 5

        data = _structured(on.call(access, 'get_decision', {'id': str(on.decision.id)}))
        assert data['title'] == 'Use PostgreSQL'

    def test_writing_with_the_write_scope(self, on):
        access = on.tokens()['access_token']
        response = on.call(access, 'create_decision', {
            'title': 'Adopt OAuth', 'context': 'c', 'decision': 'd', 'consequences': 'q'})
        assert response.status_code == 200
        created = ArchitectureDecision.query.filter_by(title='Adopt OAuth').one()
        assert created.tenant_id == on.tenant.id and created.created_by_id == on.user.id

    @pytest.mark.parametrize('tool,arguments', [
        ('create_decision', {'title': 'T', 'context': 'c', 'decision': 'd', 'consequences': 'q'}),
        ('add_decision_comment', {'id': '1', 'body': 'text'}),
        ('update_decision_status', {'id': '1', 'status': 'archived'}),
        ('link_decisions', {'source_decision_id': '1', 'target_decision_id': '1', 'relationship_type': 'relates_to'}),
        ('supersede_decision', {'source_decision_id': '1', 'target_decision_id': '1'}),
    ])
    def test_a_read_only_connection_is_asked_to_step_up_and_nothing_is_written(self, on, tool, arguments):
        access = on.tokens(scopes=['decisions:read'])['access_token']
        before = (ArchitectureDecision.query.count(), on.decision.status, on.decision.comment_count)

        response = on.call(access, tool, arguments)

        assert response.status_code == 403
        assert response.headers['WWW-Authenticate'] == INSUFFICIENT_SCOPE_CHALLENGE
        assert response.get_json()['error']['code'] == 403
        db.session.expire_all()
        assert (ArchitectureDecision.query.count(), on.decision.status, on.decision.comment_count) == before

    def test_every_write_tool_is_covered_by_the_step_up(self, on):
        """A tool added to the server's write list is refused for a read-only connection without a test of its own."""
        access = on.tokens(scopes=['decisions:read'])['access_token']
        for tool in sorted(mcp_server.WRITE_TOOLS):
            response = on.call(access, tool, {})
            assert response.status_code == 403, tool
            assert 'insufficient_scope' in response.headers['WWW-Authenticate']

    def test_an_api_key_without_write_is_answered_as_before_even_with_oauth_on(self, on):
        response = on.call(on.api_key(), 'create_decision', {
            'title': 'T', 'context': 'c', 'decision': 'd', 'consequences': 'q'})
        assert response.status_code == 200
        assert 'WWW-Authenticate' not in response.headers
        assert response.get_json()['result']['isError'] is True

    def test_api_keys_keep_working_next_to_oauth(self, on):
        key = on.api_key(scopes=('read', 'search', 'write'))
        assert on.mcp(key).status_code == 200
        response = on.call(key, 'create_decision', {
            'title': 'By key', 'context': 'c', 'decision': 'd', 'consequences': 'q'})
        assert response.status_code == 200 and response.get_json()['result'].get('isError') is not True

    def test_only_the_chosen_organisation_is_visible(self, on):
        access = on.tokens()['access_token']

        listed = _structured(on.call(access, 'list_decisions'))['decisions']
        assert [d['title'] for d in listed] == ['Use PostgreSQL']
        found = _structured(on.call(access, 'search_decisions', {'query': 'secret'}))['decisions']
        assert found == []
        response = on.call(access, 'get_decision', {'id': str(on.other_decision.id)})
        assert response.get_json()['result']['isError'] is True
        assert 'Other organisation secret' not in response.get_data(as_text=True)
        # ... and nothing can be written to the other organisation's record
        response = on.call(access, 'add_decision_comment', {'id': str(on.other_decision.id), 'body': 'hello'})
        assert response.get_json()['result']['isError'] is True
        assert on.other_decision.comment_count == 0

    def test_two_users_tokens_stay_apart(self, on):
        mine = on.tokens()['access_token']
        theirs = on.tokens(user=on.outsider, tenant=on.other_tenant)['access_token']
        assert [d['title'] for d in _structured(on.call(mine, 'list_decisions'))['decisions']] == ['Use PostgreSQL']
        assert [d['title'] for d in _structured(on.call(theirs, 'list_decisions'))['decisions']] == [
            'Other organisation secret']

    # --- every gate an API key passes ------------------------------------------

    def test_gate_system_ai_switch(self, on):
        access = on.tokens()['access_token']
        SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'false')
        response = on.mcp(access)
        assert response.status_code == 403
        assert 'AI features are not enabled on this Decision Records installation' in response.get_json()['error']['message']
        assert 'WWW-Authenticate' not in response.headers

    def test_gate_system_mcp_switch(self, on):
        access = on.tokens()['access_token']
        SystemConfig.set(SystemConfig.KEY_AI_MCP_SERVER_ENABLED, 'false')
        response = on.mcp(access)
        assert response.status_code == 403
        assert 'MCP server is not enabled' in response.get_json()['error']['message']

    def test_gate_organisation_ai_switch(self, on):
        access = on.tokens()['access_token']
        on.tenant.ai_features_enabled = False
        db.session.commit()

        response = on.mcp(access)

        assert response.status_code == 403
        assert response.get_json()['error']['message'] == mcp_server.TENANT_AI_DISABLED_ERROR
        # Not a scope problem: the client must not ask the user to consent again
        assert 'WWW-Authenticate' not in response.headers
        assert on.call(access, 'list_decisions').status_code == 403

        # Switched back on, the same connection works again without reconnecting
        on.tenant.ai_features_enabled = True
        db.session.commit()
        assert on.mcp(access).status_code == 200

    def test_gate_user_opt_out(self, on):
        access = on.tokens()['access_token']
        on.membership(on.user).ai_opt_out = True
        db.session.commit()
        response = on.mcp(access)
        assert response.status_code == 403
        assert response.get_json()['error']['message'] == mcp_server.USER_OPT_OUT_ERROR

    def test_the_gates_answer_an_oauth_token_and_an_api_key_alike(self, on):
        access = on.tokens()['access_token']
        key = on.api_key()
        states = []

        def tenant_ai_off():
            on.tenant.ai_features_enabled = False
        def tenant_ai_on():
            on.tenant.ai_features_enabled = True
        def opt_out():
            on.membership(on.user).ai_opt_out = True
        def opt_in():
            on.membership(on.user).ai_opt_out = False
        def external_off():
            on.tenant.ai_external_access_enabled = False
        def external_on():
            on.tenant.ai_external_access_enabled = True

        for change, undo in ((tenant_ai_off, tenant_ai_on), (external_off, external_on), (opt_out, opt_in)):
            change()
            db.session.commit()
            by_token, by_key = on.mcp(access), on.mcp(key)
            states.append((by_token.status_code, by_key.status_code))
            assert by_token.get_json() == by_key.get_json()
            undo()
            db.session.commit()
        assert states == [(403, 403), (403, 403), (403, 403)]

    def test_gate_membership(self, on):
        access = on.tokens()['access_token']
        db.session.delete(on.membership(on.user))
        db.session.commit()
        response = on.mcp(access)
        assert response.status_code == 401
        assert response.headers['WWW-Authenticate'] == INVALID_TOKEN_CHALLENGE

    def test_gate_anonymised_and_deleted_accounts(self, on):
        access = on.tokens()['access_token']
        on.user.is_anonymized = True
        db.session.commit()
        assert on.mcp(access).status_code == 401
        on.user.is_anonymized = False
        on.user.deleted_at = datetime.now(timezone.utc)
        db.session.commit()
        assert on.mcp(access).status_code == 401

    def test_gate_deleted_organisation(self, on):
        access = on.tokens()['access_token']
        on.tenant.deleted_at = datetime.now(timezone.utc)
        db.session.commit()
        assert on.mcp(access).status_code == 401
        response = on.call(access, 'create_decision', {
            'title': 'Should not exist', 'context': 'c', 'decision': 'd', 'consequences': 'q'})
        assert response.status_code == 401
        assert ArchitectureDecision.query.filter_by(title='Should not exist').count() == 0

    def test_an_expired_access_token(self, on):
        access = on.tokens()['access_token']
        for token in OAuthToken.query.filter_by(kind=OAuthToken.KIND_ACCESS).all():
            token.expires_at = datetime(2020, 1, 1)
        db.session.commit()
        response = on.mcp(access)
        assert response.status_code == 401
        assert response.headers['WWW-Authenticate'] == INVALID_TOKEN_CHALLENGE

    def test_a_token_issued_for_another_resource_is_refused(self, on):
        """Audience: the same token, presented to a server that is a different resource."""
        access = on.tokens()['access_token']
        assert on.mcp(access).status_code == 200

        on.monkeypatch.setenv('MCP_RESOURCE_URL', 'https://another.example.org/api/mcp')
        assert on.mcp(access).status_code == 401

        grant = OAuthGrant.query.one()
        on.monkeypatch.setenv('MCP_RESOURCE_URL', RESOURCE)
        grant.resource = 'https://decisions.example.org/api/ai'
        db.session.commit()
        assert on.mcp(access).status_code == 401

    def test_a_disconnected_application(self, on):
        access = on.tokens()['access_token']
        service.revoke_grant(OAuthGrant.query.one(), 'user', by_user=on.user)
        assert on.mcp(access).status_code == 401

    def test_a_blocked_application(self, on):
        access = on.tokens()['access_token']
        OAuthClient.query.one().disabled_at = datetime.now(timezone.utc)
        db.session.commit()
        assert on.mcp(access).status_code == 401

    def test_the_token_must_be_in_the_header(self, on):
        access = on.tokens()['access_token']
        response = on.anonymous().post(f'/api/mcp?access_token={access}',
                                       json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'})
        assert response.status_code == 401
        response = on.anonymous().post('/api/mcp', json={
            'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list', 'access_token': access})
        assert response.status_code == 401

    def test_the_current_protocol_revision_works_with_a_token(self, on):
        access = on.tokens()['access_token']
        response = on.mcp(access, body={
            'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list',
            'params': {'_meta': {
                'io.modelcontextprotocol/protocolVersion': '2026-07-28',
                'io.modelcontextprotocol/clientCapabilities': {},
            }},
        }, headers={'MCP-Protocol-Version': '2026-07-28', 'Mcp-Method': 'tools/list'})
        assert response.status_code == 200, response.get_data(as_text=True)

    def test_a_batch_with_a_bad_token_is_refused_as_a_whole(self, on):
        response = on.mcp('dro_at_unknown', body=[
            {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'},
            {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
        ], headers={'MCP-Protocol-Version': '2025-03-26'})
        assert response.status_code == 401
        assert response.headers['WWW-Authenticate'] == INVALID_TOKEN_CHALLENGE

    def test_a_batch_that_needs_more_scope_is_refused_as_a_whole(self, on):
        access = on.tokens(scopes=['decisions:read'])['access_token']
        response = on.mcp(access, body=[
            {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'},
            {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'create_decision', 'arguments': {
                'title': 'T', 'context': 'c', 'decision': 'd', 'consequences': 'q'}}},
        ], headers={'MCP-Protocol-Version': '2025-03-26'})
        assert response.status_code == 403
        assert response.headers['WWW-Authenticate'] == INSUFFICIENT_SCOPE_CHALLENGE
        assert ArchitectureDecision.query.filter_by(title='T').count() == 0


class TestOAuthTokensAreForMcpOnly:

    def test_the_external_ai_api_refuses_them(self, on):
        access = on.tokens()['access_token']
        for path in ('/api/ai/decisions', f'/api/ai/decisions/{on.decision.id}'):
            response = on.anonymous().get(path, headers={'Authorization': f'Bearer {access}'})
            assert response.status_code == 401
            assert response.get_json() == {'error': 'Invalid or expired API key'}
        response = on.anonymous().post('/api/ai/decisions', headers={'Authorization': f'Bearer {access}'}, json={
            'title': 'Should not exist', 'context': 'c', 'decision': 'd', 'consequences': 'q'})
        assert response.status_code == 401
        # The same user's API key is accepted there, so the refusal is about the kind of credential
        key = on.api_key()
        assert on.anonymous().get('/api/ai/decisions', headers={'Authorization': f'Bearer {key}'}).status_code == 200

    @pytest.mark.parametrize('path', [
        '/api/decisions', '/api/user/me', '/api/user/ai/keys', '/api/user/oauth/grants',
        '/api/tenant/oauth/grants', '/api/oauth/pending',
    ])
    def test_the_web_apps_own_api_does_not_take_them(self, on, path):
        access = on.tokens()['access_token']
        response = on.anonymous().get(path, headers={'Authorization': f'Bearer {access}'})
        assert response.status_code == 401, path

    def test_a_token_cannot_approve_a_consent_request(self, on):
        access = on.tokens()['access_token']
        public_id = on.start()
        response = on.anonymous().post(f'/api/oauth/requests/{public_id}/decision',
                                       headers={'Authorization': f'Bearer {access}'},
                                       json={'decision': 'approve', 'tenant_id': on.tenant.id})
        assert response.status_code == 401


# ============================================================================
# 7. CONNECTED APPLICATIONS
# ============================================================================

class TestOwnConnectedApps:

    def test_a_user_sees_their_own_connections_in_every_organisation(self, on):
        on.join(on.user, on.other_tenant)
        on.tokens(scopes=['decisions:read'])
        on.tokens(tenant=on.other_tenant)
        on.tokens(user=on.colleague)

        response = on.signed_in(on.user).get('/api/user/oauth/grants')

        assert response.status_code == 200
        grants = response.get_json()
        assert len(grants) == 2
        assert {grant['organisation']['domain'] for grant in grants} == {'example.com', 'other.org'}
        first = [grant for grant in grants if grant['organisation']['domain'] == 'example.com'][0]
        assert first['application'] == {'host': 'client.example.org', 'claimed_name': 'Example Client'}
        assert first['scopes'] == ['decisions:read'] and first['can_write'] is False
        assert set(first) == {'id', 'application', 'organisation', 'scopes', 'can_write', 'connected_at',
                              'last_used_at', 'expires_at'}
        text = response.get_data(as_text=True)
        assert 'dro_' not in text and 'token' not in text

    def test_disconnecting_ends_the_tokens_at_once(self, on):
        tokens = on.tokens()
        client = on.signed_in(on.user)
        grant_id = client.get('/api/user/oauth/grants').get_json()[0]['id']

        response = client.delete(f'/api/user/oauth/grants/{grant_id}')

        assert response.status_code == 200
        assert on.mcp(tokens['access_token']).status_code == 401
        assert on.refresh(tokens['refresh_token']).status_code == 400
        assert client.get('/api/user/oauth/grants').get_json() == []
        entry = AuditLog.query.filter_by(action_type=service.AUDIT_GRANT_REVOKED).one()
        assert entry.actor_user_id == on.user.id and entry.details['reason'] == 'user'
        assert client.delete(f'/api/user/oauth/grants/{grant_id}').status_code == 404

    def test_someone_elses_connection_cannot_be_ended_or_seen(self, on):
        tokens = on.tokens()
        grant_id = OAuthGrant.query.one().public_id

        colleague = on.signed_in(on.colleague)
        assert colleague.get('/api/user/oauth/grants').get_json() == []
        assert colleague.delete(f'/api/user/oauth/grants/{grant_id}').status_code == 404
        assert on.mcp(tokens['access_token']).status_code == 200

    def test_disconnecting_needs_the_csrf_token(self, on):
        tokens = on.tokens()
        grant_id = OAuthGrant.query.one().public_id
        response = on.signed_in(on.user, csrf=False).delete(f'/api/user/oauth/grants/{grant_id}')
        assert response.status_code == 403
        assert on.mcp(tokens['access_token']).status_code == 200

    def test_it_needs_a_signed_in_organisation_account(self, on):
        assert on.anonymous().get('/api/user/oauth/grants').status_code == 401
        assert on.master().get('/api/user/oauth/grants').status_code == 403


class TestTenantConnectedApps:

    def test_an_administrator_sees_every_members_connection_in_their_organisation(self, on):
        on.tokens()
        on.tokens(user=on.colleague, scopes=['decisions:read'])
        on.tokens(user=on.outsider, tenant=on.other_tenant)

        response = on.signed_in(on.admin).get('/api/tenant/oauth/grants')

        assert response.status_code == 200
        grants = response.get_json()
        assert sorted(grant['user']['name'] for grant in grants) == ['Col League', 'Pat Person']
        assert all(set(grant['user']) == {'id', 'name'} for grant in grants)
        assert 'person@example.com' not in response.get_data(as_text=True)
        assert {grant['organisation']['domain'] for grant in grants} == {'example.com'}

    def test_an_administrator_disconnects_a_member(self, on):
        tokens = on.tokens()
        grant_id = OAuthGrant.query.one().public_id

        response = on.signed_in(on.admin).delete(f'/api/tenant/oauth/grants/{grant_id}')

        assert response.status_code == 200
        assert on.mcp(tokens['access_token']).status_code == 401
        grant = OAuthGrant.query.one()
        assert grant.revoke_reason == 'admin' and grant.revoked_by_user_id == on.admin.id
        entry = AuditLog.query.filter_by(action_type=service.AUDIT_GRANT_REVOKED).one()
        assert entry.actor_user_id == on.admin.id and entry.details['grant_user_id'] == on.user.id

    def test_members_are_not_administrators(self, on):
        on.tokens()
        grant_id = OAuthGrant.query.one().public_id
        member = on.signed_in(on.colleague)
        assert member.get('/api/tenant/oauth/grants').status_code == 403
        assert member.delete(f'/api/tenant/oauth/grants/{grant_id}').status_code == 403
        assert OAuthGrant.query.one().revoked_at is None

    def test_another_organisations_administrator_cannot_see_or_end_it(self, on):
        tokens = on.tokens()
        grant_id = OAuthGrant.query.one().public_id
        outsider = on.signed_in(on.outsider)

        assert outsider.get('/api/tenant/oauth/grants').get_json() == []
        assert outsider.delete(f'/api/tenant/oauth/grants/{grant_id}').status_code == 404
        assert on.mcp(tokens['access_token']).status_code == 200

    def test_an_administrator_only_reaches_their_own_organisation_even_as_a_member_elsewhere(self, on):
        """A connection the admin's colleague made into another organisation is that organisation's business."""
        on.join(on.colleague, on.other_tenant)
        on.tokens(user=on.colleague, tenant=on.other_tenant)
        grant_id = OAuthGrant.query.one().public_id
        admin = on.signed_in(on.admin)
        assert admin.get('/api/tenant/oauth/grants').get_json() == []
        assert admin.delete(f'/api/tenant/oauth/grants/{grant_id}').status_code == 404

    def test_disconnecting_needs_the_csrf_token_and_a_session(self, on):
        on.tokens()
        grant_id = OAuthGrant.query.one().public_id
        assert on.signed_in(on.admin, csrf=False).delete(f'/api/tenant/oauth/grants/{grant_id}').status_code == 403
        assert on.anonymous().delete(f'/api/tenant/oauth/grants/{grant_id}').status_code == 401
        assert on.master().get('/api/tenant/oauth/grants').status_code == 403
        assert OAuthGrant.query.one().revoked_at is None


# ============================================================================
# 8. FRAMING, CSRF, CORS
# ============================================================================

class TestFramingAndCors:

    def _no_framing(self, response):
        policy = response.headers['Content-Security-Policy']
        assert "frame-ancestors 'none'" in policy
        assert policy.count('frame-ancestors') == 1
        assert TEAMS_ANCESTOR not in policy
        assert response.headers['X-Frame-Options'] == 'DENY'

    def test_oauth_pages_and_consent_answers_cannot_be_framed(self, on):
        self._no_framing(on.authorize())                               # the redirect
        self._no_framing(on.authorize(client_id='nonsense'))           # the error page
        client = on.signed_in(on.user)
        public_id = on.start()
        self._no_framing(on.view(client, public_id))
        self._no_framing(on.decide(client, public_id, decision='deny'))
        self._no_framing(client.get('/api/oauth/pending'))
        self._no_framing(on.anonymous().get('/oauth/consent?request=abc'))   # the page slice 5 will serve

    def test_the_rule_holds_while_the_switch_is_off(self, world):
        self._no_framing(world.anonymous().get('/oauth/authorize'))
        self._no_framing(world.anonymous().get('/oauth/consent'))

    def test_the_rest_of_the_app_keeps_its_policy(self, on):
        for response in (on.mcp(), on.anonymous().get('/api/version'), on.anonymous().get('/oauthx/authorize')):
            policy = response.headers['Content-Security-Policy']
            assert TEAMS_ANCESTOR in policy and "'none'" not in policy.split('frame-ancestors')[1].split(';')[0]
            assert response.headers['X-Frame-Options'] == 'SAMEORIGIN'

    def test_the_rest_of_the_policy_is_kept_on_oauth_paths(self, on):
        policy = on.authorize(client_id='nonsense').headers['Content-Security-Policy']
        for directive in ("default-src 'self'", "form-action 'self'", "object-src 'none'", "base-uri 'self'"):
            assert directive in policy

    def test_cors_is_only_on_the_endpoints_applications_call(self, on):
        tokens = on.tokens()
        open_to_any_origin = [
            on.anonymous().get('/.well-known/oauth-protected-resource'),
            on.anonymous().get('/.well-known/oauth-authorization-server'),
            on.refresh(tokens['refresh_token']),
            on.token_request(grant_type='nonsense', client_id=CLIENT_ID),
            on.anonymous().post('/oauth/revoke', data={'token': 'x', 'client_id': CLIENT_ID}),
        ]
        for response in open_to_any_origin:
            assert response.headers['Access-Control-Allow-Origin'] == '*'
            assert 'Access-Control-Allow-Credentials' not in response.headers

        client = on.signed_in(on.user)
        public_id = on.start()
        with_a_session = [
            on.authorize(), on.view(client, public_id), client.get('/api/oauth/pending'),
            client.get('/api/user/oauth/grants'), on.signed_in(on.admin).get('/api/tenant/oauth/grants'),
            on.decide(client, public_id, decision='deny'),
        ]
        for response in with_a_session:
            assert 'Access-Control-Allow-Origin' not in response.headers


# ============================================================================
# 9. RATE LIMITS
# ============================================================================

class TestRateLimits:

    def test_each_credential_has_its_own_mcp_limit(self, on):
        on.monkeypatch.setitem(rate_limits.LIMITS, 'mcp_credential', '3 per minute')
        access = on.tokens()['access_token']
        key = on.api_key()

        assert [on.mcp(access).status_code for _ in range(3)] == [200, 200, 200]
        limited = on.mcp(access)
        assert limited.status_code == 429
        assert int(limited.headers['Retry-After']) >= 1
        assert limited.get_json()['error']['code'] == 429
        # Another credential is not affected, and neither is a request without one
        assert on.mcp(key).status_code == 200
        assert on.mcp().status_code == 401

    def test_unknown_credentials_are_limited_one_by_one_too(self, on):
        on.monkeypatch.setitem(rate_limits.LIMITS, 'mcp_credential', '2 per minute')
        assert [on.mcp('dro_at_guess').status_code for _ in range(3)] == [401, 401, 429]
        assert on.mcp('dro_at_another-guess').status_code == 401

    def test_the_default_mcp_limit_is_above_the_app_wide_default(self, on):
        """So that adding it changes nothing for an API key that worked before."""
        assert rate_limits.LIMITS['mcp_credential'] == '300 per minute'

    def test_the_credential_is_not_the_storage_key(self, on):
        assert 'dro_at_secret' not in rate_limits.credential_key('dro_at_secret')
        assert rate_limits.credential_key('a') != rate_limits.credential_key('b')

    def test_authorize_is_limited_per_network(self, on):
        on.monkeypatch.setitem(rate_limits.LIMITS, 'authorize_prefix', '2 per 10 minutes')
        client = on.anonymous()
        url = '/oauth/authorize?' + urlencode(on.authorize_params())

        def start(address):
            return client.get(url, headers={'CF-Connecting-IP': address}).status_code

        # One IPv4 /24 shares an allowance; the next /24 has its own
        assert [start('198.51.100.7'), start('198.51.100.200'), start('198.51.100.9')] == [302, 302, 429]
        assert start('198.51.101.7') == 302
        # One IPv6 /64 shares an allowance however many addresses in it are used
        assert [start('2001:db8:1:2::1'), start('2001:db8:1:2:ffff::9'), start('2001:db8:1:2::3')] == [302, 302, 429]
        assert start('2001:db8:1:3::1') == 302
        assert OAuthAuthorizationRequest.query.count() == 6

    @pytest.mark.parametrize('address,prefix', [
        ('198.51.100.7', '198.51.100.0/24'),
        ('2001:db8:1:2:3:4:5:6', '2001:db8:1:2::/64'),
        ('::ffff:198.51.100.7', '198.51.100.0/24'),
        ('not-an-address', 'not-an-address'),
    ])
    def test_address_prefix(self, on, address, prefix):
        with on.app.test_request_context('/', headers={'CF-Connecting-IP': address}):
            assert rate_limits.address_prefix() == prefix

    def test_fetching_application_documents_is_limited_per_user(self, on):
        on.monkeypatch.setitem(rate_limits.LIMITS, 'client_metadata_fetch', '2 per minute')
        on.fetch_error = FetchError('The server answered 404')
        client = on.signed_in(on.user)

        statuses = [on.view(client, on.start()).status_code for _ in range(3)]

        assert statuses == [400, 400, 429]
        assert len(on.fetches) == 2
        # Another user has their own allowance
        assert on.view(on.signed_in(on.colleague), on.start()).status_code == 400

    def test_decisions_are_limited_per_user(self, on):
        on.monkeypatch.setitem(rate_limits.LIMITS, 'consent_decision', '1 per minute')
        client = on.signed_in(on.user)
        first, second = on.start(), on.start()
        on.view(client, first)
        on.view(client, second)
        assert on.decide(client, first, decision='deny').status_code == 200
        assert on.decide(client, second, decision='deny').status_code == 429
        assert OAuthAuthorizationRequest.query.filter_by(public_id=second).one().decision is None

    def test_naming_a_client_does_not_use_up_its_allowance(self, on):
        """Anyone can send a client_id. Requests without a real code or token of that client count against the
        caller's address only, so they cannot lock the client out for its users."""
        on.monkeypatch.setitem(rate_limits.LIMITS, 'token', '3 per minute')
        code = on.code()
        attacker = on.anonymous()
        junk = [
            {'client_id': CLIENT_ID, 'grant_type': 'x'},
            {'client_id': CLIENT_ID, 'grant_type': 'refresh_token', 'refresh_token': 'dro_rt_guess'},
            {'client_id': CLIENT_ID, 'grant_type': 'authorization_code', 'code': 'dro_ac_guess',
             'redirect_uri': REDIRECT, 'code_verifier': VERIFIER},
        ]
        for _ in range(10):
            for form in junk:
                assert attacker.post('/oauth/token', data=form, headers={'CF-Connecting-IP': '203.0.113.9'}
                                     ).status_code == 400

        real = on.exchange(code)
        assert real.status_code == 200, real.get_json()

    def test_another_clients_name_on_a_real_credential_does_not_count_against_that_client(self, on):
        on.monkeypatch.setitem(rate_limits.LIMITS, 'token', '1 per minute')
        on.monkeypatch.setitem(rate_limits.LIMITS, 'token_connection', '100 per minute')
        first = on.tokens()                       # counts once against the real client
        other = 'https://other.example.org/client.json'
        for _ in range(5):
            assert on.refresh(first['refresh_token'], client_id=other).status_code == 400
        # The other client's allowance is untouched by requests that carried our client's token
        assert rate_limits.hit('token', other) is None

    def test_requests_with_a_real_credential_count_against_the_client(self, on):
        on.monkeypatch.setitem(rate_limits.LIMITS, 'token', '2 per minute')
        first = on.tokens()                                       # 1
        second = on.refresh(first['refresh_token'])               # 2
        assert second.status_code == 200
        third = on.refresh(second.get_json()['refresh_token'])    # over
        assert third.status_code == 429
        assert third.get_json()['error'] == 'slow_down' and int(third.headers['Retry-After']) >= 1
        # Refused before it was looked at: the token is still good afterwards
        rate_limits.reset()
        assert on.refresh(second.get_json()['refresh_token']).status_code == 200

    def test_one_connection_cannot_use_up_the_clients_allowance(self, on):
        on.monkeypatch.setitem(rate_limits.LIMITS, 'token_connection', '2 per minute')
        mine = on.tokens()
        theirs = on.tokens(user=on.colleague)
        mine = on.refresh(mine['refresh_token']).get_json()
        mine = on.refresh(mine['refresh_token']).get_json()
        assert on.refresh(mine['refresh_token']).status_code == 429
        # The colleague's connection, same client, is not held back
        assert on.refresh(theirs['refresh_token']).status_code == 200

    def test_the_token_and_revoke_endpoints_are_limited_per_address(self, on):
        on.monkeypatch.setitem(rate_limits.LIMITS, 'token_address', '2 per minute')
        on.monkeypatch.setitem(rate_limits.LIMITS, 'revoke_address', '2 per minute')
        here = {'CF-Connecting-IP': '203.0.113.9'}
        there = {'CF-Connecting-IP': '203.0.113.10'}
        client = on.anonymous()
        form = {'grant_type': 'refresh_token', 'refresh_token': 'dro_rt_x', 'client_id': CLIENT_ID}
        assert [client.post('/oauth/token', data=form, headers=here).status_code for _ in range(3)] == [400, 400, 429]
        assert client.post('/oauth/token', data=form, headers=there).status_code == 400
        form = {'token': 'dro_rt_x', 'client_id': CLIENT_ID}
        assert [client.post('/oauth/revoke', data=form, headers=here).status_code for _ in range(3)] == [200, 200, 429]
        assert client.post('/oauth/revoke', data=form, headers=there).status_code == 200

    def test_a_batch_counts_once_against_the_credential(self, on):
        on.monkeypatch.setitem(rate_limits.LIMITS, 'mcp_credential', '3 per minute')
        key = on.api_key()
        batch = [{'jsonrpc': '2.0', 'id': index, 'method': 'ping'} for index in range(10)]
        headers = {'MCP-Protocol-Version': '2025-03-26'}
        statuses = [on.mcp(key, body=batch, headers=headers).status_code for _ in range(4)]
        assert statuses == [200, 200, 200, 429]

    def test_a_broken_counter_store_lets_requests_through(self, on):
        class Broken:
            def hit(self, *args, **kwargs):
                raise RuntimeError('storage down')
        on.monkeypatch.setattr(rate_limits, '_strategy', lambda: Broken())
        assert on.mcp(on.api_key()).status_code == 200


# ============================================================================
# 10. FINDINGS OF THE SECURITY REVIEW
# ============================================================================
# Each test fails on the code as it was reviewed.

EXTERNAL_ACCESS_ERROR = (
    "External AI access is not enabled for this organization. An organization admin can switch it on "
    "in the organization's settings in Decision Records, under AI Features."
)


class TestExternalAccessSwitch:
    """The organisation's "external AI access" switch gates OAuth as it gates API keys."""

    def test_the_fixture_does_not_hide_the_switch(self, world):
        """A new organisation has the switch off; the tests' organisations have it switched on explicitly."""
        fresh = Tenant(domain='fresh.example', name='Fresh', status='active', maturity_state=MaturityState.BOOTSTRAP)
        db.session.add(fresh)
        db.session.commit()
        assert not fresh.ai_external_access_enabled
        assert world.tenant.ai_external_access_enabled is True

    def test_an_api_key_cannot_be_created_without_it(self, on):
        on.tenant.ai_external_access_enabled = False
        db.session.commit()
        response = on.signed_in(on.user).post('/api/user/ai/keys', json={'name': 'k'})
        assert response.status_code == 403

    def test_consent_lists_the_organisation_as_not_available(self, on):
        on.tenant.ai_external_access_enabled = False
        db.session.commit()
        body = on.view(on.signed_in(on.user), on.start()).get_json()
        assert body['organisations'] == [{
            'id': on.tenant.id, 'name': 'Example', 'domain': 'example.com', 'eligible': False,
            'reason': 'external_access_disabled', 'is_default': True,
        }]

    def test_consent_cannot_be_given_for_it(self, on):
        client = on.signed_in(on.user)
        public_id = on.start()
        on.view(client, public_id)
        on.tenant.ai_external_access_enabled = False
        db.session.commit()

        response = on.decide(client, public_id, decision='approve', tenant_id=on.tenant.id)

        assert response.status_code == 403 and response.get_json()['code'] == 'external_access_disabled'
        assert 'redirect_to' not in response.get_json()
        assert OAuthAuthorizationRequest.query.one().code_hash is None

    def test_switching_it_off_cuts_an_oauth_connection_at_once(self, on):
        access = on.tokens()['access_token']
        assert on.call(access, 'list_decisions').status_code == 200
        on.tenant.ai_external_access_enabled = False
        db.session.commit()

        for response in (on.mcp(access), on.call(access, 'list_decisions'),
                         on.call(access, 'create_decision', {
                             'title': 'Written from outside', 'context': 'c', 'decision': 'd', 'consequences': 'e'})):
            assert response.status_code == 403
            assert response.get_json()['error']['message'] == EXTERNAL_ACCESS_ERROR
            # A switch, not a missing permission: the client must not ask the user to consent again
            assert 'WWW-Authenticate' not in response.headers
            assert 'Use PostgreSQL' not in response.get_data(as_text=True)
        assert ArchitectureDecision.query.filter_by(title='Written from outside').count() == 0

        # Switched on again, the connection works without a new consent
        on.tenant.ai_external_access_enabled = True
        db.session.commit()
        assert on.mcp(access).status_code == 200
        assert OAuthGrant.query.one().revoked_at is None

    def test_switching_it_off_cuts_an_api_key_at_once(self, on):
        key = on.api_key(scopes=('read', 'search', 'write'))
        assert on.call(key, 'list_decisions').status_code == 200
        on.tenant.ai_external_access_enabled = False
        db.session.commit()

        response = on.call(key, 'list_decisions')

        assert response.status_code == 403
        assert response.get_json()['error']['message'] == EXTERNAL_ACCESS_ERROR
        on.tenant.ai_external_access_enabled = True
        db.session.commit()
        assert on.call(key, 'list_decisions').status_code == 200

    def test_it_holds_with_oauth_switched_off_too(self, world):
        SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
        SystemConfig.set(SystemConfig.KEY_AI_MCP_SERVER_ENABLED, 'true')
        key = world.api_key()
        world.tenant.ai_external_access_enabled = False
        db.session.commit()
        assert world.mcp(key).status_code == 403


class TestGraceWindowDoesNotHideAThief:
    """A copy of a refresh token replayed inside the 30 seconds cannot take the connection over unnoticed."""

    def test_the_real_client_using_what_it_was_given_ends_the_connection_for_both(self, on):
        first = on.tokens()
        real = on.refresh(first['refresh_token']).get_json()        # the real client rotates and receives a pair
        thief = on.refresh(first['refresh_token'])                  # a copy replayed inside the window
        assert thief.status_code == 200                             # indistinguishable from a lost response, so far
        thief = thief.get_json()
        assert OAuthGrant.query.one().revoked_at is None

        # The real client did receive its pair, and uses it
        response = on.mcp(real['access_token'])

        assert response.status_code == 401
        grant = OAuthGrant.query.one()
        assert grant.revoked_at is not None and grant.revoke_reason == 'refresh_reuse'
        assert AuditLog.query.filter_by(action_type=service.AUDIT_REFRESH_REUSE).count() == 1
        # ... which ends the thief's access as well
        assert on.mcp(thief['access_token']).status_code == 401
        assert on.refresh(thief['refresh_token']).status_code == 400

    def test_the_withdrawn_refresh_token_ends_it_too(self, on):
        first = on.tokens()
        real = on.refresh(first['refresh_token']).get_json()
        thief = on.refresh(first['refresh_token']).get_json()

        assert on.refresh(real['refresh_token']).status_code == 400

        assert OAuthGrant.query.one().revoke_reason == 'refresh_reuse'
        assert AuditLog.query.filter_by(action_type=service.AUDIT_REFRESH_REUSE).count() == 1
        assert on.mcp(thief['access_token']).status_code == 401

    def test_a_third_presentation_of_the_original_ends_it(self, on):
        first = on.tokens()
        on.refresh(first['refresh_token'])
        second = on.refresh(first['refresh_token'])
        assert second.status_code == 200

        third = on.refresh(first['refresh_token'])

        assert third.status_code == 400
        assert OAuthGrant.query.one().revoke_reason == 'refresh_reuse'
        assert on.mcp(second.get_json()['access_token']).status_code == 401

    def test_a_response_that_really_was_lost_costs_nothing(self, on):
        first = on.tokens()
        on.refresh(first['refresh_token'])                          # this response never arrived
        retried = on.refresh(first['refresh_token']).get_json()     # the client asks again

        assert on.mcp(retried['access_token']).status_code == 200
        assert on.refresh(retried['refresh_token']).status_code == 200
        assert OAuthGrant.query.one().revoked_at is None
        assert AuditLog.query.filter_by(action_type=service.AUDIT_REFRESH_REUSE).count() == 0
        # The withdrawn pair is still there to be recognised
        assert OAuthToken.query.filter(OAuthToken.withdrawn_at.isnot(None)).count() == 2


class TestSessionHeadersStayOffSessionlessEndpoints:

    def test_no_csrf_token_on_metadata_token_revoke_or_mcp(self, on):
        browser = on.signed_in(on.user)
        assert browser.get('/api/user/me').headers.get('X-CSRF-Token') == CSRF     # where it belongs
        responses = [
            browser.get('/.well-known/oauth-authorization-server'),
            browser.get('/.well-known/oauth-protected-resource'),
            browser.get('/.well-known/openid-configuration'),
            browser.post('/oauth/token', data={'grant_type': 'x', 'client_id': CLIENT_ID}),
            browser.post('/oauth/revoke', data={'token': 'x', 'client_id': CLIENT_ID}),
            browser.post('/api/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'}),
        ]
        for response in responses:
            assert 'X-CSRF-Token' not in response.headers

    def test_metadata_is_not_marked_for_shared_caches(self, on):
        for path in ('/.well-known/oauth-authorization-server', '/.well-known/oauth-protected-resource'):
            cache = on.signed_in(on.user).get(path).headers['Cache-Control']
            assert 'public' not in cache and 'private' in cache


class TestApiKeyBatchesAreNotNewlyLimited:

    def test_a_large_batch_with_an_api_key_is_one_request(self, world):
        """Switch off, API key: a batch of 301 pings was answered with 200 before the per-credential limit existed."""
        SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
        SystemConfig.set(SystemConfig.KEY_AI_MCP_SERVER_ENABLED, 'true')
        key = world.api_key()
        batch = [{'jsonrpc': '2.0', 'id': index, 'method': 'ping'} for index in range(301)]

        response = world.mcp(key, body=batch, headers={'MCP-Protocol-Version': '2025-03-26'})

        assert response.status_code == 200
        assert len(response.get_json()) == 301


class TestAnonymousRequestsAreBounded:
    """What visitors who are not signed in can make the server store."""

    def test_state_is_limited_to_what_clients_need(self, on):
        assert service.MAX_STATE_LENGTH == 1024
        assert on.authorize(state='s' * 1024).status_code == 302
        assert on.authorize(state='s' * 1025).status_code == 400

    def test_one_network_cannot_pile_up_requests_by_changing_its_address(self, on):
        client = on.anonymous()
        url = '/oauth/authorize?' + urlencode(on.authorize_params(state='s' * 1024))
        statuses = [client.get(url, headers={'CF-Connecting-IP': f'2001:db8::{index:x}'}).status_code
                    for index in range(90)]
        assert statuses.count(302) == 30 and statuses.count(429) == 60
        assert OAuthAuthorizationRequest.query.count() == 30

    def test_requests_waiting_for_an_answer_are_capped_over_the_whole_installation(self, on):
        on.monkeypatch.setattr(service, 'MAX_OPEN_REQUESTS', 3)
        client = on.anonymous()
        url = '/oauth/authorize?' + urlencode(on.authorize_params())

        statuses = [client.get(url, headers={'CF-Connecting-IP': f'198.51.{index}.7'}).status_code
                    for index in range(5)]

        assert statuses == [302, 302, 302, 503, 503]
        assert OAuthAuthorizationRequest.query.count() == 3
        # An answered request no longer counts
        browser = on.signed_in(on.user)
        public_id = OAuthAuthorizationRequest.query.first().public_id
        on.view(browser, public_id)
        on.decide(browser, public_id, decision='deny')
        assert client.get(url, headers={'CF-Connecting-IP': '198.51.9.7'}).status_code == 302

    def test_unanswered_requests_go_minutes_after_they_expire(self, on):
        import retention
        on.start()
        kept = on.start()
        expired = OAuthAuthorizationRequest.query.order_by(OAuthAuthorizationRequest.id).first()
        expired.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=6)
        db.session.commit()

        assert retention.purge_undecided_oauth_requests() == 1

        assert [row.public_id for row in OAuthAuthorizationRequest.query.all()] == [kept]

    def test_the_authorization_endpoint_clears_them_in_passing(self, on):
        on.start()
        stale = OAuthAuthorizationRequest.query.one()
        stale.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=6)
        db.session.commit()
        on.monkeypatch.setattr(endpoints, '_last_stale_request_purge', 0.0)

        fresh = on.start()

        assert [row.public_id for row in OAuthAuthorizationRequest.query.all()] == [fresh]

    def test_answered_requests_and_recent_ones_are_not_cleared(self, on):
        import retention
        code = on.code()                                   # answered: its code must stay recognisable
        waiting = on.start()                               # expired a minute ago: may still be on someone's screen
        rows = {row.public_id: row for row in OAuthAuthorizationRequest.query.all()}
        long_ago = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)
        for row in rows.values():
            row.expires_at = long_ago if row.public_id != waiting else (
                datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1))
        db.session.commit()

        assert retention.purge_undecided_oauth_requests() == 0
        assert OAuthAuthorizationRequest.query.count() == 2
        assert on.exchange(code).status_code == 200


class TestALostMembershipEndsTheConnectionForGood:

    def test_a_removed_member_who_is_added_back_does_not_get_the_connection_back(self, on):
        tokens = on.tokens()
        db.session.delete(on.membership(on.user))
        db.session.commit()

        assert on.mcp(tokens['access_token']).status_code == 401

        grant = OAuthGrant.query.one()
        assert grant.revoked_at is not None and grant.revoke_reason == 'owner_gone'
        entry = AuditLog.query.filter_by(action_type=service.AUDIT_GRANT_REVOKED).one()
        assert entry.details['reason'] == 'owner_gone'
        on.join(on.user, on.tenant)
        assert on.mcp(tokens['access_token']).status_code == 401
        assert on.refresh(tokens['refresh_token']).status_code == 400

    def test_the_same_for_a_deleted_and_restored_organisation(self, on):
        tokens = on.tokens()
        on.tenant.deleted_at = datetime.now(timezone.utc)
        db.session.commit()
        assert on.mcp(tokens['access_token']).status_code == 401
        on.tenant.deleted_at = None
        db.session.commit()
        assert on.mcp(tokens['access_token']).status_code == 401
        assert OAuthGrant.query.one().revoke_reason == 'owner_gone'

    def test_the_same_for_an_anonymised_account(self, on):
        tokens = on.tokens()
        on.user.is_anonymized = True
        db.session.commit()
        assert on.mcp(tokens['access_token']).status_code == 401
        on.user.is_anonymized = False
        db.session.commit()
        assert on.mcp(tokens['access_token']).status_code == 401

    def test_erasing_an_account_removes_its_connections(self, on):
        """The one path in the app that deletes memberships (retention) deletes the grants with them."""
        import retention
        tokens = on.tokens()
        user_id = on.user.id
        assert retention.anonymize_user(user_id) is True
        assert OAuthGrant.query.filter_by(user_id=user_id).count() == 0
        assert on.mcp(tokens['access_token']).status_code == 401


class TestAUsedCodeInAnotherClientsName:

    def test_it_does_not_end_the_connection(self, on):
        code = on.code()
        tokens = on.exchange(code).get_json()

        response = on.anonymous().post('/oauth/token', data={
            'grant_type': 'authorization_code', 'code': code, 'client_id': 'https://evil.example.net/c.json',
            'redirect_uri': 'https://x.invalid/', 'code_verifier': 'w' * 43})

        assert response.status_code == 400 and response.get_json()['error'] == 'invalid_grant'
        assert OAuthGrant.query.one().revoked_at is None
        assert on.mcp(tokens['access_token']).status_code == 200

    def test_the_same_client_presenting_it_again_still_does(self, on):
        code = on.code()
        tokens = on.exchange(code).get_json()
        assert on.exchange(code).status_code == 400
        assert OAuthGrant.query.one().revoke_reason == 'code_reuse'
        assert on.mcp(tokens['access_token']).status_code == 401


class TestDocumentTextIsNotEchoed:

    @pytest.mark.parametrize('field,value', [
        ('token_endpoint_auth_method', 'private_key_jwt\n2026-11-25 [SECURITY:AUTH] forged line'),
        ('token_endpoint_auth_method', 'x\r\nforged line'),
        ('client_name', '\n\n'),
        ('grant_types', ['implicit\nforged line']),
        ('response_types', ['token\nforged line']),
    ])
    def test_values_from_the_document_reach_neither_the_log_nor_the_answer(self, on, caplog, field, value):
        import logging
        on.document = _document(**{field: value})
        with caplog.at_level(logging.DEBUG):
            response = on.view(on.signed_in(on.user), on.start())

        assert response.status_code == 400
        assert 'forged line' not in response.get_data(as_text=True)
        for record in caplog.records:
            message = record.getMessage()
            if 'Client' in message or 'oauth' in message.lower():
                assert 'forged line' not in message
                assert 'private_key_jwt' not in message
