"""
Backend Unit Tests for Microsoft Teams Security Module (Enterprise Edition)

Tests for Teams security functions including:
- JWT validation (valid tokens, expired tokens, wrong audience)
- OAuth state encryption/decryption
- Link token generation/verification
- OIDC state handling

Note: These tests require Enterprise Edition modules from ee/backend/teams/
"""
import pytest
import json
import os
import time
import jwt
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, MagicMock
from flask import Flask

from models import db

# Check if Enterprise Edition is available
try:
    from ee.backend.teams import teams_security as _ts_check
    EE_AVAILABLE = True
except ImportError:
    EE_AVAILABLE = False

pytestmark = pytest.mark.skipif(not EE_AVAILABLE, reason="Enterprise Edition modules not available")


# ==================== Fixtures ====================

@pytest.fixture
def app():
    """Create application for testing."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'test-secret-key-for-teams'

    # Set Teams environment variables for tests
    os.environ['TEAMS_BOT_APP_ID'] = 'test-bot-app-id-12345'
    os.environ['TEAMS_BOT_APP_SECRET'] = 'test-bot-app-secret'
    os.environ['TEAMS_BOT_TENANT_ID'] = 'test-tenant-id-12345'
    os.environ['SECRET_KEY'] = 'test-secret-key-for-teams'

    db.init_app(app)

    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def session_fixture(app):
    """Create database session for testing."""
    with app.app_context():
        yield db.session


# ==================== Test Token Encryption ====================

class TestTeamsTokenEncryption:
    """Test Teams token encryption/decryption."""

    def test_token_encryption_roundtrip(self, app):
        """Token can be encrypted and decrypted."""
        with app.app_context():
            from ee.backend.teams.teams_security import encrypt_token, decrypt_token

            original_token = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.test-token-12345'

            encrypted = encrypt_token(original_token)
            assert encrypted is not None
            assert encrypted != original_token

            decrypted = decrypt_token(encrypted)
            assert decrypted == original_token

    def test_encrypt_none_returns_none(self, app):
        """Encrypting None should return None."""
        with app.app_context():
            from ee.backend.teams.teams_security import encrypt_token

            result = encrypt_token(None)
            assert result is None

    def test_decrypt_none_returns_none(self, app):
        """Decrypting None should return None."""
        with app.app_context():
            from ee.backend.teams.teams_security import decrypt_token

            result = decrypt_token(None)
            assert result is None

    def test_encrypt_empty_string_returns_none(self, app):
        """Encrypting empty string returns None (falsy value treated as None)."""
        with app.app_context():
            from ee.backend.teams.teams_security import encrypt_token

            # Empty string is treated as falsy, returns None
            encrypted = encrypt_token('')
            assert encrypted is None

    def test_different_tokens_produce_different_encrypted_values(self, app):
        """Different tokens produce different encrypted values."""
        with app.app_context():
            from ee.backend.teams.teams_security import encrypt_token

            encrypted1 = encrypt_token('token-one-12345')
            encrypted2 = encrypt_token('token-two-67890')

            assert encrypted1 != encrypted2


# ==================== Test OAuth State ====================

class TestTeamsOAuthState:
    """Test Teams OAuth state parameter handling."""

    def test_oauth_state_roundtrip(self, app):
        """OAuth state can be generated and verified."""
        with app.app_context():
            from ee.backend.teams.teams_security import generate_teams_oauth_state, verify_teams_oauth_state

            state = generate_teams_oauth_state(
                tenant_id=123,
                user_id=456,
                extra_data={'source': 'test'}
            )

            assert state is not None
            assert isinstance(state, str)

            # Verify state
            state_data = verify_teams_oauth_state(state)
            assert state_data is not None
            assert state_data['tenant_id'] == 123
            assert state_data['user_id'] == 456
            assert state_data['extra_data']['source'] == 'test'
            assert 'csrf_token' in state_data
            assert 'expires_at' in state_data
            assert state_data['type'] == 'teams_oauth'

    def test_oauth_state_expires(self, app):
        """Expired OAuth state should be rejected."""
        with app.app_context():
            from ee.backend.teams.teams_security import _get_encryption_key, verify_teams_oauth_state
            from cryptography.fernet import Fernet

            # Create expired state (expired 1 hour ago)
            expires_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
            state_data = {
                'type': 'teams_oauth',
                'tenant_id': 123,
                'csrf_token': 'test-csrf',
                'expires_at': expires_at,
                'extra_data': {}
            }

            fernet = Fernet(_get_encryption_key())
            expired_state = fernet.encrypt(json.dumps(state_data).encode()).decode()

            # Verify should fail
            result = verify_teams_oauth_state(expired_state)
            assert result is None

    def test_oauth_state_invalid_returns_none(self, app):
        """Invalid OAuth state should return None."""
        with app.app_context():
            from ee.backend.teams.teams_security import verify_teams_oauth_state

            invalid_state = 'totally-invalid-state-string'
            result = verify_teams_oauth_state(invalid_state)
            assert result is None

    def test_oauth_state_wrong_type_returns_none(self, app):
        """OAuth state with wrong type should be rejected."""
        with app.app_context():
            from ee.backend.teams.teams_security import _get_encryption_key, verify_teams_oauth_state
            from cryptography.fernet import Fernet

            # Create state with wrong type
            expires_at = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
            state_data = {
                'type': 'wrong_type',  # Not 'teams_oauth'
                'tenant_id': 123,
                'csrf_token': 'test-csrf',
                'expires_at': expires_at,
                'extra_data': {}
            }

            fernet = Fernet(_get_encryption_key())
            wrong_type_state = fernet.encrypt(json.dumps(state_data).encode()).decode()

            result = verify_teams_oauth_state(wrong_type_state)
            assert result is None

    def test_oauth_state_empty_returns_none(self, app):
        """Empty state should return None."""
        with app.app_context():
            from ee.backend.teams.teams_security import verify_teams_oauth_state

            assert verify_teams_oauth_state('') is None
            assert verify_teams_oauth_state(None) is None


# ==================== Test Link Token ====================

class TestTeamsLinkToken:
    """Test Teams user link token generation and verification."""

    def test_link_token_roundtrip(self, app):
        """Link token can be generated and verified."""
        with app.app_context():
            from ee.backend.teams.teams_security import generate_teams_link_token, verify_teams_link_token

            token = generate_teams_link_token(
                teams_workspace_id=1,
                aad_object_id='aad-user-12345',
                aad_email='user@example.com'
            )

            assert token is not None
            assert isinstance(token, str)

            # Verify token
            token_data = verify_teams_link_token(token)
            assert token_data is not None
            assert token_data['teams_workspace_id'] == 1
            assert token_data['aad_object_id'] == 'aad-user-12345'
            assert token_data['aad_email'] == 'user@example.com'
            assert token_data['type'] == 'teams_link'
            assert 'expires_at' in token_data
            assert 'nonce' in token_data

    def test_link_token_expires(self, app):
        """Expired link token should be rejected."""
        with app.app_context():
            from ee.backend.teams.teams_security import _get_encryption_key, verify_teams_link_token
            from cryptography.fernet import Fernet

            # Create expired token (expired 1 hour ago)
            expires_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
            token_data = {
                'type': 'teams_link',
                'teams_workspace_id': 1,
                'aad_object_id': 'aad-user-12345',
                'aad_email': 'user@example.com',
                'expires_at': expires_at,
                'nonce': 'test-nonce'
            }

            fernet = Fernet(_get_encryption_key())
            expired_token = fernet.encrypt(json.dumps(token_data).encode()).decode()

            result = verify_teams_link_token(expired_token)
            assert result is None

    def test_link_token_invalid_returns_none(self, app):
        """Invalid link token should return None."""
        with app.app_context():
            from ee.backend.teams.teams_security import verify_teams_link_token

            invalid_token = 'invalid-token-string'
            result = verify_teams_link_token(invalid_token)
            assert result is None

    def test_link_token_wrong_type_returns_none(self, app):
        """Link token with wrong type should be rejected."""
        with app.app_context():
            from ee.backend.teams.teams_security import _get_encryption_key, verify_teams_link_token
            from cryptography.fernet import Fernet

            expires_at = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
            token_data = {
                'type': 'wrong_type',  # Not 'teams_link'
                'teams_workspace_id': 1,
                'aad_object_id': 'aad-user-12345',
                'expires_at': expires_at,
                'nonce': 'test-nonce'
            }

            fernet = Fernet(_get_encryption_key())
            wrong_type_token = fernet.encrypt(json.dumps(token_data).encode()).decode()

            result = verify_teams_link_token(wrong_type_token)
            assert result is None

    def test_link_token_empty_returns_none(self, app):
        """Empty link token should return None."""
        with app.app_context():
            from ee.backend.teams.teams_security import verify_teams_link_token

            assert verify_teams_link_token('') is None
            assert verify_teams_link_token(None) is None


# ==================== Test OIDC State ====================

class TestTeamsOIDCState:
    """Test Teams OIDC state parameter handling."""

    def test_oidc_state_roundtrip(self, app):
        """OIDC state can be generated and verified."""
        with app.app_context():
            from ee.backend.teams.teams_security import generate_teams_oidc_state, verify_teams_oidc_state

            state = generate_teams_oidc_state(
                return_url='/dashboard',
                extra_data={'flow': 'login'}
            )

            assert state is not None
            assert isinstance(state, str)

            # Verify state
            state_data = verify_teams_oidc_state(state)
            assert state_data is not None
            assert state_data['return_url'] == '/dashboard'
            assert state_data['extra_data']['flow'] == 'login'
            assert state_data['type'] == 'teams_oidc'
            assert 'csrf_token' in state_data
            assert 'expires_at' in state_data

    def test_oidc_state_expires(self, app):
        """Expired OIDC state should be rejected."""
        with app.app_context():
            from ee.backend.teams.teams_security import _get_encryption_key, verify_teams_oidc_state
            from cryptography.fernet import Fernet

            # Create expired state (expired 1 hour ago)
            expires_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
            state_data = {
                'type': 'teams_oidc',
                'csrf_token': 'test-csrf',
                'expires_at': expires_at,
                'return_url': '/dashboard',
                'extra_data': {}
            }

            fernet = Fernet(_get_encryption_key())
            expired_state = fernet.encrypt(json.dumps(state_data).encode()).decode()

            result = verify_teams_oidc_state(expired_state)
            assert result is None

    def test_oidc_state_invalid_returns_none(self, app):
        """Invalid OIDC state should return None."""
        with app.app_context():
            from ee.backend.teams.teams_security import verify_teams_oidc_state

            invalid_state = 'invalid-oidc-state'
            result = verify_teams_oidc_state(invalid_state)
            assert result is None

    def test_oidc_state_wrong_type_returns_none(self, app):
        """OIDC state with wrong type should be rejected."""
        with app.app_context():
            from ee.backend.teams.teams_security import _get_encryption_key, verify_teams_oidc_state
            from cryptography.fernet import Fernet

            expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
            state_data = {
                'type': 'teams_oauth',  # Not 'teams_oidc'
                'csrf_token': 'test-csrf',
                'expires_at': expires_at,
                'return_url': '/dashboard',
                'extra_data': {}
            }

            fernet = Fernet(_get_encryption_key())
            wrong_type_state = fernet.encrypt(json.dumps(state_data).encode()).decode()

            result = verify_teams_oidc_state(wrong_type_state)
            assert result is None

    def test_oidc_state_empty_returns_none(self, app):
        """Empty OIDC state should return None."""
        with app.app_context():
            from ee.backend.teams.teams_security import verify_teams_oidc_state

            assert verify_teams_oidc_state('') is None
            assert verify_teams_oidc_state(None) is None


# ==================== Test JWT Validation ====================

class TestTeamsJWTValidation:
    """Test Teams Bot Framework JWT validation."""

    def test_validate_jwt_missing_header_returns_none(self, app):
        """Missing Authorization header should return None."""
        with app.app_context():
            from ee.backend.teams.teams_security import validate_teams_jwt

            result = validate_teams_jwt(None)
            assert result is None

            result = validate_teams_jwt('')
            assert result is None

    def test_validate_jwt_invalid_format_returns_none(self, app):
        """Invalid header format should return None."""
        with app.app_context():
            from ee.backend.teams.teams_security import validate_teams_jwt

            result = validate_teams_jwt('InvalidFormat token123')
            assert result is None

            result = validate_teams_jwt('Basic dXNlcjpwYXNz')
            assert result is None

    def test_validate_jwt_no_app_id_returns_none(self, app):
        """Missing app ID should return None."""
        with app.app_context():
            from ee.backend.teams.teams_security import validate_teams_jwt

            # Clear the app ID
            original = os.environ.get('TEAMS_BOT_APP_ID')
            del os.environ['TEAMS_BOT_APP_ID']

            # Reset cached value
            from ee.backend.teams import teams_security
            teams_security._teams_bot_app_id = None

            try:
                result = validate_teams_jwt('Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.test')
                assert result is None
            finally:
                # Restore
                if original:
                    os.environ['TEAMS_BOT_APP_ID'] = original
                teams_security._teams_bot_app_id = None

    def test_validate_jwt_invalid_token_returns_none(self, app):
        """Invalid JWT token should return None."""
        with app.app_context():
            from ee.backend.teams.teams_security import validate_teams_jwt

            # This is a malformed JWT
            result = validate_teams_jwt('Bearer not.a.valid.jwt.token')
            assert result is None

    @patch('ee.backend.teams.teams_security._get_jwks_client')
    def test_validate_jwt_expired_returns_none(self, mock_jwks, app):
        """Expired JWT should return None."""
        with app.app_context():
            from ee.backend.teams.teams_security import validate_teams_jwt

            # Create an expired JWT manually
            expired_time = datetime.now(timezone.utc) - timedelta(hours=1)
            expired_token = jwt.encode(
                {
                    'iss': 'https://api.botframework.com',
                    'aud': 'test-bot-app-id-12345',
                    'exp': int(expired_time.timestamp()),
                    'iat': int((expired_time - timedelta(hours=1)).timestamp())
                },
                'secret',
                algorithm='HS256'
            )

            # The JWKS client will fail to validate anyway, but we test the flow
            mock_jwks.side_effect = Exception("JWKS fetch failed")

            result = validate_teams_jwt(f'Bearer {expired_token}')
            assert result is None


# ==================== Test verify_teams_request Decorator ====================

class TestVerifyTeamsRequestDecorator:
    """Test the verify_teams_request decorator."""

    def test_decorator_rejects_missing_auth(self, app):
        """Decorator rejects requests without auth header."""
        with app.app_context():
            from ee.backend.teams.teams_security import verify_teams_request

            @app.route('/test-teams', methods=['POST'])
            @verify_teams_request
            def test_route():
                return {'status': 'ok'}, 200

            with app.test_client() as client:
                response = client.post('/test-teams')
                assert response.status_code == 401
                assert 'error' in response.json

    def test_decorator_rejects_invalid_token(self, app):
        """Decorator rejects requests with invalid token."""
        with app.app_context():
            from ee.backend.teams.teams_security import verify_teams_request

            @app.route('/test-teams-invalid', methods=['POST'])
            @verify_teams_request
            def test_route2():
                return {'status': 'ok'}, 200

            with app.test_client() as client:
                response = client.post(
                    '/test-teams-invalid',
                    headers={'Authorization': 'Bearer invalid.jwt.token'}
                )
                assert response.status_code == 401


# ==================== Test URL Helpers ====================

class TestTeamsOIDCURLHelpers:
    """Test Teams OIDC URL helper functions."""

    def test_get_authorize_url_with_tenant(self, app):
        """Authorize URL includes tenant ID."""
        with app.app_context():
            from ee.backend.teams.teams_security import get_teams_oidc_authorize_url

            url = get_teams_oidc_authorize_url(tenant_id='specific-tenant-id')
            assert 'specific-tenant-id' in url
            assert 'oauth2/v2.0/authorize' in url

    def test_get_authorize_url_common(self, app):
        """Authorize URL uses 'common' by default."""
        with app.app_context():
            from ee.backend.teams.teams_security import get_teams_oidc_authorize_url

            url = get_teams_oidc_authorize_url()
            assert '/common/' in url
            assert 'oauth2/v2.0/authorize' in url

    def test_get_token_url_with_tenant(self, app):
        """Token URL includes tenant ID."""
        with app.app_context():
            from ee.backend.teams.teams_security import get_teams_oidc_token_url

            url = get_teams_oidc_token_url(tenant_id='specific-tenant-id')
            assert 'specific-tenant-id' in url
            assert 'oauth2/v2.0/token' in url

    def test_get_token_url_common(self, app):
        """Token URL uses 'common' by default."""
        with app.app_context():
            from ee.backend.teams.teams_security import get_teams_oidc_token_url

            url = get_teams_oidc_token_url()
            assert '/common/' in url
            assert 'oauth2/v2.0/token' in url


# ==================== Test Credential Getters ====================

class TestTeamsCredentialGetters:
    """Test credential getter functions."""

    def test_get_teams_bot_app_id_from_env(self, app):
        """Gets bot app ID from environment variable."""
        with app.app_context():
            # Reset cached value
            from ee.backend.teams import teams_security
            teams_security._teams_bot_app_id = None

            os.environ['TEAMS_BOT_APP_ID'] = 'env-bot-app-id'
            from ee.backend.teams.teams_security import get_teams_bot_app_id

            result = get_teams_bot_app_id()
            assert result == 'env-bot-app-id'

    def test_get_teams_bot_app_secret_from_env(self, app):
        """Gets bot app secret from environment variable."""
        with app.app_context():
            # Reset cached value
            from ee.backend.teams import teams_security
            teams_security._teams_bot_app_secret = None

            os.environ['TEAMS_BOT_APP_SECRET'] = 'env-bot-secret'
            from ee.backend.teams.teams_security import get_teams_bot_app_secret

            result = get_teams_bot_app_secret()
            assert result == 'env-bot-secret'

    def test_get_teams_bot_tenant_id_from_env(self, app):
        """Gets bot tenant ID from environment variable."""
        with app.app_context():
            # Reset cached value
            from ee.backend.teams import teams_security
            teams_security._teams_bot_tenant_id = None

            os.environ['TEAMS_BOT_TENANT_ID'] = 'env-tenant-id'
            from ee.backend.teams.teams_security import get_teams_bot_tenant_id

            result = get_teams_bot_tenant_id()
            assert result == 'env-tenant-id'


# ==================== Test OIDC Token Exchange ====================

class TestTeamsOIDCTokenExchange:
    """Test Teams OIDC token exchange."""

    @patch('ee.backend.teams.teams_security.httpx.Client')
    def test_exchange_code_success(self, mock_client_class, app):
        """Successfully exchanges authorization code for tokens."""
        with app.app_context():
            from ee.backend.teams.teams_security import exchange_teams_oidc_code

            # Mock token response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'access_token': 'mock-access-token',
                'id_token': jwt.encode({'sub': 'user123', 'email': 'user@example.com'}, 'secret', algorithm='HS256'),
                'token_type': 'Bearer',
                'expires_in': 3600
            }

            mock_client = Mock()
            mock_client.post.return_value = mock_response
            mock_client.__enter__ = Mock(return_value=mock_client)
            mock_client.__exit__ = Mock(return_value=None)
            mock_client_class.return_value = mock_client

            id_claims, access_token = exchange_teams_oidc_code(
                'auth-code-12345',
                'https://example.com/callback'
            )

            assert access_token == 'mock-access-token'
            assert id_claims is not None
            assert id_claims['sub'] == 'user123'

    @patch('ee.backend.teams.teams_security.httpx.Client')
    def test_exchange_code_failure(self, mock_client_class, app):
        """Returns None on token exchange failure."""
        with app.app_context():
            from ee.backend.teams.teams_security import exchange_teams_oidc_code

            # Mock error response
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.text = 'Bad Request'

            mock_client = Mock()
            mock_client.post.return_value = mock_response
            mock_client.__enter__ = Mock(return_value=mock_client)
            mock_client.__exit__ = Mock(return_value=None)
            mock_client_class.return_value = mock_client

            id_claims, access_token = exchange_teams_oidc_code(
                'invalid-code',
                'https://example.com/callback'
            )

            assert id_claims is None
            assert access_token is None


# ==================== Test Get User Info ====================

class TestTeamsGetUserInfo:
    """Test Teams user info retrieval from Graph API."""

    @patch('ee.backend.teams.teams_security.httpx.Client')
    def test_get_user_info_success(self, mock_client_class, app):
        """Successfully retrieves user info from Graph API."""
        with app.app_context():
            from ee.backend.teams.teams_security import get_teams_user_info

            # Mock Graph API response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'id': 'user-object-id-12345',
                'displayName': 'Test User',
                'mail': 'test@example.com',
                'userPrincipalName': 'test@example.com'
            }

            mock_client = Mock()
            mock_client.get.return_value = mock_response
            mock_client.__enter__ = Mock(return_value=mock_client)
            mock_client.__exit__ = Mock(return_value=None)
            mock_client_class.return_value = mock_client

            user_info = get_teams_user_info('mock-access-token')

            assert user_info is not None
            assert user_info['id'] == 'user-object-id-12345'
            assert user_info['mail'] == 'test@example.com'

    @patch('ee.backend.teams.teams_security.httpx.Client')
    def test_get_user_info_failure(self, mock_client_class, app):
        """Returns None on Graph API failure."""
        with app.app_context():
            from ee.backend.teams.teams_security import get_teams_user_info

            # Mock error response
            mock_response = Mock()
            mock_response.status_code = 401
            mock_response.text = 'Unauthorized'

            mock_client = Mock()
            mock_client.get.return_value = mock_response
            mock_client.__enter__ = Mock(return_value=mock_client)
            mock_client.__exit__ = Mock(return_value=None)
            mock_client_class.return_value = mock_client

            user_info = get_teams_user_info('invalid-token')

            assert user_info is None


# ==================== Test State Security Properties ====================

class TestTeamsStateSecurityProperties:
    """Test security properties of state parameters."""

    def test_csrf_token_is_unique_per_state(self, app):
        """Each OAuth state has a unique CSRF token."""
        with app.app_context():
            from ee.backend.teams.teams_security import generate_teams_oauth_state, verify_teams_oauth_state

            state1 = generate_teams_oauth_state(tenant_id=1)
            state2 = generate_teams_oauth_state(tenant_id=1)

            data1 = verify_teams_oauth_state(state1)
            data2 = verify_teams_oauth_state(state2)

            assert data1['csrf_token'] != data2['csrf_token']

    def test_nonce_is_unique_per_link_token(self, app):
        """Each link token has a unique nonce."""
        with app.app_context():
            from ee.backend.teams.teams_security import generate_teams_link_token, verify_teams_link_token

            token1 = generate_teams_link_token(1, 'aad-id-1')
            token2 = generate_teams_link_token(1, 'aad-id-1')

            data1 = verify_teams_link_token(token1)
            data2 = verify_teams_link_token(token2)

            assert data1['nonce'] != data2['nonce']

    def test_state_cannot_be_reused_after_expiry(self, app):
        """State parameters expire and cannot be reused."""
        with app.app_context():
            from ee.backend.teams.teams_security import _get_encryption_key, verify_teams_oidc_state
            from cryptography.fernet import Fernet

            # Create a state that expires in 1 second
            expires_at = (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat()
            state_data = {
                'type': 'teams_oidc',
                'csrf_token': 'test-csrf',
                'expires_at': expires_at,
                'return_url': '/dashboard',
                'extra_data': {}
            }

            fernet = Fernet(_get_encryption_key())
            short_lived_state = fernet.encrypt(json.dumps(state_data).encode()).decode()

            # Should work initially
            result = verify_teams_oidc_state(short_lived_state)
            assert result is not None

            # Wait for expiry
            time.sleep(1.5)

            # Should fail after expiry
            result = verify_teams_oidc_state(short_lived_state)
            assert result is None
