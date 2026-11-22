"""
Access requests: a setup link only ever reaches someone entitled to it.

A person asking to join an organisation is anonymous. The link that lets them
set their credentials is delivered either to the mailbox they claim (which
proves they control it) or to an administrator of that organisation, who
passes it on. It is never returned in the response to the request itself.

The four situations covered are email delivery configured or not, crossed
with an organisation that has a full administrator or only its provisional
(first) administrator.
"""
import os
import sys
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    db, User, Tenant, TenantMembership, AuthConfig, EmailConfig, AccessRequest,
    ArchitectureDecision, GlobalRole, MaturityState, SetupToken, SystemConfig
)
from tests.app_test_utils import load_test_app

PASSWORD = 'Str0ngPassword'
DOMAIN = 'acme.test'
REQUEST = '/api/auth/access-request'
SEND = 'notifications.send_account_setup_email'


@pytest.fixture
def real_app():
    app_module, test_app = load_test_app(secret_key='test-secret-key-access-requests')

    with test_app.app_context():
        db.create_all()
        app_module.init_database()
        yield app_module, test_app
        db.session.remove()
        db.drop_all()
        app_module._db_initialized = False


def make_member(email, role, *, is_admin=None):
    domain = email.split('@')[1]
    tenant = Tenant.query.filter_by(domain=domain).first()
    if not tenant:
        tenant = Tenant(domain=domain, name=domain, status='active',
                        maturity_state=MaturityState.BOOTSTRAP)
        db.session.add(tenant)
        db.session.flush()
    if is_admin is None:
        is_admin = role != GlobalRole.USER
    user = User(email=email, sso_domain=domain, auth_type='local', email_verified=True,
                is_admin=is_admin)
    user.set_name(first_name='Org', last_name='Member')
    user.set_password(PASSWORD)
    db.session.add(user)
    db.session.flush()
    db.session.add(TenantMembership(user_id=user.id, tenant_id=tenant.id, global_role=role))
    db.session.commit()
    return user


def make_organisation(admin_role, *, require_approval=None, domain=DOMAIN):
    """An organisation with one administrator and one internal decision."""
    admin = make_member(f'owner@{domain}', admin_role)
    tenant = Tenant.query.filter_by(domain=domain).first()
    db.session.add(ArchitectureDecision(
        title='Internal decision', context='c', decision='d', status='proposed',
        consequences='x', domain=domain, tenant_id=tenant.id, created_by_id=admin.id,
        decision_number=1))
    if require_approval is not None:
        db.session.add(AuthConfig(domain=domain, require_approval=require_approval))
    db.session.commit()
    return admin


def configure_email():
    db.session.add(EmailConfig(
        domain='system', smtp_server='smtp.example.test', smtp_port=587,
        smtp_username='mailer', smtp_password='secret', from_email='noreply@example.test',
        enabled=True))
    db.session.commit()


def ask_to_join(client, email=f'newcomer@{DOMAIN}'):
    return client.post(REQUEST, json={
        'email': email, 'first_name': 'New', 'last_name': 'Comer',
        'domain': email.split('@')[1], 'reason': 'I work here',
    })


def sign_in(test_app, email):
    client = test_app.test_client()
    response = client.post('/api/auth/login', json={'email': email, 'password': PASSWORD})
    assert response.status_code == 200, response.get_json()
    client.environ_base['HTTP_X_CSRF_TOKEN'] = response.headers['X-CSRF-Token']
    return client


def token_from(setup_url):
    return parse_qs(urlparse(setup_url).query)['token'][0]


def contains_setup_link(response):
    """True if a setup link or token appears anywhere in the response."""
    text = response.get_data(as_text=True)
    return 'setup_url' in text or 'setup_token' in text or '/setup?token=' in text


def assert_waiting_for_admin(response, email=f'newcomer@{DOMAIN}'):
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert not body.get('auto_approved')
    assert not contains_setup_link(response)
    assert User.query.filter_by(email=email).first() is None
    assert SetupToken.query.count() == 0
    pending = AccessRequest.query.filter_by(email=email, status='pending').all()
    assert len(pending) == 1
    return body


def approve_as(test_app, admin_email, email=f'newcomer@{DOMAIN}'):
    admin_client = sign_in(test_app, admin_email)
    pending = admin_client.get('/api/admin/access-requests/pending')
    assert pending.status_code == 200, pending.get_json()
    request_id = next(item['id'] for item in pending.get_json() if item['email'] == email)
    return admin_client.post(f'/api/admin/access-requests/{request_id}/approve', json={})


