"""Database driver selection and the start-up connection check.

On 2026-11-21 a freshly built image could not start against PostgreSQL: an
unpinned SQLAlchemy resolved to a release line that selects a different driver
for ``postgresql://`` URLs. Every test ran on SQLite, so nothing noticed.

These tests pin the behaviour that matters without needing a server, and run
for real against PostgreSQL when CI sets TEST_DATABASE_URL.
"""

import os

import pytest
from sqlalchemy import create_engine

from models import db
from tests.app_test_utils import load_test_app
from tests.conftest import fixture_database_url


class TestPostgresDriverSelection:
    def test_postgresql_url_selects_psycopg2(self):
        """create_engine imports the driver but does not connect."""
        engine = create_engine('postgresql://user:password@db.invalid:5432/decisions')

        assert engine.dialect.name == 'postgresql'
        assert engine.driver == 'psycopg2'

    def test_psycopg2_ships_its_own_libpq(self):
        """psycopg2-binary bundles libpq, so the image needs no system package for it."""
        import psycopg2

        assert psycopg2.__libpq_version__ > 0


class TestFixtureDatabase:
    def test_defaults_to_in_memory_sqlite(self, monkeypatch):
        monkeypatch.delenv('TEST_DATABASE_URL', raising=False)

        assert fixture_database_url() == 'sqlite:///:memory:'

    def test_empty_value_means_sqlite(self, monkeypatch):
        monkeypatch.setenv('TEST_DATABASE_URL', '  ')

        assert fixture_database_url() == 'sqlite:///:memory:'

    def test_uses_requested_test_database(self, monkeypatch):
        url = 'postgresql://decisions:secret@localhost:5432/decisions_test'
        monkeypatch.setenv('TEST_DATABASE_URL', url)

        assert fixture_database_url() == url

    @pytest.mark.parametrize('url', [
        'postgresql://decisions:secret@localhost:5432/decisions',
        'postgresql://decisions:secret@localhost:5432/production',
        'postgresql://decisions:secret@localhost:5432',
    ])
    def test_refuses_database_not_named_as_a_test_database(self, monkeypatch, url):
        """The fixtures drop every table, so a real database must never be accepted."""
        monkeypatch.setenv('TEST_DATABASE_URL', url)

        with pytest.raises(RuntimeError, match='must name a database containing "test"'):
            fixture_database_url()

    def test_app_fixture_runs_on_the_requested_backend(self, app):
        """Guards the PostgreSQL CI job against silently running on SQLite."""
        requested = os.environ.get('TEST_DATABASE_URL', '').strip()

        if requested.startswith('postgresql'):
            assert db.engine.dialect.name == 'postgresql'
            assert db.engine.driver == 'psycopg2'
        else:
            assert db.engine.dialect.name == 'sqlite'

    def test_round_trip_on_the_requested_backend(self, app, session, sample_user):
        assert db.session.execute(db.text('SELECT 1')).scalar() == 1
        assert sample_user.id is not None


@pytest.fixture
def real_app():
    """The real Flask app on in-memory SQLite, with initialisation not yet run."""
    app_module, test_app = load_test_app(secret_key='database-backend-test')
    saved_uri = test_app.config['SQLALCHEMY_DATABASE_URI']
    saved_state = dict(app_module.app_error_state)

    with test_app.app_context():
        app_module._db_initialized = False
        try:
            yield app_module, test_app
        finally:
            test_app.config['SQLALCHEMY_DATABASE_URI'] = saved_uri
            app_module.app_error_state.update(saved_state)
            db.session.remove()
            db.drop_all()
            app_module._db_initialized = False


class TestStartupConnectionCheck:
    def test_check_uses_the_engine_not_a_separate_connection(self, real_app, monkeypatch):
        """init_database used to open its own psycopg2 connection with
        sslmode=require for postgresql:// URLs, whatever the URL said. A
        PostgreSQL server without TLS (the self-hosting compose example) then
        failed initialisation although the engine itself could connect."""
        import psycopg2

        app_module, test_app = real_app
        calls = []

        def forbidden_connect(*args, **kwargs):
            calls.append((args, kwargs))
            raise AssertionError('init_database opened its own psycopg2 connection')

        monkeypatch.setattr(psycopg2, 'connect', forbidden_connect)
        # The engine is already bound to SQLite; only the configured URL says
        # PostgreSQL, which is what the old hand-built check keyed on.
        test_app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://user:password@db.invalid:5432/decisions'

        app_module.init_database()

        assert calls == []
        assert app_module.app_error_state['healthy'] is True
        assert app_module.app_error_state['error'] is None

    def test_health_reports_connected_database_after_start(self, real_app):
        app_module, test_app = real_app

        response = test_app.test_client().get('/health')

        assert response.status_code == 200
        assert response.get_json()['status'] == 'healthy'
        assert response.get_json()['database'] == 'connected'

    def test_unreachable_database_is_unhealthy_but_liveness_still_answers(self, real_app, monkeypatch):
        """/api/health is a liveness probe and answers without a database;
        /health is the route deploy checks must use to prove the database."""
        app_module, test_app = real_app

        def refuse(*args, **kwargs):
            raise RuntimeError('connection refused')

        monkeypatch.setattr(db.engine, 'connect', refuse)
        client = test_app.test_client()

        health = client.get('/health')
        liveness = client.get('/api/health')

        assert health.status_code == 503
        assert health.get_json()['status'] == 'unhealthy'
        assert 'connection refused' in health.get_json()['error']
        assert liveness.status_code == 200
        assert liveness.get_json()['status'] == 'ok'
