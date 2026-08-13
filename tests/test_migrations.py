"""
Regression tests for startup schema migrations.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from models import AuthConfig, TenantSettings, db
from tests.app_test_utils import load_test_app


LEGACY_MIGRATION_VERSIONS = (
    ("1.5.0", "Add governance model columns"),
    ("1.13.0", "Add AI, Slack, Teams feature columns"),
    ("1.14.0", "Add login history table"),
    ("1.14.1", "Add setup wizard support columns"),
    ("1.15.0", "Add decision comments table"),
    ("1.16.0", "Add decision relationships and tenant relationship settings"),
)


def _create_legacy_schema(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.executescript(
        """
        CREATE TABLE schema_migrations (
            version TEXT PRIMARY KEY,
            description TEXT,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE tenants (
            id INTEGER PRIMARY KEY,
            domain VARCHAR(255) NOT NULL UNIQUE,
            name VARCHAR(255),
            status VARCHAR(20) DEFAULT 'active',
            maturity_state VARCHAR(20) DEFAULT 'bootstrap'
        );

        CREATE TABLE tenant_settings (
            id INTEGER PRIMARY KEY,
            tenant_id INTEGER NOT NULL UNIQUE,
            auth_method VARCHAR(20) DEFAULT 'local',
            allow_password BOOLEAN DEFAULT 1,
            allow_passkey BOOLEAN DEFAULT 1,
            rp_name VARCHAR(255) DEFAULT 'Architecture Decisions',
            allow_registration BOOLEAN DEFAULT 1,
            require_approval BOOLEAN DEFAULT 0,
            tenant_prefix VARCHAR(3) UNIQUE,
            decision_relationship_pack_ids TEXT,
            decision_relationship_enabled_types TEXT,
            decision_relationship_custom_types TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE auth_configs (
            id INTEGER PRIMARY KEY,
            domain VARCHAR(255) NOT NULL UNIQUE,
            auth_method VARCHAR(20) NOT NULL DEFAULT 'local',
            allow_password BOOLEAN DEFAULT 1,
            allow_passkey BOOLEAN DEFAULT 1,
            allow_registration BOOLEAN DEFAULT 1,
            require_approval BOOLEAN DEFAULT 0,
            rp_name VARCHAR(255) NOT NULL DEFAULT 'Architecture Decisions',
            tenant_prefix VARCHAR(3) UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    cur.executemany(
        "INSERT INTO schema_migrations (version, description) VALUES (?, ?)",
        LEGACY_MIGRATION_VERSIONS,
    )
    cur.execute(
        "INSERT INTO tenants (id, domain, name, status, maturity_state) VALUES (?, ?, ?, ?, ?)",
        (1, "example.com", "Example Corp", "active", "bootstrap"),
    )
    cur.execute(
        """
        INSERT INTO tenant_settings (
            id, tenant_id, auth_method, allow_password, allow_passkey, rp_name,
            allow_registration, require_approval, tenant_prefix
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (1, 1, "local", 1, 1, "Architecture Decisions", 1, 0, "XMP"),
    )
    cur.execute(
        """
        INSERT INTO auth_configs (
            id, domain, auth_method, allow_password, allow_passkey,
            allow_registration, require_approval, rp_name, tenant_prefix
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (1, "example.com", "local", 1, 1, 1, 0, "Architecture Decisions", "XMP"),
    )

    conn.commit()
    conn.close()


def test_init_database_backfills_legacy_oauth_columns(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy-schema.db"
    _create_legacy_schema(db_path)

    app_module, test_app = load_test_app(
        secret_key="migration-regression-test",
        database_url=f"sqlite:///{db_path}",
    )

    with test_app.app_context():
        app_module._db_initialized = False
        app_module.init_database()

        tenant_settings = db.session.get(TenantSettings, 1)
        auth_config = db.session.get(AuthConfig, 1)

        assert tenant_settings is not None
        assert auth_config is not None
        assert tenant_settings.allow_slack_oidc is True
        assert tenant_settings.allow_google_oauth is True
        assert tenant_settings.allow_microsoft_oauth is True
        assert auth_config.allow_slack_oidc is True
        assert auth_config.allow_google_oauth is True
        assert auth_config.allow_microsoft_oauth is True

        migration_versions = {
            row[0]
            for row in db.session.execute(db.text("SELECT version FROM schema_migrations")).fetchall()
        }
        assert "1.16.1" in migration_versions
