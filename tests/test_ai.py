"""
Tests for AI/LLM integration foundation (Enterprise Edition).

Tests cover:
1. AI Config - Hierarchical configuration system
2. API Key Service - Key generation, validation, and management
3. Interaction Logger - Logging and querying AI interactions
4. API Endpoints - Super admin, tenant admin, and user endpoints

Note: These tests require Enterprise Edition modules from ee/backend/ai/
"""
import pytest
from datetime import datetime, timedelta, timezone
from flask import Flask, session as flask_session, g

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    db, User, Tenant, TenantMembership, SystemConfig, GlobalRole, MaturityState,
    AIApiKey, AIInteractionLog, LLMProvider, AIChannel, AIAction
)

# Enterprise Edition imports - skip tests if not available
try:
    from ee.backend.ai import AIConfig, AIApiKeyService, AIInteractionLogger
    EE_AVAILABLE = True
except ImportError:
    EE_AVAILABLE = False
    AIConfig = None
    AIApiKeyService = None
    AIInteractionLogger = None

pytestmark = pytest.mark.skipif(not EE_AVAILABLE, reason="Enterprise Edition modules not available")


# ============================================================================
# AI CONFIG TESTS
# ============================================================================

class TestAIConfigSystemLevel:
    """Test system-level AI configuration (Super Admin)."""

    def test_get_system_ai_enabled_default_false(self, app, session):
        """System AI is disabled by default."""
        assert AIConfig.get_system_ai_enabled() is False

    def test_get_system_ai_enabled_when_set_true(self, app, session):
        """System AI can be enabled via SystemConfig."""
        SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
        assert AIConfig.get_system_ai_enabled() is True

    def test_get_system_ai_enabled_when_set_false(self, app, session):
        """System AI can be explicitly disabled."""
        SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'false')
        assert AIConfig.get_system_ai_enabled() is False

    def test_get_system_slack_bot_enabled_default_false(self, app, session):
        """Slack bot is disabled by default."""
        assert AIConfig.get_system_slack_bot_enabled() is False

    def test_get_system_slack_bot_enabled_requires_ai_enabled(self, app, session):
        """Slack bot requires system AI to be enabled."""
        # Enable slack bot but not AI
        SystemConfig.set(SystemConfig.KEY_AI_SLACK_BOT_ENABLED, 'true')
        assert AIConfig.get_system_slack_bot_enabled() is False

        # Enable AI as well
        SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
        assert AIConfig.get_system_slack_bot_enabled() is True

    def test_get_system_mcp_server_enabled_default_false(self, app, session):
        """MCP server is disabled by default."""
        assert AIConfig.get_system_mcp_server_enabled() is False

    def test_get_system_mcp_server_enabled_requires_ai_enabled(self, app, session):
        """MCP server requires system AI to be enabled."""
        SystemConfig.set(SystemConfig.KEY_AI_MCP_SERVER_ENABLED, 'true')
        assert AIConfig.get_system_mcp_server_enabled() is False

        SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
        assert AIConfig.get_system_mcp_server_enabled() is True

    def test_get_system_external_api_enabled_default_false(self, app, session):
        """External API is disabled by default."""
        assert AIConfig.get_system_external_api_enabled() is False

    def test_get_system_external_api_enabled_requires_ai_enabled(self, app, session):
        """External API requires system AI to be enabled."""
        SystemConfig.set(SystemConfig.KEY_AI_EXTERNAL_API_ENABLED, 'true')
        assert AIConfig.get_system_external_api_enabled() is False

        SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
        assert AIConfig.get_system_external_api_enabled() is True

    def test_get_system_assisted_creation_enabled_default_false(self, app, session):
        """Assisted creation is disabled by default."""
        assert AIConfig.get_system_assisted_creation_enabled() is False

    def test_get_system_assisted_creation_enabled_requires_ai_enabled(self, app, session):
        """Assisted creation requires system AI to be enabled."""
        SystemConfig.set(SystemConfig.KEY_AI_ASSISTED_CREATION_ENABLED, 'true')
        assert AIConfig.get_system_assisted_creation_enabled() is False

        SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
        assert AIConfig.get_system_assisted_creation_enabled() is True

    def test_get_llm_provider_default_none(self, app, session):
        """LLM provider defaults to NONE."""
        provider = AIConfig.get_llm_provider()
        assert provider == LLMProvider.NONE

    def test_get_llm_provider_set_openai(self, app, session):
        """LLM provider can be set to OpenAI."""
        SystemConfig.set(SystemConfig.KEY_AI_LLM_PROVIDER, 'openai')
        provider = AIConfig.get_llm_provider()
        assert provider == LLMProvider.OPENAI

    def test_get_llm_provider_set_anthropic(self, app, session):
        """LLM provider can be set to Anthropic."""
        SystemConfig.set(SystemConfig.KEY_AI_LLM_PROVIDER, 'anthropic')
        provider = AIConfig.get_llm_provider()
        assert provider == LLMProvider.ANTHROPIC

    def test_get_llm_provider_invalid_returns_none(self, app, session):
        """Invalid LLM provider returns NONE."""
        SystemConfig.set(SystemConfig.KEY_AI_LLM_PROVIDER, 'invalid_provider')
        provider = AIConfig.get_llm_provider()
        assert provider == LLMProvider.NONE

    def test_get_llm_model_returns_none_when_not_set(self, app, session):
        """LLM model returns None when not set."""
        assert AIConfig.get_llm_model() is None

    def test_get_llm_model_returns_value_when_set(self, app, session):
        """LLM model returns value when set."""
        SystemConfig.set(SystemConfig.KEY_AI_LLM_MODEL, 'gpt-4o')
        assert AIConfig.get_llm_model() == 'gpt-4o'

    def test_get_llm_endpoint_returns_none_when_not_set(self, app, session):
        """LLM endpoint returns None when not set."""
        assert AIConfig.get_llm_endpoint() is None

    def test_get_llm_endpoint_returns_value_when_set(self, app, session):
        """LLM endpoint returns value when set."""
        SystemConfig.set(SystemConfig.KEY_AI_LLM_ENDPOINT, 'https://custom.openai.azure.com/')
        assert AIConfig.get_llm_endpoint() == 'https://custom.openai.azure.com/'

    def test_set_system_config_creates_new_entry(self, app, session):
        """set_system_config creates new config entry."""
        AIConfig.set_system_config(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
        assert SystemConfig.get(SystemConfig.KEY_AI_FEATURES_ENABLED) == 'true'

    def test_set_system_config_updates_existing_entry(self, app, session):
        """set_system_config updates existing config entry."""
        AIConfig.set_system_config(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
        AIConfig.set_system_config(SystemConfig.KEY_AI_FEATURES_ENABLED, 'false')
        assert SystemConfig.get(SystemConfig.KEY_AI_FEATURES_ENABLED) == 'false'

    def test_get_system_ai_config_returns_dict(self, app, session):
        """get_system_ai_config returns a dictionary with all config."""
        SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
        SystemConfig.set(SystemConfig.KEY_AI_LLM_PROVIDER, 'openai')
        SystemConfig.set(SystemConfig.KEY_AI_LLM_MODEL, 'gpt-4o')

        config = AIConfig.get_system_ai_config()

        assert isinstance(config, dict)
        assert 'ai_features_enabled' in config
        assert 'llm_provider' in config
        assert 'llm_model' in config
        assert config['ai_features_enabled'] is True
        assert config['llm_provider'] == 'openai'
        assert config['llm_model'] == 'gpt-4o'


class TestAIConfigTenantLevel:
    """Test tenant-level AI configuration (Tenant Admin)."""

    def test_get_tenant_ai_enabled_default_false(self, app, session, sample_tenant):
        """Tenant AI is disabled by default."""
        assert AIConfig.get_tenant_ai_enabled(sample_tenant) is False

    def test_get_tenant_ai_enabled_requires_system_enabled(self, app, session, sample_tenant):
        """Tenant AI requires system-level AI to be enabled."""
        sample_tenant.ai_features_enabled = True
        session.commit()
        assert AIConfig.get_tenant_ai_enabled(sample_tenant) is False

        SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
        assert AIConfig.get_tenant_ai_enabled(sample_tenant) is True

    def test_get_tenant_slack_queries_enabled_requires_all_levels(self, app, session, sample_tenant):
        """Slack queries require all levels to be enabled."""
        # Enable tenant level
        sample_tenant.ai_features_enabled = True
        sample_tenant.ai_slack_queries_enabled = True
        session.commit()
        assert AIConfig.get_tenant_slack_queries_enabled(sample_tenant) is False

        # Enable system AI
        SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
        assert AIConfig.get_tenant_slack_queries_enabled(sample_tenant) is False

        # Enable system Slack bot
        SystemConfig.set(SystemConfig.KEY_AI_SLACK_BOT_ENABLED, 'true')
        assert AIConfig.get_tenant_slack_queries_enabled(sample_tenant) is True

    def test_get_tenant_assisted_creation_enabled_requires_all_levels(self, app, session, sample_tenant):
        """Assisted creation requires all levels to be enabled."""
        sample_tenant.ai_features_enabled = True
        sample_tenant.ai_assisted_creation_enabled = True
        session.commit()
        assert AIConfig.get_tenant_assisted_creation_enabled(sample_tenant) is False

        SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
        SystemConfig.set(SystemConfig.KEY_AI_ASSISTED_CREATION_ENABLED, 'true')
        assert AIConfig.get_tenant_assisted_creation_enabled(sample_tenant) is True

    def test_get_tenant_external_access_enabled_requires_all_levels(self, app, session, sample_tenant):
        """External access requires all levels to be enabled."""
        sample_tenant.ai_features_enabled = True
        sample_tenant.ai_external_access_enabled = True
        session.commit()
        assert AIConfig.get_tenant_external_access_enabled(sample_tenant) is False

        SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
        SystemConfig.set(SystemConfig.KEY_AI_EXTERNAL_API_ENABLED, 'true')
        assert AIConfig.get_tenant_external_access_enabled(sample_tenant) is True

    def test_get_tenant_require_anonymization_default_true(self, app, session, sample_tenant):
        """Anonymization is required by default."""
        assert AIConfig.get_tenant_require_anonymization(sample_tenant) is True

    def test_get_tenant_log_interactions_default_true(self, app, session, sample_tenant):
        """Interaction logging is enabled by default."""
        assert AIConfig.get_tenant_log_interactions(sample_tenant) is True

    def test_get_tenant_ai_config_returns_dict(self, app, session, sample_tenant):
        """get_tenant_ai_config returns a dictionary."""
        SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
        sample_tenant.ai_features_enabled = True
        session.commit()

        config = AIConfig.get_tenant_ai_config(sample_tenant)

        assert isinstance(config, dict)
        assert 'ai_features_enabled' in config
        assert 'ai_slack_queries_enabled' in config
        assert 'ai_require_anonymization' in config
        assert 'ai_log_interactions' in config

    def test_update_tenant_ai_config(self, app, session, sample_tenant):
        """update_tenant_ai_config updates tenant settings."""
        AIConfig.update_tenant_ai_config(
            sample_tenant,
            ai_features_enabled=True,
            ai_slack_queries_enabled=True,
            ai_require_anonymization=False
        )

        session.refresh(sample_tenant)
        assert sample_tenant.ai_features_enabled is True
        assert sample_tenant.ai_slack_queries_enabled is True
        assert sample_tenant.ai_require_anonymization is False

    def test_update_tenant_ai_config_ignores_invalid_fields(self, app, session, sample_tenant):
        """update_tenant_ai_config ignores invalid fields."""
        original_domain = sample_tenant.domain
        AIConfig.update_tenant_ai_config(
            sample_tenant,
            ai_features_enabled=True,
            domain='hacked.com',  # Should be ignored
            invalid_field='value'  # Should be ignored
        )

        session.refresh(sample_tenant)
        assert sample_tenant.domain == original_domain


class TestAIConfigUserLevel:
    """Test user-level AI configuration."""

    def test_get_user_ai_opt_out_default_false(self, app, session, sample_user, sample_tenant, sample_membership):
        """User AI opt-out is false by default."""
        assert AIConfig.get_user_ai_opt_out(sample_user, sample_tenant) is False

    def test_get_user_ai_opt_out_returns_true_when_set(self, app, session, sample_user, sample_tenant, sample_membership):
        """User AI opt-out returns true when set."""
        sample_membership.ai_opt_out = True
        session.commit()
        assert AIConfig.get_user_ai_opt_out(sample_user, sample_tenant) is True

    def test_get_user_ai_opt_out_returns_false_for_non_member(self, app, session, sample_user, sample_tenant):
        """User AI opt-out returns false for non-member."""
        assert AIConfig.get_user_ai_opt_out(sample_user, sample_tenant) is False

    def test_set_user_ai_opt_out(self, app, session, sample_user, sample_tenant, sample_membership):
        """set_user_ai_opt_out updates user preference."""
        AIConfig.set_user_ai_opt_out(sample_user, sample_tenant, True)
        session.refresh(sample_membership)
        assert sample_membership.ai_opt_out is True

        AIConfig.set_user_ai_opt_out(sample_user, sample_tenant, False)
        session.refresh(sample_membership)
        assert sample_membership.ai_opt_out is False


class TestAIConfigCombinedChecks:
    """Test combined availability checks."""

    def test_is_ai_available_for_user_requires_all_levels(self, app, session, sample_user, sample_tenant, sample_membership):
        """is_ai_available_for_user requires system, tenant, and no opt-out."""
        # All disabled
        assert AIConfig.is_ai_available_for_user(sample_user, sample_tenant) is False

        # Enable system
        SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
        assert AIConfig.is_ai_available_for_user(sample_user, sample_tenant) is False

        # Enable tenant
        sample_tenant.ai_features_enabled = True
        session.commit()
        assert AIConfig.is_ai_available_for_user(sample_user, sample_tenant) is True

        # User opts out
        sample_membership.ai_opt_out = True
        session.commit()
        assert AIConfig.is_ai_available_for_user(sample_user, sample_tenant) is False

    def test_is_slack_ai_available(self, app, session, sample_user, sample_tenant, sample_membership):
        """is_slack_ai_available checks user availability and slack enabled."""
        # Enable all at system level
        SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
        SystemConfig.set(SystemConfig.KEY_AI_SLACK_BOT_ENABLED, 'true')

        # Tenant not enabled
        assert AIConfig.is_slack_ai_available(sample_user, sample_tenant) is False

        # Enable tenant AI and Slack
        sample_tenant.ai_features_enabled = True
        sample_tenant.ai_slack_queries_enabled = True
        session.commit()
        assert AIConfig.is_slack_ai_available(sample_user, sample_tenant) is True

    def test_is_assisted_creation_available(self, app, session, sample_user, sample_tenant, sample_membership):
        """is_assisted_creation_available checks all levels."""
        SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
        SystemConfig.set(SystemConfig.KEY_AI_ASSISTED_CREATION_ENABLED, 'true')
        sample_tenant.ai_features_enabled = True
        sample_tenant.ai_assisted_creation_enabled = True
        session.commit()

        assert AIConfig.is_assisted_creation_available(sample_user, sample_tenant) is True

    def test_is_external_ai_available(self, app, session, sample_user, sample_tenant, sample_membership):
        """is_external_ai_available checks all levels."""
        SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
        SystemConfig.set(SystemConfig.KEY_AI_EXTERNAL_API_ENABLED, 'true')
        sample_tenant.ai_features_enabled = True
        sample_tenant.ai_external_access_enabled = True
        session.commit()

        assert AIConfig.is_external_ai_available(sample_user, sample_tenant) is True

    def test_is_mcp_available_system_level_only(self, app, session):
        """is_mcp_available only checks system level."""
        assert AIConfig.is_mcp_available() is False

        SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
        SystemConfig.set(SystemConfig.KEY_AI_MCP_SERVER_ENABLED, 'true')
        assert AIConfig.is_mcp_available() is True


# ============================================================================
# API KEY SERVICE TESTS
# ============================================================================

class TestAIApiKeyServiceKeyGeneration:
    """Test API key generation."""

    def test_generate_key_returns_string(self, app):
        """generate_key returns a string."""
        key = AIApiKeyService.generate_key()
        assert isinstance(key, str)

    def test_generate_key_has_correct_prefix(self, app):
        """generate_key starts with correct prefix."""
        key = AIApiKeyService.generate_key()
        assert key.startswith(AIApiKeyService.KEY_PREFIX)

    def test_generate_key_is_unique(self, app):
        """generate_key produces unique keys."""
        keys = [AIApiKeyService.generate_key() for _ in range(100)]
        assert len(keys) == len(set(keys))

    def test_generate_key_has_sufficient_length(self, app):
        """generate_key produces keys of sufficient length."""
        key = AIApiKeyService.generate_key()
        # Prefix + random part
        assert len(key) > 20


class TestAIApiKeyServiceHashing:
    """Test API key hashing."""

    def test_hash_key_returns_string(self, app):
        """hash_key returns a string."""
        key = AIApiKeyService.generate_key()
        hash_value = AIApiKeyService.hash_key(key)
        assert isinstance(hash_value, str)

    def test_hash_key_is_consistent(self, app):
        """hash_key produces same hash for same key."""
        key = AIApiKeyService.generate_key()
        hash1 = AIApiKeyService.hash_key(key)
        hash2 = AIApiKeyService.hash_key(key)
        assert hash1 == hash2

    def test_hash_key_is_different_for_different_keys(self, app):
        """hash_key produces different hashes for different keys."""
        key1 = AIApiKeyService.generate_key()
        key2 = AIApiKeyService.generate_key()
        hash1 = AIApiKeyService.hash_key(key1)
        hash2 = AIApiKeyService.hash_key(key2)
        assert hash1 != hash2

    def test_hash_key_length_is_64(self, app):
        """hash_key produces 64-character SHA256 hash."""
        key = AIApiKeyService.generate_key()
        hash_value = AIApiKeyService.hash_key(key)
        assert len(hash_value) == 64

    def test_get_key_prefix_returns_first_8_chars(self, app):
        """get_key_prefix returns first 8 characters."""
        key = 'adr_abcdefgh12345678'
        prefix = AIApiKeyService.get_key_prefix(key)
        assert prefix == 'adr_abcd'


class TestAIApiKeyServiceCreateKey:
    """Test API key creation."""

    def test_create_key_returns_tuple(self, app, session, sample_user, sample_tenant, sample_membership):
        """create_key returns tuple of (APIKey, full_key)."""
        api_key, full_key = AIApiKeyService.create_key(
            sample_user, sample_tenant, 'Test Key'
        )
        assert isinstance(api_key, AIApiKey)
        assert isinstance(full_key, str)

    def test_create_key_saves_to_database(self, app, session, sample_user, sample_tenant, sample_membership):
        """create_key saves the key to database."""
        api_key, _ = AIApiKeyService.create_key(
            sample_user, sample_tenant, 'Test Key'
        )
        assert api_key.id is not None

        found = db.session.get(AIApiKey, api_key.id)
        assert found is not None
        assert found.name == 'Test Key'

    def test_create_key_with_default_scopes(self, app, session, sample_user, sample_tenant, sample_membership):
        """create_key uses default scopes when not specified."""
        api_key, _ = AIApiKeyService.create_key(
            sample_user, sample_tenant, 'Test Key'
        )
        assert 'read' in api_key.scopes
        assert 'search' in api_key.scopes

    def test_create_key_with_custom_scopes(self, app, session, sample_user, sample_tenant, sample_membership):
        """create_key uses provided scopes."""
        api_key, _ = AIApiKeyService.create_key(
            sample_user, sample_tenant, 'Test Key',
            scopes=['read', 'write']
        )
        assert 'read' in api_key.scopes
        assert 'write' in api_key.scopes
        assert 'search' not in api_key.scopes

    def test_create_key_filters_invalid_scopes(self, app, session, sample_user, sample_tenant, sample_membership):
        """create_key filters out invalid scopes."""
        api_key, _ = AIApiKeyService.create_key(
            sample_user, sample_tenant, 'Test Key',
            scopes=['read', 'invalid_scope', 'admin']
        )
        assert 'read' in api_key.scopes
        assert 'invalid_scope' not in api_key.scopes
        assert 'admin' not in api_key.scopes

    def test_create_key_with_expiration(self, app, session, sample_user, sample_tenant, sample_membership):
        """create_key sets expiration when specified."""
        api_key, _ = AIApiKeyService.create_key(
            sample_user, sample_tenant, 'Test Key',
            expires_in_days=30
        )
        assert api_key.expires_at is not None
        # Check it's approximately 30 days from now (use naive UTC to match DB storage)
        expected = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=30)
        diff = abs((api_key.expires_at - expected).total_seconds())
        assert diff < 60  # Within 1 minute

    def test_create_key_without_expiration(self, app, session, sample_user, sample_tenant, sample_membership):
        """create_key has no expiration when not specified."""
        api_key, _ = AIApiKeyService.create_key(
            sample_user, sample_tenant, 'Test Key'
        )
        assert api_key.expires_at is None

    def test_create_key_stores_hash_not_key(self, app, session, sample_user, sample_tenant, sample_membership):
        """create_key stores hash, not the actual key."""
        api_key, full_key = AIApiKeyService.create_key(
            sample_user, sample_tenant, 'Test Key'
        )
        assert api_key.key_hash != full_key
        assert api_key.key_hash == AIApiKeyService.hash_key(full_key)


class TestAIApiKeyServiceValidation:
    """Test API key validation."""

    def test_validate_key_returns_key_for_valid(self, app, session, sample_user, sample_tenant, sample_membership):
        """validate_key returns APIKey for valid key."""
        api_key, full_key = AIApiKeyService.create_key(
            sample_user, sample_tenant, 'Test Key'
        )
        validated = AIApiKeyService.validate_key(full_key)
        assert validated is not None
        assert validated.id == api_key.id

    def test_validate_key_returns_none_for_invalid(self, app, session):
        """validate_key returns None for invalid key."""
        validated = AIApiKeyService.validate_key('adr_invalid_key_12345')
        assert validated is None

    def test_validate_key_returns_none_for_wrong_prefix(self, app, session):
        """validate_key returns None for key with wrong prefix."""
        validated = AIApiKeyService.validate_key('wrong_prefix_key')
        assert validated is None

    def test_validate_key_returns_none_for_empty(self, app, session):
        """validate_key returns None for empty key."""
        assert AIApiKeyService.validate_key('') is None
        assert AIApiKeyService.validate_key(None) is None

    def test_validate_key_returns_none_for_expired(self, app, session, sample_user, sample_tenant, sample_membership):
        """validate_key returns None for expired key."""
        api_key, full_key = AIApiKeyService.create_key(
            sample_user, sample_tenant, 'Test Key',
            expires_in_days=1
        )
        # Manually set expiry to past
        api_key.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        session.commit()

        validated = AIApiKeyService.validate_key(full_key)
        assert validated is None

    def test_validate_key_returns_none_for_revoked(self, app, session, sample_user, sample_tenant, sample_membership):
        """validate_key returns None for revoked key."""
        api_key, full_key = AIApiKeyService.create_key(
            sample_user, sample_tenant, 'Test Key'
        )
        AIApiKeyService.revoke_key(api_key)

        validated = AIApiKeyService.validate_key(full_key)
        assert validated is None

    def test_validate_key_updates_last_used(self, app, session, sample_user, sample_tenant, sample_membership):
        """validate_key updates last_used_at timestamp."""
        api_key, full_key = AIApiKeyService.create_key(
            sample_user, sample_tenant, 'Test Key'
        )
        original_last_used = api_key.last_used_at

        AIApiKeyService.validate_key(full_key)
        session.refresh(api_key)

        assert api_key.last_used_at is not None
        if original_last_used:
            assert api_key.last_used_at > original_last_used


class TestAIApiKeyServiceScopes:
    """Test API key scope checking."""

    def test_has_scope_returns_true_for_valid_scope(self, app, session, sample_user, sample_tenant, sample_membership):
        """has_scope returns True when key has the scope."""
        api_key, _ = AIApiKeyService.create_key(
            sample_user, sample_tenant, 'Test Key',
            scopes=['read', 'write']
        )
        assert AIApiKeyService.has_scope(api_key, 'read') is True
        assert AIApiKeyService.has_scope(api_key, 'write') is True

    def test_has_scope_returns_false_for_missing_scope(self, app, session, sample_user, sample_tenant, sample_membership):
        """has_scope returns False when key lacks the scope."""
        api_key, _ = AIApiKeyService.create_key(
            sample_user, sample_tenant, 'Test Key',
            scopes=['read']
        )
        assert AIApiKeyService.has_scope(api_key, 'write') is False
        assert AIApiKeyService.has_scope(api_key, 'search') is False


class TestAIApiKeyServiceListAndManage:
    """Test API key listing and management."""

    def test_list_user_keys_returns_user_keys(self, app, session, sample_user, sample_tenant, sample_membership):
        """list_user_keys returns all keys for a user."""
        AIApiKeyService.create_key(sample_user, sample_tenant, 'Key 1')
        AIApiKeyService.create_key(sample_user, sample_tenant, 'Key 2')
        AIApiKeyService.create_key(sample_user, sample_tenant, 'Key 3')

        keys = AIApiKeyService.list_user_keys(sample_user, sample_tenant)
        assert len(keys) == 3

    def test_list_user_keys_excludes_revoked_by_default(self, app, session, sample_user, sample_tenant, sample_membership):
        """list_user_keys excludes revoked keys by default."""
        api_key1, _ = AIApiKeyService.create_key(sample_user, sample_tenant, 'Key 1')
        AIApiKeyService.create_key(sample_user, sample_tenant, 'Key 2')
        AIApiKeyService.revoke_key(api_key1)

        keys = AIApiKeyService.list_user_keys(sample_user, sample_tenant)
        assert len(keys) == 1

    def test_list_user_keys_includes_revoked_when_specified(self, app, session, sample_user, sample_tenant, sample_membership):
        """list_user_keys includes revoked keys when specified."""
        api_key1, _ = AIApiKeyService.create_key(sample_user, sample_tenant, 'Key 1')
        AIApiKeyService.create_key(sample_user, sample_tenant, 'Key 2')
        AIApiKeyService.revoke_key(api_key1)

        keys = AIApiKeyService.list_user_keys(sample_user, sample_tenant, include_revoked=True)
        assert len(keys) == 2

    def test_revoke_key_sets_revoked_at(self, app, session, sample_user, sample_tenant, sample_membership):
        """revoke_key sets revoked_at timestamp."""
        api_key, _ = AIApiKeyService.create_key(sample_user, sample_tenant, 'Test Key')
        assert api_key.revoked_at is None

        AIApiKeyService.revoke_key(api_key)
        session.refresh(api_key)
        assert api_key.revoked_at is not None

    def test_get_key_by_id_returns_key_for_owner(self, app, session, sample_user, sample_tenant, sample_membership):
        """get_key_by_id returns key when user is owner."""
        api_key, _ = AIApiKeyService.create_key(sample_user, sample_tenant, 'Test Key')
        found = AIApiKeyService.get_key_by_id(api_key.id, sample_user)
        assert found is not None
        assert found.id == api_key.id

    def test_get_key_by_id_returns_none_for_non_owner(self, app, session, sample_user, sample_tenant, sample_membership, admin_user):
        """get_key_by_id returns None when user is not owner."""
        api_key, _ = AIApiKeyService.create_key(sample_user, sample_tenant, 'Test Key')
        found = AIApiKeyService.get_key_by_id(api_key.id, admin_user)
        assert found is None


class TestAIApiKeyServiceSerialization:
    """Test API key serialization."""

    def test_serialize_key_includes_required_fields(self, app, session, sample_user, sample_tenant, sample_membership):
        """serialize_key includes all required fields."""
        api_key, _ = AIApiKeyService.create_key(sample_user, sample_tenant, 'Test Key')
        serialized = AIApiKeyService.serialize_key(api_key)

        assert 'id' in serialized
        assert 'name' in serialized
        assert 'key_prefix' in serialized
        assert 'scopes' in serialized
        assert 'created_at' in serialized
        assert 'is_revoked' in serialized
        assert 'is_expired' in serialized

    def test_serialize_key_does_not_include_hash(self, app, session, sample_user, sample_tenant, sample_membership):
        """serialize_key does not expose key hash."""
        api_key, _ = AIApiKeyService.create_key(sample_user, sample_tenant, 'Test Key')
        serialized = AIApiKeyService.serialize_key(api_key)

        assert 'key_hash' not in serialized


# ============================================================================
# INTERACTION LOGGER TESTS
# ============================================================================

class TestAIInteractionLoggerBasicLogging:
    """Test basic AI interaction logging."""

    def test_log_interaction_creates_entry(self, app, session, sample_tenant, sample_user, sample_membership):
        """log_interaction creates a log entry."""
        log = AIInteractionLogger.log_interaction(
            channel=AIChannel.SLACK,
            action=AIAction.SEARCH,
            tenant_id=sample_tenant.id,
            user_id=sample_user.id,
            query_text='Find authentication decisions'
        )

        assert log.id is not None
        assert log.tenant_id == sample_tenant.id
        assert log.user_id == sample_user.id
        assert log.channel == AIChannel.SLACK
        assert log.action == AIAction.SEARCH

    def test_log_interaction_with_all_fields(self, app, session, sample_tenant, sample_user, sample_membership):
        """log_interaction accepts all optional fields."""
        log = AIInteractionLogger.log_interaction(
            channel=AIChannel.API,
            action=AIAction.SUMMARIZE,
            tenant_id=sample_tenant.id,
            user_id=sample_user.id,
            query_text='Summarize decision',
            decision_ids=[1, 2, 3],
            llm_provider='openai',
            llm_model='gpt-4o',
            tokens_input=100,
            tokens_output=200,
            duration_ms=500
        )

        assert log.channel == AIChannel.API
        assert log.action == AIAction.SUMMARIZE
        assert log.llm_provider == 'openai'
        assert log.llm_model == 'gpt-4o'
        assert log.tokens_input == 100
        assert log.tokens_output == 200
        assert log.duration_ms == 500
        assert log.decision_ids == [1, 2, 3]

    def test_log_interaction_without_user(self, app, session, sample_tenant):
        """log_interaction works without user_id (for API access)."""
        log = AIInteractionLogger.log_interaction(
            channel=AIChannel.API,
            action=AIAction.READ,
            tenant_id=sample_tenant.id,
            user_id=None
        )

        assert log.id is not None
        assert log.user_id is None
        assert log.tenant_id == sample_tenant.id
        assert log.channel == AIChannel.API
        assert log.action == AIAction.READ


class TestAIInteractionLoggerConvenienceMethods:
    """Test convenience logging methods."""

    def test_log_search(self, app, session, sample_tenant, sample_user, sample_membership):
        """log_search creates a search log entry."""
        log = AIInteractionLogger.log_search(
            channel=AIChannel.SLACK,
            tenant_id=sample_tenant.id,
            query_text='Find decisions about caching',
            decision_ids=[1, 2, 3],
            user_id=sample_user.id,
            duration_ms=150
        )

        assert log.action == AIAction.SEARCH
        assert log.channel == AIChannel.SLACK
        assert log.query_text == 'Find decisions about caching'
        assert log.decision_ids == [1, 2, 3]

    def test_log_read(self, app, session, sample_tenant, sample_user, sample_membership):
        """log_read creates a read log entry."""
        log = AIInteractionLogger.log_read(
            channel=AIChannel.MCP,
            tenant_id=sample_tenant.id,
            decision_id=42,
            user_id=sample_user.id
        )

        assert log.action == AIAction.READ
        assert log.channel == AIChannel.MCP
        assert log.decision_ids == [42]

    def test_log_create(self, app, session, sample_tenant, sample_user, sample_membership):
        """log_create creates a create log entry."""
        log = AIInteractionLogger.log_create(
            channel=AIChannel.WEB,
            tenant_id=sample_tenant.id,
            decision_id=99,
            user_id=sample_user.id,
            llm_provider='anthropic',
            llm_model='claude-3-sonnet',
            tokens_input=500,
            tokens_output=1000
        )

        assert log.action == AIAction.CREATE
        assert log.channel == AIChannel.WEB
        assert log.decision_ids == [99]
        assert log.llm_provider == 'anthropic'
        assert log.llm_model == 'claude-3-sonnet'

    def test_log_summarize(self, app, session, sample_tenant, sample_user, sample_membership):
        """log_summarize creates a summarize log entry."""
        log = AIInteractionLogger.log_summarize(
            channel=AIChannel.API,
            tenant_id=sample_tenant.id,
            decision_id=123,
            user_id=sample_user.id,
            llm_provider='openai',
            llm_model='gpt-4o',
            tokens_input=1000,
            tokens_output=200
        )

        assert log.action == AIAction.SUMMARIZE
        assert log.channel == AIChannel.API
        assert log.decision_ids == [123]


class TestAIInteractionLoggerQuery:
    """Test querying AI interaction logs."""

    def test_get_tenant_logs_returns_logs(self, app, session, sample_tenant, sample_user, sample_membership):
        """get_tenant_logs returns logs for a tenant."""
        # Create some logs
        for i in range(5):
            AIInteractionLogger.log_search(
                channel=AIChannel.SLACK,
                tenant_id=sample_tenant.id,
                query_text=f'Query {i}',
                decision_ids=[],
                user_id=sample_user.id
            )

        logs = AIInteractionLogger.get_tenant_logs(sample_tenant.id)
        assert len(logs) == 5

    def test_get_tenant_logs_respects_limit(self, app, session, sample_tenant, sample_user, sample_membership):
        """get_tenant_logs respects limit parameter."""
        for i in range(10):
            AIInteractionLogger.log_search(
                channel=AIChannel.SLACK,
                tenant_id=sample_tenant.id,
                query_text=f'Query {i}',
                decision_ids=[],
                user_id=sample_user.id
            )

        logs = AIInteractionLogger.get_tenant_logs(sample_tenant.id, limit=5)
        assert len(logs) == 5

    def test_get_tenant_logs_filter_by_channel(self, app, session, sample_tenant, sample_user, sample_membership):
        """get_tenant_logs filters by channel."""
        AIInteractionLogger.log_search(
            channel=AIChannel.SLACK,
            tenant_id=sample_tenant.id,
            query_text='Slack query',
            decision_ids=[],
            user_id=sample_user.id
        )
        AIInteractionLogger.log_search(
            channel=AIChannel.API,
            tenant_id=sample_tenant.id,
            query_text='API query',
            decision_ids=[],
            user_id=sample_user.id
        )

        slack_logs = AIInteractionLogger.get_tenant_logs(
            sample_tenant.id, channel=AIChannel.SLACK
        )
        assert len(slack_logs) == 1
        assert slack_logs[0].channel == AIChannel.SLACK

    def test_get_tenant_logs_filter_by_action(self, app, session, sample_tenant, sample_user, sample_membership):
        """get_tenant_logs filters by action."""
        AIInteractionLogger.log_search(
            channel=AIChannel.SLACK,
            tenant_id=sample_tenant.id,
            query_text='Search',
            decision_ids=[],
            user_id=sample_user.id
        )
        AIInteractionLogger.log_read(
            channel=AIChannel.API,
            tenant_id=sample_tenant.id,
            decision_id=1,
            user_id=sample_user.id
        )

        search_logs = AIInteractionLogger.get_tenant_logs(
            sample_tenant.id, action=AIAction.SEARCH
        )
        assert len(search_logs) == 1
        assert search_logs[0].action == AIAction.SEARCH

    def test_get_user_logs(self, app, session, sample_tenant, sample_user, sample_membership, admin_user):
        """get_user_logs returns logs for a specific user."""
        # Log for sample_user
        AIInteractionLogger.log_search(
            channel=AIChannel.SLACK,
            tenant_id=sample_tenant.id,
            query_text='User query',
            decision_ids=[],
            user_id=sample_user.id
        )

        # admin_user needs membership
        admin_membership = TenantMembership.query.filter_by(
            user_id=admin_user.id, tenant_id=sample_tenant.id
        ).first()

        # Log for admin_user
        AIInteractionLogger.log_search(
            channel=AIChannel.SLACK,
            tenant_id=sample_tenant.id,
            query_text='Admin query',
            decision_ids=[],
            user_id=admin_user.id
        )

        user_logs = AIInteractionLogger.get_user_logs(sample_user.id, sample_tenant.id)
        assert len(user_logs) == 1
        assert user_logs[0].user_id == sample_user.id


class TestAIInteractionLoggerStats:
    """Test AI interaction statistics."""

    def test_get_tenant_stats_returns_dict(self, app, session, sample_tenant, sample_user, sample_membership):
        """get_tenant_stats returns a dictionary with stats."""
        AIInteractionLogger.log_search(
            channel=AIChannel.SLACK,
            tenant_id=sample_tenant.id,
            query_text='Query',
            decision_ids=[],
            user_id=sample_user.id
        )

        stats = AIInteractionLogger.get_tenant_stats(sample_tenant.id)

        assert isinstance(stats, dict)
        assert 'total_interactions' in stats
        assert 'unique_users' in stats
        assert 'by_channel' in stats
        assert 'by_action' in stats
        assert 'total_tokens' in stats

    def test_get_tenant_stats_counts_correctly(self, app, session, sample_tenant, sample_user, sample_membership):
        """get_tenant_stats calculates correct counts."""
        # Create various interactions
        AIInteractionLogger.log_search(
            channel=AIChannel.SLACK,
            tenant_id=sample_tenant.id,
            query_text='Query 1',
            decision_ids=[],
            user_id=sample_user.id
        )
        AIInteractionLogger.log_search(
            channel=AIChannel.API,
            tenant_id=sample_tenant.id,
            query_text='Query 2',
            decision_ids=[],
            user_id=sample_user.id
        )
        AIInteractionLogger.log_read(
            channel=AIChannel.SLACK,
            tenant_id=sample_tenant.id,
            decision_id=1,
            user_id=sample_user.id
        )

        stats = AIInteractionLogger.get_tenant_stats(sample_tenant.id)

        assert stats['total_interactions'] == 3
        assert stats['unique_users'] == 1

    def test_get_tenant_stats_sums_tokens(self, app, session, sample_tenant, sample_user, sample_membership):
        """get_tenant_stats sums token usage correctly."""
        AIInteractionLogger.log_interaction(
            channel=AIChannel.WEB,
            action=AIAction.SUMMARIZE,
            tenant_id=sample_tenant.id,
            user_id=sample_user.id,
            tokens_input=100,
            tokens_output=50
        )
        AIInteractionLogger.log_interaction(
            channel=AIChannel.WEB,
            action=AIAction.CREATE,
            tenant_id=sample_tenant.id,
            user_id=sample_user.id,
            tokens_input=200,
            tokens_output=100
        )

        stats = AIInteractionLogger.get_tenant_stats(sample_tenant.id)

        assert stats['total_tokens_input'] == 300
        assert stats['total_tokens_output'] == 150
        assert stats['total_tokens'] == 450

    def test_get_tenant_stats_with_date_range(self, app, session, sample_tenant, sample_user, sample_membership):
        """get_tenant_stats respects date range filter."""
        # Create a log
        AIInteractionLogger.log_search(
            channel=AIChannel.SLACK,
            tenant_id=sample_tenant.id,
            query_text='Query',
            decision_ids=[],
            user_id=sample_user.id
        )

        # Future date range should return zero
        start = datetime.now(timezone.utc) + timedelta(days=1)
        end = datetime.now(timezone.utc) + timedelta(days=2)
        stats = AIInteractionLogger.get_tenant_stats(sample_tenant.id, start_date=start, end_date=end)

        assert stats['total_interactions'] == 0


class TestAIInteractionLoggerSerialization:
    """Test log serialization."""

    def test_serialize_log_includes_required_fields(self, app, session, sample_tenant, sample_user, sample_membership):
        """serialize_log includes all required fields."""
        log = AIInteractionLogger.log_search(
            channel=AIChannel.SLACK,
            tenant_id=sample_tenant.id,
            query_text='Test query',
            decision_ids=[1, 2],
            user_id=sample_user.id
        )

        serialized = AIInteractionLogger.serialize_log(log)

        assert 'id' in serialized
        assert 'channel' in serialized
        assert 'action' in serialized
        assert 'query_text' in serialized
        assert 'decision_ids' in serialized
        assert 'created_at' in serialized


# ============================================================================
# AI API KEY MODEL TESTS
# ============================================================================

class TestAIApiKeyModel:
    """Test AIApiKey model methods."""

    def test_is_valid_returns_true_for_active_key(self, app, session, sample_user, sample_tenant, sample_membership):
        """is_valid returns True for active key."""
        api_key, _ = AIApiKeyService.create_key(sample_user, sample_tenant, 'Test Key')
        assert api_key.is_valid is True

    def test_is_valid_returns_false_for_revoked_key(self, app, session, sample_user, sample_tenant, sample_membership):
        """is_valid returns False for revoked key."""
        api_key, _ = AIApiKeyService.create_key(sample_user, sample_tenant, 'Test Key')
        api_key.revoked_at = datetime.now(timezone.utc)
        session.commit()
        assert api_key.is_valid is False

    def test_is_valid_returns_false_for_expired_key(self, app, session, sample_user, sample_tenant, sample_membership):
        """is_valid returns False for expired key."""
        api_key, _ = AIApiKeyService.create_key(
            sample_user, sample_tenant, 'Test Key',
            expires_in_days=1
        )
        # Use timezone-naive datetime to match DB storage
        api_key.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
        session.commit()
        assert api_key.is_valid is False

    def test_display_key_shows_prefix_with_ellipsis(self, app, session, sample_user, sample_tenant, sample_membership):
        """display_key shows prefix with ellipsis."""
        api_key, _ = AIApiKeyService.create_key(sample_user, sample_tenant, 'Test Key')
        assert api_key.display_key.endswith('...')
        assert api_key.key_prefix in api_key.display_key

    def test_has_scope_method(self, app, session, sample_user, sample_tenant, sample_membership):
        """has_scope checks scope membership."""
        api_key, _ = AIApiKeyService.create_key(
            sample_user, sample_tenant, 'Test Key',
            scopes=['read', 'search']
        )
        assert api_key.has_scope('read') is True
        assert api_key.has_scope('search') is True
        assert api_key.has_scope('write') is False

    def test_revoke_method(self, app, session, sample_user, sample_tenant, sample_membership):
        """revoke sets revoked_at timestamp."""
        api_key, _ = AIApiKeyService.create_key(sample_user, sample_tenant, 'Test Key')
        assert api_key.revoked_at is None

        api_key.revoke()
        assert api_key.revoked_at is not None

    def test_to_dict_method(self, app, session, sample_user, sample_tenant, sample_membership):
        """to_dict serializes key correctly."""
        api_key, _ = AIApiKeyService.create_key(sample_user, sample_tenant, 'Test Key')
        data = api_key.to_dict()

        assert 'id' in data
        assert 'name' in data
        assert 'key_prefix' in data
        assert 'scopes' in data
        assert 'is_valid' in data

    def test_to_dict_with_sensitive_includes_extra_fields(self, app, session, sample_user, sample_tenant, sample_membership):
        """to_dict with include_sensitive adds user_id and tenant_id."""
        api_key, _ = AIApiKeyService.create_key(sample_user, sample_tenant, 'Test Key')
        data = api_key.to_dict(include_sensitive=True)

        assert 'user_id' in data
        assert 'tenant_id' in data
        assert data['user_id'] == sample_user.id
        assert data['tenant_id'] == sample_tenant.id


# ============================================================================
# AI INTERACTION LOG MODEL TESTS
# ============================================================================

class TestAIInteractionLogModel:
    """Test AIInteractionLog model methods."""

    def test_to_dict_method(self, app, session, sample_tenant, sample_user, sample_membership):
        """to_dict serializes log correctly."""
        log = AIInteractionLogger.log_search(
            channel=AIChannel.SLACK,
            tenant_id=sample_tenant.id,
            query_text='Test query',
            decision_ids=[1, 2, 3],
            user_id=sample_user.id
        )
        data = log.to_dict()

        assert 'id' in data
        assert 'channel' in data
        assert 'action' in data
        assert 'query_text' in data
        assert 'decision_ids' in data
        assert 'created_at' in data
        # to_dict converts enums to string values
        assert data['channel'] == 'slack'
        assert data['action'] == 'search'
        assert data['query_text'] == 'Test query'


# ============================================================================
# EDGE CASE TESTS
# ============================================================================

class TestAIConfigEdgeCases:
    """Test edge cases in AI configuration."""

    def test_case_insensitive_config_values(self, app, session):
        """Config values are case-insensitive for boolean checks."""
        SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'TRUE')
        assert AIConfig.get_system_ai_enabled() is True

        SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'True')
        assert AIConfig.get_system_ai_enabled() is True

        SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'FALSE')
        assert AIConfig.get_system_ai_enabled() is False

    def test_null_tenant_ai_fields(self, app, session, sample_tenant):
        """Handles null tenant AI fields gracefully."""
        # Explicitly set to None (should use defaults)
        sample_tenant.ai_features_enabled = None
        session.commit()

        # Should not raise and treat as falsy
        assert AIConfig.get_tenant_ai_enabled(sample_tenant) is False


