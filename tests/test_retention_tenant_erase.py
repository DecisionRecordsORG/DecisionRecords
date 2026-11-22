"""
Erasing an expired soft-deleted tenant (retention.py, category "tenants").

These use the shared `app` fixture, so CI also runs them on PostgreSQL, where
foreign keys are enforced. The central test builds two tenants with a row in
every table, erases one and compares the whole database with a copy taken
before that tenant existed.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest

import retention
from models import (
    db, User, Tenant, TenantMembership, AuditLog, ArchitectureDecision, DomainApproval, Inquiry,
    GlobalRole, RetentionRun, RetentionErasure, SystemConfig,
)
from tests.retention_test_data import (
    make_full_tenant, make_user, make_decision, expire_tenant, snapshot, naive_now,
)

RECORD_TABLES = ('retention_runs', 'retention_erasures')


def run_tenants(**kwargs):
    return retention.run_retention(RetentionRun.TRIGGER_SUPER_ADMIN, categories=[retention.TENANTS], **kwargs)


def test_every_table_has_an_erase_rule(app):
    """A new model cannot be added without deciding what tenant erase does to it."""
    tables = set(db.metadata.tables)
    assert tables - set(retention.TENANT_ERASE_RULES) == set()
    assert set(retention.TENANT_ERASE_RULES) - tables == set()
    for name, (action, description) in retention.TENANT_ERASE_RULES.items():
        assert action in ('erase', 'detach', 'scrub', 'keep')
        assert description


def test_tables_that_point_at_a_tenant_or_user_are_never_marked_keep(app):
    for table in db.metadata.sorted_tables:
        points_at_tenant_data = any(
            fk.column.table.name in ('tenants', 'users', 'architecture_decisions')
            for column in table.columns for fk in column.foreign_keys
        ) or any(column.name in ('tenant_domain', 'sso_domain') for column in table.columns)
        if points_at_tenant_data:
            assert retention.TENANT_ERASE_RULES[table.name][0] != 'keep', table.name


def test_erasing_one_tenant_leaves_the_other_untouched_and_nothing_of_its_own(app, session):
    other = make_full_tenant('other.example', 'oth')
    before = snapshot(exclude=RECORD_TABLES)

    erased = make_full_tenant('erased.example', 'era')
    tenant_id = erased['tenant'].id
    member_email = erased['member'].email
    inquiry_ids = [row.id for row in Inquiry.query.filter(Inquiry.id.notin_(
        [row[0] for row in before['inquiries']])).all()]
    assert len(inquiry_ids) == 2
    expire_tenant(erased['tenant'])

    run = run_tenants()

    assert run['status'] == RetentionRun.STATUS_COMPLETED
    assert run['results']['tenants']['affected'] == 1
    assert run['results']['tenants']['errors'] == []

    after = snapshot(exclude=RECORD_TABLES)
    for table, rows in before.items():
        if table in ('inquiries', 'domain_approvals'):
            continue
        assert after[table] == rows, f'{table} differs after erasing the other tenant'

    # The two tables that keep a scrubbed row of the erased tenant
    assert [row for row in after['inquiries'] if row[0] not in inquiry_ids] == before['inquiries']
    for inquiry in Inquiry.query.filter(Inquiry.id.in_(inquiry_ids)).all():
        assert inquiry.name is None and inquiry.email is None and inquiry.message is None
        assert inquiry.user_id is None and inquiry.tenant_domain is None
        assert inquiry.redacted_at is not None
    approval = DomainApproval.query.filter_by(domain='erased.example').one()
    assert approval.status == 'approved'
    assert approval.requested_by_email is None and approval.requested_by_name is None
    assert [row for row in after['domain_approvals'] if row[0] != approval.id] == before['domain_approvals']

    # The other tenant's people can still be found
    assert db.session.get(Tenant, other['tenant'].id) is not None
    assert User.query.filter_by(sso_domain='other.example').count() == 2

    # The record says what was erased without holding any of it
    record = RetentionErasure.query.filter_by(category='tenants').one()
    assert record.entity_type == 'tenant' and record.entity_id == tenant_id
    assert record.identifier == 'erased.example'
    assert record.run_id == run['id']
    assert record.counts['users'] == 2
    assert record.counts['architecture_decisions'] == 2
    assert record.counts['tenants'] == 1
    assert all(isinstance(value, int) for value in record.counts.values())
    stored = json.dumps(record.to_dict()) + json.dumps(run)
    assert member_email not in stored and 'Decision 1' not in stored and 'A comment' not in stored


def test_second_run_changes_nothing(app, session):
    make_full_tenant('other.example', 'oth')
    erased = make_full_tenant('erased.example', 'era')
    expire_tenant(erased['tenant'])
    run_tenants()
    after_first = snapshot(exclude=RECORD_TABLES)

    second = run_tenants()

    assert second['results']['tenants']['affected'] == 0
    assert second['results']['tenants']['waiting'] == 0
    assert snapshot(exclude=RECORD_TABLES) == after_first
    assert RetentionErasure.query.count() == 1


def test_tenant_expiring_one_second_from_now_is_not_touched(app, session):
    data = make_full_tenant('soon.example', 'soo')
    now = naive_now()
    expire_tenant(data['tenant'], expired_ago=timedelta(seconds=-1), now=now)
    before = snapshot(exclude=RECORD_TABLES)

    run = run_tenants(now=now)

    assert run['results']['tenants']['waiting'] == 0
    assert snapshot(exclude=RECORD_TABLES) == before

    # One second later it is due
    later = run_tenants(now=now + timedelta(seconds=2))
    assert later['results']['tenants']['affected'] == 1


def test_expiry_is_compared_as_an_instant_whatever_the_time_zone_of_now(app, session):
    data = make_full_tenant('zone.example', 'zon')
    now = naive_now()
    expire_tenant(data['tenant'], expired_ago=timedelta(minutes=-30), now=now)  # due in 30 minutes
    plus_five = timezone(timedelta(hours=5))

    # Same instant as `now`, written as a later wall-clock time: still not due
    aware_now = now.replace(tzinfo=timezone.utc).astimezone(plus_five)
    assert run_tenants(now=aware_now)['results']['tenants']['waiting'] == 0
    assert db.session.get(Tenant, data['tenant'].id) is not None

    # 31 minutes later, in the same zone: due
    assert run_tenants(now=aware_now + timedelta(minutes=31))['results']['tenants']['affected'] == 1


def test_restored_tenant_is_not_touched(app, session):
    data = make_full_tenant('restored.example', 'res')
    expire_tenant(data['tenant'])
    tenant = db.session.get(Tenant, data['tenant'].id)
    # What POST /api/tenants/<domain>/restore does
    tenant.deleted_at = None
    tenant.deleted_by_admin = None
    tenant.deletion_expires_at = None
    tenant.status = 'active'
    for decision in ArchitectureDecision.query.filter_by(tenant_id=tenant.id).all():
        decision.deleted_at = None
        decision.deletion_expires_at = None
    db.session.commit()
    before = snapshot(exclude=RECORD_TABLES)

    run = retention.run_retention(RetentionRun.TRIGGER_AUTOMATIC)

    assert run['results']['tenants']['waiting'] == 0
    assert run['results']['decisions']['waiting'] == 0
    assert snapshot(exclude=RECORD_TABLES) == before


def test_tenant_restored_after_it_was_listed_is_skipped_at_the_recheck(app, session, monkeypatch):
    data = make_full_tenant('late.example', 'lat')
    expire_tenant(data['tenant'])
    tenant_id = data['tenant'].id
    real_due_ids = retention._due_ids

    def list_then_restore(category, now, cap=None):
        ids = real_due_ids(category, now, cap)
        tenant = db.session.get(Tenant, tenant_id)
        tenant.deleted_at = None
        tenant.deletion_expires_at = None
        tenant.status = 'active'
        db.session.commit()
        return ids

    monkeypatch.setattr(retention, '_due_ids', list_then_restore)
    run = run_tenants()

    assert run['results']['tenants']['waiting'] == 1
    assert run['results']['tenants']['affected'] == 0
    assert db.session.get(Tenant, tenant_id) is not None
    assert User.query.filter_by(sso_domain='late.example').count() == 2
    assert RetentionErasure.query.count() == 0


def test_expired_tenant_whose_status_is_not_deleted_is_never_erased(app, session):
    """Someone set it active by hand without clearing the deletion dates."""
    data = make_full_tenant('byhand.example', 'byh')
    expire_tenant(data['tenant'])
    tenant = db.session.get(Tenant, data['tenant'].id)
    tenant.status = 'active'
    db.session.commit()
    before = snapshot(exclude=RECORD_TABLES)

    preview = retention.preview_retention()
    run = retention.run_retention(RetentionRun.TRIGGER_AUTOMATIC)

    assert preview['tenants']['waiting'] == 0
    assert preview['tenants']['needs_review'] == [
        {'id': tenant.id, 'label': 'byhand.example', 'status': 'active'}]
    assert run['results']['tenants']['affected'] == 0
    # Its decisions are not erased one by one either
    assert run['results']['decisions']['waiting'] == 0
    assert snapshot(exclude=RECORD_TABLES) == before


def test_user_of_the_domain_who_belongs_to_another_tenant_is_kept(app, session):
    other = make_full_tenant('other.example', 'oth')
    erased = make_full_tenant('erased.example', 'era')
    shared = make_user('erased.example', 'shared')
    db.session.add_all([
        TenantMembership(user_id=shared.id, tenant_id=erased['tenant'].id, global_role=GlobalRole.USER),
        TenantMembership(user_id=shared.id, tenant_id=other['tenant'].id, global_role=GlobalRole.USER),
    ])
    db.session.commit()
    shared_id, shared_email = shared.id, shared.email
    expire_tenant(erased['tenant'])

    run = run_tenants()

    assert run['results']['tenants']['affected'] == 1
    kept = db.session.get(User, shared_id)
    assert kept.email == shared_email and not kept.is_anonymized and kept.password_hash
    memberships = TenantMembership.query.filter_by(user_id=shared_id).all()
    assert [m.tenant_id for m in memberships] == [other['tenant'].id]
    assert User.query.filter_by(sso_domain='erased.example').count() == 1


def test_user_named_by_another_tenants_audit_log_is_anonymised_not_deleted(app, session):
    other = make_full_tenant('other.example', 'oth')
    erased = make_full_tenant('erased.example', 'era')
    member_id, member_email = erased['member'].id, erased['member'].email
    admin_id = erased['admin'].id
    # A required column in the other tenant's records points at this user
    db.session.add(AuditLog(tenant_id=other['tenant'].id, actor_user_id=member_id, action_type='promote_user'))
    # and so does an optional one
    foreign_decision = make_decision(other['tenant'], other['admin'], 9)
    foreign_decision.updated_by_id = member_id
    db.session.commit()
    decision_id = foreign_decision.id
    expire_tenant(erased['tenant'])

    run = run_tenants()

    assert run['results']['tenants']['affected'] == 1, run['results']['tenants']['errors']
    user = db.session.get(User, member_id)
    assert user is not None and user.is_anonymized
    assert user.email != member_email and user.email.endswith('@anonymized.local')
    assert user.name == 'Former Member' and user.password_hash is None
    assert AuditLog.query.filter_by(tenant_id=other['tenant'].id, actor_user_id=member_id).count() == 1
    kept_decision = db.session.get(ArchitectureDecision, decision_id)
    assert kept_decision.updated_by_id is None and kept_decision.title == 'Decision 9 of other.example'
    assert db.session.get(User, admin_id) is None
    record = RetentionErasure.query.filter_by(category='tenants').one()
    assert record.counts['users'] == 1 and record.counts['users_anonymised'] == 1


def test_decisions_without_a_tenant_id_follow_their_domain(app, session):
    other = make_full_tenant('other.example', 'oth')
    erased = make_full_tenant('erased.example', 'era')
    legacy_erased = make_decision(erased['tenant'], erased['admin'], 7)
    legacy_other = make_decision(other['tenant'], other['admin'], 7)
    legacy_erased.tenant_id = None
    legacy_other.tenant_id = None
    db.session.commit()
    erased_id, other_id = legacy_erased.id, legacy_other.id
    expire_tenant(erased['tenant'])

    run_tenants()

    assert db.session.get(ArchitectureDecision, erased_id) is None
    assert db.session.get(ArchitectureDecision, other_id) is not None


def test_failure_part_way_through_a_tenant_rolls_all_of_it_back_and_the_next_tenant_still_runs(
        app, session, monkeypatch):
    first = make_full_tenant('first.example', 'fir')
    expire_tenant(first['tenant'], expired_ago=timedelta(hours=2))
    only_first = snapshot(exclude=RECORD_TABLES)
    second = make_full_tenant('second.example', 'sec')
    expire_tenant(second['tenant'], expired_ago=timedelta(hours=1))
    first_id, second_id = first['tenant'].id, second['tenant'].id
    real_erase = retention._erase_tenant

    def erase_then_fail(tenant, record):
        tenant_id = tenant.id
        real_erase(tenant, record)
        if tenant_id == first_id:
            raise RuntimeError('disk full while erasing secret@first.example')

    monkeypatch.setattr(retention, '_erase_tenant', erase_then_fail)
    run = retention.run_retention(
        RetentionRun.TRIGGER_SUPER_ADMIN, categories=[retention.TENANTS, retention.LOGIN_HISTORY],
        release={retention.TENANTS: 2})

    result = run['results']['tenants']
    assert run['status'] == RetentionRun.STATUS_ERRORS
    assert result['status'] == 'error' and result['affected'] == 1 and result['error_count'] == 1
    assert result['errors'][0]['entity_id'] == first_id
    assert result['errors'][0]['error'].startswith('RuntimeError')
    assert run['results']['login_history']['status'] == 'done'

    # The first tenant is exactly as it was before the second existed; the second is gone
    assert db.session.get(Tenant, first_id) is not None
    assert db.session.get(Tenant, second_id) is None
    after = snapshot(exclude=RECORD_TABLES)
    for table, rows in only_first.items():
        if table in ('inquiries', 'domain_approvals'):
            assert [row for row in after[table] if row in rows] == rows, table
        else:
            assert after[table] == rows, table
    # Only the erasure that happened is on record
    assert [r.entity_id for r in RetentionErasure.query.all()] == [second_id]

    # Nothing is stuck: the next run finishes the first tenant
    monkeypatch.setattr(retention, '_erase_tenant', real_erase)
    assert run_tenants()['results']['tenants']['affected'] == 1
    assert db.session.get(Tenant, first_id) is None


def test_more_tenants_than_the_limit_are_held_back_until_a_super_admin_releases_them(app, session):
    first = make_full_tenant('first.example', 'fir')
    second = make_full_tenant('second.example', 'sec')
    expire_tenant(first['tenant'])
    expire_tenant(second['tenant'])
    before = snapshot(exclude=RECORD_TABLES)
    assert SystemConfig.DEFAULT_RETENTION_LIMIT_TENANTS == 1

    run = retention.run_retention(RetentionRun.TRIGGER_AUTOMATIC)

    result = run['results']['tenants']
    assert run['status'] == RetentionRun.STATUS_HELD_BACK
    assert result == {'status': 'held_back', 'affected': 0, 'waiting': 2, 'limit': 1,
                      'hold_reason': 'over_limit', 'errors': []}
    assert snapshot(exclude=RECORD_TABLES) == before
    assert retention.held_back(run) == {'tenants': {'waiting': 2, 'limit': 1, 'reason': 'over_limit'}}

    release, problem = retention.check_release(['tenants'], {'tenants': 2})
    assert problem is None
    released = retention.run_retention(
        RetentionRun.TRIGGER_SUPER_ADMIN, categories=list(release), release=release, started_by='root')
    assert released['results']['tenants']['affected'] == 2
    assert released['started_by'] == 'root'
    assert Tenant.query.count() == 0


def test_single_tenant_long_overdue_is_held_back_as_a_backlog(app, session):
    data = make_full_tenant('old.example', 'old')
    expire_tenant(data['tenant'], expired_ago=timedelta(days=90))
    before = snapshot(exclude=RECORD_TABLES)

    run = retention.run_retention(RetentionRun.TRIGGER_AUTOMATIC)

    assert run['results']['tenants']['status'] == 'held_back'
    assert run['results']['tenants']['hold_reason'] == 'backlog'
    assert run['results']['tenants']['waiting'] == 1
    assert snapshot(exclude=RECORD_TABLES) == before


@pytest.mark.parametrize('expired_days, held', [(6, False), (8, True)])
def test_backlog_boundary_is_seven_days(app, session, expired_days, held):
    data = make_full_tenant('edge.example', 'edg')
    expire_tenant(data['tenant'], expired_ago=timedelta(days=expired_days))
    run = retention.run_retention(RetentionRun.TRIGGER_AUTOMATIC)
    assert (run['results']['tenants']['status'] == 'held_back') is held
    assert (db.session.get(Tenant, data['tenant'].id) is not None) is held
