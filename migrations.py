"""
Database Migration System for Decision Records

This module provides automatic schema migrations that run on application startup.
It supports both SQLite (Community Edition) and PostgreSQL (Enterprise Edition).

Design Principles:
- Migrations are idempotent (safe to run multiple times)
- Each migration has a unique version number
- Applied migrations are tracked in schema_migrations table
- Migrations run automatically on container/app startup

Usage:
    from migrations import run_migrations
    run_migrations(db)  # Called from init_database() in app.py
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def get_db_type(db):
    """Detect database type from SQLAlchemy engine."""
    dialect = db.engine.dialect.name
    return dialect  # 'sqlite', 'postgresql', etc.


def ensure_migrations_table(db):
    """Create the schema_migrations table if it doesn't exist."""
    db_type = get_db_type(db)

    if db_type == 'sqlite':
        create_sql = """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                description TEXT,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
    else:  # PostgreSQL
        create_sql = """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(50) PRIMARY KEY,
                description VARCHAR(500),
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """

    with db.engine.connect() as conn:
        conn.execute(db.text(create_sql))
        conn.commit()


def get_applied_migrations(db):
    """Get list of already applied migration versions."""
    try:
        with db.engine.connect() as conn:
            result = conn.execute(db.text("SELECT version FROM schema_migrations"))
            return {row[0] for row in result.fetchall()}
    except Exception:
        # Table might not exist yet
        return set()


def record_migration(db, version, description):
    """Record a migration as applied."""
    with db.engine.connect() as conn:
        conn.execute(
            db.text("INSERT INTO schema_migrations (version, description) VALUES (:v, :d)"),
            {"v": version, "d": description}
        )
        conn.commit()


def column_exists(db, table_name, column_name):
    """Check if a column exists in a table (works with SQLite and PostgreSQL)."""
    db_type = get_db_type(db)

    with db.engine.connect() as conn:
        if db_type == 'sqlite':
            result = conn.execute(db.text(f"PRAGMA table_info({table_name})"))
            columns = [row[1] for row in result.fetchall()]
            return column_name in columns
        else:  # PostgreSQL
            result = conn.execute(db.text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = :table AND column_name = :column
            """), {"table": table_name, "column": column_name})
            return result.fetchone() is not None


