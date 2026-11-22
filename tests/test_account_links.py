"""
Every link the server gives a person ends on a page the app has.

Recovery, setup and verification links are followed from an email or handed
over by an administrator. Each one must name a route of the Angular app, with
its token intact, and the token must do its job when the page uses it.

The routes are read from frontend/src/app/app.routes.ts, so a link to a page
that was renamed or never existed fails here.
"""
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    db, User, Tenant, TenantMembership, EmailConfig, EmailVerification, AccessRequest,
    GlobalRole, MaturityState, SetupToken, SystemConfig, WebAuthnCredential
)
from tests.app_test_utils import load_test_app

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROUTES_FILE = os.path.join(ROOT, 'frontend', 'src', 'app', 'app.routes.ts')
DOMAIN = 'acme.test'
PASSWORD = 'Str0ngPassword'
NEW_PASSWORD = 'An0therPassword'
SEND_RECOVERY = 'notifications.send_account_recovery_email'
SEND_SETUP = 'notifications.send_account_setup_email'
SEND_SETUP_TOKEN = 'notifications.send_setup_token_email'


@pytest.fixture
def real_app():
    app_module, test_app = load_test_app(secret_key='test-secret-key-account-links')

    with test_app.app_context():
        db.create_all()
        app_module.init_database()
        yield app_module, test_app
        db.session.remove()
        db.drop_all()
        app_module._db_initialized = False


# ==================== The app's routes ====================

def angular_routes():
    with open(ROUTES_FILE, encoding='utf-8') as handle:
        return re.findall(r"^\s*path:\s*'([^']*)'", handle.read(), flags=re.MULTILINE)


def matched_route(path):
    """The route pattern the Angular router picks for `path` (first match wins), or None."""
    segments = [segment for segment in path.strip('/').split('/') if segment]
    for pattern in angular_routes():
        if pattern == '**':
            continue
        parts = [part for part in pattern.split('/') if part]
        if len(parts) != len(segments):
            continue
        if all(part.startswith(':') or part == segment for part, segment in zip(parts, segments)):
            return pattern
    return None


def assert_page(url, pattern, domain=DOMAIN):
    """`url` is a page of the app, matched by route `pattern`, for `domain`."""
    parsed = urlparse(url)
    assert matched_route(parsed.path) == pattern, f'{parsed.path} is not served by {pattern}'
    assert parsed.path.strip('/').split('/')[0] == domain
    return parse_qs(parsed.query)


def token_of(url):
    query = assert_page(url, ':tenant/setup')
    assert list(query) == ['token']
    return query['token'][0]


class TestRouteMatcher:

    def test_setup_and_login_pages_exist(self):
        assert matched_route('/acme.test/setup') == ':tenant/setup'
        assert matched_route('/acme.test/login') == ':tenant/login'

    def test_a_page_that_does_not_exist_matches_nothing(self):
        assert matched_route('/acme.test/recover') is None

    def test_a_single_segment_is_the_organisation_page(self):
        assert matched_route('/acme.test') == ':tenant'


# ==================== Data ====================

def make_user(email, *, password=PASSWORD, passkeys=0, role=GlobalRole.USER, is_admin=False):
    domain = email.split('@')[1]
    tenant = Tenant.query.filter_by(domain=domain).first()
    if not tenant:
        tenant = Tenant(domain=domain, name=domain, status='active',
                        maturity_state=MaturityState.BOOTSTRAP)
        db.session.add(tenant)
        db.session.flush()
    user = User(email=email, sso_domain=domain, auth_type='local', email_verified=True, is_admin=is_admin)
    user.set_name(first_name='Pat', last_name='Example')
    if password:
        user.set_password(password)
    db.session.add(user)
    db.session.flush()
    db.session.add(TenantMembership(user_id=user.id, tenant_id=tenant.id, global_role=role))
    for index in range(passkeys):
        db.session.add(WebAuthnCredential(
            user_id=user.id, credential_id=f'existing-{user.id}-{index}'.encode(),
            public_key=b'public-key', sign_count=0))
    db.session.commit()
    return user


def configure_email():
    db.session.add(EmailConfig(
        domain='system', smtp_server='smtp.example.test', smtp_port=587,
        smtp_username='mailer', smtp_password='secret', from_email='noreply@example.test',
        enabled=True))
    db.session.commit()


