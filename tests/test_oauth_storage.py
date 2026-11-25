"""
Tests for what the public code does with the OAuth tables (both editions):

1. Housekeeping: retention.purge_expired_oauth_rows removes only rows that can
   no longer be used, and the daily thread runs it once a day.
2. Erasing an account or an organisation removes its connections.
3. A person's data export lists the applications they connected, without tokens.

The service that writes these tables is Enterprise code and is tested in
tests/test_oauth_token_service.py.
"""
import json
from datetime import datetime, timedelta

import pytest

import retention
from data_export import build_personal_data_export
from models import (
    db, GlobalRole, MaturityState, OAuthAuthorizationRequest, OAuthClient, OAuthGrant, OAuthToken,
    Tenant, TenantMembership, User,
)

NOW = datetime(2026, 11, 25, 12, 0, 0)
RESOURCE = 'https://decisions.example/api/mcp'


def _tenant(domain='example.com'):
    tenant = Tenant(domain=domain, name=domain, status='active', maturity_state=MaturityState.BOOTSTRAP)
    db.session.add(tenant)
    db.session.flush()
    return tenant


def _user(tenant, email):
    user = User(email=email, sso_domain=tenant.domain, auth_type='local', email_verified=True)
    user.set_name(first_name='Some', last_name='Person')
    db.session.add(user)
    db.session.flush()
    db.session.add(TenantMembership(user_id=user.id, tenant_id=tenant.id, global_role=GlobalRole.USER))
    db.session.flush()
    return user


def _client(client_id='https://client.example/client.json', **fields):
    client = OAuthClient(client_id=client_id, client_name='Example Client',
                         redirect_uris=['https://client.example/callback'], created_at=NOW, **fields)
    db.session.add(client)
    db.session.flush()
    return client


_counter = iter(range(1, 100000))


def _grant(user, tenant, client, **fields):
    number = next(_counter)
    values = dict(public_id=f'grant-{number}', user_id=user.id, tenant_id=tenant.id, oauth_client_id=client.id,
                  resource=RESOURCE, scopes=['decisions:read'], created_at=NOW,
                  expires_at=NOW + timedelta(days=180))
    values.update(fields)
    grant = OAuthGrant(**values)
    db.session.add(grant)
    db.session.flush()
    return grant


def _token(grant, kind=OAuthToken.KIND_ACCESS, expires_at=None, **fields):
    number = next(_counter)
    token = OAuthToken(grant_id=grant.id, kind=kind, token_hash=f'{number:064d}', created_at=NOW,
                       expires_at=expires_at or NOW + timedelta(hours=1), **fields)
    db.session.add(token)
    db.session.flush()
    return token


def _request(client, expires_at, **fields):
    number = next(_counter)
    request = OAuthAuthorizationRequest(
        public_id=f'request-{number}', client_identifier=client.client_id, oauth_client_id=client.id,
        redirect_uri='https://client.example/callback', requested_scopes=['decisions:read'],
        code_challenge='c' * 43, resource=RESOURCE, created_at=NOW, expires_at=expires_at, **fields)
    db.session.add(request)
    db.session.flush()
    return request


@pytest.fixture
def world(app):
    tenant = _tenant()
    user = _user(tenant, 'person@example.com')
    client = _client()
    db.session.commit()
    return {'tenant': tenant, 'user': user, 'client': client}


# ==================== Housekeeping ====================

