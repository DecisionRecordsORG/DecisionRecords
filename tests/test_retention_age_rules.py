"""
The four retention categories that delete by age alone (retention.AGE_RULES):

    request_log           the log of API, MCP and AI requests, 90 days
    verification_records  email confirmation and set-up records, 30 days after expiry
    access_requests       90 days after they were approved or rejected
    api_keys              90 days after they were revoked or expired

Each test puts one row just past the period and one just inside it, so a
period that is off by a day fails. They use the shared `app` fixture, so CI
also runs them on PostgreSQL (where the foreign key from the request log to
an API key is enforced).
"""

from datetime import timedelta

import pytest

import retention
from models import (
    db, User, Tenant, MaturityState, AccessRequest, EmailVerification, SetupToken, AIApiKey,
    AIInteractionLog, AIChannel, AIAction, RetentionRun, RetentionErasure,
)
from tests.retention_test_data import naive_now

NEW_CATEGORIES = (
    retention.REQUEST_LOG, retention.VERIFICATION_RECORDS, retention.ACCESS_REQUESTS, retention.API_KEYS,
)


@pytest.fixture(autouse=True)
def utc_database_session(monkeypatch):
    """As on a database session set to UTC: no waiting margin (see retention "Times")."""
    monkeypatch.setattr(retention, '_session_utc_offset_seconds', lambda: 0)


@pytest.fixture
def organisation(session):
    tenant = Tenant(domain='ages.example', name='Ages', status='active', maturity_state=MaturityState.BOOTSTRAP)
    user = User(email='keeper@ages.example', sso_domain='ages.example', auth_type='local', email_verified=True)
    user.set_name(first_name='Kay', last_name='Keeper')
    session.add_all([tenant, user])
    session.commit()
    return tenant, user


def ago(**delta):
    return naive_now() - timedelta(**delta)


def run(categories, **kwargs):
    return retention.run_retention(RetentionRun.TRIGGER_AUTOMATIC, categories=categories, **kwargs)


def log_entry(tenant, user, created_at, api_key=None, text='how do we price renewals'):
    entry = AIInteractionLog(
        user_id=user.id, tenant_id=tenant.id, api_key_id=api_key.id if api_key else None,
        channel=AIChannel.MCP, action=AIAction.SEARCH, query_text=text, created_at=created_at)
    db.session.add(entry)
    db.session.commit()
    return entry.id


def api_key(tenant, user, suffix, **dates):
    key = AIApiKey(user_id=user.id, tenant_id=tenant.id, key_hash=f'hash-{suffix}'.ljust(64, '0'),
                   key_prefix='dr_test', name=f'Key {suffix}', **dates)
    db.session.add(key)
    db.session.commit()
    return key


class TestPeriods:

    def test_the_periods_are_the_documented_ones(self):
        assert {category: days for category, (days, _) in retention.AGE_RULES.items()} == {
            'request_log': 90, 'verification_records': 30, 'access_requests': 90, 'api_keys': 90,
        }

    def test_the_daily_run_covers_them(self):
        for category in NEW_CATEGORIES:
            assert category in retention.CATEGORIES
            # Deleted by age alone, like login history: no per-run limit
            assert category not in retention.LIMITED_CATEGORIES


class TestRequestLog:

    def test_entries_older_than_90_days_go_and_newer_stay(self, app, organisation):
        tenant, user = organisation
        old = log_entry(tenant, user, ago(days=90, seconds=5))
        recent = log_entry(tenant, user, ago(days=89, hours=23))

        result = run([retention.REQUEST_LOG])['results']['request_log']

        assert (result['status'], result['affected'], result['waiting']) == ('done', 1, 1)
        assert db.session.get(AIInteractionLog, old) is None
        assert db.session.get(AIInteractionLog, recent) is not None

    def test_what_was_deleted_is_recorded_without_content(self, app, organisation):
        tenant, user = organisation
        log_entry(tenant, user, ago(days=200), text='a question naming Kay Keeper')

        run([retention.REQUEST_LOG])

        record = RetentionErasure.query.filter_by(category='request_log').one()
        assert record.entity_type == 'ai_interaction_logs'
        assert record.counts == {'rows': 1}
        assert 'Kay' not in (record.identifier or '')

    def test_nothing_waiting_writes_no_record(self, app, organisation):
        tenant, user = organisation
        log_entry(tenant, user, ago(days=1))

        result = run([retention.REQUEST_LOG])['results']['request_log']

        assert (result['affected'], result['waiting']) == (0, 0)
        assert RetentionErasure.query.count() == 0


