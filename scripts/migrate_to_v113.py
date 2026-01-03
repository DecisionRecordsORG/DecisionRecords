#!/usr/bin/env python3
"""
Migration script for v1.13.0 - AI, Slack, Teams, and Blog features.

This script adds new tables and columns for:
- AI/LLM integration (API keys, interaction logs, tenant AI settings)
- Slack integration (workspaces, user mappings)
- Microsoft Teams integration (workspaces, user mappings, conversation references)
- Blog posts
- OAuth sign-in options (Slack OIDC, Google OAuth)

Migration Steps:
1. Add new columns to existing tables (tenants, tenant_memberships, tenant_settings, auth_configs)
2. Create new tables (slack_workspaces, slack_user_mappings, teams_workspaces, etc.)

Usage:
    python scripts/migrate_to_v113.py [--dry-run] [--verbose]

Options:
    --dry-run   Show what would be done without making changes
    --verbose   Print detailed progress
"""
import os
import sys
import argparse
import re

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():
    """Get database connection from environment."""
    database_url = os.environ.get('DATABASE_URL')

    if database_url:
        # Parse the DATABASE_URL
        # Format: postgresql://user:password@host:port/database?sslmode=require
        match = re.match(r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/([^?]+)(\?.*)?', database_url)
        if match:
            user, password, host, port, database, params = match.groups()
            return psycopg2.connect(
                host=host,
                port=int(port),
                database=database,
                user=user,
                password=password,
                sslmode='require'
            )

    # Fallback to individual env vars
    return psycopg2.connect(
        host=os.environ.get('POSTGRES_HOST', 'localhost'),
        port=int(os.environ.get('POSTGRES_PORT', 5432)),
        database=os.environ.get('POSTGRES_DB', 'postgres'),
        user=os.environ.get('POSTGRES_USER', 'adruser'),
        password=os.environ.get('POSTGRES_PASSWORD', ''),
        sslmode='require'
    )


def table_exists(cur, table_name):
    """Check if a table exists."""
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = %s
        )
    """, (table_name,))
    return cur.fetchone()[0]


def column_exists(cur, table_name, column_name):
    """Check if a column exists in a table."""
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = %s
            AND column_name = %s
        )
    """, (table_name, column_name))
    return cur.fetchone()[0]