def sign_in(test_app, email, password=PASSWORD):
    client = test_app.test_client()
    response = client.post('/api/auth/login', json={'email': email, 'password': password})
    assert response.status_code == 200, response.get_json()
    client.environ_base['HTTP_X_CSRF_TOKEN'] = response.headers['X-CSRF-Token']
    return client


def request_recovery(test_app, email):
    """Ask for a recovery link the way the sign-in page does. Returns the emailed link or None."""
    with patch(SEND_RECOVERY, return_value=True) as send:
        response = test_app.test_client().post('/api/auth/request-recovery', json={'email': email})
    assert response.status_code == 200, response.get_json()
    assert response.get_json() == {
        'message': 'If an account exists with this email, a recovery link has been sent.'}
    if not send.called:
        return None
    return send.call_args.kwargs['recovery_url']


# ==================== Account recovery ====================

class TestRecoveryLink:

    def test_emailed_link_opens_the_setup_page_with_the_token(self, real_app):
        _, test_app = real_app
        configure_email()
        make_user(f'pat@{DOMAIN}')

        link = request_recovery(test_app, f'pat@{DOMAIN}')

        assert link.startswith('http://localhost/')
        setup_token, error = SetupToken.validate_token(token_of(link))
        assert error is None
        assert setup_token.purpose == SetupToken.PURPOSE_ACCOUNT_RECOVERY

    def test_page_is_told_it_is_a_recovery_and_where_the_flow_lives(self, real_app):
        _, test_app = real_app
        configure_email()
        make_user(f'pat@{DOMAIN}', passkeys=1)
        token = token_of(request_recovery(test_app, f'pat@{DOMAIN}'))

        response = test_app.test_client().post('/api/auth/setup-token/validate', json={'token': token})

        assert response.status_code == 200, response.get_json()
        body = response.get_json()
        assert body['valid'] is True
        assert body['is_recovery'] is True
        assert body['user']['email'] == f'pat@{DOMAIN}'
        # The address the server names for the flow is a page of the app, with the same token
        assert token_of(body['redirect']) == token

    def test_new_password_replaces_the_old_one_and_signs_the_person_in(self, real_app):
        _, test_app = real_app
        configure_email()
        make_user(f'pat@{DOMAIN}')
        token = token_of(request_recovery(test_app, f'pat@{DOMAIN}'))
        client = test_app.test_client()
        assert client.post('/api/auth/setup-token/validate', json={'token': token}).status_code == 200

        response = client.post('/api/auth/setup-password', json={'token': token, 'password': NEW_PASSWORD})

        assert response.status_code == 200, response.get_json()
        me = client.get('/api/user/me').get_json()
        assert me['email'] == f'pat@{DOMAIN}'
        old = test_app.test_client().post('/api/auth/login', json={'email': f'pat@{DOMAIN}', 'password': PASSWORD})
        assert old.status_code == 401
        sign_in(test_app, f'pat@{DOMAIN}', NEW_PASSWORD)

    def test_after_recovery_the_person_is_not_left_in_setup_mode(self, real_app):
        """A finished recovery is an ordinary session: the app must not send the person back to set up credentials."""
        _, test_app = real_app
        configure_email()
        make_user(f'pat@{DOMAIN}')
        token = token_of(request_recovery(test_app, f'pat@{DOMAIN}'))
        client = test_app.test_client()
        client.post('/api/auth/setup-token/validate', json={'token': token})
        client.post('/api/auth/setup-password', json={'token': token, 'password': NEW_PASSWORD})

        me = client.get('/api/user/me').get_json()

        assert 'setup_mode' not in me
        with client.session_transaction() as sess:
            assert 'setup_token' not in sess
            assert 'setup_user_id' not in sess
        # The same browser signing in again is not in setup mode either
        client.post('/api/auth/login', json={'email': f'pat@{DOMAIN}', 'password': NEW_PASSWORD})
        assert 'setup_mode' not in client.get('/api/user/me').get_json()

    def test_link_works_once(self, real_app):
        _, test_app = real_app
        configure_email()
        make_user(f'pat@{DOMAIN}')
        token = token_of(request_recovery(test_app, f'pat@{DOMAIN}'))
        test_app.test_client().post('/api/auth/setup-password', json={'token': token, 'password': NEW_PASSWORD})

        again = test_app.test_client().post('/api/auth/setup-token/validate', json={'token': token})

        assert again.status_code == 400
        assert again.get_json()['used'] is True

    def test_unknown_address_gets_the_same_answer_and_no_link(self, real_app):
        _, test_app = real_app
        configure_email()

        assert request_recovery(test_app, f'nobody@{DOMAIN}') is None
        assert SetupToken.query.count() == 0

    def test_recovery_link_of_one_account_cannot_change_another(self, real_app):
        _, test_app = real_app
        configure_email()
        make_user(f'pat@{DOMAIN}')
        other = make_user('sam@globex.test')
        token = token_of(request_recovery(test_app, f'pat@{DOMAIN}'))

        test_app.test_client().post('/api/auth/setup-password', json={'token': token, 'password': NEW_PASSWORD})

        assert db.session.get(User, other.id).check_password(PASSWORD)
        sign_in(test_app, 'sam@globex.test')


