#!/usr/bin/env python3
"""
Migration script for v1.5 Governance Model.

This script migrates the database from the old domain-based multi-tenancy
to the new Tenant/TenantMembership model.

Migration Steps:
1. Create new tables (tenants, tenant_memberships, tenant_settings, spaces, decision_spaces, audit_logs)
2. Populate tenants from existing unique domains
3. Create TenantMemberships for all existing users
4. Migrate settings from AuthConfig to TenantSettings
5. Create default Space for each tenant
6. Link existing decisions to tenants
7. Assign appropriate roles

Usage:
    python scripts/migrate_to_v15.py [--dry-run] [--verbose]

Options:
    --dry-run   Show what would be done without making changes
    --verbose   Print detailed progress
"""
import os
import sys
import argparse
import re
from datetime import datetime

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


def create_new_tables(cur, dry_run=False, verbose=False):
    """Create the new v1.5 tables if they don't exist."""
    if verbose:
        print("Step 1: Creating new tables...")

    # Check what tables need to be created
    tables_to_create = []
    if not table_exists(cur, 'tenants'):
        tables_to_create.append('tenants')
    if not table_exists(cur, 'tenant_memberships'):
        tables_to_create.append('tenant_memberships')
    if not table_exists(cur, 'tenant_settings'):
        tables_to_create.append('tenant_settings')
    if not table_exists(cur, 'spaces'):
        tables_to_create.append('spaces')
    if not table_exists(cur, 'decision_spaces'):
        tables_to_create.append('decision_spaces')
    if not table_exists(cur, 'audit_logs'):
        tables_to_create.append('audit_logs')

    if not tables_to_create:
        print("  All v1.5 tables already exist")
    else:
        print(f"  Tables to create: {', '.join(tables_to_create)}")

    if dry_run:
        print("  [DRY-RUN] Would create above tables")
        return

    # Create tenants table
    if 'tenants' in tables_to_create:
        cur.execute("""
            CREATE TABLE tenants (
                id SERIAL PRIMARY KEY,
                domain VARCHAR(255) NOT NULL UNIQUE,
                name VARCHAR(255),
                status VARCHAR(20) DEFAULT 'active',
                maturity_state VARCHAR(20) DEFAULT 'bootstrap',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                maturity_age_days INTEGER DEFAULT 14,
                maturity_user_threshold INTEGER DEFAULT 5
            )
        """)
        cur.execute("CREATE INDEX idx_tenants_domain ON tenants(domain)")
        print("  Created tenants table")

    # Create tenant_memberships table
    if 'tenant_memberships' in tables_to_create:
        cur.execute("""
            CREATE TABLE tenant_memberships (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                tenant_id INTEGER NOT NULL REFERENCES tenants(id),
                global_role VARCHAR(30) DEFAULT 'user',
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT unique_user_tenant UNIQUE (user_id, tenant_id)
            )
        """)
        cur.execute("CREATE INDEX idx_tenant_memberships_user ON tenant_memberships(user_id)")
        cur.execute("CREATE INDEX idx_tenant_memberships_tenant ON tenant_memberships(tenant_id)")
        print("  Created tenant_memberships table")

    # Create tenant_settings table
    if 'tenant_settings' in tables_to_create:
        cur.execute("""
            CREATE TABLE tenant_settings (
                id SERIAL PRIMARY KEY,
                tenant_id INTEGER NOT NULL UNIQUE REFERENCES tenants(id),
                auth_method VARCHAR(20) DEFAULT 'local',
                allow_password BOOLEAN DEFAULT TRUE,
                allow_passkey BOOLEAN DEFAULT TRUE,
                rp_name VARCHAR(255) DEFAULT 'Architecture Decisions',
                allow_registration BOOLEAN DEFAULT TRUE,
                require_approval BOOLEAN DEFAULT FALSE,
                tenant_prefix VARCHAR(3) UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("  Created tenant_settings table")

    # Create spaces table
    if 'spaces' in tables_to_create:
        cur.execute("""
            CREATE TABLE spaces (
                id SERIAL PRIMARY KEY,
                tenant_id INTEGER NOT NULL REFERENCES tenants(id),
                name VARCHAR(255) NOT NULL,
                description TEXT,
                is_default BOOLEAN DEFAULT FALSE,
                visibility_policy VARCHAR(30) DEFAULT 'tenant_visible',
                created_by_id INTEGER REFERENCES users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("CREATE INDEX idx_spaces_tenant ON spaces(tenant_id)")
        print("  Created spaces table")

    # Create decision_spaces table
    if 'decision_spaces' in tables_to_create:
        cur.execute("""
            CREATE TABLE decision_spaces (
                id SERIAL PRIMARY KEY,
                decision_id INTEGER NOT NULL REFERENCES architecture_decisions(id),
                space_id INTEGER NOT NULL REFERENCES spaces(id),
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                added_by_id INTEGER REFERENCES users(id),
                CONSTRAINT unique_decision_space UNIQUE (decision_id, space_id)
            )
        """)
        print("  Created decision_spaces table")

    # Create audit_logs table
    if 'audit_logs' in tables_to_create:
        cur.execute("""
            CREATE TABLE audit_logs (
                id SERIAL PRIMARY KEY,
                tenant_id INTEGER NOT NULL REFERENCES tenants(id),
                actor_user_id INTEGER NOT NULL REFERENCES users(id),
                action_type VARCHAR(50) NOT NULL,
                target_entity VARCHAR(50),
                target_id INTEGER,
                details JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("CREATE INDEX idx_audit_logs_tenant ON audit_logs(tenant_id)")
        cur.execute("CREATE INDEX idx_audit_logs_created ON audit_logs(created_at)")
        print("  Created audit_logs table")

    # Add tenant_id column to architecture_decisions if needed
    if not column_exists(cur, 'architecture_decisions', 'tenant_id'):
        cur.execute("""
            ALTER TABLE architecture_decisions
            ADD COLUMN tenant_id INTEGER REFERENCES tenants(id)
        """)
        cur.execute("CREATE INDEX idx_decisions_tenant ON architecture_decisions(tenant_id)")
        print("  Added tenant_id column to architecture_decisions")


def migrate_domains_to_tenants(cur, dry_run=False, verbose=False):
    """Create Tenant records for each unique domain."""
    if verbose:
        print("\nStep 2: Migrating domains to tenants...")

    # Get unique domains from users
    cur.execute("SELECT DISTINCT sso_domain FROM users WHERE sso_domain IS NOT NULL")
    user_domains = [row[0] for row in cur.fetchall()]

    # Get domains from auth_configs
    cur.execute("SELECT DISTINCT domain FROM auth_configs WHERE domain IS NOT NULL")
    auth_config_domains = [row[0] for row in cur.fetchall()]

    # Get domains from decisions
    cur.execute("SELECT DISTINCT domain FROM architecture_decisions WHERE domain IS NOT NULL")
    decision_domains = [row[0] for row in cur.fetchall()]

    # Combine all unique domains
    all_domains = set(user_domains + auth_config_domains + decision_domains)

    if verbose:
        print(f"  Found {len(all_domains)} unique domains: {', '.join(all_domains)}")

    created_tenants = {}
    for domain in all_domains:
        # Check if tenant already exists
        cur.execute("SELECT id FROM tenants WHERE domain = %s", (domain,))
        existing = cur.fetchone()

        if existing:
            if verbose:
                print(f"  Tenant for '{domain}' already exists (id={existing[0]})")
            created_tenants[domain] = existing[0]
            continue

        if dry_run:
            print(f"  [DRY-RUN] Would create tenant for domain: {domain}")
            created_tenants[domain] = None
            continue

        # Create tenant
        name = domain.split('.')[0].title() + ' Organization'
        cur.execute("""
            INSERT INTO tenants (domain, name, status, maturity_state)
            VALUES (%s, %s, 'active', 'BOOTSTRAP')
            RETURNING id
        """, (domain, name))
        tenant_id = cur.fetchone()[0]
        created_tenants[domain] = tenant_id
        print(f"  Created tenant for '{domain}' (id={tenant_id})")

    return created_tenants


def migrate_auth_configs_to_tenant_settings(cur, created_tenants, dry_run=False, verbose=False):
    """Copy settings from AuthConfig to TenantSettings."""
    if verbose:
        print("\nStep 3: Migrating auth configs to tenant settings...")

    cur.execute("SELECT * FROM auth_configs")
    columns = [desc[0] for desc in cur.description]
    auth_configs = [dict(zip(columns, row)) for row in cur.fetchall()]

    for config in auth_configs:
        tenant_id = created_tenants.get(config['domain'])
        if not tenant_id:
            # Try to find tenant by domain
            cur.execute("SELECT id FROM tenants WHERE domain = %s", (config['domain'],))
            result = cur.fetchone()
            tenant_id = result[0] if result else None

        if not tenant_id:
            print(f"  WARNING: No tenant found for auth config domain '{config['domain']}'")
            continue

        # Check if settings already exist
        cur.execute("SELECT id FROM tenant_settings WHERE tenant_id = %s", (tenant_id,))
        if cur.fetchone():
            if verbose:
                print(f"  Settings for tenant '{config['domain']}' already exist")
            continue

        if dry_run:
            print(f"  [DRY-RUN] Would create settings for tenant '{config['domain']}'")
            continue

        cur.execute("""
            INSERT INTO tenant_settings
            (tenant_id, auth_method, allow_password, allow_passkey, allow_registration,
             require_approval, rp_name, tenant_prefix)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            tenant_id,
            config.get('auth_method', 'local'),
            config.get('allow_password', True),
            config.get('allow_passkey', True),
            config.get('allow_registration', True),
            config.get('require_approval', False),
            config.get('rp_name', 'Architecture Decisions'),
            config.get('tenant_prefix')
        ))
        print(f"  Created settings for tenant '{config['domain']}'")


def create_default_spaces(cur, created_tenants, dry_run=False, verbose=False):
    """Create default space for each tenant."""
    if verbose:
        print("\nStep 4: Creating default spaces...")

    for domain, tenant_id in created_tenants.items():
        if tenant_id is None:
            continue

        # Check if default space already exists
        cur.execute("SELECT id FROM spaces WHERE tenant_id = %s AND is_default = TRUE", (tenant_id,))
        if cur.fetchone():
            if verbose:
                print(f"  Default space for tenant '{domain}' already exists")
            continue

        if dry_run:
            print(f"  [DRY-RUN] Would create default space for tenant '{domain}'")
            continue

        cur.execute("""
            INSERT INTO spaces (tenant_id, name, description, is_default, visibility_policy)
            VALUES (%s, 'General', 'Default space for all architecture decisions', TRUE, 'TENANT_VISIBLE')
        """, (tenant_id,))
        print(f"  Created default space for tenant '{domain}'")


def create_tenant_memberships(cur, created_tenants, dry_run=False, verbose=False):
    """Create TenantMembership records for all users."""
    if verbose:
        print("\nStep 5: Creating tenant memberships...")

    cur.execute("SELECT id, email, sso_domain, is_admin FROM users")
    users = cur.fetchall()
    memberships_created = 0

    for user_id, email, sso_domain, is_admin in users:
        tenant_id = created_tenants.get(sso_domain)
        if not tenant_id:
            # Try to find tenant by domain
            cur.execute("SELECT id FROM tenants WHERE domain = %s", (sso_domain,))
            result = cur.fetchone()
            tenant_id = result[0] if result else None

        if not tenant_id:
            print(f"  WARNING: No tenant found for user '{email}' with domain '{sso_domain}'")
            continue

        # Check if membership already exists
        cur.execute("""
            SELECT id FROM tenant_memberships
            WHERE user_id = %s AND tenant_id = %s
        """, (user_id, tenant_id))
        if cur.fetchone():
            if verbose:
                print(f"  Membership for '{email}' already exists")
            continue

        # Determine role based on is_admin flag
        if is_admin:
            # Check if this tenant already has an admin
            cur.execute("""
                SELECT COUNT(*) FROM tenant_memberships
                WHERE tenant_id = %s AND global_role IN ('ADMIN', 'PROVISIONAL_ADMIN')
            """, (tenant_id,))
            existing_admins = cur.fetchone()[0]

            if existing_admins == 0:
                # First admin - make them provisional admin (tenant starts in bootstrap)
                role = 'PROVISIONAL_ADMIN'
            else:
                # Already has admin(s) - make this one full admin
                role = 'ADMIN'
        else:
            role = 'USER'

        if dry_run:
            print(f"  [DRY-RUN] Would create membership for '{email}' with role {role}")
            continue

        cur.execute("""
            INSERT INTO tenant_memberships (user_id, tenant_id, global_role)
            VALUES (%s, %s, %s)
        """, (user_id, tenant_id, role))
        memberships_created += 1

        if verbose or role != 'USER':
            print(f"  Created membership for '{email}' with role {role}")

    if not dry_run:
        print(f"  Total memberships created: {memberships_created}")


def link_decisions_to_tenants(cur, created_tenants, dry_run=False, verbose=False):
    """Update decisions with tenant_id based on their domain."""
    if verbose:
        print("\nStep 6: Linking decisions to tenants...")

    # Check if tenant_id column exists (may not in dry-run before migration)
    if not column_exists(cur, 'architecture_decisions', 'tenant_id'):
        if dry_run:
            print("  [DRY-RUN] Would link all decisions to their tenants (column doesn't exist yet)")
            return
        else:
            print("  ERROR: tenant_id column doesn't exist!")
            return

    cur.execute("SELECT id, domain FROM architecture_decisions WHERE tenant_id IS NULL")
    decisions = cur.fetchall()

    if not decisions:
        print("  All decisions already have tenant_id set")
        return

    linked = 0
    for decision_id, domain in decisions:
        tenant_id = created_tenants.get(domain)
        if not tenant_id:
            # Try to find tenant by domain
            cur.execute("SELECT id FROM tenants WHERE domain = %s", (domain,))
            result = cur.fetchone()
            tenant_id = result[0] if result else None

        if not tenant_id:
            print(f"  WARNING: No tenant for decision id={decision_id} with domain '{domain}'")
            continue

        if dry_run:
            print(f"  [DRY-RUN] Would link decision id={decision_id} to tenant '{domain}'")
            continue

        cur.execute("""
            UPDATE architecture_decisions SET tenant_id = %s WHERE id = %s
        """, (tenant_id, decision_id))
        linked += 1

    if not dry_run:
        print(f"  Linked {linked} decisions to tenants")


def update_tenant_maturity(cur, created_tenants, dry_run=False, verbose=False):
    """Update tenant maturity states based on current conditions."""
    if verbose:
        print("\nStep 7: Updating tenant maturity states...")

    for domain, tenant_id in created_tenants.items():
        if tenant_id is None:
            continue

        # Get tenant info
        cur.execute("""
            SELECT maturity_state, maturity_age_days, maturity_user_threshold, created_at
            FROM tenants WHERE id = %s
        """, (tenant_id,))
        tenant = cur.fetchone()
        if not tenant:
            continue

        old_state, age_days, user_threshold, created_at = tenant

        # Handle None values with defaults
        age_days = age_days or 14
        user_threshold = user_threshold or 5

        # Count admins
        cur.execute("""
            SELECT COUNT(*) FROM tenant_memberships
            WHERE tenant_id = %s AND global_role = 'ADMIN'
        """, (tenant_id,))
        admin_count = cur.fetchone()[0]

        # Count stewards
        cur.execute("""
            SELECT COUNT(*) FROM tenant_memberships
            WHERE tenant_id = %s AND global_role = 'STEWARD'
        """, (tenant_id,))
        steward_count = cur.fetchone()[0]

        # Count total members
        cur.execute("""
            SELECT COUNT(*) FROM tenant_memberships WHERE tenant_id = %s
        """, (tenant_id,))
        member_count = cur.fetchone()[0]

        # Calculate age
        days_old = (datetime.utcnow() - created_at).days if created_at else 0

        # Determine if should be mature
        has_multi_admin = admin_count >= 2 or (admin_count >= 1 and steward_count >= 1)
        has_enough_users = member_count >= user_threshold
        is_old_enough = days_old >= age_days

        new_state = 'MATURE' if (has_multi_admin or has_enough_users or is_old_enough) else 'BOOTSTRAP'

        if new_state != old_state:
            if dry_run:
                print(f"  [DRY-RUN] Would update tenant '{domain}' maturity: {old_state} -> {new_state}")
            else:
                cur.execute("UPDATE tenants SET maturity_state = %s WHERE id = %s", (new_state, tenant_id))
                print(f"  Updated tenant '{domain}' maturity: {old_state} -> {new_state}")

                # Upgrade provisional admins to full admins if tenant is now mature
                if new_state == 'MATURE':
                    cur.execute("""
                        UPDATE tenant_memberships
                        SET global_role = 'ADMIN'
                        WHERE tenant_id = %s AND global_role = 'PROVISIONAL_ADMIN'
                        RETURNING user_id
                    """, (tenant_id,))
                    upgraded = cur.fetchall()
                    for (uid,) in upgraded:
                        print(f"    Upgraded user id={uid} from provisional to full admin")


def print_migration_summary(cur, dry_run=False):
    """Print summary of the migration."""
    print("\n" + "=" * 60)
    print("Migration Summary")
    print("=" * 60)

    if dry_run:
        print("DRY-RUN: No changes were made")
        return

    cur.execute("SELECT COUNT(*) FROM tenants")
    tenant_count = cur.fetchone()[0]
    print(f"Tenants: {tenant_count}")

    cur.execute("SELECT COUNT(*) FROM tenant_memberships")
    membership_count = cur.fetchone()[0]
    print(f"Tenant Memberships: {membership_count}")

    cur.execute("SELECT COUNT(*) FROM tenant_settings")
    settings_count = cur.fetchone()[0]
    print(f"Tenant Settings: {settings_count}")

    cur.execute("SELECT COUNT(*) FROM spaces")
    space_count = cur.fetchone()[0]
    print(f"Spaces: {space_count}")

    print("\nTenant Details:")
    cur.execute("SELECT id, domain, maturity_state FROM tenants")
    for tenant_id, domain, maturity_state in cur.fetchall():
        cur.execute("""
            SELECT COUNT(*) FROM tenant_memberships WHERE tenant_id = %s AND global_role = 'ADMIN'
        """, (tenant_id,))
        admin_count = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) FROM tenant_memberships WHERE tenant_id = %s AND global_role = 'STEWARD'
        """, (tenant_id,))
        steward_count = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) FROM tenant_memberships WHERE tenant_id = %s
        """, (tenant_id,))
        member_count = cur.fetchone()[0]

        print(f"  {domain}:")
        print(f"    - Maturity: {maturity_state}")
        print(f"    - Members: {member_count} (Admins: {admin_count}, Stewards: {steward_count})")

    # Check for any decisions without tenant_id
    cur.execute("SELECT COUNT(*) FROM architecture_decisions WHERE tenant_id IS NULL")
    orphan_decisions = cur.fetchone()[0]
    if orphan_decisions:
        print(f"\nWARNING: {orphan_decisions} decisions without tenant_id")


