"""
HTTP tests for data retention: the super admin endpoints, the settings
endpoints and the unchanged contract of POST /api/admin/execute-gdpr-tasks.
"""

from datetime import timedelta

import pytest

import retention
from models import (
    db, User, Tenant, TenantMembership, GlobalRole, MaturityState, LoginHistory, RetentionRun,
    RetentionErasure, SystemConfig, DEFAULT_MASTER_PASSWORD, DEFAULT_MASTER_USERNAME,
)
from tests.app_test_utils import load_test_app
from tests.retention_test_data import make_full_tenant, expire_tenant, naive_now

PASSWORD = 'a-long-test-password'
CRON_SECRET = 'cron-secret-for-retention-tests'


@pytest.fixture
def app_module_and_app():
    app_module, test_app = load_test_app(secret_key='test-secret-key-retention-12345')
    with test_app.app_context():
        db.create_all()
        app_module.init_database()
        yield app_module, test_app
        db.session.remove()
        db.drop_all()
        app_module._db_initialized = False


@pytest.fixture
def api_app(app_module_and_app):
    return app_module_and_app[1]


@pytest.fixture
def client(api_app):
    return api_app.test_client()


def _attach_csrf(test_client, login_response):
    token = login_response.headers.get('X-CSRF-Token')
    if not token:
        token = test_client.get('/api/auth/csrf-token').get_json()['csrf_token']
    test_client.environ_base['HTTP_X_CSRF_TOKEN'] = token


def _login_as(api_app, role):
    tenant = Tenant.query.filter_by(domain='acme.test').first()
    if tenant is None:
        tenant = Tenant(domain='acme.test', name='Acme', status='active', maturity_state=MaturityState.BOOTSTRAP)
        db.session.add(tenant)
        db.session.commit()
    user = User(email=f'{role.value}@acme.test', sso_domain='acme.test', auth_type='local', email_verified=True)
    user.set_name(first_name='Test', last_name='Person')
    user.set_password(PASSWORD)
    user.is_admin = role != GlobalRole.USER
    db.session.add(user)
    db.session.flush()
    db.session.add(TenantMembership(user_id=user.id, tenant_id=tenant.id, global_role=role))
    db.session.commit()
    test_client = api_app.test_client()
    response = test_client.post('/api/auth/login', json={'email': user.email, 'password': PASSWORD})
    assert response.status_code == 200, response.data
    _attach_csrf(test_client, response)
    return test_client


@pytest.fixture
def member_client(api_app):
    return _login_as(api_app, GlobalRole.USER)


@pytest.fixture
def admin_client(api_app):
    return _login_as(api_app, GlobalRole.ADMIN)


@pytest.fixture
def master_client(api_app):
    test_client = api_app.test_client()
    response = test_client.post('/auth/local', json={
        'username': DEFAULT_MASTER_USERNAME, 'password': DEFAULT_MASTER_PASSWORD,
    })
    assert response.status_code == 200, response.data
    _attach_csrf(test_client, response)
    return test_client


def add_old_logins(count=1):
    db.session.add_all([
        LoginHistory(email=f'old{i}@example.com', login_method='password', success=True,
                     created_at=naive_now() - timedelta(days=120))
        for i in range(count)
    ])
    db.session.commit()


def two_expired_tenants():
    for domain, key in (('first.example', 'fir'), ('second.example', 'sec')):
        expire_tenant(make_full_tenant(domain, key)['tenant'])


NEW_ENDPOINTS = [
    ('get', '/api/superadmin/retention', None),
    ('post', '/api/superadmin/retention/run', {'categories': ['login_history'], 'confirm_counts': {'login_history': 5}}),
    ('get', '/api/admin/settings/retention', None),
    ('put', '/api/admin/settings/retention', {'auto_run_enabled': False}),
    ('post', '/api/admin/settings/retention', {'limits': {'tenants': 5}}),
]
ENDPOINT_IDS = [f'{method} {url}' for method, url, _ in NEW_ENDPOINTS]


def call(test_client, method, url, body):
    return getattr(test_client, method)(url, json=body) if body is not None else getattr(test_client, method)(url)


# ==================== Who may call ====================

