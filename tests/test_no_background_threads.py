"""
No test leaves anything running that talks to the database.

The application starts one background thread per process: the daily data
retention check (retention.ensure_scheduler, called on a request once the
database is ready). Under tests it must never start, however the app was
loaded, because the fixture-based tests share one PostgreSQL database in CI.
A thread that outlives its test queries that database a minute later while
some other test is dropping its tables; PostgreSQL then reports a deadlock in
that other test's teardown, far from the cause.

Three layers keep that from happening, and each is tested here:

1. ensure_scheduler refuses to start under any sign of a test run, including
   PYTEST_CURRENT_TEST, which pytest sets for every test and child processes
   inherit (tests/test_retention_scheduler.py tests each sign on its own);
2. an autouse fixture in tests/conftest.py fails the test that leaves a
   retention thread alive;
3. the fixtures that drop the schema release every connection they hold first.
"""
import os
import subprocess
import sys
import threading

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import retention
from models import db
from tests.app_test_utils import load_test_app

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def real_app(tmp_path=None):
    built = None
    if tmp_path is not None:
        (tmp_path / 'index.html').write_text('<!doctype html><app-root></app-root>')
        built = tmp_path
    return load_test_app(secret_key='test-secret-key-background-threads', built_frontend=built)


@pytest.fixture(params=['no frontend build', 'built frontend'])
def loaded(request, tmp_path):
    """The real app, loaded each way the suite loads it, with a request served."""
    app_module, test_app = real_app(tmp_path if request.param == 'built frontend' else None)
    with test_app.app_context():
        db.create_all()
        app_module.init_database()
        yield app_module, test_app
        db.session.remove()
        db.drop_all()
        app_module._db_initialized = False
    if request.param == 'built frontend':
        load_test_app(secret_key='test-secret-key-background-threads')


class TestTheRealAppStartsNoThreadUnderTests:

    def test_serving_requests_starts_no_retention_thread(self, loaded):
        app_module, test_app = loaded
        client = test_app.test_client()

        assert client.get('/api/version').status_code == 200
        assert client.get('/api/features').status_code == 200

        assert app_module._db_initialized is True  # the point at which the app asks for the thread
        assert retention.scheduler_threads() == []
        assert retention._scheduler_thread is None

    def test_not_even_when_the_app_does_not_look_like_a_test_app(self, loaded, monkeypatch):
        """An app loaded without TESTING or FLASK_ENV still stays inert inside pytest."""
        app_module, test_app = loaded
        test_app.config['TESTING'] = False
        monkeypatch.delenv('FLASK_ENV', raising=False)
        monkeypatch.delenv('TESTING', raising=False)
        monkeypatch.delenv('RETENTION_AUTO_RUN', raising=False)
        try:
            assert test_app.test_client().get('/api/version').status_code == 200

            assert retention.scheduler_threads() == []
        finally:
            test_app.config['TESTING'] = True

    def test_the_app_asks_for_the_thread_on_every_request(self, loaded, monkeypatch):
        """So the two tests above do exercise the call that would start it."""
        app_module, test_app = loaded
        asked = []
        monkeypatch.setattr(retention, 'ensure_scheduler', lambda flask_app: asked.append(flask_app))

        test_app.test_client().get('/api/version')

        assert asked == [test_app]


class TestAChildProcessIsInertToo:

    def test_a_child_started_by_a_test_with_a_cleaned_environment_does_not_start_the_thread(self):
        """Like the rate limiter test, which removes FLASK_ENV and TESTING for its child."""
        env = {key: value for key, value in os.environ.items()
               if key not in ('FLASK_ENV', 'TESTING', 'TEST_DATABASE_URL', 'RETENTION_AUTO_RUN', 'PYTHONPATH')}
        env.update({'DATABASE_URL': 'sqlite:///:memory:', 'PYTHONDONTWRITEBYTECODE': '1'})
        script = (
            "from flask import Flask\n"
            "import retention\n"
            "app = Flask('child')\n"
            "print('STARTED', retention.ensure_scheduler(app) is not None, len(retention.scheduler_threads()))\n"
        )

        completed = subprocess.run([sys.executable, '-c', script], cwd=ROOT, env=env,
                                   capture_output=True, text=True, timeout=120)

        assert 'STARTED False 0' in completed.stdout, completed.stdout[-1000:] + completed.stderr[-1000:]

    def test_a_child_never_gets_the_shared_test_database_by_accident(self):
        """load_test_app points the real app at in-memory SQLite, never at TEST_DATABASE_URL."""
        _app_module, test_app = real_app()

        assert test_app.config['SQLALCHEMY_DATABASE_URI'] == 'sqlite:///:memory:'
        assert os.environ['DATABASE_URL'] == 'sqlite:///:memory:'


class TestTheGuardFixture:
    """tests/conftest.py fails a test that leaves a retention thread alive."""

    def test_a_leaked_thread_fails_the_test_that_leaked_it(self, pytester_like, monkeypatch):
        result = pytester_like('''
import threading
import retention

def test_leaks():
    stop = threading.Event()
    thread = threading.Thread(target=stop.wait, args=(30,), name=retention.SCHEDULER_THREAD_NAME, daemon=True)
    thread.start()
    retention._scheduler_started.append((thread, stop))

def test_next_one_is_clean():
    assert retention.scheduler_threads() == []
''')

        assert 'retention scheduler thread(s) were left running by this test' in result
        assert '1 passed, 1 error' in result or '2 passed, 1 error' in result, result[-1500:]

    def test_nothing_is_running_now(self):
        assert retention.scheduler_threads() == []
        assert [thread.name for thread in threading.enumerate()
                if thread.name == retention.SCHEDULER_THREAD_NAME] == []


@pytest.fixture
def pytester_like(tmp_path):
    """Run a small test file in a child pytest that uses this suite's conftest."""
    def run(source):
        path = os.path.join(ROOT, 'tests', f'_guard_probe_{os.getpid()}_test.py')
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(source)
        try:
            env = {key: value for key, value in os.environ.items() if key != 'TEST_DATABASE_URL'}
            env['PYTHONDONTWRITEBYTECODE'] = '1'
            completed = subprocess.run(
                [sys.executable, '-m', 'pytest', path, '-q', '-p', 'no:cacheprovider'],
                cwd=ROOT, env=env, capture_output=True, text=True, timeout=180)
            return completed.stdout + completed.stderr
        finally:
            os.remove(path)
    return run
