"""
Real-app regression tests for sign-in sessions, OAuth redirects and passkey gating.

These drive the actual Flask app (not a bare test app) so the before_request
session-expiry and CSRF hooks run exactly as they do in production.

The social sign-in routes import their provider helpers from the Enterprise
`ee` package at request time. So that the shared callback logic in app.py
(redirects, session creation, cookie attributes) is exercised in Community
Edition as well, the provider module is replaced with a small stand-in for the
duration of a test. Tests that need the real provider module live in
tests/test_google_oauth.py behind the Enterprise skip marker.
"""
import ast
import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    db, User, Tenant, TenantMembership, GlobalRole, MaturityState, SetupToken,
    WebAuthnCredential
)
from tests.app_test_utils import load_test_app

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STRONG_PASSWORD = 'Str0ngPassword'


# ==================== Fixtures and helpers ====================

@pytest.fixture
def real_app():
    """The real Flask app with all routes, on an in-memory database."""
    app_module, test_app = load_test_app(secret_key='test-secret-key-auth-session-oauth')

    with test_app.app_context():
        db.create_all()
        app_module.init_database()
        yield app_module, test_app
        db.session.remove()
        db.drop_all()
        app_module._db_initialized = False


def make_tenant(domain='acme.test'):
    tenant = Tenant(domain=domain, name=domain, status='active',
                    maturity_state=MaturityState.BOOTSTRAP)
    db.session.add(tenant)
    db.session.commit()
    return tenant


def make_user(email='pat@acme.test', *, auth_type='local', password=None, passkey=False,
              role=GlobalRole.USER):
    domain = email.split('@')[1]
    tenant = Tenant.query.filter_by(domain=domain).first() or make_tenant(domain)
    user = User(email=email, sso_domain=domain, auth_type=auth_type, email_verified=True)
    user.set_name(first_name='Pat', last_name='Example')
    if password:
        user.set_password(password)
    db.session.add(user)
    db.session.flush()
    db.session.add(TenantMembership(user_id=user.id, tenant_id=tenant.id, global_role=role))
    if passkey:
        db.session.add(WebAuthnCredential(
            user_id=user.id,
            credential_id=f'cred-{user.id}'.encode(),
            public_key=b'public-key',
            sign_count=0,
            device_name='Test key',
        ))
    db.session.commit()
    return user


# ==================== Sessions always carry an expiry ====================

class TestSessionsSurviveTheNextRequest:
    """A session without `_expires_at` is cleared by check_session_expiry()."""

    def test_setup_password_session_survives_next_request(self, real_app):
        _, test_app = real_app
        user = make_user('newhire@acme.test')
        token = SetupToken.create_for_user(user)._token_string
        client = test_app.test_client()

        response = client.post('/api/auth/setup-password',
                               json={'token': token, 'password': STRONG_PASSWORD})
        assert response.status_code == 200, response.get_json()

        with client.session_transaction() as sess:
            assert sess['user_id'] == user.id
            assert datetime.fromisoformat(sess['_expires_at']) > datetime.now(timezone.utc)

        me = client.get('/api/user/me')
        assert me.status_code == 200, me.get_json()
        assert me.get_json()['email'] == 'newhire@acme.test'

    def test_setup_password_rejects_bad_token_without_creating_session(self, real_app):
        _, test_app = real_app
        make_user('newhire@acme.test')
        client = test_app.test_client()

        response = client.post('/api/auth/setup-password',
                               json={'token': 'not-a-token', 'password': STRONG_PASSWORD})
        assert response.status_code == 401
        assert 'error' in response.get_json()
        assert client.get('/api/user/me').status_code == 401

    def test_password_login_session_survives_next_request(self, real_app):
        """Control: the path that always worked keeps working."""
        _, test_app = real_app
        make_user('pat@acme.test', password=STRONG_PASSWORD)
        client = test_app.test_client()

        response = client.post('/api/auth/login',
                               json={'email': 'pat@acme.test', 'password': STRONG_PASSWORD})
        assert response.status_code == 200, response.get_json()
        assert client.get('/api/user/me').status_code == 200

    def test_session_without_expiry_is_still_rejected(self, real_app):
        """The legacy-session guard stays: no expiry means no session."""
        _, test_app = real_app
        user = make_user('pat@acme.test', password=STRONG_PASSWORD)
        client = test_app.test_client()
        with client.session_transaction() as sess:
            sess['user_id'] = user.id

        assert client.get('/api/user/me').status_code == 401


class TestSessionCreationGoesThroughOneHelper:
    """Every sign-in path must call auth.start_user_session()."""

    SOURCES = ('app.py', 'auth.py', 'webauthn_auth.py', 'security.py')

    @staticmethod
    def _direct_user_id_assignments(path):
        with open(path, encoding='utf-8') as handle:
            tree = ast.parse(handle.read())

        hits = []
        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for node in ast.walk(func):
                if not isinstance(node, ast.Assign):
                    continue
                for target in node.targets:
                    if (isinstance(target, ast.Subscript)
                            and isinstance(target.value, ast.Name)
                            and target.value.id == 'session'
                            and isinstance(target.slice, ast.Constant)
                            and target.slice.value == 'user_id'):
                        hits.append((func.name, node.lineno))
        return hits

    def test_only_the_helper_assigns_session_user_id(self):
        offenders = []
        for name in self.SOURCES:
            for func_name, lineno in self._direct_user_id_assignments(os.path.join(REPO_ROOT, name)):
                if (name, func_name) != ('auth.py', 'start_user_session'):
                    offenders.append(f'{name}:{lineno} in {func_name}()')

        assert offenders == [], (
            "session['user_id'] must only be set by auth.start_user_session(), "
            f"which also sets the session expiry. Offenders: {offenders}"
        )
