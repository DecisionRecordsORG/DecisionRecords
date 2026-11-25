"""The production container must start without errors in its log.

Three lines were printed on every start for months and nobody read them:

1. the start script tried to write a private DNS record and was refused;
2. gunicorn could not create its control socket in a home directory the
   image's user does not have;
3. log forwarding read its settings before the database was attached to the
   app, failed, and stayed switched off.

These tests read the Enterprise start script and start the app the way a
gunicorn worker does. Enterprise only: they skip without the `ee/` checkout.
"""
import json
import os
import re
import shlex
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STARTUP_SCRIPT = os.path.join(REPO_ROOT, 'ee', 'deployment', 'startup.sh')
DEV_COMPOSE = os.path.join(REPO_ROOT, 'ee', 'deployment', 'docker-compose.dev.yml')
DOCKERFILE = os.path.join(REPO_ROOT, 'ee', 'deployment', 'Dockerfile.production')

try:
    from ee.backend.analytics import log_forwarding
    EE_AVAILABLE = os.path.exists(STARTUP_SCRIPT)
except ImportError:
    log_forwarding = None
    EE_AVAILABLE = False

pytestmark = pytest.mark.skipif(not EE_AVAILABLE, reason="Enterprise Edition modules not available")

LOAD_ERROR = 'Error loading log forwarding config'


def read(path):
    with open(path, encoding='utf-8') as handle:
        return handle.read()


def code_lines(script):
    """The script without its comments."""
    return '\n'.join(line for line in script.splitlines() if not line.lstrip().startswith('#'))


def gunicorn_command():
    """The arguments of the `exec gunicorn ...` line of the start script."""
    lines = [line for line in code_lines(read(STARTUP_SCRIPT)).splitlines() if 'gunicorn' in line]
    assert len(lines) == 1, lines
    words = shlex.split(lines[0])
    assert words[:2] == ['exec', 'gunicorn'], words
    return words[2:]


class TestStartScript:

    def test_it_is_valid_shell(self):
        completed = subprocess.run(['bash', '-n', STARTUP_SCRIPT], capture_output=True, text=True)
        assert completed.returncode == 0, completed.stderr

    def test_it_does_not_call_azure(self):
        """No instance metadata token, no management API, no DNS record.

        The record (app.adr.internal) was for Azure Container Instances. On the
        VM nothing reads it, the write was refused on every start, and with the
        permission it would publish Docker's bridge address.
        """
        code = code_lines(read(STARTUP_SCRIPT))
        for forbidden in ('169.254.169.254', 'management.azure.com', 'privateDnsZones', 'curl', 'DNS'):
            assert forbidden not in code, forbidden

    def test_it_only_starts_gunicorn(self):
        commands = [
            line.strip() for line in code_lines(read(STARTUP_SCRIPT)).splitlines()
            if line.strip() and not line.strip().startswith(('set ', 'echo '))
        ]
        assert len(commands) == 1 and commands[0].startswith('exec gunicorn '), commands

    def test_the_control_socket_is_off(self):
        """gunicorn 25.1+ opens $HOME/.gunicorn/gunicorn.ctl; the image's user has no home."""
        assert '--no-control-socket' in gunicorn_command()

    def test_the_image_user_still_has_no_home_directory(self):
        """If this changes, the control socket decision can be revisited; until then the flag stays."""
        dockerfile = read(DOCKERFILE)
        assert re.search(r'useradd -r -g appuser appuser', dockerfile)
        assert 'CMD ["./startup.sh"]' in dockerfile

    def test_the_dev_container_uses_the_same_gunicorn_arguments(self):
        match = re.search(r'^\s*command:\s*(\[.*\])\s*$', read(DEV_COMPOSE), re.MULTILINE)
        assert match, 'no command in docker-compose.dev.yml'
        assert json.loads(match.group(1)) == ['gunicorn'] + gunicorn_command()

    def test_the_installed_gunicorn_accepts_every_argument(self):
        """An option gunicorn does not know stops the container from starting.

        The deploy pre-flight starts gunicorn itself and does not run this
        script, so this is the check that the script's arguments are real.
        Runs wherever the pinned gunicorn is installed (CI installs it).
        """
        config = pytest.importorskip('gunicorn.config')
        args = gunicorn_command()
        parsed = config.Config().parser().parse_args(args)
        assert parsed.control_socket_disable is True
        assert parsed.args == ['app:app']

    def test_requirements_pin_a_gunicorn_that_has_the_option(self):
        """--no-control-socket exists from gunicorn 25.1.0."""
        match = re.search(r'^gunicorn==(\d+)\.(\d+)', read(os.path.join(REPO_ROOT, 'requirements.txt')), re.MULTILINE)
        assert match, 'gunicorn is not pinned in requirements.txt'
        assert (int(match.group(1)), int(match.group(2))) >= (25, 1)


