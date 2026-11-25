"""
Tests that race two or more database connections on the single-use claims of
the OAuth token service (Enterprise Edition): the exchange of an authorization
code and the replacement of a refresh token.

These need a database that several connections can use at once. CI runs them
on PostgreSQL (TEST_DATABASE_URL); with the default in-memory SQLite, which
has one connection, they are skipped. A file-based SQLite database also
works: TEST_DATABASE_URL=sqlite:////tmp/oauth_test.db

Note: These tests require Enterprise Edition modules from ee/backend/oauth_server/
"""
import base64
import hashlib
import os
import sys
import threading
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    db, GlobalRole, MaturityState, OAuthAuthorizationRequest, OAuthClient, OAuthGrant, OAuthToken,
    Tenant, TenantMembership, User,
)

try:
    from ee.backend.oauth_server import service, settings
    from ee.backend.oauth_server.errors import OAuthError
    EE_AVAILABLE = True
except ImportError:
    EE_AVAILABLE = False
    service = settings = None
    OAuthError = Exception

EE_TESTS_ENABLED = EE_AVAILABLE and os.environ.get('DECISION_RECORDS_EDITION', 'community') == 'enterprise'
pytestmark = pytest.mark.skipif(
    not EE_TESTS_ENABLED,
    reason="Enterprise Edition tests require DECISION_RECORDS_EDITION=enterprise and EE modules",
)

RESOURCE = 'https://decisions.example/api/mcp'
CLIENT_ID = 'https://client.example/oauth/client.json'
REDIRECT = 'https://client.example/callback'
VERIFIER = 'v' * 64
CHALLENGE = base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).rstrip(b'=').decode()
THREADS = 8


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture
def concurrent_app(app):
    """The fixture app, on a database that more than one connection can use."""
    url = str(app.config['SQLALCHEMY_DATABASE_URI'])
    if url.startswith('sqlite') and ':memory:' in url:
        pytest.skip('needs a database with more than one connection (PostgreSQL in CI)')
    return app


@pytest.fixture
def ids(concurrent_app):
    tenant = Tenant(domain='example.com', name='Example', status='active', maturity_state=MaturityState.BOOTSTRAP)
    db.session.add(tenant)
    db.session.flush()
    user = User(email='person@example.com', sso_domain='example.com', auth_type='local', email_verified=True)
    db.session.add(user)
    db.session.flush()
    db.session.add(TenantMembership(user_id=user.id, tenant_id=tenant.id, global_role=GlobalRole.USER))
    client = OAuthClient(client_id=CLIENT_ID, client_name='Example Client', redirect_uris=[REDIRECT])
    db.session.add(client)
    db.session.commit()
    result = {'tenant': tenant.id, 'user': user.id}
    # Hold no connection and no transaction while the threads work
    db.session.remove()
    return result


def _code(ids):
    request = service.create_authorization_request(CLIENT_ID, REDIRECT, CHALLENGE, RESOURCE,
                                                   scope='decisions:read decisions:write')
    service.bind_client(request, OAuthClient.query.one())
    code = service.approve_request(request, db.session.get(User, ids['user']), db.session.get(Tenant, ids['tenant']))
    db.session.remove()
    return code