class TestAuthorisation:
    def _nothing_changed(self):
        assert RetentionRun.query.count() == 0
        assert LoginHistory.query.filter(LoginHistory.email.like('old%')).count() == 1
        assert retention.get_settings()['auto_run_enabled'] is True
        assert retention.get_limits()['tenants'] == 1

    @pytest.mark.parametrize('method, url, body', NEW_ENDPOINTS, ids=ENDPOINT_IDS)
    def test_anonymous_is_refused(self, client, method, url, body):
        add_old_logins()
        response = call(client, method, url, body)
        assert response.status_code in (401, 403)
        assert 'error' in response.get_json()
        self._nothing_changed()

    @pytest.mark.parametrize('method, url, body', NEW_ENDPOINTS, ids=ENDPOINT_IDS)
    def test_member_is_refused(self, member_client, method, url, body):
        add_old_logins()
        response = call(member_client, method, url, body)
        assert response.status_code == 403
        assert response.get_json() == {'error': 'Master account access required'}
        self._nothing_changed()

    @pytest.mark.parametrize('method, url, body', NEW_ENDPOINTS, ids=ENDPOINT_IDS)
    def test_tenant_admin_is_refused(self, admin_client, method, url, body):
        add_old_logins()
        response = call(admin_client, method, url, body)
        assert response.status_code == 403
        assert response.get_json() == {'error': 'Master account access required'}
        self._nothing_changed()

    @pytest.mark.parametrize('method, url, body', NEW_ENDPOINTS, ids=ENDPOINT_IDS)
    def test_super_admin_is_allowed(self, master_client, method, url, body):
        add_old_logins()
        response = call(master_client, method, url, body)
        assert response.status_code == 200, response.get_json()

    def test_state_changing_calls_need_the_csrf_token(self, master_client):
        add_old_logins()
        master_client.environ_base.pop('HTTP_X_CSRF_TOKEN')
        response = master_client.post('/api/superadmin/retention/run', json={
            'categories': ['login_history'], 'confirm_counts': {'login_history': 1}})
        assert response.status_code == 403
        self._nothing_changed()

    @pytest.mark.parametrize('client_name', ['client', 'member_client', 'admin_client'])
    def test_cron_endpoint_refuses_everyone_but_super_admin_and_cron(self, request, client_name):
        test_client = request.getfixturevalue(client_name)
        add_old_logins()
        response = test_client.post('/api/admin/execute-gdpr-tasks')
        assert response.status_code == 403
        assert 'error' in response.get_json()
        self._nothing_changed()

    def test_cron_endpoint_refuses_a_wrong_or_unconfigured_secret(self, client, monkeypatch):
        add_old_logins()
        monkeypatch.delenv('GDPR_CRON_SECRET', raising=False)
        assert client.post('/api/admin/execute-gdpr-tasks', headers={'X-Cron-Secret': ''}).status_code == 403
        assert client.post('/api/admin/execute-gdpr-tasks', headers={'X-Cron-Secret': 'x'}).status_code == 403
        monkeypatch.setenv('GDPR_CRON_SECRET', CRON_SECRET)
        response = client.post('/api/admin/execute-gdpr-tasks', headers={'X-Cron-Secret': CRON_SECRET + 'x'})
        assert response.status_code == 403
        self._nothing_changed()


# ==================== POST /api/admin/execute-gdpr-tasks ====================

