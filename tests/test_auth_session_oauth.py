"""
Real-app regression tests for sign-in sessions, OAuth redirects and passkey gating.

These drive the actual Flask app (not a bare test app) so the before_request
session-expiry and CSRF hooks run exactly as they do in production.

The social sign-in routes import their provider helpers from the Enterprise
`ee` package at request time. So that the shared callback logic in app.py
(redirects, session creation, cookie attributes) is exercised in Community
Edition as well, the provider module is replaced with a small stand-in for the
duration of a test. Tests that need the real provider module live in
tests/test_google_oauth.py behind the Enterprise skip marker.
"""
import ast
import importlib
import os
import secrets
import sys
import types
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    db, User, Tenant, TenantMembership, AuthConfig, SSOConfig, GlobalRole,
    MaturityState, SetupToken, WebAuthnCredential
)
from tests.app_test_utils import load_test_app, parse_set_cookie, website_handoff_app

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STRONG_PASSWORD = 'Str0ngPassword'


# ==================== Fixtures and helpers ====================

@pytest.fixture
def real_app():
    """The real Flask app with all routes, on an in-memory database."""
    app_module, test_app = load_test_app(secret_key='test-secret-key-auth-session-oauth')

    with test_app.app_context():
        db.create_all()
        app_module.init_database()
        yield app_module, test_app
        db.session.remove()
        db.drop_all()
        app_module._db_initialized = False


def make_tenant(domain='acme.test'):
    tenant = Tenant(domain=domain, name=domain, status='active',
                    maturity_state=MaturityState.BOOTSTRAP)
    db.session.add(tenant)
    db.session.commit()
    return tenant


def make_user(email='pat@acme.test', *, auth_type='local', password=None, passkey=False,
              role=GlobalRole.USER):
    domain = email.split('@')[1]
    tenant = Tenant.query.filter_by(domain=domain).first() or make_tenant(domain)
    user = User(email=email, sso_domain=domain, auth_type=auth_type, email_verified=True)
    user.set_name(first_name='Pat', last_name='Example')
    if password:
        user.set_password(password)
    db.session.add(user)
    db.session.flush()
    db.session.add(TenantMembership(user_id=user.id, tenant_id=tenant.id, global_role=role))
    if passkey:
        db.session.add(WebAuthnCredential(
            user_id=user.id,
            credential_id=f'cred-{user.id}'.encode(),
            public_key=b'public-key',
            sign_count=0,
            device_name='Test key',
        ))
    db.session.commit()
    return user


# ==================== Sessions always carry an expiry ====================

class TestSessionsSurviveTheNextRequest:
    """A session without `_expires_at` is cleared by check_session_expiry()."""

    def test_setup_password_session_survives_next_request(self, real_app):
        _, test_app = real_app
        user = make_user('newhire@acme.test')
        token = SetupToken.create_for_user(user)._token_string
        client = test_app.test_client()

        response = client.post('/api/auth/setup-password',
                               json={'token': token, 'password': STRONG_PASSWORD})
        assert response.status_code == 200, response.get_json()

        with client.session_transaction() as sess:
            assert sess['user_id'] == user.id
            assert datetime.fromisoformat(sess['_expires_at']) > datetime.now(timezone.utc)

        me = client.get('/api/user/me')
        assert me.status_code == 200, me.get_json()
        assert me.get_json()['email'] == 'newhire@acme.test'

    def test_setup_password_rejects_bad_token_without_creating_session(self, real_app):
        _, test_app = real_app
        make_user('newhire@acme.test')
        client = test_app.test_client()

        response = client.post('/api/auth/setup-password',
                               json={'token': 'not-a-token', 'password': STRONG_PASSWORD})
        assert response.status_code == 401
        assert 'error' in response.get_json()
        assert client.get('/api/user/me').status_code == 401

    def test_password_login_session_survives_next_request(self, real_app):
        """Control: the path that always worked keeps working."""
        _, test_app = real_app
        make_user('pat@acme.test', password=STRONG_PASSWORD)
        client = test_app.test_client()

        response = client.post('/api/auth/login',
                               json={'email': 'pat@acme.test', 'password': STRONG_PASSWORD})
        assert response.status_code == 200, response.get_json()
        assert client.get('/api/user/me').status_code == 200

    def test_session_without_expiry_is_still_rejected(self, real_app):
        """The legacy-session guard stays: no expiry means no session."""
        _, test_app = real_app
        user = make_user('pat@acme.test', password=STRONG_PASSWORD)
        client = test_app.test_client()
        with client.session_transaction() as sess:
            sess['user_id'] = user.id

        assert client.get('/api/user/me').status_code == 401


