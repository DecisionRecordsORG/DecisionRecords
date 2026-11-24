"""
Data retention: the work behind the deletion timelines the product promises.

Five categories, each run in isolation:

    accounts       anonymise accounts whose 7-day deletion grace period is over
    decisions      erase soft-deleted decisions whose 30-day window is over
    tenants        erase soft-deleted tenants whose 30-day window is over
    login_history  delete sign-in history older than 90 days
    inquiries      delete stored contact messages older than 24 months

One routine (`run_retention`) does the work. It can run for real, as a preview
that changes nothing (`preview_retention`), and limited to chosen categories.
It is started in three ways: by the application itself once a day (the
scheduler at the bottom of this file), by a super admin, and by an operator's
cron job through POST /api/admin/execute-gdpr-tasks.

Safety rails
------------
Erasure cannot be undone, so an automatic run is deliberately timid:

* Per-category limits. If more accounts, decisions or tenants are waiting than
  the limit, the run does nothing in that category, records that it held back
  and how many are waiting, and carries on with the other categories.
* Backlog check. If the oldest waiting item is more than a few days overdue,
  retention has not been keeping up (it never ran, or it was off). The category
  is held back however few items there are, so a person looks first.
* A held back category is released only by a super admin who names the
  category and repeats the number shown in the preview.
* Every item is checked again, under a row lock, in the transaction that
  erases it. Something restored or un-scheduled a moment earlier is skipped.
* A record of what was erased (kind, identifiers, counts, never content) is
  written in the same transaction as the erasure.

Default limits and why
----------------------
accounts 10, decisions 50, tenants 1, backlog 7 days.

An account is anonymised only after its owner asked for deletion and waited
seven days; more than ten falling due on one day is not normal volume for an
installation of 25-user teams. A member can soft-delete at most a handful of
decisions an hour, so fifty expiring on one day is already a busy day; a
tenant's own decisions are erased with the tenant and do not count here.
Deleting a tenant is a rare super admin action, so two tenants expiring on the
same day is unusual enough to ask for a second look. Login history and stored
messages are deleted by age alone and have no limit: holding them back would
only add an operator step.

Times
-----
Every DateTime column stores UTC without a timezone. All comparisons here use
a naive UTC "now" so the result does not depend on the database session's
time zone (PostgreSQL converts an aware value to the session zone before
comparing it with a `timestamp` column).

Much of the application writes aware datetimes. On a PostgreSQL session that
is not set to UTC those are stored shifted by the session's offset, so a due
date in the database can be up to that many hours early. Retention therefore
waits the size of the offset plus an hour (for daylight saving changes) before
it treats anything as due: see `due_time`. On a UTC session, and on SQLite,
the wait is zero.
"""

