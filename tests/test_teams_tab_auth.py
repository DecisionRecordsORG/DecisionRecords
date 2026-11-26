"""
The Teams tab only gets a `TabAuth` token for a validated Teams sign-in token.

Everything here goes through the real routes of the real app. Teams sign-in
tokens are signed with a key generated in the test, and the download of
Microsoft's signing keys is replaced by that key's public half, so the
signature, audience, issuer, expiry and claim checks all run for real.

Private functions these tests rely on (documented signatures):
- ee.backend.oauth_providers.microsoft_oauth.validate_teams_sso_token(token, expected_audience=None),
  where expected_audience is the Teams app's application ID
- ee.backend.oauth_providers.microsoft_oauth.clear_credential_cache()
- ee.backend.teams.teams_security.get_teams_bot_app_id()
- ee.backend.teams.teams_security.generate_tab_auth_token(user_id, tenant_domain, user_email)
- ee.backend.teams.teams_security.verify_tab_auth_token(token)
- ee.backend.teams.teams_security.validate_teams_jwt(auth_header, service_url=None)
"""
import base64
import hashlib
import hmac
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    db, User, Tenant, TenantMembership, Space, DecisionSpace, ArchitectureDecision,
    GlobalRole, MaturityState, TeamsWorkspace, TeamsUserMapping
)
from tests.app_test_utils import load_test_app

# Enterprise Edition imports - skip tests if not available
try:
    import jwt
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from ee.backend.oauth_providers import microsoft_oauth
    from ee.backend.teams import teams_security
    EE_AVAILABLE = True
except ImportError:
    EE_AVAILABLE = False

EE_TESTS_ENABLED = EE_AVAILABLE and os.environ.get('DECISION_RECORDS_EDITION', 'community') == 'enterprise'
pytestmark = pytest.mark.skipif(
    not EE_TESTS_ENABLED,
    reason="Enterprise Edition tests require DECISION_RECORDS_EDITION=enterprise and EE modules",
)

APP_ID = '11111111-2222-4333-8444-555555555555'
MS_TENANT_A = 'aaaaaaaa-0000-4000-8000-000000000001'
MS_TENANT_B = 'bbbbbbbb-0000-4000-8000-000000000002'
MS_TENANT_UNKNOWN = 'cccccccc-0000-4000-8000-000000000003'
DOMAIN_A = 'acme.test'
DOMAIN_B = 'globex.test'
ALICE = f'alice@{DOMAIN_A}'
BOB = f'bob@{DOMAIN_B}'
APP_HOST = 'app.example.test'
SITE_HOST = 'example.test'
KID = 'test-signing-key'


# ============================================================================
# SIGNING KEYS AND TOKENS
# ============================================================================

def _new_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _pem(private_key):
    return private_key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())


def _public_pem(private_key):
    return private_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)


def _b64(data):
    if isinstance(data, dict):
        data = json.dumps(data, separators=(',', ':')).encode()
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()


if EE_AVAILABLE:
    MICROSOFT_KEY = _new_key()
    OTHER_KEY = _new_key()


def sso_claims(username=ALICE, *, tid=MS_TENANT_A, oid='oid-alice', **overrides):
    now = int(time.time())
    claims = {
        'aud': APP_ID,
        'iss': f'https://login.microsoftonline.com/{tid}/v2.0',
        'iat': now - 10,
        'nbf': now - 10,
        'exp': now + 600,
        'oid': oid,
        'tid': tid,
        'name': 'Alice Example',
        'preferred_username': username,
        'ver': '2.0',
        'scp': 'access_as_user',
    }
    claims.update(overrides)
    return {name: value for name, value in claims.items() if value is not None}


def sso_token(username=ALICE, *, key=None, **claims):
    return jwt.encode(sso_claims(username, **claims), _pem(key or MICROSOFT_KEY),
                      algorithm='RS256', headers={'kid': KID})


def unsigned_token(username=ALICE):
    return f"{_b64({'alg': 'none', 'typ': 'JWT', 'kid': KID})}.{_b64(sso_claims(username))}."