def complete_setup_and_read_decisions(test_app, setup_url):
    """The newcomer uses their link, sets a password and opens the decision list."""
    client = test_app.test_client()
    setup = client.post('/api/auth/setup-password',
                        json={'token': token_from(setup_url), 'password': PASSWORD})
    assert setup.status_code == 200, setup.get_json()
    decisions = client.get('/api/decisions')
    assert decisions.status_code == 200, decisions.get_json()
    return [item['title'] for item in decisions.get_json()]


# ==================== The requester never receives the link ====================

class TestRequesterNeverReceivesTheSetupLink:

    @pytest.mark.parametrize('verification_required', [False, True])
    def test_request_to_new_organisation_without_email_returns_no_link(self, real_app,
                                                                       verification_required):
        """No email delivery, organisation with only its first administrator."""
        _, test_app = real_app
        make_organisation(GlobalRole.PROVISIONAL_ADMIN)
        SystemConfig.set(SystemConfig.KEY_EMAIL_VERIFICATION_REQUIRED,
                         'true' if verification_required else 'false')
        client = test_app.test_client()

        response = ask_to_join(client)

        assert_waiting_for_admin(response)
        assert client.get('/api/decisions').status_code == 401

    @pytest.mark.parametrize('admin_role', [GlobalRole.PROVISIONAL_ADMIN, GlobalRole.ADMIN])
    @pytest.mark.parametrize('email_configured', [False, True])
    @pytest.mark.parametrize('require_approval', [None, True, False])
    @pytest.mark.parametrize('delivery', ['sent', 'not_sent', 'raises'])
    def test_no_combination_puts_a_link_in_the_response(self, real_app, admin_role,
                                                        email_configured, require_approval, delivery):
        _, test_app = real_app
        make_organisation(admin_role, require_approval=require_approval)
        if email_configured:
            configure_email()
        behaviour = {
            'sent': {'return_value': True},
            'not_sent': {'return_value': False},
            'raises': {'side_effect': RuntimeError('SMTP connection refused')},
        }[delivery]

        with patch(SEND, **behaviour):
            response = ask_to_join(test_app.test_client())

        assert response.status_code == 200, response.get_json()
        assert not contains_setup_link(response)


# ==================== The four situations ====================

class TestEmailConfiguredProvisionalAdminOnly:
    """Nobody but the first administrator exists yet; the mailbox is the proof."""

    def test_account_is_created_and_the_link_goes_to_the_mailbox(self, real_app):
        _, test_app = real_app
        make_organisation(GlobalRole.PROVISIONAL_ADMIN)
        configure_email()

        with patch(SEND, return_value=True) as send:
            response = ask_to_join(test_app.test_client())

        body = response.get_json()
        assert response.status_code == 200
        assert body['auto_approved'] is True
        assert not contains_setup_link(response)
        assert send.call_count == 1
        _, _, recipient, setup_url = send.call_args.args[:4]
        assert recipient == f'newcomer@{DOMAIN}'
        assert f'/{DOMAIN}/setup?token=' in setup_url
        assert User.query.filter_by(email=f'newcomer@{DOMAIN}').first() is not None
        assert AccessRequest.query.count() == 0
        assert complete_setup_and_read_decisions(test_app, setup_url) == ['Internal decision']

    @pytest.mark.parametrize('behaviour', [
        {'return_value': False},
        {'side_effect': RuntimeError('SMTP connection refused')},
    ])
    def test_failed_delivery_leaves_a_request_the_administrator_can_approve(self, real_app, behaviour):
        _, test_app = real_app
        make_organisation(GlobalRole.PROVISIONAL_ADMIN)
        configure_email()

        with patch(SEND, **behaviour):
            response = ask_to_join(test_app.test_client())

        body = assert_waiting_for_admin(response)
        assert body['email_sent'] is False
        assert 'could not be sent' in body['message']

        # Email is still failing when the administrator approves
        with patch(SEND, **behaviour):
            approval = approve_as(test_app, f'owner@{DOMAIN}')
        assert approval.status_code == 200, approval.get_json()
        assert approval.get_json()['email_sent'] is False
        assert 'yourself' in approval.get_json()['delivery_message']
        assert complete_setup_and_read_decisions(
            test_app, approval.get_json()['setup_url']) == ['Internal decision']

    def test_failed_delivery_does_not_block_a_second_attempt_from_working_later(self, real_app):
        """The same person asking again is told a request is already pending, not given a link."""
        _, test_app = real_app
        make_organisation(GlobalRole.PROVISIONAL_ADMIN)
        configure_email()
        with patch(SEND, return_value=False):
            ask_to_join(test_app.test_client())

        with patch(SEND, return_value=True) as send:
            again = ask_to_join(test_app.test_client())

        assert again.status_code == 400
        assert again.get_json()['error'] == 'You already have a pending access request'
        assert send.call_count == 0
        assert not contains_setup_link(again)


