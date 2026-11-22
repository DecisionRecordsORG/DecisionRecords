"""
The help link's address: SUPPORT_URL and the super admin setting.

The app shows "Can't sign in? Get help" to people who are stuck before they
are signed in. The hosted service links to its own support page. Whoever runs
another installation can point the link at their own page, or hide it, with
the SUPPORT_URL environment variable or a super admin setting; the setting
wins. The app reads the result as `support_url` from /api/features:

    absent          no choice was made: the app's default applies
    "none"          the link is hidden
    http(s) address the link leads there
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import feature_flags
from models import (
    db, User, Tenant, TenantMembership, SystemConfig, GlobalRole, MaturityState,
    DEFAULT_MASTER_PASSWORD, DEFAULT_MASTER_USERNAME
)
from tests.app_test_utils import load_test_app

SETTINGS = '/api/admin/settings/support'
PASSWORD = 'Str0ngPassword'


@pytest.fixture
def real_app(monkeypatch):
    monkeypatch.delenv('SUPPORT_URL', raising=False)
    app_module, test_app = load_test_app(secret_key='test-secret-key-support-url')

    with test_app.app_context():
        db.create_all()
        app_module.init_database()
        yield app_module, test_app
        db.session.remove()
        db.drop_all()
        app_module._db_initialized = False


def features(test_app):
    response = test_app.test_client().get('/api/features')
    assert response.status_code == 200
    return response.get_json()


def super_admin(test_app):
    client = test_app.test_client()
    response = client.post('/auth/local', json={
        'username': DEFAULT_MASTER_USERNAME, 'password': DEFAULT_MASTER_PASSWORD})
    assert response.status_code == 200, response.get_json()
    client.environ_base['HTTP_X_CSRF_TOKEN'] = response.headers.get('X-CSRF-Token', '')
    return client


def tenant_admin(test_app):
    tenant = Tenant(domain='acme.test', name='acme.test', status='active', maturity_state=MaturityState.BOOTSTRAP)
    db.session.add(tenant)
    db.session.flush()
    user = User(email='owner@acme.test', sso_domain='acme.test', auth_type='local', email_verified=True,
                is_admin=True)
    user.set_name(first_name='Org', last_name='Owner')
    user.set_password(PASSWORD)
    db.session.add(user)
    db.session.flush()
    db.session.add(TenantMembership(user_id=user.id, tenant_id=tenant.id, global_role=GlobalRole.ADMIN))
    db.session.commit()
    client = test_app.test_client()
    response = client.post('/api/auth/login', json={'email': 'owner@acme.test', 'password': PASSWORD})
    assert response.status_code == 200, response.get_json()
    client.environ_base['HTTP_X_CSRF_TOKEN'] = response.headers['X-CSRF-Token']
    return client


# ==================== Reading a value ====================

class TestNormaliseSupportUrl:

    @pytest.mark.parametrize('value', [None, '', '   ', '\n'])
    def test_nothing_means_no_choice(self, value):
        assert feature_flags.normalise_support_url(value) == ''

    @pytest.mark.parametrize('value, expected', [
        ('https://help.example.org/support', 'https://help.example.org/support'),
        ('http://intranet.example/help', 'http://intranet.example/help'),
        ('  https://help.example.org/support  ', 'https://help.example.org/support'),
        ('HTTPS://Help.Example.org/Support?x=1', 'HTTPS://Help.Example.org/Support?x=1'),
        ('https://help.example.org:8443/', 'https://help.example.org:8443/'),
    ])
    def test_http_and_https_addresses_are_kept(self, value, expected):
        assert feature_flags.normalise_support_url(value) == expected

    @pytest.mark.parametrize('value', ['none', 'NONE', ' None '])
    def test_the_word_none_hides_the_link(self, value):
        assert feature_flags.normalise_support_url(value) == 'none'

    @pytest.mark.parametrize('value', [
        'javascript:alert(1)',
        'data:text/html,<script>alert(1)</script>',
        'ftp://files.example.org/help',
        'mailto:help@example.org',
        '//help.example.org/support',
        'help.example.org/support',
        '/support',
        'https://',
        'https:///support',
        'https://help.example.org/a b',
        'https://help.example.org/\nSet-Cookie: x=1',
        'https://help.example.org/<script>',
        'https://help.example.org/"onmouseover="x',
        'https://user:secret@help.example.org/',
        'https://help.example.org/' + 'a' * 500,
        'off',
        'false',
    ])
    def test_anything_else_is_not_accepted(self, value):
        assert feature_flags.normalise_support_url(value) is None


# ==================== SUPPORT_URL in the environment ====================

class TestEnvironmentVariable:

    def test_without_it_the_features_answer_has_no_support_url(self, real_app):
        _, test_app = real_app

        assert 'support_url' not in features(test_app)

    @pytest.mark.parametrize('value', ['https://help.example.org/support', 'http://intranet.example/help'])
    def test_an_address_is_reported(self, real_app, monkeypatch, value):
        _, test_app = real_app
        monkeypatch.setenv('SUPPORT_URL', value)

        assert features(test_app)['support_url'] == value

    @pytest.mark.parametrize('value', ['none', 'NONE'])
    def test_none_hides_the_link(self, real_app, monkeypatch, value):
        _, test_app = real_app
        monkeypatch.setenv('SUPPORT_URL', value)

        assert features(test_app)['support_url'] == 'none'

    @pytest.mark.parametrize('value', ['javascript:alert(1)', 'ftp://files.example.org', 'help.example.org'])
    def test_a_value_that_is_not_an_address_hides_the_link_and_is_never_passed_on(
            self, real_app, monkeypatch, value):
        _, test_app = real_app
        monkeypatch.setenv('SUPPORT_URL', value)

        assert features(test_app)['support_url'] == 'none'

    def test_empty_value_is_the_same_as_unset(self, real_app, monkeypatch):
        _, test_app = real_app
        monkeypatch.setenv('SUPPORT_URL', '  ')

        assert 'support_url' not in features(test_app)

    def test_the_rest_of_the_features_answer_is_unchanged(self, real_app, monkeypatch):
        _, test_app = real_app
        before = features(test_app)
        monkeypatch.setenv('SUPPORT_URL', 'https://help.example.org/support')

        after = features(test_app)

        assert {key: value for key, value in after.items() if key != 'support_url'} == before
        assert after['edition'] == feature_flags.EDITION.value if hasattr(feature_flags.EDITION, 'value') \
            else after['edition'] == feature_flags.EDITION

    def test_features_is_public(self, real_app, monkeypatch):
        """People who cannot sign in are the ones who need the link."""
        _, test_app = real_app
        monkeypatch.setenv('SUPPORT_URL', 'https://help.example.org/support')

        response = test_app.test_client().get('/api/features')

        assert response.status_code == 200
        assert response.get_json()['support_url'] == 'https://help.example.org/support'


# ==================== The super admin setting ====================

class TestSuperAdminSetting:

    def test_setting_is_reported(self, real_app):
        _, test_app = real_app

        response = super_admin(test_app).post(SETTINGS, json={'support_url': 'https://help.example.org/support'})

        assert response.status_code == 200, response.get_json()
        assert response.get_json()['support_url'] == 'https://help.example.org/support'
        assert features(test_app)['support_url'] == 'https://help.example.org/support'

    def test_setting_wins_over_the_environment(self, real_app, monkeypatch):
        _, test_app = real_app
        monkeypatch.setenv('SUPPORT_URL', 'https://env.example.org/support')

        super_admin(test_app).post(SETTINGS, json={'support_url': 'https://setting.example.org/help'})

        assert features(test_app)['support_url'] == 'https://setting.example.org/help'

    def test_setting_none_hides_a_link_the_environment_gives(self, real_app, monkeypatch):
        _, test_app = real_app
        monkeypatch.setenv('SUPPORT_URL', 'https://env.example.org/support')

        response = super_admin(test_app).post(SETTINGS, json={'support_url': 'None'})

        assert response.status_code == 200, response.get_json()
        assert features(test_app)['support_url'] == 'none'

    def test_clearing_the_setting_falls_back_to_the_environment(self, real_app, monkeypatch):
        _, test_app = real_app
        monkeypatch.setenv('SUPPORT_URL', 'https://env.example.org/support')
        client = super_admin(test_app)
        client.post(SETTINGS, json={'support_url': 'https://setting.example.org/help'})

        response = client.post(SETTINGS, json={'support_url': ''})

        assert response.status_code == 200, response.get_json()
        assert response.get_json()['support_url'] == ''
        assert SystemConfig.query.filter_by(key=SystemConfig.KEY_SUPPORT_URL).count() == 0
        assert features(test_app)['support_url'] == 'https://env.example.org/support'

    def test_clearing_with_nothing_in_the_environment_leaves_no_support_url(self, real_app):
        _, test_app = real_app
        client = super_admin(test_app)
        client.post(SETTINGS, json={'support_url': 'https://setting.example.org/help'})

        client.post(SETTINGS, json={'support_url': ''})

        assert 'support_url' not in features(test_app)

    @pytest.mark.parametrize('value', ['javascript:alert(1)', 'ftp://files.example.org', 'help.example.org', 42, ['x']])
    def test_a_value_that_is_not_an_address_is_refused_and_the_old_one_kept(self, real_app, value):
        _, test_app = real_app
        client = super_admin(test_app)
        client.post(SETTINGS, json={'support_url': 'https://setting.example.org/help'})

        response = client.post(SETTINGS, json={'support_url': value})

        assert response.status_code == 400
        assert response.get_json() == {
            'error': 'The support page address must start with http:// or https://. Enter "none" to hide the link.'}
        assert features(test_app)['support_url'] == 'https://setting.example.org/help'

    def test_reading_the_settings_shows_the_setting_the_environment_and_what_applies(self, real_app, monkeypatch):
        _, test_app = real_app
        monkeypatch.setenv('SUPPORT_URL', 'https://env.example.org/support')
        client = super_admin(test_app)

        before = client.get(SETTINGS).get_json()
        client.post(SETTINGS, json={'support_url': 'none'})
        after = client.get(SETTINGS).get_json()

        assert before['support_url'] == ''
        assert before['support_url_environment'] == 'https://env.example.org/support'
        assert before['support_url_effective'] == 'https://env.example.org/support'
        assert after['support_url'] == 'none'
        assert after['support_url_effective'] == 'none'

    def test_saving_the_contact_email_alone_leaves_the_support_address(self, real_app):
        _, test_app = real_app
        client = super_admin(test_app)
        client.post(SETTINGS, json={'support_url': 'https://setting.example.org/help'})

        response = client.post(SETTINGS, json={'support_email': 'desk@example.org'})

        assert response.status_code == 200, response.get_json()
        assert features(test_app)['support_url'] == 'https://setting.example.org/help'
        assert client.get(SETTINGS).get_json()['support_email'] == 'desk@example.org'

    def test_saving_the_support_address_alone_leaves_the_contact_email(self, real_app):
        _, test_app = real_app
        client = super_admin(test_app)
        client.post(SETTINGS, json={'support_email': 'desk@example.org'})

        client.post(SETTINGS, json={'support_url': 'https://setting.example.org/help'})

        assert client.get(SETTINGS).get_json()['support_email'] == 'desk@example.org'

    def test_a_stored_value_that_is_not_an_address_hides_the_link(self, real_app):
        """A value written straight into the database is still never passed on."""
        _, test_app = real_app
        SystemConfig.set(SystemConfig.KEY_SUPPORT_URL, 'javascript:alert(1)')

        assert features(test_app)['support_url'] == 'none'


class TestOnlyASuperAdminMayChangeIt:

    def test_anonymous_caller_is_refused(self, real_app):
        _, test_app = real_app

        response = test_app.test_client().post(SETTINGS, json={'support_url': 'https://evil.example/phish'})

        assert response.status_code == 401
        assert 'support_url' not in features(test_app)

    def test_tenant_administrator_is_refused(self, real_app):
        _, test_app = real_app
        client = tenant_admin(test_app)

        saved = client.post(SETTINGS, json={'support_url': 'https://evil.example/phish'})
        read = client.get(SETTINGS)

        assert saved.status_code == 403
        assert read.status_code == 403
        assert 'support_url' not in features(test_app)
