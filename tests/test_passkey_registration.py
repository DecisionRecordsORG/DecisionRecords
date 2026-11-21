"""
Passkey registration requires proof of account control.

A passkey may be added to an existing account only by someone who has already
proven control of it: a signed-in session for that same user, or a valid
setup/recovery token for that user. Without either, registration can at most
create a first account for an organisation that has none, and only when the
instance does not require email verification.

These tests drive the real routes. The WebAuthn attestation check itself is
replaced with a stub that accepts, which is what any caller's own authenticator
produces for its own key: the tests are about whose account the key lands on.
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    db, User, Tenant, TenantMembership, AuthConfig, GlobalRole, MaturityState,
    SetupToken, SystemConfig, WebAuthnCredential, ArchitectureDecision
)
from tests.app_test_utils import load_test_app

PASSWORD = 'Str0ngPassword'
OPTIONS = '/api/webauthn/register/options'
VERIFY = '/api/webauthn/register/verify'


@pytest.fixture
def real_app():
    app_module, test_app = load_test_app(secret_key='test-secret-key-passkey-registration')

    with test_app.app_context():
        db.create_all()
        app_module.init_database()
        require_email_verification(False)
        yield app_module, test_app
        db.session.remove()
        db.drop_all()
        app_module._db_initialized = False


def require_email_verification(required):
    SystemConfig.set(SystemConfig.KEY_EMAIL_VERIFICATION_REQUIRED, 'true' if required else 'false')


def make_user(email, *, auth_type='local', password=PASSWORD, passkeys=0):
    domain = email.split('@')[1].lower()
    tenant = Tenant.query.filter_by(domain=domain).first()
    if not tenant:
        tenant = Tenant(domain=domain, name=domain, status='active',
                        maturity_state=MaturityState.BOOTSTRAP)
        db.session.add(tenant)
        db.session.flush()
    user = User(email=email, sso_domain=domain, auth_type=auth_type, email_verified=True)
    user.set_name(first_name='Pat', last_name='Example')
    if password:
        user.set_password(password)
    db.session.add(user)
    db.session.flush()
    db.session.add(TenantMembership(user_id=user.id, tenant_id=tenant.id, global_role=GlobalRole.USER))
    for index in range(passkeys):
        db.session.add(WebAuthnCredential(
            user_id=user.id, credential_id=f'existing-{user.id}-{index}'.encode(),
            public_key=b'public-key', sign_count=0))
    db.session.commit()
    return user


def passkey_count(user_id):
    return WebAuthnCredential.query.filter_by(user_id=user_id).count()


def accepted_attestation(label='new'):
    return patch('webauthn_auth.verify_registration_response', return_value=SimpleNamespace(
        credential_id=f'credential-{label}'.encode(),
        credential_public_key=b'public-key',
        sign_count=0,
    ))


def finish(client, label='new'):
    with accepted_attestation(label):
        return client.post(VERIFY, json={'credential': {'id': label}, 'device_name': 'Test device'})


def sign_in(test_app, email, password=PASSWORD):
    client = test_app.test_client()
    response = client.post('/api/auth/login', json={'email': email, 'password': password})
    assert response.status_code == 200, response.get_json()
    client.environ_base['HTTP_X_CSRF_TOKEN'] = response.headers['X-CSRF-Token']
    return client


def signed_in_email(client):
    response = client.get('/api/user/me')
    return response.get_json().get('email') if response.status_code == 200 else None


def start_setup_session(client, user, purpose=None):
    token = SetupToken.create_for_user(user, purpose=purpose)._token_string
    response = client.post('/api/auth/setup-token/validate', json={'token': token})
    assert response.status_code == 200, response.get_json()
    return token


# ==================== Refused: no proof of control ====================

class TestRegistrationWithoutProofIsRefused:

    @pytest.mark.parametrize('auth_type', ['local', 'webauthn'])
    def test_existing_account_cannot_be_given_a_passkey_anonymously(self, real_app, auth_type):
        _, test_app = real_app
        user_id = make_user('pat@acme.test', auth_type=auth_type, passkeys=1).id
        client = test_app.test_client()

        options = client.post(OPTIONS, json={'email': 'pat@acme.test', 'name': 'Someone'})
        verify = finish(client)

        assert options.status_code == 400
        assert 'challenge' not in (options.get_json() or {})
        assert verify.status_code == 400
        assert passkey_count(user_id) == 1
        assert signed_in_email(client) is None

    @pytest.mark.parametrize('email', ['PAT@acme.test', 'Pat@Acme.Test', '  pat@acme.test  '])
    def test_email_case_and_whitespace_do_not_get_around_the_check(self, real_app, email):
        _, test_app = real_app
        user_id = make_user('pat@acme.test', passkeys=1).id
        client = test_app.test_client()

        options = client.post(OPTIONS, json={'email': email, 'name': 'Someone'})
        verify = finish(client)

        assert options.status_code == 400
        assert verify.status_code == 400
        assert User.query.count() == 1
        assert passkey_count(user_id) == 1
        assert signed_in_email(client) is None

    def test_account_stored_with_mixed_case_email_is_protected_too(self, real_app):
        _, test_app = real_app
        user_id = make_user('Pat@acme.test', passkeys=1).id
        client = test_app.test_client()

        options = client.post(OPTIONS, json={'email': 'pat@acme.test', 'name': 'Someone'})

        assert options.status_code == 400
        assert finish(client).status_code == 400
        assert User.query.count() == 1
        assert passkey_count(user_id) == 1

    def test_refusal_does_not_reveal_account_details(self, real_app):
        """No user id or credential ids of the existing account in the refusal."""
        _, test_app = real_app
        make_user('pat@acme.test', passkeys=1)

        response = test_app.test_client().post(OPTIONS, json={'email': 'pat@acme.test'})

        assert set(response.get_json()) == {'error'}

    def test_signed_in_user_cannot_register_a_passkey_for_someone_else(self, real_app):
        _, test_app = real_app
        make_user('mallory@acme.test', auth_type='webauthn', passkeys=1)
        victim_id = make_user('pat@acme.test', auth_type='webauthn', passkeys=1).id
        client = sign_in(test_app, 'mallory@acme.test')

        options = client.post(OPTIONS, json={'email': 'pat@acme.test', 'name': 'Someone'})
        verify = finish(client)

        assert options.status_code == 403
        assert verify.status_code == 400
        assert passkey_count(victim_id) == 1
        assert signed_in_email(client) == 'mallory@acme.test'

    def test_setup_token_holder_cannot_register_a_passkey_for_someone_else(self, real_app):
        """A setup session names its own user; an email in the request is ignored."""
        _, test_app = real_app
        victim_id = make_user('pat@acme.test', passkeys=1).id
        invited = make_user('invited@acme.test', password=None)
        client = test_app.test_client()
        start_setup_session(client, invited)

        options = client.post(OPTIONS, json={'email': 'pat@acme.test'})
        verify = finish(client)

        assert options.status_code == 200
        assert options.get_json()['user']['name'] == 'invited@acme.test'
        assert verify.status_code == 200
        assert passkey_count(victim_id) == 1
        assert passkey_count(invited.id) == 1
        assert signed_in_email(client) == 'invited@acme.test'

    def test_new_address_in_an_existing_organisation_is_refused(self, real_app):
        """Joining an organisation goes through its access-request and invite flows."""
        _, test_app = real_app
        owner = make_user('owner@acme.test')
        tenant = Tenant.query.filter_by(domain='acme.test').first()
        db.session.add(ArchitectureDecision(
            title='Internal decision', context='c', decision='d', status='proposed',
            consequences='x', domain='acme.test', tenant_id=tenant.id,
            created_by_id=owner.id, decision_number=1))
        db.session.commit()
        client = test_app.test_client()

        options = client.post(OPTIONS, json={'email': 'newcomer@acme.test', 'name': 'New'})
        verify = finish(client)

        assert options.status_code == 400
        assert verify.status_code == 400
        assert User.query.filter_by(email='newcomer@acme.test').first() is None
        assert client.get('/api/decisions').status_code == 401

    def test_organisation_with_a_tenant_but_no_users_is_refused(self, real_app):
        _, test_app = real_app
        db.session.add(Tenant(domain='acme.test', name='Acme', status='active',
                              maturity_state=MaturityState.BOOTSTRAP))
        db.session.commit()

        response = test_app.test_client().post(OPTIONS, json={'email': 'first@acme.test'})

        assert response.status_code == 400

    def test_refused_when_email_verification_is_required(self, real_app):
        """Sign-up must go through the verification email, which issues a setup token."""
        _, test_app = real_app
        require_email_verification(True)
        client = test_app.test_client()

        options = client.post(OPTIONS, json={'email': 'founder@newco.test', 'name': 'Founder'})
        verify = finish(client)

        assert options.status_code == 403
        assert verify.status_code == 400
        assert User.query.filter_by(email='founder@newco.test').first() is None
        assert signed_in_email(client) is None

    @pytest.mark.parametrize('email,status', [
        ('someone@gmail.com', 400),          # public mailbox provider
        ('not-an-email', 400),
        ('', 400),
        (None, 400),
        (42, 400),
    ])
    def test_unusable_addresses_are_refused(self, real_app, email, status):
        _, test_app = real_app

        response = test_app.test_client().post(OPTIONS, json={'email': email})

        assert response.status_code == status
        assert 'error' in response.get_json()

    def test_registration_disabled_for_domain_is_refused(self, real_app):
        _, test_app = real_app
        db.session.add(AuthConfig(domain='newco.test', allow_registration=False))
        db.session.commit()

        response = test_app.test_client().post(OPTIONS, json={'email': 'founder@newco.test'})

        assert response.status_code == 400


# ==================== The verify step checks for itself ====================

class TestVerifyStepIsCheckedIndependently:
    """A challenge issued for one identity is not redeemable for another."""

    def test_challenge_for_a_new_address_cannot_land_on_an_account_created_since(self, real_app):
        _, test_app = real_app
        client = test_app.test_client()
        assert client.post(OPTIONS, json={'email': 'pat@newco.test'}).status_code == 200
        user_id = make_user('pat@newco.test').id   # the real owner signs up in the meantime

        verify = finish(client)

        assert verify.status_code == 400
        assert passkey_count(user_id) == 0
        assert signed_in_email(client) is None

    def test_challenge_for_a_new_address_fails_if_verification_became_required(self, real_app):
        _, test_app = real_app
        client = test_app.test_client()
        assert client.post(OPTIONS, json={'email': 'founder@newco.test'}).status_code == 200
        require_email_verification(True)

        assert finish(client).status_code == 400
        assert User.query.filter_by(email='founder@newco.test').first() is None

    def test_registration_state_naming_an_existing_account_without_proof_is_refused(self, real_app):
        """Session state from an older release carried only an email address."""
        _, test_app = real_app
        user_id = make_user('pat@acme.test', passkeys=1).id
        client = test_app.test_client()
        with client.session_transaction() as sess:
            sess['webauthn_register_challenge'] = 'Y2hhbGxlbmdl'
            sess['webauthn_register_email'] = 'pat@acme.test'
            sess['webauthn_register_name'] = 'Someone'
            sess['webauthn_register_domain'] = 'acme.test'

        verify = finish(client)

        assert verify.status_code == 400
        assert passkey_count(user_id) == 1
        assert signed_in_email(client) is None

    def test_registration_state_claiming_an_account_needs_live_proof(self, real_app):
        """Even state that names the account id is useless without a session or token for it."""
        _, test_app = real_app
        user_id = make_user('pat@acme.test', passkeys=1).id
        client = test_app.test_client()
        with client.session_transaction() as sess:
            sess['webauthn_register_challenge'] = 'Y2hhbGxlbmdl'
            sess['webauthn_register_email'] = 'pat@acme.test'
            sess['webauthn_register_name'] = 'Someone'
            sess['webauthn_register_domain'] = 'acme.test'
            sess['webauthn_register_user_id'] = user_id

        verify = finish(client)

        assert verify.status_code == 400
        assert passkey_count(user_id) == 1
        assert signed_in_email(client) is None

    def test_challenge_issued_to_a_signed_in_user_dies_with_the_session(self, real_app):
        _, test_app = real_app
        user_id = make_user('pat@acme.test', auth_type='webauthn', passkeys=1).id
        client = sign_in(test_app, 'pat@acme.test')
        assert client.post(OPTIONS, json={'email': 'pat@acme.test'}).status_code == 200
        with client.session_transaction() as sess:
            sess.pop('user_id')
            sess.pop('_expires_at')

        verify = finish(client)

        assert verify.status_code == 400
        assert passkey_count(user_id) == 1
        assert signed_in_email(client) is None

    def test_challenge_issued_to_one_user_is_not_redeemable_by_another_session(self, real_app):
        _, test_app = real_app
        victim_id = make_user('pat@acme.test', auth_type='webauthn', passkeys=1).id
        mallory = make_user('mallory@acme.test', auth_type='webauthn', passkeys=1)
        client = sign_in(test_app, 'pat@acme.test')
        assert client.post(OPTIONS, json={'email': 'pat@acme.test'}).status_code == 200
        with client.session_transaction() as sess:
            sess['user_id'] = mallory.id

        verify = finish(client)

        assert verify.status_code == 400
        assert passkey_count(victim_id) == 1
        assert passkey_count(mallory.id) == 1

    def test_challenge_issued_under_a_setup_token_dies_when_the_token_session_expires(self, real_app):
        _, test_app = real_app
        invited = make_user('invited@acme.test', password=None)
        client = test_app.test_client()
        start_setup_session(client, invited)
        assert client.post(OPTIONS, json={}).status_code == 200
        with client.session_transaction() as sess:
            sess['setup_expires'] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()

        verify = finish(client)

        assert verify.status_code == 400
        assert passkey_count(invited.id) == 0
        assert signed_in_email(client) is None

    def test_challenge_is_single_use(self, real_app):
        _, test_app = real_app
        user_id = make_user('pat@acme.test', auth_type='webauthn', passkeys=1).id
        client = sign_in(test_app, 'pat@acme.test')
        assert client.post(OPTIONS, json={'email': 'pat@acme.test'}).status_code == 200

        assert finish(client, 'first').status_code == 200
        assert finish(client, 'second').status_code == 400
        assert passkey_count(user_id) == 2

    def test_verify_without_options_is_refused(self, real_app):
        _, test_app = real_app

        response = finish(test_app.test_client())

        assert response.status_code == 400
        assert response.get_json()['error'] == 'Registration session expired'

    def test_verify_requires_a_credential(self, real_app):
        _, test_app = real_app

        response = test_app.test_client().post(VERIFY, json={})

        assert response.status_code == 400
        assert response.get_json()['error'] == 'Credential is required'


# ==================== Allowed: control already proven ====================

class TestRegistrationWithProofStillWorks:

    @pytest.mark.parametrize('sent_email', ['pat@acme.test', 'PAT@ACME.TEST'])
    def test_signed_in_user_adds_a_passkey_from_their_profile(self, real_app, sent_email):
        """The profile page posts the signed-in user's own email to the options route."""
        _, test_app = real_app
        user_id = make_user('pat@acme.test', auth_type='webauthn', passkeys=1).id
        client = sign_in(test_app, 'pat@acme.test')

        options = client.post(OPTIONS, json={'email': sent_email, 'first_name': 'Pat'})
        verify = finish(client)

        assert options.status_code == 200, options.get_json()
        assert len(options.get_json()['excludeCredentials']) == 1
        assert verify.status_code == 200, verify.get_json()
        assert verify.get_json()['user']['email'] == 'pat@acme.test'
        assert passkey_count(user_id) == 2
        assert signed_in_email(client) == 'pat@acme.test'

    def test_signed_in_user_adds_a_passkey_through_the_credentials_route(self, real_app):
        _, test_app = real_app
        user_id = make_user('pat@acme.test', auth_type='webauthn', passkeys=1).id
        client = sign_in(test_app, 'pat@acme.test')

        options = client.post('/api/user/credentials', json={})
        verify = finish(client)

        assert options.status_code == 200, options.get_json()
        assert verify.status_code == 200, verify.get_json()
        assert passkey_count(user_id) == 2
        assert signed_in_email(client) == 'pat@acme.test'

    def test_setup_link_holder_creates_their_first_passkey(self, real_app):
        """Account setup page: token validated, options requested with no email."""
        _, test_app = real_app
        invited = make_user('invited@acme.test', auth_type='webauthn', password=None)
        client = test_app.test_client()
        token = start_setup_session(client, invited)

        options = client.post(OPTIONS, json={'device_name': 'Setup Device'})
        verify = finish(client)
        used = client.post('/api/auth/setup-token/use', json={'token': token},
                           headers={'X-CSRF-Token': verify.headers.get('X-CSRF-Token', '')})

        assert options.status_code == 200, options.get_json()
        assert verify.status_code == 200, verify.get_json()
        assert used.status_code == 200
        assert passkey_count(invited.id) == 1
        assert signed_in_email(client) == 'invited@acme.test'
        with client.session_transaction() as sess:
            assert 'setup_token' not in sess
            assert '_expires_at' in sess

    def test_setup_link_holder_in_profile_setup_mode_sends_their_own_email(self, real_app):
        _, test_app = real_app
        invited = make_user('invited@acme.test', auth_type='webauthn', password=None)
        client = test_app.test_client()
        start_setup_session(client, invited)

        options = client.post(OPTIONS, json={'email': 'invited@acme.test', 'first_name': 'Pat'})
        verify = finish(client)

        assert options.status_code == 200
        assert verify.status_code == 200
        assert passkey_count(invited.id) == 1

    def test_recovery_link_holder_adds_a_passkey_to_an_account_with_credentials(self, real_app):
        _, test_app = real_app
        user = make_user('pat@acme.test', auth_type='webauthn', passkeys=1)
        client = test_app.test_client()
        start_setup_session(client, user, purpose=SetupToken.PURPOSE_ACCOUNT_RECOVERY)

        options = client.post(OPTIONS, json={})
        verify = finish(client)

        assert options.status_code == 200, options.get_json()
        assert verify.status_code == 200, verify.get_json()
        assert passkey_count(user.id) == 2
        assert signed_in_email(client) == 'pat@acme.test'

    def test_initial_setup_link_is_no_proof_once_the_account_has_credentials(self, real_app):
        """Existing rule, unchanged: only recovery links work on a set-up account."""
        _, test_app = real_app
        user = make_user('pat@acme.test', passkeys=1)
        token = SetupToken.create_for_user(user)._token_string
        client = test_app.test_client()

        validate = client.post('/api/auth/setup-token/validate', json={'token': token})
        options = client.post(OPTIONS, json={})

        assert validate.status_code == 400
        assert options.status_code == 400
        assert passkey_count(user.id) == 1

    def test_first_account_for_a_new_organisation_without_email_verification(self, real_app):
        """Self-hosted instances that switched email verification off."""
        _, test_app = real_app
        client = test_app.test_client()

        options = client.post(OPTIONS, json={'email': 'Founder@NewCo.test', 'name': 'Founder'})
        verify = finish(client)

        assert options.status_code == 200, options.get_json()
        assert verify.status_code == 200, verify.get_json()
        user = User.query.filter_by(email='founder@newco.test').first()
        assert user is not None
        assert user.sso_domain == 'newco.test'
        assert passkey_count(user.id) == 1
        assert signed_in_email(client) == 'founder@newco.test'
        # ...and the address is now taken for anyone else
        assert test_app.test_client().post(OPTIONS, json={'email': 'founder@newco.test'}).status_code == 400

    def test_sso_enforced_domain_is_still_refused(self, real_app):
        from models import SSOConfig
        _, test_app = real_app
        db.session.add(SSOConfig(domain='sso-corp.test', provider_name='Okta', client_id='c',
                                 client_secret='s', discovery_url='https://idp.example.test/x'))
        db.session.add(AuthConfig(domain='sso-corp.test', auth_method='sso'))
        db.session.commit()

        response = test_app.test_client().post(OPTIONS, json={'email': 'new@sso-corp.test'})

        assert response.status_code == 400
        assert response.get_json()['error'] == 'This domain requires SSO authentication'
