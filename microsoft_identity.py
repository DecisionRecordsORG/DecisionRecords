"""
Who a Microsoft sign-in identifies, and which organisation they belong to.

Every Microsoft sign-in path of the Enterprise Edition uses this module: the
Teams tab (single sign-on token and the sign-in window fallback), the Teams
bot, "Connect Teams" in the organisation settings, and the two web sign-ins
("Sign in with Teams", "Sign in with Microsoft"). The Community Edition has
none of those routes and never calls it. It lives beside app.py, which holds
the routes, and uses only the models.

The rules, in one place:

- A person is identified by the Microsoft tenant ID (`tid`) and their object
  ID (`oid`) in that tenant. Both are immutable. The sign-in name
  (`preferred_username`, or `upn` in v1.0 tokens) is used as the account's
  address and to find the organisation the first time a Microsoft tenant is
  seen. The `email` claim is a profile field its owner's administrator can set
  to anything, and is not used unless Microsoft marks its domain as verified.
- An organisation is keyed on the Microsoft tenant ID: the Teams workspace row
  links one Microsoft tenant to one organisation, and everyone who signs in
  from that Microsoft tenant belongs to that organisation, whatever the domain
  of their sign-in name (a Microsoft tenant can have several domains, and a
  tenant without a custom domain has only `<name>.onmicrosoft.com`).
- The first time a Microsoft tenant is seen, the organisation is the one whose
  domain equals the domain of the sign-in name, or a new one for that domain.
  A member's sign-in name always uses a domain the Microsoft tenant has
  verified, and a domain can be verified in one Microsoft tenant only. An
  organisation already linked to another Microsoft tenant is never joined.
- Guests are refused. A guest's token names the tenant they are visiting in
  `tid` and their home address in the sign-in name, so a guest could otherwise
  link the tenant they are visiting to their home organisation.
- Personal Microsoft accounts are refused.
- An account that already exists in another organisation is never moved, and
  an address on the domain of another organisation is never given an account
  outside that organisation.
"""
import logging
import re
from datetime import datetime, timezone

from models import (
    db, User, Tenant, TenantMembership, Space, GlobalRole, MaturityState,
    AuthConfig, DomainApproval, TeamsWorkspace, TeamsUserMapping
)

logger = logging.getLogger(__name__)

# The tenant personal Microsoft accounts (outlook.com and so on) sign in to
PERSONAL_ACCOUNT_TENANT_ID = '9188040d-6c67-4c5b-b112-36a304b66dad'

GUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)

# Refusal codes and the sentence shown to the person. The codes are part of
# the API: the tab maps them to its own wording.
REFUSALS = {
    'invalid_identity': 'Your Microsoft sign-in could not be verified.',
    'personal_account': 'Personal accounts cannot be used. Sign in with your work or school account.',
    'guest_account': ('Guest accounts cannot use Decision Records in this Microsoft 365 organisation. '
                      'Use it from your own organisation.'),
    'other_microsoft_tenant': 'Your Microsoft 365 organisation is not the one connected to this organisation',
    'teams_disconnected': ('An administrator disconnected Microsoft Teams from this organisation. '
                           'An administrator can reconnect it in the organisation settings on the web.'),
    'organisation_unavailable': 'This organisation is no longer available.',
    'account_in_other_organisation': ('Your address already has a Decision Records account in another '
                                      'organisation. Contact support to have it moved.'),
    'account_unavailable': 'This account can no longer be used.',
}


class SignInRefused(Exception):
    """A verified Microsoft sign-in that cannot be given an account here."""

    def __init__(self, code, message=None, extra=None):
        super().__init__(code)
        self.code = code
        self.message = message or REFUSALS.get(code, REFUSALS['invalid_identity'])
        self.extra = extra or {}

    def body(self):
        # The user limit keeps the body every sign-in path returns for it
        if self.code == 'user_limit' and isinstance(self.extra.get('refusal'), dict):
            return {**self.extra['refusal'], 'code': self.code}
        return {'error': self.message, 'code': self.code}


def unverified_token_claims(token):
    """The claims of a JWT, read without checking its signature.

    Only for an ID token received directly from Microsoft's token endpoint
    over TLS in exchange for the application's secret, which OpenID Connect
    allows in place of the signature check (Core 3.1.3.7). Never for a token
    that arrives any other way. Returns None when the token cannot be read.
    """
    import base64
    import json

    if not isinstance(token, str) or token.count('.') != 2:
        return None
    payload = token.split('.')[1]
    try:
        claims = json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)))
    except (ValueError, TypeError):
        return None
    return claims if isinstance(claims, dict) else None


