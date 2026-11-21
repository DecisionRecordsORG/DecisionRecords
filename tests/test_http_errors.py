"""
HTTP errors keep their status.

The catch-all Exception handler in app.py used to receive every HTTP error
without a handler of its own, so a rate-limited request (429) and a request
with the wrong method (405) were answered with 500 "An internal server error
occurred".
"""
import json
import os
import subprocess
import sys
from unittest.mock import patch

import pytest
from werkzeug.exceptions import Gone, TooManyRequests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db
from tests.app_test_utils import load_test_app

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def api_app():
    app_module, test_app = load_test_app(secret_key='test-secret-key-http-errors-12345')
    with test_app.app_context():
        db.create_all()
        app_module.init_database()
        yield test_app
        db.session.remove()
        db.drop_all()
        app_module._db_initialized = False


@pytest.fixture
def client(api_app):
    return api_app.test_client()


def raising(exception):
    def view(*args, **kwargs):
        raise exception
    return view


class TestWrongMethod:

    # GET is left out on purpose: when the built frontend is present its
    # catch-all GET route answers unknown /api/ GETs with a JSON 404 instead.
    @pytest.mark.parametrize('method,url', [
        ('put', '/api/contact'),
        ('delete', '/api/feedback'),
        ('put', '/api/sponsorship'),
        ('post', '/api/version'),
    ])
    def test_api_path_answers_405_as_json(self, client, method, url):
        response = getattr(client, method)(url)

        assert response.status_code == 405
        assert response.get_json() == {'error': 'Method not allowed'}
        assert 'Allow' in response.headers

    def test_non_api_path_answers_405_as_text(self, client):
        response = client.post('/login')

        assert response.status_code == 405
        assert response.mimetype == 'text/plain'
        assert response.get_data(as_text=True) == 'Method not allowed'


class TestRateLimited:

    def test_api_path_answers_429_as_json_with_retry_after(self, api_app, client):
        with patch.dict(api_app.view_functions, {'get_version': raising(TooManyRequests())}):
            response = client.get('/api/version')

        assert response.status_code == 429
        assert response.get_json() == {'error': 'Too many requests. Please wait a minute and try again.'}
        assert response.headers['Retry-After'] == '60'

    def test_retry_after_from_the_exception_is_kept(self, api_app, client):
        with patch.dict(api_app.view_functions, {'get_version': raising(TooManyRequests(retry_after=17))}):
            response = client.get('/api/version')

        assert response.status_code == 429
        assert response.headers['Retry-After'] == '17'

    def test_json_sign_in_on_an_auth_path_answers_429_as_json(self, api_app, client):
        """The super admin sign-in posts JSON to /auth/local and shows the error text."""
        with patch.dict(api_app.view_functions, {'local_login': raising(TooManyRequests())}):
            response = client.post('/auth/local', json={'username': 'admin', 'password': 'x'})

        assert response.status_code == 429
        assert response.get_json() == {'error': 'Too many requests. Please wait a minute and try again.'}
        assert 'Retry-After' in response.headers

    def test_the_real_rate_limiter_answers_429(self):
        """Run the app the way production does (rate limiting on) in a fresh process.

        The test suite disables the limiter (FLASK_ENV=testing), so the only way
        to exercise flask-limiter's own exception is a process without that flag.
        """
        pytest.importorskip('flask_limiter')
        script = (
            "import json\n"
            "import app as app_module\n"
            "client = app_module.app.test_client()\n"
            "payload = {'username': 'nobody', 'password': 'wrong-password'}\n"
            "out = []\n"
            "for _ in range(6):\n"
            "    r = client.post('/auth/local', json=payload)\n"
            "    out.append([r.status_code, r.get_json(silent=True), r.headers.get('Retry-After')])\n"
            "print('RESULT ' + json.dumps(out))\n"
        )
        env = {
            key: value for key, value in os.environ.items()
            if key not in ('FLASK_ENV', 'TESTING', 'TEST_DATABASE_URL', 'REDIS_URL', 'PYTHONPATH')
        }
        env.update({
            'DECISION_RECORDS_EDITION': 'community',
            'DATABASE_URL': 'sqlite:///:memory:',
            'SECRET_KEY': 'rate-limit-subprocess-test',
            'PYTHONDONTWRITEBYTECODE': '1',
        })

        completed = subprocess.run(
            [sys.executable, '-c', script], cwd=REPO_ROOT, env=env,
            capture_output=True, text=True, timeout=120,
        )

        result_lines = [line for line in completed.stdout.splitlines() if line.startswith('RESULT ')]
        assert result_lines, completed.stdout[-2000:] + completed.stderr[-2000:]
        results = json.loads(result_lines[-1][len('RESULT '):])

        # Super admin sign-in allows 5 attempts per minute: five are answered as
        # failed sign-ins, the sixth is refused by the limiter. It used to be a 500.
        statuses = [status for status, _body, _retry in results]
        assert statuses[:5] == [401] * 5, results
        assert statuses[5] == 429, results
        status, body, retry_after = results[-1]
        assert body == {'error': 'Too many requests. Please wait a minute and try again.'}
        assert retry_after is not None and 1 <= int(retry_after) <= 60


class TestOtherStatuses:

    def test_an_http_error_without_a_message_of_its_own_uses_its_name(self, api_app, client):
        with patch.dict(api_app.view_functions, {'get_version': raising(Gone())}):
            response = client.get('/api/version')

        assert response.status_code == 410
        assert response.get_json() == {'error': 'Gone'}

    def test_unsupported_media_type_is_415_not_500(self, client):
        """request.get_json() raises 415 when a POST has no JSON content type."""
        response = client.post('/api/auth/login', data='email=a', content_type='text/plain')

        assert response.status_code in (400, 415)
        assert 'error' in response.get_json()

    def test_unknown_api_path_is_still_404(self, client):
        response = client.get('/api/does-not-exist')

        assert response.status_code == 404
        assert 'error' in response.get_json()

    def test_unauthenticated_is_still_401(self, client):
        response = client.get('/api/system/config')

        assert response.status_code == 401
        assert response.get_json() == {'error': 'Authentication required'}

    def test_an_unexpected_exception_is_still_a_generic_500(self, api_app, client):
        with patch.dict(api_app.view_functions, {'get_version': raising(RuntimeError('secret detail'))}):
            response = client.get('/api/version')

        assert response.status_code == 500
        assert response.get_json() == {'error': 'An internal server error occurred'}
        assert 'secret detail' not in response.get_data(as_text=True)
