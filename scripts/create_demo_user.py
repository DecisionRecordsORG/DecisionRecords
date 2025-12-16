#!/usr/bin/env python3
"""
Create a demo user for a tenant with password login.

Usage:
    python scripts/create_demo_user.py brandnewcorp.com
"""

import argparse
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from app import app, db
from models import User, AuthConfig
from werkzeug.security import generate_password_hash


def create_demo_user(domain: str, email: str = None, password: str = 'demo123!'):
    """Create a demo user for the given domain."""

    if email is None:
        email = f'demo@{domain}'

    name = 'Demo User'

    with app.app_context():
        # Check if user exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            print(f"User {email} already exists. Updating password...")
            existing_user.password_hash = generate_password_hash(password)
            db.session.commit()
            print(f"Password updated for {email}")
        else:
            # Create new user
            user = User(
                email=email,
                name=name,
                sso_domain=domain,
                is_admin=True,
                auth_type='local',
                email_verified=True,
                password_hash=generate_password_hash(password)
            )
            db.session.add(user)
            db.session.commit()
            print(f"Created user: {email}")

        # Ensure AuthConfig allows password login
        auth_config = AuthConfig.query.filter_by(domain=domain).first()
        if not auth_config:
            auth_config = AuthConfig(
                domain=domain,
                allow_password=True,
                require_email_verification=False,
                require_approval=False,
                tenant_prefix='BNC'
            )
            db.session.add(auth_config)
            db.session.commit()
            print(f"Created AuthConfig for {domain} with password login enabled")
        else:
            if not auth_config.allow_password:
                auth_config.allow_password = True
                db.session.commit()
                print(f"Enabled password login for {domain}")
            else:
                print(f"AuthConfig already exists for {domain}, password login is enabled")

        print(f"\n--- Login Credentials ---")
        print(f"Email: {email}")
        print(f"Password: {password}")
        print(f"Login URL: https://decisionrecords.org/{domain}/login")
        print(f"Or locally: http://localhost:4200/{domain}/login")


def main():
    parser = argparse.ArgumentParser(description='Create a demo user for a tenant.')
    parser.add_argument('domain', help='Domain for the tenant (e.g., brandnewcorp.com)')
    parser.add_argument('--email', '-e', help='Email for the user (default: demo@<domain>)')
    parser.add_argument('--password', '-p', default='demo123!', help='Password for the user (default: demo123!)')

    args = parser.parse_args()
    create_demo_user(args.domain, args.email, args.password)


if __name__ == '__main__':
    main()