def _text(claims, name):
    value = claims.get(name)
    return value.strip() if isinstance(value, str) else ''


def is_guid(value) -> bool:
    return isinstance(value, str) and bool(GUID_PATTERN.match(value.strip()))


def _issuer_of(tenant_id):
    tenant_id = tenant_id.lower()
    return (f'https://login.microsoftonline.com/{tenant_id}/v2.0', f'https://sts.windows.net/{tenant_id}')


def split_sign_in_name(name):
    """(address, domain) of a usable sign-in name, or (None, None)."""
    if not isinstance(name, str):
        return None, None
    name = name.strip().lower()
    local_part, at, domain = name.partition('@')
    if not at or not local_part or not domain or '@' in domain or '.' not in domain \
            or any(c.isspace() for c in name):
        return None, None
    return name, domain


def looks_like_guest_name(name) -> bool:
    """A guest's user principal name inside the tenant they visit: user_home.com#EXT#@tenant."""
    return isinstance(name, str) and '#ext#' in name.lower()


def identity_from_claims(claims, *, expected_audience=None):
    """The person verified claims identify.

    `claims` must come from a token whose signature was verified, or from an
    ID token received directly from Microsoft's token endpoint. Nothing here
    replaces that verification.

    With `expected_audience` (ID tokens from the token endpoint), the `aud`
    claim must be exactly that application ID and the token must not have
    expired.

    Returns a dict (object_id, ms_tenant_id, email, domain, name). Raises
    SignInRefused.
    """
    if not isinstance(claims, dict):
        raise SignInRefused('invalid_identity')

    object_id, ms_tenant_id = _text(claims, 'oid'), _text(claims, 'tid').lower()
    if not object_id or not is_guid(ms_tenant_id):
        raise SignInRefused('invalid_identity')

    issuer = _text(claims, 'iss').lower().rstrip('/')
    if issuer not in _issuer_of(ms_tenant_id):
        logger.warning("Microsoft sign-in refused: issuer does not match the token's tenant")
        raise SignInRefused('invalid_identity')

    if expected_audience is not None:
        if _text(claims, 'aud').lower() != str(expected_audience).strip().lower():
            logger.warning("Microsoft sign-in refused: token is for another application")
            raise SignInRefused('invalid_identity')
        expires = claims.get('exp')
        if isinstance(expires, bool) or not isinstance(expires, (int, float)) \
                or expires < datetime.now(timezone.utc).timestamp() - 60:
            raise SignInRefused('invalid_identity')

    if ms_tenant_id == PERSONAL_ACCOUNT_TENANT_ID:
        raise SignInRefused('personal_account')

    # Guests: the identity provider is not the tenant that issued the token,
    # or Microsoft says so in the optional acct claim
    identity_provider = _text(claims, 'idp').lower().rstrip('/')
    if identity_provider and identity_provider not in _issuer_of(ms_tenant_id):
        raise SignInRefused('guest_account')
    if claims.get('acct') in (1, '1'):
        raise SignInRefused('guest_account')

    sign_in_name = _text(claims, 'preferred_username') or _text(claims, 'upn')
    if looks_like_guest_name(sign_in_name):
        raise SignInRefused('guest_account')
    # The email claim is a profile field and only counts when Microsoft marks
    # its domain as verified for the tenant
    if not sign_in_name and claims.get('xms_edov') in (True, 'true', 'True', 1, '1'):
        sign_in_name = _text(claims, 'email')

    email, domain = split_sign_in_name(sign_in_name)
    if not email:
        logger.warning("Microsoft sign-in refused: token carries no usable sign-in name")
        raise SignInRefused('invalid_identity')

    return {
        'object_id': object_id,
        'ms_tenant_id': ms_tenant_id,
        'email': email,
        'domain': domain,
        'name': _text(claims, 'name') or email.split('@')[0],
    }


def is_unusable_domain(domain) -> bool:
    """Domains no organisation can be created for."""
    domain = (domain or '').lower().strip()
    return (not domain or domain in ('placeholder.local', 'onmicrosoft.com')
            or DomainApproval.is_public_domain(domain) or DomainApproval.is_disposable_domain(domain))


def workspace_for_microsoft_tenant(ms_tenant_id):
    """The Teams workspace row of a Microsoft tenant (any state), or None."""
    if not is_guid(ms_tenant_id):
        return None
    return TeamsWorkspace.query.filter(
        db.func.lower(TeamsWorkspace.ms_tenant_id) == ms_tenant_id.strip().lower()
    ).first()


