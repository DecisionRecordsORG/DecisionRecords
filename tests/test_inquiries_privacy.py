"""
Privacy behaviour of inquiries and the team profile.

- A user's data export includes the inquiries they sent while signed in.
- Deleting (anonymising) an account removes the personal fields from that
  person's inquiries.
- Inquiries are purged after 24 months by the scheduled GDPR task.
- A tenant's team profile answers go when the tenant is purged.

The function-level tests use the shared ``app`` fixture, so CI also runs them
on PostgreSQL (TEST_DATABASE_URL).
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    db, User, Tenant, TenantMembership, GlobalRole, MaturityState, Inquiry,
    DEFAULT_MASTER_PASSWORD, DEFAULT_MASTER_USERNAME,
)
from tests.app_test_utils import load_test_app


def make_tenant(session, domain='example.com', name='Example Corp'):
    tenant = Tenant(domain=domain, name=name, status='active', maturity_state=MaturityState.BOOTSTRAP)
    session.add(tenant)
    session.commit()
    return tenant


def make_user(session, email='person@example.com', sso_domain='example.com'):
    user = User(email=email, sso_domain=sso_domain, auth_type='local', email_verified=True)
    user.set_name(first_name='Pat', last_name='Person')
    user.set_password('testpassword123')
    session.add(user)
    session.commit()
    return user


def make_inquiry(session, days_ago=0, **fields):
    values = {
        'source': 'contact', 'name': 'Pat Person', 'email': 'person@example.com',
        'message': 'Please call me on 555 0100.', 'organisation': 'Example Corp',
        'team_focus': 'Hiring', 'team_size': '6-25',
        'created_at': datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days_ago),
    }
    values.update(fields)
    inquiry = Inquiry(**values)
    session.add(inquiry)
    session.commit()
    return inquiry


# ==================== Model ====================

class TestInquiryModel:

    def test_defaults(self, app, session):
        inquiry = Inquiry(source='feedback', email='a@example.com')
        session.add(inquiry)
        session.commit()

        assert inquiry.id is not None
        assert inquiry.email_sent is False
        assert inquiry.handled is False
        assert inquiry.created_at is not None
        assert inquiry.redacted_at is None
        assert inquiry.to_dict()['redacted'] is False

    def test_optional_fields_may_all_be_empty(self, app, session):
        inquiry = Inquiry(source='sponsorship')
        session.add(inquiry)
        session.commit()

        data = inquiry.to_dict()
        for key in ('name', 'email', 'organisation', 'area_of_interest', 'message', 'team_focus',
                    'team_size', 'team_size_label', 'user_id', 'tenant_domain', 'handled_at', 'handled_by'):
            assert data[key] is None

    def test_long_values_fit_the_columns(self, app, session):
        """PostgreSQL enforces column lengths; the endpoints cut to these sizes."""
        inquiry = Inquiry(
            source='sponsorship', name='N' * 100, email='e' * 243 + '@example.com',
            organisation='O' * 200, area_of_interest='A' * 100, message='M' * 5000,
            team_focus='F' * 200, team_size='101-500', tenant_domain='d' * 255, handled_by='h' * 255,
        )
        session.add(inquiry)
        session.commit()

        assert db.session.get(Inquiry, inquiry.id).message == 'M' * 5000

    def test_user_link_is_a_real_foreign_key(self, app, session):
        user = make_user(session)
        inquiry = make_inquiry(session, user_id=user.id, tenant_domain='example.com')

        assert db.session.get(Inquiry, inquiry.id).user_id == user.id

    def test_retention_is_24_months(self, app):
        assert Inquiry.RETENTION_DAYS == 730


# ==================== Account deletion ====================

class TestAnonymisingAnAccount:

    def test_personal_fields_are_removed_from_inquiries_sent_while_signed_in(self, app, session):
        from app import anonymize_user
        user = make_user(session)
        inquiry = make_inquiry(session, source='feedback', user_id=user.id, tenant_domain='example.com',
                               email='a-different-address@example.net')

        assert anonymize_user(user.id) is True

        session.refresh(inquiry)
        assert inquiry.name is None
        assert inquiry.email is None
        assert inquiry.message is None
        assert inquiry.user_id is None
        assert inquiry.redacted_at is not None
        assert inquiry.to_dict()['redacted'] is True

    def test_what_kind_of_team_wrote_is_kept(self, app, session):
        from app import anonymize_user
        user = make_user(session)
        inquiry = make_inquiry(session, user_id=user.id, tenant_domain='example.com')

        anonymize_user(user.id)

        session.refresh(inquiry)
        assert inquiry.source == 'contact'
        assert inquiry.team_focus == 'Hiring'
        assert inquiry.team_size == '6-25'
        assert inquiry.tenant_domain == 'example.com'
        assert inquiry.created_at is not None

    def test_inquiries_carrying_the_account_email_are_redacted_too(self, app, session):
        """Sent from the website without signing in, with the same address."""
        from app import anonymize_user
        user = make_user(session, email='person@example.com')
        inquiry = make_inquiry(session, email='Person@Example.com', user_id=None)

        anonymize_user(user.id)

        session.refresh(inquiry)
        assert inquiry.email is None
        assert inquiry.name is None
        assert inquiry.message is None

    def test_other_peoples_inquiries_are_untouched(self, app, session):
        from app import anonymize_user
        user = make_user(session, email='person@example.com')
        other_user = make_user(session, email='other@example.com')
        theirs = make_inquiry(session, email='other@example.com', name='Other Person', user_id=other_user.id)
        anonymous = make_inquiry(session, email='visitor@elsewhere.test', name='A Visitor', user_id=None)

        anonymize_user(user.id)

        session.refresh(theirs)
        session.refresh(anonymous)
        assert theirs.email == 'other@example.com' and theirs.name == 'Other Person'
        assert theirs.user_id == other_user.id and theirs.redacted_at is None
        assert anonymous.email == 'visitor@elsewhere.test' and anonymous.message is not None

    def test_account_without_inquiries_still_anonymises(self, app, session):
        from app import anonymize_user
        user = make_user(session)

        assert anonymize_user(user.id) is True

    def test_team_profile_answer_stays_without_the_link_to_the_person(self, app, session):
        from app import anonymize_user
        tenant = make_tenant(session)
        user = make_user(session)
        tenant.team_focus = 'Hiring'
        tenant.team_size = '1-5'
        tenant.team_profile_answered_at = datetime.now(timezone.utc)
        tenant.team_profile_answered_by_id = user.id
        session.commit()

        anonymize_user(user.id)

        session.refresh(tenant)
        assert tenant.team_profile_answered_by_id is None
        assert tenant.team_focus == 'Hiring'
        assert tenant.team_size == '1-5'


# ==================== 24 month purge ====================

class TestPurge:

    def test_inquiries_older_than_24_months_are_deleted(self, app, session):
        from app import purge_old_inquiries
        old = make_inquiry(session, days_ago=731)
        ancient = make_inquiry(session, days_ago=2000, source='feedback')
        recent = make_inquiry(session, days_ago=729)
        today = make_inquiry(session)
        old_id, ancient_id = old.id, ancient.id

        purged = purge_old_inquiries()

        assert purged == 2
        session.expire_all()
        assert db.session.get(Inquiry, old_id) is None
        assert db.session.get(Inquiry, ancient_id) is None
        assert db.session.get(Inquiry, recent.id) is not None
        assert db.session.get(Inquiry, today.id) is not None

    def test_handled_state_does_not_protect_an_old_inquiry(self, app, session):
        from app import purge_old_inquiries
        make_inquiry(session, days_ago=800, handled=True)
        make_inquiry(session, days_ago=800, handled=False)

        assert purge_old_inquiries() == 2
        assert Inquiry.query.count() == 0

    def test_nothing_to_purge(self, app, session):
        from app import purge_old_inquiries
        make_inquiry(session, days_ago=10)

        assert purge_old_inquiries() == 0
        assert Inquiry.query.count() == 1

    def test_empty_table(self, app, session):
        from app import purge_old_inquiries

        assert purge_old_inquiries() == 0

    def test_cutoff_follows_the_time_given(self, app, session):
        from app import purge_old_inquiries
        make_inquiry(session, days_ago=10)

        assert purge_old_inquiries(datetime.now(timezone.utc) + timedelta(days=725)) == 1


# ==================== HTTP: export and the scheduled task ====================

class TestOverHTTP:

    @pytest.fixture
    def api_app(self):
        app_module, test_app = load_test_app(secret_key='test-secret-key-inquiry-privacy-12345')
        with test_app.app_context():
            db.create_all()
            app_module.init_database()
            yield test_app
            db.session.remove()
            db.drop_all()
            app_module._db_initialized = False

    @pytest.fixture
    def user_and_client(self, api_app):
        tenant = make_tenant(db.session, domain='privacy.test', name='Privacy Test')
        user = make_user(db.session, email='pat@privacy.test', sso_domain='privacy.test')
        db.session.add(TenantMembership(user_id=user.id, tenant_id=tenant.id, global_role=GlobalRole.USER))
        db.session.commit()

        client = api_app.test_client()
        response = client.post('/api/auth/login', json={'email': user.email, 'password': 'testpassword123'})
        assert response.status_code == 200, response.data
        client.environ_base['HTTP_X_CSRF_TOKEN'] = response.headers.get('X-CSRF-Token', '')
        return user, client

    def test_export_includes_inquiries_sent_while_signed_in(self, user_and_client):
        user, client = user_and_client
        client.post('/api/feedback', json={
            'name': 'Pat Person', 'email': 'pat@privacy.test',
            'feedback': 'It would help to export decisions as a PDF.', 'contact_consent': True,
            'team_focus': 'Clinical protocols',
        })

        response = client.post('/api/user/export-data')

        assert response.status_code == 200
        inquiries = response.get_json()['inquiries']
        assert len(inquiries) == 1
        assert inquiries[0]['source'] == 'feedback'
        assert inquiries[0]['name'] == 'Pat Person'
        assert inquiries[0]['email'] == 'pat@privacy.test'
        assert inquiries[0]['message'] == 'It would help to export decisions as a PDF.'
        assert inquiries[0]['team_focus'] == 'Clinical protocols'
        assert inquiries[0]['contact_consent'] is True
        assert inquiries[0]['created_at'] is not None

    def test_export_leaves_out_internal_fields(self, user_and_client):
        user, client = user_and_client
        make_inquiry(db.session, user_id=user.id, handled=True, handled_by='admin')

        exported = client.post('/api/user/export-data').get_json()['inquiries'][0]

        assert 'handled' not in exported
        assert 'handled_by' not in exported
        assert 'email_sent' not in exported

    def test_export_excludes_inquiries_from_other_people_and_anonymous_ones(self, user_and_client):
        user, client = user_and_client
        other = make_user(db.session, email='other@privacy.test', sso_domain='privacy.test')
        make_inquiry(db.session, user_id=other.id, email='other@privacy.test')
        # Same address typed into the public form by someone who was not signed in
        make_inquiry(db.session, user_id=None, email='pat@privacy.test')

        response = client.post('/api/user/export-data')

        assert response.get_json()['inquiries'] == []

    def test_export_with_no_inquiries_has_an_empty_list(self, user_and_client):
        _user, client = user_and_client

        assert client.post('/api/user/export-data').get_json()['inquiries'] == []

    def test_scheduled_task_purges_old_inquiries(self, api_app, monkeypatch):
        monkeypatch.setenv('GDPR_CRON_SECRET', 'cron-secret-for-test')
        make_inquiry(db.session, days_ago=900)
        keep = make_inquiry(db.session, days_ago=5)

        response = api_app.test_client().post(
            '/api/admin/execute-gdpr-tasks', headers={'X-Cron-Secret': 'cron-secret-for-test'}
        )

        assert response.status_code == 200
        assert response.get_json()['results']['purged_inquiries'] == 1
        db.session.expire_all()
        assert [inquiry.id for inquiry in Inquiry.query.all()] == [keep.id]

    def test_scheduled_task_reports_zero_when_there_is_nothing_to_purge(self, api_app, monkeypatch):
        monkeypatch.setenv('GDPR_CRON_SECRET', 'cron-secret-for-test')

        response = api_app.test_client().post(
            '/api/admin/execute-gdpr-tasks', headers={'X-Cron-Secret': 'cron-secret-for-test'}
        )

        assert response.get_json()['results']['purged_inquiries'] == 0

    def test_scheduled_task_still_refuses_callers_without_the_secret(self, api_app, monkeypatch):
        monkeypatch.setenv('GDPR_CRON_SECRET', 'cron-secret-for-test')
        make_inquiry(db.session, days_ago=900)

        response = api_app.test_client().post(
            '/api/admin/execute-gdpr-tasks', headers={'X-Cron-Secret': 'wrong'}
        )

        assert response.status_code == 403
        assert Inquiry.query.count() == 1

    def test_scheduled_task_redacts_inquiries_of_accounts_due_for_deletion(self, api_app, monkeypatch):
        monkeypatch.setenv('GDPR_CRON_SECRET', 'cron-secret-for-test')
        user = make_user(db.session, email='leaving@privacy.test', sso_domain='privacy.test')
        user.deletion_requested_at = datetime.now(timezone.utc) - timedelta(days=8)
        user.deletion_scheduled_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.session.commit()
        inquiry = make_inquiry(db.session, user_id=user.id, email='leaving@privacy.test')

        response = api_app.test_client().post(
            '/api/admin/execute-gdpr-tasks', headers={'X-Cron-Secret': 'cron-secret-for-test'}
        )

        assert response.get_json()['results']['anonymized_users'] == 1
        db.session.expire_all()
        redacted = db.session.get(Inquiry, inquiry.id)
        assert redacted.email is None and redacted.name is None and redacted.message is None

    def test_team_profile_answers_go_when_the_tenant_is_purged(self, api_app, monkeypatch):
        monkeypatch.setenv('GDPR_CRON_SECRET', 'cron-secret-for-test')
        tenant = make_tenant(db.session, domain='closing.test', name='Closing')
        tenant.team_focus = 'Hiring'
        tenant.team_size = '1-5'
        tenant.team_profile_answered_at = datetime.now(timezone.utc)
        tenant.deleted_at = datetime.now(timezone.utc) - timedelta(days=31)
        tenant.deletion_expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.session.commit()

        response = api_app.test_client().post(
            '/api/admin/execute-gdpr-tasks', headers={'X-Cron-Secret': 'cron-secret-for-test'}
        )

        assert response.get_json()['results']['purged_tenants'] == 1
        db.session.expire_all()
        assert Tenant.query.filter_by(domain='closing.test').first() is None
        rows = db.session.execute(db.text("SELECT team_focus FROM tenants")).fetchall()
        assert ('Hiring',) not in [tuple(row) for row in rows]

    def test_a_tenant_waiting_to_be_purged_is_left_out_of_the_interest_summary(self, api_app):
        tenant = make_tenant(db.session, domain='closing.test', name='Closing')
        tenant.team_focus = 'Hiring'
        tenant.team_size = '1-5'
        tenant.deleted_at = datetime.now(timezone.utc)
        tenant.deletion_expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        db.session.commit()

        client = api_app.test_client()
        login = client.post('/auth/local', json={
            'username': DEFAULT_MASTER_USERNAME, 'password': DEFAULT_MASTER_PASSWORD,
        })
        assert login.status_code == 200

        summary = client.get('/api/superadmin/inquiries/summary').get_json()

        assert summary['tenants']['total'] == 0
        assert summary['team_focus_answers'] == []
