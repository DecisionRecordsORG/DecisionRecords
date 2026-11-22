"""
Inquiries: messages from the contact, sponsorship ("Get in touch") and feedback
forms are stored before the notification email is attempted, and a super admin
can list, handle and delete them.

Covers the three form endpoints (store first, then email; optional team_focus;
tolerance of null, wrong-typed and missing fields), the super admin endpoints
(authorisation, paging, filters) and the interest summary.
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    db, User, Tenant, TenantMembership, GlobalRole, MaturityState, MasterAccount,
    EmailConfig, Inquiry, DEFAULT_MASTER_PASSWORD, DEFAULT_MASTER_USERNAME,
    TEAM_SIZE_CODES, SystemConfig,
)
from tests.app_test_utils import load_test_app


PASSWORD = 'testpassword123'

CONTACT = {
    'name': 'Ada Lovelace',
    'email': 'ada@example.org',
    'message': 'Hello, I would like to know more.',
}
SPONSORSHIP = {
    'organisation_name': 'Analytical Engines Ltd',
    'contact_email': 'ada@example.org',
}
FEEDBACK = {
    'name': 'Ada Lovelace',
    'email': 'ada@example.org',
    'feedback': 'The decision list is easy to read.',
}

# (url, valid payload, source)
FORMS = [
    ('/api/contact', CONTACT, 'contact'),
    ('/api/sponsorship', SPONSORSHIP, 'sponsorship'),
    ('/api/feedback', FEEDBACK, 'feedback'),
]
FORM_IDS = [source for _url, _payload, source in FORMS]


# ==================== Fixtures ====================

@pytest.fixture
def app_module_and_app():
    app_module, test_app = load_test_app(secret_key='test-secret-key-inquiries-12345')
    with test_app.app_context():
        db.create_all()
        app_module.init_database()
        yield app_module, test_app
        db.session.remove()
        db.drop_all()
        app_module._db_initialized = False


@pytest.fixture
def api_app(app_module_and_app):
    return app_module_and_app[1]


@pytest.fixture
def app_module(app_module_and_app):
    return app_module_and_app[0]


@pytest.fixture
def client(api_app):
    return api_app.test_client()


def _attach_csrf(test_client, login_response):
    token = login_response.headers.get('X-CSRF-Token')
    if not token:
        token = test_client.get('/api/auth/csrf-token').get_json()['csrf_token']
    test_client.environ_base['HTTP_X_CSRF_TOKEN'] = token


def _make_tenant(domain, name):
    tenant = Tenant(domain=domain, name=name, status='active', maturity_state=MaturityState.BOOTSTRAP)
    db.session.add(tenant)
    db.session.commit()
    return tenant


def _make_user(tenant, email, role, first_name='Test', last_name='Person'):
    user = User(email=email, sso_domain=tenant.domain, auth_type='local', email_verified=True)
    user.set_name(first_name=first_name, last_name=last_name)
    user.set_password(PASSWORD)
    user.is_admin = role != GlobalRole.USER
    db.session.add(user)
    db.session.flush()
    db.session.add(TenantMembership(user_id=user.id, tenant_id=tenant.id, global_role=role))
    db.session.commit()
    return user


def _login(api_app, user):
    test_client = api_app.test_client()
    response = test_client.post('/api/auth/login', json={'email': user.email, 'password': PASSWORD})
    assert response.status_code == 200, response.data
    _attach_csrf(test_client, response)
    return test_client


@pytest.fixture
def tenant(api_app):
    return _make_tenant('acme.test', 'Acme')


@pytest.fixture
def member(api_app, tenant):
    return _make_user(tenant, 'member@acme.test', GlobalRole.USER)


@pytest.fixture
def tenant_admin(api_app, tenant):
    return _make_user(tenant, 'admin@acme.test', GlobalRole.ADMIN, first_name='Grace', last_name='Hopper')


@pytest.fixture
def member_client(api_app, member):
    return _login(api_app, member)


@pytest.fixture
def admin_client(api_app, tenant_admin):
    return _login(api_app, tenant_admin)


@pytest.fixture
def master_client(api_app):
    test_client = api_app.test_client()
    response = test_client.post('/auth/local', json={
        'username': DEFAULT_MASTER_USERNAME, 'password': DEFAULT_MASTER_PASSWORD,
    })
    assert response.status_code == 200, response.data
    _attach_csrf(test_client, response)
    return test_client


def enable_email(enabled=True):
    config = EmailConfig(
        domain='system', smtp_server='smtp.example.org', smtp_port=587,
        smtp_username='mailer', smtp_password='not-a-real-password',
        from_email='noreply@example.org', from_name='Decision Records', enabled=enabled,
    )
    db.session.add(config)
    db.session.commit()
    return config


def stored():
    db.session.expire_all()
    return Inquiry.query.order_by(Inquiry.id).all()


def add_inquiry(source='contact', days_ago=0, **fields):
    values = {
        'name': 'Ada Lovelace', 'email': 'ada@example.org', 'message': 'Hello there, a message.',
        'created_at': datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days_ago),
    }
    values.update(fields)
    inquiry = Inquiry(source=source, **values)
    db.session.add(inquiry)
    db.session.commit()
    return inquiry


# ==================== The three forms: store first, then email ====================

@pytest.mark.parametrize('url,payload,source', FORMS, ids=FORM_IDS)
class TestFormsStoreThenEmail:

    def test_message_is_stored_and_marked_emailed_when_the_email_goes_out(self, client, url, payload, source):
        enable_email()

        with patch('notifications.send_email', return_value=True) as send_email:
            response = client.post(url, json=payload)

        assert response.status_code == 200
        assert 'message' in response.get_json()
        send_email.assert_called_once()

        (inquiry,) = stored()
        assert inquiry.source == source
        assert inquiry.email == 'ada@example.org'
        assert inquiry.email_sent is True
        assert inquiry.handled is False
        assert inquiry.created_at is not None

    def test_message_is_kept_when_email_is_not_configured(self, client, url, payload, source):
        with patch('notifications.send_email', return_value=True) as send_email:
            response = client.post(url, json=payload)

        assert response.status_code == 200
        body = response.get_json()
        assert 'message' in body and 'error' not in body
        send_email.assert_not_called()

        (inquiry,) = stored()
        assert inquiry.source == source
        assert inquiry.email_sent is False

    def test_message_is_kept_when_the_only_email_config_is_disabled(self, client, url, payload, source):
        enable_email(enabled=False)

        with patch('notifications.send_email', return_value=True) as send_email:
            response = client.post(url, json=payload)

        assert response.status_code == 200
        send_email.assert_not_called()
        assert stored()[0].email_sent is False

    def test_message_is_kept_when_the_send_fails(self, client, url, payload, source):
        enable_email()

        with patch('notifications.send_email', return_value=False):
            response = client.post(url, json=payload)

        assert response.status_code == 200
        assert 'error' not in response.get_json()
        (inquiry,) = stored()
        assert inquiry.email_sent is False

    def test_message_is_kept_when_the_send_raises(self, client, url, payload, source):
        enable_email()

        with patch('notifications.send_email', side_effect=RuntimeError('smtp exploded')):
            response = client.post(url, json=payload)

        assert response.status_code == 200
        assert stored()[0].email_sent is False

    def test_emailed_but_not_stored_is_still_a_success(self, client, app_module, url, payload, source):
        enable_email()

        with patch.object(app_module, '_store_inquiry', return_value=None), \
                patch('notifications.send_email', return_value=True) as send_email:
            response = client.post(url, json=payload)

        assert response.status_code == 200
        send_email.assert_called_once()
        assert stored() == []

    def test_neither_stored_nor_configured_is_reported_as_unavailable(self, client, app_module, url, payload, source):
        with patch.object(app_module, '_store_inquiry', return_value=None):
            response = client.post(url, json=payload)

        assert response.status_code == 503
        assert response.get_json() == {'error': 'Email service temporarily unavailable'}

    def test_neither_stored_nor_emailed_is_an_error(self, client, app_module, url, payload, source):
        enable_email()

        with patch.object(app_module, '_store_inquiry', return_value=None), \
                patch('notifications.send_email', return_value=False):
            response = client.post(url, json=payload)

        assert response.status_code == 500
        body = response.get_json()
        assert 'error' in body and 'message' not in body

    def test_a_database_failure_while_storing_does_not_lose_the_email(self, client, url, payload, source):
        enable_email()
        real_commit = db.session.commit
        calls = {'n': 0}

        def failing_once():
            calls['n'] += 1
            if calls['n'] == 1:
                raise RuntimeError('database is read-only')
            return real_commit()

        with patch.object(db.session, 'commit', side_effect=failing_once), \
                patch('notifications.send_email', return_value=True) as send_email:
            response = client.post(url, json=payload)

        assert response.status_code == 200
        send_email.assert_called_once()
        assert stored() == []

    def test_team_focus_is_stored_trimmed(self, client, url, payload, source):
        response = client.post(url, json={**payload, 'team_focus': '  Hiring and pay reviews  '})

        assert response.status_code == 200
        assert stored()[0].team_focus == 'Hiring and pay reviews'

    def test_team_focus_is_optional(self, client, url, payload, source):
        response = client.post(url, json=payload)

        assert response.status_code == 200
        assert stored()[0].team_focus is None

    @pytest.mark.parametrize('bad', [None, '', '   ', 42, True, ['x'], {'a': 1}])
    def test_team_focus_of_the_wrong_type_is_ignored(self, client, url, payload, source, bad):
        response = client.post(url, json={**payload, 'team_focus': bad})

        assert response.status_code == 200
        assert stored()[0].team_focus is None

    def test_team_focus_is_cut_to_200_characters(self, client, url, payload, source):
        response = client.post(url, json={**payload, 'team_focus': 'F' * 5000})

        assert response.status_code == 200
        assert stored()[0].team_focus == 'F' * 200

    def test_team_focus_markup_is_stripped(self, client, url, payload, source):
        response = client.post(url, json={
            **payload, 'team_focus': 'Procurement <script>alert(1)</script><img src=x onerror=alert(2)>',
        })

        assert response.status_code == 200
        team_focus = stored()[0].team_focus
        assert '<' not in team_focus and '>' not in team_focus
        assert team_focus.startswith('Procurement')

    def test_ampersand_is_stored_as_typed(self, client, url, payload, source):
        response = client.post(url, json={**payload, 'team_focus': 'R&D and hiring'})

        assert response.status_code == 200
        assert stored()[0].team_focus == 'R&D and hiring'

    @pytest.mark.parametrize('code', TEAM_SIZE_CODES)
    def test_known_team_size_is_stored(self, client, url, payload, source, code):
        response = client.post(url, json={**payload, 'team_size': code})

        assert response.status_code == 200
        assert stored()[0].team_size == code

    @pytest.mark.parametrize('bad', [None, '', 'huge', 25, ['6-25']])
    def test_unknown_team_size_is_ignored(self, client, url, payload, source, bad):
        response = client.post(url, json={**payload, 'team_size': bad})

        assert response.status_code == 200
        assert stored()[0].team_size is None

    @pytest.mark.parametrize('body', [None, {}, [], ['a', 'b'], 'text', 7])
    def test_missing_or_non_object_body_is_rejected_and_nothing_is_stored(self, client, url, payload, source, body):
        response = client.post(url, json=body)

        assert response.status_code == 400
        assert response.get_json() == {'error': 'No data provided'}
        assert stored() == []

    def test_non_json_body_is_rejected(self, client, url, payload, source):
        plain = client.post(url, data='name=Ada', content_type='text/plain')
        broken = client.post(url, data='{"name": ', content_type='application/json')

        for response in (plain, broken):
            assert response.status_code == 400
            assert response.get_json() == {'error': 'No data provided'}
        assert stored() == []

    def test_invalid_email_is_rejected_and_nothing_is_stored(self, client, url, payload, source):
        email_key = 'contact_email' if source == 'sponsorship' else 'email'

        response = client.post(url, json={**payload, email_key: 'not-an-email'})

        assert response.status_code == 400
        assert response.get_json() == {'error': 'Invalid email address'}
        assert stored() == []

    def test_wrong_method_is_405(self, client, url, payload, source):
        response = client.put(url, json=payload)

        assert response.status_code == 405
        assert response.get_json() == {'error': 'Method not allowed'}
        assert stored() == []

    def test_anonymous_sender_has_no_user_or_tenant(self, client, url, payload, source):
        client.post(url, json=payload)

        inquiry = stored()[0]
        assert inquiry.user_id is None
        assert inquiry.tenant_domain is None

    def test_signed_in_sender_is_recorded(self, member_client, member, url, payload, source):
        response = member_client.post(url, json=payload)

        assert response.status_code == 200
        inquiry = stored()[0]
        assert inquiry.user_id == member.id
        assert inquiry.tenant_domain == 'acme.test'

    def test_super_admin_sender_is_not_recorded_as_a_user(self, master_client, url, payload, source):
        response = master_client.post(url, json=payload)

        assert response.status_code == 200
        inquiry = stored()[0]
        assert inquiry.user_id is None
        assert inquiry.tenant_domain is None


def test_no_ip_address_or_user_agent_is_stored(client):
    client.post('/api/contact', json=CONTACT, headers={
        'User-Agent': 'TrackMe/1.0', 'CF-Connecting-IP': '203.0.113.9',
    })

    columns = {column.name for column in Inquiry.__table__.columns}
    assert not any('ip' == name or 'ip_' in name or 'agent' in name for name in columns)
    row = stored()[0].to_dict()
    assert 'TrackMe/1.0' not in str(row)
    assert '203.0.113.9' not in str(row)


class TestContactForm:

    def test_fields_are_stored(self, client):
        client.post('/api/contact', json={**CONTACT, 'team_focus': 'Clinical protocols'})

        inquiry = stored()[0]
        assert inquiry.name == 'Ada Lovelace'
        assert inquiry.email == 'ada@example.org'
        assert inquiry.message == 'Hello, I would like to know more.'
        assert inquiry.team_focus == 'Clinical protocols'
        assert inquiry.organisation is None
        assert inquiry.area_of_interest is None
        assert inquiry.contact_consent is None

    def test_team_focus_is_included_in_the_email(self, client):
        enable_email()

        with patch('notifications.send_email', return_value=True) as send_email:
            client.post('/api/contact', json={**CONTACT, 'team_focus': 'Clinical protocols'})

        _config, _to, _subject, html_content, text_content = send_email.call_args.args
        assert 'Clinical protocols' in html_content
        assert 'Clinical protocols' in text_content

    def test_email_is_unchanged_without_team_focus(self, client):
        enable_email()

        with patch('notifications.send_email', return_value=True) as send_email:
            client.post('/api/contact', json=CONTACT)

        _config, _to, _subject, html_content, text_content = send_email.call_args.args
        assert 'Team decides about' not in html_content
        assert 'Team decides about' not in text_content

    @pytest.mark.parametrize('missing', ['name', 'email', 'message'])
    def test_required_field_missing_stores_nothing(self, client, missing):
        payload = {key: value for key, value in CONTACT.items() if key != missing}

        response = client.post('/api/contact', json=payload)

        assert response.status_code == 400
        assert response.get_json() == {'error': 'Name, email, and message are required'}
        assert stored() == []

    def test_overlong_fields_are_cut(self, client):
        client.post('/api/contact', json={'name': 'N' * 500, 'email': 'ada@example.org', 'message': 'M' * 20000})

        inquiry = stored()[0]
        assert inquiry.name == 'N' * 100
        assert inquiry.message == 'M' * 5000


class TestSponsorshipForm:

    def test_fields_are_stored(self, client):
        client.post('/api/sponsorship', json={
            **SPONSORSHIP, 'contact_name': 'Ada Lovelace', 'area_of_interest': 'Sponsorship',
            'message': 'We would like to help.', 'team_focus': 'Capital spending',
        })

        inquiry = stored()[0]
        assert inquiry.organisation == 'Analytical Engines Ltd'
        assert inquiry.email == 'ada@example.org'
        assert inquiry.name == 'Ada Lovelace'
        assert inquiry.area_of_interest == 'Sponsorship'
        assert inquiry.message == 'We would like to help.'
        assert inquiry.team_focus == 'Capital spending'

    def test_null_optional_fields_are_accepted(self, client):
        """JSON null used to raise AttributeError ('NoneType' has no attribute 'strip')."""
        enable_email()

        with patch('notifications.send_email', return_value=True) as send_email:
            response = client.post('/api/sponsorship', json={
                **SPONSORSHIP, 'contact_name': None, 'area_of_interest': None, 'message': None,
                'team_focus': None,
            })

        assert response.status_code == 200
        send_email.assert_called_once()
        inquiry = stored()[0]
        assert inquiry.name is None
        assert inquiry.area_of_interest is None
        assert inquiry.message is None

    @pytest.mark.parametrize('bad', [42, 3.5, True, ['x'], {'a': 1}, '', '   '])
    def test_optional_fields_of_the_wrong_type_are_treated_as_not_given(self, client, bad):
        response = client.post('/api/sponsorship', json={
            **SPONSORSHIP, 'contact_name': bad, 'area_of_interest': bad, 'message': bad,
        })

        assert response.status_code == 200
        inquiry = stored()[0]
        assert inquiry.name is None
        assert inquiry.area_of_interest is None
        assert inquiry.message is None

    def test_missing_optional_fields_are_accepted(self, client):
        response = client.post('/api/sponsorship', json=SPONSORSHIP)

        assert response.status_code == 200
        assert response.get_json() == {'message': 'Thank you for reaching out! We will be in touch shortly.'}

    @pytest.mark.parametrize('field', ['organisation_name', 'contact_email'])
    @pytest.mark.parametrize('bad', [None, '', '  ', 42, ['x']])
    def test_required_field_null_blank_or_wrong_type_is_rejected(self, client, field, bad):
        response = client.post('/api/sponsorship', json={**SPONSORSHIP, field: bad})

        assert response.status_code == 400
        assert response.get_json() == {'error': 'Organisation name and contact email are required'}
        assert stored() == []

    @pytest.mark.parametrize('field', ['organisation_name', 'contact_email'])
    def test_required_field_missing_is_rejected(self, client, field):
        payload = {key: value for key, value in SPONSORSHIP.items() if key != field}

        response = client.post('/api/sponsorship', json=payload)

        assert response.status_code == 400
        assert stored() == []

    def test_overlong_fields_are_cut(self, client):
        client.post('/api/sponsorship', json={
            'organisation_name': 'O' * 900, 'contact_email': 'ada@example.org',
            'contact_name': 'N' * 900, 'area_of_interest': 'A' * 900, 'message': 'M' * 9000,
        })

        inquiry = stored()[0]
        assert inquiry.organisation == 'O' * 200
        assert inquiry.name == 'N' * 100
        assert inquiry.area_of_interest == 'A' * 100
        assert inquiry.message == 'M' * 2000

    def test_team_focus_is_included_in_the_email(self, client):
        enable_email()

        with patch('notifications.send_email', return_value=True) as send_email:
            client.post('/api/sponsorship', json={**SPONSORSHIP, 'team_focus': 'Capital spending'})

        _config, _to, _subject, html_content, text_content = send_email.call_args.args
        assert 'Capital spending' in html_content
        assert 'Capital spending' in text_content


class TestFeedbackForm:

    def test_fields_and_consent_are_stored(self, client):
        client.post('/api/feedback', json={**FEEDBACK, 'contact_consent': True})

        inquiry = stored()[0]
        assert inquiry.name == 'Ada Lovelace'
        assert inquiry.message == 'The decision list is easy to read.'
        assert inquiry.contact_consent is True

    def test_consent_defaults_to_no(self, client):
        client.post('/api/feedback', json=FEEDBACK)

        assert stored()[0].contact_consent is False

    def test_camel_case_consent_from_the_app_dialog_is_honoured(self, client):
        client.post('/api/feedback', json={**FEEDBACK, 'contactConsent': True})

        assert stored()[0].contact_consent is True

    @pytest.mark.parametrize('field', ['name', 'email', 'feedback'])
    @pytest.mark.parametrize('bad', [None, '', '  ', 42, ['x'], {'a': 1}])
    def test_required_field_null_blank_or_wrong_type_is_rejected(self, client, field, bad):
        """JSON null used to raise AttributeError and answer 500."""
        response = client.post('/api/feedback', json={**FEEDBACK, field: bad})

        assert response.status_code == 400
        assert response.get_json() == {'error': 'Name, email, and feedback are required'}
        assert stored() == []

    def test_short_feedback_is_rejected(self, client):
        response = client.post('/api/feedback', json={**FEEDBACK, 'feedback': 'Too short'})

        assert response.status_code == 400
        assert response.get_json() == {'error': 'Feedback must be at least 10 characters'}
        assert stored() == []

    def test_success_message_is_unchanged(self, client):
        response = client.post('/api/feedback', json=FEEDBACK)

        assert response.get_json() == {'message': 'Thank you for your feedback! We will review it shortly.'}

    def test_overlong_feedback_is_cut(self, client):
        client.post('/api/feedback', json={**FEEDBACK, 'feedback': 'F' * 20000})

        assert stored()[0].message == 'F' * 5000


# ==================== Super admin endpoints ====================

SUPERADMIN_REQUESTS = [
    ('get', '/api/superadmin/inquiries', None),
    ('get', '/api/superadmin/inquiries/summary', None),
    ('put', '/api/superadmin/inquiries/{id}/handled', {'handled': True}),
    ('delete', '/api/superadmin/inquiries/{id}', None),
]
SUPERADMIN_IDS = ['list', 'summary', 'mark-handled', 'delete']


def _call(test_client, method, url, body, inquiry_id):
    kwargs = {'json': body} if body is not None else {}
    return getattr(test_client, method)(url.format(id=inquiry_id), **kwargs)


@pytest.mark.parametrize('method,url,body', SUPERADMIN_REQUESTS, ids=SUPERADMIN_IDS)
class TestSuperadminInquiriesAuthorisation:

    def test_anonymous_is_refused(self, client, method, url, body):
        inquiry = add_inquiry()

        response = _call(client, method, url, body, inquiry.id)

        assert response.status_code == 401
        assert response.get_json() == {'error': 'Authentication required'}
        assert len(stored()) == 1 and stored()[0].handled is False

    def test_ordinary_user_is_refused(self, member_client, method, url, body):
        inquiry = add_inquiry()

        response = _call(member_client, method, url, body, inquiry.id)

        assert response.status_code == 403
        assert response.get_json() == {'error': 'Master account access required'}
        assert len(stored()) == 1 and stored()[0].handled is False

    def test_tenant_admin_is_refused(self, admin_client, method, url, body):
        inquiry = add_inquiry()

        response = _call(admin_client, method, url, body, inquiry.id)

        assert response.status_code == 403
        assert response.get_json() == {'error': 'Master account access required'}
        assert len(stored()) == 1 and stored()[0].handled is False

    def test_super_admin_is_allowed(self, master_client, method, url, body):
        inquiry = add_inquiry()

        response = _call(master_client, method, url, body, inquiry.id)

        assert response.status_code == 200


class TestSuperadminInquiryList:

    def test_empty_list(self, master_client):
        body = master_client.get('/api/superadmin/inquiries').get_json()

        assert body == {'total': 0, 'limit': 50, 'offset': 0, 'unhandled_total': 0, 'items': []}

    def test_newest_first_with_every_field(self, master_client):
        old = add_inquiry(days_ago=3, name='Old')
        new = add_inquiry('sponsorship', days_ago=0, name='New', organisation='Acme',
                          area_of_interest='Sponsorship', team_focus='Hiring', team_size='6-25')

        body = master_client.get('/api/superadmin/inquiries').get_json()

        assert [item['id'] for item in body['items']] == [new.id, old.id]
        assert body['total'] == 2 and body['unhandled_total'] == 2
        first = body['items'][0]
        assert first['source'] == 'sponsorship'
        assert first['organisation'] == 'Acme'
        assert first['team_focus'] == 'Hiring'
        assert first['team_size'] == '6-25'
        assert first['team_size_label'] == '6 to 25 people'
        assert first['email_sent'] is False
        assert first['handled'] is False
        assert first['redacted'] is False
        assert set(first) >= {
            'id', 'source', 'name', 'email', 'organisation', 'area_of_interest', 'message',
            'team_focus', 'team_size', 'user_id', 'tenant_domain', 'created_at', 'email_sent',
            'handled', 'handled_at', 'handled_by', 'contact_consent',
        }

    def test_paging(self, master_client):
        ids = [add_inquiry(days_ago=10 - n, name=f'Sender {n}').id for n in range(5)]
        newest_first = list(reversed(ids))

        first = master_client.get('/api/superadmin/inquiries?limit=2').get_json()
        second = master_client.get('/api/superadmin/inquiries?limit=2&offset=2').get_json()
        last = master_client.get('/api/superadmin/inquiries?limit=2&offset=4').get_json()
        beyond = master_client.get('/api/superadmin/inquiries?limit=2&offset=40').get_json()

        assert [item['id'] for item in first['items']] == newest_first[:2]
        assert [item['id'] for item in second['items']] == newest_first[2:4]
        assert [item['id'] for item in last['items']] == newest_first[4:]
        assert beyond['items'] == []
        for page in (first, second, last, beyond):
            assert page['total'] == 5 and page['limit'] == 2

    def test_limit_is_capped(self, master_client):
        assert master_client.get('/api/superadmin/inquiries?limit=5000').get_json()['limit'] == 200
        assert master_client.get('/api/superadmin/inquiries?limit=0').get_json()['limit'] == 1
        assert master_client.get('/api/superadmin/inquiries?offset=-5').get_json()['offset'] == 0

    @pytest.mark.parametrize('query', ['limit=abc', 'offset=1.5', 'source=newsletter', 'handled=maybe'])
    def test_invalid_query_is_rejected(self, master_client, query):
        response = master_client.get(f'/api/superadmin/inquiries?{query}')

        assert response.status_code == 400
        assert 'error' in response.get_json()

    def test_filter_by_source(self, master_client):
        add_inquiry('contact')
        add_inquiry('feedback')
        add_inquiry('feedback')

        body = master_client.get('/api/superadmin/inquiries?source=feedback').get_json()

        assert body['total'] == 2
        assert {item['source'] for item in body['items']} == {'feedback'}

    def test_filter_by_handled_state(self, master_client):
        add_inquiry(name='Open')
        add_inquiry(name='Done', handled=True)

        handled = master_client.get('/api/superadmin/inquiries?handled=true').get_json()
        unhandled = master_client.get('/api/superadmin/inquiries?handled=false').get_json()
        everything = master_client.get('/api/superadmin/inquiries?handled=').get_json()

        assert [item['name'] for item in handled['items']] == ['Done']
        assert [item['name'] for item in unhandled['items']] == ['Open']
        assert everything['total'] == 2
        # The unhandled count ignores the filter: it feeds the navigation badge
        assert handled['unhandled_total'] == 1

    def test_filters_combine(self, master_client):
        add_inquiry('contact', handled=True)
        add_inquiry('feedback', handled=True)
        add_inquiry('feedback')

        body = master_client.get('/api/superadmin/inquiries?source=feedback&handled=true').get_json()

        assert body['total'] == 1


class TestSuperadminInquiryActions:

    def test_mark_handled_records_who_and_when(self, master_client):
        inquiry = add_inquiry()

        response = master_client.put(f'/api/superadmin/inquiries/{inquiry.id}/handled', json={'handled': True})

        assert response.status_code == 200
        body = response.get_json()
        assert body['message'] == 'Inquiry marked as handled'
        assert body['inquiry']['handled'] is True
        assert body['inquiry']['handled_by'] == DEFAULT_MASTER_USERNAME
        assert body['inquiry']['handled_at'] is not None
        assert stored()[0].handled is True

    def test_mark_unhandled_clears_who_and_when(self, master_client):
        inquiry = add_inquiry(handled=True, handled_by='admin', handled_at=datetime.now(timezone.utc))

        response = master_client.put(f'/api/superadmin/inquiries/{inquiry.id}/handled', json={'handled': False})

        assert response.status_code == 200
        body = response.get_json()
        assert body['message'] == 'Inquiry marked as not handled'
        assert body['inquiry']['handled'] is False
        assert body['inquiry']['handled_by'] is None
        assert body['inquiry']['handled_at'] is None

    @pytest.mark.parametrize('body', [None, {}, {'handled': None}, {'handled': 'yes'}, {'handled': 1}, ['true']])
    def test_handled_must_be_a_boolean(self, master_client, body):
        inquiry = add_inquiry()

        response = master_client.put(f'/api/superadmin/inquiries/{inquiry.id}/handled', json=body)

        assert response.status_code == 400
        assert response.get_json() == {'error': 'handled must be true or false'}
        assert stored()[0].handled is False

    def test_mark_handled_unknown_id_is_404(self, master_client):
        response = master_client.put('/api/superadmin/inquiries/9999/handled', json={'handled': True})

        assert response.status_code == 404
        assert response.get_json() == {'error': 'Inquiry not found'}

    def test_delete_removes_only_that_inquiry(self, master_client):
        keep = add_inquiry(name='Keep')
        remove = add_inquiry(name='Remove')

        response = master_client.delete(f'/api/superadmin/inquiries/{remove.id}')

        assert response.status_code == 200
        assert response.get_json() == {'message': 'Inquiry deleted'}
        assert [inquiry.id for inquiry in stored()] == [keep.id]

    def test_delete_unknown_id_is_404(self, master_client):
        response = master_client.delete('/api/superadmin/inquiries/9999')

        assert response.status_code == 404
        assert response.get_json() == {'error': 'Inquiry not found'}

    @pytest.mark.parametrize('method', ['put', 'delete'])
    def test_writes_need_a_csrf_token(self, master_client, method):
        inquiry = add_inquiry()
        url = f'/api/superadmin/inquiries/{inquiry.id}' + ('/handled' if method == 'put' else '')

        response = getattr(master_client, method)(
            url, json={'handled': True}, environ_overrides={'HTTP_X_CSRF_TOKEN': ''}
        )

        assert response.status_code == 403
        assert len(stored()) == 1 and stored()[0].handled is False


class TestInterestSummary:

    def test_empty_installation(self, master_client):
        body = master_client.get('/api/superadmin/inquiries/summary').get_json()

        assert body['tenants']['total'] == 0
        assert body['inquiries'] == {
            'total': 0, 'unhandled': 0, 'not_emailed': 0,
            'by_source': [
                {'source': 'contact', 'count': 0},
                {'source': 'sponsorship', 'count': 0},
                {'source': 'feedback', 'count': 0},
            ],
            'by_team_size': body['tenants']['by_team_size'],
        }
        assert [row['code'] for row in body['tenants']['by_team_size']] == list(TEAM_SIZE_CODES) + [None]
        assert all(row['count'] == 0 for row in body['tenants']['by_team_size'])
        assert body['team_focus_answers'] == []

    def test_counts_and_distinct_answers(self, master_client):
        small = _make_tenant('small.test', 'Small')
        small.team_size, small.team_focus = '1-5', 'Hiring'
        other = _make_tenant('other.test', 'Other')
        other.team_size, other.team_focus = '1-5', '  hiring '
        large = _make_tenant('large.test', 'Large')
        large.team_size, large.team_focus = '501+', 'Clinical protocols'
        _make_tenant('silent.test', 'Silent')
        deleted = _make_tenant('gone.test', 'Gone')
        deleted.team_size, deleted.team_focus = '6-25', 'Should not be listed'
        deleted.deleted_at = datetime.now(timezone.utc)
        db.session.commit()

        add_inquiry('contact', team_focus='Hiring', team_size='6-25', email_sent=True)
        add_inquiry('contact', team_focus='Supplier choices', handled=True)
        add_inquiry('feedback')

        body = master_client.get('/api/superadmin/inquiries/summary').get_json()

        tenant_sizes = {row['code']: row['count'] for row in body['tenants']['by_team_size']}
        assert body['tenants']['total'] == 4
        assert body['tenants']['with_team_focus'] == 3
        assert tenant_sizes == {'1-5': 2, '6-25': 0, '26-100': 0, '101-500': 0, '501+': 1, None: 1}

        inquiry_sizes = {row['code']: row['count'] for row in body['inquiries']['by_team_size']}
        assert body['inquiries']['total'] == 3
        assert body['inquiries']['unhandled'] == 2
        assert body['inquiries']['not_emailed'] == 2
        assert inquiry_sizes['6-25'] == 1 and inquiry_sizes[None] == 2
        assert {row['source']: row['count'] for row in body['inquiries']['by_source']} == {
            'contact': 2, 'sponsorship': 0, 'feedback': 1,
        }

        answers = {entry['text']: (entry['tenants'], entry['inquiries']) for entry in body['team_focus_answers']}
        assert answers == {
            'Clinical protocols': (1, 0),
            'Hiring': (2, 1),
            'Supplier choices': (0, 1),
        }
        assert [entry['text'] for entry in body['team_focus_answers']] == sorted(answers, key=str.lower)

    def test_labels_are_given_for_every_size(self, master_client):
        body = master_client.get('/api/superadmin/inquiries/summary').get_json()

        labels = [row['label'] for row in body['tenants']['by_team_size']]
        assert labels == [
            '1 to 5 people', '6 to 25 people', '26 to 100 people', '101 to 500 people',
            'More than 500 people', 'Not answered',
        ]


# ==================== Where the three forms are emailed ====================

@pytest.mark.parametrize('url,payload,source', FORMS, ids=FORM_IDS)
class TestFormsShareOneRecipient:
    """All three forms go to the Contact Form Email setting, with one default."""

    def _recipient(self, client, url, payload):
        enable_email()
        with patch('notifications.send_email', return_value=True) as send_email:
            response = client.post(url, json=payload)
        assert response.status_code == 200, response.get_json()
        send_email.assert_called_once()
        return send_email.call_args.args[1]

    def test_default_is_the_address_the_public_pages_give(self, client, url, payload, source):
        assert SystemConfig.DEFAULT_SUPPORT_EMAIL == 'contact@decisionrecords.org'
        assert self._recipient(client, url, payload) == 'contact@decisionrecords.org'

    def test_the_setting_is_used(self, client, url, payload, source):
        SystemConfig.set(SystemConfig.KEY_SUPPORT_EMAIL, 'desk@example.org')

        assert self._recipient(client, url, payload) == 'desk@example.org'

    def test_a_setting_that_holds_the_old_default_keeps_its_value(self, client, url, payload, source):
        """A super admin who saved the old address chose it; nothing rewrites it."""
        SystemConfig.set(SystemConfig.KEY_SUPPORT_EMAIL, 'admin@decisionrecords.org')

        assert self._recipient(client, url, payload) == 'admin@decisionrecords.org'
        assert SystemConfig.get(SystemConfig.KEY_SUPPORT_EMAIL) == 'admin@decisionrecords.org'


class TestNotificationDefaultsAgree:
    """Called without a recipient, each email function falls back to the same address."""

    def test_no_function_has_an_address_of_its_own(self, api_app):
        import inspect
        import notifications

        for function in (notifications.send_feedback_email, notifications.send_contact_email,
                         notifications.send_sponsorship_inquiry_email):
            source = inspect.getsource(function)
            assert '@decisionrecords.org' not in source, function.__name__
            assert 'recipient_email' in inspect.signature(function).parameters, function.__name__

    def test_each_falls_back_to_the_default(self, api_app):
        import notifications

        with patch('notifications.send_email', return_value=True) as send_email:
            notifications.send_feedback_email(None, 'Ada', 'ada@example.org', 'Some feedback here')
            notifications.send_contact_email(None, 'Ada', 'ada@example.org', 'A message')
            notifications.send_sponsorship_inquiry_email(None, 'Example Org', 'ada@example.org')

        assert [call.args[1] for call in send_email.call_args_list] == ['contact@decisionrecords.org'] * 3


class TestStartingUpKeepsAStoredRecipient:

    def test_init_database_does_not_touch_a_stored_contact_email(self, app_module, api_app):
        SystemConfig.set(SystemConfig.KEY_SUPPORT_EMAIL, 'admin@decisionrecords.org')

        app_module._db_initialized = False
        app_module.init_database()

        assert SystemConfig.get(SystemConfig.KEY_SUPPORT_EMAIL) == 'admin@decisionrecords.org'

    def test_super_admin_settings_report_the_new_default(self, api_app):
        from models import DEFAULT_MASTER_PASSWORD, DEFAULT_MASTER_USERNAME
        admin = api_app.test_client()
        login = admin.post('/auth/local', json={
            'username': DEFAULT_MASTER_USERNAME, 'password': DEFAULT_MASTER_PASSWORD})
        assert login.status_code == 200

        settings = admin.get('/api/admin/settings/support').get_json()

        assert settings['support_email'] == 'contact@decisionrecords.org'
        assert settings['defaults']['support_email'] == 'contact@decisionrecords.org'