def _organisation_name(domain):
    return domain.split('.')[0].replace('-', ' ').title() or domain


def _create_organisation(domain, email, name):
    """A new organisation set up the way every sign-in path sets one up."""
    tenant = Tenant(
        domain=domain,
        name=_organisation_name(domain),
        status='active',
        maturity_state=MaturityState.BOOTSTRAP,
        created_at=datetime.now(timezone.utc)
    )
    db.session.add(tenant)
    db.session.flush()

    if not AuthConfig.query.filter_by(domain=domain).first():
        db.session.add(AuthConfig(
            domain=domain,
            auth_method='local',
            allow_password=True,
            allow_passkey=True,
            allow_slack_oidc=True,
            allow_google_oauth=True,
            allow_microsoft_oauth=True,
            allow_registration=True,
            require_approval=True,
            rp_name='Decision Records'
        ))

    if not DomainApproval.query.filter_by(domain=domain).first():
        db.session.add(DomainApproval(
            domain=domain,
            status='approved',
            requested_by_email=email,
            requested_by_name=name,
            auto_approved=True,
            reviewed_at=datetime.now(timezone.utc)
        ))

    db.session.add(Space(
        tenant_id=tenant.id,
        name='General',
        description='Default space for decisions',
        is_default=True,
        created_at=datetime.now(timezone.utc)
    ))
    logger.info(f"Created organisation {tenant.id} for domain {domain} from a Microsoft sign-in")
    return tenant


def check_address_domain(tenant, domain):
    """Refuse a sign-in name whose domain is not the organisation's and is not free.

    A Microsoft tenant can have several domains, so a member of the tenant an
    organisation is linked to may sign in with a name on another domain. That
    domain must not be a personal mail domain, and must not be the domain of
    a different organisation here: an address of another organisation's
    domain is never given an account outside that organisation.
    """
    domain = (domain or '').lower()
    if domain == tenant.domain:
        return
    if is_unusable_domain(domain):
        raise SignInRefused('personal_account')
    if Tenant.query.filter_by(domain=domain).first() is not None:
        logger.warning(f"Microsoft sign-in refused: {domain} belongs to another organisation "
                       f"than the one linked to the Microsoft tenant ({tenant.domain})")
        raise SignInRefused('other_microsoft_tenant')


def organisation_for_identity(identity, *, workspace=None, link=True):
    """The organisation a verified Microsoft identity belongs to.

    Keyed on the Microsoft tenant ID. The first time a Microsoft tenant is
    seen it is linked to the organisation of the sign-in name's domain (an
    existing one that no other Microsoft tenant is linked to, or a new one).

    `workspace` may be passed when the caller already holds the workspace row
    of the identity's Microsoft tenant (the bot does). With `link=False`
    nothing is created or linked and None is returned when there is no
    organisation yet.

    Returns (tenant, workspace). Nothing is committed. Raises SignInRefused.
    """
    ms_tenant_id, domain = identity['ms_tenant_id'], identity['domain']

    if workspace is not None and (workspace.ms_tenant_id or '').lower() != ms_tenant_id:
        raise SignInRefused('other_microsoft_tenant')
    if workspace is None:
        workspace = workspace_for_microsoft_tenant(ms_tenant_id)

    if workspace is not None:
        if workspace.status == TeamsWorkspace.STATUS_DISCONNECTED or workspace.is_active is False:
            raise SignInRefused('teams_disconnected')
        if workspace.tenant_id:
            tenant = workspace.tenant
            if tenant is None or tenant.deleted_at is not None:
                raise SignInRefused('organisation_unavailable')
            check_address_domain(tenant, domain)
            return tenant, workspace

    # This Microsoft tenant has no organisation yet
    if is_unusable_domain(domain):
        raise SignInRefused('personal_account')

    tenant = Tenant.query.filter_by(domain=domain).first()
    if tenant is not None:
        if tenant.deleted_at is not None:
            raise SignInRefused('organisation_unavailable')
        linked = TeamsWorkspace.query.filter_by(tenant_id=tenant.id).first()
        if linked is not None and linked is not workspace:
            logger.warning(f"Microsoft sign-in refused: tenant {ms_tenant_id} is not the one "
                           f"connected to {domain}")
            raise SignInRefused('other_microsoft_tenant')

    if not link:
        return tenant, workspace

    if tenant is None:
        tenant = _create_organisation(domain, identity['email'], identity['name'])

    if workspace is None:
        workspace = TeamsWorkspace(
            ms_tenant_id=ms_tenant_id,
            tenant_id=tenant.id,
            status=TeamsWorkspace.STATUS_ACTIVE,
            is_active=True
        )
        db.session.add(workspace)
    else:
        workspace.tenant_id = tenant.id
    db.session.flush()
    logger.info(f"Linked Microsoft tenant {ms_tenant_id} to organisation {tenant.id} ({tenant.domain})")
    return tenant, workspace


