#!/usr/bin/env python3
"""
Migration script for v1.14.0 - Login History Tracking

This script adds the login_history table for tracking all login attempts
across the system.

New table:
- login_history: Tracks all login attempts with method, IP, success status

Usage:
    # Preview changes (dry-run)
    DATABASE_URL="postgresql://..." python scripts/migrate_to_v114.py --dry-run --verbose

    # Apply changes
    DATABASE_URL="postgresql://..." python scripts/migrate_to_v114.py --verbose
"""

import os
import sys
import argparse
import psycopg2
from psycopg2.extras import RealDictCursor


def get_database_url():
    """Get database URL from environment."""
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        return database_url

    # Try to construct from individual components
    host = os.environ.get('DB_HOST')
    user = os.environ.get('DB_USER')
    password = os.environ.get('DB_PASSWORD')
    dbname = os.environ.get('DB_NAME', 'postgres')

    if host and user and password:
        return f"postgresql://{user}:{password}@{host}:5432/{dbname}?sslmode=require"

    return None


def table_exists(cur, table_name):
    """Check if a table exists in the database."""
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = %s
        )
    """, (table_name,))
    return cur.fetchone()[0]


def index_exists(cur, index_name):
    """Check if an index exists in the database."""
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM pg_indexes
            WHERE schemaname = 'public'
            AND indexname = %s
        )
    """, (index_name,))
    return cur.fetchone()[0]


def create_login_history_table(cur, dry_run=False, verbose=False):
    """Create the login_history table."""
    if verbose:
        print("\n[1/5] Checking login_history table...")

    if table_exists(cur, 'login_history'):
        if verbose:
            print("  Table 'login_history' already exists, skipping")
        return 0

    if dry_run:
        if verbose:
            print("  [DRY-RUN] Would create table 'login_history'")
        return 0

    if verbose:
        print("  Creating table 'login_history'...")

    cur.execute("""
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
    """)

    if verbose:
        print("  Created table 'login_history'")
    return 1


def create_login_history_indexes(cur, dry_run=False, verbose=False):
    """Create indexes for the login_history table."""
    indexes = [
        ('idx_login_history_user', 'CREATE INDEX idx_login_history_user ON login_history(user_id)'),
        ('idx_login_history_email', 'CREATE INDEX idx_login_history_email ON login_history(email)'),
        ('idx_login_history_tenant', 'CREATE INDEX idx_login_history_tenant ON login_history(tenant_domain)'),
        ('idx_login_history_created', 'CREATE INDEX idx_login_history_created ON login_history(created_at)'),
        ('idx_login_history_success', 'CREATE INDEX idx_login_history_success ON login_history(success)'),
    ]

    created = 0
    for i, (index_name, create_sql) in enumerate(indexes, start=2):
        if verbose:
            print(f"\n[{i}/5] Checking index '{index_name}'...")

        if index_exists(cur, index_name):
            if verbose:
                print(f"  Index '{index_name}' already exists, skipping")
            continue

        if dry_run:
            if verbose:
                print(f"  [DRY-RUN] Would create index '{index_name}'")
            continue

        if verbose:
            print(f"  Creating index '{index_name}'...")

        cur.execute(create_sql)
        created += 1

        if verbose:
            print(f"  Created index '{index_name}'")

    return created


def run_migration(dry_run=False, verbose=False):
    """Run the migration."""
    database_url = get_database_url()
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        print("Set it directly or provide DB_HOST, DB_USER, DB_PASSWORD")
        sys.exit(1)

    print("=" * 60)
    print("Migration v1.14.0 - Login History Tracking")
    print("=" * 60)

    if dry_run:
        print("\n*** DRY-RUN MODE - No changes will be made ***\n")

    try:
        conn = psycopg2.connect(database_url)
        conn.autocommit = False
        cur = conn.cursor()

        changes = 0

        # Create login_history table
        changes += create_login_history_table(cur, dry_run, verbose)

        # Create indexes (only if table exists)
        if table_exists(cur, 'login_history'):
            changes += create_login_history_indexes(cur, dry_run, verbose)

        if dry_run:
            print("\n" + "=" * 60)
            print(f"DRY-RUN COMPLETE: {changes} change(s) would be made")
            print("=" * 60)
            conn.rollback()
        else:
            conn.commit()
            print("\n" + "=" * 60)
            print(f"MIGRATION COMPLETE: {changes} change(s) applied")
            print("=" * 60)

        cur.close()
        conn.close()

    except psycopg2.Error as e:
        print(f"\nERROR: Database error: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='Migration script for v1.14.0 - Login History Tracking'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without applying them'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed progress'
    )

    args = parser.parse_args()
    run_migration(dry_run=args.dry_run, verbose=args.verbose)


if __name__ == '__main__':
    main()
