"""Tests for SMTP credential encryption in Community Edition.

Community Edition runs without the private ``ee`` package, so the encryption
key can only come from the ``SMTP_ENCRYPTION_KEY`` environment variable.
Looking the key up must never raise when ``ee`` is absent: an unguarded import
turned saving SMTP settings into a 500 for every self-hosted install.
"""

import sys

import pytest
from cryptography.fernet import Fernet

import crypto


@pytest.fixture
def without_enterprise_modules(monkeypatch):
    """Make ``import ee.backend.azure.keyvault_client`` fail like it does in CE."""
    for name in ("ee", "ee.backend", "ee.backend.azure", "ee.backend.azure.keyvault_client"):
        monkeypatch.setitem(sys.modules, name, None)


class TestEncryptionKeyWithoutEnterpriseModules:
    def test_missing_key_returns_none_instead_of_raising(self, without_enterprise_modules, monkeypatch):
        monkeypatch.delenv("SMTP_ENCRYPTION_KEY", raising=False)

        assert crypto._get_encryption_key() is None

    def test_key_is_read_from_environment(self, without_enterprise_modules, monkeypatch):
        key = Fernet.generate_key().decode("utf-8")
        monkeypatch.setenv("SMTP_ENCRYPTION_KEY", key)

        assert crypto._get_encryption_key() == key.encode("utf-8")

    def test_empty_environment_key_is_treated_as_missing(self, without_enterprise_modules, monkeypatch):
        monkeypatch.setenv("SMTP_ENCRYPTION_KEY", "")

        assert crypto._get_encryption_key() is None


class TestPasswordEncryptionWithoutEnterpriseModules:
    def test_encrypt_without_key_stores_plaintext_instead_of_raising(
        self, without_enterprise_modules, monkeypatch
    ):
        monkeypatch.delenv("SMTP_ENCRYPTION_KEY", raising=False)

        assert crypto.encrypt_password("smtp-secret") == "smtp-secret"

    def test_encrypt_and_decrypt_round_trip_with_environment_key(
        self, without_enterprise_modules, monkeypatch
    ):
        monkeypatch.setenv("SMTP_ENCRYPTION_KEY", Fernet.generate_key().decode("utf-8"))

        encrypted = crypto.encrypt_password("smtp-secret")

        assert encrypted.startswith(crypto.ENCRYPTED_PREFIX)
        assert "smtp-secret" not in encrypted
        assert crypto.is_password_encrypted(encrypted)
        assert crypto.decrypt_password(encrypted) == "smtp-secret"

    def test_decrypt_encrypted_value_without_key_returns_none(self, without_enterprise_modules, monkeypatch):
        monkeypatch.setenv("SMTP_ENCRYPTION_KEY", Fernet.generate_key().decode("utf-8"))
        encrypted = crypto.encrypt_password("smtp-secret")
        monkeypatch.delenv("SMTP_ENCRYPTION_KEY")

        assert crypto.decrypt_password(encrypted) is None

    def test_plaintext_and_empty_values_pass_through(self, without_enterprise_modules, monkeypatch):
        monkeypatch.delenv("SMTP_ENCRYPTION_KEY", raising=False)

        assert crypto.decrypt_password("legacy-plaintext") == "legacy-plaintext"
        assert crypto.encrypt_password("") == ""
        assert crypto.encrypt_password(None) is None
