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


# ==================== Inquiries and team profile (2.3.0) ====================

TEAM_PROFILE_COLUMNS = {
    "team_focus", "team_size", "team_profile_answered_at", "team_profile_answered_by_id",
}


def _sqlite_columns(db_path: Path, table: str) -> set[str]:
    conn = sqlite3.connect(db_path)
    try:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    finally:
        conn.close()


def _sqlite_tables(db_path: Path) -> set[str]:
    conn = sqlite3.connect(db_path)
    try:
        return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    finally:
        conn.close()


def test_startup_adds_inquiries_and_team_profile_to_an_existing_database(tmp_path: Path) -> None:
    from models import Inquiry, Tenant

    db_path = tmp_path / "legacy-schema.db"
    _create_legacy_schema(db_path)
    assert "inquiries" not in _sqlite_tables(db_path)
    assert not TEAM_PROFILE_COLUMNS & _sqlite_columns(db_path, "tenants")

    app_module, test_app = load_test_app(
        secret_key="migration-inquiries", database_url=f"sqlite:///{db_path}"
    )

    with test_app.app_context():
        app_module._db_initialized = False
        app_module.init_database()

        assert TEAM_PROFILE_COLUMNS <= _sqlite_columns(db_path, "tenants")
        assert {column.name for column in Inquiry.__table__.columns} <= _sqlite_columns(db_path, "inquiries")

        # The existing tenant is untouched and has no answers yet. (The legacy
        # fixture's tenants table is a minimal one, so it is read through the
        # new columns only, not the whole model.)
        team_profile = db.session.query(
            Tenant.domain, Tenant.name, Tenant.team_focus, Tenant.team_size,
            Tenant.team_profile_answered_at, Tenant.team_profile_answered_by_id,
        ).filter(Tenant.id == 1).one()
        assert tuple(team_profile) == ("example.com", "Example Corp", None, None, None, None)

        # Both are usable through the models straight away
        Tenant.query.filter(Tenant.id == 1).update(
            {"team_focus": "Hiring", "team_size": "6-25"}, synchronize_session=False
        )
        db.session.add(Inquiry(source="contact", name="Ada", email="ada@example.org", message="Hello"))
        db.session.commit()
        db.session.expire_all()
        assert db.session.query(Tenant.team_size).filter(Tenant.id == 1).scalar() == "6-25"
        stored = Inquiry.query.one()
        assert stored.email_sent is False and stored.handled is False and stored.created_at is not None

        versions = {
            row[0]
            for row in db.session.execute(db.text("SELECT version FROM schema_migrations")).fetchall()
        }
        assert "2.3.0" in versions

        db.session.remove()
        app_module._db_initialized = False


def test_starting_twice_changes_nothing_the_second_time(tmp_path: Path) -> None:
    from migrations import migrate_2_3_0, run_migrations
    from models import Inquiry

    db_path = tmp_path / "legacy-schema.db"
    _create_legacy_schema(db_path)
    app_module, test_app = load_test_app(
        secret_key="migration-inquiries-twice", database_url=f"sqlite:///{db_path}"
    )

    with test_app.app_context():
        app_module._db_initialized = False
        app_module.init_database()
        db.session.add(Inquiry(source="feedback", email="ada@example.org", message="Kept"))
        db.session.commit()
        columns_before = _sqlite_columns(db_path, "tenants")

        app_module._db_initialized = False
        app_module.init_database()

        assert run_migrations(db) == 0
        assert migrate_2_3_0(db) == 0
        assert _sqlite_columns(db_path, "tenants") == columns_before
        assert Inquiry.query.one().message == "Kept"

        db.session.remove()
        app_module._db_initialized = False


