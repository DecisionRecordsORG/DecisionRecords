"""
AI API Key Service.

Handles generation, validation, and management of API keys
for external AI access (Custom GPTs, agents, MCP clients).
"""

import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple

from models import db, AIApiKey, User, Tenant


class AIApiKeyService:
    """Service for managing AI API keys."""

    # Key format: adr_<random_32_chars>
    KEY_PREFIX = 'adr_'
    KEY_LENGTH = 32
    PREFIX_LENGTH = 8  # Characters to store for identification

    @staticmethod
    def generate_key() -> str:
        """
        Generate a new API key.

        Returns:
            Full API key string (shown to user once, never stored)
        """
        random_part = secrets.token_urlsafe(AIApiKeyService.KEY_LENGTH)
        return f"{AIApiKeyService.KEY_PREFIX}{random_part}"

    @staticmethod
    def hash_key(key: str) -> str:
        """
        Hash an API key for secure storage.

        Args:
            key: The full API key

        Returns:
            SHA256 hash of the key
        """
        return hashlib.sha256(key.encode()).hexdigest()

    @staticmethod
    def get_key_prefix(key: str) -> str:
        """
        Get the prefix of a key for identification.

        Args:
            key: The full API key

        Returns:
            First 8 characters of the key
        """
        return key[:AIApiKeyService.PREFIX_LENGTH]

    @staticmethod
    def create_key(
        user: User,
        tenant: Tenant,
        name: str,
        scopes: Optional[List[str]] = None,
        expires_in_days: Optional[int] = None
    ) -> Tuple[AIApiKey, str]:
        """
        Create a new API key for a user.

        Args:
            user: The user creating the key
            tenant: The tenant context for the key
            name: A friendly name for the key
            scopes: List of scopes (default: ['read', 'search'])
            expires_in_days: Days until expiration (None = no expiration)

        Returns:
            Tuple of (AIApiKey model instance, full key string)
            The full key is only returned once and should be shown to user.
        """
        if scopes is None:
            scopes = ['read', 'search']

        # Validate scopes
        valid_scopes = {'read', 'search', 'write'}
        scopes = [s for s in scopes if s in valid_scopes]

        # Generate the key
        full_key = AIApiKeyService.generate_key()
        key_hash = AIApiKeyService.hash_key(full_key)
        key_prefix = AIApiKeyService.get_key_prefix(full_key)

        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        # Create the key record
        api_key = AIApiKey(
            user_id=user.id,
            tenant_id=tenant.id,
            key_hash=key_hash,
            key_prefix=key_prefix,
            name=name,
            scopes=scopes,
            expires_at=expires_at
        )

        db.session.add(api_key)
        db.session.commit()

        return api_key, full_key

    @staticmethod
    def validate_key(key: str) -> Optional[AIApiKey]:
        """
        Validate an API key and return the associated record.

        Args:
            key: The full API key to validate

        Returns:
            AIApiKey if valid, None if invalid/expired/revoked
        """
        if not key or not key.startswith(AIApiKeyService.KEY_PREFIX):
            return None

        key_hash = AIApiKeyService.hash_key(key)
        api_key = AIApiKey.query.filter_by(key_hash=key_hash).first()

        if not api_key:
            return None

        # Check if revoked
        if api_key.revoked_at:
            return None

        # Check if expired
        if api_key.expires_at and api_key.expires_at < datetime.utcnow():
            return None

        # Update last used timestamp
        api_key.last_used_at = datetime.utcnow()
        db.session.commit()

        return api_key

    @staticmethod
    def has_scope(api_key: AIApiKey, scope: str) -> bool:
        """
        Check if an API key has a specific scope.

        Args:
            api_key: The API key record
            scope: The scope to check ('read', 'search', 'write')

        Returns:
            True if the key has the scope
        """
        return scope in (api_key.scopes or [])

    @staticmethod
    def revoke_key(api_key: AIApiKey) -> None:
        """
        Revoke an API key.

        Args:
            api_key: The API key to revoke
        """
        api_key.revoked_at = datetime.utcnow()
        db.session.commit()

    @staticmethod
    def list_user_keys(user: User, tenant: Tenant, include_revoked: bool = False) -> List[AIApiKey]:
        """
        List all API keys for a user in a tenant.

        Args:
            user: The user
            tenant: The tenant context
            include_revoked: Whether to include revoked keys

        Returns:
            List of AIApiKey records
        """
        query = AIApiKey.query.filter_by(
            user_id=user.id,
            tenant_id=tenant.id
        )

        if not include_revoked:
            query = query.filter(AIApiKey.revoked_at.is_(None))

        return query.order_by(AIApiKey.created_at.desc()).all()

    @staticmethod
    def get_key_by_id(key_id: str, user: User) -> Optional[AIApiKey]:
        """
        Get an API key by its ID, ensuring it belongs to the user.

        Args:
            key_id: The UUID of the API key
            user: The user requesting the key

        Returns:
            AIApiKey if found and belongs to user, None otherwise
        """
        return AIApiKey.query.filter_by(
            id=key_id,
            user_id=user.id
        ).first()

    @staticmethod
    def serialize_key(api_key: AIApiKey) -> Dict[str, Any]:
        """
        Serialize an API key for API response.

        Note: Never includes the actual key or hash.

        Args:
            api_key: The API key to serialize

        Returns:
            Dictionary representation
        """
        return {
            'id': str(api_key.id),
            'name': api_key.name,
            'key_prefix': api_key.key_prefix,
            'scopes': api_key.scopes,
            'created_at': api_key.created_at.isoformat() if api_key.created_at else None,
            'last_used_at': api_key.last_used_at.isoformat() if api_key.last_used_at else None,
            'expires_at': api_key.expires_at.isoformat() if api_key.expires_at else None,
            'is_revoked': api_key.revoked_at is not None,
            'is_expired': api_key.expires_at and api_key.expires_at < datetime.utcnow(),
        }

    @staticmethod
    def cleanup_expired_keys(days_after_expiry: int = 30) -> int:
        """
        Delete expired keys that have been expired for a certain number of days.

        Args:
            days_after_expiry: Days after expiry before deletion

        Returns:
            Number of keys deleted
        """
        cutoff = datetime.utcnow() - timedelta(days=days_after_expiry)
        result = AIApiKey.query.filter(
            AIApiKey.expires_at < cutoff
        ).delete()
        db.session.commit()
        return result