# ==================== Setup links ====================

class TestSetupLinks:

    def test_page_is_given_a_setup_address_with_the_token(self, real_app):
        _, test_app = real_app
        user = make_user(f'new@{DOMAIN}', password=None)
        token = SetupToken.create_for_user(user)._token_string

        response = test_app.test_client().post('/api/auth/setup-token/validate', json={'token': token})

        body = response.get_json()
        assert response.status_code == 200, body
        assert body['is_recovery'] is False
        assert token_of(body['redirect']) == token

    def test_already_set_up_account_is_sent_to_the_sign_in_page(self, real_app):
        _, test_app = real_app
        user = make_user(f'pat@{DOMAIN}')
        token = SetupToken.create_for_user(user)._token_string

        response = test_app.test_client().post('/api/auth/setup-token/validate', json={'token': token})

        assert response.status_code == 400
        assert response.get_json()['already_setup'] is True
        assert_page(response.get_json()['redirect'], ':tenant/login')

    def test_link_an_administrator_generates_opens_the_setup_page(self, real_app):
        _, test_app = real_app
        make_user(f'owner@{DOMAIN}', role=GlobalRole.ADMIN, is_admin=True)
        newcomer = make_user(f'new@{DOMAIN}', password=None)

        response = sign_in(test_app, f'owner@{DOMAIN}').post(f'/api/admin/users/{newcomer.id}/setup-link')

        assert response.status_code == 200, response.get_json()
        token = token_of(response.get_json()['setup_url'])
        assert SetupToken.validate_token(token)[0].user_id == newcomer.id

    def test_link_an_administrator_emails_opens_the_setup_page(self, real_app):
        _, test_app = real_app
        configure_email()
        make_user(f'owner@{DOMAIN}', role=GlobalRole.ADMIN, is_admin=True)
        newcomer = make_user(f'new@{DOMAIN}', password=None)

        with patch(SEND_SETUP_TOKEN, return_value=True) as send:
            response = sign_in(test_app, f'owner@{DOMAIN}').post(
                f'/api/admin/users/{newcomer.id}/send-setup-email')

        assert response.status_code == 200, response.get_json()
        token = token_of(send.call_args.kwargs['setup_url'])
        assert SetupToken.validate_token(token)[0].user_id == newcomer.id

    def test_setting_a_password_from_a_setup_link_signs_the_person_in(self, real_app):
        _, test_app = real_app
        user = make_user(f'new@{DOMAIN}', password=None)
        token = SetupToken.create_for_user(user)._token_string
        client = test_app.test_client()
        client.post('/api/auth/setup-token/validate', json={'token': token})

        response = client.post('/api/auth/setup-password', json={'token': token, 'password': NEW_PASSWORD})

        assert response.status_code == 200, response.get_json()
        me = client.get('/api/user/me').get_json()
        assert me['email'] == f'new@{DOMAIN}'
        assert 'setup_mode' not in me


# ==================== Verification links ====================

def verification(email, purpose, token='verify-token'):
    db.session.add(EmailVerification(
        email=email, name='New Comer', token=token, purpose=purpose, domain=email.split('@')[1],
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2)))
    db.session.commit()
    return token