def table_exists(db, table_name):
    """Check if a table exists (works with SQLite and PostgreSQL)."""
    db_type = get_db_type(db)

    with db.engine.connect() as conn:
        if db_type == 'sqlite':
            result = conn.execute(db.text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=:name"
            ), {"name": table_name})
            return result.fetchone() is not None
        else:  # PostgreSQL
            result = conn.execute(db.text("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = :name
            """), {"name": table_name})
            return result.fetchone() is not None


def add_column(db, table_name, column_name, column_type, default=None):
    """Add a column to a table if it doesn't exist."""
    if column_exists(db, table_name, column_name):
        logger.debug(f"Column {table_name}.{column_name} already exists")
        return False

    db_type = get_db_type(db)

    # Build ALTER TABLE statement
    if default is not None:
        if isinstance(default, bool):
            default_str = "TRUE" if default else "FALSE"
        elif isinstance(default, str):
            default_str = f"'{default}'"
        else:
            default_str = str(default)
        sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type} DEFAULT {default_str}"
    else:
        sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"

    with db.engine.connect() as conn:
        conn.execute(db.text(sql))
        conn.commit()

    logger.info(f"Added column {table_name}.{column_name}")
    return True


# =============================================================================
# Migration Definitions
# =============================================================================
# Each migration is a dict with:
#   - version: Unique version string (use semver-like format)
#   - description: Human-readable description
#   - migrate: Function that performs the migration (receives db)

MIGRATIONS = [
    {
        "version": "1.5.0",
        "description": "Add governance model columns",
        "migrate": lambda db: migrate_1_5_0(db)
    },
    {
        "version": "1.13.0",
        "description": "Add AI, Slack, Teams feature columns",
        "migrate": lambda db: migrate_1_13_0(db)
    },
    {
        "version": "1.14.0",
        "description": "Add login history table",
        "migrate": lambda db: migrate_1_14_0(db)
    },
    {
        "version": "1.14.1",
        "description": "Add setup wizard support columns",
        "migrate": lambda db: migrate_1_14_1(db)
    },
    {
        "version": "1.15.0",
        "description": "Add decision comments table",
        "migrate": lambda db: migrate_1_15_0(db)
    },
    {
        "version": "1.16.0",
        "description": "Add decision relationships and tenant relationship settings",
        "migrate": lambda db: migrate_1_16_0(db)
    },
    {
        "version": "1.16.1",
        "description": "Backfill tenant and auth OAuth provider columns",
        "migrate": lambda db: migrate_1_16_1(db)
    },
    {
        "version": "2.2.0",
        "description": "Rename stored default display names to Decision Records",
        "migrate": lambda db: migrate_2_2_0(db)
    },
    {
        "version": "2.3.0",
        "description": "Add inquiries table and tenant team profile columns",
        "migrate": lambda db: migrate_2_3_0(db)
    },
    {
        "version": "2.4.0",
        "description": "Add retention run history tables",
        "migrate": lambda db: migrate_2_4_0(db)
    },
    {
        "version": "2.5.0",
        "description": "Finish the anonymisation of accounts anonymised by earlier versions",
        "migrate": lambda db: migrate_2_5_0(db)
    },
    {
        "version": "2.6.0",
        "description": "Add decision template, industry and decision type columns",
        "migrate": lambda db: migrate_2_6_0(db)
    },
    {
        "version": "2.7.0",
        "description": "Add the OAuth client, grant, authorization request and token tables",
        "migrate": lambda db: migrate_2_7_0(db)
    },
    {
        "version": "2.8.0",
        "description": "Add oauth_tokens.withdrawn_at and oauth_tokens.repeat_answered_at",
        "migrate": lambda db: migrate_2_8_0(db)
    },
    {
        "version": "2.9.0",
        "description": "Encrypt SSO client secrets at rest; add users.name_edited_at",
        "migrate": lambda db: migrate_2_9_0(db)
    },
]


def migrate_1_5_0(db):
    """Migration for v1.5.0 - Governance model."""
    changes = 0

    # Add maturity_state to tenants
    if not column_exists(db, 'tenants', 'maturity_state'):
        add_column(db, 'tenants', 'maturity_state', 'VARCHAR(20)', default='bootstrap')
        changes += 1

    # Add status to tenants
    if not column_exists(db, 'tenants', 'status'):
        add_column(db, 'tenants', 'status', 'VARCHAR(20)', default='active')
        changes += 1

    return changes


def migrate_1_13_0(db):
    """Migration for v1.13.0 - AI, Slack, Teams features."""
    changes = 0

    # Add AI opt-out to tenant memberships
    if table_exists(db, 'tenant_memberships'):
        if not column_exists(db, 'tenant_memberships', 'ai_opt_out'):
            add_column(db, 'tenant_memberships', 'ai_opt_out', 'BOOLEAN', default=False)
            changes += 1

    # Add auto_approved to domain_approvals
    if table_exists(db, 'domain_approvals'):
        if not column_exists(db, 'domain_approvals', 'auto_approved'):
            add_column(db, 'domain_approvals', 'auto_approved', 'BOOLEAN', default=False)
            changes += 1

    # Add tenant_prefix to auth_configs
    if table_exists(db, 'auth_configs'):
        if not column_exists(db, 'auth_configs', 'tenant_prefix'):
            add_column(db, 'auth_configs', 'tenant_prefix', 'VARCHAR(3)')
            changes += 1

    return changes


def migrate_1_14_0(db):
    """Migration for v1.14.0 - Login history table."""
    if table_exists(db, 'login_history'):
        logger.debug("login_history table already exists")
        return 0

    db_type = get_db_type(db)

    if db_type == 'sqlite':
        create_sql = """
            CREATE TABLE login_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                email VARCHAR(255) NOT NULL,
                tenant_domain VARCHAR(255),
                login_method VARCHAR(20) NOT NULL,
                ip_address VARCHAR(45),
                user_agent VARCHAR(500),
                success BOOLEAN NOT NULL DEFAULT 0,
                failure_reason VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
    else:  # PostgreSQL
        create_sql = """
            CREATE TABLE login_history (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                email VARCHAR(255) NOT NULL,
                tenant_domain VARCHAR(255),
                login_method VARCHAR(20) NOT NULL,
                ip_address VARCHAR(45),
                user_agent VARCHAR(500),
                success BOOLEAN NOT NULL DEFAULT FALSE,
                failure_reason VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """

    with db.engine.connect() as conn:
        conn.execute(db.text(create_sql))
        conn.commit()

    logger.info("Created login_history table")
    return 1


def migrate_1_14_1(db):
    """Migration for v1.14.1 - Setup wizard support."""
    changes = 0

    # Ensure users table has password_hash for local auth
    if table_exists(db, 'users'):
        if not column_exists(db, 'users', 'password_hash'):
            add_column(db, 'users', 'password_hash', 'VARCHAR(255)')
            changes += 1

    return changes


def migrate_1_15_0(db):
    """Migration for v1.15.0 - ADR comments."""
    db_type = get_db_type(db)
    changes = 0

    if not table_exists(db, 'decision_comments'):
        if db_type == 'sqlite':
            create_sql = """
                CREATE TABLE decision_comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    decision_id INTEGER NOT NULL REFERENCES architecture_decisions(id) ON DELETE CASCADE,
                    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    body TEXT NOT NULL,
                    author_display VARCHAR(255),
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    deleted_at TIMESTAMP,
                    deleted_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL
                )
            """
        else:  # PostgreSQL
            create_sql = """
                CREATE TABLE decision_comments (
                    id SERIAL PRIMARY KEY,
                    decision_id INTEGER NOT NULL REFERENCES architecture_decisions(id) ON DELETE CASCADE,
                    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    body TEXT NOT NULL,
                    author_display VARCHAR(255),
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    deleted_at TIMESTAMP,
                    deleted_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL
                )
            """

        with db.engine.connect() as conn:
            conn.execute(db.text(create_sql))
            conn.commit()

        logger.info("Created decision_comments table")
        changes += 1

    with db.engine.connect() as conn:
        conn.execute(db.text(
            "CREATE INDEX IF NOT EXISTS idx_decision_comments_decision_id "
            "ON decision_comments(decision_id)"
        ))
        conn.execute(db.text(
            "CREATE INDEX IF NOT EXISTS idx_decision_comments_tenant_id "
            "ON decision_comments(tenant_id)"
        ))
        conn.commit()

    return changes


def migrate_1_16_0(db):
    """Migration for v1.16.0 - decision relationships and tenant configuration."""
    db_type = get_db_type(db)
    changes = 0

    if not table_exists(db, 'decision_relationships'):
        if db_type == 'sqlite':
            create_sql = """
                CREATE TABLE decision_relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    source_decision_id INTEGER NOT NULL REFERENCES architecture_decisions(id) ON DELETE CASCADE,
                    target_decision_id INTEGER NOT NULL REFERENCES architecture_decisions(id) ON DELETE CASCADE,
                    relationship_type VARCHAR(64) NOT NULL,
                    notes TEXT,
                    target_previous_status VARCHAR(50),
                    created_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    updated_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    deleted_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    deleted_at TIMESTAMP
                )
            """
        else:
            create_sql = """
                CREATE TABLE decision_relationships (
                    id SERIAL PRIMARY KEY,
                    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    source_decision_id INTEGER NOT NULL REFERENCES architecture_decisions(id) ON DELETE CASCADE,
                    target_decision_id INTEGER NOT NULL REFERENCES architecture_decisions(id) ON DELETE CASCADE,
                    relationship_type VARCHAR(64) NOT NULL,
                    notes TEXT,
                    target_previous_status VARCHAR(50),
                    created_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    updated_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    deleted_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    deleted_at TIMESTAMP
                )
            """

        with db.engine.connect() as conn:
            conn.execute(db.text(create_sql))
            conn.commit()

        logger.info("Created decision_relationships table")
        changes += 1

    if table_exists(db, 'decision_relationships'):
        with db.engine.connect() as conn:
            conn.execute(db.text(
                "CREATE INDEX IF NOT EXISTS idx_decision_relationships_tenant_id "
                "ON decision_relationships(tenant_id)"
            ))
            conn.execute(db.text(
                "CREATE INDEX IF NOT EXISTS idx_decision_relationships_source_type "
                "ON decision_relationships(source_decision_id, relationship_type)"
            ))
            conn.execute(db.text(
                "CREATE INDEX IF NOT EXISTS idx_decision_relationships_target_type "
                "ON decision_relationships(target_decision_id, relationship_type)"
            ))
            conn.commit()

    if table_exists(db, 'tenant_settings'):
        if not column_exists(db, 'tenant_settings', 'decision_relationship_pack_ids'):
            add_column(db, 'tenant_settings', 'decision_relationship_pack_ids', 'TEXT')
            changes += 1
        if not column_exists(db, 'tenant_settings', 'decision_relationship_enabled_types'):
            add_column(db, 'tenant_settings', 'decision_relationship_enabled_types', 'TEXT')
            changes += 1
        if not column_exists(db, 'tenant_settings', 'decision_relationship_custom_types'):
            add_column(db, 'tenant_settings', 'decision_relationship_custom_types', 'TEXT')
            changes += 1

    return changes


def migrate_1_16_1(db):
    """Migration for v1.16.1 - ensure legacy databases have OAuth provider flags."""
    changes = 0
    oauth_columns = (
        ('allow_slack_oidc', 'BOOLEAN', True),
        ('allow_google_oauth', 'BOOLEAN', True),
        ('allow_microsoft_oauth', 'BOOLEAN', True),
    )

    for table_name in ('tenant_settings', 'auth_configs'):
        if not table_exists(db, table_name):
            continue

        for column_name, column_type, default in oauth_columns:
            if column_exists(db, table_name, column_name):
                continue
            add_column(db, table_name, column_name, column_type, default=default)
            changes += 1

    return changes


# Stored display defaults that named the product "Architecture Decisions".
# (table, column, old default, new default)
RENAMED_DISPLAY_DEFAULTS = (
    ('email_configs', 'from_name', 'Architecture Decisions', 'Decision Records'),
    ('auth_configs', 'rp_name', 'Architecture Decisions', 'Decision Records'),
    ('tenant_settings', 'rp_name', 'Architecture Decisions', 'Decision Records'),
    ('spaces', 'description', 'Default space for all architecture decisions',
     'Default space for all decisions'),
)


def migrate_2_2_0(db):
    """Migration for v2.2.0 - rename stored default display names.

    Data only. A value is changed only where it still equals the old default,
    so names an administrator chose are kept. Running it again changes nothing.
    These columns are display text: the email from-name, the passkey prompt
    name (rp_name, not rp_id) and the default space description.
    """
    changes = 0

    for table_name, column_name, old_default, new_default in RENAMED_DISPLAY_DEFAULTS:
        if not table_exists(db, table_name) or not column_exists(db, table_name, column_name):
            continue

        with db.engine.connect() as conn:
            result = conn.execute(
                db.text(f"UPDATE {table_name} SET {column_name} = :new WHERE {column_name} = :old"),
                {"new": new_default, "old": old_default}
            )
            conn.commit()

        if result.rowcount and result.rowcount > 0:
            logger.info(f"Renamed {result.rowcount} default value(s) in {table_name}.{column_name}")
            changes += result.rowcount

    return changes


def migrate_2_3_0(db):
    """Migration for v2.3.0 - inquiries table and tenant team profile columns.

    On a fresh database db.create_all() has already created everything and
    this changes nothing. On an existing database it creates the inquiries
    table and adds the four team profile columns to tenants. Safe to repeat.
    """
    changes = 0
    db_type = get_db_type(db)

    if not table_exists(db, 'inquiries'):
        id_column = (
            "id INTEGER PRIMARY KEY AUTOINCREMENT" if db_type == 'sqlite'
            else "id SERIAL PRIMARY KEY"
        )
        create_sql = f"""
            CREATE TABLE inquiries (
                {id_column},
                source VARCHAR(20) NOT NULL,
                name VARCHAR(100),
                email VARCHAR(255),
                organisation VARCHAR(200),
                area_of_interest VARCHAR(100),
                message TEXT,
                team_focus VARCHAR(200),
                team_size VARCHAR(20),
                contact_consent BOOLEAN,
                user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                tenant_domain VARCHAR(255),
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                email_sent BOOLEAN NOT NULL DEFAULT FALSE,
                handled BOOLEAN NOT NULL DEFAULT FALSE,
                handled_at TIMESTAMP,
                handled_by VARCHAR(255),
                redacted_at TIMESTAMP
            )
        """
        with db.engine.connect() as conn:
            conn.execute(db.text(create_sql))
            conn.commit()

        logger.info("Created inquiries table")
        changes += 1

    if table_exists(db, 'inquiries'):
        with db.engine.connect() as conn:
            for column_name in ('source', 'email', 'user_id', 'created_at', 'handled'):
                conn.execute(db.text(
                    f"CREATE INDEX IF NOT EXISTS ix_inquiries_{column_name} "
                    f"ON inquiries({column_name})"
                ))
            conn.commit()

    if table_exists(db, 'tenants'):
        team_profile_columns = (
            ('team_focus', 'VARCHAR(200)'),
            ('team_size', 'VARCHAR(20)'),
            ('team_profile_answered_at', 'TIMESTAMP'),
            ('team_profile_answered_by_id', 'INTEGER REFERENCES users(id) ON DELETE SET NULL'),
        )
        for column_name, column_type in team_profile_columns:
            if add_column(db, 'tenants', column_name, column_type):
                changes += 1

    return changes


def migrate_2_4_0(db):
    """Migration for v2.4.0 - run history of the data retention routine.

    Two new tables: retention_runs (one row per run, with a unique claim key
    that lets one worker claim the automatic run of a day) and
    retention_erasures (what each run erased). They are created from the model
    definitions, so the columns, the unique constraint and the indexes are the
    same as on a fresh database, on SQLite and on PostgreSQL. Running it again
    changes nothing.
    """
    from models import RetentionRun, RetentionErasure

    changes = 0
    for model in (RetentionRun, RetentionErasure):
        if table_exists(db, model.__tablename__):
            continue
        model.__table__.create(bind=db.engine, checkfirst=True)
        logger.info(f"Created {model.__tablename__} table")
        changes += 1

    return changes


def migrate_2_5_0(db):
    """Migration for v2.5.0 - finish the anonymisation of accounts anonymised earlier.

    Until this version, anonymising an account left the author's name on their
    comments (decision_comments.author_display), the name and description they
    gave their API keys, their role requests and the text of their AI queries.
    Accounts anonymised from now on are cleaned in full by
    retention._anonymise_user_record; this does the same for accounts that
    were already anonymised, which can be told apart by users.is_anonymized.

    What cannot be repaired here: text that was keyed by the person's email
    address or name (a failed sign-in recorded by address, the requester of a
    domain, a name inside an audit entry). The address and the name were
    erased with the account, so those rows can no longer be matched.

    Plain UPDATE and DELETE statements that SQLite and PostgreSQL both run.
    Safe to repeat: a second run finds nothing to change.
    """
    from retention import FORMER_MEMBER, DELETED_KEY_NAME

    anonymised = "SELECT id FROM users WHERE is_anonymized"
    statements = []
    if table_exists(db, 'users') and column_exists(db, 'users', 'is_anonymized'):
        if table_exists(db, 'decision_comments'):
            statements.append((
                f"UPDATE decision_comments SET author_display = :former "
                f"WHERE user_id IN ({anonymised}) "
                f"AND (author_display IS NULL OR author_display <> :former)",
                {'former': FORMER_MEMBER}))
        if table_exists(db, 'ai_api_keys'):
            statements.append((
                f"UPDATE ai_api_keys SET name = :name, description = NULL "
                f"WHERE user_id IN ({anonymised}) AND (name <> :name OR description IS NOT NULL)",
                {'name': DELETED_KEY_NAME}))
        if table_exists(db, 'ai_interaction_logs'):
            statements.append((
                f"UPDATE ai_interaction_logs SET query_text = NULL "
                f"WHERE user_id IN ({anonymised}) AND query_text IS NOT NULL", {}))
        if table_exists(db, 'role_requests'):
            statements.append((f"DELETE FROM role_requests WHERE user_id IN ({anonymised})", {}))

    changes = 0
    with db.engine.connect() as conn:
        for sql, params in statements:
            changes += conn.execute(db.text(sql), params).rowcount or 0
        conn.commit()

    if changes:
        logger.info(f"Finished the anonymisation of earlier deleted accounts ({changes} rows)")
    return changes


DECISION_TEMPLATE_COLUMNS = (
    ('tenants', 'industry', 'VARCHAR(8)'),
    ('tenant_settings', 'decision_template_id', 'VARCHAR(64)'),
    ('tenant_settings', 'decision_template_notice_dismissed_at', 'TIMESTAMP'),
    ('architecture_decisions', 'decision_type', 'VARCHAR(100)'),
    ('decision_history', 'decision_type', 'VARCHAR(100)'),
)


def migrate_2_6_0(db):
    """Migration for v2.6.0 - decision templates, industry and decision type.

    Five nullable columns and nothing else: no existing row is read or
    changed. A tenant without a template keeps the default (General) layout,
    and a decision without a type is valid. The same ALTER TABLE statements
    run on SQLite and PostgreSQL; a second run finds every column in place.
    """
    changes = 0
    for table_name, column_name, column_type in DECISION_TEMPLATE_COLUMNS:
        if not table_exists(db, table_name):
            continue
        if add_column(db, table_name, column_name, column_type):
            changes += 1
    return changes


def migrate_2_7_0(db):
    """Migration for v2.7.0 - tables for OAuth authorization of the MCP server.

    Four new, empty tables: oauth_clients, oauth_grants,
    oauth_authorization_requests and oauth_tokens. They are created from the
    model definitions, in the order their foreign keys need, so columns,
    unique constraints and indexes are the same as on a fresh database, on
    SQLite and on PostgreSQL. No existing table or row is touched, and a
    second run finds every table in place. Only the Enterprise Edition writes
    to them; in the Community Edition they stay empty.
    """
    from models import OAuthClient, OAuthGrant, OAuthAuthorizationRequest, OAuthToken

    changes = 0
    for model in (OAuthClient, OAuthGrant, OAuthAuthorizationRequest, OAuthToken):
        if table_exists(db, model.__tablename__):
            continue
        model.__table__.create(bind=db.engine, checkfirst=True)
        logger.info(f"Created {model.__tablename__} table")
        changes += 1

    return changes


OAUTH_TOKEN_REUSE_COLUMNS = ('withdrawn_at', 'repeat_answered_at')


def migrate_2_8_0(db):
    """Migration for v2.8.0 - oauth_tokens.withdrawn_at and repeat_answered_at.

    Two nullable columns on a table that 2.7.0 created; no row is read or
    changed. A database that gets oauth_tokens from the current model (a
    fresh one, or one where 2.7.0 runs now) already has the columns, and a
    second run finds them in place.
    """
    if not table_exists(db, 'oauth_tokens'):
        return 0
    changes = 0
    for column_name in OAUTH_TOKEN_REUSE_COLUMNS:
        if add_column(db, 'oauth_tokens', column_name, 'TIMESTAMP'):
            changes += 1
    return changes


def encrypt_sso_client_secrets(db):
    """Encrypt SSO client secrets that are still stored as plain text. Returns how many.

    Uses crypto.encrypt_password, the mechanism that protects saved SMTP
    passwords: a value that is already encrypted is left alone, and without an
    encryption key (a Community installation that has not set
    SMTP_ENCRYPTION_KEY) nothing is changed, so a value is never lost. Each
    new value is decrypted again before it is stored. Safe to run any number
    of times; the application also runs it at every start, so secrets are
    encrypted on the first start after a key is configured.
    """
    from crypto import encrypt_password, decrypt_password, is_password_encrypted

    if not table_exists(db, 'sso_configs'):
        return 0

    changes = 0
    with db.engine.connect() as conn:
        rows = conn.execute(db.text("SELECT id, client_secret FROM sso_configs")).fetchall()
        for row_id, secret in rows:
            if not secret or is_password_encrypted(secret):
                continue
            encrypted = encrypt_password(secret)
            if not is_password_encrypted(encrypted) or decrypt_password(encrypted) != secret:
                # No key, or the key does not round-trip: leave the value as it is
                continue
            conn.execute(
                db.text("UPDATE sso_configs SET client_secret = :secret WHERE id = :id AND client_secret = :old"),
                {"secret": encrypted, "id": row_id, "old": secret})
            changes += 1
        conn.commit()

    if changes:
        logger.info(f"Encrypted {changes} SSO client secret(s) at rest")
    return changes


def migrate_2_9_0(db):
    """Migration for v2.9.0 - encrypted SSO client secrets and users.name_edited_at.

    1. sso_configs.client_secret is widened to 1024 characters on PostgreSQL
       (an encrypted value is about twice as long as the secret; SQLite does
       not enforce the length). Widening a VARCHAR rewrites nothing.
    2. Existing client secrets are encrypted in place: see
       encrypt_sso_client_secrets. Reads accept both forms, so a secret that
       could not be encrypted now (no key yet) keeps working.
    3. users.name_edited_at, a nullable timestamp, is added. No row is changed.

    A second run finds the column wide enough, every secret encrypted and the
    new column in place.
    """
    changes = 0

    if table_exists(db, 'sso_configs') and get_db_type(db) == 'postgresql':
        with db.engine.connect() as conn:
            current = conn.execute(db.text(
                "SELECT character_maximum_length FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'sso_configs' "
                "AND column_name = 'client_secret'")).scalar()
            if current is not None and current < 1024:
                conn.execute(db.text(
                    "ALTER TABLE sso_configs ALTER COLUMN client_secret TYPE VARCHAR(1024)"))
                changes += 1
            conn.commit()

    changes += encrypt_sso_client_secrets(db)

    if table_exists(db, 'users') and add_column(db, 'users', 'name_edited_at', 'TIMESTAMP'):
        changes += 1

    return changes


# =============================================================================
# Migration Runner
# =============================================================================

def run_migrations(db):
    """
    Run all pending migrations.

    This is called from init_database() in app.py on every startup.
    It's safe to call multiple times - already applied migrations are skipped.

    Args:
        db: SQLAlchemy database instance

    Returns:
        int: Number of migrations applied
    """
    logger.info("Checking for pending database migrations...")

    # Ensure migrations tracking table exists
    ensure_migrations_table(db)

    # Get already applied migrations
    applied = get_applied_migrations(db)
    logger.debug(f"Already applied migrations: {applied}")

    # Run pending migrations in order
    total_changes = 0
    migrations_applied = 0

    for migration in MIGRATIONS:
        version = migration["version"]

        if version in applied:
            logger.debug(f"Migration {version} already applied, skipping")
            continue

        description = migration["description"]
        logger.info(f"Applying migration {version}: {description}")

        try:
            changes = migration["migrate"](db)
            record_migration(db, version, description)
            total_changes += changes
            migrations_applied += 1
            logger.info(f"Migration {version} completed ({changes} changes)")
        except Exception as e:
            logger.error(f"Migration {version} failed: {e}")
            raise

    if migrations_applied > 0:
        logger.info(f"Applied {migrations_applied} migration(s) with {total_changes} total changes")
    else:
        logger.info("No pending migrations")

    return migrations_applied