class TestEmailConfiguredFullAdmin:

    @pytest.mark.parametrize('require_approval', [None, True])
    def test_request_waits_for_the_administrator(self, real_app, require_approval):
        _, test_app = real_app
        make_organisation(GlobalRole.ADMIN, require_approval=require_approval)
        configure_email()

        with patch(SEND, return_value=True) as send:
            response = ask_to_join(test_app.test_client())

        assert_waiting_for_admin(response)
        assert send.call_count == 0

        with patch(SEND, return_value=True) as send:
            approval = approve_as(test_app, f'owner@{DOMAIN}')
        assert approval.status_code == 200
        assert send.call_count == 1  # approval is when the requester is emailed
        assert complete_setup_and_read_decisions(
            test_app, approval.get_json()['setup_url']) == ['Internal decision']

    def test_organisation_that_switched_approval_off_admits_by_email(self, real_app):
        _, test_app = real_app
        make_organisation(GlobalRole.ADMIN, require_approval=False)
        configure_email()

        with patch(SEND, return_value=True) as send:
            response = ask_to_join(test_app.test_client())

        assert response.get_json()['auto_approved'] is True
        assert not contains_setup_link(response)
        assert send.call_count == 1


class TestNoEmailFullAdmin:

    @pytest.mark.parametrize('require_approval', [None, True, False])
    def test_request_waits_for_the_administrator_who_is_shown_the_link(self, real_app,
                                                                      require_approval):
        _, test_app = real_app
        make_organisation(GlobalRole.ADMIN, require_approval=require_approval)

        with patch(SEND, return_value=True) as send:
            response = ask_to_join(test_app.test_client())

        body = assert_waiting_for_admin(response)
        assert body['email_sent'] is False
        assert send.call_count == 0

        approval = approve_as(test_app, f'owner@{DOMAIN}')
        assert approval.status_code == 200
        assert complete_setup_and_read_decisions(
            test_app, approval.get_json()['setup_url']) == ['Internal decision']


class TestNoEmailProvisionalAdminOnly:
    """A new organisation without email must still be able to admit its second member."""

    def test_first_administrator_approves_and_is_shown_the_link(self, real_app):
        _, test_app = real_app
        make_organisation(GlobalRole.PROVISIONAL_ADMIN)

        response = ask_to_join(test_app.test_client())
        body = assert_waiting_for_admin(response)
        assert 'administrator' in body['message']

        approval = approve_as(test_app, f'owner@{DOMAIN}')

        assert approval.status_code == 200, approval.get_json()
        approved = approval.get_json()
        assert f'/{DOMAIN}/setup?token=' in approved['setup_url']
        assert approved['user']['email'] == f'newcomer@{DOMAIN}'
        assert AccessRequest.query.filter_by(status='pending').count() == 0
        assert complete_setup_and_read_decisions(test_app, approved['setup_url']) == ['Internal decision']
        assert User.query.filter_by(sso_domain=DOMAIN).count() == 2

    def test_administrator_can_see_the_pending_request(self, real_app):
        _, test_app = real_app
        make_organisation(GlobalRole.PROVISIONAL_ADMIN)
        ask_to_join(test_app.test_client())

        pending = sign_in(test_app, f'owner@{DOMAIN}').get('/api/admin/access-requests/pending')

        assert pending.status_code == 200
        assert [item['email'] for item in pending.get_json()] == [f'newcomer@{DOMAIN}']


# ==================== Who may approve, and existing rules ====================

