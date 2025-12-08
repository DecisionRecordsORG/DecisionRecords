"""WebAuthn authentication helpers for passwordless login."""

import base64
import json
from datetime import datetime
from flask import session, request
from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
    options_to_json,
)
from webauthn.helpers import bytes_to_base64url, base64url_to_bytes
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    UserVerificationRequirement,
    ResidentKeyRequirement,
    PublicKeyCredentialDescriptor,
    AuthenticatorTransport,
)

from models import db, User, WebAuthnCredential, AuthConfig


def get_rp_id():
    """Get the Relying Party ID from the request host."""
    host = request.host.split(':')[0]  # Remove port if present
    return host


def get_rp_origin():
    """Get the origin for WebAuthn verification.

    For local development with Angular proxy, we need to use the frontend origin.
    The frontend sends the 'Origin' header which we should use when available.
    """
    # Check for forwarded origin (from proxy) or use Origin header
    origin = request.headers.get('Origin')
    if origin:
        return origin

    # Fallback to constructing from request
    scheme = 'https' if request.is_secure else 'http'
    return f"{scheme}://{request.host}"


def get_auth_config(domain):
    """Get authentication configuration for a domain."""
    return AuthConfig.query.filter_by(domain=domain).first()


def create_registration_options(user_email, user_name, domain):
    """Generate WebAuthn registration options for a new user or new credential."""
    rp_id = get_rp_id()

    # Get RP name from auth config or use default
    auth_config = get_auth_config(domain)
    rp_name = auth_config.rp_name if auth_config else 'Architecture Decisions'

    # Check if user already exists
    existing_user = User.query.filter_by(email=user_email).first()

    # Get existing credentials to exclude
    exclude_credentials = []
    if existing_user:
        for cred in existing_user.webauthn_credentials:
            exclude_credentials.append(
                PublicKeyCredentialDescriptor(
                    id=cred.credential_id,
                    transports=[AuthenticatorTransport.HYBRID, AuthenticatorTransport.INTERNAL]
                )
            )

    # Generate user ID (use existing or create new)
    if existing_user:
        user_id = str(existing_user.id).encode('utf-8')
    else:
        # Use email as temporary user ID for new users
        user_id = user_email.encode('utf-8')

    options = generate_registration_options(
        rp_id=rp_id,
        rp_name=rp_name,
        user_id=user_id,
        user_name=user_email,
        user_display_name=user_name or user_email,
        exclude_credentials=exclude_credentials if exclude_credentials else None,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )

    # Store challenge in session
    session['webauthn_register_challenge'] = bytes_to_base64url(options.challenge)
    session['webauthn_register_email'] = user_email
    session['webauthn_register_name'] = user_name
    session['webauthn_register_domain'] = domain

    return options_to_json(options)


def verify_registration(credential_json, device_name=None):
    """Verify WebAuthn registration response and create/update user."""
    challenge_b64 = session.pop('webauthn_register_challenge', None)
    email = session.pop('webauthn_register_email', None)
    name = session.pop('webauthn_register_name', None)
    domain = session.pop('webauthn_register_domain', None)

    if not challenge_b64 or not email or not domain:
        return None, 'Registration session expired'

    try:
        challenge = base64url_to_bytes(challenge_b64)

        verification = verify_registration_response(
            credential=credential_json,
            expected_challenge=challenge,
            expected_rp_id=get_rp_id(),
            expected_origin=get_rp_origin(),
        )

        # Get or create user
        user = User.query.filter_by(email=email).first()
        if not user:
            # Check if registration is allowed
            auth_config = get_auth_config(domain)
            if auth_config and not auth_config.allow_registration:
                return None, 'Registration is not allowed for this domain'

            # Check if this is the first user for the domain (make them admin)
            is_first_user = User.query.filter_by(sso_domain=domain).count() == 0

            user = User(
                email=email,
                name=name,
                sso_domain=domain,
                auth_type='webauthn',
                is_admin=is_first_user,
            )
            db.session.add(user)
            db.session.flush()  # Get the user ID

        # Store the credential
        credential = WebAuthnCredential(
            user_id=user.id,
            credential_id=verification.credential_id,
            public_key=verification.credential_public_key,
            sign_count=verification.sign_count,
            device_name=device_name,
            transports=json.dumps(['internal', 'hybrid']),  # Default transports
        )
        db.session.add(credential)

        user.last_login = datetime.utcnow()
        db.session.commit()

        return user, None

    except Exception as e:
        db.session.rollback()
        return None, str(e)