def _usable(user):
    return bool(user) and not user.is_anonymized and user.deleted_at is None


def existing_account(identity, tenant, workspace):
    """The account this identity already has in the organisation, or None.

    Found by the workspace's record of the object ID first, so a person whose
    sign-in name changed keeps their account, then by address. Raises
    SignInRefused when the address belongs to an account elsewhere.
    """
    mapping = None
    if workspace is not None and workspace.id is not None:
        mapping = TeamsUserMapping.query.filter_by(
            teams_workspace_id=workspace.id,
            aad_object_id=identity['object_id']
        ).first()
    if mapping and mapping.user_id:
        user = db.session.get(User, mapping.user_id)
        if user is not None:
            if not _usable(user):
                raise SignInRefused('account_unavailable')
            if user.sso_domain == tenant.domain:
                return user, mapping

    user = User.query.filter(db.func.lower(User.email) == identity['email']).first()
    if user is None:
        return None, mapping
    if not _usable(user):
        raise SignInRefused('account_unavailable')
    if user.sso_domain != tenant.domain:
        raise SignInRefused('account_in_other_organisation')
    return user, mapping


def ensure_membership(user, tenant):
    """Make the account a member of the organisation; the first member administers it."""
    membership = TenantMembership.query.filter_by(user_id=user.id, tenant_id=tenant.id).first()
    if membership:
        return membership
    is_first_member = (
        user.sso_domain == tenant.domain
        and TenantMembership.query.filter_by(tenant_id=tenant.id).count() == 0
        and User.query.filter(User.sso_domain == tenant.domain, User.id != user.id).count() == 0
    )
    membership = TenantMembership(
        user_id=user.id,
        tenant_id=tenant.id,
        global_role=GlobalRole.PROVISIONAL_ADMIN if is_first_member else GlobalRole.USER,
        joined_at=datetime.now(timezone.utc)
    )
    db.session.add(membership)
    if is_first_member:
        # admin_required reads the user flag
        user.is_admin = True
    return membership


def sign_in(identity, *, user_limit_refusal, workspace=None, new_account_auth_type='teams'):
    """Find or create the account and organisation of a verified Microsoft identity.

    `user_limit_refusal(domain, email)` is the application's own user limit
    check. A new account gets `new_account_auth_type` ('teams': Microsoft is
    its identity provider and it needs no local credential); pass None to
    leave the default for the caller to settle. Commits on success; on
    refusal nothing is kept.

    Returns (user, tenant, workspace). Raises SignInRefused.
    """
    try:
        tenant, workspace = organisation_for_identity(identity, workspace=workspace)
        user, mapping = existing_account(identity, tenant, workspace)

        if user is None:
            refusal = user_limit_refusal(tenant.domain, identity['email'])
            if refusal:
                raise SignInRefused('user_limit', refusal.get('message'), extra={'refusal': refusal})
            from auth import get_or_create_user
            user = get_or_create_user(identity['email'], identity['name'], identity['object_id'],
                                      tenant.domain)
            if new_account_auth_type:
                user.auth_type = new_account_auth_type
            user.email_verified = True
            method = 'auto_provisioned'
        else:
            user.last_login = datetime.now(timezone.utc)
            method = 'auto_linked'

        if not user.aad_object_id:
            user.aad_object_id = identity['object_id']
        ensure_membership(user, tenant)

        if mapping is None:
            db.session.add(TeamsUserMapping(
                teams_workspace_id=workspace.id,
                aad_object_id=identity['object_id'],
                aad_user_principal_name=identity['email'],
                aad_email=identity['email'],
                aad_display_name=identity['name'],
                user_id=user.id,
                linked_at=datetime.now(timezone.utc),
                link_method=method
            ))
        elif mapping.user_id != user.id:
            mapping.user_id = user.id
            mapping.linked_at = datetime.now(timezone.utc)
            mapping.link_method = method

        db.session.commit()
        return user, tenant, workspace
    except SignInRefused:
        db.session.rollback()
        raise