def hmac_token_keyed_with_public_key(username=ALICE):
    signing_input = f"{_b64({'alg': 'HS256', 'typ': 'JWT', 'kid': KID})}.{_b64(sso_claims(username))}"
    signature = hmac.new(_public_pem(MICROSOFT_KEY), signing_input.encode(), hashlib.sha256).digest()
    return f'{signing_input}.{_b64(signature)}'


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def real_app(monkeypatch):
    import feature_flags
    monkeypatch.setenv('APP_BASE_URL', f'https://{APP_HOST}')
    monkeypatch.setenv('OAUTH_BASE_URL', f'https://{SITE_HOST}')
    app_module, test_app = load_test_app(secret_key='test-secret-key-teams-tab')
    monkeypatch.setitem(feature_flags.FEATURES, 'teams_integration', True)
    monkeypatch.setattr(teams_security, 'get_teams_bot_app_id', lambda: APP_ID)

    # Microsoft's signing keys are "downloaded" from the key generated above
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(MICROSOFT_KEY.public_key(), as_dict=True)
    jwk.update({'kid': KID, 'use': 'sig', 'alg': 'RS256'})
    monkeypatch.setattr(jwt.PyJWKClient, 'fetch_data', lambda self: {'keys': [jwk]})
    microsoft_oauth.clear_credential_cache()

    with test_app.app_context():
        db.create_all()
        app_module.init_database()
        yield app_module, test_app
        db.session.remove()
        db.drop_all()
        app_module._db_initialized = False
    microsoft_oauth.clear_credential_cache()


@pytest.fixture
def client(real_app):
    _, test_app = real_app
    return test_app.test_client()


def make_org(domain, ms_tenant_id=None, *, members=()):
    """A tenant with a default space, optionally connected to a Microsoft 365 tenant."""
    tenant = Tenant(domain=domain, name=domain, status='active',
                    maturity_state=MaturityState.BOOTSTRAP)
    db.session.add(tenant)
    db.session.flush()
    db.session.add(Space(tenant_id=tenant.id, name=f'General {domain}', is_default=True))
    if ms_tenant_id:
        db.session.add(TeamsWorkspace(
            tenant_id=tenant.id, ms_tenant_id=ms_tenant_id,
            status=TeamsWorkspace.STATUS_ACTIVE, is_active=True))
    for email in members:
        user = User(email=email, sso_domain=domain, auth_type='local', email_verified=True)
        user.set_name(first_name='Org', last_name='Member')
        db.session.add(user)
        db.session.flush()
        db.session.add(TenantMembership(user_id=user.id, tenant_id=tenant.id,
                                        global_role=GlobalRole.USER))
    db.session.commit()
    return tenant


def make_decision(tenant, title, owner_email=None):
    owner = User.query.filter_by(email=owner_email).first() if owner_email else None
    number = ArchitectureDecision.query.filter_by(tenant_id=tenant.id).count() + 1
    decision = ArchitectureDecision(
        tenant_id=tenant.id, domain=tenant.domain, decision_number=number, title=title,
        status='accepted', context='context', decision='decision', consequences='consequences',
        created_by_id=owner.id if owner else None, owner_id=owner.id if owner else None)
    db.session.add(decision)
    db.session.commit()
    return decision


@pytest.fixture
def two_orgs(real_app):
    tenant_a = make_org(DOMAIN_A, MS_TENANT_A, members=[ALICE])
    tenant_b = make_org(DOMAIN_B, MS_TENANT_B, members=[BOB])
    make_decision(tenant_a, 'Acme decision', ALICE)
    make_decision(tenant_b, 'Globex decision', BOB)
    return tenant_a, tenant_b


def row_counts():
    return {
        'users': User.query.count(),
        'tenants': Tenant.query.count(),
        'memberships': TenantMembership.query.count(),
        'workspaces': TeamsWorkspace.query.count(),
        'mappings': TeamsUserMapping.query.count(),
        'decisions': ArchitectureDecision.query.count(),
    }


def tab_headers(token):
    return {'Authorization': f'TabAuth {token}'}


def tab_token_for(email):
    user = User.query.filter_by(email=email).first()
    return teams_security.generate_tab_auth_token(user.id, user.sso_domain, user.email)


def sign_in(client, token):
    """Exchange a Teams sign-in token for a tab token through the documented endpoint."""
    return client.post('/api/teams/sso/validate', json={'token': token})


def provision(client, token=None, body=None):
    headers = {'Authorization': f'Bearer {token}'} if token else {}
    return client.post('/api/teams/tab/provision', json=body or {}, headers=headers)


def no_token_in(response):
    body = response.get_json(silent=True) or {}
    return not body.get('tabAuthToken') and not body.get('tab_auth_token')


# ============================================================================
# AN IDENTITY IN THE REQUEST BODY IS NOT A SIGN-IN
# ============================================================================