class TestSessionCreationGoesThroughOneHelper:
    """Every sign-in path must call auth.start_user_session()."""

    SOURCES = ('app.py', 'auth.py', 'webauthn_auth.py', 'security.py')

    @staticmethod
    def _direct_user_id_assignments(path):
        with open(path, encoding='utf-8') as handle:
            tree = ast.parse(handle.read())

        hits = []
        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for node in ast.walk(func):
                if not isinstance(node, ast.Assign):
                    continue
                for target in node.targets:
                    if (isinstance(target, ast.Subscript)
                            and isinstance(target.value, ast.Name)
                            and target.value.id == 'session'
                            and isinstance(target.slice, ast.Constant)
                            and target.slice.value == 'user_id'):
                        hits.append((func.name, node.lineno))
        return hits

    def test_only_the_helper_assigns_session_user_id(self):
        offenders = []
        for name in self.SOURCES:
            for func_name, lineno in self._direct_user_id_assignments(os.path.join(REPO_ROOT, name)):
                if (name, func_name) != ('auth.py', 'start_user_session'):
                    offenders.append(f'{name}:{lineno} in {func_name}()')

        assert offenders == [], (
            "session['user_id'] must only be set by auth.start_user_session(), "
            f"which also sets the session expiry. Offenders: {offenders}"
        )


# ==================== Social sign-in stand-ins ====================

APP_BASE = 'https://app.example.test'


class FakeProvider:
    """Stand-in for one Enterprise provider module, enough to drive app.py's routes."""

    def __init__(self, name, module, initiate, callback, attrs, userinfo, feature=None,
                 welcome_suffix=''):
        self.name = name
        self.module = module
        self.initiate = initiate
        self.callback = callback
        self.attrs = attrs
        self.userinfo = userinfo
        self.feature = feature
        self.welcome_suffix = welcome_suffix
        self.states = {}

    def generate_state(self, return_url=None, extra_data=None):
        token = f'state-{len(self.states) + 1}-{secrets.token_urlsafe(8)}'
        self.states[token] = {
            'type': self.name,
            'return_url': return_url,
            'extra_data': extra_data or {},
        }
        return token

    def verify_state(self, state):
        return self.states.get(state)

    def install(self, monkeypatch):
        module = types.ModuleType(self.module)
        for attr, value in self.attrs(self).items():
            setattr(module, attr, value)

        # Make the parent packages importable where the Enterprise tree is absent.
        parts = self.module.split('.')
        for depth in range(1, len(parts)):
            parent = '.'.join(parts[:depth])
            try:
                importlib.import_module(parent)
            except ImportError:
                stub = types.ModuleType(parent)
                stub.__path__ = []
                monkeypatch.setitem(sys.modules, parent, stub)
        monkeypatch.setitem(sys.modules, self.module, module)

        if self.feature:
            import feature_flags
            monkeypatch.setitem(feature_flags.FEATURES, self.feature, True)
        return self

    def default_destination(self, domain):
        return f'{APP_BASE}/{domain}{self.welcome_suffix}'

    def with_welcome(self, url):
        if not self.welcome_suffix:
            return url
        return url + ('&' if '?' in url else '?') + self.welcome_suffix.lstrip('?')


def _google():
    return FakeProvider(
        name='google',
        module='ee.backend.oauth_providers.google_oauth',
        initiate='/auth/google',
        callback='/auth/google/callback',
        attrs=lambda p: {
            'is_google_oauth_configured': lambda: True,
            'get_google_client_id': lambda: 'test-google-client-id',
            'get_google_client_secret': lambda: 'test-google-client-secret',
            'generate_google_oauth_state': p.generate_state,
            'verify_google_oauth_state': p.verify_state,
            'GOOGLE_OAUTH_AUTHORIZE_URL': 'https://accounts.google.com/o/oauth2/v2/auth',
            'GOOGLE_OAUTH_TOKEN_URL': 'https://oauth2.googleapis.com/token',
            'GOOGLE_OAUTH_USERINFO_URL': 'https://www.googleapis.com/oauth2/v3/userinfo',
            'GOOGLE_OAUTH_SCOPES': 'openid email profile',
        },
        userinfo=lambda email: {'email': email, 'name': 'Pat Example', 'sub': 'google-sub-1'},
    )