class TestApprovalIsRestricted:

    def _pending_request_id(self, test_app):
        make_organisation(GlobalRole.PROVISIONAL_ADMIN)
        ask_to_join(test_app.test_client())
        return AccessRequest.query.filter_by(status='pending').first().id

    def test_anonymous_caller_cannot_approve(self, real_app):
        _, test_app = real_app
        request_id = self._pending_request_id(test_app)

        response = test_app.test_client().post(f'/api/admin/access-requests/{request_id}/approve', json={})

        assert response.status_code == 401
        assert not contains_setup_link(response)

    def test_ordinary_member_cannot_approve(self, real_app):
        _, test_app = real_app
        request_id = self._pending_request_id(test_app)
        make_member(f'member@{DOMAIN}', GlobalRole.USER)

        response = sign_in(test_app, f'member@{DOMAIN}').post(
            f'/api/admin/access-requests/{request_id}/approve', json={})

        assert response.status_code == 403
        assert not contains_setup_link(response)

    def test_administrator_of_another_organisation_cannot_approve(self, real_app):
        _, test_app = real_app
        request_id = self._pending_request_id(test_app)
        make_member('owner@other.test', GlobalRole.ADMIN)

        response = sign_in(test_app, 'owner@other.test').post(
            f'/api/admin/access-requests/{request_id}/approve', json={})

        assert response.status_code == 403
        assert not contains_setup_link(response)


class TestExistingAccessRequestRules:

    def test_existing_account_is_refused(self, real_app):
        _, test_app = real_app
        make_organisation(GlobalRole.ADMIN)

        response = ask_to_join(test_app.test_client(), email=f'owner@{DOMAIN}')

        assert response.status_code == 400
        assert response.get_json()['error'] == 'An account with this email already exists'

    def test_unknown_organisation_is_refused(self, real_app):
        _, test_app = real_app

        response = ask_to_join(test_app.test_client(), email='someone@nowhere.test')

        assert response.status_code == 400

    def test_missing_fields_are_refused(self, real_app):
        _, test_app = real_app

        response = test_app.test_client().post(REQUEST, json={'email': f'newcomer@{DOMAIN}'})

        assert response.status_code == 400
        assert response.get_json()['error'] == 'Email and first name are required'

    def test_user_limit_still_applies_to_automatic_admission(self, real_app):
        _, test_app = real_app
        make_organisation(GlobalRole.PROVISIONAL_ADMIN)
        configure_email()
        SystemConfig.set(SystemConfig.KEY_MAX_USERS_PER_TENANT, '1')

        with patch(SEND, return_value=True) as send:
            response = ask_to_join(test_app.test_client())

        assert response.status_code == 403
        assert response.get_json()['error'] == 'User limit reached'
        assert send.call_count == 0
        assert User.query.filter_by(email=f'newcomer@{DOMAIN}').first() is None


class TestTenantStatusMatchesAdmission:
    """The sign-in page offers "join" only when a request would be admitted by email."""

    @pytest.mark.parametrize('admin_role,email_configured,require_approval,expected', [
        (GlobalRole.PROVISIONAL_ADMIN, True, None, False),    # admitted by emailed link
        (GlobalRole.PROVISIONAL_ADMIN, False, None, True),    # waits for the first administrator
        (GlobalRole.ADMIN, True, None, True),                 # waits for an administrator
        (GlobalRole.ADMIN, False, None, True),
        (GlobalRole.ADMIN, True, False, False),               # approval switched off, email works
        (GlobalRole.ADMIN, False, False, True),               # approval switched off, no email
    ])
    def test_effective_require_approval(self, real_app, admin_role, email_configured,
                                        require_approval, expected):
        _, test_app = real_app
        make_organisation(admin_role, require_approval=require_approval)
        if email_configured:
            configure_email()

        status = test_app.test_client().get(f'/api/auth/tenant/{DOMAIN}')
        with patch(SEND, return_value=True):
            response = ask_to_join(test_app.test_client())

        assert status.status_code == 200, status.get_json()
        assert status.get_json()['effective_require_approval'] is expected
        # what the page promised is what the request did
        assert bool(response.get_json().get('auto_approved')) is (not expected)


# ==================== Approval emails the requester ====================