class TestProvisionNeedsAValidatedSignInToken:

    def body_naming(self, email, ms_tenant_id=MS_TENANT_A):
        return {
            'aadObjectId': 'made-up-object-id',
            'userPrincipalName': email,
            'displayName': 'Somebody',
            'msTenantId': ms_tenant_id,
        }

    def test_request_naming_an_existing_user_gets_no_token(self, client, two_orgs):
        before = row_counts()

        response = provision(client, body=self.body_naming(ALICE))

        assert response.status_code == 401, response.get_data(as_text=True)
        assert 'error' in response.get_json()
        assert no_token_in(response)
        assert row_counts() == before

    def test_request_naming_an_existing_user_cannot_read_that_organisations_decisions(
            self, client, two_orgs):
        response = provision(client, body=self.body_naming(ALICE))
        body = response.get_json(silent=True) or {}
        token = body.get('tabAuthToken') or 'no-token-was-issued'

        listing = client.get('/api/teams/tab/decisions', headers=tab_headers(token))

        assert listing.status_code == 401, listing.get_data(as_text=True)
        assert 'Acme decision' not in listing.get_data(as_text=True)

    def test_request_naming_a_new_user_creates_no_account(self, client, two_orgs):
        before = row_counts()

        response = provision(client, body=self.body_naming(f'newcomer@{DOMAIN_A}'))

        assert response.status_code == 401
        assert row_counts() == before
        assert User.query.filter_by(email=f'newcomer@{DOMAIN_A}').first() is None

    def test_request_for_an_unlinked_workspace_creates_no_tenant(self, client, two_orgs):
        db.session.add(TeamsWorkspace(ms_tenant_id=MS_TENANT_UNKNOWN,
                                      status=TeamsWorkspace.STATUS_PENDING_CONSENT, is_active=True))
        db.session.commit()
        before = row_counts()

        response = provision(client, body=self.body_naming('founder@newcorp.test', MS_TENANT_UNKNOWN))

        assert response.status_code == 401
        assert row_counts() == before
        assert Tenant.query.filter_by(domain='newcorp.test').first() is None
        assert db.session.get(TeamsWorkspace, TeamsWorkspace.query.filter_by(
            ms_tenant_id=MS_TENANT_UNKNOWN).first().id).tenant_id is None

    @pytest.mark.parametrize('authorization', [
        'Bearer', 'Bearer ', 'Bearer not-a-token', 'Basic YWxpY2U6cGFzcw==', 'TabAuth abc',
    ])
    def test_malformed_authorization_is_refused(self, client, two_orgs, authorization):
        before = row_counts()

        response = client.post('/api/teams/tab/provision', json=self.body_naming(ALICE),
                               headers={'Authorization': authorization})

        assert response.status_code == 401
        assert no_token_in(response)
        assert row_counts() == before

    def test_body_fields_do_not_change_who_a_valid_token_signs_in(self, client, two_orgs):
        response = provision(client, sso_token(ALICE), body=self.body_naming(BOB, MS_TENANT_B))

        assert response.status_code == 200, response.get_data(as_text=True)
        body = response.get_json()
        assert body['success'] is True
        assert body['user']['email'] == ALICE
        assert body['tenantDomain'] == DOMAIN_A
        listing = client.get('/api/teams/tab/decisions', headers=tab_headers(body['tabAuthToken']))
        assert [d['title'] for d in listing.get_json()] == ['Acme decision']


# ============================================================================
# TEAMS SIGN-IN TOKEN VALIDATION
# ============================================================================

def _refused_tokens():
    past = int(time.time()) - 3600
    future = int(time.time()) + 3600
    return {
        'wrong audience': lambda: sso_token(aud='99999999-0000-4000-8000-000000000000'),
        'audience of another host': lambda: sso_token(aud=f'api://elsewhere.test/{APP_ID}'),
        'audience URI of another application': lambda: sso_token(aud=f'api://{SITE_HOST}/{APP_ID}-other'),
        'botid audience without a host': lambda: sso_token(aud=f'api://botid-{APP_ID}'),
        'no issued-at time': lambda: sso_token(iat=None),
        'issuer that is not Microsoft': lambda: sso_token(iss='https://login.example.test/common/v2.0'),
        'issuer without a tenant': lambda: sso_token(iss='https://login.microsoftonline.com/common/v2.0'),
        'tenant mismatch between issuer and tid': lambda: sso_token(
            iss=f'https://login.microsoftonline.com/{MS_TENANT_B}/v2.0'),
        'expired': lambda: sso_token(iat=past - 600, nbf=past - 600, exp=past),
        'not yet valid': lambda: sso_token(nbf=future, exp=future + 600),
        'no expiry': lambda: sso_token(exp=None),
        'unsigned': unsigned_token,
        'signed with a shared secret': hmac_token_keyed_with_public_key,
        'signed by another key': lambda: sso_token(key=OTHER_KEY),
        'missing oid': lambda: sso_token(oid=None),
        'missing tid': lambda: sso_token(tid=None, iss=f'https://login.microsoftonline.com/{MS_TENANT_A}/v2.0'),
        'no username, unverified email': lambda: sso_token(preferred_username=None, email=ALICE),
        'username that is not an address': lambda: sso_token(preferred_username='alice'),
        'not a token': lambda: 'not-a-token',
    }