class TestPurgeOfExpiredOAuthRows:

    def test_nothing_usable_is_removed(self, world):
        grant = _grant(world['user'], world['tenant'], world['client'])
        old_refresh = _token(grant, OAuthToken.KIND_REFRESH, expires_at=NOW + timedelta(days=20),
                             rotated_at=NOW - timedelta(days=10))
        _token(grant, OAuthToken.KIND_REFRESH, expires_at=NOW + timedelta(days=30), parent_id=old_refresh.id)
        _token(grant, OAuthToken.KIND_ACCESS, expires_at=NOW + timedelta(minutes=5))
        # Expired an hour ago: refused when presented, not yet worth deleting
        _token(grant, OAuthToken.KIND_ACCESS, expires_at=NOW - timedelta(hours=1))
        _request(world['client'], NOW + timedelta(minutes=5))
        db.session.commit()

        counts = retention.purge_expired_oauth_rows(NOW)

        assert not any(counts.values()), counts
        assert OAuthGrant.query.count() == 1
        assert OAuthToken.query.count() == 4
        assert OAuthAuthorizationRequest.query.count() == 1
        assert OAuthClient.query.count() == 1

    def test_expired_tokens_go_and_a_used_refresh_token_stays_until_its_own_expiry(self, world):
        grant = _grant(world['user'], world['tenant'], world['client'])
        gone = _token(grant, OAuthToken.KIND_REFRESH, expires_at=NOW - timedelta(days=2),
                      rotated_at=NOW - timedelta(days=31))
        # Its successor outlives it and must not be left pointing at a deleted row
        successor = _token(grant, OAuthToken.KIND_REFRESH, expires_at=NOW + timedelta(days=5), parent_id=gone.id)
        still_recognised = _token(grant, OAuthToken.KIND_REFRESH, expires_at=NOW + timedelta(days=3),
                                  rotated_at=NOW - timedelta(days=27))
        expired_access = _token(grant, OAuthToken.KIND_ACCESS, expires_at=NOW - timedelta(days=2))
        ids = (gone.id, successor.id, still_recognised.id, expired_access.id)
        db.session.commit()

        counts = retention.purge_expired_oauth_rows(NOW)

        assert counts['oauth_tokens'] == 2
        assert db.session.get(OAuthToken, ids[0]) is None
        assert db.session.get(OAuthToken, ids[3]) is None
        assert db.session.get(OAuthToken, ids[1]).parent_id is None
        assert db.session.get(OAuthToken, ids[2]).rotated_at is not None
        assert OAuthGrant.query.count() == 1

    def test_requests_go_once_neither_they_nor_their_code_can_be_used(self, world):
        waiting = _request(world['client'], NOW + timedelta(minutes=1))
        abandoned = _request(world['client'], NOW - timedelta(days=2))
        grant = _grant(world['user'], world['tenant'], world['client'])
        exchanged = _request(world['client'], NOW - timedelta(days=2), code_hash='e' * 64,
                             code_expires_at=NOW - timedelta(days=2), code_used_at=NOW - timedelta(days=2),
                             grant_id=grant.id)
        recent_code = _request(world['client'], NOW - timedelta(days=2), code_hash='f' * 64,
                               code_expires_at=NOW - timedelta(hours=2))
        ids = (waiting.id, abandoned.id, exchanged.id, recent_code.id)
        db.session.commit()

        counts = retention.purge_expired_oauth_rows(NOW)

        assert counts['oauth_authorization_requests'] == 2
        remaining = {row.id for row in OAuthAuthorizationRequest.query.all()}
        assert remaining == {ids[0], ids[3]}
        assert OAuthGrant.query.count() == 1  # the grant does not depend on its request

    def test_ended_grants_go_after_thirty_days_with_everything_of_theirs(self, world):
        user, tenant, client = world['user'], world['tenant'], world['client']
        working = _grant(user, tenant, client)
        _token(working)
        revoked_recently = _grant(user, tenant, client, revoked_at=NOW - timedelta(days=5), revoke_reason='user')
        revoked_long_ago = _grant(user, tenant, client, revoked_at=NOW - timedelta(days=31), revoke_reason='user',
                                  revoked_by_user_id=user.id)
        parent = _token(revoked_long_ago, OAuthToken.KIND_REFRESH, expires_at=NOW - timedelta(days=31))
        _token(revoked_long_ago, OAuthToken.KIND_REFRESH, expires_at=NOW - timedelta(days=31), parent_id=parent.id)
        _request(client, NOW - timedelta(days=200), grant_id=revoked_long_ago.id, code_hash='g' * 64,
                 code_expires_at=NOW - timedelta(days=200))
        expired_long_ago = _grant(user, tenant, client, created_at=NOW - timedelta(days=300),
                                  expires_at=NOW - timedelta(days=31))
        expired_recently = _grant(user, tenant, client, created_at=NOW - timedelta(days=190),
                                  expires_at=NOW - timedelta(days=10))
        kept = {working.id, revoked_recently.id, expired_recently.id}
        gone = {revoked_long_ago.id, expired_long_ago.id}
        db.session.commit()

        counts = retention.purge_expired_oauth_rows(NOW)

        assert counts['oauth_grants'] == 2
        assert {row.id for row in OAuthGrant.query.all()} == kept
        assert OAuthToken.query.filter(OAuthToken.grant_id.in_(gone)).count() == 0
        assert OAuthAuthorizationRequest.query.count() == 0
        assert OAuthToken.query.count() == 1

    def test_a_client_is_forgotten_only_when_unused_and_not_blocked(self, world):
        connected = world['client']
        connected.last_used_at = NOW - timedelta(days=90)
        _grant(world['user'], world['tenant'], connected)
        unused = _client('https://unused.example/client.json')
        unused.created_at = NOW - timedelta(days=90)
        recent = _client('https://recent.example/client.json')
        recent.created_at = NOW - timedelta(days=90)
        recent.last_used_at = NOW - timedelta(days=3)
        blocked = _client('https://blocked.example/client.json', disabled_at=NOW - timedelta(days=90),
                          disabled_reason='phishing')
        blocked.created_at = NOW - timedelta(days=90)
        asked = _client('https://asked.example/client.json')
        asked.created_at = NOW - timedelta(days=90)
        _request(asked, NOW + timedelta(minutes=5))
        db.session.commit()

        counts = retention.purge_expired_oauth_rows(NOW)

        assert counts['oauth_clients'] == 1
        assert {client.client_id for client in OAuthClient.query.all()} == {
            'https://client.example/client.json', 'https://recent.example/client.json',
            'https://blocked.example/client.json', 'https://asked.example/client.json',
        }

    def test_running_it_again_changes_nothing(self, world):
        grant = _grant(world['user'], world['tenant'], world['client'], revoked_at=NOW - timedelta(days=40))
        _token(grant, expires_at=NOW - timedelta(days=40))
        db.session.commit()

        assert retention.purge_expired_oauth_rows(NOW)['oauth_grants'] == 1
        assert not any(retention.purge_expired_oauth_rows(NOW).values())

    def test_empty_tables_are_fine(self, app):
        """The Community Edition never writes these tables."""
        assert not any(retention.purge_expired_oauth_rows(NOW).values())

    def test_the_daily_thread_purges_once_a_day(self, world):
        grant = _grant(world['user'], world['tenant'], world['client'], revoked_at=NOW - timedelta(days=40))
        grant_id = grant.id
        db.session.commit()
        state = {}

        assert retention.purge_oauth_rows_if_due(state, NOW) is True
        assert db.session.get(OAuthGrant, grant_id) is None

        _grant(world['user'], world['tenant'], world['client'], revoked_at=NOW - timedelta(days=40))
        db.session.commit()
        assert retention.purge_oauth_rows_if_due(state, NOW + timedelta(hours=3)) is False
        assert OAuthGrant.query.count() == 1

        assert retention.purge_oauth_rows_if_due(state, NOW + timedelta(days=1)) is True
        assert OAuthGrant.query.count() == 0

    def test_a_failed_purge_is_tried_again_the_same_day(self, world, monkeypatch):
        state = {}

        def broken(now=None):
            raise RuntimeError('database went away')

        monkeypatch.setattr(retention, 'purge_expired_oauth_rows', broken)
        with pytest.raises(RuntimeError):
            retention.purge_oauth_rows_if_due(state, NOW)
        monkeypatch.undo()

        assert retention.purge_oauth_rows_if_due(state, NOW) is True

    def test_the_purge_does_not_depend_on_the_automatic_retention_setting(self, world, monkeypatch):
        monkeypatch.setenv(retention.AUTO_RUN_ENV, 'false')
        _grant(world['user'], world['tenant'], world['client'], revoked_at=NOW - timedelta(days=40))
        db.session.commit()

        assert retention.purge_oauth_rows_if_due({}, NOW) is True
        assert OAuthGrant.query.count() == 0