class TestCronEndpoint:
    def test_cron_secret_runs_and_keeps_the_response_shape(self, client, monkeypatch):
        monkeypatch.setenv('GDPR_CRON_SECRET', CRON_SECRET)
        add_old_logins(2)

        response = client.post('/api/admin/execute-gdpr-tasks', headers={'X-Cron-Secret': CRON_SECRET})

        assert response.status_code == 200
        body = response.get_json()
        assert body['message'] == 'GDPR tasks executed'
        assert body['results'] == {
            'anonymized_users': 0, 'purged_decisions': 0, 'purged_tenants': 0,
            'cleaned_login_history': 2, 'purged_inquiries': 0}
        assert body['held_back'] == {} and body['errors'] == {} and body['status'] == 'completed'
        stored = db.session.get(RetentionRun, body['run_id'])
        assert stored.trigger == 'cron' and stored.started_by is None

    def test_super_admin_session_runs_and_is_recorded_by_name(self, master_client):
        add_old_logins(1)
        response = master_client.post('/api/admin/execute-gdpr-tasks')
        assert response.status_code == 200
        body = response.get_json()
        assert body['results']['cleaned_login_history'] == 1
        stored = db.session.get(RetentionRun, body['run_id'])
        assert stored.trigger == 'super_admin' and stored.started_by == DEFAULT_MASTER_USERNAME

    def test_over_the_limit_is_held_back_and_reported(self, client, monkeypatch):
        monkeypatch.setenv('GDPR_CRON_SECRET', CRON_SECRET)
        two_expired_tenants()
        add_old_logins(1)

        response = client.post('/api/admin/execute-gdpr-tasks', headers={'X-Cron-Secret': CRON_SECRET})

        assert response.status_code == 200
        body = response.get_json()
        assert body['results']['purged_tenants'] == 0 and body['results']['cleaned_login_history'] == 1
        assert body['held_back'] == {'tenants': {'waiting': 2, 'limit': 1, 'reason': 'over_limit'}}
        assert body['status'] == 'held_back'
        assert Tenant.query.filter(Tenant.domain.in_(['first.example', 'second.example'])).count() == 2

    def test_cron_cannot_release_a_held_back_category(self, client, monkeypatch):
        monkeypatch.setenv('GDPR_CRON_SECRET', CRON_SECRET)
        two_expired_tenants()
        response = client.post(
            '/api/admin/execute-gdpr-tasks', headers={'X-Cron-Secret': CRON_SECRET},
            json={'categories': ['tenants'], 'confirm_counts': {'tenants': 2}, 'release': {'tenants': 2}})
        assert response.status_code == 200
        assert response.get_json()['held_back']['tenants']['waiting'] == 2
        assert Tenant.query.filter(Tenant.domain.in_(['first.example', 'second.example'])).count() == 2

    def test_categories_can_be_chosen_and_are_validated(self, master_client):
        add_old_logins(1)
        bad = master_client.post('/api/admin/execute-gdpr-tasks', json={'categories': ['logins']})
        assert bad.status_code == 400 and 'error' in bad.get_json()
        assert master_client.post('/api/admin/execute-gdpr-tasks', json={'categories': 'all'}).status_code == 400
        assert RetentionRun.query.count() == 0

        chosen = master_client.post('/api/admin/execute-gdpr-tasks', json={'categories': ['inquiries']})
        assert chosen.status_code == 200
        assert chosen.get_json()['results']['cleaned_login_history'] == 0
        assert db.session.get(RetentionRun, chosen.get_json()['run_id']).categories == ['inquiries']


# ==================== Super admin page ====================

class TestStatusAndRun:
    def test_status_shows_settings_preview_held_back_and_runs_without_changing_anything(self, master_client):
        two_expired_tenants()
        add_old_logins(3)
        retention.run_retention(RetentionRun.TRIGGER_CRON, categories=['inquiries'])

        response = master_client.get('/api/superadmin/retention')

        assert response.status_code == 200
        body = response.get_json()
        assert body['categories'] == list(retention.CATEGORIES)
        assert body['automatic'] == {'active': True, 'disabled_by': None, 'last_run': None}
        assert body['settings']['limits'] == {'accounts': 10, 'decisions': 50, 'tenants': 1}
        assert body['preview']['tenants']['waiting'] == 2 and body['preview']['tenants']['would_hold'] is True
        assert [item['label'] for item in body['preview']['tenants']['items']] == ['first.example', 'second.example']
        assert body['preview']['login_history']['waiting'] == 3
        assert body['held_back'] == ['tenants']
        assert body['run_in_progress'] is None
        assert len(body['runs']) == 1 and body['runs'][0]['trigger'] == 'cron'
        assert LoginHistory.query.filter(LoginHistory.email.like('old%')).count() == 3
        assert RetentionRun.query.count() == 1

    def test_status_says_why_the_automatic_run_is_off(self, master_client, monkeypatch):
        retention.save_settings({'auto_run_enabled': False})
        automatic = master_client.get('/api/superadmin/retention').get_json()['automatic']
        assert automatic['active'] is False and automatic['disabled_by'] == 'setting'
        monkeypatch.setenv('RETENTION_AUTO_RUN', 'false')
        automatic = master_client.get('/api/superadmin/retention').get_json()['automatic']
        assert automatic['active'] is False and automatic['disabled_by'] == 'environment'

    def test_status_shows_the_last_automatic_run(self, master_client):
        retention.run_automatic_if_due()
        automatic = master_client.get('/api/superadmin/retention').get_json()['automatic']
        assert automatic['last_run']['trigger'] == 'automatic' and automatic['last_run']['status'] == 'completed'

    def test_super_admin_releases_a_held_back_category(self, master_client):
        two_expired_tenants()

        response = master_client.post('/api/superadmin/retention/run', json={
            'categories': ['tenants'], 'confirm_counts': {'tenants': 2}})

        assert response.status_code == 200, response.get_json()
        body = response.get_json()
        assert body['message'] == 'Retention run finished'
        assert body['run']['results']['tenants']['affected'] == 2
        assert body['run']['trigger'] == 'super_admin' and body['run']['started_by'] == DEFAULT_MASTER_USERNAME
        assert body['run']['categories'] == ['tenants']
        assert Tenant.query.filter(Tenant.domain.in_(['first.example', 'second.example'])).count() == 0
        assert RetentionErasure.query.filter_by(category='tenants').count() == 2

    def test_run_is_refused_when_more_are_waiting_than_confirmed(self, master_client):
        two_expired_tenants()
        response = master_client.post('/api/superadmin/retention/run', json={
            'categories': ['tenants'], 'confirm_counts': {'tenants': 1}})
        assert response.status_code == 409
        body = response.get_json()
        assert body['waiting'] == {'tenants': 2} and 'error' in body
        assert Tenant.query.filter(Tenant.domain.in_(['first.example', 'second.example'])).count() == 2
        assert RetentionRun.query.count() == 0

    @pytest.mark.parametrize('body', [
        {},
        {'categories': []},
        {'categories': ['tenants']},
        {'categories': ['tenants'], 'confirm_counts': {'accounts': 1}},
        {'categories': ['tenants'], 'confirm_counts': {'tenants': 'two'}},
        {'categories': ['everything'], 'confirm_counts': {'everything': 1}},
        {'categories': 'tenants', 'confirm_counts': {'tenants': 2}},
    ])
    def test_run_needs_categories_and_counts(self, master_client, body):
        two_expired_tenants()
        response = master_client.post('/api/superadmin/retention/run', json=body)
        assert response.status_code == 400
        assert 'error' in response.get_json()
        assert Tenant.query.filter(Tenant.domain.in_(['first.example', 'second.example'])).count() == 2
        assert RetentionRun.query.count() == 0

    def test_run_is_refused_while_another_run_is_going(self, master_client):
        add_old_logins(1)
        db.session.add(RetentionRun(trigger='automatic', status='running', started_at=naive_now()))
        db.session.commit()
        response = master_client.post('/api/superadmin/retention/run', json={
            'categories': ['login_history'], 'confirm_counts': {'login_history': 1}})
        assert response.status_code == 409
        assert response.get_json() == {'error': 'A retention run is in progress. Try again when it has finished.'}
        assert LoginHistory.query.filter(LoginHistory.email.like('old%')).count() == 1