REFUSED = sorted(_refused_tokens()) if EE_AVAILABLE else []

# Tokens Microsoft's signature, audience, issuer and validity checks all pass
# for, which the route still refuses because the verified claims do not name
# an account. Every other case is refused by the token validator itself.
REFUSED_BY_THE_ROUTE = {'no username, unverified email', 'username that is not an address'}


class TestSignInTokenValidation:

    def test_valid_token_signs_in_and_the_tab_token_works(self, client, two_orgs):
        response = sign_in(client, sso_token(ALICE))

        assert response.status_code == 200, response.get_data(as_text=True)
        body = response.get_json()
        assert body['valid'] is True
        assert body['tenant_domain'] == DOMAIN_A
        assert body['user']['email'] == ALICE
        assert body['user']['id'] == User.query.filter_by(email=ALICE).first().id
        listing = client.get('/api/teams/tab/decisions', headers=tab_headers(body['tab_auth_token']))
        assert listing.status_code == 200
        assert [d['title'] for d in listing.get_json()] == ['Acme decision']

    def test_first_sign_in_of_a_new_colleague_creates_the_account_in_their_organisation(
            self, client, two_orgs):
        newcomer = f'newcomer@{DOMAIN_A}'

        response = sign_in(client, sso_token(newcomer.upper().replace('@ACME.TEST', '@Acme.Test'),
                                             oid='oid-newcomer'))

        assert response.status_code == 200, response.get_data(as_text=True)
        user = User.query.filter_by(email=newcomer).first()
        assert user is not None
        assert user.sso_domain == DOMAIN_A
        tenant = Tenant.query.filter_by(domain=DOMAIN_A).first()
        assert TenantMembership.query.filter_by(user_id=user.id, tenant_id=tenant.id).count() == 1
        assert response.get_json()['tenant_domain'] == DOMAIN_A

    @pytest.mark.parametrize('audience', [
        APP_ID,
        APP_ID.upper(),
        f'api://{APP_ID}',
        f'api://{SITE_HOST}/{APP_ID}',
        f'api://{SITE_HOST}/botid-{APP_ID}',
        f'api://{APP_HOST}/{APP_ID}',
        f'api://{APP_HOST}/botid-{APP_ID}',
    ])
    def test_accepted_audience_forms(self, client, two_orgs, audience):
        response = sign_in(client, sso_token(aud=audience))

        assert response.status_code == 200, response.get_data(as_text=True)

    def test_audience_host_comes_from_configuration_not_from_the_request(self, client, two_orgs):
        response = client.post(
            '/api/teams/sso/validate',
            json={'token': sso_token(aud=f'api://elsewhere.test/{APP_ID}')},
            headers={'Host': 'elsewhere.test'})

        assert response.status_code == 401
        assert no_token_in(response)

    @pytest.mark.parametrize('case', REFUSED)
    @pytest.mark.parametrize('endpoint', ['sso/validate', 'tab/provision'])
    def test_refused_tokens(self, real_app, client, two_orgs, endpoint, case):
        token = _refused_tokens()[case]()
        before = row_counts()
        _, test_app = real_app
        with test_app.test_request_context('/'):
            verified = microsoft_oauth.validate_teams_sso_token(token, expected_audience=APP_ID)
        assert (verified is None) == (case not in REFUSED_BY_THE_ROUTE)

        response = sign_in(client, token) if endpoint == 'sso/validate' else provision(client, token)

        assert response.status_code == 401, response.get_data(as_text=True)
        assert 'error' in response.get_json()
        assert no_token_in(response)
        assert row_counts() == before

    def test_verified_email_claim_is_accepted_when_there_is_no_username(self, client, two_orgs):
        response = sign_in(client, sso_token(preferred_username=None, email=ALICE, xms_edov=True))

        assert response.status_code == 200, response.get_data(as_text=True)
        assert response.get_json()['user']['email'] == ALICE

    def test_username_wins_over_an_email_claim_naming_someone_else(self, client, two_orgs):
        make_org('initech.test', members=['carol@initech.test'])

        response = sign_in(client, sso_token(ALICE, email='carol@initech.test'))

        assert response.status_code == 200
        assert response.get_json()['user']['email'] == ALICE
        assert response.get_json()['tenant_domain'] == DOMAIN_A

    def test_key_download_failure_refuses_the_sign_in(self, client, two_orgs, monkeypatch):
        def unreachable(self):
            raise jwt.PyJWKClientError('signing keys unavailable')
        monkeypatch.setattr(jwt.PyJWKClient, 'fetch_data', unreachable)
        before = row_counts()

        response = sign_in(client, sso_token(ALICE))

        assert response.status_code == 401
        assert no_token_in(response)
        assert row_counts() == before

    def test_missing_app_id_refuses_the_sign_in(self, client, two_orgs, monkeypatch):
        monkeypatch.setattr(teams_security, 'get_teams_bot_app_id', lambda: None)

        response = sign_in(client, sso_token(ALICE))

        assert response.status_code == 503
        assert no_token_in(response)

    def test_missing_token_is_a_bad_request(self, client, two_orgs):
        assert client.post('/api/teams/sso/validate', json={}).status_code == 400
        assert client.post('/api/teams/sso/validate', json={'token': {'a': 1}}).status_code == 400
        assert client.post('/api/teams/sso/validate', data='x',
                           content_type='text/plain').status_code == 400

    def test_token_from_another_microsoft_tenant_cannot_enter_a_connected_organisation(
            self, client, two_orgs):
        """Acme connected Microsoft tenant A; a token from tenant B naming an Acme address is refused."""
        before = row_counts()

        response = sign_in(client, sso_token(f'intruder@{DOMAIN_A}', tid=MS_TENANT_B, oid='oid-x'))

        assert response.status_code == 403, response.get_data(as_text=True)
        assert no_token_in(response)
        assert row_counts() == before

    def test_personal_mail_domains_are_refused(self, client, two_orgs):
        before = row_counts()

        response = sign_in(client, sso_token('someone@gmail.com', tid=MS_TENANT_UNKNOWN))

        assert response.status_code == 403
        assert no_token_in(response)
        assert row_counts() == before


