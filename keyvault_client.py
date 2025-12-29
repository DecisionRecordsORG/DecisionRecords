"""
Azure Key Vault client for secure credential management.

All application secrets should be stored in Azure Key Vault:
- flask-secret-key: Flask session signing key
- database-url: PostgreSQL connection string (optional, can use env var)
- smtp-username: SMTP authentication username
- smtp-password: SMTP authentication password
"""
import logging
import os
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)


class KeyVaultClient:
    """Azure Key Vault client for secure credential management."""

    def __init__(self):
        self.vault_url = os.environ.get('AZURE_KEYVAULT_URL', 'https://adr-keyvault-eu.vault.azure.net/')
        self._client = None
        self._credential = None
        self._initialized = False
        self._init_error = None

    def _initialize(self):
        """Lazy initialization of Key Vault client.

        Re-attempts initialization if a previous attempt failed, since
        Azure credentials may become available later (e.g., after Azure CLI login).
        """
        # If already successfully initialized, return True
        if self._initialized and self._client is not None:
            return True

        # Reset state for retry
        self._initialized = True
        self._init_error = None
        self._client = None
        self._credential = None

        try:
            self._credential = DefaultAzureCredential()
            self._client = SecretClient(vault_url=self.vault_url, credential=self._credential)
            logger.info(f"Azure Key Vault client initialized: {self.vault_url}")
            return True
        except Exception as e:
            self._init_error = str(e)
            logger.warning(f"Azure Key Vault not available: {e}. Using environment variables as fallback.")
            return False

    @property
    def is_available(self):
        """Check if Key Vault is available."""
        self._initialize()
        return self._client is not None

    def get_secret(self, secret_name, fallback_env_var=None, default=None):
        """
        Get a secret from Key Vault with fallback to environment variable.

        Args:
            secret_name: Name of the secret in Key Vault
            fallback_env_var: Environment variable to use if Key Vault unavailable
            default: Default value if neither Key Vault nor env var has the secret

        Returns:
            The secret value, or default if not found
        """
        # Try Key Vault first
        if self._initialize() and self._client:
            try:
                secret = self._client.get_secret(secret_name)
                return secret.value
            except Exception as e:
                logger.debug(f"Secret '{secret_name}' not found in Key Vault: {e}")

        # Fallback to environment variable
        if fallback_env_var:
            env_value = os.environ.get(fallback_env_var)
            if env_value:
                logger.debug(f"Using '{fallback_env_var}' environment variable for '{secret_name}'")
                return env_value

        return default

    def get_flask_secret_key(self):
        """
        Get Flask SECRET_KEY from Key Vault or environment.

        Priority:
        1. Key Vault 'flask-secret-key'
        2. Environment variable 'SECRET_KEY'
        3. None (caller should generate a random key with warning)
        """
        return self.get_secret('flask-secret-key', fallback_env_var='SECRET_KEY')

    def get_database_url(self):
        """
        Get database URL from Key Vault or environment.

        Priority:
        1. Key Vault 'database-url'
        2. Environment variable 'DATABASE_URL'
        3. Default SQLite for local development
        """
        return self.get_secret(
            'database-url',
            fallback_env_var='DATABASE_URL',
            default='sqlite:///architecture_decisions.db'
        )

    def get_smtp_credentials(self):
        """
        Get SMTP credentials from Key Vault or environment variables.

        Priority:
        1. Key Vault 'smtp-username' and 'smtp-password'
        2. Environment variables 'SMTP_USERNAME' and 'SMTP_PASSWORD'
        """
        username = self.get_secret('smtp-username', fallback_env_var='SMTP_USERNAME')
        password = self.get_secret('smtp-password', fallback_env_var='SMTP_PASSWORD')

        if not username or not password:
            logger.warning("SMTP credentials not found in Key Vault or environment variables")
            return None, None

        return username, password

    def get_posthog_api_key(self):
        """
        Get PostHog API key from Key Vault or environment.

        Priority:
        1. Key Vault 'posthog-api-key'
        2. Environment variable 'POSTHOG_API_KEY'
        3. None (analytics will fall back to SystemConfig or be disabled)
        """
        return self.get_secret('posthog-api-key', fallback_env_var='POSTHOG_API_KEY')

    def get_analytics_salt(self):
        """
        Get analytics salt for hashing user IDs.

        Priority:
        1. Key Vault 'analytics-salt'
        2. Environment variable 'ANALYTICS_SALT'
        3. Default salt (for development only)
        """
        return self.get_secret(
            'analytics-salt',
            fallback_env_var='ANALYTICS_SALT',
            default='default-analytics-salt-change-in-production'
        )

    def get_log_forwarding_api_key(self):
        """
        Get log forwarding (OTLP) API key from Key Vault or environment.

        Priority:
        1. Key Vault 'log-forwarding-api-key'
        2. Environment variable 'LOG_FORWARDING_API_KEY'
        3. None (log forwarding will check SystemConfig as fallback)
        """
        return self.get_secret('log-forwarding-api-key', fallback_env_var='LOG_FORWARDING_API_KEY')

    # =========================================================================
    # SLACK INTEGRATION SECRETS
    # =========================================================================

    def get_slack_client_id(self):
        """
        Get Slack OAuth client ID from Key Vault or environment.

        Priority:
        1. Key Vault 'slack-client-id'
        2. Environment variable 'SLACK_CLIENT_ID'
        """
        return self.get_secret('slack-client-id', fallback_env_var='SLACK_CLIENT_ID')

    def get_slack_client_secret(self):
        """
        Get Slack OAuth client secret from Key Vault or environment.

        Priority:
        1. Key Vault 'slack-client-secret'
        2. Environment variable 'SLACK_CLIENT_SECRET'
        """
        return self.get_secret('slack-client-secret', fallback_env_var='SLACK_CLIENT_SECRET')

    def get_slack_signing_secret(self):
        """
        Get Slack signing secret for request verification from Key Vault or environment.

        Priority:
        1. Key Vault 'slack-signing-secret'
        2. Environment variable 'SLACK_SIGNING_SECRET'
        """
        return self.get_secret('slack-signing-secret', fallback_env_var='SLACK_SIGNING_SECRET')


# Global instance
keyvault_client = KeyVaultClient()