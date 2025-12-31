"""
AI Configuration Management.

Handles hierarchical AI feature configuration:
1. System-level (Super Admin) - Master switches for all AI features
2. Tenant-level (Tenant Admin) - Per-organization settings
3. User-level - Individual opt-out preferences
"""

from typing import Optional, Dict, Any
from models import db, SystemConfig, Tenant, TenantMembership, User, LLMProvider


class AIConfig:
    """
    AI configuration manager with hierarchical checks.

    Features are only available if enabled at all levels:
    - System level must be ON
    - Tenant level must be ON
    - User must not have opted out
    """

    # =========================================================================
    # System-Level Configuration (Super Admin)
    # =========================================================================

    @staticmethod
    def get_system_ai_enabled() -> bool:
        """Check if AI features are enabled at system level."""
        config = SystemConfig.query.filter_by(key=SystemConfig.KEY_AI_FEATURES_ENABLED).first()
        if config:
            return config.value.lower() == 'true'
        return SystemConfig.DEFAULT_AI_FEATURES_ENABLED

    @staticmethod
    def get_system_slack_bot_enabled() -> bool:
        """Check if Slack AI bot is enabled at system level."""
        if not AIConfig.get_system_ai_enabled():
            return False
        config = SystemConfig.query.filter_by(key=SystemConfig.KEY_AI_SLACK_BOT_ENABLED).first()
        if config:
            return config.value.lower() == 'true'
        return SystemConfig.DEFAULT_AI_SLACK_BOT_ENABLED

    @staticmethod
    def get_system_mcp_server_enabled() -> bool:
        """Check if MCP server is enabled at system level."""
        if not AIConfig.get_system_ai_enabled():
            return False
        config = SystemConfig.query.filter_by(key=SystemConfig.KEY_AI_MCP_SERVER_ENABLED).first()
        if config:
            return config.value.lower() == 'true'
        return SystemConfig.DEFAULT_AI_MCP_SERVER_ENABLED

    @staticmethod
    def get_system_external_api_enabled() -> bool:
        """Check if external AI API is enabled at system level."""
        if not AIConfig.get_system_ai_enabled():
            return False
        config = SystemConfig.query.filter_by(key=SystemConfig.KEY_AI_EXTERNAL_API_ENABLED).first()
        if config:
            return config.value.lower() == 'true'
        return SystemConfig.DEFAULT_AI_EXTERNAL_API_ENABLED

    @staticmethod
    def get_system_assisted_creation_enabled() -> bool:
        """Check if AI-assisted creation is enabled at system level."""
        if not AIConfig.get_system_ai_enabled():
            return False
        config = SystemConfig.query.filter_by(key=SystemConfig.KEY_AI_ASSISTED_CREATION_ENABLED).first()
        if config:
            return config.value.lower() == 'true'
        return SystemConfig.DEFAULT_AI_ASSISTED_CREATION_ENABLED

    @staticmethod
    def get_llm_provider() -> LLMProvider:
        """Get the configured LLM provider."""
        config = SystemConfig.query.filter_by(key=SystemConfig.KEY_AI_LLM_PROVIDER).first()
        if config:
            try:
                return LLMProvider(config.value)
            except ValueError:
                return LLMProvider.NONE
        return LLMProvider(SystemConfig.DEFAULT_AI_LLM_PROVIDER)

    @staticmethod
    def get_llm_model() -> Optional[str]:
        """Get the configured LLM model name."""
        config = SystemConfig.query.filter_by(key=SystemConfig.KEY_AI_LLM_MODEL).first()
        return config.value if config else None

    @staticmethod
    def get_llm_api_key_secret() -> Optional[str]:
        """Get the Key Vault reference for the LLM API key."""
        config = SystemConfig.query.filter_by(key=SystemConfig.KEY_AI_LLM_API_KEY_SECRET).first()
        return config.value if config else None

    @staticmethod
    def get_llm_endpoint() -> Optional[str]:
        """Get custom LLM endpoint (for Azure OpenAI or self-hosted)."""
        config = SystemConfig.query.filter_by(key=SystemConfig.KEY_AI_LLM_ENDPOINT).first()
        return config.value if config else None

    @staticmethod
    def set_system_config(key: str, value: str) -> None:
        """Set a system-level AI configuration value."""
        config = SystemConfig.query.filter_by(key=key).first()
        if config:
            config.value = value
        else:
            config = SystemConfig(key=key, value=value)
            db.session.add(config)
        db.session.commit()

    @staticmethod
    def get_system_ai_config() -> Dict[str, Any]:
        """Get all system-level AI configuration as a dictionary."""
        return {
            'ai_features_enabled': AIConfig.get_system_ai_enabled(),
            'ai_slack_bot_enabled': AIConfig.get_system_slack_bot_enabled(),
            'ai_mcp_server_enabled': AIConfig.get_system_mcp_server_enabled(),
            'ai_external_api_enabled': AIConfig.get_system_external_api_enabled(),
            'ai_assisted_creation_enabled': AIConfig.get_system_assisted_creation_enabled(),
            'llm_provider': AIConfig.get_llm_provider().value,
            'llm_model': AIConfig.get_llm_model(),
            'llm_endpoint': AIConfig.get_llm_endpoint(),
            # Never expose the API key secret reference
        }

    # =========================================================================
    # Tenant-Level Configuration (Tenant Admin)
    # =========================================================================

    @staticmethod
    def get_tenant_ai_enabled(tenant: Tenant) -> bool:
        """Check if AI features are enabled for a tenant."""
        if not AIConfig.get_system_ai_enabled():
            return False
        return tenant.ai_features_enabled

    @staticmethod
    def get_tenant_slack_queries_enabled(tenant: Tenant) -> bool:
        """Check if Slack AI queries are enabled for a tenant."""
        if not AIConfig.get_system_slack_bot_enabled():
            return False
        if not tenant.ai_features_enabled:
            return False
        return tenant.ai_slack_queries_enabled

    @staticmethod
    def get_tenant_assisted_creation_enabled(tenant: Tenant) -> bool:
        """Check if AI-assisted creation is enabled for a tenant."""
        if not AIConfig.get_system_assisted_creation_enabled():
            return False
        if not tenant.ai_features_enabled:
            return False
        return tenant.ai_assisted_creation_enabled

    @staticmethod
    def get_tenant_external_access_enabled(tenant: Tenant) -> bool:
        """Check if external AI access is enabled for a tenant."""
        if not AIConfig.get_system_external_api_enabled():
            return False
        if not tenant.ai_features_enabled:
            return False
        return tenant.ai_external_access_enabled

    @staticmethod
    def get_tenant_require_anonymization(tenant: Tenant) -> bool:
        """Check if anonymization is required for a tenant."""
        return tenant.ai_require_anonymization

    @staticmethod
    def get_tenant_log_interactions(tenant: Tenant) -> bool:
        """Check if AI interactions should be logged for a tenant."""
        return tenant.ai_log_interactions

    @staticmethod
    def get_tenant_ai_config(tenant: Tenant) -> Dict[str, Any]:
        """Get all tenant-level AI configuration as a dictionary."""
        return {
            'ai_features_enabled': AIConfig.get_tenant_ai_enabled(tenant),
            'ai_slack_queries_enabled': AIConfig.get_tenant_slack_queries_enabled(tenant),
            'ai_assisted_creation_enabled': AIConfig.get_tenant_assisted_creation_enabled(tenant),
            'ai_external_access_enabled': AIConfig.get_tenant_external_access_enabled(tenant),
            'ai_require_anonymization': tenant.ai_require_anonymization,
            'ai_log_interactions': tenant.ai_log_interactions,
        }

    @staticmethod
    def update_tenant_ai_config(tenant: Tenant, **kwargs) -> None:
        """Update tenant AI configuration."""
        allowed_fields = [
            'ai_features_enabled', 'ai_slack_queries_enabled',
            'ai_assisted_creation_enabled', 'ai_external_access_enabled',
            'ai_require_anonymization', 'ai_log_interactions',
        ]
        for field, value in kwargs.items():
            if field in allowed_fields:
                setattr(tenant, field, value)
        db.session.commit()

    # =========================================================================
    # User-Level Configuration
    # =========================================================================

    @staticmethod
    def get_user_ai_opt_out(user: User, tenant: Tenant) -> bool:
        """Check if a user has opted out of AI features for a tenant."""
        membership = TenantMembership.query.filter_by(
            user_id=user.id,
            tenant_id=tenant.id
        ).first()
        if membership:
            return membership.ai_opt_out
        return False

    @staticmethod
    def set_user_ai_opt_out(user: User, tenant: Tenant, opt_out: bool) -> None:
        """Set user's AI opt-out preference for a tenant."""
        membership = TenantMembership.query.filter_by(
            user_id=user.id,
            tenant_id=tenant.id
        ).first()
        if membership:
            membership.ai_opt_out = opt_out
            db.session.commit()

    # =========================================================================
    # Combined Checks (All Levels)
    # =========================================================================

    @staticmethod
    def is_ai_available_for_user(user: User, tenant: Tenant) -> bool:
        """
        Check if AI features are available for a specific user in a tenant.

        This is the main check to use before any AI operation.
        Returns True only if:
        - System-level AI is enabled
        - Tenant-level AI is enabled
        - User has not opted out
        """
        if not AIConfig.get_tenant_ai_enabled(tenant):
            return False
        if AIConfig.get_user_ai_opt_out(user, tenant):
            return False
        return True

    @staticmethod
    def is_slack_ai_available(user: User, tenant: Tenant) -> bool:
        """Check if Slack AI queries are available for a user."""
        if not AIConfig.is_ai_available_for_user(user, tenant):
            return False
        return AIConfig.get_tenant_slack_queries_enabled(tenant)

    @staticmethod
    def is_assisted_creation_available(user: User, tenant: Tenant) -> bool:
        """Check if AI-assisted creation is available for a user."""
        if not AIConfig.is_ai_available_for_user(user, tenant):
            return False
        return AIConfig.get_tenant_assisted_creation_enabled(tenant)

    @staticmethod
    def is_external_ai_available(user: User, tenant: Tenant) -> bool:
        """Check if external AI access is available for a user."""
        if not AIConfig.is_ai_available_for_user(user, tenant):
            return False
        return AIConfig.get_tenant_external_access_enabled(tenant)

    @staticmethod
    def is_mcp_available() -> bool:
        """
        Check if MCP server is available.

        MCP is system-level only - no tenant/user checks needed
        as authentication happens via API keys which are tenant-scoped.
        """
        return AIConfig.get_system_mcp_server_enabled()
