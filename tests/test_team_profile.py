"""
Team profile: two optional answers a tenant admin gives about the team
("What does your team make decisions about?" and team size), stored on the
tenant, editable in organisation settings and visible to the super admin.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    db, User, Tenant, TenantMembership, GlobalRole, MaturityState, AuditLog,
    DEFAULT_MASTER_PASSWORD, DEFAULT_MASTER_USERNAME, TEAM_SIZE_CODES, TEAM_SIZE_OPTIONS,
)
from tests.app_test_utils import load_test_app


PASSWORD = 'testpassword123'
URL = '/api/tenant/team-profile'


@pytest.fixture
def api_app():
    app_module, test_app = load_test_app(secret_key='test-secret-key-team-profile-12345')
    with test_app.app_context():
        db.create_all()
        app_module.init_database()
        yield test_app
        db.session.remove()
        db.drop_all()
        app_module._db_initialized = False


def make_tenant(domain, name):
    tenant = Tenant(domain=domain, name=name, status='active', maturity_state=MaturityState.BOOTSTRAP)
    db.session.add(tenant)
    db.session.commit()
    return tenant


def make_user(tenant, email, role, first_name='Test', last_name='Person'):
    user = User(email=email, sso_domain=tenant.domain, auth_type='local', email_verified=True)
    user.set_name(first_name=first_name, last_name=last_name)
    user.set_password(PASSWORD)
    user.is_admin = role != GlobalRole.USER
    db.session.add(user)
    db.session.flush()
    db.session.add(TenantMembership(user_id=user.id, tenant_id=tenant.id, global_role=role))
    db.session.commit()
    return user


def login(api_app, user):
    client = api_app.test_client()
    response = client.post('/api/auth/login', json={'email': user.email, 'password': PASSWORD})
    assert response.status_code == 200, response.data
    token = response.headers.get('X-CSRF-Token') or client.get('/api/auth/csrf-token').get_json()['csrf_token']
    client.environ_base['HTTP_X_CSRF_TOKEN'] = token
    return client


def login_master(api_app):
    client = api_app.test_client()
    response = client.post('/auth/local', json={
        'username': DEFAULT_MASTER_USERNAME, 'password': DEFAULT_MASTER_PASSWORD,
    })
    assert response.status_code == 200, response.data
    token = response.headers.get('X-CSRF-Token') or client.get('/api/auth/csrf-token').get_json()['csrf_token']
    client.environ_base['HTTP_X_CSRF_TOKEN'] = token
    return client


@pytest.fixture
def acme(api_app):
    return make_tenant('acme.test', 'Acme')


@pytest.fixture
def admin(api_app, acme):
    return make_user(acme, 'admin@acme.test', GlobalRole.ADMIN, first_name='Grace', last_name='Hopper')


@pytest.fixture
def admin_client(api_app, admin):
    return login(api_app, admin)


def reload(tenant):
    db.session.expire_all()
    return db.session.get(Tenant, tenant.id)


class TestAuthorisation:

    @pytest.mark.parametrize('method', ['get', 'put'])
    def test_anonymous_is_refused(self, api_app, acme, method):
        response = getattr(api_app.test_client(), method)(URL, json={'team_size': '1-5'})

        assert response.status_code == 401
        assert response.get_json() == {'error': 'Authentication required'}
        assert reload(acme).team_size is None

    @pytest.mark.parametrize('method', ['get', 'put'])
    def test_ordinary_user_is_refused(self, api_app, acme, method):
        client = login(api_app, make_user(acme, 'member@acme.test', GlobalRole.USER))

        response = getattr(client, method)(URL, json={'team_size': '1-5'})

        assert response.status_code == 403
        assert response.get_json() == {'error': 'Permission denied. Admin or Steward role required.'}
        assert reload(acme).team_size is None

    @pytest.mark.parametrize('role', [GlobalRole.ADMIN, GlobalRole.STEWARD, GlobalRole.PROVISIONAL_ADMIN])
    def test_admin_level_roles_may_read_and_save(self, api_app, acme, role):
        client = login(api_app, make_user(acme, 'lead@acme.test', role))

        assert client.get(URL).status_code == 200
        response = client.put(URL, json={'team_size': '6-25'})

        assert response.status_code == 200
        assert reload(acme).team_size == '6-25'

    @pytest.mark.parametrize('method', ['get', 'put'])
    def test_super_admin_is_refused(self, api_app, acme, method):
        client = login_master(api_app)

        response = getattr(client, method)(URL, json={'team_size': '1-5'})

        assert response.status_code == 403
        assert response.get_json() == {'error': 'Super admin accounts cannot access a team profile'}
        assert reload(acme).team_size is None

    def test_save_needs_a_csrf_token(self, admin_client, acme):
        response = admin_client.put(URL, json={'team_size': '1-5'}, environ_overrides={'HTTP_X_CSRF_TOKEN': ''})

        assert response.status_code == 403
        assert reload(acme).team_size is None


class TestReadAndSave:

    def test_unanswered_profile(self, admin_client):
        body = admin_client.get(URL).get_json()

        assert body['team_focus'] is None
        assert body['team_size'] is None
        assert body['team_size_label'] is None
        assert body['answered_at'] is None
        assert body['answered_by'] is None
        assert body['team_focus_max_length'] == 200
        assert body['team_size_options'] == [
            {'code': code, 'label': label} for code, label in TEAM_SIZE_OPTIONS
        ]

    def test_save_both_answers(self, admin_client, acme, admin):
        response = admin_client.put(URL, json={'team_focus': '  Hiring and pay reviews ', 'team_size': '26-100'})

        assert response.status_code == 200
        body = response.get_json()
        assert body['message'] == 'Team profile saved'
        assert body['team_focus'] == 'Hiring and pay reviews'
        assert body['team_size'] == '26-100'
        assert body['team_size_label'] == '26 to 100 people'
        assert body['answered_at'] is not None
        assert body['answered_by'] == 'Grace Hopper'

        tenant = reload(acme)
        assert tenant.team_focus == 'Hiring and pay reviews'
        assert tenant.team_size == '26-100'
        assert tenant.team_profile_answered_at is not None
        assert tenant.team_profile_answered_by_id == admin.id

        assert admin_client.get(URL).get_json()['team_focus'] == 'Hiring and pay reviews'

    @pytest.mark.parametrize('code', TEAM_SIZE_CODES)
    def test_every_listed_size_is_accepted(self, admin_client, acme, code):
        assert admin_client.put(URL, json={'team_size': code}).status_code == 200
        assert reload(acme).team_size == code

    def test_a_field_left_out_keeps_its_value(self, admin_client, acme):
        admin_client.put(URL, json={'team_focus': 'Hiring', 'team_size': '1-5'})

        admin_client.put(URL, json={'team_size': '6-25'})

        tenant = reload(acme)
        assert tenant.team_focus == 'Hiring'
        assert tenant.team_size == '6-25'

    @pytest.mark.parametrize('empty', [None, '', '   '])
    def test_null_or_blank_clears_an_answer(self, admin_client, acme, empty):
        admin_client.put(URL, json={'team_focus': 'Hiring', 'team_size': '1-5'})

        response = admin_client.put(URL, json={'team_focus': empty})

        assert response.status_code == 200
        tenant = reload(acme)
        assert tenant.team_focus is None
        assert tenant.team_size == '1-5'
        assert tenant.team_profile_answered_at is not None

    def test_clearing_both_answers_clears_who_and_when(self, admin_client, acme):
        admin_client.put(URL, json={'team_focus': 'Hiring', 'team_size': '1-5'})

        admin_client.put(URL, json={'team_focus': None, 'team_size': None})

        tenant = reload(acme)
        assert tenant.team_focus is None and tenant.team_size is None
        assert tenant.team_profile_answered_at is None
        assert tenant.team_profile_answered_by_id is None

    def test_empty_object_changes_nothing(self, admin_client, acme):
        admin_client.put(URL, json={'team_focus': 'Hiring', 'team_size': '1-5'})
        answered_at = reload(acme).team_profile_answered_at

        response = admin_client.put(URL, json={})

        assert response.status_code == 200
        tenant = reload(acme)
        assert tenant.team_focus == 'Hiring' and tenant.team_size == '1-5'
        assert tenant.team_profile_answered_at == answered_at

    def test_saving_the_same_values_does_not_change_who_answered(self, api_app, acme, admin, admin_client):
        admin_client.put(URL, json={'team_focus': 'Hiring'})
        steward_client = login(api_app, make_user(acme, 'steward@acme.test', GlobalRole.STEWARD))

        steward_client.put(URL, json={'team_focus': 'Hiring'})

        assert reload(acme).team_profile_answered_by_id == admin.id

    def test_markup_is_stripped_and_ampersand_kept(self, admin_client, acme):
        admin_client.put(URL, json={'team_focus': 'R&D <script>alert(1)</script>budgets'})

        team_focus = reload(acme).team_focus
        assert '<' not in team_focus and '>' not in team_focus
        assert team_focus.startswith('R&D ')

    def test_change_is_written_to_the_audit_log_without_the_free_text(self, admin_client, acme, admin):
        admin_client.put(URL, json={'team_focus': 'Hiring', 'team_size': '1-5'})

        entry = AuditLog.query.filter_by(action_type='update_team_profile').one()
        assert entry.tenant_id == acme.id
        assert entry.actor_user_id == admin.id
        assert entry.details == {'team_size': '1-5', 'has_team_focus': True}


class TestValidation:

    def test_team_focus_longer_than_200_characters_is_rejected(self, admin_client, acme):
        response = admin_client.put(URL, json={'team_focus': 'F' * 201})

        assert response.status_code == 400
        assert response.get_json() == {'error': 'Team focus must be 200 characters or fewer'}
        assert reload(acme).team_focus is None

    def test_team_focus_of_exactly_200_characters_is_accepted(self, admin_client, acme):
        response = admin_client.put(URL, json={'team_focus': 'F' * 200})

        assert response.status_code == 200
        assert reload(acme).team_focus == 'F' * 200

    @pytest.mark.parametrize('bad', [42, True, ['Hiring'], {'text': 'Hiring'}])
    def test_team_focus_of_the_wrong_type_is_rejected(self, admin_client, acme, bad):
        response = admin_client.put(URL, json={'team_focus': bad})

        assert response.status_code == 400
        assert response.get_json() == {'error': 'Team focus must be text'}
        assert reload(acme).team_focus is None

    @pytest.mark.parametrize('bad', ['huge', '1-10', '6 to 25 people', 25, ['6-25'], {'code': '6-25'}])
    def test_unknown_team_size_is_rejected(self, admin_client, acme, bad):
        response = admin_client.put(URL, json={'team_size': bad})

        assert response.status_code == 400
        assert response.get_json() == {'error': 'Team size is not one of the listed ranges'}
        assert reload(acme).team_size is None

    def test_one_invalid_field_saves_nothing(self, admin_client, acme):
        response = admin_client.put(URL, json={'team_focus': 'Hiring', 'team_size': 'huge'})

        assert response.status_code == 400
        tenant = reload(acme)
        assert tenant.team_focus is None and tenant.team_size is None

    @pytest.mark.parametrize('body', [None, [], ['team_size'], 'text', 5])
    def test_missing_or_non_object_body_is_rejected(self, admin_client, body):
        response = admin_client.put(URL, json=body)

        assert response.status_code == 400
        assert response.get_json() == {'error': 'No data provided'}


class TestTenantIsolation:

    def test_an_admin_only_reads_and_changes_their_own_tenant(self, api_app, acme, admin_client):
        globex = make_tenant('globex.test', 'Globex')
        globex_client = login(api_app, make_user(globex, 'admin@globex.test', GlobalRole.ADMIN))
        globex_client.put(URL, json={'team_focus': 'Supplier choices', 'team_size': '501+'})

        assert admin_client.get(URL).get_json()['team_focus'] is None
        admin_client.put(URL, json={'team_focus': 'Hiring', 'team_size': '1-5'})

        assert reload(globex).team_focus == 'Supplier choices'
        assert reload(globex).team_size == '501+'
        assert reload(acme).team_focus == 'Hiring'
        assert globex_client.get(URL).get_json()['team_focus'] == 'Supplier choices'

    def test_the_tenant_cannot_be_chosen_by_the_caller(self, api_app, acme, admin_client):
        globex = make_tenant('globex.test', 'Globex')

        response = admin_client.put(
            f'{URL}?domain=globex.test&tenant_id={globex.id}',
            json={'team_size': '1-5', 'domain': 'globex.test', 'tenant_id': globex.id},
        )

        assert response.status_code == 200
        assert reload(globex).team_size is None
        assert reload(acme).team_size == '1-5'


class TestWhereTheAnswersAppear:

    def test_user_me_says_whether_the_team_has_answered(self, admin_client):
        assert admin_client.get('/api/user/me').get_json()['tenant_info']['team_profile_answered'] is False

        admin_client.put(URL, json={'team_size': '1-5'})

        assert admin_client.get('/api/user/me').get_json()['tenant_info']['team_profile_answered'] is True

    def test_super_admin_tenant_list_includes_the_answers(self, api_app, acme, admin, admin_client):
        admin_client.put(URL, json={'team_focus': 'Hiring', 'team_size': '6-25'})
        make_user(make_tenant('quiet.test', 'Quiet'), 'someone@quiet.test', GlobalRole.ADMIN)

        rows = {row['domain']: row for row in login_master(api_app).get('/api/tenants').get_json()}

        assert rows['acme.test']['team_focus'] == 'Hiring'
        assert rows['acme.test']['team_size'] == '6-25'
        assert rows['acme.test']['team_size_label'] == '6 to 25 people'
        assert rows['acme.test']['team_profile_answered_at'] is not None
        assert rows['quiet.test']['team_focus'] is None
        assert rows['quiet.test']['team_size'] is None
        assert rows['quiet.test']['team_profile_answered_at'] is None

    def test_tenant_list_stays_super_admin_only(self, admin_client):
        assert admin_client.get('/api/tenants').status_code == 403

    def test_dismissing_onboarding_does_not_need_an_answer(self, admin_client, acme):
        response = admin_client.post('/api/user/dismiss-admin-onboarding', json={})

        assert response.status_code == 200
        assert reload(acme).team_focus is None