import logging
import os
import random
import threading
import time
import uuid
import json
import re
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from models import (
    db, User, Tenant, TenantMembership, TenantSettings, Space, DecisionSpace, AuditLog,
    LoginHistory, Inquiry, UserConsent, SSOConfig, EmailConfig, AuthConfig, DomainApproval,
    WebAuthnCredential, Subscription, ITInfrastructure, ArchitectureDecision,
    DecisionRelationship, DecisionHistory, DecisionComment, AccessRequest, RoleRequest,
    SetupToken, EmailVerification, SlackWorkspace, SlackUserMapping, TeamsWorkspace,
    TeamsUserMapping, TeamsConversationReference, AIApiKey, AIInteractionLog, SystemConfig,
    RetentionRun, RetentionErasure, decision_infrastructure,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

ACCOUNTS = 'accounts'
DECISIONS = 'decisions'
TENANTS = 'tenants'
LOGIN_HISTORY = 'login_history'
INQUIRIES = 'inquiries'

# The order they run in. Age-based deletes go before the per-item erasures so
# a slow or failing erase cannot hold them up.
CATEGORIES = (ACCOUNTS, LOGIN_HISTORY, INQUIRIES, DECISIONS, TENANTS)

# Categories an automatic run limits. The other two are deleted by age alone.
LIMITED_CATEGORIES = (ACCOUNTS, DECISIONS, TENANTS)

LIMIT_KEYS = {
    ACCOUNTS: (SystemConfig.KEY_RETENTION_LIMIT_ACCOUNTS, SystemConfig.DEFAULT_RETENTION_LIMIT_ACCOUNTS),
    DECISIONS: (SystemConfig.KEY_RETENTION_LIMIT_DECISIONS, SystemConfig.DEFAULT_RETENTION_LIMIT_DECISIONS),
    TENANTS: (SystemConfig.KEY_RETENTION_LIMIT_TENANTS, SystemConfig.DEFAULT_RETENTION_LIMIT_TENANTS),
}
MAX_LIMIT = 100000
MAX_BACKLOG_DAYS = 3650

# Keys the cron endpoint has always returned, per category.
LEGACY_RESULT_KEYS = {
    ACCOUNTS: 'anonymized_users',
    DECISIONS: 'purged_decisions',
    TENANTS: 'purged_tenants',
    LOGIN_HISTORY: 'cleaned_login_history',
    INQUIRIES: 'purged_inquiries',
}

LOGIN_HISTORY_RETENTION_DAYS = 90

STATUS_DONE = 'done'
STATUS_HELD_BACK = 'held_back'
STATUS_ERROR = 'error'

HOLD_OVER_LIMIT = 'over_limit'
HOLD_BACKLOG = 'backlog'

PREVIEW_ITEM_LIMIT = 100
MAX_RECORDED_ERRORS = 20

# A run still marked "running" after this long was cut off (worker killed,
# container stopped). It is marked interrupted so it no longer counts as live.
STALE_RUN_AFTER = timedelta(hours=6)

AUTO_RUN_ENV = 'RETENTION_AUTO_RUN'
_FALSE_VALUES = ('false', '0', 'no', 'off')


def utcnow():
    """Now, in UTC, without a timezone: the form the DateTime columns store."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_naive_utc(value):
    """A datetime as naive UTC. Naive values are taken to be UTC already."""
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _iso(value):
    return value.isoformat() + 'Z' if value else None


def _session_utc_offset_seconds():
    """The database session's offset from UTC in seconds. 0 on SQLite."""
    if db.engine.dialect.name != 'postgresql':
        return 0
    return int(db.session.execute(sa.text('SELECT EXTRACT(TIMEZONE FROM now())')).scalar() or 0)


def safety_margin():
    """How long to wait past a stored due date before trusting it (see "Times")."""
    offset = abs(_session_utc_offset_seconds())
    return timedelta(seconds=offset) + timedelta(hours=1) if offset else timedelta(0)


def due_time(now=None):
    """The moment everything is compared with: now, in naive UTC, minus the safety margin."""
    return (to_naive_utc(now) or utcnow()) - safety_margin()


def _short_error(exc):
    """Exception class and first line only: no statement parameters, no row values."""
    original = getattr(exc, 'orig', None) or exc
    first_line = (str(original).strip().splitlines() or [''])[0]
    return f'{type(original).__name__}: {first_line}'[:300]


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def auto_run_disabled_by_environment():
    """True when RETENTION_AUTO_RUN turns the automatic run off for this process."""
    return os.environ.get(AUTO_RUN_ENV, '').strip().lower() in _FALSE_VALUES


def get_limits():
    """The per-category limits of an automatic run."""
    limits = {}
    for category, (key, default) in LIMIT_KEYS.items():
        value = SystemConfig.get_int(key, default=default)
        limits[category] = value if value >= 0 else default
    return limits


def get_backlog_days():
    value = SystemConfig.get_int(
        SystemConfig.KEY_RETENTION_BACKLOG_DAYS, default=SystemConfig.DEFAULT_RETENTION_BACKLOG_DAYS
    )
    return value if value >= 0 else SystemConfig.DEFAULT_RETENTION_BACKLOG_DAYS


def get_settings():
    """Retention settings as the settings API returns them."""
    setting_enabled = SystemConfig.get_bool(
        SystemConfig.KEY_RETENTION_AUTO_RUN_ENABLED, default=SystemConfig.DEFAULT_RETENTION_AUTO_RUN_ENABLED
    )
    by_environment = auto_run_disabled_by_environment()
    return {
        'auto_run_enabled': setting_enabled,
        'auto_run_disabled_by_environment': by_environment,
        'auto_run_active': setting_enabled and not by_environment,
        'limits': get_limits(),
        'backlog_days': get_backlog_days(),
        'defaults': {
            'auto_run_enabled': SystemConfig.DEFAULT_RETENTION_AUTO_RUN_ENABLED,
            'limits': {category: default for category, (_, default) in LIMIT_KEYS.items()},
            'backlog_days': SystemConfig.DEFAULT_RETENTION_BACKLOG_DAYS,
        },
    }


def _whole_number(value, maximum):
    """value as an int between 0 and maximum, or None when it is not one."""
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    try:
        number = int(value)
    except (ValueError, TypeError):
        return None
    if isinstance(value, str) and value.strip() != str(number):
        return None
    return number if 0 <= number <= maximum else None


def save_settings(data):
    """Validate and store retention settings. Returns an error string or None.

    Nothing is stored unless every value given is valid.
    """
    updates = []

    if 'auto_run_enabled' in data:
        if not isinstance(data['auto_run_enabled'], bool):
            return 'auto_run_enabled must be true or false'
        updates.append((
            SystemConfig.KEY_RETENTION_AUTO_RUN_ENABLED,
            'true' if data['auto_run_enabled'] else 'false',
            'Run data retention automatically once a day',
        ))

    limits = data.get('limits')
    if limits is not None:
        if not isinstance(limits, dict):
            return 'limits must be an object'
        for category, value in limits.items():
            if category not in LIMIT_KEYS:
                return f"limits can be set for: {', '.join(LIMITED_CATEGORIES)}"
            number = _whole_number(value, MAX_LIMIT)
            if number is None:
                return f'The limit for {category} must be a whole number between 0 and {MAX_LIMIT}'
            updates.append((
                LIMIT_KEYS[category][0], number,
                f'Most {category} one automatic retention run may erase (0 = always hold back)',
            ))

    if 'backlog_days' in data:
        number = _whole_number(data['backlog_days'], MAX_BACKLOG_DAYS)
        if number is None:
            return f'backlog_days must be a whole number between 0 and {MAX_BACKLOG_DAYS}'
        updates.append((
            SystemConfig.KEY_RETENTION_BACKLOG_DAYS, number,
            'Hold a category back when its oldest item is more than this many days overdue (0 = off)',
        ))

    for key, value, description in updates:
        SystemConfig.set(key, value, description=description)
    return None


# ---------------------------------------------------------------------------
# What is waiting
# ---------------------------------------------------------------------------

def _not_anonymised():
    # is_anonymized is NULL on rows older than the column
    return sa.or_(User.is_anonymized.is_(False), User.is_anonymized.is_(None))


def _accounts_due(now):
    return (
        User.deletion_scheduled_at.isnot(None),
        User.deletion_scheduled_at <= now,
        User.deleted_at.is_(None),
        _not_anonymised(),
    )


def _decisions_due(now):
    # A soft-deleted tenant's decisions are erased with the tenant (or come
    # back with it when it is restored), never one by one.
    in_deleted_tenant = sa.exists().where(
        Tenant.id == ArchitectureDecision.tenant_id, Tenant.deleted_at.isnot(None)
    )
    return (
        ArchitectureDecision.deleted_at.isnot(None),
        ArchitectureDecision.deletion_expires_at.isnot(None),
        ArchitectureDecision.deletion_expires_at <= now,
        ~in_deleted_tenant,
    )


def _tenants_expired(now):
    return (
        Tenant.deleted_at.isnot(None),
        Tenant.deletion_expires_at.isnot(None),
        Tenant.deletion_expires_at <= now,
    )


def _tenants_due(now):
    # Soft-deleting a tenant sets status 'deleted' and restoring it sets
    # 'active'. An expired tenant in any other status was changed by hand and
    # is never erased here: see `tenants_needing_review`.
    return _tenants_expired(now) + (Tenant.status == 'deleted',)


def tenants_needing_review(now):
    """Expired soft-deleted tenants whose status is not 'deleted'. Never erased."""
    return Tenant.query.filter(
        *_tenants_expired(now), sa.or_(Tenant.status != 'deleted', Tenant.status.is_(None))
    ).order_by(Tenant.id).all()


def _login_history_cutoff(now):
    return now - timedelta(days=LOGIN_HISTORY_RETENTION_DAYS)


def _inquiries_cutoff(now):
    return now - timedelta(days=Inquiry.RETENTION_DAYS)


def _waiting(category, now):
    """(count, oldest due date) for a category."""
    if category == ACCOUNTS:
        column, filters = User.deletion_scheduled_at, _accounts_due(now)
        count = db.session.query(sa.func.count(User.id)).filter(*filters).scalar()
    elif category == DECISIONS:
        column, filters = ArchitectureDecision.deletion_expires_at, _decisions_due(now)
        count = db.session.query(sa.func.count(ArchitectureDecision.id)).filter(*filters).scalar()
    elif category == TENANTS:
        column, filters = Tenant.deletion_expires_at, _tenants_due(now)
        count = db.session.query(sa.func.count(Tenant.id)).filter(*filters).scalar()
    elif category == LOGIN_HISTORY:
        count = db.session.query(sa.func.count(LoginHistory.id)).filter(
            LoginHistory.created_at < _login_history_cutoff(now)).scalar()
        return count or 0, None
    else:
        count = db.session.query(sa.func.count(Inquiry.id)).filter(
            Inquiry.created_at < _inquiries_cutoff(now)).scalar()
        return count or 0, None
    oldest = db.session.query(sa.func.min(column)).filter(*filters).scalar() if count else None
    return count or 0, to_naive_utc(oldest)


def _due_ids(category, now, cap=None):
    """Ids of the items due in a per-item category, oldest first, at most `cap`.

    Only a list of candidates: each one is checked again under a row lock in
    the transaction that erases it.
    """
    if category == ACCOUNTS:
        query = db.session.query(User.id).filter(*_accounts_due(now)).order_by(
            User.deletion_scheduled_at, User.id)
    elif category == DECISIONS:
        query = db.session.query(ArchitectureDecision.id).filter(*_decisions_due(now)).order_by(
            ArchitectureDecision.deletion_expires_at, ArchitectureDecision.id)
    else:
        query = db.session.query(Tenant.id).filter(*_tenants_due(now)).order_by(
            Tenant.deletion_expires_at, Tenant.id)
    ids = [row[0] for row in (query.limit(cap) if cap is not None else query).all()]
    db.session.commit()
    return ids


def _hold_reason(category, count, oldest, now, limits, backlog_days):
    """Why an automatic run would hold this category back, or None."""
    if category not in LIMITED_CATEGORIES or count == 0:
        return None
    if count > limits[category]:
        return HOLD_OVER_LIMIT
    if backlog_days > 0 and oldest is not None and now - oldest > timedelta(days=backlog_days):
        return HOLD_BACKLOG
    return None


def _preview_items(category, now):
    """Up to PREVIEW_ITEM_LIMIT waiting items, oldest first, for a super admin to read."""
    if category == ACCOUNTS:
        rows = User.query.filter(*_accounts_due(now)).order_by(
            User.deletion_scheduled_at, User.id).limit(PREVIEW_ITEM_LIMIT).all()
        return [{
            'id': user.id,
            'label': user.email,
            'due_at': _iso(to_naive_utc(user.deletion_scheduled_at)),
        } for user in rows]
    if category == DECISIONS:
        rows = ArchitectureDecision.query.filter(*_decisions_due(now)).order_by(
            ArchitectureDecision.deletion_expires_at, ArchitectureDecision.id).limit(PREVIEW_ITEM_LIMIT).all()
        return [{
            'id': decision.id,
            'label': _decision_identifier(decision),
            'due_at': _iso(to_naive_utc(decision.deletion_expires_at)),
        } for decision in rows]
    if category == TENANTS:
        rows = Tenant.query.filter(*_tenants_due(now)).order_by(
            Tenant.deletion_expires_at, Tenant.id).limit(PREVIEW_ITEM_LIMIT).all()
        return [{
            'id': tenant.id,
            'label': tenant.domain,
            'due_at': _iso(to_naive_utc(tenant.deletion_expires_at)),
            'counts': _tenant_preview_counts(tenant),
        } for tenant in rows]
    return []


def preview_retention(now=None, categories=None, include_items=True):
    """What a run would affect right now. Changes nothing.

    Returns {category: {waiting, limit, would_hold, hold_reason, oldest_due_at,
    cutoff, items, items_truncated}}. `would_hold` says what an automatic run
    would do; a super admin can still run the category deliberately.
    """
    now = due_time(now)
    limits = get_limits()
    backlog_days = get_backlog_days()
    preview = {}
    for category in _normalise_categories(categories):
        count, oldest = _waiting(category, now)
        reason = _hold_reason(category, count, oldest, now, limits, backlog_days)
        entry = {
            'waiting': count,
            'limit': limits.get(category),
            'would_hold': reason is not None,
            'hold_reason': reason,
            'oldest_due_at': _iso(oldest),
            'cutoff': None,
            'items': [],
            'items_truncated': False,
        }
        if category == LOGIN_HISTORY:
            entry['cutoff'] = _iso(_login_history_cutoff(now))
        elif category == INQUIRIES:
            entry['cutoff'] = _iso(_inquiries_cutoff(now))
        elif include_items and count:
            entry['items'] = _preview_items(category, now)
            entry['items_truncated'] = count > len(entry['items'])
        if category == TENANTS:
            entry['needs_review'] = [
                {'id': tenant.id, 'label': tenant.domain, 'status': tenant.status}
                for tenant in tenants_needing_review(now)
            ]
        preview[category] = entry
    return preview


def _normalise_categories(categories):
    if categories is None:
        return list(CATEGORIES)
    unknown = [c for c in categories if c not in CATEGORIES]
    if unknown:
        raise ValueError(f"Unknown retention category: {', '.join(str(c) for c in unknown)}")
    return [c for c in CATEGORIES if c in categories]


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

# The name a deleted member's contributions carry.
FORMER_MEMBER = 'Former Member'
# What replaces the person's email address where it was written into a record.
DELETED_USER = 'deleted-user'
# The name left on an API key of a deleted member (the key itself is revoked).
DELETED_KEY_NAME = 'Deleted key'

# What anonymising an account does with every text, JSON and binary column in
# the database. A person's name, email address or IP address can sit in a
# column as text instead of being a reference to their account; a reference
# turns into "Former Member" by itself when the account row is anonymised, a
# copy of the name does not.
#
#   CLEARED         can name the person. Anonymisation empties it, replaces it
#                   or deletes the row.
#   CONTENT         what the person wrote as part of the organisation's record
#                   (a decision, a comment, the reason for a change). Kept on
#                   purpose: the product keeps contributions and removes who
#                   made them.
#   NOT_THE_PERSON  settings, codes, the organisation's own details, and names
#                   of other people (a super admin, another requester), who are
#                   handled when their own account is anonymised.
#
# tests/test_account_anonymise.py fails when a column is missing from this
# list, and searches every one of these columns for the person after an
# anonymisation, so a new column cannot be added without deciding.
CLEARED = 'cleared'
CONTENT = 'content'
NOT_THE_PERSON = 'not the person'


def _account_text_rules():
    cleared = {
        'users': 'email name first_name last_name password_hash sso_subject aad_object_id',
        'webauthn_credentials': 'credential_id public_key device_name transports',  # rows deleted
        'setup_tokens': 'email token_hash',                                          # rows deleted
        'email_verifications': 'email name token access_request_reason',             # rows deleted
        'access_requests': 'email name reason rejection_reason',                     # rows deleted
        'role_requests': 'reason rejection_reason',                # the person's own requests are deleted
        'slack_user_mappings': 'slack_user_id slack_email',                          # rows deleted
        'teams_user_mappings': 'aad_object_id aad_user_principal_name aad_email aad_display_name',  # rows deleted
        'teams_conversation_references': 'conversation_id reference_json',  # personal chat deleted, name removed elsewhere
        'domain_approvals': 'requested_by_email requested_by_name',
        'login_history': 'email ip_address user_agent',
        'user_consents': 'ip_address',
        'inquiries': 'name email message',
        'architecture_decisions': 'owner_email',
        'decision_comments': 'author_display',
        'audit_logs': 'details',                                   # the name and address are replaced
        'ai_api_keys': 'name description',
        'ai_interaction_logs': 'query_text',
    }
    content = {
        'architecture_decisions': 'title context decision consequences',
        'decision_history': 'title context decision_text consequences change_reason',
        'decision_comments': 'body',
        'decision_relationships': 'notes',
        'spaces': 'name description',
        'it_infrastructure': 'name description',
    }
    not_the_person = {
        'users': 'sso_domain auth_type',
        'setup_tokens': 'purpose',
        'email_verifications': 'purpose domain',
        'access_requests': 'domain status',
        'slack_user_mappings': 'link_method',
        'teams_user_mappings': 'link_method',
        'teams_conversation_references': 'channel_id team_id context_type',
        'domain_approvals': 'domain status rejection_reason',
        'login_history': 'tenant_domain login_method failure_reason',
        'user_consents': 'consent_type',
        # organisation, area of interest and the team answers describe an organisation; handled_by is a super admin
        'inquiries': 'source organisation area_of_interest team_focus team_size tenant_domain handled_by',
        # decision_type is one of a fixed list from the decision template, never free text
        'architecture_decisions': 'status domain decision_type',
        'decision_history': 'status decision_type',
        'decision_relationships': 'relationship_type target_previous_status',
        'it_infrastructure': 'type domain',
        'audit_logs': 'action_type target_entity',
        'ai_api_keys': 'key_hash key_prefix scopes',               # the key is revoked
        'ai_interaction_logs': 'decision_ids llm_provider llm_model error_message',
        'tenants': 'domain name status deleted_by_admin team_focus team_size industry',
        'tenant_settings': 'auth_method rp_name tenant_prefix decision_relationship_pack_ids '
                           'decision_relationship_enabled_types decision_relationship_custom_types '
                           'decision_template_id',
        'auth_configs': 'domain auth_method rp_name tenant_prefix',
        'sso_configs': 'domain provider_name client_id client_secret discovery_url',
        'email_configs': 'domain smtp_server smtp_username smtp_password from_email from_name',
        'slack_workspaces': 'workspace_id workspace_name bot_token_encrypted status default_channel_id '
                            'default_channel_name granted_scopes app_version',
        'teams_workspaces': 'ms_tenant_id ms_tenant_name service_url bot_id status default_channel_id '
                            'default_channel_name default_team_id default_team_name app_version',
        'master_accounts': 'username password_hash name',
        'system_config': 'key value description',
        'blog_posts': 'slug title excerpt author category read_time image meta_description meta_keywords content',
        'retention_runs': 'claim_key trigger started_by status categories results error',
        'retention_erasures': 'category entity_type identifier counts',
    }
    rules = {}
    for rule, tables in ((CLEARED, cleared), (CONTENT, content), (NOT_THE_PERSON, not_the_person)):
        for table, columns in tables.items():
            for column in columns.split():
                rules[f'{table}.{column}'] = rule
    return rules


ACCOUNT_TEXT_RULES = _account_text_rules()


def _replace_in_text(text, replacements):
    """`text` with every (pattern, replacement) applied."""
    for pattern, replacement in replacements:
        text = pattern.sub(replacement, text)
    return text


def _redact_json(value, replacements):
    """A copy of a JSON value with the replacements applied to every string in it."""
    if isinstance(value, str):
        return _replace_in_text(value, replacements)
    if isinstance(value, list):
        return [_redact_json(item, replacements) for item in value]
    if isinstance(value, dict):
        return {_replace_in_text(key, replacements) if isinstance(key, str) else key:
                _redact_json(item, replacements) for key, item in value.items()}
    return value


def _person_replacements(email, names):
    """Patterns that find a person in free text: their address, then their name.

    Both are matched whatever the letter case. A name is matched as whole
    words only, so a short name is not found inside another word.
    """
    replacements = []
    if email:
        replacements.append((re.compile(re.escape(email), re.IGNORECASE), DELETED_USER))
    for name in sorted({(name or '').strip() for name in names}, key=len, reverse=True):
        if len(name) < 2 or name == FORMER_MEMBER:
            continue
        replacements.append((re.compile(r'(?<!\w)' + re.escape(name) + r'(?!\w)', re.IGNORECASE), FORMER_MEMBER))
    return replacements


def _redact_audit_entries(user_id, tenant_ids, replacements):
    """Replace the person's address and name in audit log details. Returns the number of rows changed.

    Looks at the entries of the person's organisations, the entries they
    performed and the entries about them, not at every entry of every tenant.
    """
    if not replacements:
        return 0
    scope = sa.or_(
        AuditLog.actor_user_id == user_id,
        sa.and_(AuditLog.target_entity == 'user', AuditLog.target_id == user_id),
        AuditLog.tenant_id.in_(tenant_ids) if tenant_ids else sa.false(),
    )
    changed = 0
    for entry in AuditLog.query.filter(scope).all():
        if entry.details is None:
            continue
        redacted = _redact_json(entry.details, replacements)
        if redacted != entry.details:
            entry.details = redacted
            changed += 1
    return changed


def _forget_in_teams_conversations(aad_object_ids):
    """Remove a person from stored Teams conversation references. Returns the number of rows touched.

    A reference records who the bot was talking to when it was stored (their
    display name and directory id). A personal chat with the person is
    deleted. A channel or group conversation is kept, without the person:
    sending a message there needs the service address and the conversation id
    only.
    """
    touched = 0
    for aad_object_id in sorted({value for value in aad_object_ids if value}):
        rows = TeamsConversationReference.query.filter(
            TeamsConversationReference.reference_json.contains(aad_object_id, autoescape=True)).all()
        for row in rows:
            try:
                reference = json.loads(row.reference_json)
            except (TypeError, ValueError):
                reference = None
            member = reference.get('user') if isinstance(reference, dict) else None
            names_person = isinstance(member, dict) and aad_object_id in (member.get('aadObjectId'), member.get('id'))
            if row.context_type == 'personal' and (names_person or reference is None):
                db.session.delete(row)
            elif names_person:
                reference.pop('user')
                row.reference_json = json.dumps(reference)
            elif reference is None:
                # Not readable as JSON and it carries the id: keep the row, drop the text
                row.reference_json = '{}'
            else:
                continue
            touched += 1
    return touched


def _anonymise_user_record(user):
    """Strip a user's personal data in the current transaction. Returns counts.

    The row stays so contributions keep a (now anonymous) author. Does not commit.
    ACCOUNT_TEXT_RULES lists every column this has to deal with.
    """
    anonymous_email = f"deleted-{uuid.uuid4()}@anonymized.local"
    original_email = user.email
    email_key = (original_email or '').lower()
    counts = {}

    # Read what identifies the person before it is overwritten
    names = [user.name, user.get_full_name(), ' '.join(part for part in (user.first_name, user.last_name) if part)]
    replacements = _person_replacements(original_email, names)
    home_tenant = Tenant.query.filter_by(domain=user.sso_domain).first() if user.sso_domain else None
    tenant_ids = {membership.tenant_id for membership in TenantMembership.query.filter_by(user_id=user.id).all()}
    if home_tenant:
        tenant_ids.add(home_tenant.id)
    aad_object_ids = {user.aad_object_id}

    user.email = anonymous_email
    user.name = FORMER_MEMBER
    user.first_name = None
    user.last_name = None
    user.password_hash = None
    user.sso_subject = None
    user.aad_object_id = None
    user.is_anonymized = True
    user.deleted_at = utcnow()

    # Detach decisions (keep content, remove author link)
    for decision in user.decisions_created:
        decision.created_by_id = None
    # The owner fields name a person too
    ArchitectureDecision.query.filter(ArchitectureDecision.owner_id == user.id).update(
        {'owner_id': None}, synchronize_session=False)
    if email_key:
        ArchitectureDecision.query.filter(
            sa.func.lower(ArchitectureDecision.owner_email) == email_key
        ).update({'owner_email': None}, synchronize_session=False)

    # Comments stay. The author is stored as text beside the reference, so the
    # text is replaced: comments of this account, and comments recorded with
    # only the person's address as author.
    comment_filter = DecisionComment.user_id == user.id
    if email_key:
        comment_filter = sa.or_(comment_filter, sa.and_(
            DecisionComment.user_id.is_(None), sa.func.lower(DecisionComment.author_display) == email_key))
    counts['comments_reattributed'] = DecisionComment.query.filter(comment_filter).update(
        {'author_display': FORMER_MEMBER}, synchronize_session=False)

    # Everything that lets this person sign in or act
    credentials = list(user.webauthn_credentials)
    for cred in credentials:
        db.session.delete(cred)
    counts['webauthn_credentials'] = len(credentials)

    memberships = TenantMembership.query.filter_by(user_id=user.id).all()
    for membership in memberships:
        db.session.delete(membership)
    counts['tenant_memberships'] = len(memberships)

    token_filter = SetupToken.user_id == user.id
    if email_key:
        token_filter = sa.or_(token_filter, sa.func.lower(SetupToken.email) == email_key)
    counts['setup_tokens'] = SetupToken.query.filter(token_filter).delete(synchronize_session=False)

    counts['ai_api_keys_revoked'] = AIApiKey.query.filter(
        AIApiKey.user_id == user.id, AIApiKey.revoked_at.is_(None)
    ).update({'revoked_at': utcnow()}, synchronize_session=False)
    # The key rows stay for the usage records that point at them, without the
    # name and description the person typed
    AIApiKey.query.filter(AIApiKey.user_id == user.id).update(
        {'name': DELETED_KEY_NAME, 'description': None}, synchronize_session=False)
    # The usage record stays (when, which kind, how many decisions), not what was asked
    counts['ai_queries_cleared'] = AIInteractionLog.query.filter(
        AIInteractionLog.user_id == user.id, AIInteractionLog.query_text.isnot(None)
    ).update({'query_text': None}, synchronize_session=False)

    # Rows that only describe this person
    counts['subscriptions'] = Subscription.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    # Linked chat accounts, and unlinked ones that carry the person's address
    slack_filter = SlackUserMapping.user_id == user.id
    teams_filter = TeamsUserMapping.user_id == user.id
    if email_key:
        slack_filter = sa.or_(slack_filter, sa.func.lower(SlackUserMapping.slack_email) == email_key)
        teams_filter = sa.or_(
            teams_filter,
            sa.func.lower(TeamsUserMapping.aad_email) == email_key,
            sa.func.lower(TeamsUserMapping.aad_user_principal_name) == email_key)
    if user.aad_object_id:
        teams_filter = sa.or_(teams_filter, TeamsUserMapping.aad_object_id == user.aad_object_id)
    aad_object_ids.update(row.aad_object_id for row in TeamsUserMapping.query.filter(teams_filter).all())
    counts['slack_user_mappings'] = SlackUserMapping.query.filter(slack_filter).delete(
        synchronize_session=False)
    counts['teams_user_mappings'] = TeamsUserMapping.query.filter(teams_filter).delete(
        synchronize_session=False)
    counts['teams_conversations'] = _forget_in_teams_conversations(aad_object_ids)
    # A role request only describes the person who made it
    counts['role_requests'] = RoleRequest.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    UserConsent.query.filter_by(user_id=user.id).update({'ip_address': None}, synchronize_session=False)
    if email_key:
        counts['email_verifications'] = EmailVerification.query.filter(
            sa.func.lower(EmailVerification.email) == email_key).delete(synchronize_session=False)
        counts['access_requests'] = AccessRequest.query.filter(
            sa.func.lower(AccessRequest.email) == email_key).delete(synchronize_session=False)
        # The request for the organisation's domain keeps its outcome, not who asked
        counts['domain_approvals_redacted'] = DomainApproval.query.filter(
            sa.func.lower(DomainApproval.requested_by_email) == email_key
        ).update({'requested_by_email': None, 'requested_by_name': None}, synchronize_session=False)

    # Redact LoginHistory entries: the person's sign-ins, and attempts recorded
    # with their address before any account was matched (failed sign-ins)
    login_filter = LoginHistory.user_id == user.id
    if email_key:
        login_filter = sa.or_(login_filter, sa.func.lower(LoginHistory.email) == email_key)
    counts['login_history_redacted'] = LoginHistory.query.filter(login_filter).update(
        {'email': anonymous_email, 'ip_address': None, 'user_agent': None}, synchronize_session=False)

    # Remove the personal fields from messages this person sent through the
    # contact, sponsorship and feedback forms: those sent while signed in and
    # those that carry the account's email address.
    inquiry_filter = Inquiry.user_id == user.id
    if email_key:
        inquiry_filter = sa.or_(inquiry_filter, sa.func.lower(Inquiry.email) == email_key)
    inquiries = Inquiry.query.filter(inquiry_filter).all()
    for inquiry in inquiries:
        inquiry.redact()
    counts['inquiries_redacted'] = len(inquiries)

    # A team profile answer stays with the tenant, without the link to this person
    Tenant.query.filter_by(team_profile_answered_by_id=user.id).update(
        {'team_profile_answered_by_id': None}, synchronize_session=False
    )

    # Audit log entries stay; the person's address and name inside their details are replaced
    counts['audit_entries_redacted'] = _redact_audit_entries(user.id, tenant_ids, replacements)

    return counts


def anonymize_user(user_id):
    """
    Anonymize a user's personal data per GDPR Art. 17 and deletion-controls.md spec.

    Preserves contributions (decisions remain, author set to None).
    Redacts PII from audit logs and login history. Commits. Returns False when
    there is no such user or the user is already anonymised.
    """
    user = db.session.get(User, user_id)
    if not user or user.is_anonymized:
        return False
    _anonymise_user_record(user)
    db.session.commit()
    return True


def _run_accounts(now, run_id, cap):
    ids = _due_ids(ACCOUNTS, now, cap)

    affected, errors = 0, []
    for user_id in ids:
        try:
            # Lock the row and check again: the owner may have cancelled the
            # deletion since the list above was read.
            user = User.query.filter(User.id == user_id).with_for_update().populate_existing().first()
            due = (
                user is not None and not user.is_anonymized and user.deleted_at is None
                and user.deletion_scheduled_at is not None
                and to_naive_utc(user.deletion_scheduled_at) <= now
            )
            if not due:
                db.session.rollback()
                continue
            record = RetentionErasure(run_id=run_id, category=ACCOUNTS, entity_type='user', entity_id=user_id)
            db.session.add(record)
            record.counts = _anonymise_user_record(user)
            db.session.commit()
            affected += 1
        except Exception as exc:
            db.session.rollback()
            logger.exception('Retention: anonymising account %s failed', user_id)
            errors.append({'entity_id': user_id, 'error': _short_error(exc)})
    return affected, errors


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------

def _decision_identifier(decision):
    number = decision.decision_number if decision.decision_number is not None else '?'
    return f'{decision.domain}#{number}'


def _delete_decisions(decision_ids, extra_relationship_filter=None):
    """Delete decisions and every row that hangs off them. Returns counts.

    `decision_ids` is a SELECT of decision ids (or a list). Core deletes in
    foreign-key order, so nothing depends on ORM cascades or on the database
    having ON DELETE rules.
    """
    history = DecisionHistory.__table__
    comments = DecisionComment.__table__
    links = DecisionSpace.__table__
    relationships = DecisionRelationship.__table__
    decisions = ArchitectureDecision.__table__

    relationship_filter = sa.or_(
        relationships.c.source_decision_id.in_(decision_ids),
        relationships.c.target_decision_id.in_(decision_ids),
    )
    if extra_relationship_filter is not None:
        relationship_filter = sa.or_(relationship_filter, extra_relationship_filter)

    counts = {}
    counts['decision_infrastructure'] = db.session.execute(
        decision_infrastructure.delete().where(decision_infrastructure.c.decision_id.in_(decision_ids))
    ).rowcount
    counts['decision_relationships'] = db.session.execute(
        relationships.delete().where(relationship_filter)).rowcount
    counts['decision_history'] = db.session.execute(
        history.delete().where(history.c.decision_id.in_(decision_ids))).rowcount
    counts['decision_comments'] = db.session.execute(
        comments.delete().where(comments.c.decision_id.in_(decision_ids))).rowcount
    counts['decision_spaces'] = db.session.execute(
        links.delete().where(links.c.decision_id.in_(decision_ids))).rowcount
    counts['architecture_decisions'] = db.session.execute(
        decisions.delete().where(decisions.c.id.in_(decision_ids))).rowcount
    return counts


def _run_decisions(now, run_id, cap):
    ids = _due_ids(DECISIONS, now, cap)

    affected, errors = 0, []
    for decision_id in ids:
        try:
            # Lock and check again: the decision may have been restored.
            still_due = db.session.query(ArchitectureDecision).filter(
                ArchitectureDecision.id == decision_id, *_decisions_due(now)
            ).with_for_update().populate_existing().first()
            if still_due is None:
                db.session.rollback()
                continue
            record = RetentionErasure(
                run_id=run_id, category=DECISIONS, entity_type='decision', entity_id=decision_id,
                identifier=_decision_identifier(still_due),
            )
            db.session.add(record)
            db.session.flush()
            db.session.expunge(still_due)
            counts = _delete_decisions([decision_id])
            counts.pop('architecture_decisions', None)
            record.counts = counts
            db.session.commit()
            affected += 1
        except Exception as exc:
            db.session.rollback()
            logger.exception('Retention: erasing decision %s failed', decision_id)
            errors.append({'entity_id': decision_id, 'error': _short_error(exc)})
    return affected, errors


# ---------------------------------------------------------------------------
# Tenants
# ---------------------------------------------------------------------------

# What erasing a tenant does to every table. "T" is the tenant, "D" its domain,
# "its users" are the users whose sign-in domain is D and who are not a member
# of any other tenant.
#
#   erase   rows are deleted
#   detach  rows are kept, the link to the tenant or its users is removed
#   scrub   rows are kept, personal fields are emptied
#   keep    not tenant data, never touched
#
# tests/test_retention_tenant_erase.py fails when a table is missing from this
# list, so a new model cannot be added without deciding what happens to it.
TENANT_ERASE_RULES = {
    'tenants': ('erase', 'the row for T, last'),
    'tenant_settings': ('erase', 'rows for T'),
    'tenant_memberships': ('erase', 'rows for T, and any other membership row of its users'),
    'spaces': ('erase', 'rows for T'),
    'decision_spaces': ('erase', "links of T's decisions and of T's spaces"),
    'architecture_decisions': ('erase', 'rows for T, and rows with no tenant id whose domain is D'),
    'decision_history': ('erase', "history of T's decisions"),
    'decision_comments': ('erase', "comments on T's decisions and comments recorded for T"),
    'decision_relationships': ('erase', "rows for T and rows that touch one of T's decisions"),
    'decision_infrastructure': ('erase', "links of T's decisions and of D's infrastructure"),
    'it_infrastructure': ('erase', 'rows whose domain is D'),
    'audit_logs': ('erase', "rows for T (they name T's members); the retention record replaces them"),
    'role_requests': ('erase', 'rows for T and rows made by its users'),
    'access_requests': ('erase', 'rows whose domain is D'),
    'email_verifications': ('erase', 'rows whose domain is D'),
    'sso_configs': ('erase', 'the row for D (holds a client secret)'),
    'email_configs': ('erase', 'the row for D (holds SMTP credentials)'),
    'auth_configs': ('erase', 'the row for D'),
    'slack_workspaces': ('erase', 'the workspace claimed by T (holds an access token)'),
    'slack_user_mappings': ('erase', "mappings of T's workspace; a mapping elsewhere to one of its users is detached"),
    'teams_workspaces': ('erase', 'the workspace connected to T'),
    'teams_user_mappings': ('erase', "mappings of T's workspace; a mapping elsewhere to one of its users is detached"),
    'teams_conversation_references': ('erase', "rows of T's workspace"),
    'ai_api_keys': ('erase', 'keys of T and keys of its users'),
    'ai_interaction_logs': ('erase', 'rows for T; a row elsewhere that used an erased key or user is detached'),
    'users': ('erase', 'its users. A user who is still named by a required column in another '
                       "tenant's records is anonymised instead. A user of D who is a member of "
                       'another tenant is kept untouched'),
    'webauthn_credentials': ('erase', 'credentials of its users'),
    'subscriptions': ('erase', 'rows of its users'),
    'user_consents': ('erase', 'rows of its users'),
    'setup_tokens': ('erase', 'tokens of its users and tokens sent to their email addresses'),
    'login_history': ('erase', 'rows of its users and rows whose tenant domain is D'),
    'inquiries': ('scrub', 'messages from its users lose name, email and message; rows that name D '
                           'lose the domain. The message count and team answers stay until the '
                           '24-month purge'),
    'domain_approvals': ('scrub', 'the row for D keeps its status (so a rejected domain stays '
                                  'rejected) and loses the requester name and email'),
    'master_accounts': ('keep', 'super admin accounts'),
    'system_config': ('keep', 'installation settings'),
    'blog_posts': ('keep', 'website content'),
    'retention_runs': ('keep', 'the record of retention runs'),
    'retention_erasures': ('keep', 'the record of what was erased'),
}


def _tenant_scope(tenant):
    """Selects that define what belongs to a tenant."""
    decisions = ArchitectureDecision.__table__
    domain = tenant.domain.lower()
    decision_ids = sa.select(decisions.c.id).where(sa.or_(
        decisions.c.tenant_id == tenant.id,
        sa.and_(decisions.c.tenant_id.is_(None), sa.func.lower(decisions.c.domain) == domain),
    ))
    space_ids = sa.select(Space.__table__.c.id).where(Space.__table__.c.tenant_id == tenant.id)
    infrastructure_ids = sa.select(ITInfrastructure.__table__.c.id).where(
        sa.func.lower(ITInfrastructure.__table__.c.domain) == domain)
    return domain, decision_ids, space_ids, infrastructure_ids


def _tenant_user_ids(tenant):
    """Ids of the tenant's own users: sign-in domain D, member of no other tenant."""
    memberships = TenantMembership.__table__
    users = User.__table__
    elsewhere = sa.exists().where(
        memberships.c.user_id == users.c.id, memberships.c.tenant_id != tenant.id)
    rows = db.session.execute(
        sa.select(users.c.id).where(sa.func.lower(users.c.sso_domain) == tenant.domain.lower(), ~elsewhere)
        .order_by(users.c.id)
    ).all()
    return [row[0] for row in rows]


def _count(table, *where):
    return db.session.execute(sa.select(sa.func.count()).select_from(table).where(*where)).scalar() or 0


def _tenant_preview_counts(tenant):
    """The main things erasing this tenant would remove. Reads only."""
    _, decision_ids, _, _ = _tenant_scope(tenant)
    return {
        'users': len(_tenant_user_ids(tenant)),
        'decisions': _count(ArchitectureDecision.__table__, ArchitectureDecision.__table__.c.id.in_(decision_ids)),
        'spaces': _count(Space.__table__, Space.__table__.c.tenant_id == tenant.id),
        'memberships': _count(TenantMembership.__table__, TenantMembership.__table__.c.tenant_id == tenant.id),
    }


def _chunks(values, size=500):
    for start in range(0, len(values), size):
        yield values[start:start + size]


def _erase_tenant(tenant, record):
    """Erase one tenant in the current transaction, following TENANT_ERASE_RULES.

    Fills `record.counts` with rows removed per table. Does not commit. Any
    error (for example a foreign key from a table this code does not know)
    propagates so the caller rolls the whole tenant back.
    """
    tenant_id = tenant.id
    domain, decision_ids, space_ids, infrastructure_ids = _tenant_scope(tenant)

    same_domain = Tenant.query.filter(
        sa.func.lower(Tenant.domain) == domain, Tenant.id != tenant_id).count()
    if same_domain:
        raise RuntimeError('Another tenant uses the same domain in a different case; not erased')

    user_ids = _tenant_user_ids(tenant)
    user_emails = [
        (row[0] or '').lower() for chunk in _chunks(user_ids)
        for row in db.session.execute(sa.select(User.__table__.c.email).where(User.__table__.c.id.in_(chunk)))
    ]
    db.session.expunge(tenant)
    counts = {}

    def delete(table, *where):
        name = table.name
        counts[name] = counts.get(name, 0) + db.session.execute(table.delete().where(*where)).rowcount

    def delete_for_users(table, column):
        for chunk in _chunks(user_ids):
            delete(table, column.in_(chunk))

    # Decisions and everything hanging off them
    relationships = DecisionRelationship.__table__
    links = DecisionSpace.__table__
    comments = DecisionComment.__table__
    delete(decision_infrastructure, decision_infrastructure.c.infrastructure_id.in_(infrastructure_ids))
    delete(links, links.c.space_id.in_(space_ids))
    delete(comments, comments.c.tenant_id == tenant_id)
    for name, removed in _delete_decisions(
        decision_ids, extra_relationship_filter=relationships.c.tenant_id == tenant_id
    ).items():
        counts[name] = counts.get(name, 0) + removed
    delete(ITInfrastructure.__table__, sa.func.lower(ITInfrastructure.__table__.c.domain) == domain)
    delete(Space.__table__, Space.__table__.c.tenant_id == tenant_id)

    # AI keys and logs. A log row of another tenant that used an erased key keeps its row.
    ai_keys = AIApiKey.__table__
    ai_logs = AIInteractionLog.__table__
    delete(ai_logs, ai_logs.c.tenant_id == tenant_id)
    key_filters = [ai_keys.c.tenant_id == tenant_id] + [ai_keys.c.user_id.in_(chunk) for chunk in _chunks(user_ids)]
    for key_filter in key_filters:
        db.session.execute(ai_logs.update().where(
            ai_logs.c.api_key_id.in_(sa.select(ai_keys.c.id).where(key_filter))
        ).values(api_key_id=None))
        delete(ai_keys, key_filter)

    # Slack and Teams workspaces
    slack = SlackWorkspace.__table__
    slack_ids = sa.select(slack.c.id).where(slack.c.tenant_id == tenant_id)
    delete(SlackUserMapping.__table__, SlackUserMapping.__table__.c.slack_workspace_id.in_(slack_ids))
    delete(slack, slack.c.tenant_id == tenant_id)
    teams = TeamsWorkspace.__table__
    teams_ids = sa.select(teams.c.id).where(teams.c.tenant_id == tenant_id)
    delete(TeamsUserMapping.__table__, TeamsUserMapping.__table__.c.teams_workspace_id.in_(teams_ids))
    delete(TeamsConversationReference.__table__,
           TeamsConversationReference.__table__.c.teams_workspace_id.in_(teams_ids))
    delete(teams, teams.c.tenant_id == tenant_id)

    # Rows keyed by tenant id
    delete(RoleRequest.__table__, RoleRequest.__table__.c.tenant_id == tenant_id)
    delete(AuditLog.__table__, AuditLog.__table__.c.tenant_id == tenant_id)
    delete(TenantMembership.__table__, TenantMembership.__table__.c.tenant_id == tenant_id)
    delete(TenantSettings.__table__, TenantSettings.__table__.c.tenant_id == tenant_id)

    # Rows keyed by domain
    for model in (SSOConfig, EmailConfig, AuthConfig, AccessRequest, EmailVerification):
        delete(model.__table__, sa.func.lower(model.__table__.c.domain) == domain)
    approvals = DomainApproval.__table__
    counts['domain_approvals_scrubbed'] = db.session.execute(
        approvals.update().where(sa.func.lower(approvals.c.domain) == domain)
        .values(requested_by_email=None, requested_by_name=None)
    ).rowcount
    login_history = LoginHistory.__table__
    delete(login_history, sa.func.lower(login_history.c.tenant_domain) == domain)
    inquiries = Inquiry.__table__
    redaction = {'name': None, 'email': None, 'message': None, 'user_id': None, 'redacted_at': utcnow()}
    scrubbed = 0
    for chunk in _chunks(user_ids):
        scrubbed += db.session.execute(
            inquiries.update().where(inquiries.c.user_id.in_(chunk)).values(**redaction)).rowcount
    for chunk in _chunks([email for email in user_emails if email]):
        scrubbed += db.session.execute(
            inquiries.update().where(sa.func.lower(inquiries.c.email).in_(chunk)).values(**redaction)).rowcount
    db.session.execute(
        inquiries.update().where(sa.func.lower(inquiries.c.tenant_domain) == domain).values(tenant_domain=None))
    counts['inquiries_scrubbed'] = scrubbed

    # The tenant's users
    delete_for_users(WebAuthnCredential.__table__, WebAuthnCredential.__table__.c.user_id)
    delete_for_users(Subscription.__table__, Subscription.__table__.c.user_id)
    delete_for_users(UserConsent.__table__, UserConsent.__table__.c.user_id)
    delete_for_users(SetupToken.__table__, SetupToken.__table__.c.user_id)
    for chunk in _chunks([email for email in user_emails if email]):
        delete(SetupToken.__table__, sa.func.lower(SetupToken.__table__.c.email).in_(chunk))
    delete_for_users(login_history, login_history.c.user_id)
    delete_for_users(RoleRequest.__table__, RoleRequest.__table__.c.user_id)
    delete_for_users(TenantMembership.__table__, TenantMembership.__table__.c.user_id)

    # Any other column that points at one of these users: empty it when it
    # may be empty; when it may not, the user row has to stay (anonymised).
    users = User.__table__
    still_needed = set()
    for table in db.metadata.sorted_tables:
        if table.name == users.name:
            continue
        for column in table.columns:
            if not any(fk.column is users.c.id for fk in column.foreign_keys):
                continue
            for chunk in _chunks(user_ids):
                if column.nullable:
                    db.session.execute(table.update().where(column.in_(chunk)).values({column.name: None}))
                else:
                    still_needed.update(
                        row[0] for row in db.session.execute(sa.select(column).where(column.in_(chunk)).distinct())
                    )

    removable = [user_id for user_id in user_ids if user_id not in still_needed]
    for chunk in _chunks(removable):
        delete(users, users.c.id.in_(chunk))
    for user_id in sorted(still_needed):
        user = db.session.get(User, user_id)
        if user is not None and not user.is_anonymized:
            _anonymise_user_record(user)
    counts['users_anonymised'] = len(still_needed)

    delete(Tenant.__table__, Tenant.__table__.c.id == tenant_id)
    record.counts = {name: number for name, number in counts.items() if number}


def _run_tenants(now, run_id, cap):
    ids = _due_ids(TENANTS, now, cap)

    affected, errors = 0, []
    for tenant_id in ids:
        try:
            # Lock and check again: the tenant may have been restored.
            tenant = Tenant.query.filter(
                Tenant.id == tenant_id, *_tenants_due(now)
            ).with_for_update().populate_existing().first()
            if tenant is None:
                db.session.rollback()
                continue
            record = RetentionErasure(
                run_id=run_id, category=TENANTS, entity_type='tenant', entity_id=tenant_id,
                identifier=tenant.domain,
            )
            db.session.add(record)
            db.session.flush()
            _erase_tenant(tenant, record)
            db.session.commit()
            affected += 1
        except Exception as exc:
            db.session.rollback()
            logger.exception('Retention: erasing tenant %s failed', tenant_id)
            errors.append({'entity_id': tenant_id, 'error': _short_error(exc)})
    return affected, errors


# ---------------------------------------------------------------------------
# Login history and inquiries
# ---------------------------------------------------------------------------

def _delete_older_than(model, category, cutoff, run_id):
    try:
        count = db.session.query(sa.func.count(model.id)).filter(model.created_at < cutoff).scalar() or 0
        if not count:
            db.session.rollback()
            return 0, []
        record = RetentionErasure(
            run_id=run_id, category=category, entity_type=model.__tablename__,
            identifier=f'created before {cutoff.isoformat()}Z',
        )
        db.session.add(record)
        deleted = model.query.filter(model.created_at < cutoff).delete(synchronize_session=False)
        record.counts = {'rows': deleted}
        db.session.commit()
        return deleted, []
    except Exception as exc:
        db.session.rollback()
        logger.exception('Retention: deleting old %s failed', model.__tablename__)
        return 0, [{'entity_id': None, 'error': _short_error(exc)}]


def purge_old_inquiries(now=None):
    """Delete inquiries older than Inquiry.RETENTION_DAYS (24 months). Returns how many."""
    now = due_time(now)
    purged = Inquiry.query.filter(Inquiry.created_at < _inquiries_cutoff(now)).delete(synchronize_session=False)
    if purged:
        db.session.commit()
    return purged


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------

def _run_category(category, now, run_id, cap):
    if category == ACCOUNTS:
        return _run_accounts(now, run_id, cap)
    if category == DECISIONS:
        return _run_decisions(now, run_id, cap)
    if category == TENANTS:
        return _run_tenants(now, run_id, cap)
    if category == LOGIN_HISTORY:
        return _delete_older_than(LoginHistory, LOGIN_HISTORY, _login_history_cutoff(now), run_id)
    return _delete_older_than(Inquiry, INQUIRIES, _inquiries_cutoff(now), run_id)


def run_retention(trigger, categories=None, now=None, release=None, started_by=None, run=None):
    """Run retention for real and record it. Returns the stored run as a dict.

    trigger     RetentionRun.TRIGGER_* : who started it.
    categories  limit the run to these; None means all five.
    release     {category: count}. Categories a super admin runs deliberately:
                the limits and the backlog check are skipped for them and at
                most `count` items (the number the super admin saw) are
                processed. Every other category is subject to the limits.
    run         an already claimed RetentionRun row (the automatic run).

    Each category is isolated. A failure is rolled back, recorded in the run
    and does not stop the categories after it. Inside accounts, decisions and
    tenants each item has its own transaction, so one bad item costs only
    itself and what was done before it stays done and recorded.
    """
    started = time.monotonic()
    wanted = _normalise_categories(categories)
    now = due_time(now)
    release = dict(release or {})

    if run is None:
        run = RetentionRun(trigger=trigger, started_by=started_by, started_at=utcnow(),
                           status=RetentionRun.STATUS_RUNNING)
        db.session.add(run)
    run.categories = wanted
    run.results = {}
    db.session.commit()
    run_id = run.id

    limits = get_limits()
    backlog_days = get_backlog_days()
    results = {}

    def save(status=None, error=None):
        stored = db.session.get(RetentionRun, run_id)
        stored.results = dict(results)
        if status:
            stored.status = status
            stored.finished_at = utcnow()
            stored.duration_ms = int((time.monotonic() - started) * 1000)
        if error:
            stored.error = error
        db.session.commit()
        return stored

    for category in wanted:
        entry = {'status': STATUS_DONE, 'affected': 0, 'waiting': 0, 'limit': limits.get(category),
                 'hold_reason': None, 'errors': []}
        try:
            count, oldest = _waiting(category, now)
            entry['waiting'] = count
            cap = None
            if category in release:
                cap = release[category]
            else:
                entry['hold_reason'] = _hold_reason(category, count, oldest, now, limits, backlog_days)
            db.session.commit()

            if entry['hold_reason']:
                entry['status'] = STATUS_HELD_BACK
                logger.warning(
                    'Retention: %s held back (%s): %s waiting, limit %s. A super admin must run it.',
                    category, entry['hold_reason'], count, limits.get(category))
            elif count:
                affected, errors = _run_category(category, now, run_id, cap)
                entry['affected'] = affected
                entry['errors'] = errors[:MAX_RECORDED_ERRORS]
                entry['error_count'] = len(errors)
                if errors:
                    entry['status'] = STATUS_ERROR
        except Exception as exc:
            db.session.rollback()
            logger.exception('Retention: category %s failed', category)
            entry['status'] = STATUS_ERROR
            entry['errors'] = (entry['errors'] + [{'entity_id': None, 'error': _short_error(exc)}])[:MAX_RECORDED_ERRORS]
            entry['error_count'] = entry.get('error_count', 0) + 1
        results[category] = entry
        try:
            save()
        except Exception:
            db.session.rollback()
            logger.exception('Retention: could not record progress of run %s', run_id)

    statuses = {entry['status'] for entry in results.values()}
    if STATUS_ERROR in statuses:
        final = RetentionRun.STATUS_ERRORS
    elif STATUS_HELD_BACK in statuses:
        final = RetentionRun.STATUS_HELD_BACK
    else:
        final = RetentionRun.STATUS_COMPLETED
    stored = save(status=final)
    logger.info('Retention run %s (%s) finished: %s %s', run_id, stored.trigger, final, {
        category: (entry['status'], entry['affected']) for category, entry in results.items()
    })
    return stored.to_dict()


def legacy_results(run):
    """A run's counts under the keys POST /api/admin/execute-gdpr-tasks has always returned."""
    results = run.get('results') or {}
    return {
        legacy_key: (results.get(category) or {}).get('affected', 0)
        for category, legacy_key in LEGACY_RESULT_KEYS.items()
    }


def held_back(run):
    """{category: {waiting, limit, reason}} for the categories a run held back."""
    return {
        category: {'waiting': entry['waiting'], 'limit': entry.get('limit'), 'reason': entry.get('hold_reason')}
        for category, entry in (run.get('results') or {}).items()
        if entry.get('status') == STATUS_HELD_BACK
    }


def run_errors(run):
    return {
        category: entry.get('errors') or []
        for category, entry in (run.get('results') or {}).items()
        if entry.get('status') == STATUS_ERROR
    }


def check_release(categories, confirm_counts, now=None):
    """Check a super admin's deliberate run before anything is erased.

    Every category must be named and must come with the number of items the
    super admin saw in the preview. If more are waiting now than that number,
    the request is refused so nothing unseen is erased.

    Returns (release, None) or (None, (error message, status code, extra)).
    """
    if not isinstance(categories, list) or not categories:
        return None, ('Choose at least one category to run', 400, {})
    unknown = [c for c in categories if c not in CATEGORIES]
    if unknown:
        return None, (f"Unknown category. Choose from: {', '.join(CATEGORIES)}", 400, {})
    if not isinstance(confirm_counts, dict):
        return None, ('confirm_counts must give the number waiting for every category', 400, {})

    now = due_time(now)
    release, changed = {}, {}
    for category in categories:
        confirmed = _whole_number(confirm_counts.get(category), 10 ** 9)
        if confirmed is None:
            return None, (f'confirm_counts must give the number waiting for {category}', 400, {})
        waiting, _ = _waiting(category, now)
        if waiting > confirmed:
            changed[category] = waiting
        release[category] = confirmed
    if changed:
        return None, (
            'More items are waiting now than when you confirmed. Check the list again.',
            409, {'waiting': changed},
        )
    return release, None


# ---------------------------------------------------------------------------
# Run history
# ---------------------------------------------------------------------------

def mark_interrupted_runs(now=None):
    """Mark runs that never finished as interrupted. Returns how many."""
    now = to_naive_utc(now) or utcnow()
    stale = RetentionRun.query.filter(
        RetentionRun.status == RetentionRun.STATUS_RUNNING,
        RetentionRun.started_at < now - STALE_RUN_AFTER,
    ).all()
    for run in stale:
        run.status = RetentionRun.STATUS_INTERRUPTED
        run.finished_at = now
        run.error = 'The run did not finish. The process that ran it stopped.'
    if stale:
        db.session.commit()
    return len(stale)


def run_in_progress(now=None):
    """A run that is still going (and not stale), or None."""
    now = to_naive_utc(now) or utcnow()
    return RetentionRun.query.filter(
        RetentionRun.status == RetentionRun.STATUS_RUNNING,
        RetentionRun.started_at >= now - STALE_RUN_AFTER,
    ).order_by(RetentionRun.id.desc()).first()


def recent_runs(limit=20):
    runs = RetentionRun.query.order_by(RetentionRun.started_at.desc(), RetentionRun.id.desc()).limit(limit).all()
    return [run.to_dict() for run in runs]


def retention_status(now=None):
    """Everything the super admin page shows."""
    now = to_naive_utc(now) or utcnow()
    mark_interrupted_runs(now)
    settings = get_settings()
    last_automatic = RetentionRun.query.filter_by(trigger=RetentionRun.TRIGGER_AUTOMATIC).order_by(
        RetentionRun.started_at.desc(), RetentionRun.id.desc()).first()
    preview = preview_retention(now)
    active = run_in_progress(now)
    return {
        'settings': settings,
        'automatic': {
            'active': settings['auto_run_active'],
            'disabled_by': (
                'environment' if settings['auto_run_disabled_by_environment']
                else None if settings['auto_run_enabled'] else 'setting'
            ),
            'last_run': last_automatic.to_dict() if last_automatic else None,
        },
        'preview': preview,
        'held_back': [category for category in CATEGORIES if preview[category]['would_hold']],
        'run_in_progress': active.to_dict() if active else None,
        'runs': recent_runs(),
        'categories': list(CATEGORIES),
    }


# ---------------------------------------------------------------------------
# The automatic run
# ---------------------------------------------------------------------------
#
# Trigger: one small daemon thread per gunicorn worker, started on the first
# request that worker serves after the database is ready. Each thread wakes
# every CHECK_INTERVAL_SECONDS and tries to claim "the automatic run of this
# UTC day" by inserting a row with a unique claim key. The database lets
# exactly one insert win, across workers, containers and restarts; every other
# thread sees the unique-key error and goes back to sleep.
#
# Why a thread and not a check inside requests: the work can take seconds
# (erasing a tenant) and must never delay or fail someone's request, and an
# installation that gets no traffic for days must still keep its promises.
# The image's health check requests /api/health every 30 seconds, which is
# enough to start the thread after a restart; from then on it needs no traffic.
#
# Why not start the thread at import: under `gunicorn --preload` threads
# started in the master do not exist in the forked workers, and importing
# app.py in a test, a script or a migration must not start background work.
# The start is tied to the process id, so a forked or replaced worker starts
# its own thread on its next request.
#
# The thread opens its own application context and removes its session after
# every check, so it never shares a session or a connection with a request.
# A worker killed mid-run leaves a row in status "running": it is marked
# interrupted after STALE_RUN_AFTER, and the next day has a new claim key, so
# a crash can never block the following day's run. Every item is erased in its
# own transaction, so an interrupted run leaves nothing half done.

SCHEDULER_THREAD_NAME = 'retention-scheduler'
CHECK_INTERVAL_SECONDS = 15 * 60
FIRST_CHECK_DELAY_SECONDS = 60

_scheduler_lock = threading.Lock()
_scheduler_pid = None
_scheduler_thread = None
_scheduler_stop = None
# Every thread this module started in this process, with the event that stops
# it. A forked worker starts its own thread while the module state it
# inherited still names the parent's; stop_scheduler() must be able to stop
# whatever was started here, not only the one the globals point at.
_scheduler_started = []


def automatic_claim_key(now):
    return f'auto:{now.date().isoformat()}'


def claim_automatic_run(now=None):
    """Claim the automatic run of the UTC day `now` falls in.

    Returns the new RetentionRun, or None when the day is already claimed.
    Atomic on PostgreSQL and SQLite: the unique constraint on claim_key lets
    one INSERT commit and makes every other one fail.
    """
    now = to_naive_utc(now) or utcnow()
    run = RetentionRun(
        claim_key=automatic_claim_key(now), trigger=RetentionRun.TRIGGER_AUTOMATIC,
        status=RetentionRun.STATUS_RUNNING, started_at=utcnow(),
    )
    db.session.add(run)
    try:
        db.session.commit()
    except IntegrityError:
        # Another worker claimed this day first
        db.session.rollback()
        return None
    except SQLAlchemyError as exc:
        # For example SQLite's writer lock timing out. Not claimed; the next
        # check tries again.
        db.session.rollback()
        logger.warning('Retention: could not claim the automatic run: %s', _short_error(exc))
        return None
    return run


def run_automatic_if_due(now=None):
    """Do today's automatic run unless it is off, already claimed or one is running.

    Returns the run as a dict, or None when nothing was done.
    """
    now = to_naive_utc(now) or utcnow()
    if not get_settings()['auto_run_active']:
        db.session.rollback()
        return None
    mark_interrupted_runs(now)
    already = RetentionRun.query.filter_by(claim_key=automatic_claim_key(now)).first()
    if already is not None or run_in_progress(now) is not None:
        db.session.rollback()
        return None
    run = claim_automatic_run(now)
    if run is None:
        return None
    return run_retention(RetentionRun.TRIGGER_AUTOMATIC, now=now, run=run)


def _scheduler_loop(app, stop, interval, first_delay):
    if stop.wait(first_delay):
        return
    while not stop.is_set():
        try:
            with app.app_context():
                try:
                    run_automatic_if_due()
                finally:
                    db.session.remove()
        except Exception:
            # Never let the thread die: tomorrow's run depends on it.
            logger.exception('Retention: the automatic check failed; it will be tried again')
        if stop.wait(interval):
            return


def _testing(app):
    """True under tests, however the app was created.

    PYTEST_CURRENT_TEST is set by pytest in its own process for the length of
    every test and is inherited by child processes a test starts, so an app
    created without the TESTING flag, or in a subprocess whose environment was
    cleaned, still never starts the thread. A thread that outlives its test
    runs retention queries against the shared test database while another
    test is dropping its tables.
    """
    return bool(
        app.config.get('TESTING')
        or os.environ.get('FLASK_ENV') == 'testing'
        or os.environ.get('TESTING', '').lower() in ('1', 'true', 'yes')
        or os.environ.get('PYTEST_CURRENT_TEST')
    )


def scheduler_threads():
    """The retention threads alive in this process."""
    return [thread for thread in threading.enumerate() if thread.name == SCHEDULER_THREAD_NAME]


def ensure_scheduler(app, force=False, interval=None, first_delay=None):
    """Start this process's retention thread if it is not running. Cheap to call.

    Does nothing under tests (unless `force`) or when RETENTION_AUTO_RUN is
    off. Returns the thread, or None when none was started.
    """
    global _scheduler_pid, _scheduler_thread, _scheduler_stop
    pid = os.getpid()
    if _scheduler_pid == pid and _scheduler_thread is not None and _scheduler_thread.is_alive():
        return _scheduler_thread
    if not force and (_testing(app) or auto_run_disabled_by_environment()):
        return None
    with _scheduler_lock:
        if _scheduler_pid == pid and _scheduler_thread is not None and _scheduler_thread.is_alive():
            return _scheduler_thread
        if interval is None:
            interval = CHECK_INTERVAL_SECONDS
        if first_delay is None:
            # Spread the workers out so they do not all ask at the same moment
            first_delay = FIRST_CHECK_DELAY_SECONDS + random.uniform(0, 30)
        stop = threading.Event()
        thread = threading.Thread(
            target=_scheduler_loop, args=(app, stop, interval, first_delay),
            name=SCHEDULER_THREAD_NAME, daemon=True,
        )
        thread.start()
        _scheduler_pid, _scheduler_thread, _scheduler_stop = pid, thread, stop
        _scheduler_started.append((thread, stop))
        logger.info('Retention: automatic run thread started in process %s', pid)
        return thread


def stop_scheduler(timeout=5):
    """Stop every retention thread this process started (tests)."""
    global _scheduler_pid, _scheduler_thread, _scheduler_stop
    with _scheduler_lock:
        started = list(_scheduler_started)
        del _scheduler_started[:]
        _scheduler_pid = _scheduler_thread = _scheduler_stop = None
    for _thread, stop in started:
        stop.set()
    for thread, _stop in started:
        if thread.is_alive():
            thread.join(timeout)
