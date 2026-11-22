"""
The retention routine (retention.py): accounts, decisions, login history,
inquiries, limits, preview and the run record. Tenant erase has its own file.

These use the shared `app` fixture, so CI also runs them on PostgreSQL.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest

import retention
from models import (
    db, User, Tenant, TenantMembership, AuditLog, ArchitectureDecision, DecisionHistory, DecisionComment,
    DecisionSpace, DecisionRelationship, LoginHistory, Inquiry, WebAuthnCredential, Subscription,
    UserConsent, SetupToken, AccessRequest, EmailVerification, AIApiKey, SlackUserMapping,
    TeamsUserMapping, RetentionRun, RetentionErasure, SystemConfig, decision_infrastructure,
)
from tests.retention_test_data import (
    make_full_tenant, make_user, make_decision, soft_delete, expire_tenant, snapshot, naive_now,
)

RECORD_TABLES = ('retention_runs', 'retention_erasures')


@pytest.fixture(autouse=True)
def utc_database_session(request, monkeypatch):
    """Run as on a database session set to UTC (what CI and the images use).

    A PostgreSQL session in another zone makes retention wait some hours past
    every due date (retention.safety_margin), which the to-the-second tests
    below would trip over. Tests that ask for `real_session_offset` get the
    real behaviour.
    """
    if 'real_session_offset' not in request.fixturenames:
        monkeypatch.setattr(retention, '_session_utc_offset_seconds', lambda: 0)


def run(categories=None, trigger=RetentionRun.TRIGGER_AUTOMATIC, **kwargs):
    return retention.run_retention(trigger, categories=categories, **kwargs)


def schedule_deletion(user, due_in):
    user.deletion_requested_at = naive_now() - timedelta(days=7)
    user.deletion_scheduled_at = naive_now() + due_in
    db.session.commit()


def old_login(days_ago, email='someone@example.com'):
    entry = LoginHistory(email=email, login_method='password', success=True, ip_address='203.0.113.1',
                         created_at=naive_now() - timedelta(days=days_ago))
    db.session.add(entry)
    db.session.commit()
    return entry.id


def old_inquiry(days_ago):
    inquiry = Inquiry(source='contact', name='Sender', email='sender@example.org', message='Hello',
                      created_at=naive_now() - timedelta(days=days_ago))
    db.session.add(inquiry)
    db.session.commit()
    return inquiry.id


# ==================== Accounts ====================

class TestAccounts:
    def test_account_past_its_grace_date_is_anonymised_and_nothing_personal_is_left(self, app, session):
        data = make_full_tenant('team.example', 'tea')
        member = data['member']
        member_id, email = member.id, member.email
        schedule_deletion(member, timedelta(seconds=-1))

        result = run([retention.ACCOUNTS])['results']['accounts']

        assert result['status'] == 'done' and result['affected'] == 1
        user = db.session.get(User, member_id)
        assert user.is_anonymized and user.deleted_at is not None
        assert user.email.endswith('@anonymized.local') and user.name == 'Former Member'
        assert user.first_name is None and user.last_name is None
        assert user.password_hash is None and user.sso_subject is None and user.aad_object_id is None

        assert WebAuthnCredential.query.filter_by(user_id=member_id).count() == 0
        assert TenantMembership.query.filter_by(user_id=member_id).count() == 0
        assert Subscription.query.filter_by(user_id=member_id).count() == 0
        assert SetupToken.query.filter_by(user_id=member_id).count() == 0
        assert SlackUserMapping.query.filter_by(user_id=member_id).count() == 0
        assert TeamsUserMapping.query.filter_by(user_id=member_id).count() == 0
        assert UserConsent.query.filter_by(user_id=member_id).one().ip_address is None
        assert AIApiKey.query.filter_by(user_id=member_id).one().revoked_at is not None
        entry = LoginHistory.query.filter_by(user_id=member_id).one()
        assert entry.email == user.email and entry.ip_address is None and entry.user_agent is None
        inquiry = Inquiry.query.filter_by(source='feedback').one()
        assert inquiry.email is None and inquiry.name is None and inquiry.message is None
        assert AuditLog.query.one().details == {'email': 'deleted-user'}

        # Contributions stay, without the person
        decision = db.session.get(ArchitectureDecision, data['decisions'][0].id)
        assert decision.title and decision.created_by_id is None
        assert decision.owner_id is None and decision.owner_email is None

        # No row anywhere still carries the address
        dump = json.dumps(snapshot(exclude=RECORD_TABLES), default=str)
        assert email not in dump

        # The other member is untouched
        admin = db.session.get(User, data['admin'].id)
        assert admin.email == 'admin@team.example' and not admin.is_anonymized
        assert db.session.get(ArchitectureDecision, data['decisions'][1].id).owner_email == admin.email

        record = RetentionErasure.query.one()
        assert (record.category, record.entity_type, record.entity_id) == ('accounts', 'user', member_id)
        assert record.identifier is None
        assert email not in json.dumps(record.to_dict())

    def test_requests_and_verifications_sent_to_the_address_are_removed(self, app, session):
        user = make_user('team.example', 'leaver')
        db.session.add_all([
            AccessRequest(email='Leaver@team.example', name='Leaver Person', domain='team.example'),
            AccessRequest(email='stays@team.example', name='Stays Person', domain='team.example'),
            EmailVerification(email=user.email, token='t1', domain='team.example',
                              expires_at=naive_now() + timedelta(days=1)),
            SetupToken(email=user.email, token_hash='h1', expires_at=naive_now() + timedelta(days=1)),
        ])
        schedule_deletion(user, timedelta(minutes=-5))

        assert run([retention.ACCOUNTS])['results']['accounts']['affected'] == 1

        assert [r.email for r in AccessRequest.query.all()] == ['stays@team.example']
        assert EmailVerification.query.count() == 0
        assert SetupToken.query.count() == 0

    def test_account_due_one_second_from_now_is_not_touched(self, app, session):
        user = make_user('team.example', 'waiting')
        now = naive_now()
        user.deletion_scheduled_at = now + timedelta(seconds=1)
        db.session.commit()
        before = snapshot(exclude=RECORD_TABLES)

        result = run([retention.ACCOUNTS], now=now)['results']['accounts']

        assert result['waiting'] == 0 and result['affected'] == 0
        assert snapshot(exclude=RECORD_TABLES) == before
        assert run([retention.ACCOUNTS], now=now + timedelta(seconds=1))['results']['accounts']['affected'] == 1

    def test_aware_now_in_another_zone_means_the_same_instant(self, app, session):
        user = make_user('team.example', 'zone')
        now = naive_now()
        user.deletion_scheduled_at = now + timedelta(hours=1)
        db.session.commit()
        zone = timezone(timedelta(hours=-8))
        aware_now = now.replace(tzinfo=timezone.utc).astimezone(zone)

        assert run([retention.ACCOUNTS], now=aware_now)['results']['accounts']['waiting'] == 0
        later = run([retention.ACCOUNTS], now=aware_now + timedelta(hours=2))
        assert later['results']['accounts']['affected'] == 1

    def test_cancelled_deletion_is_not_touched(self, app, session):
        user = make_user('team.example', 'stayer')
        schedule_deletion(user, timedelta(days=-1))
        # What POST /api/user/cancel-deletion does
        user.deletion_requested_at = None
        user.deletion_scheduled_at = None
        db.session.commit()
        before = snapshot(exclude=RECORD_TABLES)

        assert run([retention.ACCOUNTS])['results']['accounts']['waiting'] == 0
        assert snapshot(exclude=RECORD_TABLES) == before

    def test_deletion_cancelled_after_listing_is_skipped_at_the_recheck(self, app, session, monkeypatch):
        user = make_user('team.example', 'changed')
        schedule_deletion(user, timedelta(hours=-1))
        user_id = user.id
        real = retention._due_ids

        def list_then_cancel(category, now, cap=None):
            ids = real(category, now, cap)
            db.session.get(User, user_id).deletion_scheduled_at = None
            db.session.commit()
            return ids

        monkeypatch.setattr(retention, '_due_ids', list_then_cancel)
        result = run([retention.ACCOUNTS])['results']['accounts']

        assert result['waiting'] == 1 and result['affected'] == 0
        assert db.session.get(User, user_id).email == 'changed@team.example'
        assert RetentionErasure.query.count() == 0

    def test_account_from_before_the_anonymised_column_is_still_found(self, app, session):
        user = make_user('team.example', 'legacy')
        schedule_deletion(user, timedelta(hours=-1))
        db.session.execute(User.__table__.update().where(User.id == user.id).values(is_anonymized=None))
        db.session.commit()

        assert run([retention.ACCOUNTS])['results']['accounts']['affected'] == 1

    def test_second_run_changes_nothing(self, app, session):
        user = make_user('team.example', 'once')
        schedule_deletion(user, timedelta(hours=-1))
        run([retention.ACCOUNTS])
        after_first = snapshot(exclude=RECORD_TABLES)

        again = run([retention.ACCOUNTS])['results']['accounts']

        assert again['waiting'] == 0 and again['affected'] == 0
        assert snapshot(exclude=RECORD_TABLES) == after_first

    def test_one_failing_account_is_rolled_back_recorded_and_the_others_are_done(self, app, session, monkeypatch):
        first = make_user('team.example', 'first')
        broken = make_user('team.example', 'broken')
        last = make_user('team.example', 'last')
        for index, user in enumerate((first, broken, last)):
            user.deletion_scheduled_at = naive_now() - timedelta(hours=3 - index)
        db.session.commit()
        broken_id = broken.id
        real = retention._anonymise_user_record

        def fail_for_one(user):
            counts = real(user)
            if user.id == broken_id:
                raise ValueError('boom')
            return counts

        monkeypatch.setattr(retention, '_anonymise_user_record', fail_for_one)
        result = run([retention.ACCOUNTS])['results']['accounts']

        assert result['status'] == 'error' and result['affected'] == 2 and result['error_count'] == 1
        assert result['errors'] == [{'entity_id': broken_id, 'error': 'ValueError: boom'}]
        still = db.session.get(User, broken_id)
        assert still.email == 'broken@team.example' and not still.is_anonymized and still.password_hash
        assert sorted(r.entity_id for r in RetentionErasure.query.all()) == sorted([first.id, last.id])


# ==================== Decisions ====================

class TestDecisions:
    def _tenant(self):
        return make_full_tenant('team.example', 'tea')

    def test_expired_decision_and_everything_attached_is_erased_and_the_rest_stays(self, app, session):
        data = self._tenant()
        first, second = data['decisions']
        first_id, second_id = first.id, second.id
        soft_delete(first, naive_now() - timedelta(seconds=1), by=data['member'])
        db.session.commit()

        result = run([retention.DECISIONS])['results']['decisions']

        assert result['status'] == 'done' and result['affected'] == 1, result
        assert db.session.get(ArchitectureDecision, first_id) is None
        assert DecisionHistory.query.filter_by(decision_id=first_id).count() == 0
        assert DecisionComment.query.filter_by(decision_id=first_id).count() == 0
        assert DecisionSpace.query.filter_by(decision_id=first_id).count() == 0
        assert DecisionRelationship.query.count() == 0
        assert db.session.execute(decision_infrastructure.select()).all() == []
        assert db.session.get(ArchitectureDecision, second_id) is not None
        assert db.session.get(Tenant, data['tenant'].id) is not None
        assert User.query.count() == 2

        record = RetentionErasure.query.one()
        assert (record.category, record.entity_type, record.entity_id) == ('decisions', 'decision', first_id)
        assert record.identifier == 'team.example#1'
        assert record.counts == {'decision_infrastructure': 1, 'decision_relationships': 1,
                                 'decision_history': 1, 'decision_comments': 1, 'decision_spaces': 1}
        assert 'Decision 1' not in json.dumps(record.to_dict())

    def test_decision_expiring_one_second_from_now_is_not_touched(self, app, session):
        data = self._tenant()
        now = naive_now()
        soft_delete(data['decisions'][0], now + timedelta(seconds=1))
        db.session.commit()
        before = snapshot(exclude=RECORD_TABLES)

        assert run([retention.DECISIONS], now=now)['results']['decisions']['waiting'] == 0
        assert snapshot(exclude=RECORD_TABLES) == before
        later = run([retention.DECISIONS], now=now + timedelta(seconds=1))
        assert later['results']['decisions']['affected'] == 1

    def test_restored_decision_is_not_touched(self, app, session):
        data = self._tenant()
        decision = data['decisions'][0]
        soft_delete(decision, naive_now() - timedelta(days=1))
        db.session.commit()
        # What POST /api/decisions/<id>/restore does
        decision.deleted_at = None
        decision.deleted_by_id = None
        decision.deletion_expires_at = None
        db.session.commit()
        before = snapshot(exclude=RECORD_TABLES)

        assert run([retention.DECISIONS])['results']['decisions']['waiting'] == 0
        assert snapshot(exclude=RECORD_TABLES) == before

    def test_decision_restored_after_listing_is_skipped_at_the_recheck(self, app, session, monkeypatch):
        data = self._tenant()
        decision_id = data['decisions'][0].id
        soft_delete(data['decisions'][0], naive_now() - timedelta(hours=1))
        db.session.commit()
        real = retention._due_ids

        def list_then_restore(category, now, cap=None):
            ids = real(category, now, cap)
            decision = db.session.get(ArchitectureDecision, decision_id)
            decision.deleted_at = None
            decision.deletion_expires_at = None
            db.session.commit()
            return ids

        monkeypatch.setattr(retention, '_due_ids', list_then_restore)
        result = run([retention.DECISIONS])['results']['decisions']

        assert result['affected'] == 0
        assert db.session.get(ArchitectureDecision, decision_id) is not None
        assert DecisionHistory.query.filter_by(decision_id=decision_id).count() == 1

    def test_soft_deleted_decision_without_an_expiry_date_is_not_touched(self, app, session):
        data = self._tenant()
        data['decisions'][0].deleted_at = naive_now() - timedelta(days=400)
        db.session.commit()

        assert run([retention.DECISIONS])['results']['decisions']['waiting'] == 0

    def test_decisions_of_a_soft_deleted_tenant_wait_for_the_tenant(self, app, session):
        data = self._tenant()
        soft_delete(data['decisions'][0], naive_now() - timedelta(days=2))
        tenant = data['tenant']
        tenant.deleted_at = naive_now() - timedelta(days=1)
        tenant.deletion_expires_at = naive_now() + timedelta(days=29)
        tenant.status = 'deleted'
        db.session.commit()

        assert run([retention.DECISIONS])['results']['decisions']['waiting'] == 0
        assert ArchitectureDecision.query.count() == 2

    def test_second_run_changes_nothing(self, app, session):
        data = self._tenant()
        soft_delete(data['decisions'][0], naive_now() - timedelta(hours=1))
        db.session.commit()
        run([retention.DECISIONS])
        after_first = snapshot(exclude=RECORD_TABLES)

        assert run([retention.DECISIONS])['results']['decisions']['affected'] == 0
        assert snapshot(exclude=RECORD_TABLES) == after_first


# ==================== Login history and inquiries ====================

class TestAgeBasedDeletes:
    def test_login_history_older_than_90_days_is_deleted_and_newer_kept(self, app, session):
        old_id = old_login(91)
        edge_id = old_login(89)

        result = run([retention.LOGIN_HISTORY])['results']['login_history']

        assert result == {'status': 'done', 'affected': 1, 'waiting': 1, 'limit': None,
                          'hold_reason': None, 'errors': [], 'error_count': 0}
        assert db.session.get(LoginHistory, old_id) is None
        assert db.session.get(LoginHistory, edge_id) is not None
        record = RetentionErasure.query.one()
        assert record.category == 'login_history' and record.counts == {'rows': 1}
        assert record.identifier.startswith('created before ')

    def test_login_history_boundary_is_exact(self, app, session):
        now = naive_now()
        entry = LoginHistory(email='a@example.com', login_method='password', success=True,
                             created_at=now - timedelta(days=90) + timedelta(seconds=1))
        db.session.add(entry)
        db.session.commit()

        assert run([retention.LOGIN_HISTORY], now=now)['results']['login_history']['affected'] == 0
        later = run([retention.LOGIN_HISTORY], now=now + timedelta(seconds=2))
        assert later['results']['login_history']['affected'] == 1

    def test_inquiries_older_than_24_months_are_deleted_and_newer_kept(self, app, session):
        old_id = old_inquiry(Inquiry.RETENTION_DAYS + 1)
        new_id = old_inquiry(Inquiry.RETENTION_DAYS - 1)

        result = run([retention.INQUIRIES])['results']['inquiries']

        assert result['affected'] == 1
        assert db.session.get(Inquiry, old_id) is None
        assert db.session.get(Inquiry, new_id) is not None
        assert RetentionErasure.query.one().counts == {'rows': 1}

    def test_a_large_backlog_of_old_rows_is_not_held_back(self, app, session):
        db.session.add_all([
            LoginHistory(email=f'u{i}@example.com', login_method='password', success=True,
                         created_at=naive_now() - timedelta(days=400))
            for i in range(250)
        ])
        db.session.commit()

        result = run()['results']['login_history']

        assert result['status'] == 'done' and result['affected'] == 250
        assert LoginHistory.query.count() == 0

    def test_nothing_to_delete_writes_no_record(self, app, session):
        old_login(1)
        result = run([retention.LOGIN_HISTORY, retention.INQUIRIES])
        assert result['status'] == RetentionRun.STATUS_COMPLETED
        assert RetentionErasure.query.count() == 0


# ==================== Limits, preview, releasing ====================

class TestLimits:
    def _users_due(self, count, hours_ago=1):
        users = []
        for index in range(count):
            user = make_user('team.example', f'due{index}')
            user.deletion_scheduled_at = naive_now() - timedelta(hours=hours_ago, minutes=index)
            users.append(user)
        db.session.commit()
        return [user.id for user in users]

    def test_defaults(self, app, session):
        assert retention.get_limits() == {'accounts': 10, 'decisions': 50, 'tenants': 1}
        assert retention.get_backlog_days() == 7
        settings = retention.get_settings()
        assert settings['auto_run_enabled'] is True and settings['auto_run_active'] is True

    def test_at_the_limit_runs_and_one_over_holds_back(self, app, session):
        SystemConfig.set(SystemConfig.KEY_RETENTION_LIMIT_ACCOUNTS, 3)
        self._users_due(3)
        assert run([retention.ACCOUNTS])['results']['accounts']['affected'] == 3

        self._users_due(4)
        before = snapshot(exclude=RECORD_TABLES)
        held = run([retention.ACCOUNTS])
        assert held['status'] == RetentionRun.STATUS_HELD_BACK
        assert held['results']['accounts'] == {
            'status': 'held_back', 'affected': 0, 'waiting': 4, 'limit': 3,
            'hold_reason': 'over_limit', 'errors': []}
        assert snapshot(exclude=RECORD_TABLES) == before

    def test_a_held_back_category_does_not_stop_the_others(self, app, session):
        SystemConfig.set(SystemConfig.KEY_RETENTION_LIMIT_ACCOUNTS, 1)
        self._users_due(2)
        old_login(120)
        old_inquiry(Inquiry.RETENTION_DAYS + 5)

        results = run()['results']

        assert results['accounts']['status'] == 'held_back'
        assert results['login_history']['affected'] == 1
        assert results['inquiries']['affected'] == 1
        assert User.query.filter_by(is_anonymized=True).count() == 0

    def test_limit_of_zero_always_holds_back(self, app, session):
        SystemConfig.set(SystemConfig.KEY_RETENTION_LIMIT_ACCOUNTS, 0)
        self._users_due(1)
        assert run([retention.ACCOUNTS])['results']['accounts']['status'] == 'held_back'

    def test_few_items_long_overdue_are_held_back_as_a_backlog(self, app, session):
        self._users_due(2, hours_ago=24 * 30)
        before = snapshot(exclude=RECORD_TABLES)

        result = run([retention.ACCOUNTS])['results']['accounts']

        assert result['status'] == 'held_back' and result['hold_reason'] == 'backlog'
        assert snapshot(exclude=RECORD_TABLES) == before

    def test_backlog_check_can_be_turned_off(self, app, session):
        SystemConfig.set(SystemConfig.KEY_RETENTION_BACKLOG_DAYS, 0)
        self._users_due(2, hours_ago=24 * 30)
        assert run([retention.ACCOUNTS])['results']['accounts']['affected'] == 2

    def test_cron_and_plain_super_admin_runs_are_held_back_too(self, app, session):
        SystemConfig.set(SystemConfig.KEY_RETENTION_LIMIT_ACCOUNTS, 1)
        self._users_due(2)
        for trigger in (RetentionRun.TRIGGER_CRON, RetentionRun.TRIGGER_SUPER_ADMIN):
            assert run(trigger=trigger)['results']['accounts']['status'] == 'held_back'

    def test_release_needs_every_category_named_with_the_count_seen(self, app, session):
        self._users_due(2)
        assert retention.check_release(None, {})[1][1] == 400
        assert retention.check_release([], {})[1][1] == 400
        assert retention.check_release(['everything'], {'everything': 1})[1][1] == 400
        assert retention.check_release(['accounts'], None)[1][1] == 400
        assert retention.check_release(['accounts'], {})[1][1] == 400
        assert retention.check_release(['accounts'], {'accounts': '2x'})[1][1] == 400
        assert retention.check_release(['accounts'], {'accounts': True})[1][1] == 400
        assert retention.check_release(['accounts'], {'accounts': -1})[1][1] == 400
        assert retention.check_release(['accounts'], {'accounts': 2}) == ({'accounts': 2}, None)

    def test_release_is_refused_when_more_are_waiting_than_were_confirmed(self, app, session):
        self._users_due(3)
        release, problem = retention.check_release(['accounts'], {'accounts': 2})
        assert release is None
        message, status, extra = problem
        assert status == 409 and extra == {'waiting': {'accounts': 3}}
        assert User.query.filter_by(is_anonymized=True).count() == 0

    def test_release_never_processes_more_than_the_confirmed_count(self, app, session):
        SystemConfig.set(SystemConfig.KEY_RETENTION_LIMIT_ACCOUNTS, 1)
        ids = self._users_due(5)

        result = run([retention.ACCOUNTS], trigger=RetentionRun.TRIGGER_SUPER_ADMIN,
                     release={'accounts': 3})['results']['accounts']

        assert result['status'] == 'done' and result['affected'] == 3 and result['waiting'] == 5
        # Oldest due first
        anonymised = sorted(u.id for u in User.query.filter_by(is_anonymized=True).all())
        assert anonymised == sorted(ids[-3:])

    def test_release_only_lifts_the_limit_for_the_categories_named(self, app, session):
        SystemConfig.set(SystemConfig.KEY_RETENTION_LIMIT_ACCOUNTS, 1)
        SystemConfig.set(SystemConfig.KEY_RETENTION_LIMIT_DECISIONS, 0)
        self._users_due(2)
        data = make_full_tenant('other.example', 'oth')
        soft_delete(data['decisions'][0], naive_now() - timedelta(hours=1))
        db.session.commit()

        results = run(trigger=RetentionRun.TRIGGER_SUPER_ADMIN, release={'accounts': 2})['results']

        assert results['accounts']['affected'] == 2
        assert results['decisions']['status'] == 'held_back'

    def test_unknown_category_is_refused_before_anything_runs(self, app, session):
        with pytest.raises(ValueError):
            run(['accounts', 'everything'])
        assert RetentionRun.query.count() == 0

    def test_settings_are_validated_and_saved_together(self, app, session):
        assert retention.save_settings({'limits': {'accounts': 5, 'tenants': 'many'}}) is not None
        assert retention.get_limits()['accounts'] == 10
        assert retention.save_settings({'limits': {'users': 5}}) is not None
        assert retention.save_settings({'limits': [1, 2]}) is not None
        assert retention.save_settings({'limits': {'accounts': -1}}) is not None
        assert retention.save_settings({'limits': {'accounts': 1.5}}) is not None
        assert retention.save_settings({'auto_run_enabled': 'no'}) is not None
        assert retention.save_settings({'backlog_days': 99999}) is not None

        assert retention.save_settings({
            'auto_run_enabled': False, 'limits': {'accounts': 5, 'decisions': 20, 'tenants': 0},
            'backlog_days': 14}) is None
        settings = retention.get_settings()
        assert settings['auto_run_enabled'] is False and settings['auto_run_active'] is False
        assert settings['limits'] == {'accounts': 5, 'decisions': 20, 'tenants': 0}
        assert settings['backlog_days'] == 14

    def test_environment_switch_turns_the_automatic_run_off(self, app, session, monkeypatch):
        for value in ('false', '0', 'off', 'No'):
            monkeypatch.setenv('RETENTION_AUTO_RUN', value)
            settings = retention.get_settings()
            assert settings['auto_run_disabled_by_environment'] is True
            assert settings['auto_run_active'] is False and settings['auto_run_enabled'] is True
        monkeypatch.setenv('RETENTION_AUTO_RUN', 'true')
        assert retention.get_settings()['auto_run_active'] is True


class TestPreview:
    def test_preview_reports_what_would_be_affected_and_changes_nothing(self, app, session):
        data = make_full_tenant('team.example', 'tea')
        gone = make_full_tenant('gone.example', 'gon')
        schedule_deletion(data['member'], timedelta(hours=-2))
        soft_delete(data['decisions'][1], naive_now() - timedelta(hours=3))
        db.session.commit()
        expire_tenant(gone['tenant'])
        old_login(100)
        old_inquiry(Inquiry.RETENTION_DAYS + 1)
        before = snapshot()

        preview = retention.preview_retention()

        assert snapshot() == before
        assert set(preview) == set(retention.CATEGORIES)
        assert {category: entry['waiting'] for category, entry in preview.items()} == {
            'accounts': 1, 'decisions': 1, 'tenants': 1, 'login_history': 1, 'inquiries': 1}
        assert all(entry['would_hold'] is False for entry in preview.values())
        assert [item['label'] for item in preview['accounts']['items']] == ['member@team.example']
        assert [item['label'] for item in preview['decisions']['items']] == ['team.example#2']
        tenant_item = preview['tenants']['items'][0]
        assert tenant_item['label'] == 'gone.example'
        assert tenant_item['counts'] == {'users': 2, 'decisions': 2, 'spaces': 1, 'memberships': 2}
        assert preview['tenants']['limit'] == 1 and preview['login_history']['limit'] is None
        assert preview['login_history']['cutoff'].endswith('Z')
        assert preview['accounts']['oldest_due_at'].endswith('Z')

    def test_preview_matches_what_the_run_then_does(self, app, session):
        data = make_full_tenant('team.example', 'tea')
        schedule_deletion(data['member'], timedelta(hours=-2))
        old_login(100)
        preview = retention.preview_retention()

        results = run()['results']

        assert {c: r['affected'] for c, r in results.items()} == {c: p['waiting'] for c, p in preview.items()}
        assert all(entry['waiting'] == 0 for entry in retention.preview_retention().values())

    def test_preview_says_when_an_automatic_run_would_hold_back(self, app, session):
        SystemConfig.set(SystemConfig.KEY_RETENTION_LIMIT_ACCOUNTS, 0)
        user = make_user('team.example', 'held')
        schedule_deletion(user, timedelta(hours=-1))

        preview = retention.preview_retention(categories=['accounts'])

        assert list(preview) == ['accounts']
        assert preview['accounts']['would_hold'] is True and preview['accounts']['hold_reason'] == 'over_limit'

    def test_preview_item_list_is_capped_and_says_so(self, app, session, monkeypatch):
        monkeypatch.setattr(retention, 'PREVIEW_ITEM_LIMIT', 2)
        for index in range(3):
            user = make_user('team.example', f'p{index}')
            user.deletion_scheduled_at = naive_now() - timedelta(hours=1)
        db.session.commit()

        entry = retention.preview_retention()['accounts']

        assert entry['waiting'] == 3 and len(entry['items']) == 2 and entry['items_truncated'] is True


# ==================== The run record ====================

class TestRunRecord:
    def test_run_is_stored_with_trigger_counts_and_duration(self, app, session):
        old_login(100)
        result = run(trigger=RetentionRun.TRIGGER_CRON)

        stored = RetentionRun.query.one()
        assert result == stored.to_dict()
        assert stored.trigger == 'cron' and stored.status == 'completed' and stored.claim_key is None
        assert stored.categories == list(retention.CATEGORIES)
        assert set(stored.results) == set(retention.CATEGORIES)
        assert stored.results['login_history']['affected'] == 1
        assert stored.finished_at is not None and stored.finished_at >= stored.started_at
        assert stored.duration_ms is not None and stored.duration_ms >= 0
        assert result['started_at'].endswith('Z')

    def test_legacy_result_keys(self, app, session):
        old_login(100)
        result = run()
        assert retention.legacy_results(result) == {
            'anonymized_users': 0, 'purged_decisions': 0, 'purged_tenants': 0,
            'cleaned_login_history': 1, 'purged_inquiries': 0}
        assert retention.held_back(result) == {} and retention.run_errors(result) == {}

    def test_a_category_that_fails_outright_is_recorded_and_the_rest_still_run(self, app, session, monkeypatch):
        old_login(100)
        old_inquiry(Inquiry.RETENTION_DAYS + 1)
        user = make_user('team.example', 'fine')
        schedule_deletion(user, timedelta(hours=-1))
        real = retention._run_category

        def explode(category, now, run_id, cap):
            if category == retention.LOGIN_HISTORY:
                db.session.add(LoginHistory(email='half@example.com', login_method='password', success=True))
                db.session.flush()
                raise RuntimeError('database went away')
            return real(category, now, run_id, cap)

        monkeypatch.setattr(retention, '_run_category', explode)
        result = run()

        assert result['status'] == RetentionRun.STATUS_ERRORS
        failed = result['results']['login_history']
        assert failed['status'] == 'error' and failed['affected'] == 0
        assert failed['errors'] == [{'entity_id': None, 'error': 'RuntimeError: database went away'}]
        assert retention.run_errors(result) == {'login_history': failed['errors']}
        # The half-done work was rolled back
        assert LoginHistory.query.filter_by(email='half@example.com').count() == 0
        assert LoginHistory.query.count() == 1
        # Categories before and after it finished
        assert result['results']['accounts']['affected'] == 1
        assert result['results']['inquiries']['affected'] == 1
        assert RetentionRun.query.one().status == RetentionRun.STATUS_ERRORS

    def test_recorded_errors_carry_no_statement_or_row_values(self, app, session):
        from sqlalchemy.exc import IntegrityError
        error = IntegrityError(
            "INSERT INTO users (email) VALUES (%(email)s)", {'email': 'secret@example.com'},
            Exception('duplicate key value violates unique constraint "users_email_key"\n'
                      'DETAIL:  Key (email)=(secret@example.com) already exists.'))
        text = retention._short_error(error)
        assert 'secret@example.com' not in text and 'users_email_key' in text
        assert len(retention._short_error(RuntimeError('x' * 1000))) <= 300

    def test_whole_run_twice_changes_nothing_the_second_time(self, app, session):
        data = make_full_tenant('team.example', 'tea')
        gone = make_full_tenant('gone.example', 'gon')
        schedule_deletion(data['member'], timedelta(hours=-2))
        soft_delete(data['decisions'][1], naive_now() - timedelta(hours=3))
        db.session.commit()
        expire_tenant(gone['tenant'])
        old_login(100)
        old_inquiry(Inquiry.RETENTION_DAYS + 1)

        first = run()
        assert {c: r['affected'] for c, r in first['results'].items()} == {
            'accounts': 1, 'login_history': 1, 'inquiries': 1, 'decisions': 1, 'tenants': 1}
        after_first = snapshot(exclude=RECORD_TABLES)
        erasures = RetentionErasure.query.count()

        second = run()

        assert all(r['affected'] == 0 and r['waiting'] == 0 for r in second['results'].values())
        assert snapshot(exclude=RECORD_TABLES) == after_first
        assert RetentionErasure.query.count() == erasures
        assert RetentionRun.query.count() == 2


# ==================== Database sessions that are not UTC ====================

@pytest.fixture
def real_session_offset():
    """Ask for this to keep retention's real time zone handling."""