def main():
    parser = argparse.ArgumentParser(description='Migrate database to v1.5 governance model')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--verbose', '-v', action='store_true', help='Print detailed progress')
    args = parser.parse_args()

    print("=" * 60)
    print("v1.5 Governance Model Migration")
    print("=" * 60)

    if args.dry_run:
        print("DRY-RUN MODE: No changes will be made\n")

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Step 1: Create new tables
        create_new_tables(cur, dry_run=args.dry_run, verbose=args.verbose)

        # Step 2: Create tenants from domains
        created_tenants = migrate_domains_to_tenants(cur, dry_run=args.dry_run, verbose=args.verbose)

        # In dry-run mode with existing tables, load actual tenant IDs for subsequent steps
        if args.dry_run and table_exists(cur, 'tenants'):
            cur.execute("SELECT domain, id FROM tenants")
            for domain, tenant_id in cur.fetchall():
                created_tenants[domain] = tenant_id

        # Step 3: Migrate auth configs to tenant settings
        migrate_auth_configs_to_tenant_settings(cur, created_tenants, dry_run=args.dry_run, verbose=args.verbose)

        # Step 4: Create default spaces
        create_default_spaces(cur, created_tenants, dry_run=args.dry_run, verbose=args.verbose)

        # Step 5: Create tenant memberships
        create_tenant_memberships(cur, created_tenants, dry_run=args.dry_run, verbose=args.verbose)

        # Step 6: Link decisions to tenants
        link_decisions_to_tenants(cur, created_tenants, dry_run=args.dry_run, verbose=args.verbose)

        # Step 7: Update maturity states
        update_tenant_maturity(cur, created_tenants, dry_run=args.dry_run, verbose=args.verbose)

        # Commit if not dry run
        if not args.dry_run:
            conn.commit()

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