# ==================== Erasure ====================

class TestErasureRemovesConnections:

    def _connections(self, user, tenant, client):
        grant = _grant(user, tenant, client)
        parent = _token(grant, OAuthToken.KIND_REFRESH, rotated_at=NOW)
        _token(grant, OAuthToken.KIND_REFRESH, parent_id=parent.id)
        _token(grant, OAuthToken.KIND_ACCESS, parent_id=parent.id)
        _request(client, NOW + timedelta(minutes=5), user_id=user.id, tenant_id=tenant.id, grant_id=grant.id,
                 code_hash=f'{next(_counter):064d}')
        _request(client, NOW + timedelta(minutes=5), user_id=user.id)
        return grant

    def test_anonymising_an_account_deletes_its_connections_and_no_one_elses(self, world):
        tenant, client = world['tenant'], world['client']
        leaving = world['user']
        staying = _user(tenant, 'colleague@example.com')
        self._connections(leaving, tenant, client)
        kept = self._connections(staying, tenant, client)
        # The leaving user once ended a colleague's connection as an admin
        ended = _grant(staying, tenant, client, revoked_at=NOW, revoked_by_user_id=leaving.id, revoke_reason='admin')
        leaving_id, kept_id, ended_id = leaving.id, kept.id, ended.id
        db.session.commit()

        assert retention.anonymize_user(leaving_id) is True

        assert OAuthGrant.query.filter_by(user_id=leaving_id).count() == 0
        assert OAuthAuthorizationRequest.query.filter_by(user_id=leaving_id).count() == 0
        assert {grant.id for grant in OAuthGrant.query.all()} == {kept_id, ended_id}
        assert OAuthToken.query.count() == 3
        assert {token.grant_id for token in OAuthToken.query.all()} == {kept_id}
        assert OAuthAuthorizationRequest.query.count() == 2
        assert OAuthClient.query.count() == 1

    def test_erasing_a_tenant_deletes_its_connections_and_keeps_the_client(self, app):
        from tests.retention_test_data import make_full_tenant, expire_tenant
        erased = make_full_tenant('erased.test', 'one')
        kept = make_full_tenant('kept.test', 'two')
        erased_id, kept_id = erased['tenant'].id, kept['tenant'].id
        assert OAuthGrant.query.filter_by(tenant_id=erased_id).count() >= 1
        assert OAuthGrant.query.filter_by(tenant_id=kept_id).count() >= 1
        tokens_of_kept = OAuthToken.query.join(OAuthGrant, OAuthToken.grant_id == OAuthGrant.id).filter(
            OAuthGrant.tenant_id == kept_id).count()
        expire_tenant(db.session.get(Tenant, erased_id))

        from models import RetentionRun
        retention.run_retention(RetentionRun.TRIGGER_SUPER_ADMIN, categories=[retention.TENANTS])

        assert db.session.get(Tenant, erased_id) is None
        assert OAuthGrant.query.filter_by(tenant_id=erased_id).count() == 0
        assert OAuthAuthorizationRequest.query.filter_by(tenant_id=erased_id).count() == 0
        assert OAuthGrant.query.filter_by(tenant_id=kept_id).count() >= 1
        assert OAuthToken.query.count() == tokens_of_kept
        assert OAuthClient.query.count() == 1