# Runs in a fresh interpreter: imports the app as a gunicorn worker does and
# serves a first request, with log forwarding switched on in the database.
WORKER_SCRIPT = r'''
import json, logging, sys

records = []

class Collect(logging.Handler):
    def emit(self, record):
        records.append([record.name, record.levelname, record.getMessage()])

logging.getLogger().addHandler(Collect())

from ee.backend.analytics import log_forwarding

started = []

def fake_init(app):
    config = log_forwarding._get_log_forwarding_config()
    started.append({'enabled': config['enabled'], 'endpoint_url': config['endpoint_url']})
    return True

# No exporter is started: the test is about when and whether set-up happens.
log_forwarding._init_otel_logger_provider = fake_init

import app as app_module

after_import = {'started': list(started), 'records': list(records)}
client = app_module.app.test_client()
status = client.get('/api/version').status_code
print('RESULT ' + json.dumps({
    'after_import': after_import,
    'status': status,
    'started': started,
    'records': records,
    'db_initialized': app_module._db_initialized,
}))
'''

SEED_SCRIPT = r'''
import app as app_module
from models import SystemConfig

app_module.app.test_client().get('/api/version')
assert app_module._db_initialized
with app_module.app.app_context():
    SystemConfig.set(SystemConfig.KEY_LOG_FORWARDING_ENABLED, SWITCH_VALUE)
    SystemConfig.set(SystemConfig.KEY_LOG_FORWARDING_ENDPOINT_URL, 'http://127.0.0.1:4317')
print('SEEDED')
'''


def run_python(script, database_path):
    env = {
        key: value for key, value in os.environ.items()
        if key not in ('TEST_DATABASE_URL', 'PYTHONPATH')
    }
    env.update({
        'DECISION_RECORDS_EDITION': 'enterprise',
        'DATABASE_URL': f'sqlite:///{database_path}',
        'SECRET_KEY': 'startup-log-subprocess-test',
        'AZURE_KEYVAULT_URL': '',
        'FLASK_ENV': 'testing',
        'TESTING': 'true',
        'PYTHONDONTWRITEBYTECODE': '1',
    })
    return subprocess.run(
        [sys.executable, '-c', script], cwd=REPO_ROOT, env=env,
        capture_output=True, text=True, timeout=180,
    )


def start_worker(tmp_path, enabled):
    database_path = tmp_path / 'startup.db'
    seeded = run_python(SEED_SCRIPT.replace('SWITCH_VALUE', repr('true' if enabled else 'false')), database_path)
    assert 'SEEDED' in seeded.stdout, seeded.stdout[-2000:] + seeded.stderr[-2000:]

    completed = run_python(WORKER_SCRIPT, database_path)
    lines = [line for line in completed.stdout.splitlines() if line.startswith('RESULT ')]
    assert lines, completed.stdout[-2000:] + completed.stderr[-2000:]
    return json.loads(lines[-1][len('RESULT '):]), completed


