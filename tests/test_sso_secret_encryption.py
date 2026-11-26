"""
SSO client secrets are encrypted at rest (migration 2.9.0).

They use the mechanism that already protects saved SMTP passwords
(crypto.py: Fernet, key from SMTP_ENCRYPTION_KEY or, in the Enterprise
Edition, from the secret store). These tests pin:

  - a secret saved through the API is stored encrypted and is used decrypted;
  - a value stored before encryption existed still works (reads tolerate it);
  - the migration encrypts existing values in place, can run twice, and
    changes nothing on an installation without a key;
  - an encrypted value never leaves through the API.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet

import crypto
import migrations
from migrations import encrypt_sso_client_secrets, migrate_2_9_0
from models import db, SSOConfig, User, Tenant, TenantMembership, GlobalRole, MaturityState
from tests.app_test_utils import load_test_app

PASSWORD = 'a-long-test-password'
SECRET = 'q8~Zx.client-secret/with+odd=chars'


@pytest.fixture
def key(monkeypatch):
    value = Fernet.generate_key().decode('utf-8')
    monkeypatch.setenv('SMTP_ENCRYPTION_KEY', value)
    monkeypatch.delenv('AZURE_KEYVAULT_URL', raising=False)
    return value


@pytest.fixture
def no_key(monkeypatch):
    monkeypatch.delenv('SMTP_ENCRYPTION_KEY', raising=False)
    monkeypatch.delenv('AZURE_KEYVAULT_URL', raising=False)
    monkeypatch.setattr(crypto, '_get_encryption_key', lambda: None)


def stored_secret(config_id):
    """The column as it is in the database, bypassing the model."""
    return db.session.execute(
        db.text('SELECT client_secret FROM sso_configs WHERE id = :id'), {'id': config_id}).scalar()


def add_plain(domain, secret=SECRET):
    config = SSOConfig(domain=domain, provider_name='IdP', client_id='client', client_secret=secret,
                       discovery_url='https://idp.example.test/.well-known/openid-configuration')
    db.session.add(config)
    db.session.commit()
    return config.id


class TestModel:

    def test_set_stores_ciphertext_and_get_returns_the_secret(self, app, session, key):
        config = SSOConfig(domain='a.test', provider_name='IdP', client_id='client', discovery_url='https://x.test')
        config.set_client_secret(SECRET)
        session.add(config)
        session.commit()

        raw = stored_secret(config.id)
        assert raw.startswith(crypto.ENCRYPTED_PREFIX)
        assert SECRET not in raw
        assert config.get_client_secret() == SECRET
        assert Fernet(key.encode()).decrypt(raw[len(crypto.ENCRYPTED_PREFIX):].encode()).decode() == SECRET

    def test_a_value_saved_before_encryption_still_reads(self, app, session, key):
        config = db.session.get(SSOConfig, add_plain('legacy.test'))

        assert config.get_client_secret() == SECRET

    def test_without_a_key_the_secret_is_stored_as_given_and_still_works(self, app, session, no_key):
        config = SSOConfig(domain='nokey.test', provider_name='IdP', client_id='client', discovery_url='https://x.test')
        config.set_client_secret(SECRET)
        session.add(config)
        session.commit()

        assert stored_secret(config.id) == SECRET
        assert config.get_client_secret() == SECRET

    def test_an_encrypted_value_with_the_wrong_key_gives_nothing_not_garbage(self, app, session, key, monkeypatch):
        config = SSOConfig(domain='rotated.test', provider_name='IdP', client_id='client', discovery_url='https://x.test')
        config.set_client_secret(SECRET)
        session.add(config)
        session.commit()

        monkeypatch.setenv('SMTP_ENCRYPTION_KEY', Fernet.generate_key().decode('utf-8'))

        assert config.get_client_secret() is None

    def test_a_long_secret_fits_the_column(self, app, session, key):
        long_secret = 'S' * 400
        config = SSOConfig(domain='long.test', provider_name='IdP', client_id='client', discovery_url='https://x.test')
        config.set_client_secret(long_secret)
        session.add(config)
        session.commit()

        assert len(stored_secret(config.id)) <= SSOConfig.__table__.c.client_secret.type.length == 1024
        db.session.expire_all()
        assert db.session.get(SSOConfig, config.id).get_client_secret() == long_secret

    def test_to_dict_never_includes_the_secret_unless_asked_and_then_decrypted(self, app, session, key):
        config = SSOConfig(domain='dict.test', provider_name='IdP', client_id='client', discovery_url='https://x.test')
        config.set_client_secret(SECRET)
        session.add(config)
        session.commit()

        assert 'client_secret' not in config.to_dict()
        assert config.to_dict(include_secret=True)['client_secret'] == SECRET


class TestMigration:

    def test_existing_secrets_are_encrypted_in_place(self, app, session, key):
        first, second = add_plain('one.test', 'secret-one'), add_plain('two.test', 'secret-two')

        assert encrypt_sso_client_secrets(db) == 2

        db.session.expire_all()
        for config_id, secret in ((first, 'secret-one'), (second, 'secret-two')):
            raw = stored_secret(config_id)
            assert raw.startswith(crypto.ENCRYPTED_PREFIX) and secret not in raw
            assert db.session.get(SSOConfig, config_id).get_client_secret() == secret

    def test_running_it_twice_changes_nothing_the_second_time(self, app, session, key):
        config_id = add_plain('twice.test')
        assert migrate_2_9_0(db) >= 1
        db.session.expire_all()
        after_first = stored_secret(config_id)

        assert migrate_2_9_0(db) == 0

        db.session.expire_all()
        assert stored_secret(config_id) == after_first
        assert db.session.get(SSOConfig, config_id).get_client_secret() == SECRET

    def test_already_encrypted_and_plain_rows_side_by_side(self, app, session, key):
        encrypted = SSOConfig(domain='done.test', provider_name='IdP', client_id='client', discovery_url='https://x.test')
        encrypted.set_client_secret('already')
        session.add(encrypted)
        session.commit()
        before = stored_secret(encrypted.id)
        plain = add_plain('todo.test', 'not-yet')

        assert encrypt_sso_client_secrets(db) == 1

        db.session.expire_all()
        assert stored_secret(encrypted.id) == before
        assert db.session.get(SSOConfig, plain).get_client_secret() == 'not-yet'

    def test_without_a_key_nothing_is_changed_and_nothing_is_lost(self, app, session, no_key):
        config_id = add_plain('nokey.test')

        assert encrypt_sso_client_secrets(db) == 0
        assert migrate_2_9_0(db) == 0

        db.session.expire_all()
        assert stored_secret(config_id) == SECRET

    def test_a_key_that_cannot_encrypt_leaves_the_value_alone(self, app, session, monkeypatch):
        monkeypatch.setenv('SMTP_ENCRYPTION_KEY', 'not-a-fernet-key')
        monkeypatch.delenv('AZURE_KEYVAULT_URL', raising=False)
        config_id = add_plain('badkey.test')

        assert encrypt_sso_client_secrets(db) == 0

        db.session.expire_all()
        assert stored_secret(config_id) == SECRET

    def test_no_table_no_error(self):
        fake_db = SimpleNamespace(
            engine=SimpleNamespace(dialect=SimpleNamespace(name='sqlite'), connect=lambda: _NoTables()),
            text=lambda sql: sql,
        )

        assert encrypt_sso_client_secrets(fake_db) == 0

    def test_the_migration_is_registered(self):
        versions = [entry['version'] for entry in migrations.MIGRATIONS]
        assert versions[-1] == '2.9.0' or '2.9.0' in versions

    def test_postgresql_widens_the_column_once(self):
        """No PostgreSQL server here: check the statements the migration would send to one."""
        statements = []
        fake_db = SimpleNamespace(
            engine=SimpleNamespace(dialect=SimpleNamespace(name='postgresql'),
                                   connect=lambda: _PostgresStandIn(statements, width=255)),
            text=lambda sql: sql,
        )

        changes = migrate_2_9_0(fake_db)

        ddl = [s for s in statements if s.startswith('ALTER TABLE')]
        assert ddl == [
            'ALTER TABLE sso_configs ALTER COLUMN client_secret TYPE VARCHAR(1024)',
            'ALTER TABLE users ADD COLUMN name_edited_at TIMESTAMP',
        ]
        assert changes == 2
        for sqlite_only in ('PRAGMA', 'sqlite_master', 'DATETIME'):
            assert not any(sqlite_only in s for s in statements)

        statements.clear()
        fake_db.engine.connect = lambda: _PostgresStandIn(statements, width=1024, has_name_column=True)
        assert migrate_2_9_0(fake_db) == 0
        assert not any(s.startswith('ALTER TABLE') for s in statements)


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)

    def scalar(self):
        return self._rows[0][0] if self._rows else None


class _NoTables:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, statement, params=None):
        return _Result([])

    def commit(self):
        pass


class _PostgresStandIn(_NoTables):
    def __init__(self, statements, width, has_name_column=False):
        self.statements = statements
        self.width = width
        self.has_name_column = has_name_column

    def execute(self, statement, params=None):
        sql = ' '.join(str(statement).split())
        self.statements.append(sql)
        if 'information_schema.tables' in sql:
            return _Result([('x',)])
        if 'character_maximum_length' in sql:
            return _Result([(self.width,)])
        if 'information_schema.columns' in sql:
            return _Result([('x',)] if self.has_name_column else [])
        return _Result([])


class TestStartupAndApi:

    @pytest.fixture
    def app_module_and_app(self, tmp_path: Path, key):
        app_module, test_app = load_test_app(
            secret_key='test-secret-key-sso-secret-12345',
            database_url=f"sqlite:///{tmp_path / 'sso.db'}")
        with test_app.app_context():
            db.create_all()
            yield app_module, test_app
            db.session.remove()
            db.drop_all()
            app_module._db_initialized = False

    def admin_client(self, test_app, domain='sso.test'):
        tenant = Tenant(domain=domain, name='SSO', status='active', maturity_state=MaturityState.BOOTSTRAP)
        user = User(email=f'admin@{domain}', sso_domain=domain, auth_type='local', email_verified=True,
                    is_admin=True)
        user.set_name(first_name='Ada', last_name='Admin')
        user.set_password(PASSWORD)
        db.session.add_all([tenant, user])
        db.session.flush()
        db.session.add(TenantMembership(user_id=user.id, tenant_id=tenant.id, global_role=GlobalRole.ADMIN))
        db.session.commit()
        client = test_app.test_client()
        response = client.post('/api/auth/login', json={'email': user.email, 'password': PASSWORD})
        assert response.status_code == 200, response.data
        token = response.headers.get('X-CSRF-Token') or client.get('/api/auth/csrf-token').get_json()['csrf_token']
        client.environ_base['HTTP_X_CSRF_TOKEN'] = token
        return client

    def test_start_up_encrypts_secrets_saved_earlier_and_is_recorded(self, app_module_and_app):
        app_module, test_app = app_module_and_app
        config_id = add_plain('startup.test')

        app_module.init_database()

        db.session.expire_all()
        assert stored_secret(config_id).startswith(crypto.ENCRYPTED_PREFIX)
        assert db.session.get(SSOConfig, config_id).get_client_secret() == SECRET
        versions = {row[0] for row in db.session.execute(db.text('SELECT version FROM schema_migrations'))}
        assert '2.9.0' in versions

    def test_a_secret_saved_while_there_was_no_key_is_encrypted_on_a_later_start(
            self, app_module_and_app, monkeypatch):
        app_module, test_app = app_module_and_app
        app_module.init_database()  # the migration is now recorded as applied
        config_id = add_plain('later.test')

        app_module._db_initialized = False
        app_module.init_database()

        db.session.expire_all()
        assert stored_secret(config_id).startswith(crypto.ENCRYPTED_PREFIX)

    def test_saving_through_the_api_encrypts_and_never_returns_the_secret(self, app_module_and_app, monkeypatch):
        app_module, test_app = app_module_and_app
        app_module.init_database()
        monkeypatch.setattr(app_module, 'get_oidc_config', lambda url: {'authorization_endpoint': 'https://idp/a'})
        client = self.admin_client(test_app)

        created = client.post('/api/admin/sso', json={
            'domain': 'sso.test', 'provider_name': 'Okta', 'client_id': 'client-1',
            'client_secret': SECRET, 'discovery_url': 'https://idp.example.test/.well-known/openid-configuration'})

        assert created.status_code == 201, created.data
        body = created.get_json()
        assert 'client_secret' not in body
        raw = stored_secret(body['id'])
        assert raw.startswith(crypto.ENCRYPTED_PREFIX) and SECRET not in raw
        assert db.session.get(SSOConfig, body['id']).get_client_secret() == SECRET

        updated = client.put(f"/api/admin/sso/{body['id']}", json={'client_secret': 'rotated-secret'})

        assert updated.status_code == 200 and 'client_secret' not in updated.get_json()
        db.session.expire_all()
        raw = stored_secret(body['id'])
        assert raw.startswith(crypto.ENCRYPTED_PREFIX) and 'rotated-secret' not in raw
        assert db.session.get(SSOConfig, body['id']).get_client_secret() == 'rotated-secret'
        listed = client.get('/api/admin/sso').get_json()
        assert all('client_secret' not in entry for entry in listed)

    def test_sign_in_sends_the_decrypted_secret_to_the_provider(self, app_module_and_app, monkeypatch):
        app_module, test_app = app_module_and_app
        app_module.init_database()
        config = SSOConfig(domain='login.test', provider_name='Okta', client_id='client-1',
                           discovery_url='https://idp.example.test/.well-known/openid-configuration')
        config.set_client_secret(SECRET)
        db.session.add(config)
        db.session.commit()
        monkeypatch.setattr(app_module, 'get_oidc_config',
                            lambda url: {'authorization_endpoint': 'https://idp.example.test/authorize'})
        seen = {}
        real_session = app_module.OAuth2Session

        def recording_session(*args, **kwargs):
            seen.update(kwargs)
            return real_session(*args, **kwargs)

        monkeypatch.setattr(app_module, 'OAuth2Session', recording_session)

        response = test_app.test_client().get(f'/auth/sso/{config.id}')

        assert response.status_code == 302
        assert seen['client_secret'] == SECRET

    def test_sign_in_is_refused_clearly_when_the_secret_cannot_be_decrypted(
            self, app_module_and_app, monkeypatch, caplog):
        """A lost or changed key does not send people to the identity provider to fail there."""
        app_module, test_app = app_module_and_app
        app_module.init_database()
        config = SSOConfig(domain='lost-key.test', provider_name='Okta', client_id='client-1',
                           discovery_url='https://idp.example.test/.well-known/openid-configuration')
        config.set_client_secret(SECRET)
        db.session.add(config)
        db.session.commit()
        monkeypatch.setattr(app_module, 'get_oidc_config',
                            lambda url: {'authorization_endpoint': 'https://idp.example.test/authorize'})
        monkeypatch.setenv('SMTP_ENCRYPTION_KEY', Fernet.generate_key().decode('utf-8'))
        client = test_app.test_client()

        with caplog.at_level('ERROR'):
            response = client.get(f'/auth/sso/{config.id}')

        assert response.status_code == 503
        assert b'unavailable' in response.data
        assert 'lost-key.test' in caplog.text and 'cannot be decrypted' in caplog.text
        with client.session_transaction() as flask_session:
            assert 'sso_config_id' not in flask_session

    def test_the_callback_is_refused_clearly_when_the_secret_cannot_be_decrypted(
            self, app_module_and_app, monkeypatch):
        app_module, test_app = app_module_and_app
        app_module.init_database()
        config = SSOConfig(domain='lost-key2.test', provider_name='Okta', client_id='client-1',
                           discovery_url='https://idp.example.test/.well-known/openid-configuration')
        config.set_client_secret(SECRET)
        db.session.add(config)
        db.session.commit()
        monkeypatch.setattr(app_module, 'get_oidc_config',
                            lambda url: {'token_endpoint': 'https://idp.example.test/token'})
        monkeypatch.setenv('SMTP_ENCRYPTION_KEY', Fernet.generate_key().decode('utf-8'))
        client = test_app.test_client()
        with client.session_transaction() as flask_session:
            flask_session['sso_config_id'] = config.id
            flask_session['oauth_state'] = 'state-1'

        response = client.get('/auth/callback?code=abc&state=state-1')

        assert response.status_code == 503

    def test_start_up_names_the_organisations_whose_secret_cannot_be_decrypted(
            self, app_module_and_app, monkeypatch, caplog):
        app_module, test_app = app_module_and_app
        app_module.init_database()
        readable = SSOConfig(domain='fine.test', provider_name='IdP', client_id='c', discovery_url='https://x.test')
        readable.set_client_secret(SECRET)
        db.session.add(readable)
        db.session.commit()
        assert migrations.unreadable_sso_client_secrets(db) == []

        monkeypatch.setenv('SMTP_ENCRYPTION_KEY', Fernet.generate_key().decode('utf-8'))
        app_module._db_initialized = False
        with caplog.at_level('ERROR'):
            app_module.init_database()

        assert migrations.unreadable_sso_client_secrets(db) == ['fine.test']
        assert '1 SSO client secret(s) cannot be decrypted' in caplog.text
        assert 'fine.test' in caplog.text