def test_migration_creates_the_inquiries_table_itself_when_it_is_missing(tmp_path: Path) -> None:
    """Without db.create_all(): the migration's own SQL must match the model."""
    from migrations import migrate_2_3_0
    from models import Inquiry

    db_path = tmp_path / "legacy-schema.db"
    _create_legacy_schema(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR(255) NOT NULL)")
    conn.commit()
    conn.close()

    app_module, test_app = load_test_app(
        secret_key="migration-inquiries-raw", database_url=f"sqlite:///{db_path}"
    )

    with test_app.app_context():
        assert "inquiries" not in _sqlite_tables(db_path)

        # 1 table + 4 tenant columns
        assert migrate_2_3_0(db) == 5

        model_columns = {column.name for column in Inquiry.__table__.columns}
        assert _sqlite_columns(db_path, "inquiries") == model_columns
        assert TEAM_PROFILE_COLUMNS <= _sqlite_columns(db_path, "tenants")

        conn = sqlite3.connect(db_path)
        indexes = {row[1] for row in conn.execute("PRAGMA index_list(inquiries)").fetchall()}
        conn.execute(
            "INSERT INTO inquiries (source, email) VALUES ('contact', 'ada@example.org')"
        )
        conn.commit()
        row = conn.execute("SELECT email_sent, handled, created_at FROM inquiries").fetchone()
        conn.close()
        assert {f"ix_inquiries_{name}" for name in ("source", "email", "user_id", "created_at", "handled")} <= indexes
        # Defaults come from the table itself, not only from the model
        assert row[0] in (0, False) and row[1] in (0, False) and row[2] is not None

        assert migrate_2_3_0(db) == 0
        db.session.remove()
        app_module._db_initialized = False


def test_fresh_database_initialises_with_inquiries_and_team_profile(tmp_path: Path) -> None:
    from migrations import migrate_2_3_0
    from models import Inquiry, Tenant

    db_path = tmp_path / "fresh.db"
    app_module, test_app = load_test_app(
        secret_key="migration-inquiries-fresh", database_url=f"sqlite:///{db_path}"
    )

    with test_app.app_context():
        app_module._db_initialized = False
        app_module.init_database()

        assert "inquiries" in _sqlite_tables(db_path)
        assert TEAM_PROFILE_COLUMNS <= _sqlite_columns(db_path, "tenants")
        assert migrate_2_3_0(db) == 0

        db.session.add(Tenant(domain="fresh.test", name="Fresh", team_focus="Hiring", team_size="1-5"))
        db.session.add(Inquiry(source="sponsorship", organisation="Fresh", email="a@fresh.test"))
        db.session.commit()
        assert Tenant.query.filter_by(domain="fresh.test").one().team_size == "1-5"

        versions = {
            row[0]
            for row in db.session.execute(db.text("SELECT version FROM schema_migrations")).fetchall()
        }
        assert "2.3.0" in versions

        db.session.remove()
        db.drop_all()
        app_module._db_initialized = False


class _RecordingConnection:
    """Stands in for a PostgreSQL connection: records SQL, answers the existence checks."""

    def __init__(self, statements):
        self.statements = statements

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, statement, params=None):
        sql = str(statement)
        self.statements.append(sql)
        params = params or {}

        class Result:
            def __init__(self, row):
                self._row = row

            def fetchone(self):
                return self._row

            def fetchall(self):
                return [self._row] if self._row else []

        if "information_schema.tables" in sql:
            created = any("CREATE TABLE inquiries" in s for s in self.statements)
            exists = params.get("name") in ("tenants", "users") or (params.get("name") == "inquiries" and created)
            return Result(("x",) if exists else None)
        if "information_schema.columns" in sql:
            return Result(None)  # no column exists yet
        return Result(None)

    def commit(self):
        pass