class TestVerificationLinks:

    def test_emailed_verification_link_is_the_endpoint_that_verifies(self, real_app):
        app_module, test_app = real_app
        configure_email()
        sent = {}

        def capture(email_config, to_email, subject, html_content, text_content=None):
            sent['text'] = text_content or html_content
            return True

        with test_app.test_request_context('/', base_url='https://app.example.test'), \
                patch('notifications.send_email', capture), patch.object(app_module, 'send_email', capture, create=True):
            assert app_module.send_verification_email(f'new@{DOMAIN}', 'verify-token', 'signup', DOMAIN)

        link = re.search(r'https://app\.example\.test/\S*verify-token', sent['text']).group(0)
        assert urlparse(link).path == '/api/auth/verify-email/verify-token'

    def test_sign_up_link_lands_on_the_setup_page_with_a_working_token(self, real_app):
        _, test_app = real_app
        token = verification(f'founder@{DOMAIN}', 'signup')

        response = test_app.test_client().get(f'/api/auth/verify-email/{token}')

        assert response.status_code == 302
        setup = token_of(response.headers['Location'])
        setup_token, error = SetupToken.validate_token(setup)
        assert error is None
        assert setup_token.user.email == f'founder@{DOMAIN}'

    def test_access_request_link_lands_on_the_sign_in_page(self, real_app):
        _, test_app = real_app
        make_user(f'owner@{DOMAIN}', role=GlobalRole.ADMIN, is_admin=True)
        token = verification(f'new@{DOMAIN}', 'access_request')

        response = test_app.test_client().get(f'/api/auth/verify-email/{token}')

        assert response.status_code == 302
        query = assert_page(response.headers['Location'], ':tenant/login')
        assert query == {'access_requested': ['1']}
        assert AccessRequest.query.filter_by(email=f'new@{DOMAIN}', status='pending').count() == 1

    def test_link_opened_twice_lands_on_the_sign_in_page(self, real_app):
        _, test_app = real_app
        token = verification(f'founder@{DOMAIN}', 'signup')
        test_app.test_client().get(f'/api/auth/verify-email/{token}')

        response = test_app.test_client().get(f'/api/auth/verify-email/{token}')

        assert response.status_code == 302
        assert assert_page(response.headers['Location'], ':tenant/login') == {}

    @pytest.mark.parametrize('expired, error', [(False, 'invalid_token'), (True, 'expired_token')])
    def test_bad_link_lands_on_the_landing_page_with_the_reason(self, real_app, expired, error):
        _, test_app = real_app
        token = 'no-such-token'
        if expired:
            token = verification(f'founder@{DOMAIN}', 'signup')
            EmailVerification.query.filter_by(token=token).update(
                {'expires_at': datetime.now(timezone.utc) - timedelta(hours=1)})
            db.session.commit()

        response = test_app.test_client().get(f'/api/auth/verify-email/{token}')

        assert response.status_code == 302
        parsed = urlparse(response.headers['Location'])
        assert parsed.path == '/'
        assert parse_qs(parsed.query) == {'error': [error]}


# ==================== Test-only helper used by the browser tests ====================

class TestIncompleteUserHelper:

    def test_setup_token_it_returns_is_a_real_one(self, real_app):
        _, test_app = real_app

        response = test_app.test_client().post('/api/test/create-incomplete-user', json={
            'email': 'new@helper.test', 'first_name': 'New', 'last_name': 'Comer'})

        body = response.get_json()
        assert response.status_code == 200, body
        query = assert_page(body['setup_url'], ':tenant/setup', domain='helper.test')
        assert query == {'token': [body['setup_token']]}
        validate = test_app.test_client().post('/api/auth/setup-token/validate', json={'token': body['setup_token']})
        assert validate.status_code == 200, validate.get_json()
        assert validate.get_json()['is_recovery'] is False

    def test_recovery_token_for_an_existing_account(self, real_app):
        _, test_app = real_app
        make_user(f'pat@{DOMAIN}')

        response = test_app.test_client().post('/api/test/create-setup-token', json={
            'email': f'pat@{DOMAIN}', 'purpose': 'account_recovery'})

        body = response.get_json()
        assert response.status_code == 200, body
        token = token_of(body['setup_url'])
        validate = test_app.test_client().post('/api/auth/setup-token/validate', json={'token': token})
        assert validate.get_json()['is_recovery'] is True

    def test_helpers_are_refused_outside_testing(self, real_app, monkeypatch):
        _, test_app = real_app
        make_user(f'pat@{DOMAIN}')
        monkeypatch.setenv('FLASK_ENV', 'production')

        response = test_app.test_client().post('/api/test/create-setup-token', json={
            'email': f'pat@{DOMAIN}', 'purpose': 'account_recovery'})

        assert response.status_code == 403
        assert SetupToken.query.count() == 0
