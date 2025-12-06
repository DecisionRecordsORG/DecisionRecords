"""
Azure Key Vault client for secure credential management.
"""
import logging
import os
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)

class KeyVaultClient:
    """Azure Key Vault client for secure credential management."""
    
    def __init__(self):
        self.vault_url = "https://adr-keyvault-eu.vault.azure.net/"
        self.credential = DefaultAzureCredential()
        self.client = SecretClient(vault_url=self.vault_url, credential=self.credential)
        
    def get_secret(self, secret_name):
        """Get a secret from Key Vault."""
        try:
            secret = self.client.get_secret(secret_name)
            return secret.value
        except Exception as e:
            logger.error(f"Failed to retrieve secret '{secret_name}' from Key Vault: {str(e)}")
            return None
    
    def get_smtp_credentials(self):
        """Get SMTP credentials from Key Vault."""
        username = self.get_secret("smtp-username")
        password = self.get_secret("smtp-password")
        
        if not username or not password:
            logger.warning("SMTP credentials not found in Key Vault")
            return None, None
            
        return username, password

# Global instance
keyvault_client = KeyVaultClient()