class TestAIApiKeyEdgeCases:
    """Test edge cases in API key service."""

    def test_create_key_with_empty_scopes(self, app, session, sample_user, sample_tenant, sample_membership):
        """Creating key with empty scopes uses defaults."""
        api_key, _ = AIApiKeyService.create_key(
            sample_user, sample_tenant, 'Test Key',
            scopes=[]
        )
        # Empty scopes should result in empty list, not default
        assert api_key.scopes == []

    def test_validate_key_with_special_characters(self, app, session):
        """validate_key handles special characters safely."""
        # These should not cause errors
        assert AIApiKeyService.validate_key("adr_<script>alert('xss')</script>") is None
        assert AIApiKeyService.validate_key("adr_'; DROP TABLE users; --") is None


class TestAIInteractionLogEdgeCases:
    """Test edge cases in interaction logging."""

    def test_log_with_empty_decision_ids(self, app, session, sample_tenant, sample_user, sample_membership):
        """Logging with empty decision_ids works correctly."""
        log = AIInteractionLogger.log_search(
            channel=AIChannel.SLACK,
            tenant_id=sample_tenant.id,
            query_text='Query',
            decision_ids=[],
            user_id=sample_user.id
        )
        assert log.decision_ids == []

    def test_log_with_none_query_text(self, app, session, sample_tenant, sample_user, sample_membership):
        """Logging with None query_text works correctly."""
        log = AIInteractionLogger.log_read(
            channel=AIChannel.API,
            tenant_id=sample_tenant.id,
            decision_id=1,
            user_id=sample_user.id
        )
        assert log.query_text is None

    def test_stats_with_no_logs(self, app, session, sample_tenant):
        """get_tenant_stats handles empty log set."""
        stats = AIInteractionLogger.get_tenant_stats(sample_tenant.id)
        assert stats['total_interactions'] == 0
        assert stats['unique_users'] == 0
        assert stats['total_tokens'] == 0


