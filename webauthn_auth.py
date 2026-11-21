"""WebAuthn authentication helpers for passwordless login."""

import base64
import json
from datetime import datetime, timezone
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

from sqlalchemy import func

from models import (
    db, User, WebAuthnCredential, AuthConfig, SSOConfig, SystemConfig, Tenant,
    DomainApproval
)

# Returned whenever a registration cannot be tied to a proven identity.
REGISTRATION_REFUSED = 'Registration could not be completed. Please sign in and try again.'
_UNSET = object()


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


def domain_requires_sso(domain):
    """Return True when a tenant enforces its own SSO provider for sign-in.

    A tenant enforces SSO when it has an enabled SSO configuration and has not
    chosen another primary method in its auth config. This is a property of the
    tenant, not of User.auth_type: a user may also have signed in with a social
    provider (which records auth_type 'sso' for accounts with no local
    credential) without the tenant requiring SSO.
    """
    if not domain:
        return False

    sso_config = SSOConfig.query.filter_by(domain=domain, enabled=True).first()
    if not sso_config:
        return False

    auth_config = get_auth_config(domain)
    return not auth_config or auth_config.auth_method == 'sso'


def find_user_by_email(email):
    """Look a user up by email address, ignoring case and surrounding whitespace."""
    if not email or not isinstance(email, str):
        return None
    return User.query.filter(func.lower(User.email) == email.strip().lower()).first()


def new_account_registration_refusal(email, domain):
    """Why a caller with no proven identity may not register a passkey for `email`.

    Returns (message, status) or None when registration may go ahead.

    A caller who has not proven control of an account (no signed-in session,
    no setup or recovery token) can only create the first account of an
    organisation that has none, and only when the instance does not require
    email verification. These are the conditions direct sign-up applies.
    Existing accounts are reached through sign-in, a setup link or a recovery
    link; existing organisations through their access-request and invite flows.
    """
    if not email or not domain:
        return 'Invalid email format', 400

    if domain_requires_sso(domain):
        return 'This domain requires SSO authentication', 400

    if find_user_by_email(email):
        return 'An account with this email already exists. Please sign in to add a passkey.', 400

    if SystemConfig.get_bool(SystemConfig.KEY_EMAIL_VERIFICATION_REQUIRED, default=True):
        return 'Email verification is required. Please sign up with your email address first.', 403

    if DomainApproval.is_public_domain(domain):
        return f'{domain} is a public email provider. Please use your work email address.', 400

    if DomainApproval.is_disposable_domain(domain):
        return 'Disposable email addresses are not allowed. Please use your work email address.', 400

    domain_approval = DomainApproval.query.filter_by(domain=domain).first()
    if domain_approval and domain_approval.status == 'rejected':
        return 'Your organization domain has been rejected.', 403

    has_tenant = Tenant.query.filter(func.lower(Tenant.domain) == domain).first() is not None
    has_users = User.query.filter(func.lower(User.sso_domain) == domain).count() > 0
    if has_tenant or has_users:
        return 'This organization already has users. Please use the login page.', 400

    auth_config = get_auth_config(domain)
    if auth_config and not auth_config.allow_registration:
        return 'Registration is not allowed for this domain', 400

    return None


def create_registration_options(user_email, user_name, domain, existing_user=None):
    """Generate WebAuthn registration options.

    `existing_user` is the account the passkey will be added to. The caller
    must already have proven control of it (signed-in session or setup token):
    it is never looked up from an email address here. Leave it as None only to
    register the first passkey of an account that does not exist yet.

    The challenge is bound to that identity in the session, and
    verify_registration() checks the binding again.
    """
    rp_id = get_rp_id()

    # Get RP name from auth config or use default
    auth_config = get_auth_config(domain)
    rp_name = auth_config.rp_name if auth_config else 'Decision Records'

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
    session['webauthn_register_user_id'] = existing_user.id if existing_user else None

    return options_to_json(options)


def verify_registration(credential_json, device_name=None, proven_user_ids=()):
    """Verify a WebAuthn registration response and store the credential.

    `proven_user_ids` are the accounts the current request has proven control
    of (signed-in session, setup or recovery token). The credential is stored
    on an existing account only if the challenge was issued for that account
    and it is still among them. Otherwise the registration may only create a
    new account, subject to new_account_registration_refusal(). This check
    does not rely on the options step having been enforced.
    """
    challenge_b64 = session.pop('webauthn_register_challenge', None)
    email = session.pop('webauthn_register_email', None)
    name = session.pop('webauthn_register_name', None)
    domain = session.pop('webauthn_register_domain', None)
    bound_user_id = session.pop('webauthn_register_user_id', _UNSET)

    if not challenge_b64 or not email or not domain:
        return None, 'Registration session expired'

    if bound_user_id is _UNSET:
        # State written before challenges were bound to an identity.
        return None, REGISTRATION_REFUSED

    user = None
    if bound_user_id is not None:
        user = db.session.get(User, bound_user_id)
        if (not user
                or bound_user_id not in set(proven_user_ids)
                or (user.email or '').strip().lower() != email.strip().lower()):
            return None, REGISTRATION_REFUSED
    else:
        refusal = new_account_registration_refusal(email, domain)
        if refusal:
            return None, refusal[0]

    try:
        challenge = base64url_to_bytes(challenge_b64)

        verification = verify_registration_response(
            credential=credential_json,
            expected_challenge=challenge,
            expected_rp_id=get_rp_id(),
            expected_origin=get_rp_origin(),
        )

        if not user:
            # New account (allowed by new_account_registration_refusal above).
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

        user.last_login = datetime.now(timezone.utc)
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
        # Offer the user's registered credentials whatever their auth_type:
        # password-first and social sign-in accounts can hold passkeys too.
        user = User.query.filter_by(email=email).first()
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
        db_credential.last_used_at = datetime.now(timezone.utc)
        user.last_login = datetime.now(timezone.utc)
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
    user = db.session.get(User, user_id)
    if user and len(user.webauthn_credentials) <= 1:
        return False, 'Cannot delete the only credential'

    db.session.delete(credential)
    db.session.commit()
    return True, None
