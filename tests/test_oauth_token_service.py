"""
Tests for the OAuth token and grant service (Enterprise Edition):
ee/backend/oauth_server/service.py with pkce.py and scopes.py.

Covers the life of a connection: request, the user's decision, the code
exchange (PKCE, single use, binding to client, redirect URI and resource),
access token validation (audience, expiry, the owner's place in the
organisation), refresh with rotation and reuse detection, and revocation.
Nothing here is reachable over HTTP yet; the endpoints come later.

Note: These tests require Enterprise Edition modules from ee/backend/oauth_server/
"""
import base64
import hashlib
import os
import sys
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    db, AuditLog, GlobalRole, MaturityState, OAuthAuthorizationRequest, OAuthClient, OAuthGrant,
    OAuthToken, Tenant, TenantMembership, User,
)

try:
    from ee.backend.oauth_server import pkce, scopes, service, settings
    from ee.backend.oauth_server.errors import OAuthError
    EE_AVAILABLE = True
except ImportError:
    EE_AVAILABLE = False
    pkce = scopes = service = settings = None
    OAuthError = Exception

EE_TESTS_ENABLED = EE_AVAILABLE and os.environ.get('DECISION_RECORDS_EDITION', 'community') == 'enterprise'
pytestmark = pytest.mark.skipif(
    not EE_TESTS_ENABLED,
    reason="Enterprise Edition tests require DECISION_RECORDS_EDITION=enterprise and EE modules",
)

NOW = datetime(2026, 11, 25, 12, 0, 0)
RESOURCE = 'https://decisions.example/api/mcp'
CLIENT_ID = 'https://client.example/oauth/client.json'
REDIRECT = 'https://client.example/callback'
VERIFIER = 'v' * 64
CHALLENGE = base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).rstrip(b'=').decode()


def _error(excinfo):
    return excinfo.value.error


@pytest.fixture
def world(app):
    tenant = Tenant(domain='example.com', name='Example', status='active', maturity_state=MaturityState.BOOTSTRAP)
    other_tenant = Tenant(domain='other.org', name='Other', status='active', maturity_state=MaturityState.BOOTSTRAP)
    db.session.add_all([tenant, other_tenant])
    db.session.flush()
    user = User(email='person@example.com', sso_domain='example.com', auth_type='local', email_verified=True)
    colleague = User(email='colleague@example.com', sso_domain='example.com', auth_type='local', email_verified=True)
    db.session.add_all([user, colleague])
    db.session.flush()
    membership = TenantMembership(user_id=user.id, tenant_id=tenant.id, global_role=GlobalRole.USER)
    db.session.add_all([
        membership,
        TenantMembership(user_id=colleague.id, tenant_id=tenant.id, global_role=GlobalRole.ADMIN),
    ])
    client = OAuthClient(client_id=CLIENT_ID, client_name='Example Client',
                         redirect_uris=[REDIRECT, 'http://localhost/callback'], created_at=NOW)
    other_client = OAuthClient(client_id='https://other.example/client.json', client_name='Other Client',
                               redirect_uris=['https://other.example/callback'], created_at=NOW)
    db.session.add_all([client, other_client])
    db.session.commit()
    return {'tenant': tenant, 'other_tenant': other_tenant, 'user': user, 'colleague': colleague,
            'membership': membership, 'client': client, 'other_client': other_client}


def _request(world, scope='decisions:read decisions:write', redirect_uri=REDIRECT, now=NOW, bind=True, **fields):
    request = service.create_authorization_request(
        CLIENT_ID, redirect_uri, CHALLENGE, RESOURCE, scope=scope, state='abc', now=now, **fields)
    if bind:
        service.bind_client(request, world['client'])
    return request


def _code(world, now=NOW, **kwargs):
    request = _request(world, now=now, **kwargs)
    code = service.approve_request(request, world['user'], world['tenant'], now=now)
    return request, code


def _tokens(world, now=NOW, **kwargs):
    _request_row, code = _code(world, now=now, **kwargs)
    return service.exchange_code(code, CLIENT_ID, REDIRECT, VERIFIER, resource=RESOURCE, now=now)


def _grant():
    return OAuthGrant.query.order_by(OAuthGrant.id.desc()).first()


# ============================================================================
# PKCE AND SCOPES
# ============================================================================

class TestPkce:

    def test_rfc_7636_appendix_b_vector(self):
        verifier = 'dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk'
        challenge = 'E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM'
        assert pkce.challenge_for(verifier) == challenge
        assert pkce.verify(verifier, challenge) is True

    @pytest.mark.parametrize('verifier', [
        None, '', 'short', 'v' * 42, 'v' * 129, 'v' * 63 + ' ', 'v' * 63 + '+', 'v' * 63 + '/', 12345,
        'w' * 64,
    ])
    def test_wrong_or_malformed_verifier_fails(self, verifier):
        assert pkce.verify(verifier, CHALLENGE) is False

    @pytest.mark.parametrize('challenge', [
        None, '', 'c' * 42, 'c' * 44, 'c' * 42 + '=', 'c' * 42 + '+', VERIFIER,
    ])
    def test_malformed_challenge_is_not_valid(self, challenge):
        assert pkce.is_valid_challenge(challenge) is False
        assert pkce.verify(VERIFIER, challenge) is False

    def test_a_plain_challenge_never_verifies(self):
        """The verifier itself as challenge is the "plain" method, which is not supported."""
        verifier = 'p' * 43
        assert pkce.verify(verifier, verifier) is False


class TestScopes:

    @pytest.mark.parametrize('asked,expected', [
        (None, ['decisions:read']),
        ('', ['decisions:read']),
        ('decisions:read', ['decisions:read']),
        ('decisions:write', ['decisions:read', 'decisions:write']),
        ('decisions:write decisions:read', ['decisions:read', 'decisions:write']),
        ('decisions:read decisions:read', ['decisions:read']),
        ('offline_access decisions:read', ['decisions:read']),
        ('admin openid decisions:delete', ['decisions:read']),
        (['decisions:write', 7, None], ['decisions:read', 'decisions:write']),
    ])
    def test_normalise(self, asked, expected):
        assert scopes.normalise(asked) == expected

    def test_the_user_can_grant_less_but_never_more_than_was_asked(self):
        assert scopes.narrow(['decisions:read'], 'decisions:read decisions:write') == ['decisions:read']
        assert scopes.narrow(['decisions:read', 'decisions:write'], 'decisions:read') == ['decisions:read']
        assert scopes.narrow(['decisions:write'], 'decisions:write') == ['decisions:read', 'decisions:write']
        assert scopes.narrow([], 'decisions:write') == ['decisions:read']

    def test_mapping_to_api_key_scopes(self):
        assert scopes.to_key_scopes(['decisions:read']) == ['read', 'search']
        assert scopes.to_key_scopes(['decisions:read', 'decisions:write']) == ['read', 'search', 'write']
        # Writing includes reading
        assert scopes.to_key_scopes(['decisions:write']) == ['read', 'search', 'write']
        assert scopes.to_key_scopes(None) == ['read', 'search']
        assert 'write' not in scopes.to_key_scopes(['decisions:read', 'unknown'])

    def test_subset_for_refresh(self):
        granted = ['decisions:read']
        assert scopes.is_subset(None, granted) is True
        assert scopes.is_subset('decisions:read', granted) is True
        assert scopes.is_subset('decisions:read offline_access', granted) is True
        assert scopes.is_subset('decisions:write', granted) is False
        assert scopes.is_subset('something:else', granted) is False