class TestVerificationRecords:

    def verification(self, expires_at, verified=False, email='new@ages.example'):
        row = EmailVerification(
            email=email, name='New Person', token=f'token-{expires_at.isoformat()}-{verified}',
            purpose='signup', domain='ages.example', expires_at=expires_at,
            verified_at=expires_at - timedelta(hours=1) if verified else None)
        db.session.add(row)
        db.session.commit()
        return row.id

    def setup_token(self, user, expires_at, used=False):
        row = SetupToken(user_id=user.id, token_hash=f'hash-{expires_at.isoformat()}-{used}',
                         purpose=SetupToken.PURPOSE_INITIAL_SETUP, expires_at=expires_at,
                         used_at=expires_at - timedelta(hours=1) if used else None)
        db.session.add(row)
        db.session.commit()
        return row.id

    def test_records_go_30_days_after_they_expired(self, app, organisation):
        _, user = organisation
        old_unused = self.verification(ago(days=30, seconds=5))
        old_used = self.verification(ago(days=45), verified=True)
        expired_recently = self.verification(ago(days=29, hours=23))
        still_valid = self.verification(naive_now() + timedelta(hours=2))
        old_link = self.setup_token(user, ago(days=31))
        old_used_link = self.setup_token(user, ago(days=31), used=True)
        recent_link = self.setup_token(user, ago(days=2))

        result = run([retention.VERIFICATION_RECORDS])['results']['verification_records']

        assert (result['status'], result['affected'], result['waiting']) == ('done', 4, 4)
        for gone in (old_unused, old_used):
            assert db.session.get(EmailVerification, gone) is None
        for kept in (expired_recently, still_valid):
            assert db.session.get(EmailVerification, kept) is not None
        for gone in (old_link, old_used_link):
            assert db.session.get(SetupToken, gone) is None
        assert db.session.get(SetupToken, recent_link) is not None

    def test_each_table_gets_its_own_record(self, app, organisation):
        _, user = organisation
        self.verification(ago(days=60))
        self.setup_token(user, ago(days=60))

        run([retention.VERIFICATION_RECORDS])

        records = {record.entity_type: record.counts for record in
                   RetentionErasure.query.filter_by(category='verification_records').all()}
        assert records == {'email_verifications': {'rows': 1}, 'setup_tokens': {'rows': 1}}


class TestAccessRequests:

    def request(self, status, decided_days_ago=None, email='asker@ages.example', created_days_ago=400,
                processed=True):
        decided_at = ago(days=decided_days_ago, seconds=5) if decided_days_ago is not None else None
        row = AccessRequest(
            email=email, name='Asker Person', domain='ages.example', reason='I work here', status=status,
            created_at=ago(days=created_days_ago), updated_at=decided_at or ago(days=created_days_ago),
            processed_at=decided_at if processed else None)
        db.session.add(row)
        db.session.commit()
        return row.id

    def test_decided_requests_go_after_90_days_and_pending_ones_stay(self, app, organisation):
        approved_long_ago = self.request('approved', 90)
        rejected_long_ago = self.request('rejected', 120)
        approved_recently = self.request('approved', 89)
        pending_for_a_year = self.request('pending')

        result = run([retention.ACCESS_REQUESTS])['results']['access_requests']

        assert (result['status'], result['affected'], result['waiting']) == ('done', 2, 2)
        assert db.session.get(AccessRequest, approved_long_ago) is None
        assert db.session.get(AccessRequest, rejected_long_ago) is None
        assert db.session.get(AccessRequest, approved_recently) is not None
        assert db.session.get(AccessRequest, pending_for_a_year) is not None

    def test_a_request_without_a_decision_date_is_counted_from_its_last_change(self, app, organisation):
        """Older rows were decided without processed_at being filled in."""
        old = self.request('approved', 100, processed=False)
        recent = self.request('rejected', 10, processed=False)

        run([retention.ACCESS_REQUESTS])

        assert db.session.get(AccessRequest, old) is None
        assert db.session.get(AccessRequest, recent) is not None