def create_authentication_options(email=None):
    """Generate WebAuthn authentication options."""
    rp_id = get_rp_id()

    allow_credentials = []

    if email:
        # Specific user authentication
        user = User.query.filter_by(email=email, auth_type='webauthn').first()
        if user and user.webauthn_credentials:
            for cred in user.webauthn_credentials:
                transports = json.loads(cred.transports) if cred.transports else ['internal', 'hybrid']
                allow_credentials.append(
                    PublicKeyCredentialDescriptor(
                        id=cred.credential_id,
                        transports=[AuthenticatorTransport(t) for t in transports if t in ['usb', 'ble', 'nfc', 'internal', 'hybrid']]
                    )
                )
        session['webauthn_auth_email'] = email
    else:
        # Discoverable credential authentication (passkey)
        session.pop('webauthn_auth_email', None)

    options = generate_authentication_options(
        rp_id=rp_id,
        allow_credentials=allow_credentials if allow_credentials else None,
        user_verification=UserVerificationRequirement.PREFERRED,
    )

    # Store challenge in session
    session['webauthn_auth_challenge'] = bytes_to_base64url(options.challenge)

    return options_to_json(options)


def verify_authentication(credential_json):
    """Verify WebAuthn authentication response and log in user."""
    challenge_b64 = session.pop('webauthn_auth_challenge', None)
    expected_email = session.pop('webauthn_auth_email', None)

    if not challenge_b64:
        return None, 'Authentication session expired'

    try:
        challenge = base64url_to_bytes(challenge_b64)

        # Parse the credential to get the credential ID
        if isinstance(credential_json, str):
            cred_data = json.loads(credential_json)
        else:
            cred_data = credential_json

        # Decode credential ID from base64url
        raw_id = cred_data.get('rawId') or cred_data.get('id')
        if not raw_id:
            return None, 'Missing credential ID'

        # Add padding if needed for base64url decoding
        padding = 4 - len(raw_id) % 4
        if padding != 4:
            raw_id += '=' * padding

        credential_id = base64url_to_bytes(raw_id.replace('=', ''))

        # Find the credential in database
        db_credential = WebAuthnCredential.query.filter_by(credential_id=credential_id).first()
        if not db_credential:
            return None, 'Credential not found'

        user = db_credential.user

        # If email was specified, verify it matches
        if expected_email and user.email != expected_email:
            return None, 'Credential does not match expected user'

        verification = verify_authentication_response(
            credential=credential_json,
            expected_challenge=challenge,
            expected_rp_id=get_rp_id(),
            expected_origin=get_rp_origin(),
            credential_public_key=db_credential.public_key,
            credential_current_sign_count=db_credential.sign_count,
        )

        # Update sign count
        db_credential.sign_count = verification.new_sign_count
        db_credential.last_used_at = datetime.utcnow()
        user.last_login = datetime.utcnow()
        db.session.commit()

        return user, None

    except Exception as e:
        db.session.rollback()
        return None, str(e)


def get_user_credentials(user_id):
    """Get all WebAuthn credentials for a user."""
    credentials = WebAuthnCredential.query.filter_by(user_id=user_id).all()
    return [c.to_dict() for c in credentials]


def delete_credential(user_id, credential_id):
    """Delete a WebAuthn credential."""
    # Decode credential ID
    padding = 4 - len(credential_id) % 4
    if padding != 4:
        credential_id += '=' * padding

    cred_id_bytes = base64url_to_bytes(credential_id.replace('=', ''))

    credential = WebAuthnCredential.query.filter_by(
        user_id=user_id,
        credential_id=cred_id_bytes
    ).first()

    if not credential:
        return False, 'Credential not found'

    # Check if this is the user's only credential
    user = User.query.get(user_id)
    if user and len(user.webauthn_credentials) <= 1:
        return False, 'Cannot delete the only credential'

    db.session.delete(credential)
    db.session.commit()
    return True, None