# ============================================================================
# SUPER ADMIN AI SETTINGS API TESTS
# ============================================================================

# These tests use the api_app fixture pattern from test_api_integration.py
# to test the actual HTTP endpoints with all routes registered.

from models import MasterAccount, DEFAULT_MASTER_USERNAME, DEFAULT_MASTER_PASSWORD


@pytest.fixture(scope='function')
def api_app():
    """Create application with actual routes for API testing.

    Unlike the base conftest.py app fixture, this imports the actual app
    with all routes registered, so we can test the full HTTP cycle.
    """
    # Set testing environment BEFORE importing app
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['TESTING'] = 'True'
    os.environ['FLASK_SECRET_KEY'] = 'test-secret-key-for-ai-api-tests-12345'

    # Import app module to get the configured Flask app
    import app as app_module
    test_app = app_module.app

    # Reset the global _db_initialized flag to ensure proper initialization
    app_module._db_initialized = False

    # Ensure testing mode is on and relax session cookie settings for testing
    test_app.config['TESTING'] = True
    test_app.config['SECRET_KEY'] = 'test-secret-key-for-ai-api-tests-12345'
    test_app.config['SESSION_COOKIE_SAMESITE'] = None
    test_app.config['SESSION_COOKIE_HTTPONLY'] = False

    with test_app.app_context():
        db.create_all()
        app_module.init_database()
        yield test_app
        db.session.remove()
        db.drop_all()
        app_module._db_initialized = False


