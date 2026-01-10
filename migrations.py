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