class TestApprovalEmailsTheRequester:
    """The sign-in page tells a requester they will hear by email; approval sends that email."""

    def _request_and_approve(self, test_app, send_result=True, side_effect=None):
        ask_to_join(test_app.test_client())
        with patch(SEND, return_value=send_result, side_effect=side_effect) as send:
            approval = approve_as(test_app, f'owner@{DOMAIN}')
        assert approval.status_code == 200, approval.get_json()
        return approval.get_json(), send

    def test_requester_is_emailed_the_setup_link_the_administrator_is_shown(self, real_app):
        _, test_app = real_app
        make_organisation(GlobalRole.ADMIN)
        configure_email()

        body, send = self._request_and_approve(test_app)

        assert send.call_count == 1
        args = send.call_args.args
        assert args[1] == 'New Comer'                       # name
        assert args[2] == f'newcomer@{DOMAIN}'              # recipient: the requester, nobody else
        assert args[3] == body['setup_url']                 # the same link
        assert args[4] == SetupToken.TOKEN_VALIDITY_HOURS
        assert send.call_args.kwargs == {'tenant_name': DOMAIN}
        assert body['email_sent'] is True
        assert body['delivery_message'] == f'The setup link was emailed to newcomer@{DOMAIN}.'
        # The emailed link works
        assert complete_setup_and_read_decisions(test_app, args[3]) == ['Internal decision']

    def test_without_email_the_administrator_is_told_to_pass_the_link_on(self, real_app):
        _, test_app = real_app
        make_organisation(GlobalRole.ADMIN)

        body, send = self._request_and_approve(test_app)

        assert send.call_count == 0
        assert body['email_sent'] is False
        assert body['delivery_message'] == (
            f'Email is not set up, so no email was sent. Give this link to newcomer@{DOMAIN} yourself.')
        assert f'/{DOMAIN}/setup?token=' in body['setup_url']

    @pytest.mark.parametrize('failure', [
        {'send_result': False},
        {'side_effect': RuntimeError('smtp down')},
    ], ids=['send reports failure', 'send raises'])
    def test_failed_send_still_approves_and_tells_the_administrator(self, real_app, failure):
        _, test_app = real_app
        make_organisation(GlobalRole.ADMIN)
        configure_email()

        body, send = self._request_and_approve(test_app, **failure)

        assert send.call_count == 1
        assert body['message'] == 'Access request approved'
        assert body['email_sent'] is False
        assert body['delivery_message'] == (
            f'The email to newcomer@{DOMAIN} could not be sent. Give this link to newcomer@{DOMAIN} yourself.')
        assert AccessRequest.query.filter_by(status='approved').count() == 1
        assert complete_setup_and_read_decisions(test_app, body['setup_url']) == ['Internal decision']

    def test_the_organisation_s_own_email_settings_are_used_when_there_are_no_system_ones(self, real_app):
        _, test_app = real_app
        make_organisation(GlobalRole.ADMIN)
        db.session.add(EmailConfig(
            domain=DOMAIN, smtp_server='smtp.acme.test', smtp_port=587, smtp_username='mailer',
            smtp_password='secret', from_email=f'noreply@{DOMAIN}', enabled=True))
        db.session.commit()

        body, send = self._request_and_approve(test_app)

        assert send.call_count == 1
        assert send.call_args.args[0].domain == DOMAIN
        assert body['email_sent'] is True

    def test_another_organisation_s_email_settings_are_never_used(self, real_app):
        _, test_app = real_app
        make_organisation(GlobalRole.ADMIN)
        db.session.add(EmailConfig(
            domain='globex.test', smtp_server='smtp.globex.test', smtp_port=587, smtp_username='mailer',
            smtp_password='secret', from_email='noreply@globex.test', enabled=True))
        db.session.commit()

        body, send = self._request_and_approve(test_app)

        assert send.call_count == 0
        assert body['email_sent'] is False

    def test_existing_account_without_credentials_is_emailed_its_link(self, real_app):
        _, test_app = real_app
        make_organisation(GlobalRole.ADMIN)
        configure_email()
        waiting = User(email=f'newcomer@{DOMAIN}', sso_domain=DOMAIN, auth_type='webauthn')
        waiting.set_name(first_name='New', last_name='Comer')
        db.session.add_all([waiting, AccessRequest(
            email=f'newcomer@{DOMAIN}', name='New Comer', domain=DOMAIN, reason='x')])
        db.session.commit()

        with patch(SEND, return_value=True) as send:
            approval = approve_as(test_app, f'owner@{DOMAIN}')

        body = approval.get_json()
        assert approval.status_code == 200, body
        assert send.call_count == 1
        assert send.call_args.args[3] == body['setup_url']
        assert body['email_sent'] is True

    def test_existing_account_with_credentials_gets_no_link_and_no_email(self, real_app):
        _, test_app = real_app
        make_organisation(GlobalRole.ADMIN)
        configure_email()
        make_member(f'newcomer@{DOMAIN}', GlobalRole.USER)
        db.session.add(AccessRequest(email=f'newcomer@{DOMAIN}', name='New Comer', domain=DOMAIN, reason='x'))
        db.session.commit()

        with patch(SEND, return_value=True) as send:
            approval = approve_as(test_app, f'owner@{DOMAIN}')

        body = approval.get_json()
        assert approval.status_code == 200, body
        assert send.call_count == 0
        assert body['setup_url'] is None
        assert body['email_sent'] is False
        assert body['delivery_message'] is None

    def test_refused_approval_sends_nothing(self, real_app):
        _, test_app = real_app
        make_organisation(GlobalRole.ADMIN)
        make_organisation(GlobalRole.ADMIN, domain='globex.test')
        configure_email()
        ask_to_join(test_app.test_client())
        request_id = AccessRequest.query.one().id

        with patch(SEND, return_value=True) as send:
            response = sign_in(test_app, 'owner@globex.test').post(
                f'/api/admin/access-requests/{request_id}/approve', json={})

        assert response.status_code == 403
        assert send.call_count == 0
        assert User.query.filter_by(email=f'newcomer@{DOMAIN}').first() is None

    def test_rejecting_a_request_sends_no_email(self, real_app):
        """There is no rejection email in the product; rejecting stays silent."""
        _, test_app = real_app
        make_organisation(GlobalRole.ADMIN)
        configure_email()
        ask_to_join(test_app.test_client())
        request_id = AccessRequest.query.one().id

        with patch('notifications.send_email', return_value=True) as send:
            response = sign_in(test_app, f'owner@{DOMAIN}').post(
                f'/api/admin/access-requests/{request_id}/reject', json={'reason': 'Not a colleague'})

        assert response.status_code == 200, response.get_json()
        assert send.call_count == 0