@pytest.fixture
def api_client(api_app):
    """Create test client for making HTTP requests."""
    return api_app.test_client()


@pytest.fixture
def master_account(api_app):
    """Get the default master account created by initialize_database()."""
    master = MasterAccount.query.filter_by(username=DEFAULT_MASTER_USERNAME).first()
    if not master:
        master = MasterAccount(
            username=DEFAULT_MASTER_USERNAME,
            name='System Administrator'
        )
        master.set_password('changeme')
        db.session.add(master)
        db.session.commit()
    return master


@pytest.fixture
def master_client(api_app, master_account):
    """Create authenticated client for master account."""
    client = api_app.test_client()

    # Authenticate via the actual login endpoint
    response = client.post('/auth/local', json={
        'username': master_account.username,
        'password': DEFAULT_MASTER_PASSWORD
    })

    if response.status_code != 200:
        raise RuntimeError(f"Master login failed: {response.status_code} - {response.data}")

    return client


@pytest.fixture
def api_test_tenant(api_app):
    """Create a test tenant for API tests."""
    tenant = Tenant(
        domain='apitest.com',
        name='API Test Corp',
        status='active',
        maturity_state=MaturityState.BOOTSTRAP
    )
    db.session.add(tenant)
    db.session.commit()
    return tenant