def _microsoft():
    return FakeProvider(
        name='microsoft',
        module='ee.backend.oauth_providers.microsoft_oauth',
        initiate='/auth/microsoft',
        callback='/auth/microsoft/callback',
        attrs=lambda p: {
            'is_microsoft_oauth_configured': lambda: True,
            'get_microsoft_client_id': lambda: 'test-ms-client-id',
            'get_microsoft_client_secret': lambda: 'test-ms-client-secret',
            'generate_microsoft_oauth_state': p.generate_state,
            'verify_microsoft_oauth_state': p.verify_state,
            'MICROSOFT_OAUTH_AUTHORIZE_URL': 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize',
            'MICROSOFT_OAUTH_TOKEN_URL': 'https://login.microsoftonline.com/common/oauth2/v2.0/token',
            'MICROSOFT_GRAPH_USER_URL': 'https://graph.microsoft.com/v1.0/me',
            'MICROSOFT_OAUTH_SCOPES': 'openid email profile User.Read',
        },
        userinfo=lambda email: {'mail': email, 'displayName': 'Pat Example', 'id': 'ms-object-1'},
    )


def _slack():
    return FakeProvider(
        name='slack',
        module='ee.backend.slack.slack_security',
        initiate='/auth/slack/oidc',
        callback='/auth/slack/oidc/callback',
        attrs=lambda p: {
            'get_slack_client_id': lambda: 'test-slack-client-id',
            'get_slack_client_secret': lambda: 'test-slack-client-secret',
            'generate_slack_oidc_state': p.generate_state,
            'verify_slack_oidc_state': p.verify_state,
            'SLACK_OIDC_AUTHORIZE_URL': 'https://slack.com/openid/connect/authorize',
            'SLACK_OIDC_TOKEN_URL': 'https://slack.com/api/openid.connect.token',
            'SLACK_OIDC_USERINFO_URL': 'https://slack.com/api/openid.connect.userInfo',
            'SLACK_OIDC_SCOPES': 'openid email profile',
        },
        userinfo=lambda email: {'ok': True, 'email': email, 'name': 'Pat Example', 'sub': 'U123'},
        feature='slack_integration',
        welcome_suffix='?slack_welcome=1',
    )


def _teams():
    provider = FakeProvider(
        name='teams',
        module='ee.backend.teams.teams_security',
        initiate='/auth/teams/oidc',
        callback='/auth/teams/oidc/callback',
        attrs=lambda p: {
            'get_teams_bot_app_id': lambda: 'test-teams-app-id',
            'generate_teams_oidc_state': p.generate_state,
            'verify_teams_oidc_state': p.verify_state,
            'exchange_teams_oidc_code': lambda code, redirect_uri: (dict(p.claims), 'access-token'),
            'get_teams_user_info': lambda access_token: None,
            'TEAMS_OIDC_SCOPES': 'openid email profile',
        },
        userinfo=lambda email: {},
        feature='teams_integration',
    )
    provider.claims = {}
    return provider


PROVIDER_FACTORIES = {
    'google': _google,
    'microsoft': _microsoft,
    'slack': _slack,
    'teams': _teams,
}
SOCIAL_PROVIDERS = ['google', 'microsoft', 'slack']
ALL_PROVIDERS = SOCIAL_PROVIDERS + ['teams']


@pytest.fixture
def oauth_env(real_app, monkeypatch):
    """Real app plus a factory that installs a stand-in provider module."""
    app_module, test_app = real_app
    monkeypatch.setenv('APP_BASE_URL', APP_BASE)
    monkeypatch.delenv('OAUTH_BASE_URL', raising=False)

    def install(name):
        return PROVIDER_FACTORIES[name]().install(monkeypatch)

    return test_app, install


def _http_mocks(provider, email):
    token = Mock(ok=True, status_code=200)
    token.json.return_value = {'access_token': 'provider-access-token'}
    userinfo = Mock(ok=True, status_code=200)
    userinfo.json.return_value = provider.userinfo(email)
    return patch('requests.post', return_value=token), patch('requests.get', return_value=userinfo)


def start_sign_in(client, provider, return_url=None, **kwargs):
    """Call the initiate route and return (response, state)."""
    query = {} if return_url is None else {'return_url': return_url}
    response = client.get(provider.initiate, query_string=query, **kwargs)
    assert response.status_code == 302, response.get_data(as_text=True)
    state = parse_qs(urlparse(response.headers['Location']).query)['state'][0]
    return response, state


