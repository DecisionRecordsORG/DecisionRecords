#!/usr/bin/env python3
"""
Cleanup script for test user data.

Usage:
    python scripts/cleanup_test_user.py <email>
    python scripts/cleanup_test_user.py test@rulemesh.com
    python scripts/cleanup_test_user.py --domain rulemesh.com  # Clean all test users for a domain (excludes admins)
"""

import argparse
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():
    """Get database connection from environment."""
    database_url = os.environ.get('DATABASE_URL')

    if database_url:
        # Parse the DATABASE_URL
        # Format: postgresql://user:password@host:port/database?sslmode=require
        import re
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


def cleanup_user_by_email(email: str, dry_run: bool = False) -> dict:
    """
    Clean up all data for a specific user email.

    Returns dict with counts of deleted records.
    """
    conn = get_db_connection()
    cur = conn.cursor()

    results = {
        'email': email,
        'user_found': False,
        'setup_tokens_deleted': 0,
        'webauthn_credentials_deleted': 0,
        'access_requests_deleted': 0,
        'user_deleted': 0,
    }

    try:
        # Find the user
        cur.execute("SELECT id, name, sso_domain, is_admin FROM users WHERE email = %s", (email.lower(),))
        user = cur.fetchone()

        if user:
            user_id, name, domain, is_admin = user
            results['user_found'] = True
            results['user_name'] = name
            results['user_domain'] = domain
            results['is_admin'] = is_admin

            if is_admin:
                print(f"WARNING: {email} is an admin user!")
                confirm = input("Are you sure you want to delete this admin? (yes/no): ")
                if confirm.lower() != 'yes':
                    print("Aborted.")
                    return results

            if dry_run:
                # Count what would be deleted
                cur.execute("SELECT COUNT(*) FROM setup_tokens WHERE user_id = %s", (user_id,))
                results['setup_tokens_deleted'] = cur.fetchone()[0]

                cur.execute("SELECT COUNT(*) FROM webauthn_credentials WHERE user_id = %s", (user_id,))
                results['webauthn_credentials_deleted'] = cur.fetchone()[0]

                results['user_deleted'] = 1
            else:
                # Delete setup tokens
                cur.execute("DELETE FROM setup_tokens WHERE user_id = %s", (user_id,))
                results['setup_tokens_deleted'] = cur.rowcount

                # Delete webauthn credentials
                cur.execute("DELETE FROM webauthn_credentials WHERE user_id = %s", (user_id,))
                results['webauthn_credentials_deleted'] = cur.rowcount

                # Delete the user
                cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
                results['user_deleted'] = cur.rowcount

        # Also clean up any access requests for this email
        if dry_run:
            cur.execute("SELECT COUNT(*) FROM access_requests WHERE email = %s", (email.lower(),))
            results['access_requests_deleted'] = cur.fetchone()[0]
        else:
            cur.execute("DELETE FROM access_requests WHERE email = %s", (email.lower(),))
            results['access_requests_deleted'] = cur.rowcount

        if not dry_run:
            conn.commit()

    finally:
        cur.close()
        conn.close()

    return results


def cleanup_domain(domain: str, dry_run: bool = False, include_admins: bool = False) -> dict:
    """
    Clean up all non-admin test users for a domain.

    Returns dict with counts of deleted records.
    """
    conn = get_db_connection()
    cur = conn.cursor()

    results = {
        'domain': domain,
        'users_found': 0,
        'users_deleted': 0,
        'setup_tokens_deleted': 0,
        'webauthn_credentials_deleted': 0,
        'access_requests_deleted': 0,
        'skipped_admins': [],
    }

    try:
        # Find users for this domain
        if include_admins:
            cur.execute("SELECT id, email, name, is_admin FROM users WHERE sso_domain = %s", (domain,))
        else:
            cur.execute("SELECT id, email, name, is_admin FROM users WHERE sso_domain = %s AND is_admin = FALSE", (domain,))

        users = cur.fetchall()
        results['users_found'] = len(users)

        # Also check for admins that would be skipped
        if not include_admins:
            cur.execute("SELECT email FROM users WHERE sso_domain = %s AND is_admin = TRUE", (domain,))
            results['skipped_admins'] = [row[0] for row in cur.fetchall()]

        if users:
            user_ids = [u[0] for u in users]

            if dry_run:
                # Count what would be deleted
                cur.execute("SELECT COUNT(*) FROM setup_tokens WHERE user_id = ANY(%s)", (user_ids,))
                results['setup_tokens_deleted'] = cur.fetchone()[0]

                cur.execute("SELECT COUNT(*) FROM webauthn_credentials WHERE user_id = ANY(%s)", (user_ids,))
                results['webauthn_credentials_deleted'] = cur.fetchone()[0]

                results['users_deleted'] = len(users)
            else:
                # Delete setup tokens
                cur.execute("DELETE FROM setup_tokens WHERE user_id = ANY(%s)", (user_ids,))
                results['setup_tokens_deleted'] = cur.rowcount

                # Delete webauthn credentials
                cur.execute("DELETE FROM webauthn_credentials WHERE user_id = ANY(%s)", (user_ids,))
                results['webauthn_credentials_deleted'] = cur.rowcount

                # Delete users
                cur.execute("DELETE FROM users WHERE id = ANY(%s)", (user_ids,))
                results['users_deleted'] = cur.rowcount

        # Clean up access requests for this domain
        if dry_run:
            cur.execute("SELECT COUNT(*) FROM access_requests WHERE domain = %s", (domain,))
            results['access_requests_deleted'] = cur.fetchone()[0]
        else:
            cur.execute("DELETE FROM access_requests WHERE domain = %s", (domain,))
            results['access_requests_deleted'] = cur.rowcount

        if not dry_run:
            conn.commit()

    finally:
        cur.close()
        conn.close()

    return results