# ==================== Data export ====================

class TestExportListsConnectedApps:

    def test_connections_are_listed_without_any_token(self, world):
        user, tenant, client = world['user'], world['tenant'], world['client']
        grant = _grant(user, tenant, client, scopes=['decisions:read', 'decisions:write'],
                       last_used_at=NOW + timedelta(hours=1))
        token = _token(grant)
        _grant(user, tenant, client, revoked_at=NOW + timedelta(days=1), revoke_reason='user')
        other = _user(tenant, 'colleague@example.com')
        _grant(other, tenant, client)
        token_hash = token.token_hash
        db.session.commit()

        export = build_personal_data_export(db.session.get(User, user.id))

        apps = export['connected_apps']
        assert len(apps) == 2
        assert apps[0] == {
            'application': 'Example Client',
            'application_id': 'https://client.example/client.json',
            'tenant_domain': 'example.com',
            'resource': RESOURCE,
            'scopes': ['decisions:read', 'decisions:write'],
            'connected_at': NOW.isoformat(),
            'last_used_at': (NOW + timedelta(hours=1)).isoformat(),
            'expires_at': (NOW + timedelta(days=180)).isoformat(),
            'revoked_at': None,
            'revoke_reason': None,
        }
        assert apps[1]['revoke_reason'] == 'user'
        assert token_hash not in json.dumps(export, default=str)

    def test_no_connections_gives_an_empty_list(self, world):
        export = build_personal_data_export(db.session.get(User, world['user'].id))
        assert export['connected_apps'] == []