def finish_sign_in(client, provider, email, state, **kwargs):
    """Call the callback route with the provider's HTTP calls mocked."""
    if provider.name == 'teams':
        provider.claims = {'email': email, 'name': 'Pat Example', 'tid': 'ms-tenant'}
    post, get = _http_mocks(provider, email)
    with post as post_mock, get:
        response = client.get(provider.callback, query_string={'code': 'auth-code', 'state': state},
                              **kwargs)
    response.token_request = post_mock
    return response


def sign_in(client, provider, email, return_url=None):
    _, state = start_sign_in(client, provider, return_url=return_url)
    return finish_sign_in(client, provider, email, state)


# ==================== Open redirect after OAuth ====================

HOSTILE_RETURN_URLS = [
    'https://evil.example/phish',
    'http://evil.example',
    '//evil.example',
    '///evil.example',
    '/\\evil.example',
    '\\\\evil.example',
    'javascript:alert(document.domain)',
    'evil.example',
    '@evil.example',
    '/\t/evil.example',
    '/%2F/evil.example',
    '/%5Cevil.example',
    '/acme.test\r\nSet-Cookie: session=stolen',
]


class TestOAuthReturnUrlIsSameSiteOnly:
    """return_url travels in the OAuth state; it must never send the user off-site."""

    @pytest.mark.parametrize('provider_name', ALL_PROVIDERS)
    @pytest.mark.parametrize('return_url', HOSTILE_RETURN_URLS)
    def test_hostile_return_url_falls_back_to_tenant_home(self, oauth_env, provider_name, return_url):
        test_app, install = oauth_env
        provider = install(provider_name)
        make_user('pat@acme.test', password=STRONG_PASSWORD)
        client = test_app.test_client()

        response = sign_in(client, provider, 'pat@acme.test', return_url=return_url)

        assert response.status_code == 302
        assert response.headers['Location'] == provider.default_destination('acme.test')

    @pytest.mark.parametrize('provider_name', ALL_PROVIDERS)
    @pytest.mark.parametrize('return_url', HOSTILE_RETURN_URLS)
    def test_callback_does_not_trust_return_url_already_in_state(self, oauth_env, provider_name,
                                                                return_url):
        """States minted before this fix (or by another code path) are validated too."""
        test_app, install = oauth_env
        provider = install(provider_name)
        make_user('pat@acme.test', password=STRONG_PASSWORD)
        client = test_app.test_client()
        state = provider.generate_state(return_url=return_url)

        response = finish_sign_in(client, provider, 'pat@acme.test', state)

        assert response.status_code == 302
        assert response.headers['Location'] == provider.default_destination('acme.test')

    @pytest.mark.parametrize('provider_name', ALL_PROVIDERS)
    def test_hostile_return_url_is_not_carried_in_state(self, oauth_env, provider_name):
        test_app, install = oauth_env
        provider = install(provider_name)
        client = test_app.test_client()

        _, state = start_sign_in(client, provider, return_url='https://evil.example/phish')

        assert provider.states[state]['return_url'] == '/'

    @pytest.mark.parametrize('provider_name', ALL_PROVIDERS)
    @pytest.mark.parametrize('return_url', [
        '/acme.test/decisions/42',
        '/acme.test/decisions?status=accepted',
    ])
    def test_same_site_return_url_is_honoured(self, oauth_env, provider_name, return_url):
        test_app, install = oauth_env
        provider = install(provider_name)
        make_user('pat@acme.test', password=STRONG_PASSWORD)
        client = test_app.test_client()

        response = sign_in(client, provider, 'pat@acme.test', return_url=return_url)

        assert response.status_code == 302
        assert response.headers['Location'] == provider.with_welcome(f'{APP_BASE}{return_url}')

    @pytest.mark.parametrize('provider_name', ALL_PROVIDERS)
    @pytest.mark.parametrize('return_url', [None, '/', '/?utm=1', ''])
    def test_missing_or_root_return_url_goes_to_tenant_home(self, oauth_env, provider_name, return_url):
        test_app, install = oauth_env
        provider = install(provider_name)
        make_user('pat@acme.test', password=STRONG_PASSWORD)
        client = test_app.test_client()

        response = sign_in(client, provider, 'pat@acme.test', return_url=return_url)

        assert response.status_code == 302
        assert response.headers['Location'] == provider.default_destination('acme.test')

    @pytest.mark.parametrize('provider_name', ALL_PROVIDERS)
    def test_redirect_stays_on_request_host_without_app_base_url(self, oauth_env, monkeypatch,
                                                                 provider_name):
        test_app, install = oauth_env
        monkeypatch.delenv('APP_BASE_URL', raising=False)
        provider = install(provider_name)
        make_user('pat@acme.test', password=STRONG_PASSWORD)
        client = test_app.test_client()

        response = sign_in(client, provider, 'pat@acme.test', return_url='https://evil.example')

        assert response.status_code == 302
        assert urlparse(response.headers['Location']).netloc in ('', 'localhost')
        assert 'evil.example' not in response.headers['Location']