class TestApiKeys:

    def test_revoked_and_expired_keys_go_after_90_days_and_working_keys_stay(self, app, organisation):
        tenant, user = organisation
        revoked_long_ago = api_key(tenant, user, 'a', revoked_at=ago(days=90, seconds=5)).id
        expired_long_ago = api_key(tenant, user, 'b', expires_at=ago(days=91)).id
        revoked_recently = api_key(tenant, user, 'c', revoked_at=ago(days=89)).id
        expired_recently = api_key(tenant, user, 'd', expires_at=ago(days=5)).id
        never_expires = api_key(tenant, user, 'e', created_at=ago(days=900)).id
        expires_later = api_key(tenant, user, 'f', expires_at=naive_now() + timedelta(days=30)).id
        # Revoked recently although its expiry date is long past: gone, it stopped working 91 days ago
        both = api_key(tenant, user, 'g', expires_at=ago(days=91), revoked_at=ago(days=1)).id

        result = run([retention.API_KEYS])['results']['api_keys']

        assert (result['status'], result['affected'], result['waiting']) == ('done', 3, 3)
        for gone in (revoked_long_ago, expired_long_ago, both):
            assert db.session.get(AIApiKey, gone) is None
        for kept in (revoked_recently, expired_recently, never_expires, expires_later):
            assert db.session.get(AIApiKey, kept) is not None

    def test_request_log_lines_of_a_deleted_key_stay_without_the_reference(self, app, organisation):
        tenant, user = organisation
        key = api_key(tenant, user, 'a', revoked_at=ago(days=120))
        line = log_entry(tenant, user, ago(days=3), api_key=key)

        result = run([retention.API_KEYS])['results']['api_keys']

        assert result['status'] == 'done' and result['errors'] == []
        kept = db.session.get(AIInteractionLog, line)
        assert kept is not None and kept.api_key_id is None
        record = RetentionErasure.query.filter_by(category='api_keys').one()
        assert record.counts == {'request_log_references_cleared': 1, 'rows': 1}


class TestPreviewAndRuns:

    def test_preview_counts_each_category_and_gives_its_cutoff(self, app, organisation):
        tenant, user = organisation
        log_entry(tenant, user, ago(days=100))
        log_entry(tenant, user, ago(days=101))
        api_key(tenant, user, 'a', revoked_at=ago(days=100))

        preview = retention.preview_retention()

        assert preview['request_log']['waiting'] == 2
        assert preview['api_keys']['waiting'] == 1
        assert preview['verification_records']['waiting'] == 0
        assert preview['access_requests']['waiting'] == 0
        for category in NEW_CATEGORIES:
            entry = preview[category]
            assert entry['limit'] is None and entry['would_hold'] is False
            assert entry['cutoff'].endswith('Z') and entry['items'] == []
        # Nothing was changed by looking
        assert AIInteractionLog.query.count() == 2 and AIApiKey.query.count() == 1

    def test_a_full_automatic_run_does_all_four(self, app, organisation):
        tenant, user = organisation
        key = api_key(tenant, user, 'a', expires_at=ago(days=100))
        log_entry(tenant, user, ago(days=100), api_key=key)
        db.session.add(EmailVerification(email='x@ages.example', token='t', purpose='signup',
                                         domain='ages.example', expires_at=ago(days=40)))
        db.session.add(AccessRequest(email='y@ages.example', name='Y', domain='ages.example', status='rejected',
                                     processed_at=ago(days=100), updated_at=ago(days=100)))
        db.session.commit()

        stored = run(None)

        assert stored['status'] == RetentionRun.STATUS_COMPLETED
        assert {category: stored['results'][category]['affected'] for category in NEW_CATEGORIES} == {
            'request_log': 1, 'verification_records': 1, 'access_requests': 1, 'api_keys': 1}
        assert (AIInteractionLog.query.count(), EmailVerification.query.count(),
                AccessRequest.query.count(), AIApiKey.query.count()) == (0, 0, 0, 0)

    def test_a_second_run_finds_nothing(self, app, organisation):
        tenant, user = organisation
        log_entry(tenant, user, ago(days=100))
        run(list(NEW_CATEGORIES))

        again = run(list(NEW_CATEGORIES))

        assert all(again['results'][category]['affected'] == 0 for category in NEW_CATEGORIES)

    def test_a_failure_in_one_table_is_recorded_and_the_other_table_is_still_done(
            self, app, organisation, monkeypatch):
        _, user = organisation
        db.session.add(EmailVerification(email='x@ages.example', token='t', purpose='signup',
                                         domain='ages.example', expires_at=ago(days=40)))
        db.session.add(SetupToken(user_id=user.id, token_hash='h', purpose=SetupToken.PURPOSE_INITIAL_SETUP,
                                  expires_at=ago(days=40)))
        db.session.commit()
        days, tables = retention.AGE_RULES[retention.VERIFICATION_RECORDS]

        def broken(cutoff):
            raise RuntimeError('boom')

        monkeypatch.setitem(retention.AGE_RULES, retention.VERIFICATION_RECORDS,
                            (days, ((EmailVerification, broken), tables[1])))

        result = run([retention.VERIFICATION_RECORDS])

        entry = result['results']['verification_records']
        # The count of what is waiting fails first: the category is reported as an error
        assert entry['status'] == 'error'
        assert result['status'] == RetentionRun.STATUS_ERRORS
        assert EmailVerification.query.count() == 1