@pytest.fixture
def api_test_user(api_app, api_test_tenant):
    """Create a regular test user for API tests."""
    user = User(
        email='user@apitest.com',
        sso_domain='apitest.com',
        auth_type='local',
        email_verified=True
    )
    user.set_name(first_name='Test', last_name='User')
    user.set_password('testpassword123')
    db.session.add(user)
    db.session.flush()

    membership = TenantMembership(
        user_id=user.id,
        tenant_id=api_test_tenant.id,
        global_role=GlobalRole.USER
    )
    db.session.add(membership)
    db.session.commit()
    return user


@pytest.fixture
def user_client(api_app, api_test_user):
    """Create authenticated client for regular user."""
    client = api_app.test_client()

    # Regular users login via /api/auth/login endpoint
    response = client.post('/api/auth/login', json={
        'email': api_test_user.email,
        'password': 'testpassword123'
    })

    if response.status_code != 200:
        raise RuntimeError(f"User login failed: {response.status_code} - {response.data}")

    return client


class TestSuperAdminAISettingsAPI:
    """Test super admin AI settings endpoints (/api/admin/settings/ai)."""

    def test_get_ai_settings_requires_auth(self, api_client):
        """GET /api/admin/settings/ai requires authentication."""
        response = api_client.get('/api/admin/settings/ai')
        assert response.status_code == 401

    def test_get_ai_settings_requires_master(self, user_client):
        """GET /api/admin/settings/ai requires master account."""
        response = user_client.get('/api/admin/settings/ai')
        assert response.status_code == 403

    def test_get_ai_settings_success(self, master_client):
        """GET /api/admin/settings/ai returns settings for master user."""
        response = master_client.get('/api/admin/settings/ai')
        assert response.status_code == 200

        data = response.get_json()
        assert 'ai_features_enabled' in data
        assert 'external_api_enabled' in data
        assert 'mcp_server_enabled' in data
        assert 'slack_bot_enabled' in data

        # Default values should be False
        assert data['ai_features_enabled'] is False
        assert data['external_api_enabled'] is False
        assert data['mcp_server_enabled'] is False
        assert data['slack_bot_enabled'] is False

    def test_save_ai_settings_requires_auth(self, api_client):
        """POST /api/admin/settings/ai requires authentication."""
        response = api_client.post('/api/admin/settings/ai', json={
            'ai_features_enabled': True
        })
        assert response.status_code == 401

    def test_save_ai_settings_requires_master(self, user_client):
        """POST /api/admin/settings/ai requires master account."""
        response = user_client.post('/api/admin/settings/ai', json={
            'ai_features_enabled': True
        })
        assert response.status_code == 403

    def test_save_ai_settings_enable_all(self, master_client):
        """POST /api/admin/settings/ai can enable all AI features."""
        response = master_client.post('/api/admin/settings/ai', json={
            'ai_features_enabled': True,
            'external_api_enabled': True,
            'mcp_server_enabled': True,
            'slack_bot_enabled': True
        })
        assert response.status_code == 200

        data = response.get_json()
        assert data['message'] == 'AI settings updated successfully'
        assert data['ai_features_enabled'] is True
        assert data['external_api_enabled'] is True
        assert data['mcp_server_enabled'] is True
        assert data['slack_bot_enabled'] is True

        # Verify settings are persisted
        response = master_client.get('/api/admin/settings/ai')
        data = response.get_json()
        assert data['ai_features_enabled'] is True
        assert data['external_api_enabled'] is True
        assert data['mcp_server_enabled'] is True
        assert data['slack_bot_enabled'] is True

    def test_save_ai_settings_disable_all(self, master_client):
        """POST /api/admin/settings/ai can disable all AI features."""
        # First enable all
        master_client.post('/api/admin/settings/ai', json={
            'ai_features_enabled': True,
            'external_api_enabled': True,
            'mcp_server_enabled': True,
            'slack_bot_enabled': True
        })

        # Then disable all
        response = master_client.post('/api/admin/settings/ai', json={
            'ai_features_enabled': False,
            'external_api_enabled': False,
            'mcp_server_enabled': False,
            'slack_bot_enabled': False
        })
        assert response.status_code == 200

        data = response.get_json()
        assert data['ai_features_enabled'] is False
        assert data['external_api_enabled'] is False
        assert data['mcp_server_enabled'] is False
        assert data['slack_bot_enabled'] is False

    def test_save_ai_settings_partial_update(self, master_client):
        """POST /api/admin/settings/ai can update individual settings."""
        # Enable only ai_features_enabled
        response = master_client.post('/api/admin/settings/ai', json={
            'ai_features_enabled': True
        })
        assert response.status_code == 200

        data = response.get_json()
        assert data['ai_features_enabled'] is True
        # Others should still be false (their default)
        assert data['external_api_enabled'] is False

        # Now enable external_api_enabled separately
        response = master_client.post('/api/admin/settings/ai', json={
            'external_api_enabled': True
        })
        assert response.status_code == 200

        data = response.get_json()
        # Both should now be true
        assert data['ai_features_enabled'] is True
        assert data['external_api_enabled'] is True

    def test_put_method_also_works(self, master_client):
        """PUT /api/admin/settings/ai works the same as POST."""
        response = master_client.put('/api/admin/settings/ai', json={
            'ai_features_enabled': True,
            'mcp_server_enabled': True
        })
        assert response.status_code == 200

        data = response.get_json()
        assert data['ai_features_enabled'] is True
        assert data['mcp_server_enabled'] is True