# ==================== auth_type, social sign-in and passkeys ====================

def make_sso_tenant(domain='sso-corp.test', *, enabled=True, auth_method='sso', with_auth_config=True):
    """A tenant with its own OIDC identity provider configured."""
    if not Tenant.query.filter_by(domain=domain).first():
        make_tenant(domain)
    db.session.add(SSOConfig(
        domain=domain, provider_name='Okta', client_id='client', client_secret='secret',
        discovery_url='https://idp.example.test/.well-known/openid-configuration', enabled=enabled,
    ))
    if with_auth_config:
        db.session.add(AuthConfig(domain=domain, auth_method=auth_method))
    db.session.commit()


def passkey_options(test_app, email):
    return test_app.test_client().post('/api/webauthn/authenticate/options', json={'email': email})


class TestSocialSignInKeepsLocalCredentials:
    """Signing in once with Google/Microsoft/Slack must not disable a user's passkey."""

    @pytest.mark.parametrize('provider_name', SOCIAL_PROVIDERS)
    def test_user_with_password_and_passkey_keeps_auth_type_and_passkey(self, oauth_env, provider_name):
        test_app, install = oauth_env
        provider = install(provider_name)
        user = make_user('pat@acme.test', password=STRONG_PASSWORD, passkey=True)
        user_id = user.id

        response = sign_in(test_app.test_client(), provider, 'pat@acme.test')
        assert response.status_code == 302
        assert response.headers['Location'] == provider.default_destination('acme.test')

        db.session.expire_all()
        assert db.session.get(User, user_id).auth_type == 'local'

        options = passkey_options(test_app, 'pat@acme.test')
        assert options.status_code == 200, options.get_json()
        assert 'challenge' in options.get_json()

    @pytest.mark.parametrize('provider_name', SOCIAL_PROVIDERS)
    @pytest.mark.parametrize('auth_type,password,passkey', [
        ('local', STRONG_PASSWORD, False),
        ('webauthn', None, True),
        ('webauthn', STRONG_PASSWORD, True),
    ])
    def test_users_with_a_local_credential_keep_their_auth_type(self, oauth_env, provider_name,
                                                                auth_type, password, passkey):
        test_app, install = oauth_env
        provider = install(provider_name)
        user_id = make_user('pat@acme.test', auth_type=auth_type, password=password, passkey=passkey).id

        assert sign_in(test_app.test_client(), provider, 'pat@acme.test').status_code == 302

        db.session.expire_all()
        assert db.session.get(User, user_id).auth_type == auth_type

    @pytest.mark.parametrize('provider_name', SOCIAL_PROVIDERS)
    def test_user_without_local_credentials_is_marked_sso_and_can_use_the_app(self, oauth_env,
                                                                             provider_name):
        """An approved member with no password or passkey relies on the provider alone."""
        test_app, install = oauth_env
        provider = install(provider_name)
        user_id = make_user('invited@acme.test').id
        client = test_app.test_client()

        assert sign_in(client, provider, 'invited@acme.test').status_code == 302

        db.session.expire_all()
        assert db.session.get(User, user_id).auth_type == 'sso'
        # login_required must not bounce them to credential setup
        decisions = client.get('/api/decisions')
        assert decisions.status_code == 200, decisions.get_json()

    @pytest.mark.parametrize('provider_name', SOCIAL_PROVIDERS)
    def test_new_user_created_by_social_sign_in_is_marked_sso(self, oauth_env, provider_name):
        test_app, install = oauth_env
        provider = install(provider_name)
        client = test_app.test_client()

        response = sign_in(client, provider, 'founder@newco.test')
        assert response.status_code == 302
        assert response.headers['Location'] == provider.default_destination('newco.test')

        user = User.query.filter_by(email='founder@newco.test').first()
        assert user is not None
        assert user.auth_type == 'sso'
        assert client.get('/api/decisions').status_code == 200