class TestRequesterIsToldWhatWillHappen:
    """What the sign-in page says after a request matches what approval will do."""

    def test_with_email_the_requester_is_told_an_email_will_come(self, real_app):
        _, test_app = real_app
        make_organisation(GlobalRole.ADMIN)
        configure_email()

        body = assert_waiting_for_admin(ask_to_join(test_app.test_client()))

        assert body['approval_email'] is True
        assert body['message'] == (
            'Your request has been submitted. When an administrator of your organization approves it, '
            'you will receive an email with a link to set up your sign-in. If the email cannot be sent, '
            'the administrator will give you the link.')

    def test_without_email_the_requester_is_told_the_administrator_gives_the_link(self, real_app):
        _, test_app = real_app
        make_organisation(GlobalRole.ADMIN)

        body = assert_waiting_for_admin(ask_to_join(test_app.test_client()))

        assert body['approval_email'] is False
        assert body['message'] == (
            'Your request has been submitted. An administrator of your organization '
            'will approve it and give you a link to set up your sign-in.')
        assert 'email' not in body['message'].lower()

    @pytest.mark.parametrize('email_configured', [True, False])
    def test_tenant_status_says_whether_approval_can_be_emailed(self, real_app, email_configured):
        _, test_app = real_app
        make_organisation(GlobalRole.ADMIN)
        if email_configured:
            configure_email()

        status = test_app.test_client().get(f'/api/auth/tenant/{DOMAIN}')

        assert status.status_code == 200, status.get_json()
        assert status.get_json()['email_available'] is email_configured

    def test_tenant_status_counts_the_organisation_s_own_email_settings_only(self, real_app):
        _, test_app = real_app
        make_organisation(GlobalRole.ADMIN)
        make_organisation(GlobalRole.ADMIN, domain='globex.test')
        db.session.add(EmailConfig(
            domain='globex.test', smtp_server='smtp.globex.test', smtp_port=587, smtp_username='mailer',
            smtp_password='secret', from_email='noreply@globex.test', enabled=True))
        db.session.commit()

        client = test_app.test_client()

        assert client.get('/api/auth/tenant/globex.test').get_json()['email_available'] is True
        assert client.get(f'/api/auth/tenant/{DOMAIN}').get_json()['email_available'] is False