def main():
    parser = argparse.ArgumentParser(
        description='Clean up test user data from the database.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Delete a specific user by email
    python scripts/cleanup_test_user.py test@rulemesh.com

    # Preview what would be deleted (dry run)
    python scripts/cleanup_test_user.py test@rulemesh.com --dry-run

    # Delete all non-admin users for a domain
    python scripts/cleanup_test_user.py --domain rulemesh.com

    # Delete all users for a domain (including admins - dangerous!)
    python scripts/cleanup_test_user.py --domain rulemesh.com --include-admins
        """
    )

    parser.add_argument('email', nargs='?', help='Email address of the user to clean up')
    parser.add_argument('--domain', '-d', help='Clean all non-admin users for this domain')
    parser.add_argument('--dry-run', '-n', action='store_true', help='Show what would be deleted without actually deleting')
    parser.add_argument('--include-admins', action='store_true', help='Include admin users when cleaning by domain (dangerous!)')

    args = parser.parse_args()

    if not args.email and not args.domain:
        parser.error('Either email or --domain is required')

    if args.email and args.domain:
        parser.error('Cannot specify both email and --domain')

    try:
        if args.domain:
            if args.include_admins:
                print(f"WARNING: This will delete ALL users for domain {args.domain}, including admins!")
                confirm = input("Are you sure? Type 'yes' to confirm: ")
                if confirm.lower() != 'yes':
                    print("Aborted.")
                    return

            results = cleanup_domain(args.domain, dry_run=args.dry_run, include_admins=args.include_admins)

            action = "Would delete" if args.dry_run else "Deleted"
            print(f"\n{'DRY RUN - ' if args.dry_run else ''}Cleanup results for domain: {results['domain']}")
            print(f"  Users found: {results['users_found']}")
            print(f"  {action} {results['users_deleted']} users")
            print(f"  {action} {results['setup_tokens_deleted']} setup tokens")
            print(f"  {action} {results['webauthn_credentials_deleted']} webauthn credentials")
            print(f"  {action} {results['access_requests_deleted']} access requests")

            if results['skipped_admins']:
                print(f"\n  Skipped admin users: {', '.join(results['skipped_admins'])}")
        else:
            results = cleanup_user_by_email(args.email, dry_run=args.dry_run)

            action = "Would delete" if args.dry_run else "Deleted"
            print(f"\n{'DRY RUN - ' if args.dry_run else ''}Cleanup results for: {results['email']}")

            if results['user_found']:
                print(f"  User: {results.get('user_name', 'N/A')} ({results.get('user_domain', 'N/A')})")
                print(f"  Is Admin: {results.get('is_admin', False)}")
                print(f"  {action} {results['setup_tokens_deleted']} setup tokens")
                print(f"  {action} {results['webauthn_credentials_deleted']} webauthn credentials")
                print(f"  {action} {results['user_deleted']} user record")
            else:
                print("  User not found in database")

            print(f"  {action} {results['access_requests_deleted']} access requests")

        if args.dry_run:
            print("\nRun without --dry-run to actually delete.")
        else:
            print("\nCleanup complete!")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