def test_migration_sql_for_postgresql_uses_no_sqlite_only_syntax() -> None:
    """No PostgreSQL server here: check the statements the migration would send to one."""
    from types import SimpleNamespace

    import migrations
    from migrations import migrate_2_3_0

    statements: list[str] = []
    fake_db = SimpleNamespace(
        engine=SimpleNamespace(
            dialect=SimpleNamespace(name="postgresql"),
            connect=lambda: _RecordingConnection(statements),
        ),
        text=lambda sql: sql,
    )

    changes = migrate_2_3_0(fake_db)

    assert changes == 5
    ddl = "\n".join(s for s in statements if "information_schema" not in s)
    assert "CREATE TABLE inquiries" in ddl
    assert "id SERIAL PRIMARY KEY" in ddl
    for sqlite_only in ("AUTOINCREMENT", "PRAGMA", "sqlite_master", "DATETIME"):
        assert sqlite_only not in ddl
    for column in sorted(TEAM_PROFILE_COLUMNS):
        assert f"ALTER TABLE tenants ADD COLUMN {column} " in ddl
    assert "team_profile_answered_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL" in ddl
    assert migrations.get_db_type(fake_db) == "postgresql"


# ==================== Retention run history (2.4.0) ====================

RETENTION_TABLES = {"retention_runs", "retention_erasures"}


def test_startup_adds_retention_tables_to_an_existing_database(tmp_path: Path) -> None:
    from migrations import migrate_2_4_0, run_migrations
    from models import RetentionRun

    db_path = tmp_path / "legacy-schema.db"
    _create_legacy_schema(db_path)
    assert not RETENTION_TABLES & _sqlite_tables(db_path)
    app_module, test_app = load_test_app(
        secret_key="migration-retention-legacy", database_url=f"sqlite:///{db_path}"
    )

    with test_app.app_context():
        app_module._db_initialized = False
        app_module.init_database()

        assert RETENTION_TABLES <= _sqlite_tables(db_path)
        versions = {
            row[0]
            for row in db.session.execute(db.text("SELECT version FROM schema_migrations")).fetchall()
        }
        assert "2.4.0" in versions

        db.session.add(RetentionRun(trigger="automatic", claim_key="auto:2026-01-01"))
        db.session.commit()

        # Starting again changes nothing and keeps the row
        app_module._db_initialized = False
        app_module.init_database()
        assert run_migrations(db) == 0
        assert migrate_2_4_0(db) == 0
        assert RetentionRun.query.one().claim_key == "auto:2026-01-01"

        db.session.remove()
        app_module._db_initialized = False


def test_fresh_database_initialises_with_retention_tables(tmp_path: Path) -> None:
    from migrations import migrate_2_4_0

    db_path = tmp_path / "fresh.db"
    app_module, test_app = load_test_app(
        secret_key="migration-retention-fresh", database_url=f"sqlite:///{db_path}"
    )

    with test_app.app_context():
        app_module._db_initialized = False
        app_module.init_database()

        assert RETENTION_TABLES <= _sqlite_tables(db_path)
        assert migrate_2_4_0(db) == 0

        db.session.remove()
        db.drop_all()
        app_module._db_initialized = False


def test_retention_migration_creates_the_tables_itself_with_the_unique_claim_key(app) -> None:
    """Without db.create_all(), on the fixture database (PostgreSQL in CI)."""
    import pytest
    from sqlalchemy.exc import IntegrityError
    from migrations import migrate_2_4_0, table_exists
    from models import RetentionErasure, RetentionRun

    db.session.remove()
    RetentionErasure.__table__.drop(bind=db.engine)
    RetentionRun.__table__.drop(bind=db.engine)
    assert not table_exists(db, "retention_runs") and not table_exists(db, "retention_erasures")

    assert migrate_2_4_0(db) == 2
    assert table_exists(db, "retention_runs") and table_exists(db, "retention_erasures")
    assert migrate_2_4_0(db) == 0

    db.session.add(RetentionRun(trigger="automatic", claim_key="auto:2026-01-01"))
    db.session.add(RetentionRun(trigger="cron"))
    db.session.add(RetentionRun(trigger="super_admin"))
    db.session.add(RetentionErasure(category="tenants", entity_type="tenant", entity_id=1, counts={"users": 2}))
    db.session.commit()
    assert RetentionErasure.query.one().counts == {"users": 2}

    db.session.add(RetentionRun(trigger="automatic", claim_key="auto:2026-01-01"))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