def type_exists(cur, type_name):
    """Check if a PostgreSQL type (enum) exists."""
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM pg_type
            WHERE typname = %s
        )
    """, (type_name,))
    return cur.fetchone()[0]


def add_columns_to_tenants(cur, dry_run=False, verbose=False):
    """Add AI feature columns to tenants table."""
    if verbose:
        print("\nAdding AI columns to tenants table...")

    columns = [
        ('ai_features_enabled', 'BOOLEAN DEFAULT FALSE'),
        ('ai_slack_queries_enabled', 'BOOLEAN DEFAULT FALSE'),
        ('ai_assisted_creation_enabled', 'BOOLEAN DEFAULT FALSE'),
        ('ai_external_access_enabled', 'BOOLEAN DEFAULT FALSE'),
        ('ai_require_anonymization', 'BOOLEAN DEFAULT TRUE'),
        ('ai_log_interactions', 'BOOLEAN DEFAULT TRUE'),
    ]

    added = 0
    for col_name, col_def in columns:
        if column_exists(cur, 'tenants', col_name):
            if verbose:
                print(f"  Column '{col_name}' already exists")
            continue

        if dry_run:
            print(f"  [DRY-RUN] Would add column '{col_name}' to tenants")
        else:
            cur.execute(f"ALTER TABLE tenants ADD COLUMN {col_name} {col_def}")
            print(f"  Added column '{col_name}' to tenants")
            added += 1

    return added


def add_columns_to_tenant_memberships(cur, dry_run=False, verbose=False):
    """Add AI opt-out column to tenant_memberships table."""
    if verbose:
        print("\nAdding AI columns to tenant_memberships table...")

    columns = [
        ('ai_opt_out', 'BOOLEAN DEFAULT FALSE'),
    ]

    added = 0
    for col_name, col_def in columns:
        if column_exists(cur, 'tenant_memberships', col_name):
            if verbose:
                print(f"  Column '{col_name}' already exists")
            continue

        if dry_run:
            print(f"  [DRY-RUN] Would add column '{col_name}' to tenant_memberships")
        else:
            cur.execute(f"ALTER TABLE tenant_memberships ADD COLUMN {col_name} {col_def}")
            print(f"  Added column '{col_name}' to tenant_memberships")
            added += 1

    return added


def add_columns_to_tenant_settings(cur, dry_run=False, verbose=False):
    """Add OAuth columns to tenant_settings table."""
    if verbose:
        print("\nAdding OAuth columns to tenant_settings table...")

    columns = [
        ('allow_slack_oidc', 'BOOLEAN DEFAULT TRUE'),
        ('allow_google_oauth', 'BOOLEAN DEFAULT TRUE'),
    ]

    added = 0
    for col_name, col_def in columns:
        if column_exists(cur, 'tenant_settings', col_name):
            if verbose:
                print(f"  Column '{col_name}' already exists")
            continue

        if dry_run:
            print(f"  [DRY-RUN] Would add column '{col_name}' to tenant_settings")
        else:
            cur.execute(f"ALTER TABLE tenant_settings ADD COLUMN {col_name} {col_def}")
            print(f"  Added column '{col_name}' to tenant_settings")
            added += 1

    return added


def add_columns_to_auth_configs(cur, dry_run=False, verbose=False):
    """Add OAuth columns to auth_configs table."""
    if verbose:
        print("\nAdding OAuth columns to auth_configs table...")

    columns = [
        ('allow_slack_oidc', 'BOOLEAN DEFAULT TRUE'),
        ('allow_google_oauth', 'BOOLEAN DEFAULT TRUE'),
    ]

    added = 0
    for col_name, col_def in columns:
        if column_exists(cur, 'auth_configs', col_name):
            if verbose:
                print(f"  Column '{col_name}' already exists")
            continue

        if dry_run:
            print(f"  [DRY-RUN] Would add column '{col_name}' to auth_configs")
        else:
            cur.execute(f"ALTER TABLE auth_configs ADD COLUMN {col_name} {col_def}")
            print(f"  Added column '{col_name}' to auth_configs")
            added += 1

    return added


def create_enum_types(cur, dry_run=False, verbose=False):
    """Create enum types for AI integration."""
    if verbose:
        print("\nCreating enum types...")

    enums = [
        ('aichannel', ['slack', 'teams', 'mcp', 'api', 'web']),
        ('aiaction', ['search', 'read', 'create', 'update', 'query']),
    ]

    created = 0
    for enum_name, values in enums:
        if type_exists(cur, enum_name):
            if verbose:
                print(f"  Enum type '{enum_name}' already exists")
            continue

        if dry_run:
            print(f"  [DRY-RUN] Would create enum type '{enum_name}'")
        else:
            values_str = ", ".join([f"'{v}'" for v in values])
            cur.execute(f"CREATE TYPE {enum_name} AS ENUM ({values_str})")
            print(f"  Created enum type '{enum_name}'")
            created += 1

    return created


def create_slack_tables(cur, dry_run=False, verbose=False):
    """Create Slack integration tables."""
    if verbose:
        print("\nCreating Slack integration tables...")

    created = 0

    # slack_workspaces
    if not table_exists(cur, 'slack_workspaces'):
        if dry_run:
            print("  [DRY-RUN] Would create slack_workspaces table")
        else:
            cur.execute("""
                CREATE TABLE slack_workspaces (
                    id SERIAL PRIMARY KEY,
                    tenant_id INTEGER UNIQUE REFERENCES tenants(id),
                    workspace_id VARCHAR(50) NOT NULL UNIQUE,
                    workspace_name VARCHAR(255),
                    bot_token_encrypted TEXT NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending_claim',
                    claimed_at TIMESTAMP,
                    claimed_by_id INTEGER REFERENCES users(id),
                    default_channel_id VARCHAR(50),
                    default_channel_name VARCHAR(255),
                    notifications_enabled BOOLEAN DEFAULT TRUE,
                    notify_on_create BOOLEAN DEFAULT TRUE,
                    notify_on_status_change BOOLEAN DEFAULT TRUE,
                    is_active BOOLEAN DEFAULT TRUE,
                    installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity_at TIMESTAMP,
                    granted_scopes TEXT,
                    scopes_updated_at TIMESTAMP,
                    app_version VARCHAR(20)
                )
            """)
            cur.execute("CREATE INDEX idx_slack_workspaces_tenant ON slack_workspaces(tenant_id)")
            cur.execute("CREATE INDEX idx_slack_workspaces_workspace ON slack_workspaces(workspace_id)")
            print("  Created slack_workspaces table")
            created += 1
    elif verbose:
        print("  slack_workspaces table already exists")

    # slack_user_mappings
    if not table_exists(cur, 'slack_user_mappings'):
        if dry_run:
            print("  [DRY-RUN] Would create slack_user_mappings table")
        else:
            cur.execute("""
                CREATE TABLE slack_user_mappings (
                    id SERIAL PRIMARY KEY,
                    slack_workspace_id INTEGER NOT NULL REFERENCES slack_workspaces(id),
                    slack_user_id VARCHAR(50) NOT NULL,
                    slack_email VARCHAR(320),
                    user_id INTEGER REFERENCES users(id),
                    link_method VARCHAR(20),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    linked_at TIMESTAMP,
                    CONSTRAINT uq_slack_user_workspace UNIQUE (slack_workspace_id, slack_user_id)
                )
            """)
            cur.execute("CREATE INDEX idx_slack_user_mappings_workspace ON slack_user_mappings(slack_workspace_id)")
            cur.execute("CREATE INDEX idx_slack_user_mappings_user ON slack_user_mappings(slack_user_id)")
            print("  Created slack_user_mappings table")
            created += 1
    elif verbose:
        print("  slack_user_mappings table already exists")

    return created


def create_teams_tables(cur, dry_run=False, verbose=False):
    """Create Microsoft Teams integration tables."""
    if verbose:
        print("\nCreating Microsoft Teams integration tables...")

    created = 0

    # teams_workspaces
    if not table_exists(cur, 'teams_workspaces'):
        if dry_run:
            print("  [DRY-RUN] Would create teams_workspaces table")
        else:
            cur.execute("""
                CREATE TABLE teams_workspaces (
                    id SERIAL PRIMARY KEY,
                    tenant_id INTEGER UNIQUE REFERENCES tenants(id),
                    ms_tenant_id VARCHAR(50) NOT NULL UNIQUE,
                    ms_tenant_name VARCHAR(255),
                    service_url VARCHAR(500),
                    bot_id VARCHAR(100),
                    status VARCHAR(20) DEFAULT 'pending_consent',
                    consent_granted_at TIMESTAMP,
                    consent_granted_by_id INTEGER REFERENCES users(id),
                    default_channel_id VARCHAR(100),
                    default_channel_name VARCHAR(255),
                    default_team_id VARCHAR(100),
                    default_team_name VARCHAR(255),
                    notifications_enabled BOOLEAN DEFAULT TRUE,
                    notify_on_create BOOLEAN DEFAULT TRUE,
                    notify_on_status_change BOOLEAN DEFAULT TRUE,
                    is_active BOOLEAN DEFAULT TRUE,
                    installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity_at TIMESTAMP,
                    app_version VARCHAR(20)
                )
            """)
            cur.execute("CREATE INDEX idx_teams_workspaces_tenant ON teams_workspaces(tenant_id)")
            cur.execute("CREATE INDEX idx_teams_workspaces_ms_tenant ON teams_workspaces(ms_tenant_id)")
            print("  Created teams_workspaces table")
            created += 1
    elif verbose:
        print("  teams_workspaces table already exists")

    # teams_user_mappings
    if not table_exists(cur, 'teams_user_mappings'):
        if dry_run:
            print("  [DRY-RUN] Would create teams_user_mappings table")
        else:
            cur.execute("""
                CREATE TABLE teams_user_mappings (
                    id SERIAL PRIMARY KEY,
                    teams_workspace_id INTEGER NOT NULL REFERENCES teams_workspaces(id),
                    aad_object_id VARCHAR(50) NOT NULL,
                    aad_user_principal_name VARCHAR(320),
                    aad_email VARCHAR(320),
                    aad_display_name VARCHAR(255),
                    user_id INTEGER REFERENCES users(id),
                    link_method VARCHAR(20),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    linked_at TIMESTAMP,
                    CONSTRAINT uq_teams_user_workspace UNIQUE (teams_workspace_id, aad_object_id)
                )
            """)
            cur.execute("CREATE INDEX idx_teams_user_mappings_workspace ON teams_user_mappings(teams_workspace_id)")
            cur.execute("CREATE INDEX idx_teams_user_mappings_aad ON teams_user_mappings(aad_object_id)")
            print("  Created teams_user_mappings table")
            created += 1
    elif verbose:
        print("  teams_user_mappings table already exists")

    # teams_conversation_references
    if not table_exists(cur, 'teams_conversation_references'):
        if dry_run:
            print("  [DRY-RUN] Would create teams_conversation_references table")
        else:
            cur.execute("""
                CREATE TABLE teams_conversation_references (
                    id SERIAL PRIMARY KEY,
                    teams_workspace_id INTEGER NOT NULL REFERENCES teams_workspaces(id),
                    conversation_id VARCHAR(500) NOT NULL,
                    channel_id VARCHAR(100),
                    team_id VARCHAR(100),
                    reference_json TEXT NOT NULL,
                    context_type VARCHAR(20) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT uq_teams_conversation UNIQUE (teams_workspace_id, conversation_id)
                )
            """)
            cur.execute("CREATE INDEX idx_teams_conv_ref_workspace ON teams_conversation_references(teams_workspace_id)")
            print("  Created teams_conversation_references table")
            created += 1
    elif verbose:
        print("  teams_conversation_references table already exists")

    return created


def create_blog_table(cur, dry_run=False, verbose=False):
    """Create blog_posts table."""
    if verbose:
        print("\nCreating blog_posts table...")

    if table_exists(cur, 'blog_posts'):
        if verbose:
            print("  blog_posts table already exists")
        return 0

    if dry_run:
        print("  [DRY-RUN] Would create blog_posts table")
        return 0

    cur.execute("""
        CREATE TABLE blog_posts (
            id SERIAL PRIMARY KEY,
            slug VARCHAR(255) NOT NULL UNIQUE,
            title VARCHAR(500) NOT NULL,
            excerpt TEXT NOT NULL,
            author VARCHAR(255) NOT NULL DEFAULT 'Decision Records',
            category VARCHAR(100) NOT NULL,
            read_time VARCHAR(50) NOT NULL DEFAULT '5 min read',
            image VARCHAR(500),
            meta_description VARCHAR(300),
            meta_keywords VARCHAR(500),
            published BOOLEAN DEFAULT TRUE,
            featured BOOLEAN DEFAULT FALSE,
            publish_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("CREATE INDEX idx_blog_posts_slug ON blog_posts(slug)")
    cur.execute("CREATE INDEX idx_blog_posts_published ON blog_posts(published)")
    print("  Created blog_posts table")
    return 1


def create_ai_tables(cur, dry_run=False, verbose=False):
    """Create AI/LLM integration tables."""
    if verbose:
        print("\nCreating AI/LLM integration tables...")

    created = 0

    # ai_api_keys
    if not table_exists(cur, 'ai_api_keys'):
        if dry_run:
            print("  [DRY-RUN] Would create ai_api_keys table")
        else:
            cur.execute("""
                CREATE TABLE ai_api_keys (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
                    key_hash VARCHAR(64) NOT NULL UNIQUE,
                    key_prefix VARCHAR(8) NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    description VARCHAR(500),
                    scopes JSONB DEFAULT '["read", "search"]',
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_used_at TIMESTAMP,
                    expires_at TIMESTAMP,
                    revoked_at TIMESTAMP
                )
            """)
            cur.execute("CREATE INDEX idx_ai_api_key_hash ON ai_api_keys(key_hash)")
            cur.execute("CREATE INDEX idx_ai_api_key_user ON ai_api_keys(user_id)")
            cur.execute("CREATE INDEX idx_ai_api_key_tenant ON ai_api_keys(tenant_id)")
            print("  Created ai_api_keys table")
            created += 1
    elif verbose:
        print("  ai_api_keys table already exists")

    # ai_interaction_logs
    if not table_exists(cur, 'ai_interaction_logs'):
        if dry_run:
            print("  [DRY-RUN] Would create ai_interaction_logs table")
        else:
            # First ensure the enum types exist
            if not type_exists(cur, 'aichannel'):
                cur.execute("CREATE TYPE aichannel AS ENUM ('slack', 'teams', 'mcp', 'api', 'web')")
            if not type_exists(cur, 'aiaction'):
                cur.execute("CREATE TYPE aiaction AS ENUM ('search', 'read', 'create', 'update', 'query')")

            cur.execute("""
                CREATE TABLE ai_interaction_logs (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    tenant_id INTEGER REFERENCES tenants(id),
                    api_key_id INTEGER REFERENCES ai_api_keys(id),
                    channel aichannel NOT NULL,
                    action aiaction NOT NULL,
                    query_text TEXT,
                    query_anonymized BOOLEAN DEFAULT FALSE,
                    decision_ids JSONB,
                    decision_count INTEGER DEFAULT 0,
                    llm_provider VARCHAR(50),
                    llm_model VARCHAR(100),
                    tokens_input INTEGER,
                    tokens_output INTEGER,
                    duration_ms INTEGER,
                    success BOOLEAN DEFAULT TRUE,
                    error_message VARCHAR(500),
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("CREATE INDEX idx_ai_log_tenant_created ON ai_interaction_logs(tenant_id, created_at)")
            cur.execute("CREATE INDEX idx_ai_log_user_created ON ai_interaction_logs(user_id, created_at)")
            cur.execute("CREATE INDEX idx_ai_log_channel ON ai_interaction_logs(channel)")
            cur.execute("CREATE INDEX idx_ai_log_action ON ai_interaction_logs(action)")
            print("  Created ai_interaction_logs table")
            created += 1
    elif verbose:
        print("  ai_interaction_logs table already exists")

    return created


def print_migration_summary(cur, dry_run=False):
    """Print summary of the migration."""
    print("\n" + "=" * 60)
    print("Migration Summary")
    print("=" * 60)

    if dry_run:
        print("DRY-RUN: No changes were made")
        return

    # Check column counts
    tables_with_new_cols = ['tenants', 'tenant_memberships', 'tenant_settings', 'auth_configs']
    for table in tables_with_new_cols:
        cur.execute(f"""
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = '{table}'
        """)
        col_count = cur.fetchone()[0]
        print(f"  {table}: {col_count} columns")

    # Check new tables
    new_tables = [
        'slack_workspaces', 'slack_user_mappings',
        'teams_workspaces', 'teams_user_mappings', 'teams_conversation_references',
        'blog_posts', 'ai_api_keys', 'ai_interaction_logs'
    ]
    print("\nNew tables:")
    for table in new_tables:
        exists = table_exists(cur, table)
        status = "EXISTS" if exists else "MISSING"
        print(f"  {table}: {status}")


def main():
    parser = argparse.ArgumentParser(description='Migrate database to v1.13.0 (AI, Slack, Teams, Blog)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--verbose', '-v', action='store_true', help='Print detailed progress')
    args = parser.parse_args()

    print("=" * 60)
    print("v1.13.0 Migration - AI, Slack, Teams, Blog Features")
    print("=" * 60)

    if args.dry_run:
        print("DRY-RUN MODE: No changes will be made\n")

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        total_changes = 0

        # Step 1: Add columns to existing tables
        print("\nStep 1: Adding columns to existing tables...")
        total_changes += add_columns_to_tenants(cur, dry_run=args.dry_run, verbose=args.verbose)
        total_changes += add_columns_to_tenant_memberships(cur, dry_run=args.dry_run, verbose=args.verbose)
        total_changes += add_columns_to_tenant_settings(cur, dry_run=args.dry_run, verbose=args.verbose)
        total_changes += add_columns_to_auth_configs(cur, dry_run=args.dry_run, verbose=args.verbose)

        # Step 2: Create enum types
        print("\nStep 2: Creating enum types...")
        total_changes += create_enum_types(cur, dry_run=args.dry_run, verbose=args.verbose)

        # Step 3: Create Slack tables
        print("\nStep 3: Creating Slack integration tables...")
        total_changes += create_slack_tables(cur, dry_run=args.dry_run, verbose=args.verbose)

        # Step 4: Create Teams tables
        print("\nStep 4: Creating Microsoft Teams integration tables...")
        total_changes += create_teams_tables(cur, dry_run=args.dry_run, verbose=args.verbose)

        # Step 5: Create blog table
        print("\nStep 5: Creating blog table...")
        total_changes += create_blog_table(cur, dry_run=args.dry_run, verbose=args.verbose)

        # Step 6: Create AI tables
        print("\nStep 6: Creating AI/LLM integration tables...")
        total_changes += create_ai_tables(cur, dry_run=args.dry_run, verbose=args.verbose)

        # Commit if not dry run
        if not args.dry_run:
            conn.commit()
            print(f"\nCommitted {total_changes} changes to database")

        # Print summary
        print_migration_summary(cur, dry_run=args.dry_run)

        cur.close()
        conn.close()

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\nMigration complete!")


if __name__ == '__main__':
    main()