class TestResourceComparison:

    @pytest.mark.parametrize('left,right,same', [
        (RESOURCE, RESOURCE, True),
        (RESOURCE, 'HTTPS://Decisions.Example/api/mcp', True),
        (RESOURCE, RESOURCE + '/', True),
        (RESOURCE, 'https://decisions.example/api/MCP', False),
        (RESOURCE, 'https://decisions.example/api', False),
        (RESOURCE, 'https://decisions.example', False),
        (RESOURCE, 'https://decisions.example.evil.test/api/mcp', False),
        (RESOURCE, 'https://evil.test/api/mcp', False),
        (RESOURCE, 'http://decisions.example/api/mcp', False),
        (RESOURCE, RESOURCE + '#x', False),
        (RESOURCE, RESOURCE + '?x=1', False),
        (RESOURCE, 'https://user@decisions.example/api/mcp', False),
        (RESOURCE, 'decisions.example/api/mcp', False),
        (RESOURCE, None, False),
        (None, None, False),
        ('', '', False),
    ])
    def test_same_resource(self, left, right, same):
        assert service.same_resource(left, right) is same


# ============================================================================
# THE REQUEST AND THE DECISION
# ============================================================================

class TestAuthorizationRequest:

    def test_request_is_stored_as_asked(self, world):
        request = _request(world, bind=False)

        assert len(request.public_id) >= 40
        assert request.client_identifier == CLIENT_ID
        assert request.oauth_client_id is None
        assert request.requested_scopes == ['decisions:read', 'decisions:write']
        assert request.state == 'abc'
        assert request.resource == RESOURCE
        assert request.expires_at == NOW + settings.AUTHORIZATION_REQUEST_LIFETIME
        assert request.decision is None and request.code_hash is None

    @pytest.mark.parametrize('fields,error', [
        ({'code_challenge_method': 'plain'}, 'invalid_request'),
        ({'code_challenge': ''}, 'invalid_request'),
        ({'code_challenge': None}, 'invalid_request'),
        ({'code_challenge': VERIFIER}, 'invalid_request'),
        ({'redirect_uri': 'http://client.example/callback'}, 'invalid_request'),
        ({'redirect_uri': 'myapp://callback'}, 'invalid_request'),
        ({'redirect_uri': 'javascript:alert(1)'}, 'invalid_request'),
        ({'redirect_uri': ''}, 'invalid_request'),
        ({'resource': 'not a url'}, 'invalid_target'),
        ({'state': 's' * 1025}, 'invalid_request'),
    ])
    def test_malformed_requests_are_refused_and_not_stored(self, world, fields, error):
        values = dict(client_identifier=CLIENT_ID, redirect_uri=REDIRECT, code_challenge=CHALLENGE,
                      resource=RESOURCE, now=NOW)
        values.update(fields)
        with pytest.raises(OAuthError) as excinfo:
            service.create_authorization_request(**values)
        assert _error(excinfo) == error
        assert OAuthAuthorizationRequest.query.count() == 0

    def test_which_client_a_credential_belongs_to(self, world):
        _request_row, code = _code(world)
        assert service.client_of_credential('authorization_code', code) == CLIENT_ID
        assert service.credential_owner_key('authorization_code', code).startswith('request:')
        tokens = service.exchange_code(code, CLIENT_ID, REDIRECT, VERIFIER, now=NOW)
        assert service.client_of_credential('refresh_token', tokens['refresh_token']) == CLIENT_ID
        assert service.credential_owner_key('refresh_token', tokens['refresh_token']) == f'grant:{_grant().id}'
        for grant_type, value in (('refresh_token', tokens['access_token']), ('refresh_token', 'dro_rt_x'),
                                  ('authorization_code', 'dro_ac_x'), ('authorization_code', None),
                                  ('client_credentials', code), (None, code), ('refresh_token', '')):
            assert service.client_of_credential(grant_type, value) is None
            assert service.credential_owner_key(grant_type, value) is None

    def test_open_request_lookup(self, world):
        request = _request(world)
        assert service.get_open_request(request.public_id, NOW).id == request.id
        assert service.get_open_request(request.public_id, NOW + timedelta(minutes=10)) is None
        assert service.get_open_request('nope', NOW) is None
        assert service.get_open_request(None, NOW) is None

        service.deny_request(request, world['user'], now=NOW)
        assert service.get_open_request(request.public_id, NOW) is None

    def test_redirect_uri_must_be_one_the_client_published(self, world):
        request = service.create_authorization_request(
            CLIENT_ID, 'https://evil.test/callback', CHALLENGE, RESOURCE, now=NOW)
        with pytest.raises(OAuthError) as excinfo:
            service.bind_client(request, world['client'])
        assert _error(excinfo) == 'invalid_request'
        assert db.session.get(OAuthAuthorizationRequest, request.id).oauth_client_id is None

    def test_a_loopback_redirect_matches_whatever_the_port(self, world):
        request = service.create_authorization_request(
            CLIENT_ID, 'http://localhost:53124/callback', CHALLENGE, RESOURCE, now=NOW)
        service.bind_client(request, world['client'])
        assert request.oauth_client_id == world['client'].id

    def test_request_cannot_be_bound_to_another_client(self, world):
        request = _request(world, bind=False)
        with pytest.raises(OAuthError):
            service.bind_client(request, world['other_client'])

    def test_a_blocked_client_cannot_be_bound(self, world):
        world['client'].disabled_at = NOW
        db.session.commit()
        request = _request(world, bind=False)
        with pytest.raises(OAuthError):
            service.bind_client(request, world['client'])

    def test_only_the_account_that_opened_the_consent_page_can_answer(self, world):
        request = _request(world)
        service.bind_user(request, world['user'])
        service.bind_user(request, world['user'])  # opening it again is fine

        with pytest.raises(OAuthError):
            service.bind_user(request, world['colleague'])
        with pytest.raises(OAuthError):
            service.approve_request(request, world['colleague'], world['tenant'], now=NOW)
        assert db.session.get(OAuthAuthorizationRequest, request.id).decision is None

        assert service.approve_request(request, world['user'], world['tenant'], now=NOW)