# ==================== Settings ====================

class TestSettings:
    def test_get_returns_values_and_defaults(self, master_client):
        body = master_client.get('/api/admin/settings/retention').get_json()
        assert body['auto_run_enabled'] is True and body['auto_run_active'] is True
        assert body['auto_run_disabled_by_environment'] is False
        assert body['limits'] == {'accounts': 10, 'decisions': 50, 'tenants': 1}
        assert body['backlog_days'] == 7
        assert body['defaults'] == {'auto_run_enabled': True, 'backlog_days': 7,
                                    'limits': {'accounts': 10, 'decisions': 50, 'tenants': 1}}

    def test_save_stores_in_system_config(self, master_client):
        response = master_client.put('/api/admin/settings/retention', json={
            'auto_run_enabled': False, 'limits': {'accounts': 3, 'tenants': 0}, 'backlog_days': 30})
        assert response.status_code == 200
        body = response.get_json()
        assert body['message'] == 'Retention settings saved'
        assert body['auto_run_enabled'] is False and body['backlog_days'] == 30
        assert body['limits'] == {'accounts': 3, 'decisions': 50, 'tenants': 0}
        assert SystemConfig.get(SystemConfig.KEY_RETENTION_AUTO_RUN_ENABLED) == 'false'
        assert SystemConfig.get(SystemConfig.KEY_RETENTION_LIMIT_ACCOUNTS) == '3'

    @pytest.mark.parametrize('body', [
        {'auto_run_enabled': 'yes'},
        {'limits': {'tenants': -1}},
        {'limits': {'tenants': 100001}},
        {'limits': {'login_history': 5}},
        {'limits': 'none'},
        {'backlog_days': 'week'},
    ])
    def test_invalid_values_are_refused_and_nothing_is_saved(self, master_client, body):
        response = master_client.put('/api/admin/settings/retention', json=body)
        assert response.status_code == 400
        assert 'error' in response.get_json()
        assert retention.get_settings()['limits'] == {'accounts': 10, 'decisions': 50, 'tenants': 1}
        assert retention.get_settings()['auto_run_enabled'] is True

    def test_body_must_be_an_object(self, master_client):
        response = master_client.put('/api/admin/settings/retention', json=['auto_run_enabled'])
        assert response.status_code == 400 and 'error' in response.get_json()


# ==================== The thread and the request path ====================