class TestLogForwardingAtStartUp:

    def test_a_worker_starts_forwarding_when_it_is_switched_on(self, tmp_path):
        """The regression: set-up ran before db.init_app(app) and never took effect."""
        result, completed = start_worker(tmp_path, enabled=True)

        assert result['status'] == 200
        assert result['db_initialized'] is True
        # Not while importing: the database is not ready then.
        assert result['after_import']['started'] == []
        # Once, after the database was initialised, with the stored settings.
        assert result['started'] == [{'enabled': True, 'endpoint_url': 'http://127.0.0.1:4317'}]

        messages = [message for _name, _level, message in result['records']]
        assert not [m for m in messages if LOAD_ERROR in m], messages
        assert LOAD_ERROR not in completed.stderr
        assert LOAD_ERROR not in completed.stdout

    def test_no_error_is_logged_from_the_log_forwarding_module_at_start_up(self, tmp_path):
        result, _completed = start_worker(tmp_path, enabled=True)
        problems = [
            record for record in result['records']
            if record[0] == 'ee.backend.analytics.log_forwarding' and record[1] in ('WARNING', 'ERROR', 'CRITICAL')
        ]
        assert problems == []

    def test_a_worker_does_not_start_forwarding_when_it_is_switched_off(self, tmp_path):
        result, completed = start_worker(tmp_path, enabled=False)

        assert result['status'] == 200
        assert result['started'] == []
        assert LOAD_ERROR not in completed.stderr

    def test_app_does_not_set_up_forwarding_at_import(self):
        """Nothing between the imports and db.init_app(app) may read settings from the database."""
        source = read(os.path.join(REPO_ROOT, 'app.py'))
        before_database = source[:source.index('\ndb.init_app(app)')]
        assert 'setup_log_forwarding(app)' not in before_database
        assert source.count('setup_log_forwarding_from_settings()') >= 2  # defined and called


@pytest.fixture
def clean_cache():
    """Each test starts and ends with an empty settings cache."""
    def reset():
        for key in log_forwarding._config_cache:
            log_forwarding._config_cache[key] = None
    reset()
    yield
    reset()


class TestSettingsReadFailure:

    def test_a_failed_read_is_not_remembered_as_disabled(self, app, session, clean_cache, caplog):
        """A read that fails must not hide the stored settings for five minutes.

        It did: after the failed read at start-up the super admin page showed
        log forwarding as disabled with default values, whatever was stored.
        """
        from unittest.mock import patch
        from models import SystemConfig

        SystemConfig.set(SystemConfig.KEY_LOG_FORWARDING_ENABLED, 'true')
        SystemConfig.set(SystemConfig.KEY_LOG_FORWARDING_ENDPOINT_URL, 'https://otlp.example.test:4317')

        with patch.object(SystemConfig, 'get_bool', side_effect=RuntimeError('database not ready')):
            with caplog.at_level('ERROR', logger='ee.backend.analytics.log_forwarding'):
                failed = log_forwarding._get_log_forwarding_config()
        assert failed['enabled'] is False
        assert LOAD_ERROR in caplog.text

        config = log_forwarding._get_log_forwarding_config()
        assert config['enabled'] is True
        assert config['endpoint_url'] == 'https://otlp.example.test:4317'

    def test_a_successful_read_is_cached(self, app, session, clean_cache):
        from unittest.mock import patch
        from models import SystemConfig

        SystemConfig.set(SystemConfig.KEY_LOG_FORWARDING_ENABLED, 'true')
        assert log_forwarding._get_log_forwarding_config()['enabled'] is True

        with patch.object(SystemConfig, 'get_bool', side_effect=AssertionError('read again')):
            assert log_forwarding._get_log_forwarding_config()['enabled'] is True

    def test_set_up_does_nothing_when_the_settings_cannot_be_read(self, app, clean_cache):
        """Set-up must never raise into the app's start-up."""
        from unittest.mock import patch
        from models import SystemConfig

        with patch.object(SystemConfig, 'get_bool', side_effect=RuntimeError('database not ready')), \
                patch.object(log_forwarding, '_init_otel_logger_provider') as init:
            log_forwarding.setup_log_forwarding(app)
        init.assert_not_called()