class TestTheCapOnWaitingRequests:
    """
    Second review, F2. The cap on waiting requests bounds storage. Reaching
    it must not refuse people: the oldest request nobody has opened makes room.
    These run on PostgreSQL in CI as well as on SQLite.
    """

    @pytest.fixture(autouse=True)
    def small_cap(self, monkeypatch):
        monkeypatch.setattr(service, 'MAX_OPEN_REQUESTS', 3)

    @staticmethod
    def _waiting():
        return [row.public_id for row in OAuthAuthorizationRequest.query.order_by(OAuthAuthorizationRequest.id)]

    def test_at_the_cap_a_new_request_replaces_the_oldest_unopened_one(self, world):
        first, second, third = (_request(world, bind=False).public_id for _ in range(3))

        fourth = _request(world, bind=False).public_id

        assert self._waiting() == [second, third, fourth]
        fifth = _request(world, bind=False).public_id
        assert self._waiting() == [third, fourth, fifth]
        assert service.get_open_request(first, now=NOW) is None

    def test_a_request_a_signed_in_user_has_opened_is_never_evicted(self, world):
        opened = _request(world, bind=False)
        service.bind_user(opened, world['user'])
        second, third = (_request(world, bind=False).public_id for _ in range(2))

        fourth = _request(world, bind=False).public_id

        assert self._waiting() == [opened.public_id, third, fourth]
        assert service.get_open_request(second, now=NOW) is None
        # ... and it can still be answered
        service.bind_client(opened, world['client'])
        assert service.approve_request(opened, world['user'], world['tenant'], now=NOW)

    def test_a_request_evicted_the_moment_it_was_stored_is_a_refusal_not_a_crash(self, world, monkeypatch):
        """
        At the cap, a request arriving at the same moment can evict the one
        just stored. The caller must be told to try again (503), not fail
        later with a server error when it reads the vanished row.
        """
        real_commit = db.session.commit

        def commit_then_lose_the_row():
            real_commit()
            # another request, at the same moment, evicts every unopened one
            db.session.execute(OAuthAuthorizationRequest.__table__.delete())
            real_commit()

        monkeypatch.setattr(db.session, 'commit', commit_then_lose_the_row)
        with pytest.raises(OAuthError) as refused:
            _request(world, bind=False)
        assert refused.value.error == 'temporarily_unavailable'
        assert refused.value.status == 503

    def test_it_is_refused_only_when_every_waiting_request_has_been_opened(self, world):
        opened = []
        for user in (world['user'], world['colleague'], world['user']):
            request = _request(world, bind=False)
            service.bind_user(request, user)
            opened.append(request.public_id)

        with pytest.raises(OAuthError) as excinfo:
            _request(world, bind=False)

        assert _error(excinfo) == 'temporarily_unavailable' and excinfo.value.status == 503
        assert self._waiting() == opened

    def test_answered_and_expired_requests_neither_count_nor_are_evicted(self, world):
        answered = _request(world)
        service.bind_user(answered, world['user'])
        code = service.approve_request(answered, world['user'], world['tenant'], now=NOW)
        expired = _request(world, bind=False, now=NOW - timedelta(minutes=11)).public_id
        waiting = [_request(world, bind=False).public_id for _ in range(3)]

        newest = _request(world, bind=False).public_id

        assert self._waiting() == [answered.public_id, expired] + waiting[1:] + [newest]
        # The answered request's code is still good
        assert service.exchange_code(code, CLIENT_ID, REDIRECT, VERIFIER, now=NOW)['access_token']

    def test_below_the_cap_nothing_is_evicted(self, world):
        made = [_request(world, bind=False).public_id for _ in range(3)]
        assert self._waiting() == made

    def test_eviction_is_one_row_for_one_new_request(self, world):
        """The table does not shrink below the cap when it is hit: one out, one in."""
        for _ in range(10):
            _request(world, bind=False)
        assert OAuthAuthorizationRequest.query.count() == 3


class TestDecision:

    def test_approval_returns_a_code_and_stores_only_its_hash(self, world):
        request, code = _code(world)

        assert code.startswith(settings.CODE_PREFIX) and len(code) > 40
        assert request.decision == OAuthAuthorizationRequest.DECISION_APPROVED
        assert request.user_id == world['user'].id
        assert request.tenant_id == world['tenant'].id
        assert request.code_hash == hashlib.sha256(code.encode()).hexdigest()
        assert request.code_expires_at == NOW + settings.AUTHORIZATION_CODE_LIFETIME
        assert code not in repr([column for column in db.session.execute(
            OAuthAuthorizationRequest.__table__.select()).one()])
        assert OAuthGrant.query.count() == 0  # the grant is created by the exchange

    def test_the_user_can_switch_writing_off(self, world):
        request = _request(world)
        service.approve_request(request, world['user'], world['tenant'], granted_scopes=['decisions:read'], now=NOW)
        assert request.granted_scopes == ['decisions:read']

    def test_the_user_cannot_grant_more_than_was_asked(self, world):
        request = _request(world, scope='decisions:read')
        service.approve_request(request, world['user'], world['tenant'],
                                granted_scopes=['decisions:read', 'decisions:write'], now=NOW)
        assert request.granted_scopes == ['decisions:read']

    def test_approval_needs_membership_of_the_chosen_organisation(self, world):
        request = _request(world)
        with pytest.raises(OAuthError) as excinfo:
            service.approve_request(request, world['user'], world['other_tenant'], now=NOW)
        assert _error(excinfo) == 'access_denied'
        assert db.session.get(OAuthAuthorizationRequest, request.id).decision is None

    def test_approval_needs_a_bound_client(self, world):
        request = _request(world, bind=False)
        with pytest.raises(OAuthError):
            service.approve_request(request, world['user'], world['tenant'], now=NOW)
        assert db.session.get(OAuthAuthorizationRequest, request.id).code_hash is None

    def test_an_expired_request_cannot_be_approved(self, world):
        request = _request(world)
        with pytest.raises(OAuthError):
            service.approve_request(request, world['user'], world['tenant'],
                                    now=NOW + settings.AUTHORIZATION_REQUEST_LIFETIME)

    def test_a_request_is_answered_once(self, world):
        request, first_code = _code(world)
        with pytest.raises(OAuthError):
            service.approve_request(request, world['user'], world['tenant'], now=NOW)
        with pytest.raises(OAuthError):
            service.deny_request(request, world['user'], now=NOW)
        # The first code still works
        assert service.exchange_code(first_code, CLIENT_ID, REDIRECT, VERIFIER, now=NOW)['access_token']

    def test_denial_leaves_no_code(self, world):
        request = _request(world)
        service.deny_request(request, world['user'], now=NOW)

        assert request.decision == OAuthAuthorizationRequest.DECISION_DENIED
        assert request.code_hash is None
        with pytest.raises(OAuthError):
            service.approve_request(request, world['user'], world['tenant'], now=NOW)


# ============================================================================
# THE CODE EXCHANGE
# ============================================================================

