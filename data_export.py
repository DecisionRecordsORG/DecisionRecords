"""
The export of one person's personal data (GDPR Art. 20, data portability).

`build_personal_data_export(user)` gathers everything the application holds
about `user` and nothing about anyone else:

* rows are selected by this user's id, or by this user's email address for the
  few tables that are keyed by address;
* a comment thread contributes only this user's comments;
* a decision contributes its own content, never the names or addresses of the
  people who worked on it;
* nothing that lets someone sign in or act is included: no password hash, no
  passkey key material, no API key or its hash, no setup or verification token.

EXPORT_RULES names every column that points at a user and says where its rows
appear in the export, or why they do not. tests/test_personal_data_export.py
fails when a model gains such a column without a rule, so a new place that
holds personal data cannot be added without deciding.
"""

from datetime import datetime, timezone

import sqlalchemy as sa

from models import (
    db, Tenant, TenantMembership, AuditLog, LoginHistory, Inquiry, UserConsent,
    WebAuthnCredential, Subscription, ArchitectureDecision, DecisionHistory, DecisionComment,
    AccessRequest, RoleRequest, SlackUserMapping, TeamsUserMapping, AIApiKey, AIInteractionLog,
)

# Most rows of one kind in an export. The existing sections used 500.
SECTION_LIMIT = 500

# column that references users.id -> the export section its rows appear in,
# or None with the reason they are left out.
EXPORT_RULES = {
    'tenant_memberships.user_id': ('memberships', 'organisations the person belongs to and their role'),
    'architecture_decisions.created_by_id': ('decisions_authored', 'decisions the person wrote'),
    'architecture_decisions.owner_id': ('decisions_owned', 'decisions the person owns'),
    'architecture_decisions.updated_by_id': (None, 'the last editor of a decision; the edits a person made are '
                                                   'listed under decision_changes'),
    'architecture_decisions.deleted_by_id': (None, 'who deleted a decision is in the audit trail'),
    'decision_history.changed_by_id': ('decision_changes', 'changes the person made to decisions'),
    'decision_comments.user_id': ('comments', "the person's own comments"),
    'decision_comments.deleted_by_id': (None, 'who removed a comment; the comment belongs to its author'),
    'decision_relationships.created_by_id': (None, "links between decisions are the organisation's record"),
    'decision_relationships.updated_by_id': (None, "links between decisions are the organisation's record"),
    'decision_relationships.deleted_by_id': (None, "links between decisions are the organisation's record"),
    'decision_spaces.added_by_id': (None, "which space a decision is in is the organisation's record"),
    'spaces.created_by_id': (None, "spaces are the organisation's structure"),
    'it_infrastructure.created_by_id': (None, "infrastructure items are the organisation's record"),
    'audit_logs.actor_user_id': ('audit_trail', 'actions the person performed'),
    'login_history.user_id': ('login_history', "the person's sign-ins"),
    'inquiries.user_id': ('inquiries', 'messages the person sent us while signed in'),
    'user_consents.user_id': ('consents', "the person's consent choices"),
    'webauthn_credentials.user_id': ('passkeys', 'passkey names and dates, without key material'),
    'subscriptions.user_id': ('notification_settings', "the person's email notification choices"),
    'role_requests.user_id': ('role_requests', 'role requests the person made'),
    'role_requests.reviewed_by_id': (None, "a decision on someone else's request"),
    'access_requests.processed_by_id': (None, "a decision on someone else's request"),
    'tenants.team_profile_answered_by_id': ('team_profile_answers', 'team profile answers the person gave'),
    'ai_api_keys.user_id': ('ai_api_keys', 'API key names and dates, without the key or its hash'),
    'ai_interaction_logs.user_id': ('ai_interactions', "the person's AI queries"),
    'slack_user_mappings.user_id': ('linked_accounts', 'the linked Slack account'),
    'teams_user_mappings.user_id': ('linked_accounts', 'the linked Microsoft Teams account'),
    'slack_workspaces.claimed_by_id': (None, "the workspace connection is the organisation's setting"),
    'teams_workspaces.consent_granted_by_id': (None, "the workspace connection is the organisation's setting"),
    'setup_tokens.user_id': (None, 'short-lived sign-in links; they would let someone act as the person'),
}


def _iso(value):
    return value.isoformat() if value else None


def _enum(value):
    return getattr(value, 'value', value)


def _decision_entry(decision, user, with_content):
    entry = {
        'id': decision.id,
        'title': decision.title,
        'status': decision.status,
        'created_at': _iso(decision.created_at),
        'updated_at': _iso(decision.updated_at),
    }
    if with_content:
        # The decision's own text. Shown only for a decision the person can
        # still open: one of their organisation that has not been deleted.
        visible = decision.deleted_at is None and decision.domain == user.sso_domain
        entry.update({
            'decision_number': decision.decision_number,
            'context': decision.context if visible else None,
            'decision': decision.decision if visible else None,
            'consequences': decision.consequences if visible else None,
            'deleted_at': _iso(decision.deleted_at),
        })
    return entry