# ============================================================================
# TAB TOKEN: SIGNATURE, EXPIRY, USER AND TENANT BINDING
# ============================================================================

TAB_ROUTES = [
    ('get', '/api/teams/tab/decisions'),
    ('get', '/api/teams/tab/decisions/1'),
    ('get', '/api/teams/tab/spaces'),
    ('post', '/api/teams/tab/decisions'),
]


class TestTabTokenCheck:

    def call(self, client, method, path, headers):
        kwargs = {'json': {'title': 'From a refused request'}} if method == 'post' else {}
        return getattr(client, method)(path, headers=headers, **kwargs)

    @pytest.mark.parametrize('method,path', TAB_ROUTES)
    def test_no_token_is_refused(self, client, two_orgs, method, path):
        before = row_counts()

        assert self.call(client, method, path, {}).status_code == 401
        assert row_counts() == before

    @pytest.mark.parametrize('method,path', TAB_ROUTES)
    def test_altered_token_is_refused(self, client, two_orgs, method, path):
        token = tab_token_for(ALICE)
        altered = token[:-6] + ('AAAAAA' if not token.endswith('AAAAAA') else 'BBBBBB')

        assert self.call(client, method, path, tab_headers(altered)).status_code == 401

    @pytest.mark.parametrize('method,path', TAB_ROUTES)
    def test_expired_token_is_refused(self, client, two_orgs, monkeypatch, method, path):
        token = tab_token_for(ALICE)

        class Tomorrow(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime.now(tz) + timedelta(hours=24, minutes=1)
        monkeypatch.setattr(teams_security, 'datetime', Tomorrow)

        assert self.call(client, method, path, tab_headers(token)).status_code == 401

    @pytest.mark.parametrize('method,path', TAB_ROUTES)
    def test_token_of_another_kind_is_refused(self, client, two_orgs, method, path):
        # Another kind of token this module signs with the same key: a sign-in state
        other_kind = teams_security.generate_teams_oidc_state(return_url='/')

        assert self.call(client, method, path, tab_headers(other_kind)).status_code == 401

    @pytest.mark.parametrize('method,path', TAB_ROUTES)
    def test_sign_in_token_is_not_a_tab_token(self, client, two_orgs, method, path):
        headers = {'Authorization': f'Bearer {sso_token(ALICE)}'}

        assert self.call(client, method, path, headers).status_code == 401
        assert self.call(client, method, path, tab_headers(sso_token(ALICE))).status_code == 401

    def test_token_for_a_removed_account_is_refused(self, client, two_orgs):
        token = teams_security.generate_tab_auth_token(987654, DOMAIN_A, 'ghost@acme.test')

        assert client.get('/api/teams/tab/decisions', headers=tab_headers(token)).status_code == 401

    def test_token_for_an_anonymized_account_is_refused(self, client, two_orgs):
        token = tab_token_for(ALICE)
        User.query.filter_by(email=ALICE).first().is_anonymized = True
        db.session.commit()

        assert client.get('/api/teams/tab/decisions', headers=tab_headers(token)).status_code == 401

    def test_token_stops_working_when_the_user_no_longer_belongs_to_its_tenant(
            self, client, two_orgs):
        token = tab_token_for(ALICE)
        alice = User.query.filter_by(email=ALICE).first()
        alice.sso_domain = DOMAIN_B
        db.session.commit()

        response = client.get('/api/teams/tab/decisions', headers=tab_headers(token))

        assert response.status_code == 401
        assert 'Globex decision' not in response.get_data(as_text=True)

    def test_token_naming_a_tenant_the_user_does_not_belong_to_is_refused(self, client, two_orgs):
        alice = User.query.filter_by(email=ALICE).first()
        token = teams_security.generate_tab_auth_token(alice.id, DOMAIN_B, alice.email)

        for method, path in TAB_ROUTES:
            assert self.call(client, method, path, tab_headers(token)).status_code == 401


class TestTabRoutesStayInsideTheTokensTenant:

    def test_list_shows_only_the_tokens_tenant(self, client, two_orgs):
        response = client.get('/api/teams/tab/decisions', headers=tab_headers(tab_token_for(ALICE)))

        assert response.status_code == 200
        assert [d['title'] for d in response.get_json()] == ['Acme decision']

    def test_decision_of_another_tenant_cannot_be_read_by_id(self, client, two_orgs):
        own = ArchitectureDecision.query.filter_by(domain=DOMAIN_A).first()
        foreign = ArchitectureDecision.query.filter_by(domain=DOMAIN_B).first()
        headers = tab_headers(tab_token_for(ALICE))

        assert client.get(f'/api/teams/tab/decisions/{own.id}', headers=headers).status_code == 200
        response = client.get(f'/api/teams/tab/decisions/{foreign.id}', headers=headers)

        assert response.status_code == 404
        assert 'Globex decision' not in response.get_data(as_text=True)
        # The same answer as for an ID that does not exist
        missing = client.get('/api/teams/tab/decisions/999999', headers=headers)
        assert missing.status_code == 404
        assert missing.get_json() == response.get_json()

    def test_every_decision_id_outside_the_tenant_is_refused(self, client, two_orgs):
        tenant_b = Tenant.query.filter_by(domain=DOMAIN_B).first()
        for index in range(5):
            make_decision(tenant_b, f'Globex secret {index}', BOB)
        headers = tab_headers(tab_token_for(ALICE))
        own_ids = {d.id for d in ArchitectureDecision.query.filter_by(domain=DOMAIN_A)}

        for decision_id in range(1, 12):
            response = client.get(f'/api/teams/tab/decisions/{decision_id}', headers=headers)
            assert response.status_code == (200 if decision_id in own_ids else 404)
            assert 'Globex' not in response.get_data(as_text=True)

    def test_deleted_decision_is_not_returned(self, client, two_orgs):
        own = ArchitectureDecision.query.filter_by(domain=DOMAIN_A).first()
        own.deleted_at = datetime.now(timezone.utc)
        db.session.commit()

        response = client.get(f'/api/teams/tab/decisions/{own.id}',
                              headers=tab_headers(tab_token_for(ALICE)))

        assert response.status_code == 404

    def test_spaces_are_those_of_the_tokens_tenant(self, client, two_orgs):
        response = client.get('/api/teams/tab/spaces', headers=tab_headers(tab_token_for(ALICE)))

        assert response.status_code == 200
        assert [s['name'] for s in response.get_json()['spaces']] == [f'General {DOMAIN_A}']

    def test_create_lands_in_the_tokens_tenant_whatever_the_body_says(self, client, two_orgs):
        tenant_a, tenant_b = two_orgs
        foreign_space = Space.query.filter_by(tenant_id=tenant_b.id).first()
        bob = User.query.filter_by(email=BOB).first()

        response = client.post('/api/teams/tab/decisions', headers=tab_headers(tab_token_for(ALICE)), json={
            'title': 'Written by Alice',
            'tenant_id': tenant_b.id,
            'domain': DOMAIN_B,
            'tenant_domain': DOMAIN_B,
            'owner_id': bob.id,
            'created_by_id': bob.id,
            'space_id': foreign_space.id,
        })

        assert response.status_code == 201, response.get_data(as_text=True)
        created = db.session.get(ArchitectureDecision, response.get_json()['decision']['id'])
        alice = User.query.filter_by(email=ALICE).first()
        assert (created.tenant_id, created.domain) == (tenant_a.id, DOMAIN_A)
        assert (created.created_by_id, created.owner_id) == (alice.id, alice.id)
        assert DecisionSpace.query.filter_by(decision_id=created.id).count() == 0
        assert ArchitectureDecision.query.filter_by(domain=DOMAIN_B).count() == 1
        bob_view = client.get('/api/teams/tab/decisions', headers=tab_headers(tab_token_for(BOB)))
        assert [d['title'] for d in bob_view.get_json()] == ['Globex decision']

    def test_create_links_a_space_of_the_tokens_tenant(self, client, two_orgs):
        tenant_a, _ = two_orgs
        own_space = Space.query.filter_by(tenant_id=tenant_a.id).first()

        response = client.post('/api/teams/tab/decisions', headers=tab_headers(tab_token_for(ALICE)),
                               json={'title': 'In a space', 'space_id': own_space.id})

        assert response.status_code == 201
        decision_id = response.get_json()['decision']['id']
        assert DecisionSpace.query.filter_by(decision_id=decision_id, space_id=own_space.id).count() == 1


# ============================================================================
# OTHER TEAMS ROUTES
# ============================================================================

class TestOtherTeamsRoutesNeedProof:

    def test_webhook_without_a_bot_framework_token_is_refused(self, client, two_orgs):
        before = row_counts()

        response = client.post('/api/teams/webhook', json={
            'type': 'installationUpdate', 'action': 'add', 'serviceUrl': 'https://example.test/',
            'channelData': {'tenant': {'id': MS_TENANT_UNKNOWN}},
        })

        assert response.status_code == 401
        assert row_counts() == before

    SERVICE_URL = 'https://smba.example.test/emea/'

    def bot_framework_token(self, **overrides):
        now = int(time.time())
        claims = {
            'iss': 'https://api.botframework.com',
            'aud': APP_ID,
            'iat': now - 10,
            'nbf': now - 10,
            'exp': now + 600,
            'serviceurl': self.SERVICE_URL,
        }
        claims.update(overrides)
        claims = {name: value for name, value in claims.items() if value is not None}
        return jwt.encode(claims, _pem(MICROSOFT_KEY),
                          algorithm='RS256', headers={'kid': KID})

    def install(self, client, monkeypatch, token, service_url=None):
        """Deliver a bot installation activity; a workspace row appears only when it is accepted."""
        # The Bot Framework key set is "downloaded" from the key generated in this file
        monkeypatch.setattr(teams_security, '_get_jwks_client',
                            lambda: jwt.PyJWKClient('https://keys.invalid/bot-framework'))
        return client.post(
            '/api/teams/webhook',
            headers={'Authorization': f'Bearer {token}'},
            json={'type': 'installationUpdate', 'action': 'add', 'channelId': 'msteams',
                  'serviceUrl': service_url or self.SERVICE_URL,
                  'channelData': {'tenant': {'id': MS_TENANT_UNKNOWN}}})

    def installed(self):
        return TeamsWorkspace.query.filter_by(ms_tenant_id=MS_TENANT_UNKNOWN).count() == 1

    def test_webhook_accepts_a_token_bound_to_the_activitys_service_url(self, client, two_orgs, monkeypatch):
        response = self.install(client, monkeypatch, self.bot_framework_token())

        assert response.status_code == 200, response.get_data(as_text=True)
        assert self.installed()

    @pytest.mark.parametrize('case,claims', [
        ('service URL of another activity', {'serviceurl': 'https://elsewhere.test/emea/'}),
        ('no service URL claim', {'serviceurl': None}),
        ('issuer that is not the Bot Framework', {'iss': f'https://login.microsoftonline.com/{MS_TENANT_A}/v2.0'}),
        ('another audience', {'aud': '99999999-0000-4000-8000-000000000000'}),
        ('expired', {'exp': 1000000000}),
    ])
    def test_webhook_refuses(self, client, two_orgs, monkeypatch, case, claims):
        before = row_counts()

        response = self.install(client, monkeypatch, self.bot_framework_token(**claims))

        assert response.status_code == 401, response.get_data(as_text=True)
        assert not self.installed()
        assert row_counts() == before

    def test_webhook_refuses_a_valid_token_replayed_with_another_service_url(
            self, client, two_orgs, monkeypatch):
        before = row_counts()

        response = self.install(client, monkeypatch, self.bot_framework_token(),
                                service_url='https://elsewhere.test/emea/')

        assert response.status_code == 401
        assert row_counts() == before

    def test_webhook_refuses_a_token_signed_by_another_key(self, client, two_orgs, monkeypatch):
        now = int(time.time())
        token = jwt.encode({'iss': 'https://api.botframework.com', 'aud': APP_ID, 'exp': now + 600,
                            'serviceurl': self.SERVICE_URL},
                           _pem(OTHER_KEY), algorithm='RS256', headers={'kid': KID})

        response = self.install(client, monkeypatch, token)

        assert response.status_code == 401
        assert not self.installed()

    def test_webhook_passes_the_activitys_service_url_to_the_validator(self, client, two_orgs, monkeypatch):
        seen = {}

        def validator(auth_header, service_url=None):
            seen['service_url'] = service_url
            return None
        monkeypatch.setattr(teams_security, 'validate_teams_jwt', validator)

        response = client.post('/api/teams/webhook', headers={'Authorization': 'Bearer x'},
                               json={'type': 'message', 'serviceUrl': self.SERVICE_URL})

        assert response.status_code == 401
        assert seen == {'service_url': self.SERVICE_URL}

    def test_webhook_works_with_a_validator_that_takes_only_the_header(self, client, two_orgs, monkeypatch):
        """The Enterprise module released before the service URL check has this signature."""
        monkeypatch.setattr(teams_security, 'validate_teams_jwt', lambda auth_header: None)

        response = client.post('/api/teams/webhook', headers={'Authorization': 'Bearer x'},
                               json={'type': 'message', 'serviceUrl': self.SERVICE_URL})

        assert response.status_code == 401

    def test_webhook_refuses_when_the_signing_keys_cannot_be_fetched(self, client, two_orgs, monkeypatch):
        def unreachable():
            raise RuntimeError('signing keys unavailable')
        monkeypatch.setattr(teams_security, '_get_jwks_client', unreachable)
        before = row_counts()

        response = client.post(
            '/api/teams/webhook',
            headers={'Authorization': f'Bearer {sso_token(ALICE)}'},
            json={'type': 'installationUpdate', 'action': 'add', 'serviceUrl': 'https://example.test/',
                  'channelData': {'tenant': {'id': MS_TENANT_UNKNOWN}}})

        assert response.status_code == 401
        assert row_counts() == before

    @pytest.mark.parametrize('method,path', [
        ('get', '/api/teams/oauth/start'),
        ('get', '/api/teams/settings'),
        ('put', '/api/teams/settings'),
        ('post', '/api/teams/disconnect'),
        ('get', '/api/teams/channels'),
        ('post', '/api/teams/test'),
    ])
    def test_workspace_administration_needs_a_session(self, client, two_orgs, method, path):
        response = getattr(client, method)(path, json={'default_channel_id': 'x'} if method != 'get' else None)

        assert response.status_code == 401

    def test_consent_callback_without_valid_state_connects_nothing(self, client, two_orgs):
        before = row_counts()
        tenant_a, _ = two_orgs

        response = client.get(f'/api/teams/oauth/callback?tenant={MS_TENANT_UNKNOWN}&state=forged')

        assert response.status_code == 302
        assert 'teams_error=invalid_state' in response.headers['Location']
        assert row_counts() == before

    @pytest.mark.parametrize('method,path', [
        ('get', '/api/teams/link/initiate?token=x'),
        ('post', '/api/teams/link/validate'),
        ('post', '/api/teams/link/complete'),
    ])
    def test_the_account_linking_routes_are_gone(self, client, two_orgs, method, path):
        """S10: nothing issued link tokens any more, so the routes were removed."""
        before = row_counts()

        response = getattr(client, method)(path, json={'token': 'anything'} if method == 'post' else None)

        assert response.status_code in (404, 405)
        assert row_counts() == before