class TestCodeExchange:

    def test_exchange_creates_the_grant_and_returns_tokens(self, world):
        request, code = _code(world)

        response = service.exchange_code(code, CLIENT_ID, REDIRECT, VERIFIER, resource=RESOURCE, now=NOW)

        assert set(response) == {'access_token', 'token_type', 'expires_in', 'refresh_token', 'scope'}
        assert response['token_type'] == 'Bearer'
        assert response['expires_in'] == int(settings.ACCESS_TOKEN_LIFETIME.total_seconds())
        assert response['scope'] == 'decisions:read decisions:write'
        assert response['access_token'].startswith(settings.ACCESS_TOKEN_PREFIX)
        assert response['refresh_token'].startswith(settings.REFRESH_TOKEN_PREFIX)
        assert not response['access_token'].startswith('adr_')

        grant = _grant()
        assert (grant.user_id, grant.tenant_id, grant.oauth_client_id) == (
            world['user'].id, world['tenant'].id, world['client'].id)
        assert grant.resource == RESOURCE
        assert grant.scopes == ['decisions:read', 'decisions:write']
        assert grant.expires_at == NOW + settings.GRANT_LIFETIME
        assert len(grant.public_id) == 36
        assert db.session.get(OAuthAuthorizationRequest, request.id).grant_id == grant.id
        assert db.session.get(OAuthAuthorizationRequest, request.id).code_used_at == NOW

    def test_tokens_are_stored_hashed_only(self, world):
        response = _tokens(world)
        stored = {token.token_hash for token in OAuthToken.query.all()}

        assert stored == {hashlib.sha256(response[name].encode()).hexdigest()
                          for name in ('access_token', 'refresh_token')}
        dump = repr(db.session.execute(OAuthToken.__table__.select()).all())
        assert response['access_token'] not in dump and response['refresh_token'] not in dump

    def test_the_grant_is_recorded_in_the_audit_log_without_tokens(self, world):
        response = _tokens(world)
        entry = AuditLog.query.filter_by(action_type=service.AUDIT_GRANT_CREATED).one()

        assert entry.tenant_id == world['tenant'].id and entry.actor_user_id == world['user'].id
        assert entry.details['client_id'] == CLIENT_ID
        assert entry.details['scopes'] == ['decisions:read', 'decisions:write']
        assert entry.details['redirect_host'] == 'client.example'
        text = repr(entry.details)
        assert response['access_token'] not in text and response['refresh_token'] not in text

    def test_resource_may_be_left_out_of_the_token_request(self, world):
        _request_row, code = _code(world)
        assert service.exchange_code(code, CLIENT_ID, REDIRECT, VERIFIER, now=NOW)['access_token']

    @pytest.mark.parametrize('change,error', [
        ({'code_verifier': 'w' * 64}, 'invalid_grant'),
        ({'code_verifier': None}, 'invalid_grant'),
        ({'code_verifier': ''}, 'invalid_grant'),
        ({'code_verifier': CHALLENGE}, 'invalid_grant'),
        ({'client_identifier': 'https://other.example/client.json'}, 'invalid_grant'),
        ({'client_identifier': None}, 'invalid_grant'),
        ({'redirect_uri': 'https://client.example/callback/'}, 'invalid_grant'),
        ({'redirect_uri': 'https://evil.test/callback'}, 'invalid_grant'),
        ({'redirect_uri': None}, 'invalid_grant'),
        ({'resource': 'https://evil.test/api/mcp'}, 'invalid_target'),
        ({'resource': 'https://decisions.example/api/ai'}, 'invalid_target'),
    ])
    def test_a_wrong_parameter_is_refused_and_leaves_the_code_usable(self, world, change, error):
        _request_row, code = _code(world)
        values = dict(client_identifier=CLIENT_ID, redirect_uri=REDIRECT, code_verifier=VERIFIER, resource=RESOURCE)
        values.update(change)

        with pytest.raises(OAuthError) as excinfo:
            service.exchange_code(code, now=NOW, **values)

        assert _error(excinfo) == error
        assert OAuthGrant.query.count() == 0 and OAuthToken.query.count() == 0
        # A wrong guess by someone else does not burn the real client's code
        assert service.exchange_code(code, CLIENT_ID, REDIRECT, VERIFIER, resource=RESOURCE, now=NOW)['access_token']

    @pytest.mark.parametrize('code', [None, '', 'dro_ac_unknown', 'adr_something', 12345])
    def test_unknown_codes_are_refused(self, world, code):
        with pytest.raises(OAuthError) as excinfo:
            service.exchange_code(code, CLIENT_ID, REDIRECT, VERIFIER, now=NOW)
        assert _error(excinfo) == 'invalid_grant'

    def test_an_access_or_refresh_token_is_not_a_code(self, world):
        response = _tokens(world)
        for value in (response['access_token'], response['refresh_token']):
            with pytest.raises(OAuthError):
                service.exchange_code(value, CLIENT_ID, REDIRECT, VERIFIER, now=NOW)

    def test_an_expired_code_is_refused(self, world):
        _request_row, code = _code(world)
        with pytest.raises(OAuthError) as excinfo:
            service.exchange_code(code, CLIENT_ID, REDIRECT, VERIFIER,
                                  now=NOW + settings.AUTHORIZATION_CODE_LIFETIME)
        assert _error(excinfo) == 'invalid_grant'
        assert OAuthGrant.query.count() == 0

    def test_a_code_works_once_and_a_second_use_ends_the_connection(self, world):
        _request_row, code = _code(world)
        first = service.exchange_code(code, CLIENT_ID, REDIRECT, VERIFIER, now=NOW)
        assert service.validate_access_token(first['access_token'], RESOURCE, now=NOW) is not None

        with pytest.raises(OAuthError) as excinfo:
            service.exchange_code(code, CLIENT_ID, REDIRECT, VERIFIER, now=NOW + timedelta(seconds=5))

        assert _error(excinfo) == 'invalid_grant'
        grant = _grant()
        assert grant.revoked_at is not None and grant.revoke_reason == settings.REVOKED_CODE_REUSE
        assert service.validate_access_token(first['access_token'], RESOURCE, now=NOW + timedelta(seconds=6)) is None
        with pytest.raises(OAuthError):
            service.refresh(first['refresh_token'], CLIENT_ID, now=NOW + timedelta(seconds=6))
        assert AuditLog.query.filter_by(action_type=service.AUDIT_CODE_REUSE).count() == 1
        assert OAuthGrant.query.count() == 1

    @pytest.mark.parametrize('redirect_uri,verifier', [
        ('https://wrong.example/cb', 'x' * 43),      # the observer has the code and nothing else
        (REDIRECT, 'x' * 43),                        # ... or knows the redirect URI, which is published
        (REDIRECT, None),
        (REDIRECT, ''),
        ('https://wrong.example/cb', VERIFIER),
        (None, VERIFIER),
    ])
    def test_a_used_code_without_the_redirect_uri_and_verifier_changes_nothing(self, world, redirect_uri, verifier):
        """
        Second review, F4. The client_id is public and a code passes through
        browser history, proxy logs and Referer headers. Whoever saw a used
        code could present it in the right client's name and disconnect the
        user. Only the application holds the PKCE verifier.
        """
        _request_row, code = _code(world)
        first = service.exchange_code(code, CLIENT_ID, REDIRECT, VERIFIER, now=NOW)

        with pytest.raises(OAuthError) as excinfo:
            service.exchange_code(code, CLIENT_ID, redirect_uri, verifier, now=NOW + timedelta(seconds=5))

        assert _error(excinfo) == 'invalid_grant'
        assert _grant().revoked_at is None
        assert service.validate_access_token(first['access_token'], RESOURCE, now=NOW + timedelta(seconds=6))
        assert AuditLog.query.filter_by(action_type=service.AUDIT_CODE_REUSE).count() == 0
        # The application itself presenting it again, with everything right, still ends the connection
        with pytest.raises(OAuthError):
            service.exchange_code(code, CLIENT_ID, REDIRECT, VERIFIER, now=NOW + timedelta(seconds=7))
        assert _grant().revoke_reason == settings.REVOKED_CODE_REUSE

    def test_a_used_code_in_another_clients_name_changes_nothing(self, world):
        """Anyone who saw a used code could otherwise disconnect its user."""
        _request_row, code = _code(world)
        first = service.exchange_code(code, CLIENT_ID, REDIRECT, VERIFIER, now=NOW)

        for other in ('https://other.example/client.json', 'https://evil.example/c.json', None, ''):
            with pytest.raises(OAuthError) as excinfo:
                service.exchange_code(code, other, REDIRECT, VERIFIER, now=NOW + timedelta(seconds=5))
            assert _error(excinfo) == 'invalid_grant'

        assert _grant().revoked_at is None
        assert service.validate_access_token(first['access_token'], RESOURCE, now=NOW + timedelta(seconds=6))
        assert AuditLog.query.filter_by(action_type=service.AUDIT_CODE_REUSE).count() == 0

    def test_a_denied_request_has_nothing_to_exchange(self, world):
        request = _request(world)
        service.deny_request(request, world['user'], now=NOW)
        assert OAuthAuthorizationRequest.query.filter(OAuthAuthorizationRequest.code_hash.isnot(None)).count() == 0

    def test_no_tokens_when_the_user_left_between_consent_and_exchange(self, world):
        _request_row, code = _code(world)
        db.session.delete(world['membership'])
        db.session.commit()

        with pytest.raises(OAuthError) as excinfo:
            service.exchange_code(code, CLIENT_ID, REDIRECT, VERIFIER, now=NOW)

        assert _error(excinfo) == 'invalid_grant'
        assert OAuthGrant.query.count() == 0 and OAuthToken.query.count() == 0

    def test_no_tokens_for_a_client_blocked_after_consent(self, world):
        _request_row, code = _code(world)
        world['client'].disabled_at = NOW
        db.session.commit()
        with pytest.raises(OAuthError):
            service.exchange_code(code, CLIENT_ID, REDIRECT, VERIFIER, now=NOW)
        assert OAuthGrant.query.count() == 0

    def test_the_narrowed_scope_is_what_the_tokens_carry(self, world):
        request = _request(world)
        code = service.approve_request(request, world['user'], world['tenant'],
                                       granted_scopes=['decisions:read'], now=NOW)
        response = service.exchange_code(code, CLIENT_ID, REDIRECT, VERIFIER, now=NOW)

        assert response['scope'] == 'decisions:read'
        assert service.key_scopes(_grant()) == ['read', 'search']