def build_personal_data_export(user):
    """Everything held about `user`, as a JSON-serialisable dict. Reads only."""
    email_key = (user.email or '').lower()

    export = {
        'export_date': datetime.now(timezone.utc).isoformat(),
        'data_subject': {
            'id': user.id,
            'email': user.email,
            'name': user.get_full_name(),
            'first_name': user.first_name,
            'last_name': user.last_name,
        },
        'profile': {
            'auth_type': user.auth_type,
            'email_verified': user.email_verified,
            'created_at': user.created_at.isoformat(),
            'last_login': _iso(user.last_login),
            'sso_domain': user.sso_domain,
        },
        'decisions_authored': [],
        'memberships': [],
        'audit_trail': [],
        'login_history': [],
        'inquiries': [],
    }

    # ---- Sections the export has always had ----

    for decision in ArchitectureDecision.query.filter_by(created_by_id=user.id).order_by(
            ArchitectureDecision.id).all():
        export['decisions_authored'].append(_decision_entry(decision, user, with_content=True))

    for membership in TenantMembership.query.filter_by(user_id=user.id).all():
        tenant = db.session.get(Tenant, membership.tenant_id)
        export['memberships'].append({
            'tenant_name': tenant.name if tenant else None,
            'tenant_domain': tenant.domain if tenant else None,
            'role': membership.global_role.value,
            'joined_at': _iso(membership.joined_at),
        })

    audit_entries = AuditLog.query.filter_by(actor_user_id=user.id).order_by(
        AuditLog.created_at.desc()).limit(SECTION_LIMIT).all()
    for entry in audit_entries:
        export['audit_trail'].append({
            'action': entry.action_type,
            'target': entry.target_entity,
            'created_at': entry.created_at.isoformat(),
        })

    login_entries = LoginHistory.query.filter_by(user_id=user.id).order_by(
        LoginHistory.created_at.desc()).limit(SECTION_LIMIT).all()
    for entry in login_entries:
        export['login_history'].append({
            'method': entry.login_method,
            'success': entry.success,
            'ip_address': entry.ip_address,
            'created_at': _iso(entry.created_at),
            'user_agent': entry.user_agent,
            'failure_reason': entry.failure_reason,
        })

    sent_inquiries = Inquiry.query.filter_by(user_id=user.id).order_by(
        Inquiry.created_at.desc()).limit(SECTION_LIMIT).all()
    for inquiry in sent_inquiries:
        export['inquiries'].append({
            'source': inquiry.source,
            'name': inquiry.name,
            'email': inquiry.email,
            'organisation': inquiry.organisation,
            'area_of_interest': inquiry.area_of_interest,
            'message': inquiry.message,
            'team_focus': inquiry.team_focus,
            'team_size': inquiry.team_size,
            'contact_consent': inquiry.contact_consent,
            'created_at': _iso(inquiry.created_at),
        })

    # ---- Account ----

    export['account_status'] = {
        'has_password': user.has_password(),
        'deletion_requested_at': _iso(user.deletion_requested_at),
        'deletion_scheduled_at': _iso(user.deletion_scheduled_at),
        'has_seen_admin_onboarding': bool(user.has_seen_admin_onboarding),
    }

    # Passkeys: what the person named them and when they were used. The
    # credential id, the public key and the counter stay out.
    export['passkeys'] = [{
        'device_name': credential.device_name,
        'created_at': _iso(credential.created_at),
        'last_used_at': _iso(credential.last_used_at),
    } for credential in WebAuthnCredential.query.filter_by(user_id=user.id).order_by(
        WebAuthnCredential.id).all()]

    subscription = Subscription.query.filter_by(user_id=user.id).first()
    export['notification_settings'] = {
        'notify_on_create': subscription.notify_on_create,
        'notify_on_update': subscription.notify_on_update,
        'notify_on_status_change': subscription.notify_on_status_change,
        'created_at': _iso(subscription.created_at),
        'updated_at': _iso(subscription.updated_at),
    } if subscription else None

    export['consents'] = [{
        'consent_type': consent.consent_type,
        'granted': consent.granted,
        'granted_at': _iso(consent.granted_at),
        'withdrawn_at': _iso(consent.withdrawn_at),
        'ip_address': consent.ip_address,
        'created_at': _iso(consent.created_at),
        'updated_at': _iso(consent.updated_at),
    } for consent in UserConsent.query.filter_by(user_id=user.id).order_by(UserConsent.id).all()]

    # ---- Contributions ----

    # Only this person's comments: other people's comments on the same decision are theirs.
    # The decision's title is given only for a decision the person can still open.
    comments = db.session.query(DecisionComment, ArchitectureDecision.title).outerjoin(
        ArchitectureDecision, sa.and_(
            ArchitectureDecision.id == DecisionComment.decision_id,
            ArchitectureDecision.deleted_at.is_(None),
            ArchitectureDecision.domain == user.sso_domain,
        )
    ).filter(DecisionComment.user_id == user.id).order_by(
        DecisionComment.created_at.desc(), DecisionComment.id.desc()).limit(SECTION_LIMIT).all()
    export['comments'] = [{
        'id': comment.id,
        'decision_id': comment.decision_id,
        'decision_title': title,
        'body': comment.body,
        'created_at': _iso(comment.created_at),
        'updated_at': _iso(comment.updated_at),
        'deleted_at': _iso(comment.deleted_at),
    } for comment, title in comments]

    # Owned by account, or named as owner by address within the person's own
    # organisation. A decision of another organisation that names this address
    # as an outside owner is that organisation's record and stays out.
    owner_filter = ArchitectureDecision.owner_id == user.id
    if email_key:
        owner_filter = sa.or_(owner_filter, sa.and_(
            sa.func.lower(ArchitectureDecision.owner_email) == email_key,
            ArchitectureDecision.domain == user.sso_domain,
        ))
    export['decisions_owned'] = [
        _decision_entry(decision, user, with_content=True)
        for decision in ArchitectureDecision.query.filter(owner_filter).order_by(ArchitectureDecision.id).all()
    ]

    changes = DecisionHistory.query.filter_by(changed_by_id=user.id).order_by(
        DecisionHistory.changed_at.desc(), DecisionHistory.id.desc()).limit(SECTION_LIMIT).all()
    export['decision_changes'] = [{
        'decision_id': change.decision_id,
        'changed_at': _iso(change.changed_at),
        'change_reason': change.change_reason,
    } for change in changes]

    # ---- Requests ----

    export['role_requests'] = [{
        'requested_role': _enum(role_request.requested_role),
        'reason': role_request.reason,
        'status': _enum(role_request.status),
        'created_at': _iso(role_request.created_at),
        'reviewed_at': _iso(role_request.reviewed_at),
        'rejection_reason': role_request.rejection_reason,
    } for role_request in RoleRequest.query.filter_by(user_id=user.id).order_by(RoleRequest.id).all()]

    # Access requests carry an address, not a user id
    access_requests = AccessRequest.query.filter(
        sa.func.lower(AccessRequest.email) == email_key).order_by(AccessRequest.id).all() if email_key else []
    export['access_requests'] = [{
        'name': access_request.name,
        'email': access_request.email,
        'domain': access_request.domain,
        'reason': access_request.reason,
        'status': access_request.status,
        'created_at': _iso(access_request.created_at),
        'processed_at': _iso(access_request.processed_at),
        'rejection_reason': access_request.rejection_reason,
    } for access_request in access_requests]

    export['team_profile_answers'] = [{
        'tenant_domain': tenant.domain,
        'team_focus': tenant.team_focus,
        'team_size': tenant.team_size,
        'answered_at': _iso(tenant.team_profile_answered_at),
    } for tenant in Tenant.query.filter_by(team_profile_answered_by_id=user.id).order_by(Tenant.id).all()]

    # ---- Integrations ----

    # API keys: the name and dates the person sees in the app. Never the key or its hash.
    export['ai_api_keys'] = [{
        'name': key.name,
        'description': key.description,
        'key_prefix': key.key_prefix,
        'scopes': key.scopes,
        'created_at': _iso(key.created_at),
        'last_used_at': _iso(key.last_used_at),
        'expires_at': _iso(key.expires_at),
        'revoked_at': _iso(key.revoked_at),
    } for key in AIApiKey.query.filter_by(user_id=user.id).order_by(AIApiKey.id).all()]

    interactions = AIInteractionLog.query.filter_by(user_id=user.id).order_by(
        AIInteractionLog.created_at.desc(), AIInteractionLog.id.desc()).limit(SECTION_LIMIT).all()
    export['ai_interactions'] = [{
        'channel': _enum(interaction.channel),
        'action': _enum(interaction.action),
        'query_text': interaction.query_text,
        'decision_count': interaction.decision_count,
        'success': interaction.success,
        'created_at': _iso(interaction.created_at),
    } for interaction in interactions]

    linked = []
    for mapping in SlackUserMapping.query.filter_by(user_id=user.id).order_by(SlackUserMapping.id).all():
        linked.append({
            'service': 'slack',
            'account_id': mapping.slack_user_id,
            'email': mapping.slack_email,
            'display_name': None,
            'link_method': mapping.link_method,
            'linked_at': _iso(mapping.linked_at),
        })
    for mapping in TeamsUserMapping.query.filter_by(user_id=user.id).order_by(TeamsUserMapping.id).all():
        linked.append({
            'service': 'teams',
            'account_id': mapping.aad_object_id,
            'email': mapping.aad_email or mapping.aad_user_principal_name,
            'display_name': mapping.aad_display_name,
            'link_method': mapping.link_method,
            'linked_at': _iso(mapping.linked_at),
        })
    export['linked_accounts'] = linked

    return export