class TestTenantAdminAISettingsAPI:
    """Test tenant admin AI settings endpoints (/api/tenant/ai/config)."""

    @pytest.fixture
    def admin_test_tenant(self, api_app):
        """Create a test tenant with admin user for AI tests."""
        tenant = Tenant(
            domain='admintest.com',
            name='Admin Test Corp',
            status='active',
            maturity_state=MaturityState.BOOTSTRAP
        )
        db.session.add(tenant)
        db.session.commit()
        return tenant

    @pytest.fixture
    def admin_test_user(self, api_app, admin_test_tenant):
        """Create an admin user for tenant AI settings tests."""
        user = User(
            email='admin@admintest.com',
            sso_domain='admintest.com',
            auth_type='local',
            email_verified=True
        )
        user.set_name(first_name='Admin', last_name='User')
        user.set_password('adminpassword123')
        db.session.add(user)
        db.session.flush()

        membership = TenantMembership(
            user_id=user.id,
            tenant_id=admin_test_tenant.id,
            global_role=GlobalRole.ADMIN
        )
        db.session.add(membership)
        db.session.commit()
        return user

    @pytest.fixture
    def admin_client(self, api_app, admin_test_user):
        """Create authenticated client for admin user."""
        client = api_app.test_client()

        response = client.post('/api/auth/login', json={
            'email': admin_test_user.email,
            'password': 'adminpassword123'
        })

        if response.status_code != 200:
            raise RuntimeError(f"Admin login failed: {response.status_code} - {response.data}")

        return client

    def test_get_tenant_ai_config_requires_auth(self, api_client):
        """GET /api/tenant/ai/config requires authentication."""
        response = api_client.get('/api/tenant/ai/config')
        assert response.status_code == 401

    def test_get_tenant_ai_config_requires_admin(self, user_client):
        """GET /api/tenant/ai/config requires admin role."""
        response = user_client.get('/api/tenant/ai/config')
        assert response.status_code == 403

    def test_get_tenant_ai_config_success(self, admin_client):
        """GET /api/tenant/ai/config returns config for admin."""
        response = admin_client.get('/api/tenant/ai/config')
        assert response.status_code == 200

        data = response.get_json()
        # Check flat structure with system-level settings
        assert 'system_ai_enabled' in data
        assert 'system_slack_bot_enabled' in data
        assert 'system_external_api_enabled' in data
        # Check tenant-level settings
        assert 'ai_features_enabled' in data
        assert 'ai_slack_queries_enabled' in data

    def test_update_tenant_ai_config_requires_auth(self, api_client):
        """POST /api/tenant/ai/config requires authentication."""
        response = api_client.post('/api/tenant/ai/config', json={
            'ai_features_enabled': True
        })
        assert response.status_code == 401

    def test_update_tenant_ai_config_requires_admin(self, user_client):
        """POST /api/tenant/ai/config requires admin role."""
        response = user_client.post('/api/tenant/ai/config', json={
            'ai_features_enabled': True
        })
        assert response.status_code == 403

    def test_update_tenant_ai_config_requires_system_enabled(self, admin_client):
        """POST /api/tenant/ai/config fails if system AI is disabled."""
        # System AI is disabled by default
        response = admin_client.post('/api/tenant/ai/config', json={
            'ai_features_enabled': True
        })
        assert response.status_code == 403
        data = response.get_json()
        assert 'system level' in data['error'].lower()

    def test_update_tenant_ai_config_success(self, api_app, admin_client, master_client):
        """POST /api/tenant/ai/config can update tenant settings when system AI is enabled."""
        # First enable system-level AI as super admin
        response = master_client.post('/api/admin/settings/ai', json={
            'ai_features_enabled': True,
            'external_api_enabled': True,
            'slack_bot_enabled': True
        })
        assert response.status_code == 200

        # Now tenant admin can enable tenant-level settings
        response = admin_client.post('/api/tenant/ai/config', json={
            'ai_features_enabled': True,
            'ai_external_access_enabled': True
        })
        assert response.status_code == 200

        data = response.get_json()
        # Check the message is present (may vary slightly)
        assert 'message' in data
        assert 'updated' in data['message'].lower()
        # Config values are in nested 'config' object
        assert data['config']['ai_features_enabled'] is True
        assert data['config']['ai_external_access_enabled'] is True

    def test_update_tenant_ai_config_partial_update(self, api_app, admin_client, master_client):
        """POST /api/tenant/ai/config can update individual settings."""
        # Enable system AI first (including external API to test tenant-level)
        master_client.post('/api/admin/settings/ai', json={
            'ai_features_enabled': True,
            'external_api_enabled': True
        })

        # Enable only ai_features_enabled
        response = admin_client.post('/api/tenant/ai/config', json={
            'ai_features_enabled': True
        })
        assert response.status_code == 200

        # Enable external access separately
        response = admin_client.post('/api/tenant/ai/config', json={
            'ai_external_access_enabled': True
        })
        assert response.status_code == 200

        # Verify settings are in nested 'config' object
        data = response.get_json()
        assert data['config']['ai_features_enabled'] is True
        assert data['config']['ai_external_access_enabled'] is True