# ============================================================================
# ACCESS TOKENS
# ============================================================================

class TestAccessTokenValidation:

    def test_a_valid_token_gives_its_grant(self, world):
        response = _tokens(world)
        grant = service.validate_access_token(response['access_token'], RESOURCE, now=NOW + timedelta(minutes=5))

        assert grant.id == _grant().id
        assert (grant.user_id, grant.tenant_id) == (world['user'].id, world['tenant'].id)
        assert service.key_scopes(grant) == ['read', 'search', 'write']

    def test_expiry(self, world):
        response = _tokens(world)
        last_moment = NOW + settings.ACCESS_TOKEN_LIFETIME - timedelta(seconds=1)
        assert service.validate_access_token(response['access_token'], RESOURCE, now=last_moment) is not None
        assert service.validate_access_token(
            response['access_token'], RESOURCE, now=NOW + settings.ACCESS_TOKEN_LIFETIME) is None

    @pytest.mark.parametrize('resource', [
        'https://decisions.example/api/ai', 'https://decisions.example', 'https://evil.test/api/mcp',
        'http://decisions.example/api/mcp', None, '',
    ])
    def test_a_token_is_only_good_for_the_resource_it_was_issued_for(self, world, resource):
        response = _tokens(world)
        assert service.validate_access_token(response['access_token'], resource, now=NOW) is None

    def test_the_resource_is_compared_without_regard_to_host_case_or_trailing_slash(self, world):
        response = _tokens(world)
        assert service.validate_access_token(
            response['access_token'], 'https://Decisions.Example/api/mcp/', now=NOW) is not None

    @pytest.mark.parametrize('value', [None, '', 'adr_an_api_key', 'dro_at_unknown', 'Bearer x', 42])
    def test_other_values_are_refused(self, world, value):
        _tokens(world)
        assert service.validate_access_token(value, RESOURCE, now=NOW) is None

    def test_a_refresh_token_or_code_is_not_an_access_token(self, world):
        request, code = _code(world)
        response = service.exchange_code(code, CLIENT_ID, REDIRECT, VERIFIER, now=NOW)
        assert service.validate_access_token(response['refresh_token'], RESOURCE, now=NOW) is None
        assert service.validate_access_token(code, RESOURCE, now=NOW) is None
        # ... also when someone swaps the prefix
        swapped = settings.ACCESS_TOKEN_PREFIX + response['refresh_token'][len(settings.REFRESH_TOKEN_PREFIX):]
        assert service.validate_access_token(swapped, RESOURCE, now=NOW) is None

    def test_a_token_stops_when_the_grant_expires(self, world, monkeypatch):
        monkeypatch.setattr(settings, 'GRANT_LIFETIME', timedelta(minutes=30))
        response = _tokens(world)

        assert response['expires_in'] == 30 * 60  # never longer than the grant
        assert service.validate_access_token(response['access_token'], RESOURCE, now=NOW + timedelta(minutes=29))
        assert service.validate_access_token(
            response['access_token'], RESOURCE, now=NOW + timedelta(minutes=30)) is None

    def test_removed_member_is_refused_and_the_connection_ended_for_good(self, world):
        response = _tokens(world)
        db.session.delete(world['membership'])
        db.session.commit()

        assert service.validate_access_token(response['access_token'], RESOURCE, now=NOW) is None

        grant = _grant()
        assert grant.revoked_at == NOW and grant.revoke_reason == settings.REVOKED_OWNER_GONE
        entry = AuditLog.query.filter_by(action_type=service.AUDIT_GRANT_REVOKED).one()
        assert entry.details['reason'] == settings.REVOKED_OWNER_GONE
        # Added back, the same token does not work again: that takes a new consent
        db.session.add(TenantMembership(user_id=world['user'].id, tenant_id=world['tenant'].id,
                                        global_role=GlobalRole.USER))
        db.session.commit()
        assert service.validate_access_token(response['access_token'], RESOURCE, now=NOW) is None
        with pytest.raises(OAuthError):
            service.refresh(response['refresh_token'], CLIENT_ID, now=NOW)

    @pytest.mark.parametrize('state', ['anonymised', 'deleted'])
    def test_anonymised_or_deleted_user_is_refused(self, world, state):
        response = _tokens(world)
        if state == 'anonymised':
            world['user'].is_anonymized = True
        else:
            world['user'].deleted_at = NOW
        db.session.commit()

        assert service.validate_access_token(response['access_token'], RESOURCE, now=NOW) is None
        assert _grant().revoke_reason == settings.REVOKED_OWNER_GONE

    def test_deleted_tenant_is_refused_and_restoring_it_does_not_bring_the_connection_back(self, world):
        response = _tokens(world)
        world['tenant'].deleted_at = NOW
        db.session.commit()
        assert service.validate_access_token(response['access_token'], RESOURCE, now=NOW) is None

        world['tenant'].deleted_at = None
        db.session.commit()
        assert service.validate_access_token(response['access_token'], RESOURCE, now=NOW) is None
        assert _grant().revoke_reason == settings.REVOKED_OWNER_GONE

    def test_a_connection_nobody_used_while_the_organisation_was_deleted_survives_its_restoring(self, world):
        """Ending the connection happens when a token is presented; a deletion that is undone unnoticed changes nothing."""
        response = _tokens(world)
        world['tenant'].deleted_at = NOW
        db.session.commit()
        world['tenant'].deleted_at = None
        db.session.commit()
        assert service.validate_access_token(response['access_token'], RESOURCE, now=NOW) is not None

    def test_a_blocked_client_is_refused(self, world):
        response = _tokens(world)
        world['client'].disabled_at = NOW
        db.session.commit()
        assert service.validate_access_token(response['access_token'], RESOURCE, now=NOW) is None

    def test_last_use_is_recorded_but_not_on_every_request(self, world):
        response = _tokens(world)
        token = OAuthToken.query.filter_by(kind=OAuthToken.KIND_ACCESS).one()
        assert token.last_used_at is None

        service.validate_access_token(response['access_token'], RESOURCE, now=NOW + timedelta(seconds=10))
        assert token.last_used_at == NOW + timedelta(seconds=10)
        assert _grant().last_used_at == NOW + timedelta(seconds=10)

        service.validate_access_token(response['access_token'], RESOURCE, now=NOW + timedelta(seconds=40))
        assert token.last_used_at == NOW + timedelta(seconds=10)

        service.validate_access_token(response['access_token'], RESOURCE, now=NOW + timedelta(seconds=71))
        assert token.last_used_at == NOW + timedelta(seconds=71)

    def test_grants_of_two_organisations_stay_apart(self, world):
        db.session.add(TenantMembership(user_id=world['user'].id, tenant_id=world['other_tenant'].id,
                                        global_role=GlobalRole.USER))
        db.session.commit()
        first = _tokens(world)
        request = _request(world)
        code = service.approve_request(request, world['user'], world['other_tenant'], now=NOW)
        second = service.exchange_code(code, CLIENT_ID, REDIRECT, VERIFIER, now=NOW)

        assert service.validate_access_token(first['access_token'], RESOURCE, now=NOW).tenant_id == world['tenant'].id
        assert service.validate_access_token(
            second['access_token'], RESOURCE, now=NOW).tenant_id == world['other_tenant'].id