class TestRequestHook:
    def test_requests_do_not_start_the_thread_under_tests(self, client):
        assert client.get('/api/health').status_code == 200
        assert retention._scheduler_thread is None

    def test_every_request_asks_for_the_thread_once_the_database_is_ready(self, app_module_and_app, monkeypatch):
        app_module, test_app = app_module_and_app
        asked = []
        monkeypatch.setattr(retention, 'ensure_scheduler', lambda flask_app: asked.append(flask_app))
        assert test_app.test_client().get('/api/health').status_code == 200
        assert asked == [test_app]

    def test_a_request_succeeds_even_if_the_thread_cannot_start(self, app_module_and_app, monkeypatch):
        _, test_app = app_module_and_app

        def broken(flask_app):
            raise RuntimeError("can't start new thread")

        monkeypatch.setattr(retention, 'ensure_scheduler', broken)
        assert test_app.test_client().get('/api/health').status_code == 200


# ==================== Restoring a tenant before it is erased ====================

class TestRestoreBeforeErase:
    """Restore is the only way back before the 30 days are over, so it has to work."""

    def test_soft_deleted_tenant_can_be_restored_and_is_then_left_alone(self, master_client):
        data = make_full_tenant('undo.example', 'und')
        tenant_id = data['tenant'].id

        deleted = master_client.delete('/api/tenants/undo.example', json={'confirm_delete': True})
        assert deleted.status_code == 200, deleted.get_json()
        assert db.session.get(Tenant, tenant_id).status == 'deleted'

        restored = master_client.post('/api/tenants/undo.example/restore')

        assert restored.status_code == 200, restored.get_json()
        assert restored.get_json()['restored']['decisions_restored'] == 2
        db.session.expire_all()
        tenant = db.session.get(Tenant, tenant_id)
        assert tenant.status == 'active' and tenant.deleted_at is None and tenant.deletion_expires_at is None

        # Even a run far in the future finds nothing to erase
        run = retention.run_retention(
            RetentionRun.TRIGGER_AUTOMATIC, categories=['tenants', 'decisions'],
            now=naive_now() + timedelta(days=400))
        assert run['results']['tenants']['waiting'] == 0 and run['results']['decisions']['waiting'] == 0
        assert db.session.get(Tenant, tenant_id) is not None

    def test_restore_is_refused_once_the_window_is_over(self, master_client):
        data = make_full_tenant('late.example', 'lat')
        expire_tenant(data['tenant'])
        response = master_client.post('/api/tenants/late.example/restore')
        assert response.status_code == 400
        assert response.get_json()['error'] == 'Retention window has expired'

    def test_soft_delete_sets_what_retention_looks_for(self, master_client):
        data = make_full_tenant('closing.example', 'clo')
        master_client.delete('/api/tenants/closing.example', json={'confirm_delete': True})
        db.session.expire_all()
        tenant = db.session.get(Tenant, data['tenant'].id)
        assert tenant.status == 'deleted' and tenant.deleted_at is not None

        assert retention.preview_retention(now=naive_now() + timedelta(days=29))['tenants']['waiting'] == 0
        due = retention.preview_retention(now=naive_now() + timedelta(days=30, minutes=1))['tenants']
        assert due['waiting'] == 1 and due['items'][0]['label'] == 'closing.example'


# ==================== Test-only seeding endpoint (used by the e2e specs) ====================

class TestBacklogSeedEndpoint:
    def test_not_available_outside_testing(self, client, monkeypatch):
        monkeypatch.setenv('FLASK_ENV', 'production')
        response = client.post('/api/test/retention-backlog', json={'tenants': 2})
        assert response.status_code == 403
        assert response.get_json() == {'error': 'Not available'}
        assert Tenant.query.count() == 0

    def test_creates_tenants_and_logins_that_are_due(self, client):
        response = client.post('/api/test/retention-backlog', json={'tenants': 2, 'old_logins': 3, 'prefix': 'seed'})
        assert response.status_code == 200
        body = response.get_json()
        assert len(body['tenants']) == 2 and all(domain.startswith('seed-') for domain in body['tenants'])

        preview = retention.preview_retention()
        assert preview['tenants']['waiting'] == 2 and preview['tenants']['hold_reason'] == 'over_limit'
        assert preview['tenants']['items'][0]['counts'] == {
            'users': 1, 'decisions': 1, 'spaces': 0, 'memberships': 1}
        assert preview['login_history']['waiting'] == 3
        assert preview['decisions']['waiting'] == 0

    def test_rejects_values_that_are_not_numbers(self, client):
        response = client.post('/api/test/retention-backlog', json={'tenants': 'many'})
        assert response.status_code == 400 and 'error' in response.get_json()