def _race(app, work, count=THREADS):
    """Run `work()` in `count` threads that start together, each with its own session. Returns their outcomes."""
    barrier = threading.Barrier(count)
    outcomes = [None] * count

    def run(index):
        with app.app_context():
            try:
                barrier.wait(timeout=10)
                outcomes[index] = ('ok', work())
            except OAuthError as error:
                outcomes[index] = ('refused', error.error)
            except Exception as exc:  # anything else is a failure of the test
                outcomes[index] = ('crashed', repr(exc))
            finally:
                db.session.remove()

    threads = [threading.Thread(target=run, args=(index,)) for index in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert not any(thread.is_alive() for thread in threads), 'a thread did not finish (deadlock?)'
    assert not [outcome for outcome in outcomes if outcome is None or outcome[0] == 'crashed'], outcomes
    return outcomes


def test_one_code_presented_many_times_at_once_gives_tokens_once(concurrent_app, ids):
    code = _code(ids)

    outcomes = _race(concurrent_app, lambda: service.exchange_code(code, CLIENT_ID, REDIRECT, VERIFIER))

    succeeded = [result for kind, result in outcomes if kind == 'ok']
    refused = [result for kind, result in outcomes if kind == 'refused']
    assert len(succeeded) == 1, outcomes
    assert refused == ['invalid_grant'] * (THREADS - 1)

    # One grant came of it, never two
    assert OAuthGrant.query.count() == 1
    assert OAuthToken.query.count() == 2
    assert OAuthAuthorizationRequest.query.one().code_used_at is not None
    # The other presentations were second uses of a single-use code: the
    # connection they point at is ended, and its tokens with it
    grant = OAuthGrant.query.one()
    assert grant.revoked_at is not None and grant.revoke_reason == settings.REVOKED_CODE_REUSE
    assert service.validate_access_token(succeeded[0]['access_token'], RESOURCE) is None


def test_one_refresh_token_presented_twice_at_once_leaves_one_working_pair(concurrent_app, ids):
    """The retry of a request whose answer may have been lost, arriving while the first is still being handled."""
    first = service.exchange_code(_code(ids), CLIENT_ID, REDIRECT, VERIFIER)
    db.session.remove()

    outcomes = _race(concurrent_app, lambda: service.refresh(first['refresh_token'], CLIENT_ID), count=2)

    succeeded = [result for kind, result in outcomes if kind == 'ok']
    refused = [result for kind, result in outcomes if kind == 'refused']
    assert succeeded, outcomes
    assert set(refused) <= {'invalid_grant'}

    # One presentation again within the grace window is not theft: the connection is still there ...
    grant = OAuthGrant.query.one()
    assert grant.revoked_at is None
    # ... and however the two interleaved, exactly one refresh token is usable
    # afterwards, and it is one that was handed out
    now = _now()
    usable = OAuthToken.query.filter(
        OAuthToken.kind == OAuthToken.KIND_REFRESH, OAuthToken.rotated_at.is_(None),
        OAuthToken.withdrawn_at.is_(None), OAuthToken.expires_at > now).all()
    assert len(usable) == 1
    handed_out = {hashlib.sha256(result['refresh_token'].encode()).hexdigest(): result for result in succeeded}
    assert usable[0].token_hash in handed_out
    winner = handed_out[usable[0].token_hash]
    assert len({result['refresh_token'] for result in succeeded}) == len(succeeded)
    # The surviving pair works, and the original token is spent
    assert service.validate_access_token(winner['access_token'], RESOURCE) is not None
    db.session.remove()
    assert service.refresh(winner['refresh_token'], CLIENT_ID, now=now + timedelta(minutes=5))['access_token']
    assert OAuthToken.query.filter_by(
        token_hash=hashlib.sha256(first['refresh_token'].encode()).hexdigest()).one().rotated_at is not None


def test_one_refresh_token_presented_many_times_at_once_ends_the_connection(concurrent_app, ids):
    """More than one repeat of a used refresh token is not a lost response. Nothing usable may be left behind."""
    first = service.exchange_code(_code(ids), CLIENT_ID, REDIRECT, VERIFIER)
    db.session.remove()

    outcomes = _race(concurrent_app, lambda: service.refresh(first['refresh_token'], CLIENT_ID))

    succeeded = [result for kind, result in outcomes if kind == 'ok']
    refused = [result for kind, result in outcomes if kind == 'refused']
    assert set(refused) == {'invalid_grant'}
    # The first use and at most one repeat are answered; the third presentation ends the connection
    assert 1 <= len(succeeded) <= 2, outcomes
    assert len({result['refresh_token'] for result in succeeded}) == len(succeeded)

    grant = OAuthGrant.query.one()
    assert grant.revoked_at is not None and grant.revoke_reason == settings.REVOKED_REFRESH_REUSE
    for result in succeeded:
        assert service.validate_access_token(result['access_token'], RESOURCE) is None
        db.session.remove()
        with pytest.raises(OAuthError):
            service.refresh(result['refresh_token'], CLIENT_ID)
        db.session.remove()


def test_a_refresh_and_a_revocation_at_once_never_leave_a_live_token_on_an_ended_grant(concurrent_app, ids):
    first = service.exchange_code(_code(ids), CLIENT_ID, REDIRECT, VERIFIER)
    grant_id = OAuthGrant.query.one().id
    db.session.remove()
    barrier = threading.Barrier(2)
    results = {}

    def refresher():
        with concurrent_app.app_context():
            try:
                barrier.wait(timeout=10)
                results['refresh'] = service.refresh(first['refresh_token'], CLIENT_ID)
            except OAuthError as error:
                results['refresh'] = error.error
            except Exception as exc:
                results['refresh_crash'] = repr(exc)
            finally:
                db.session.remove()

    def revoker():
        with concurrent_app.app_context():
            try:
                barrier.wait(timeout=10)
                service.revoke_grant(db.session.get(OAuthGrant, grant_id), settings.REVOKED_BY_USER)
                results['revoke'] = True
            except Exception as exc:
                results['revoke_crash'] = repr(exc)
            finally:
                db.session.remove()

    threads = [threading.Thread(target=refresher), threading.Thread(target=revoker)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert not any(thread.is_alive() for thread in threads)
    assert 'refresh_crash' not in results and 'revoke_crash' not in results, results

    # Whoever was first, the grant is ended and nothing issued for it is accepted
    assert OAuthGrant.query.one().revoked_at is not None
    assert service.validate_access_token(first['access_token'], RESOURCE) is None
    if isinstance(results['refresh'], dict):
        assert service.validate_access_token(results['refresh']['access_token'], RESOURCE) is None
        db.session.remove()
        with pytest.raises(OAuthError):
            service.refresh(results['refresh']['refresh_token'], CLIENT_ID)