class TestSessionTimeZone:
    def test_utc_session_and_sqlite_wait_nothing(self, app, session, real_session_offset):
        if db.engine.dialect.name == 'postgresql':
            db.session.execute(db.text("SET TIME ZONE 'UTC'"))
        assert retention._session_utc_offset_seconds() == 0
        assert retention.safety_margin() == timedelta(0)
        now = naive_now()
        assert retention.due_time(now) == now

    def test_postgresql_session_in_another_zone_is_measured(self, app, session, real_session_offset):
        if db.engine.dialect.name != 'postgresql':
            pytest.skip('SQLite has no session time zone')
        try:
            db.session.execute(db.text("SET TIME ZONE 'Asia/Kolkata'"))
            assert retention._session_utc_offset_seconds() == 19800
            assert retention.safety_margin() == timedelta(hours=6, minutes=30)
            db.session.execute(db.text("SET TIME ZONE 'America/Phoenix'"))
            assert retention._session_utc_offset_seconds() == -25200
            assert retention.safety_margin() == timedelta(hours=8)
        finally:
            db.session.execute(db.text("SET TIME ZONE 'UTC'"))
            db.session.commit()

    def test_nothing_is_due_until_the_margin_has_passed(self, app, session, monkeypatch, real_session_offset):
        """Eight hours west of UTC, a stored due date can be eight hours early."""
        monkeypatch.setattr(retention, '_session_utc_offset_seconds', lambda: -8 * 3600)
        early = make_user('team.example', 'early')
        late = make_user('team.example', 'late')
        early.deletion_scheduled_at = naive_now() - timedelta(hours=8, minutes=59)
        late.deletion_scheduled_at = naive_now() - timedelta(hours=9, minutes=1)
        data = make_full_tenant('gone.example', 'gon')
        expire_tenant(data['tenant'], expired_ago=timedelta(hours=5))
        old_login(90)
        db.session.commit()
        early_id, late_id = early.id, late.id

        preview = retention.preview_retention()
        results = run()['results']

        assert preview['accounts']['waiting'] == 1 and preview['tenants']['waiting'] == 0
        assert results['accounts']['affected'] == 1 and results['tenants']['affected'] == 0
        assert results['login_history']['affected'] == 0
        assert db.session.get(User, late_id).is_anonymized
        assert not db.session.get(User, early_id).is_anonymized
        assert db.session.get(Tenant, data['tenant'].id) is not None
        release, problem = retention.check_release(['tenants'], {'tenants': 0})
        assert problem is None and release == {'tenants': 0}
