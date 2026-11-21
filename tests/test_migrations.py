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


# ==================== Renamed display defaults (2.2.0) ====================

OLD_NAME = "Architecture Decisions"
NEW_NAME = "Decision Records"


def _load_legacy_app(tmp_path: Path):
    db_path = tmp_path / "legacy-schema.db"
    _create_legacy_schema(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO tenants (id, domain, name) VALUES (2, 'custom.test', 'Custom Corp')")
    conn.execute(
        "INSERT INTO tenant_settings (id, tenant_id, rp_name, tenant_prefix) VALUES (2, 2, 'Custom Corp Decisions', 'CST')"
    )
    conn.execute(
        "INSERT INTO auth_configs (id, domain, rp_name, tenant_prefix) VALUES (2, 'custom.test', 'Custom Corp Decisions', 'CST')"
    )
    conn.commit()
    conn.close()
    return load_test_app(secret_key="migration-display-defaults", database_url=f"sqlite:///{db_path}")


def test_startup_renames_only_values_still_on_the_old_default(tmp_path: Path) -> None:
    app_module, test_app = _load_legacy_app(tmp_path)

    with test_app.app_context():
        app_module._db_initialized = False
        app_module.init_database()

        assert db.session.get(AuthConfig, 1).rp_name == NEW_NAME
        assert db.session.get(TenantSettings, 1).rp_name == NEW_NAME
        assert db.session.get(AuthConfig, 2).rp_name == "Custom Corp Decisions"
        assert db.session.get(TenantSettings, 2).rp_name == "Custom Corp Decisions"
        # Identifiers are not display text and are left alone
        assert db.session.get(AuthConfig, 1).tenant_prefix == "XMP"
        assert db.session.get(AuthConfig, 1).domain == "example.com"

        versions = {
            row[0]
            for row in db.session.execute(db.text("SELECT version FROM schema_migrations")).fetchall()
        }
        assert "2.2.0" in versions


def test_display_default_rename_covers_email_and_spaces_and_is_idempotent(tmp_path: Path) -> None:
    from migrations import migrate_2_2_0
    from models import EmailConfig, Space

    app_module, test_app = _load_legacy_app(tmp_path)

    with test_app.app_context():
        app_module._db_initialized = False
        app_module.init_database()

        def email(domain, from_name):
            return EmailConfig(
                domain=domain, smtp_server="smtp.example.test", smtp_port=587, smtp_username="u",
                smtp_password="p", from_email="noreply@example.test", from_name=from_name)

        db.session.add_all([
            email("system", OLD_NAME),
            email("custom.test", "Custom Corp"),
            Space(tenant_id=1, name="General", is_default=True,
                  description="Default space for all architecture decisions"),
            Space(tenant_id=2, name="General", is_default=True, description="Everything we decide"),
        ])
        db.session.get(AuthConfig, 2).rp_name = OLD_NAME
        db.session.commit()

        assert migrate_2_2_0(db) == 3
        db.session.expire_all()

        assert EmailConfig.query.filter_by(domain="system").one().from_name == NEW_NAME
        assert EmailConfig.query.filter_by(domain="custom.test").one().from_name == "Custom Corp"
        assert db.session.get(AuthConfig, 2).rp_name == NEW_NAME
        assert Space.query.filter_by(tenant_id=1).one().description == "Default space for all decisions"
        assert Space.query.filter_by(tenant_id=2).one().description == "Everything we decide"

        assert migrate_2_2_0(db) == 0


def test_new_rows_default_to_decision_records(tmp_path: Path) -> None:
    from models import EmailConfig

    app_module, test_app = load_test_app(secret_key="migration-new-row-defaults")

    with test_app.app_context():
        db.create_all()
        try:
            auth_config = AuthConfig(domain="fresh.test")
            email_config = EmailConfig(
                domain="fresh.test", smtp_server="smtp.example.test", smtp_port=587,
                smtp_username="u", smtp_password="p", from_email="noreply@example.test")
            db.session.add_all([auth_config, email_config])
            db.session.commit()

            assert auth_config.rp_name == NEW_NAME
            assert email_config.from_name == NEW_NAME
        finally:
            db.session.remove()
            db.drop_all()
            app_module._db_initialized = False