# ============================================================================
# REFRESH
# ============================================================================

class TestRefresh:

    def test_refresh_replaces_both_tokens(self, world):
        first = _tokens(world)
        later = NOW + timedelta(minutes=50)

        second = service.refresh(first['refresh_token'], CLIENT_ID, resource=RESOURCE, now=later)

        assert second['access_token'] != first['access_token']
        assert second['refresh_token'] != first['refresh_token']
        assert second['scope'] == 'decisions:read decisions:write'
        assert service.validate_access_token(second['access_token'], RESOURCE, now=later) is not None
        # The old access token runs out by itself; it is not cut short
        assert service.validate_access_token(first['access_token'], RESOURCE, now=later) is not None
        assert OAuthGrant.query.count() == 1
        assert _grant().last_used_at == later

    def test_a_chain_of_refreshes_keeps_working(self, world):
        tokens = _tokens(world)
        moment = NOW
        for _ in range(5):
            moment += timedelta(days=20)
            tokens = service.refresh(tokens['refresh_token'], CLIENT_ID, now=moment)
        assert service.validate_access_token(tokens['access_token'], RESOURCE, now=moment) is not None
        assert _grant().revoked_at is None

    def test_an_unused_refresh_token_dies_after_the_idle_time(self, world):
        tokens = _tokens(world)
        with pytest.raises(OAuthError) as excinfo:
            service.refresh(tokens['refresh_token'], CLIENT_ID, now=NOW + settings.REFRESH_TOKEN_IDLE_LIFETIME)
        assert _error(excinfo) == 'invalid_grant'
        assert _grant().revoked_at is None  # running out is not an attack

    def test_the_connection_ends_at_the_absolute_lifetime_however_often_it_was_used(self, world):
        tokens = _tokens(world)
        moment = NOW
        while moment + timedelta(days=25) < NOW + settings.GRANT_LIFETIME:
            moment += timedelta(days=25)
            tokens = service.refresh(tokens['refresh_token'], CLIENT_ID, now=moment)

        end = NOW + settings.GRANT_LIFETIME
        refresh_row = OAuthToken.query.filter_by(
            token_hash=hashlib.sha256(tokens['refresh_token'].encode()).hexdigest()).one()
        assert refresh_row.expires_at == end  # never beyond the grant
        with pytest.raises(OAuthError):
            service.refresh(tokens['refresh_token'], CLIENT_ID, now=end)
        assert service.validate_access_token(tokens['access_token'], RESOURCE, now=end) is None

    def test_a_used_refresh_token_presented_again_ends_the_connection(self, world):
        first = _tokens(world)
        second = service.refresh(first['refresh_token'], CLIENT_ID, now=NOW + timedelta(minutes=10))
        # The real client uses what it got
        assert service.validate_access_token(second['access_token'], RESOURCE, now=NOW + timedelta(minutes=11))

        with pytest.raises(OAuthError) as excinfo:
            service.refresh(first['refresh_token'], CLIENT_ID, now=NOW + timedelta(minutes=12))

        assert _error(excinfo) == 'invalid_grant'
        grant = _grant()
        assert grant.revoked_at == NOW + timedelta(minutes=12)
        assert grant.revoke_reason == settings.REVOKED_REFRESH_REUSE
        after = NOW + timedelta(minutes=13)
        assert service.validate_access_token(second['access_token'], RESOURCE, now=after) is None
        with pytest.raises(OAuthError):
            service.refresh(second['refresh_token'], CLIENT_ID, now=after)
        entry = AuditLog.query.filter_by(action_type=service.AUDIT_REFRESH_REUSE).one()
        assert entry.tenant_id == world['tenant'].id

    def test_reuse_long_after_rotation_ends_the_connection_even_if_nothing_was_used(self, world):
        first = _tokens(world)
        service.refresh(first['refresh_token'], CLIENT_ID, now=NOW + timedelta(minutes=10))
        with pytest.raises(OAuthError):
            service.refresh(first['refresh_token'], CLIENT_ID,
                            now=NOW + timedelta(minutes=10) + settings.REFRESH_REUSE_GRACE)
        assert _grant().revoked_at is not None

    def test_a_lost_response_can_be_retried_within_the_grace_window(self, world):
        first = _tokens(world)
        moment = NOW + timedelta(minutes=10)
        lost = service.refresh(first['refresh_token'], CLIENT_ID, now=moment)

        retried = service.refresh(first['refresh_token'], CLIENT_ID, now=moment + timedelta(seconds=10))

        assert _grant().revoked_at is None
        assert retried['refresh_token'] != lost['refresh_token']
        assert service.validate_access_token(retried['access_token'], RESOURCE, now=moment + timedelta(seconds=11))
        # What the lost response carried is taken back, not forgotten: the rows stay, marked
        withdrawn = OAuthToken.query.filter(OAuthToken.withdrawn_at.isnot(None)).all()
        assert sorted(token.kind for token in withdrawn) == ['access', 'refresh']
        assert {token.token_hash for token in withdrawn} == {
            hashlib.sha256(lost[name].encode()).hexdigest() for name in ('access_token', 'refresh_token')}
        # ... and the retried pair carries on
        assert service.refresh(retried['refresh_token'], CLIENT_ID, now=moment + timedelta(minutes=30))
        assert _grant().revoked_at is None

    @pytest.mark.parametrize('which', ['access_token', 'refresh_token'])
    def test_using_a_withdrawn_token_ends_the_connection(self, world, which):
        """If the "lost" response did arrive, two parties hold tokens. The first use of the withdrawn pair shows it."""
        first = _tokens(world)
        moment = NOW + timedelta(minutes=10)
        withdrawn = service.refresh(first['refresh_token'], CLIENT_ID, now=moment)
        replayed = service.refresh(first['refresh_token'], CLIENT_ID, now=moment + timedelta(seconds=10))
        later = moment + timedelta(seconds=20)

        if which == 'access_token':
            assert service.validate_access_token(withdrawn['access_token'], RESOURCE, now=later) is None
        else:
            with pytest.raises(OAuthError) as excinfo:
                service.refresh(withdrawn['refresh_token'], CLIENT_ID, now=later)
            assert _error(excinfo) == 'invalid_grant'

        grant = _grant()
        assert grant.revoked_at == later and grant.revoke_reason == settings.REVOKED_REFRESH_REUSE
        entry = AuditLog.query.filter_by(action_type=service.AUDIT_REFRESH_REUSE).one()
        assert entry.tenant_id == world['tenant'].id
        assert service.validate_access_token(replayed['access_token'], RESOURCE, now=later) is None
        with pytest.raises(OAuthError):
            service.refresh(replayed['refresh_token'], CLIENT_ID, now=later)

    def test_the_grace_is_given_once_per_token(self, world):
        first = _tokens(world)
        moment = NOW + timedelta(minutes=10)
        service.refresh(first['refresh_token'], CLIENT_ID, now=moment)
        second = service.refresh(first['refresh_token'], CLIENT_ID, now=moment + timedelta(seconds=5))

        with pytest.raises(OAuthError):
            service.refresh(first['refresh_token'], CLIENT_ID, now=moment + timedelta(seconds=10))

        assert _grant().revoke_reason == settings.REVOKED_REFRESH_REUSE
        assert service.validate_access_token(
            second['access_token'], RESOURCE, now=moment + timedelta(seconds=11)) is None

    def test_a_withdrawn_token_does_not_get_a_grace_of_its_own(self, world):
        first = _tokens(world)
        moment = NOW + timedelta(minutes=10)
        withdrawn = service.refresh(first['refresh_token'], CLIENT_ID, now=moment)
        service.refresh(first['refresh_token'], CLIENT_ID, now=moment + timedelta(seconds=1))
        with pytest.raises(OAuthError):
            service.refresh(withdrawn['refresh_token'], CLIENT_ID, now=moment + timedelta(seconds=2))
        assert _grant().revoked_at is not None

    def test_no_grace_once_the_new_access_token_was_used(self, world):
        first = _tokens(world)
        moment = NOW + timedelta(minutes=10)
        second = service.refresh(first['refresh_token'], CLIENT_ID, now=moment)
        service.validate_access_token(second['access_token'], RESOURCE, now=moment + timedelta(seconds=2))

        with pytest.raises(OAuthError):
            service.refresh(first['refresh_token'], CLIENT_ID, now=moment + timedelta(seconds=5))
        assert _grant().revoke_reason == settings.REVOKED_REFRESH_REUSE

    def test_no_grace_once_the_new_refresh_token_was_used(self, world):
        first = _tokens(world)
        moment = NOW + timedelta(minutes=10)
        second = service.refresh(first['refresh_token'], CLIENT_ID, now=moment)
        service.refresh(second['refresh_token'], CLIENT_ID, now=moment + timedelta(seconds=2))

        with pytest.raises(OAuthError):
            service.refresh(first['refresh_token'], CLIENT_ID, now=moment + timedelta(seconds=5))
        assert _grant().revoke_reason == settings.REVOKED_REFRESH_REUSE

    def test_another_client_cannot_use_or_burn_the_token(self, world):
        tokens = _tokens(world)
        with pytest.raises(OAuthError) as excinfo:
            service.refresh(tokens['refresh_token'], 'https://other.example/client.json', now=NOW)
        assert _error(excinfo) == 'invalid_grant'
        assert _grant().revoked_at is None
        assert service.refresh(tokens['refresh_token'], CLIENT_ID, now=NOW)['access_token']

    @pytest.mark.parametrize('value', [None, '', 'dro_rt_unknown', 'adr_key', 7])
    def test_unknown_refresh_tokens_are_refused(self, world, value):
        _tokens(world)
        with pytest.raises(OAuthError) as excinfo:
            service.refresh(value, CLIENT_ID, now=NOW)
        assert _error(excinfo) == 'invalid_grant'

    def test_an_access_token_cannot_be_used_to_refresh(self, world):
        tokens = _tokens(world)
        with pytest.raises(OAuthError):
            service.refresh(tokens['access_token'], CLIENT_ID, now=NOW)

    def test_refresh_cannot_add_scopes_and_the_token_survives_the_attempt(self, world):
        request = _request(world)
        code = service.approve_request(request, world['user'], world['tenant'],
                                       granted_scopes=['decisions:read'], now=NOW)
        tokens = service.exchange_code(code, CLIENT_ID, REDIRECT, VERIFIER, now=NOW)

        with pytest.raises(OAuthError) as excinfo:
            service.refresh(tokens['refresh_token'], CLIENT_ID, scope='decisions:read decisions:write', now=NOW)
        assert _error(excinfo) == 'invalid_scope'

        again = service.refresh(tokens['refresh_token'], CLIENT_ID, scope='decisions:read offline_access', now=NOW)
        assert again['scope'] == 'decisions:read'

    def test_refresh_for_another_resource_is_refused_and_the_token_survives(self, world):
        tokens = _tokens(world)
        with pytest.raises(OAuthError) as excinfo:
            service.refresh(tokens['refresh_token'], CLIENT_ID, resource='https://evil.test/api/mcp', now=NOW)
        assert _error(excinfo) == 'invalid_target'
        assert service.refresh(tokens['refresh_token'], CLIENT_ID, resource=RESOURCE, now=NOW)['access_token']

    def test_refresh_after_the_user_left_ends_the_connection(self, world):
        tokens = _tokens(world)
        db.session.delete(world['membership'])
        db.session.commit()

        with pytest.raises(OAuthError) as excinfo:
            service.refresh(tokens['refresh_token'], CLIENT_ID, now=NOW + timedelta(minutes=5))

        assert _error(excinfo) == 'invalid_grant'
        assert _grant().revoke_reason == settings.REVOKED_OWNER_GONE
        assert OAuthToken.query.filter(OAuthToken.expires_at > NOW + timedelta(minutes=5)).count() == 0

    def test_refresh_is_refused_for_a_blocked_client(self, world):
        tokens = _tokens(world)
        world['client'].disabled_at = NOW
        db.session.commit()
        with pytest.raises(OAuthError):
            service.refresh(tokens['refresh_token'], CLIENT_ID, now=NOW)