class TestPasskeySignInGate:
    """Passkey sign-in is blocked by tenant SSO enforcement, not by a user's auth_type."""

    def test_user_already_flipped_to_sso_can_use_existing_passkey(self, real_app):
        """Accounts flipped by the old behaviour recover without a data migration."""
        _, test_app = real_app
        make_user('pat@acme.test', auth_type='sso', password=STRONG_PASSWORD, passkey=True)

        response = passkey_options(test_app, 'pat@acme.test')

        assert response.status_code == 200, response.get_json()
        assert 'challenge' in response.get_json()

    def test_sso_user_without_passkey_is_pointed_at_sso(self, real_app):
        _, test_app = real_app
        make_user('pat@acme.test', auth_type='sso')

        response = passkey_options(test_app, 'pat@acme.test')

        assert response.status_code == 400
        assert 'SSO' in response.get_json()['error']

    def test_local_user_without_passkey_gets_no_passkeys_error(self, real_app):
        _, test_app = real_app
        make_user('pat@acme.test', password=STRONG_PASSWORD)

        response = passkey_options(test_app, 'pat@acme.test')

        assert response.status_code == 400
        assert response.get_json()['error'] == 'No passkeys registered for this account'

    def test_unknown_user_returns_404(self, real_app):
        _, test_app = real_app

        response = passkey_options(test_app, 'nobody@acme.test')

        assert response.status_code == 404
        assert response.get_json()['error'] == 'User not found'

    def test_options_without_email_still_supported(self, real_app):
        """Discoverable-credential sign-in sends no email."""
        _, test_app = real_app

        response = test_app.test_client().post('/api/webauthn/authenticate/options', json={})

        assert response.status_code == 200
        assert 'challenge' in response.get_json()

    @pytest.mark.parametrize('auth_type', ['local', 'webauthn', 'sso'])
    def test_tenant_enforcing_sso_blocks_passkey_options(self, real_app, auth_type):
        _, test_app = real_app
        make_sso_tenant('sso-corp.test')
        make_user('pat@sso-corp.test', auth_type=auth_type, passkey=True)

        response = passkey_options(test_app, 'pat@sso-corp.test')

        assert response.status_code == 400
        assert 'SSO' in response.get_json()['error']

    def test_sso_configured_without_auth_config_counts_as_enforced(self, real_app):
        """Same rule as passkey registration: SSO config with no auth config means SSO only."""
        _, test_app = real_app
        make_sso_tenant('sso-corp.test', with_auth_config=False)
        make_user('pat@sso-corp.test', passkey=True)

        assert passkey_options(test_app, 'pat@sso-corp.test').status_code == 400

    @pytest.mark.parametrize('kwargs', [
        {'auth_method': 'local'},                    # SSO offered alongside other methods
        {'auth_method': 'sso', 'enabled': False},    # SSO config switched off
    ])
    def test_tenant_not_enforcing_sso_allows_passkey_options(self, real_app, kwargs):
        _, test_app = real_app
        make_sso_tenant('mixed.test', **kwargs)
        make_user('pat@mixed.test', passkey=True)

        response = passkey_options(test_app, 'pat@mixed.test')

        assert response.status_code == 200, response.get_json()

    def test_tenant_enforcing_sso_blocks_passkey_verification(self, real_app):
        """The email-less passkey flow skips the options check, so verify enforces it too."""
        app_module, test_app = real_app
        make_sso_tenant('sso-corp.test')
        user = make_user('pat@sso-corp.test', passkey=True)
        client = test_app.test_client()

        with patch.object(app_module, 'verify_authentication', return_value=(user, None)):
            response = client.post('/api/webauthn/authenticate/verify', json={'credential': {'id': 'x'}})

        assert response.status_code == 400
        assert 'SSO' in response.get_json()['error']
        assert client.get('/api/user/me').status_code == 401

    @pytest.mark.parametrize('auth_type', ['local', 'webauthn', 'sso'])
    def test_passkey_verification_signs_in_when_sso_not_enforced(self, real_app, auth_type):
        app_module, test_app = real_app
        user = make_user('pat@acme.test', auth_type=auth_type, password=STRONG_PASSWORD, passkey=True)
        client = test_app.test_client()

        with patch.object(app_module, 'verify_authentication', return_value=(user, None)):
            response = client.post('/api/webauthn/authenticate/verify', json={'credential': {'id': 'x'}})

        assert response.status_code == 200, response.get_json()
        me = client.get('/api/user/me')
        assert me.status_code == 200
        assert me.get_json()['email'] == 'pat@acme.test'

    def test_passkey_registration_still_refused_for_sso_enforced_domain(self, real_app):
        _, test_app = real_app
        make_sso_tenant('sso-corp.test')

        response = test_app.test_client().post(
            '/api/webauthn/register/options',
            json={'email': 'new@sso-corp.test', 'name': 'New Person'})

        assert response.status_code == 400
        assert response.get_json()['error'] == 'This domain requires SSO authentication'

    def test_options_offer_registered_credentials_whatever_the_auth_type(self, real_app):
        """A password-first ('local') account's passkeys are listed for non-discoverable keys."""
        _, test_app = real_app
        make_user('pat@acme.test', auth_type='local', password=STRONG_PASSWORD, passkey=True)

        response = passkey_options(test_app, 'pat@acme.test')

        assert response.status_code == 200
        assert len(response.get_json().get('allowCredentials') or []) == 1


