"""
Tests for External AI API routes.

Tests cover:
1. require_ai_api_key decorator - authentication and authorization
2. Search endpoint /api/ai/search
3. List endpoint /api/ai/decisions (GET)
4. Get decision endpoint /api/ai/decisions/<id> (GET)
5. Create decision endpoint /api/ai/decisions (POST)
6. Get history endpoint /api/ai/decisions/<id>/history (GET)
7. OpenAPI schema endpoint /api/ai/openapi.json (GET)
"""
import pytest
import json
import os
import sys
from datetime import datetime, timedelta, timezone

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    db, User, Tenant, TenantMembership, SystemConfig, GlobalRole, MaturityState,
    AIApiKey, ArchitectureDecision, DecisionHistory
)
from ai import AIConfig, AIApiKeyService


def _ensure_testing_env():
    """Ensure testing environment is set before app import."""
    if os.environ.get('FLASK_ENV') != 'testing':
        os.environ['FLASK_ENV'] = 'testing'
        os.environ['TESTING'] = 'True'


# Set testing environment at module load time
_ensure_testing_env()


# ============================================================================
# require_ai_api_key DECORATOR TESTS
# ============================================================================

class TestRequireAiApiKeyDecorator:
    """Test the require_ai_api_key decorator for authentication and authorization."""

    @pytest.fixture
    def api_app(self):
        """Create app with AI API blueprint."""
        _ensure_testing_env()
        import app as flask_app
        flask_app.app.config['TESTING'] = True
        flask_app.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        flask_app.app.config['WTF_CSRF_ENABLED'] = False

        with flask_app.app.app_context():
            db.create_all()
            yield flask_app.app
            db.drop_all()

    @pytest.fixture
    def client(self, api_app):
        """Create test client."""
        return api_app.test_client()

    @pytest.fixture
    def enable_external_api(self, api_app):
        """Enable AI and External API at system level."""
        with api_app.app_context():
            SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
            SystemConfig.set(SystemConfig.KEY_AI_EXTERNAL_API_ENABLED, 'true')
            db.session.commit()

    @pytest.fixture
    def ai_tenant(self, api_app, enable_external_api):
        """Create a tenant with AI features enabled."""
        with api_app.app_context():
            tenant = Tenant(
                domain='aitest.com',
                name='AI Test Corp',
                status='active',
                maturity_state=MaturityState.BOOTSTRAP,
                ai_features_enabled=True,
                ai_external_access_enabled=True,
                ai_log_interactions=False
            )
            db.session.add(tenant)
            db.session.commit()
            return tenant.id

    @pytest.fixture
    def api_user_and_key(self, api_app, ai_tenant):
        """Create a user with API key having all scopes."""
        with api_app.app_context():
            tenant = Tenant.query.get(ai_tenant)
            user = User(
                email='apiuser@aitest.com',
                sso_domain='aitest.com',
                auth_type='local',
                email_verified=True
            )
            user.set_name(first_name='API', last_name='User')
            db.session.add(user)
            db.session.flush()

            membership = TenantMembership(
                user_id=user.id,
                tenant_id=tenant.id,
                global_role=GlobalRole.USER
            )
            db.session.add(membership)
            db.session.commit()

            api_key, full_key = AIApiKeyService.create_key(
                user, tenant, 'Test Key',
                scopes=['read', 'search', 'write']
            )
            return user.id, full_key, tenant.id

    def test_missing_authorization_header_returns_401(self, client, enable_external_api):
        """Returns 401 when Authorization header is missing."""
        response = client.get('/api/ai/decisions')
        assert response.status_code == 401
        data = response.get_json()
        assert 'error' in data
        assert 'Authorization' in data['error'] or 'Missing' in data['error']

    def test_invalid_authorization_format_returns_401(self, client, enable_external_api):
        """Returns 401 when Authorization header format is wrong."""
        response = client.get(
            '/api/ai/decisions',
            headers={'Authorization': 'Basic abc123'}
        )
        assert response.status_code == 401
        data = response.get_json()
        assert 'error' in data

    def test_invalid_api_key_returns_401(self, client, enable_external_api):
        """Returns 401 when API key is invalid."""
        response = client.get(
            '/api/ai/decisions',
            headers={'Authorization': 'Bearer adr_invalid_key_12345678'}
        )
        assert response.status_code == 401
        data = response.get_json()
        assert 'error' in data
        assert 'Invalid' in data['error'] or 'expired' in data['error']

    def test_ai_features_disabled_returns_503(self, client, api_app):
        """Returns 503 when AI features are disabled at system level."""
        with api_app.app_context():
            SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'false')
            db.session.commit()

        response = client.get(
            '/api/ai/decisions',
            headers={'Authorization': 'Bearer adr_test_key'}
        )
        assert response.status_code == 503
        data = response.get_json()
        assert 'error' in data
        assert 'AI features are not enabled' in data['error']

    def test_external_api_disabled_returns_503(self, client, api_app):
        """Returns 503 when External API is disabled at system level."""
        with api_app.app_context():
            SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
            SystemConfig.set(SystemConfig.KEY_AI_EXTERNAL_API_ENABLED, 'false')
            db.session.commit()

        response = client.get(
            '/api/ai/decisions',
            headers={'Authorization': 'Bearer adr_test_key'}
        )
        assert response.status_code == 503
        data = response.get_json()
        assert 'error' in data
        assert 'External AI API is not enabled' in data['error']

    def test_tenant_ai_disabled_returns_403(self, client, api_app, enable_external_api):
        """Returns 403 when tenant AI is disabled."""
        with api_app.app_context():
            # Create tenant without AI enabled
            tenant = Tenant(
                domain='noai.com',
                name='No AI Corp',
                status='active',
                maturity_state=MaturityState.BOOTSTRAP,
                ai_features_enabled=False,
                ai_external_access_enabled=False
            )
            db.session.add(tenant)
            db.session.flush()

            user = User(
                email='user@noai.com',
                sso_domain='noai.com',
                auth_type='local',
                email_verified=True
            )
            user.set_name(first_name='No', last_name='AI')
            db.session.add(user)
            db.session.flush()

            membership = TenantMembership(
                user_id=user.id,
                tenant_id=tenant.id,
                global_role=GlobalRole.USER
            )
            db.session.add(membership)
            db.session.commit()

            api_key, full_key = AIApiKeyService.create_key(
                user, tenant, 'Test Key',
                scopes=['read', 'search']
            )

        response = client.get(
            '/api/ai/decisions',
            headers={'Authorization': f'Bearer {full_key}'}
        )
        assert response.status_code == 403
        data = response.get_json()
        assert 'error' in data
        assert 'AI features are not enabled for this organization' in data['error']

    def test_tenant_external_access_disabled_returns_403(self, client, api_app, enable_external_api):
        """Returns 403 when tenant external access is disabled."""
        with api_app.app_context():
            # Create tenant with AI but no external access
            tenant = Tenant(
                domain='noexternal.com',
                name='No External Corp',
                status='active',
                maturity_state=MaturityState.BOOTSTRAP,
                ai_features_enabled=True,
                ai_external_access_enabled=False
            )
            db.session.add(tenant)
            db.session.flush()

            user = User(
                email='user@noexternal.com',
                sso_domain='noexternal.com',
                auth_type='local',
                email_verified=True
            )
            user.set_name(first_name='No', last_name='External')
            db.session.add(user)
            db.session.flush()

            membership = TenantMembership(
                user_id=user.id,
                tenant_id=tenant.id,
                global_role=GlobalRole.USER
            )
            db.session.add(membership)
            db.session.commit()

            api_key, full_key = AIApiKeyService.create_key(
                user, tenant, 'Test Key',
                scopes=['read', 'search']
            )

        response = client.get(
            '/api/ai/decisions',
            headers={'Authorization': f'Bearer {full_key}'}
        )
        assert response.status_code == 403
        data = response.get_json()
        assert 'error' in data
        assert 'External AI access is not enabled' in data['error']

    def test_user_opted_out_returns_403(self, client, api_app, enable_external_api):
        """Returns 403 when user has opted out of AI features."""
        with api_app.app_context():
            tenant = Tenant(
                domain='optedout.com',
                name='Opted Out Corp',
                status='active',
                maturity_state=MaturityState.BOOTSTRAP,
                ai_features_enabled=True,
                ai_external_access_enabled=True
            )
            db.session.add(tenant)
            db.session.flush()

            user = User(
                email='user@optedout.com',
                sso_domain='optedout.com',
                auth_type='local',
                email_verified=True
            )
            user.set_name(first_name='Opted', last_name='Out')
            db.session.add(user)
            db.session.flush()

            membership = TenantMembership(
                user_id=user.id,
                tenant_id=tenant.id,
                global_role=GlobalRole.USER,
                ai_opt_out=True  # User opted out
            )
            db.session.add(membership)
            db.session.commit()

            api_key, full_key = AIApiKeyService.create_key(
                user, tenant, 'Test Key',
                scopes=['read', 'search']
            )

        response = client.get(
            '/api/ai/decisions',
            headers={'Authorization': f'Bearer {full_key}'}
        )
        assert response.status_code == 403
        data = response.get_json()
        assert 'error' in data
        assert 'opted out' in data['error']

    def test_missing_required_scope_returns_403(self, client, api_app, enable_external_api, ai_tenant):
        """Returns 403 when API key lacks required scope."""
        with api_app.app_context():
            tenant = Tenant.query.get(ai_tenant)
            user = User(
                email='readonly@aitest.com',
                sso_domain='aitest.com',
                auth_type='local',
                email_verified=True
            )
            user.set_name(first_name='Read', last_name='Only')
            db.session.add(user)
            db.session.flush()

            membership = TenantMembership(
                user_id=user.id,
                tenant_id=tenant.id,
                global_role=GlobalRole.USER
            )
            db.session.add(membership)
            db.session.commit()

            # Create key with only read scope (no search scope for search endpoint)
            api_key, full_key = AIApiKeyService.create_key(
                user, tenant, 'Read Only Key',
                scopes=['read']  # Missing 'search' scope
            )

        # Search endpoint requires 'search' scope
        response = client.post(
            '/api/ai/search',
            json={'query': 'test'},
            headers={'Authorization': f'Bearer {full_key}'}
        )
        assert response.status_code == 403
        data = response.get_json()
        assert 'error' in data
        assert 'scope' in data['error']

    def test_successful_authentication(self, client, api_user_and_key):
        """Returns 200 with valid API key and all required conditions met."""
        user_id, full_key, tenant_id = api_user_and_key
        response = client.get(
            '/api/ai/decisions',
            headers={'Authorization': f'Bearer {full_key}'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert 'decisions' in data


# ============================================================================
# SEARCH ENDPOINT TESTS
# ============================================================================

class TestSearchEndpoint:
    """Test /api/ai/search endpoint."""

    @pytest.fixture
    def api_app(self):
        """Create app with AI API blueprint."""
        _ensure_testing_env()
        import app as flask_app
        flask_app.app.config['TESTING'] = True
        flask_app.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        flask_app.app.config['WTF_CSRF_ENABLED'] = False

        with flask_app.app.app_context():
            db.create_all()
            yield flask_app.app
            db.drop_all()

    @pytest.fixture
    def client(self, api_app):
        """Create test client."""
        return api_app.test_client()

    @pytest.fixture
    def setup_with_decisions(self, api_app):
        """Set up tenant, user, API key, and sample decisions."""
        with api_app.app_context():
            SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
            SystemConfig.set(SystemConfig.KEY_AI_EXTERNAL_API_ENABLED, 'true')
            db.session.commit()

            tenant = Tenant(
                domain='search.com',
                name='Search Corp',
                status='active',
                maturity_state=MaturityState.BOOTSTRAP,
                ai_features_enabled=True,
                ai_external_access_enabled=True,
                ai_log_interactions=False
            )
            db.session.add(tenant)
            db.session.flush()

            user = User(
                email='user@search.com',
                sso_domain='search.com',
                auth_type='local',
                email_verified=True
            )
            user.set_name(first_name='Search', last_name='User')
            db.session.add(user)
            db.session.flush()

            membership = TenantMembership(
                user_id=user.id,
                tenant_id=tenant.id,
                global_role=GlobalRole.USER
            )
            db.session.add(membership)

            # Create sample decisions
            decisions = [
                ArchitectureDecision(
                    title='Use PostgreSQL for persistence',
                    context='We need a reliable database',
                    decision='PostgreSQL is chosen',
                    consequences='Requires DBA skills',
                    status='accepted',
                    domain=tenant.domain,
                    tenant_id=tenant.id,
                    created_by_id=user.id,
                    decision_number=1
                ),
                ArchitectureDecision(
                    title='Use Redis for caching',
                    context='We need fast caching',
                    decision='Redis is chosen',
                    consequences='Requires memory',
                    status='proposed',
                    domain=tenant.domain,
                    tenant_id=tenant.id,
                    created_by_id=user.id,
                    decision_number=2
                ),
                ArchitectureDecision(
                    title='Use Kubernetes for deployment',
                    context='We need container orchestration',
                    decision='Kubernetes is chosen',
                    consequences='Requires DevOps skills',
                    status='accepted',
                    domain=tenant.domain,
                    tenant_id=tenant.id,
                    created_by_id=user.id,
                    decision_number=3
                )
            ]
            for d in decisions:
                db.session.add(d)
            db.session.commit()

            api_key, full_key = AIApiKeyService.create_key(
                user, tenant, 'Search Key',
                scopes=['read', 'search', 'write']
            )
            return full_key

    def test_search_with_query_success(self, client, setup_with_decisions):
        """Successful search with query text."""
        full_key = setup_with_decisions
        response = client.post(
            '/api/ai/search',
            json={'query': 'PostgreSQL'},
            headers={'Authorization': f'Bearer {full_key}'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert 'query' in data
        assert 'count' in data
        assert 'decisions' in data
        assert data['query'] == 'PostgreSQL'
        assert data['count'] >= 1

    def test_search_with_status_filter(self, client, setup_with_decisions):
        """Search with status filter."""
        full_key = setup_with_decisions
        response = client.post(
            '/api/ai/search',
            json={'query': '', 'status': 'proposed'},
            headers={'Authorization': f'Bearer {full_key}'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['count'] >= 0
        for decision in data['decisions']:
            assert decision['status'] == 'proposed'

    def test_search_with_limit(self, client, setup_with_decisions):
        """Search respects limit parameter."""
        full_key = setup_with_decisions
        response = client.post(
            '/api/ai/search',
            json={'query': '', 'limit': 2},
            headers={'Authorization': f'Bearer {full_key}'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert len(data['decisions']) <= 2

    def test_search_invalid_status_returns_400(self, client, setup_with_decisions):
        """Invalid status returns 400."""
        full_key = setup_with_decisions
        response = client.post(
            '/api/ai/search',
            json={'query': 'test', 'status': 'invalid_status'},
            headers={'Authorization': f'Bearer {full_key}'}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'Invalid status' in data['error']


# ============================================================================
# LIST DECISIONS ENDPOINT TESTS
# ============================================================================

class TestListDecisionsEndpoint:
    """Test /api/ai/decisions (GET) endpoint."""

    @pytest.fixture
    def api_app(self):
        """Create app with AI API blueprint."""
        _ensure_testing_env()
        import app as flask_app
        flask_app.app.config['TESTING'] = True
        flask_app.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        flask_app.app.config['WTF_CSRF_ENABLED'] = False

        with flask_app.app.app_context():
            db.create_all()
            yield flask_app.app
            db.drop_all()

    @pytest.fixture
    def client(self, api_app):
        """Create test client."""
        return api_app.test_client()

    @pytest.fixture
    def setup_with_decisions(self, api_app):
        """Set up tenant, user, API key, and sample decisions."""
        with api_app.app_context():
            SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
            SystemConfig.set(SystemConfig.KEY_AI_EXTERNAL_API_ENABLED, 'true')
            db.session.commit()

            tenant = Tenant(
                domain='list.com',
                name='List Corp',
                status='active',
                maturity_state=MaturityState.BOOTSTRAP,
                ai_features_enabled=True,
                ai_external_access_enabled=True,
                ai_log_interactions=False
            )
            db.session.add(tenant)
            db.session.flush()

            user = User(
                email='user@list.com',
                sso_domain='list.com',
                auth_type='local',
                email_verified=True
            )
            user.set_name(first_name='List', last_name='User')
            db.session.add(user)
            db.session.flush()

            membership = TenantMembership(
                user_id=user.id,
                tenant_id=tenant.id,
                global_role=GlobalRole.USER
            )
            db.session.add(membership)

            # Create sample decisions
            for i in range(5):
                decision = ArchitectureDecision(
                    title=f'Decision {i + 1}',
                    context=f'Context for decision {i + 1}',
                    decision=f'Decision text {i + 1}',
                    consequences=f'Consequences {i + 1}',
                    status='accepted' if i % 2 == 0 else 'proposed',
                    domain=tenant.domain,
                    tenant_id=tenant.id,
                    created_by_id=user.id,
                    decision_number=i + 1
                )
                db.session.add(decision)
            db.session.commit()

            api_key, full_key = AIApiKeyService.create_key(
                user, tenant, 'List Key',
                scopes=['read', 'search', 'write']
            )
            return full_key

    def test_list_with_pagination(self, client, setup_with_decisions):
        """List decisions with pagination."""
        full_key = setup_with_decisions
        response = client.get(
            '/api/ai/decisions?limit=2&offset=0',
            headers={'Authorization': f'Bearer {full_key}'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert 'total' in data
        assert 'offset' in data
        assert 'limit' in data
        assert 'count' in data
        assert 'decisions' in data
        assert data['limit'] == 2
        assert data['offset'] == 0
        assert len(data['decisions']) <= 2

    def test_list_with_status_filter(self, client, setup_with_decisions):
        """List decisions with status filter."""
        full_key = setup_with_decisions
        response = client.get(
            '/api/ai/decisions?status=proposed',
            headers={'Authorization': f'Bearer {full_key}'}
        )
        assert response.status_code == 200
        data = response.get_json()
        for decision in data['decisions']:
            assert decision['status'] == 'proposed'

    def test_list_invalid_order_by_returns_400(self, client, setup_with_decisions):
        """Invalid order_by returns 400."""
        full_key = setup_with_decisions
        response = client.get(
            '/api/ai/decisions?order_by=invalid_field',
            headers={'Authorization': f'Bearer {full_key}'}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'Invalid order_by' in data['error']

    def test_list_invalid_order_returns_400(self, client, setup_with_decisions):
        """Invalid order returns 400."""
        full_key = setup_with_decisions
        response = client.get(
            '/api/ai/decisions?order=invalid',
            headers={'Authorization': f'Bearer {full_key}'}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'Invalid order' in data['error']


# ============================================================================
# GET DECISION ENDPOINT TESTS
# ============================================================================

class TestGetDecisionEndpoint:
    """Test /api/ai/decisions/<id> (GET) endpoint."""

    @pytest.fixture
    def api_app(self):
        """Create app with AI API blueprint."""
        _ensure_testing_env()
        import app as flask_app
        flask_app.app.config['TESTING'] = True
        flask_app.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        flask_app.app.config['WTF_CSRF_ENABLED'] = False

        with flask_app.app.app_context():
            db.create_all()
            yield flask_app.app
            db.drop_all()

    @pytest.fixture
    def client(self, api_app):
        """Create test client."""
        return api_app.test_client()

    @pytest.fixture
    def setup_with_decision(self, api_app):
        """Set up tenant, user, API key, and a sample decision."""
        with api_app.app_context():
            SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
            SystemConfig.set(SystemConfig.KEY_AI_EXTERNAL_API_ENABLED, 'true')
            db.session.commit()

            tenant = Tenant(
                domain='getdecision.com',
                name='Get Decision Corp',
                status='active',
                maturity_state=MaturityState.BOOTSTRAP,
                ai_features_enabled=True,
                ai_external_access_enabled=True,
                ai_log_interactions=False
            )
            db.session.add(tenant)
            db.session.flush()

            user = User(
                email='user@getdecision.com',
                sso_domain='getdecision.com',
                auth_type='local',
                email_verified=True
            )
            user.set_name(first_name='Get', last_name='User')
            db.session.add(user)
            db.session.flush()

            membership = TenantMembership(
                user_id=user.id,
                tenant_id=tenant.id,
                global_role=GlobalRole.USER
            )
            db.session.add(membership)

            decision = ArchitectureDecision(
                title='Test Decision for Get',
                context='Test context',
                decision='Test decision text',
                consequences='Test consequences',
                status='accepted',
                domain=tenant.domain,
                tenant_id=tenant.id,
                created_by_id=user.id,
                decision_number=42
            )
            db.session.add(decision)
            db.session.commit()

            api_key, full_key = AIApiKeyService.create_key(
                user, tenant, 'Get Key',
                scopes=['read', 'search']
            )
            return full_key, decision.id

    def test_get_by_numeric_id(self, client, setup_with_decision):
        """Get decision by numeric ID."""
        full_key, decision_id = setup_with_decision
        response = client.get(
            f'/api/ai/decisions/{decision_id}',
            headers={'Authorization': f'Bearer {full_key}'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['id'] == decision_id
        assert data['title'] == 'Test Decision for Get'

    def test_get_by_display_id(self, client, setup_with_decision):
        """Get decision by display ID (ADR-XX)."""
        full_key, decision_id = setup_with_decision
        response = client.get(
            '/api/ai/decisions/ADR-42',
            headers={'Authorization': f'Bearer {full_key}'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['decision_number'] == 42
        assert data['title'] == 'Test Decision for Get'

    def test_get_not_found_returns_404(self, client, setup_with_decision):
        """Not found returns 404."""
        full_key, _ = setup_with_decision
        response = client.get(
            '/api/ai/decisions/99999',
            headers={'Authorization': f'Bearer {full_key}'}
        )
        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data
        assert 'not found' in data['error']


# ============================================================================
# CREATE DECISION ENDPOINT TESTS
# ============================================================================

class TestCreateDecisionEndpoint:
    """Test /api/ai/decisions (POST) endpoint."""

    @pytest.fixture
    def api_app(self):
        """Create app with AI API blueprint."""
        _ensure_testing_env()
        import app as flask_app
        flask_app.app.config['TESTING'] = True
        flask_app.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        flask_app.app.config['WTF_CSRF_ENABLED'] = False

        with flask_app.app.app_context():
            db.create_all()
            yield flask_app.app
            db.drop_all()

    @pytest.fixture
    def client(self, api_app):
        """Create test client."""
        return api_app.test_client()

    @pytest.fixture
    def setup_for_create(self, api_app):
        """Set up tenant, user, and API key for creation tests."""
        with api_app.app_context():
            SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
            SystemConfig.set(SystemConfig.KEY_AI_EXTERNAL_API_ENABLED, 'true')
            db.session.commit()

            tenant = Tenant(
                domain='create.com',
                name='Create Corp',
                status='active',
                maturity_state=MaturityState.BOOTSTRAP,
                ai_features_enabled=True,
                ai_external_access_enabled=True,
                ai_log_interactions=False
            )
            db.session.add(tenant)
            db.session.flush()

            user = User(
                email='user@create.com',
                sso_domain='create.com',
                auth_type='local',
                email_verified=True
            )
            user.set_name(first_name='Create', last_name='User')
            db.session.add(user)
            db.session.flush()

            membership = TenantMembership(
                user_id=user.id,
                tenant_id=tenant.id,
                global_role=GlobalRole.USER
            )
            db.session.add(membership)
            db.session.commit()

            # Write scope key
            write_api_key, write_key = AIApiKeyService.create_key(
                user, tenant, 'Write Key',
                scopes=['read', 'search', 'write']
            )
            # Read-only key
            read_api_key, read_key = AIApiKeyService.create_key(
                user, tenant, 'Read Key',
                scopes=['read', 'search']
            )
            return write_key, read_key

    def test_missing_required_fields_returns_400(self, client, setup_for_create):
        """Missing required fields returns 400."""
        write_key, _ = setup_for_create
        response = client.post(
            '/api/ai/decisions',
            json={'title': 'Only Title'},
            headers={'Authorization': f'Bearer {write_key}'}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'Missing required field' in data['error']

    def test_title_too_long_returns_400(self, client, setup_for_create):
        """Title exceeding max length returns 400."""
        write_key, _ = setup_for_create
        response = client.post(
            '/api/ai/decisions',
            json={
                'title': 'x' * 256,
                'context': 'Test context',
                'decision': 'Test decision',
                'consequences': 'Test consequences'
            },
            headers={'Authorization': f'Bearer {write_key}'}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'exceeds maximum length' in data['error']

    def test_invalid_status_returns_400(self, client, setup_for_create):
        """Invalid status for creation returns 400."""
        write_key, _ = setup_for_create
        response = client.post(
            '/api/ai/decisions',
            json={
                'title': 'Test Title',
                'context': 'Test context',
                'decision': 'Test decision',
                'consequences': 'Test consequences',
                'status': 'archived'  # Not allowed for creation
            },
            headers={'Authorization': f'Bearer {write_key}'}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'Invalid status' in data['error']

    def test_successful_creation_returns_201(self, client, setup_for_create):
        """Successful creation returns 201."""
        write_key, _ = setup_for_create
        response = client.post(
            '/api/ai/decisions',
            json={
                'title': 'New Decision via API',
                'context': 'Created through external AI API',
                'decision': 'We decided to use the API',
                'consequences': 'Easy integration',
                'status': 'proposed'
            },
            headers={'Authorization': f'Bearer {write_key}'}
        )
        assert response.status_code == 201
        data = response.get_json()
        assert 'message' in data
        assert 'decision' in data
        assert data['decision']['title'] == 'New Decision via API'
        assert data['decision']['status'] == 'proposed'

    def test_create_requires_write_scope(self, client, setup_for_create):
        """Create endpoint requires write scope."""
        _, read_key = setup_for_create
        response = client.post(
            '/api/ai/decisions',
            json={
                'title': 'Test Title',
                'context': 'Test context',
                'decision': 'Test decision',
                'consequences': 'Test consequences'
            },
            headers={'Authorization': f'Bearer {read_key}'}
        )
        assert response.status_code == 403
        data = response.get_json()
        assert 'error' in data
        assert 'scope' in data['error']


# ============================================================================
# GET DECISION HISTORY ENDPOINT TESTS
# ============================================================================

class TestGetDecisionHistoryEndpoint:
    """Test /api/ai/decisions/<id>/history (GET) endpoint."""

    @pytest.fixture
    def api_app(self):
        """Create app with AI API blueprint."""
        _ensure_testing_env()
        import app as flask_app
        flask_app.app.config['TESTING'] = True
        flask_app.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        flask_app.app.config['WTF_CSRF_ENABLED'] = False

        with flask_app.app.app_context():
            db.create_all()
            yield flask_app.app
            db.drop_all()

    @pytest.fixture
    def client(self, api_app):
        """Create test client."""
        return api_app.test_client()

    @pytest.fixture
    def setup_with_history(self, api_app):
        """Set up tenant, user, API key, decision with history."""
        with api_app.app_context():
            SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
            SystemConfig.set(SystemConfig.KEY_AI_EXTERNAL_API_ENABLED, 'true')
            db.session.commit()

            tenant = Tenant(
                domain='history.com',
                name='History Corp',
                status='active',
                maturity_state=MaturityState.BOOTSTRAP,
                ai_features_enabled=True,
                ai_external_access_enabled=True,
                ai_log_interactions=False
            )
            db.session.add(tenant)
            db.session.flush()

            user = User(
                email='user@history.com',
                sso_domain='history.com',
                auth_type='local',
                email_verified=True
            )
            user.set_name(first_name='History', last_name='User')
            db.session.add(user)
            db.session.flush()

            membership = TenantMembership(
                user_id=user.id,
                tenant_id=tenant.id,
                global_role=GlobalRole.USER
            )
            db.session.add(membership)

            decision = ArchitectureDecision(
                title='Decision With History',
                context='Test context',
                decision='Test decision text',
                consequences='Test consequences',
                status='proposed',
                domain=tenant.domain,
                tenant_id=tenant.id,
                created_by_id=user.id,
                decision_number=1
            )
            db.session.add(decision)
            db.session.flush()

            # Add history entries using the actual DecisionHistory model structure
            # DecisionHistory stores snapshots of the entire decision, not field changes
            for i in range(3):
                history = DecisionHistory(
                    decision_id=decision.id,
                    title=f'Title version {i + 1}',
                    context='Historical context',
                    decision_text='Historical decision text',
                    status='proposed' if i == 0 else 'accepted',
                    consequences='Historical consequences',
                    changed_by_id=user.id,
                    change_reason=f'Version {i + 1} change'
                )
                db.session.add(history)
            db.session.commit()

            api_key, full_key = AIApiKeyService.create_key(
                user, tenant, 'History Key',
                scopes=['read', 'search']
            )
            return full_key, decision.id

    def test_get_history_success(self, client, setup_with_history):
        """Successful history retrieval."""
        full_key, decision_id = setup_with_history
        response = client.get(
            f'/api/ai/decisions/{decision_id}/history',
            headers={'Authorization': f'Bearer {full_key}'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert 'decision_id' in data
        assert 'display_id' in data
        assert 'history' in data
        assert isinstance(data['history'], list)
        assert len(data['history']) == 3
        # Verify history entry structure
        history_entry = data['history'][0]
        assert 'changed_at' in history_entry
        assert 'changed_by' in history_entry
        assert 'change_reason' in history_entry
        assert 'title' in history_entry
        assert 'status' in history_entry

    def test_get_history_not_found_returns_404(self, client, setup_with_history):
        """Not found decision returns 404."""
        full_key, _ = setup_with_history
        response = client.get(
            '/api/ai/decisions/99999/history',
            headers={'Authorization': f'Bearer {full_key}'}
        )
        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data
        assert 'not found' in data['error']


# ============================================================================
# OPENAPI SCHEMA ENDPOINT TESTS
# ============================================================================

class TestOpenAPISchemaEndpoint:
    """Test /api/ai/openapi.json endpoint."""

    @pytest.fixture
    def api_app(self):
        """Create app with AI API blueprint."""
        _ensure_testing_env()
        import app as flask_app
        flask_app.app.config['TESTING'] = True
        flask_app.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        flask_app.app.config['WTF_CSRF_ENABLED'] = False

        with flask_app.app.app_context():
            db.create_all()
            yield flask_app.app
            db.drop_all()

    @pytest.fixture
    def client(self, api_app):
        """Create test client."""
        return api_app.test_client()

    def test_openapi_returns_valid_schema(self, client):
        """Returns valid OpenAPI 3.1 schema."""
        response = client.get('/api/ai/openapi.json')
        assert response.status_code == 200
        data = response.get_json()

        # Check OpenAPI version
        assert 'openapi' in data
        assert data['openapi'] == '3.1.0'

        # Check info
        assert 'info' in data
        assert 'title' in data['info']
        assert 'version' in data['info']

        # Check paths
        assert 'paths' in data
        assert '/search' in data['paths']
        assert '/decisions' in data['paths']
        assert '/decisions/{id}' in data['paths']
        assert '/decisions/{id}/history' in data['paths']

        # Check security
        assert 'components' in data
        assert 'securitySchemes' in data['components']
        assert 'bearerAuth' in data['components']['securitySchemes']

    def test_openapi_no_authentication_required(self, client):
        """OpenAPI endpoint does not require authentication."""
        # No Authorization header provided
        response = client.get('/api/ai/openapi.json')
        assert response.status_code == 200
        data = response.get_json()
        assert 'openapi' in data


# ============================================================================
# EDGE CASE TESTS
# ============================================================================

class TestExternalAIAPIEdgeCases:
    """Test edge cases in External AI API."""

    @pytest.fixture
    def api_app(self):
        """Create app with AI API blueprint."""
        _ensure_testing_env()
        import app as flask_app
        flask_app.app.config['TESTING'] = True
        flask_app.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        flask_app.app.config['WTF_CSRF_ENABLED'] = False

        with flask_app.app.app_context():
            db.create_all()
            yield flask_app.app
            db.drop_all()

    @pytest.fixture
    def client(self, api_app):
        """Create test client."""
        return api_app.test_client()

    @pytest.fixture
    def setup_basic(self, api_app):
        """Basic setup for edge case tests."""
        with api_app.app_context():
            SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
            SystemConfig.set(SystemConfig.KEY_AI_EXTERNAL_API_ENABLED, 'true')
            db.session.commit()

            tenant = Tenant(
                domain='edge.com',
                name='Edge Corp',
                status='active',
                maturity_state=MaturityState.BOOTSTRAP,
                ai_features_enabled=True,
                ai_external_access_enabled=True,
                ai_log_interactions=False
            )
            db.session.add(tenant)
            db.session.flush()

            user = User(
                email='user@edge.com',
                sso_domain='edge.com',
                auth_type='local',
                email_verified=True
            )
            user.set_name(first_name='Edge', last_name='User')
            db.session.add(user)
            db.session.flush()

            membership = TenantMembership(
                user_id=user.id,
                tenant_id=tenant.id,
                global_role=GlobalRole.USER
            )
            db.session.add(membership)
            db.session.commit()

            api_key, full_key = AIApiKeyService.create_key(
                user, tenant, 'Edge Key',
                scopes=['read', 'search', 'write']
            )
            return full_key

    def test_empty_search_query(self, client, setup_basic):
        """Search with empty query still works."""
        full_key = setup_basic
        response = client.post(
            '/api/ai/search',
            json={'query': ''},
            headers={'Authorization': f'Bearer {full_key}'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['query'] == ''

    def test_search_with_special_characters(self, client, setup_basic):
        """Search handles special characters."""
        full_key = setup_basic
        response = client.post(
            '/api/ai/search',
            json={'query': "test'query%with;special--chars"},
            headers={'Authorization': f'Bearer {full_key}'}
        )
        assert response.status_code == 200

    def test_list_with_zero_offset(self, client, setup_basic):
        """List with zero offset works."""
        full_key = setup_basic
        response = client.get(
            '/api/ai/decisions?offset=0',
            headers={'Authorization': f'Bearer {full_key}'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['offset'] == 0

    def test_create_with_whitespace_only_fields_fails(self, client, setup_basic):
        """Creating with whitespace-only fields fails."""
        full_key = setup_basic
        response = client.post(
            '/api/ai/decisions',
            json={
                'title': '   ',
                'context': 'Test context',
                'decision': 'Test decision',
                'consequences': 'Test consequences'
            },
            headers={'Authorization': f'Bearer {full_key}'}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_get_decision_with_adr_prefix_variations(self, client, api_app, setup_basic):
        """Get decision handles ADR prefix variations."""
        full_key = setup_basic
        with api_app.app_context():
            tenant = Tenant.query.filter_by(domain='edge.com').first()
            user = User.query.filter_by(email='user@edge.com').first()
            decision = ArchitectureDecision(
                title='Test ADR Prefix',
                context='Context',
                decision='Decision',
                consequences='Consequences',
                status='proposed',
                domain=tenant.domain,
                tenant_id=tenant.id,
                created_by_id=user.id,
                decision_number=123
            )
            db.session.add(decision)
            db.session.commit()

        # Test with ADR-123
        response = client.get(
            '/api/ai/decisions/ADR-123',
            headers={'Authorization': f'Bearer {full_key}'}
        )
        assert response.status_code == 200

        # Test with just 123 (in the decision_number)
        response = client.get(
            '/api/ai/decisions/adr-123',
            headers={'Authorization': f'Bearer {full_key}'}
        )
        assert response.status_code == 200