# ============================================================================
# ENDING A CONNECTION
# ============================================================================

class TestRevocation:

    def test_the_user_ends_a_connection(self, world):
        tokens = _tokens(world)
        grant = _grant()

        assert service.revoke_grant(grant, settings.REVOKED_BY_USER, by_user=world['user'], now=NOW) is True

        assert grant.revoked_at == NOW and grant.revoked_by_user_id == world['user'].id
        assert service.validate_access_token(tokens['access_token'], RESOURCE, now=NOW) is None
        with pytest.raises(OAuthError):
            service.refresh(tokens['refresh_token'], CLIENT_ID, now=NOW)
        # Refused, and not mistaken for token theft
        assert grant.revoke_reason == settings.REVOKED_BY_USER
        entry = AuditLog.query.filter_by(action_type=service.AUDIT_GRANT_REVOKED).one()
        assert entry.actor_user_id == world['user'].id and entry.details['reason'] == settings.REVOKED_BY_USER
        assert service.revoke_grant(grant, settings.REVOKED_BY_USER, by_user=world['user'], now=NOW) is False

    def test_an_admin_ends_a_members_connection(self, world):
        _tokens(world)
        grant = _grant()
        service.revoke_grant(grant, settings.REVOKED_BY_ADMIN, by_user=world['colleague'], now=NOW)

        entry = AuditLog.query.filter_by(action_type=service.AUDIT_GRANT_REVOKED).one()
        assert entry.actor_user_id == world['colleague'].id
        assert entry.details['grant_user_id'] == world['user'].id

    @pytest.mark.parametrize('which', ['access_token', 'refresh_token'])
    def test_the_client_revokes_with_either_token(self, world, which):
        tokens = _tokens(world)

        assert service.revoke_token(tokens[which], CLIENT_ID, now=NOW) is True

        assert _grant().revoke_reason == settings.REVOKED_BY_CLIENT
        assert service.validate_access_token(tokens['access_token'], RESOURCE, now=NOW) is None

    def test_another_client_cannot_revoke(self, world):
        tokens = _tokens(world)
        assert service.revoke_token(tokens['refresh_token'], 'https://other.example/client.json', now=NOW) is False
        assert service.revoke_token('dro_rt_unknown', CLIENT_ID, now=NOW) is False
        assert service.revoke_token(None, CLIENT_ID, now=NOW) is False
        assert _grant().revoked_at is None

    def test_one_connection_ends_without_touching_another(self, world):
        first = _tokens(world)
        first_grant = _grant()
        second = _tokens(world)

        service.revoke_grant(first_grant, settings.REVOKED_BY_USER, by_user=world['user'], now=NOW)

        assert service.validate_access_token(first['access_token'], RESOURCE, now=NOW) is None
        assert service.validate_access_token(second['access_token'], RESOURCE, now=NOW) is not None

    def test_leaving_an_organisation_ends_the_connections_there_only(self, world):
        db.session.add(TenantMembership(user_id=world['user'].id, tenant_id=world['other_tenant'].id,
                                        global_role=GlobalRole.USER))
        db.session.commit()
        here = _tokens(world)
        _tokens(world)
        request = _request(world)
        code = service.approve_request(request, world['user'], world['other_tenant'], now=NOW)
        elsewhere = service.exchange_code(code, CLIENT_ID, REDIRECT, VERIFIER, now=NOW)

        ended = service.revoke_grants_of_member(world['user'].id, world['tenant'].id, now=NOW)

        assert ended == 2
        assert service.validate_access_token(here['access_token'], RESOURCE, now=NOW) is None
        assert service.validate_access_token(elsewhere['access_token'], RESOURCE, now=NOW) is not None
        assert service.revoke_grants_of_member(world['user'].id, world['tenant'].id, now=NOW) == 0

    def test_listing_live_connections(self, world):
        _tokens(world)
        ended = _grant()
        _tokens(world, now=NOW + timedelta(minutes=1))
        service.revoke_grant(ended, settings.REVOKED_BY_USER, by_user=world['user'], now=NOW + timedelta(minutes=2))
        later = NOW + timedelta(minutes=3)

        assert len(service.live_grants_for_user(world['user'].id, now=later)) == 1
        assert len(service.live_grants_for_user(world['user'].id, world['other_tenant'].id, now=later)) == 0
        assert len(service.live_grants_for_tenant(world['tenant'].id, now=later)) == 1
        assert service.live_grants_for_tenant(world['other_tenant'].id, now=later) == []
        assert service.live_grants_for_user(world['user'].id, now=NOW + settings.GRANT_LIFETIME + timedelta(days=1)) == []

    def test_housekeeping_keeps_reuse_detection_working_and_then_forgets(self, world):
        """The public purge and this service agree on how long a used refresh token is remembered."""
        import retention
        first = _tokens(world)
        service.refresh(first['refresh_token'], CLIENT_ID, now=NOW + timedelta(days=1))

        retention.purge_expired_oauth_rows(NOW + timedelta(days=20))
        assert OAuthToken.query.filter(OAuthToken.rotated_at.isnot(None)).count() == 1

        with pytest.raises(OAuthError):
            service.refresh(first['refresh_token'], CLIENT_ID, now=NOW + timedelta(days=21))
        assert _grant().revoke_reason == settings.REVOKED_REFRESH_REUSE