# ==================== Website-to-app handoff ====================

SITE = 'https://decisionrecords.test'            # marketing website; OAuth callbacks land here
APP_HOST = 'https://app.decisionrecords.test'    # the app
COOKIE_DOMAIN = 'decisionrecords.test'
OTHER_SITE = 'https://unrelated.test'


@pytest.fixture
def handoff_env(monkeypatch):
    """Real app configured like production: callback on the website, app on a subdomain."""
    with website_handoff_app(
        secret_key='test-secret-key-website-handoff',
        cookie_domain=COOKIE_DOMAIN,
        oauth_base_url=SITE,
        app_base_url=APP_HOST,
    ) as (app_module, test_app):
        yield test_app, lambda name: PROVIDER_FACTORIES[name]().install(monkeypatch)


class TestWebsiteToAppHandoff:
    """Sign in on the website host, arrive signed in on the app host."""

    def test_app_reads_handoff_settings_from_environment(self, handoff_env):
        test_app, _ = handoff_env

        assert test_app.config['SESSION_COOKIE_DOMAIN'] == COOKIE_DOMAIN
        assert test_app.config['SESSION_COOKIE_SECURE'] is True

    @pytest.mark.parametrize('provider_name', SOCIAL_PROVIDERS)
    def test_sign_in_on_website_lands_signed_in_on_app(self, handoff_env, provider_name):
        test_app, install = handoff_env
        provider = install(provider_name)
        make_user('pat@acme.test', password=STRONG_PASSWORD)
        client = test_app.test_client()
        callback_uri = f'{SITE}{provider.callback}'

        # 1. The website's sign-in button hits the initiate route on the website host.
        initiate, state = start_sign_in(client, provider, base_url=SITE)
        authorize = urlparse(initiate.headers['Location'])
        assert authorize.netloc not in ('decisionrecords.test', 'app.decisionrecords.test')
        assert parse_qs(authorize.query)['redirect_uri'] == [callback_uri]

        # 2. The provider sends the browser back to the website host.
        callback = finish_sign_in(client, provider, 'pat@acme.test', state, base_url=SITE)
        assert callback.status_code == 302
        assert callback.headers['Location'] == provider.default_destination('acme.test').replace(
            APP_BASE, APP_HOST)
        # The code is exchanged with the same redirect_uri that was authorised.
        assert callback.token_request.call_args.kwargs['data']['redirect_uri'] == callback_uri

        # 3. The session cookie is scoped to the parent domain, as configured.
        cookie = parse_set_cookie(callback)
        assert cookie is not None, callback.headers.getlist('Set-Cookie')
        assert cookie['domain'] == COOKIE_DOMAIN
        assert cookie['path'] == '/'
        assert cookie['secure'] is True
        assert cookie['httponly'] is True
        assert cookie['samesite'] == 'Lax'
        assert 'expires' in cookie  # permanent session, not a browser-session cookie

        # 4. The app host receives that cookie and recognises the user.
        me = client.get('/api/user/me', base_url=APP_HOST)
        assert me.status_code == 200, me.get_json()
        assert me.get_json()['email'] == 'pat@acme.test'

        # ...and so does a browser that is handed only the Set-Cookie value.
        fresh = test_app.test_client(use_cookies=False)
        replayed = fresh.get('/api/user/me', base_url=APP_HOST,
                             headers={'Cookie': f"session={cookie['value']}"})
        assert replayed.status_code == 200

        # The cookie jar does scope by domain: another site gets nothing.
        assert client.get('/api/user/me', base_url=OTHER_SITE).status_code == 401

    def test_new_visitor_signing_up_on_website_lands_on_new_tenant(self, handoff_env):
        test_app, install = handoff_env
        provider = install('google')
        client = test_app.test_client()

        _, state = start_sign_in(client, provider, base_url=SITE)
        callback = finish_sign_in(client, provider, 'founder@newco.test', state, base_url=SITE)

        assert callback.status_code == 302
        assert callback.headers['Location'] == f'{APP_HOST}/newco.test'
        me = client.get('/api/user/me', base_url=APP_HOST)
        assert me.status_code == 200
        assert me.get_json()['email'] == 'founder@newco.test'

    def test_return_url_is_resolved_on_the_app_host(self, handoff_env):
        test_app, install = handoff_env
        provider = install('google')
        make_user('pat@acme.test', password=STRONG_PASSWORD)
        client = test_app.test_client()

        _, state = start_sign_in(client, provider, return_url='/acme.test/decisions/7', base_url=SITE)
        callback = finish_sign_in(client, provider, 'pat@acme.test', state, base_url=SITE)

        assert callback.headers['Location'] == f'{APP_HOST}/acme.test/decisions/7'

    @pytest.mark.parametrize('failure', ['missing_code', 'invalid_state', 'provider_error'])
    def test_failed_callback_sets_no_signed_in_session(self, handoff_env, failure):
        test_app, install = handoff_env
        provider = install('google')
        client = test_app.test_client()
        _, state = start_sign_in(client, provider, base_url=SITE)
        query = {
            'missing_code': {'state': state},
            'invalid_state': {'code': 'auth-code', 'state': 'forged'},
            'provider_error': {'error': 'access_denied', 'state': state},
        }[failure]

        callback = client.get(provider.callback, query_string=query, base_url=SITE)

        assert callback.status_code == 302
        assert callback.headers['Location'].startswith('/?error=')
        assert client.get('/api/user/me', base_url=APP_HOST).status_code == 401

    def test_logout_on_app_host_clears_the_shared_cookie(self, handoff_env):
        test_app, install = handoff_env
        provider = install('google')
        make_user('pat@acme.test', password=STRONG_PASSWORD)
        client = test_app.test_client()
        _, state = start_sign_in(client, provider, base_url=SITE)
        finish_sign_in(client, provider, 'pat@acme.test', state, base_url=SITE)
        assert client.get('/api/user/me', base_url=APP_HOST).status_code == 200

        logout = client.post('/api/auth/logout', base_url=APP_HOST)

        assert logout.status_code == 200
        assert logout.get_json()['redirect_url'] == SITE
        assert any(
            header.startswith('session=;') and f'Domain={COOKIE_DOMAIN}' in header
            for header in logout.headers.getlist('Set-Cookie')
        ), logout.headers.getlist('Set-Cookie')
        assert client.get('/api/user/me', base_url=APP_HOST).status_code == 401
        assert client.get('/api/user/me', base_url=SITE).status_code == 401


class TestHandoffNeedsSharedCookieDomain:
    """Documents why SESSION_COOKIE_DOMAIN must be set when the hosts differ."""

    def test_without_cookie_domain_the_app_host_is_not_signed_in(self, monkeypatch):
        with website_handoff_app(
            secret_key='test-secret-key-website-handoff',
            cookie_domain=None,
            oauth_base_url=SITE,
            app_base_url=APP_HOST,
        ) as (_, test_app):
            provider = PROVIDER_FACTORIES['google']().install(monkeypatch)
            make_user('pat@acme.test', password=STRONG_PASSWORD)
            client = test_app.test_client()

            _, state = start_sign_in(client, provider, base_url=SITE)
            callback = finish_sign_in(client, provider, 'pat@acme.test', state, base_url=SITE)

            cookie = parse_set_cookie(callback)
            assert cookie is not None
            assert 'domain' not in cookie
            assert callback.headers['Location'] == f'{APP_HOST}/acme.test'
            # Host-only cookie: valid on the website host, absent on the app host.
            assert client.get('/api/user/me', base_url=SITE).status_code == 200
            assert client.get('/api/user/me', base_url=APP_HOST).status_code == 401
