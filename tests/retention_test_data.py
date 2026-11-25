"""Test data for the retention tests: a tenant with a row in every table."""

from datetime import datetime, timedelta, timezone

import sqlalchemy as sa

from models import (
    db, User, Tenant, TenantMembership, TenantSettings, Space, DecisionSpace, AuditLog,
    LoginHistory, Inquiry, UserConsent, SSOConfig, EmailConfig, AuthConfig, DomainApproval,
    WebAuthnCredential, Subscription, ITInfrastructure, ArchitectureDecision,
    DecisionRelationship, DecisionHistory, DecisionComment, AccessRequest, RoleRequest,
    RequestedRole, SetupToken, EmailVerification, SlackWorkspace, SlackUserMapping,
    TeamsWorkspace, TeamsUserMapping, TeamsConversationReference, AIApiKey, AIInteractionLog,
    AIChannel, AIAction, GlobalRole, MaturityState, decision_infrastructure,
)


def naive_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def make_user(domain, local, **extra):
    user = User(email=f'{local}@{domain}', sso_domain=domain, auth_type='local', email_verified=True, **extra)
    user.set_name(first_name=local.capitalize(), last_name='Person')
    user.set_password('a-long-test-password')
    db.session.add(user)
    db.session.flush()
    return user


def make_decision(tenant, author, number, title=None, **extra):
    decision = ArchitectureDecision(
        title=title or f'Decision {number} of {tenant.domain}',
        context='Why we needed to decide', decision='What we decided', consequences='What follows',
        status='accepted', domain=tenant.domain, tenant_id=tenant.id, decision_number=number,
        created_by_id=author.id if author else None, updated_by_id=author.id if author else None,
        owner_id=author.id if author else None, owner_email=author.email if author else None,
        **extra,
    )
    db.session.add(decision)
    db.session.flush()
    return decision


def soft_delete(decision, expires_at, by=None, deleted_at=None):
    decision.deleted_at = deleted_at or expires_at - timedelta(days=30)
    decision.deleted_by_id = by.id if by else None
    decision.deletion_expires_at = expires_at


def make_full_tenant(domain, key):
    """A tenant with at least one row in every table that can belong to one.

    `key` keeps unique columns (prefix, tokens, workspace ids) apart between tenants.
    Returns a dict of the main objects.
    """
    now = naive_now()
    tenant = Tenant(domain=domain, name=f'{key} team', status='active', maturity_state=MaturityState.BOOTSTRAP,
                    team_focus='Clinical protocols', team_size=None)
    db.session.add(tenant)
    db.session.flush()

    admin = make_user(domain, 'admin')
    member = make_user(domain, 'member')
    tenant.team_profile_answered_by_id = admin.id
    tenant.team_profile_answered_at = now

    db.session.add_all([
        TenantSettings(tenant_id=tenant.id, tenant_prefix=key[:3].upper()),
        TenantMembership(user_id=admin.id, tenant_id=tenant.id, global_role=GlobalRole.ADMIN),
        TenantMembership(user_id=member.id, tenant_id=tenant.id, global_role=GlobalRole.USER),
        WebAuthnCredential(user_id=member.id, credential_id=f'cred-{key}'.encode(), public_key=b'public-key'),
        Subscription(user_id=member.id),
        UserConsent(user_id=member.id, consent_type='analytics', granted=True, ip_address='203.0.113.9'),
        SetupToken(user_id=member.id, token_hash=f'hash-user-{key}', expires_at=now + timedelta(days=1)),
        SetupToken(email=admin.email, token_hash=f'hash-email-{key}', expires_at=now + timedelta(days=1)),
        LoginHistory(user_id=member.id, email=member.email, tenant_domain=domain, login_method='password',
                     ip_address='203.0.113.9', user_agent='Browser', success=True, created_at=now),
        LoginHistory(email=f'stranger@{domain}', tenant_domain=domain, login_method='password',
                     ip_address='203.0.113.10', success=False, failure_reason='Unknown user', created_at=now),
        SSOConfig(domain=domain, provider_name='IdP', client_id='client', client_secret='secret',
                  discovery_url='https://idp.example/.well-known/openid-configuration'),
        EmailConfig(domain=domain, smtp_server='smtp.example', smtp_username='mailer', smtp_password='secret',
                    from_email=f'noreply@{domain}'),
        AuthConfig(domain=domain, tenant_prefix=key[:3].lower()),
        DomainApproval(domain=domain, status='approved', requested_by_email=admin.email,
                       requested_by_name='Admin Person'),
        AccessRequest(email=f'joiner@{domain}', name='Joiner Person', domain=domain, reason='Please let me in',
                      processed_by_id=admin.id),
        EmailVerification(email=f'joiner@{domain}', token=f'token-{key}', domain=domain,
                          expires_at=now + timedelta(days=1)),
        RoleRequest(user_id=member.id, tenant_id=tenant.id, requested_role=RequestedRole.STEWARD,
                    reason='I look after the records', reviewed_by_id=admin.id),
        AuditLog(tenant_id=tenant.id, actor_user_id=admin.id, action_type='promote_user', target_entity='user',
                 target_id=member.id, details={'email': member.email}),
        Inquiry(source='feedback', name='Member Person', email=member.email, message='A message',
                user_id=member.id, tenant_domain=domain, created_at=now),
        Inquiry(source='contact', name='Admin Person', email=admin.email.upper(), message='Another message',
                created_at=now),
    ])

    space = Space(tenant_id=tenant.id, name='General', is_default=True, created_by_id=admin.id)
    db.session.add(space)
    db.session.flush()

    first = make_decision(tenant, member, 1)
    second = make_decision(tenant, admin, 2)
    infrastructure = ITInfrastructure(name=f'Server {key}', type='server', domain=domain, created_by_id=admin.id)
    db.session.add(infrastructure)
    db.session.flush()
    db.session.add_all([
        DecisionSpace(decision_id=first.id, space_id=space.id, added_by_id=admin.id),
        DecisionHistory(decision_id=first.id, title='Earlier title', context='c', decision_text='d',
                        status='proposed', consequences='q', changed_by_id=member.id),
        DecisionComment(decision_id=first.id, tenant_id=tenant.id, user_id=member.id, body='A comment'),
        DecisionRelationship(tenant_id=tenant.id, source_decision_id=first.id, target_decision_id=second.id,
                             relationship_type='supersedes', created_by_id=admin.id),
    ])
    db.session.execute(decision_infrastructure.insert().values(
        decision_id=first.id, infrastructure_id=infrastructure.id, created_at=now))

    slack = SlackWorkspace(workspace_id=f'T{key}', bot_token_encrypted='token', tenant_id=tenant.id,
                           claimed_by_id=admin.id)
    teams = TeamsWorkspace(ms_tenant_id=f'ms-{key}', tenant_id=tenant.id, consent_granted_by_id=admin.id)
    api_key = AIApiKey(user_id=member.id, tenant_id=tenant.id, key_hash=f'{key:0<64}'[:64],
                       key_prefix=key[:8], name='My key')
    db.session.add_all([slack, teams, api_key])
    db.session.flush()
    add_connected_app(member, tenant, key)
    db.session.add_all([
        SlackUserMapping(slack_workspace_id=slack.id, slack_user_id=f'U{key}', slack_email=member.email,
                         user_id=member.id),
        TeamsUserMapping(teams_workspace_id=teams.id, aad_object_id=f'aad-{key}', aad_email=member.email,
                         user_id=member.id),
        TeamsConversationReference(teams_workspace_id=teams.id, conversation_id=f'conv-{key}',
                                   reference_json='{}', context_type='channel'),
        AIInteractionLog(channel=AIChannel.MCP, action=AIAction.SEARCH, user_id=member.id, tenant_id=tenant.id,
                         api_key_id=api_key.id),
    ])
    db.session.commit()
    return {'tenant': tenant, 'admin': admin, 'member': member, 'space': space,
            'decisions': [first, second], 'slack': slack, 'teams': teams, 'api_key': api_key}


def expire_tenant(tenant, expired_ago=timedelta(hours=1), now=None):
    """Soft-delete a tenant the way DELETE /api/tenants/<domain> does, with the window already over."""
    now = now or naive_now()
    expires_at = now - expired_ago
    deleted_at = expires_at - timedelta(days=30)
    for decision in ArchitectureDecision.query.filter_by(tenant_id=tenant.id).all():
        if not decision.deleted_at:
            decision.deleted_at = deleted_at
            decision.deletion_expires_at = expires_at
    tenant.deleted_at = deleted_at
    tenant.deleted_by_admin = 'superadmin'
    tenant.deletion_expires_at = expires_at
    tenant.status = 'deleted'
    db.session.commit()



def add_connected_app(user, tenant, key):
    """A connected application for `user` in `tenant`: client, grant, an access and a rotated refresh
    token with its successor, and the consent request the grant came from. Nothing names the person."""
    from datetime import datetime, timedelta, timezone
    from models import OAuthClient, OAuthGrant, OAuthAuthorizationRequest, OAuthToken
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    client_id = 'https://client.example/oauth/client.json'
    client = OAuthClient.query.filter_by(client_id=client_id).first()
    if client is None:
        client = OAuthClient(client_id=client_id, client_name='Example Client',
                             client_uri='https://client.example',
                             redirect_uris=['https://client.example/callback'],
                             metadata_fetched_at=now, metadata_expires_at=now + timedelta(hours=1))
        db.session.add(client)
        db.session.flush()
    resource = 'https://decisions.example/api/mcp'
    grant = OAuthGrant(public_id=f'grant-{key}'[:36], user_id=user.id, tenant_id=tenant.id,
                       oauth_client_id=client.id, resource=resource, scopes=['decisions:read'],
                       expires_at=now + timedelta(days=180))
    db.session.add(grant)
    db.session.flush()
    old_refresh = OAuthToken(grant_id=grant.id, kind=OAuthToken.KIND_REFRESH,
                             token_hash=f'oauth-old-{key}'.ljust(64, '0')[:64],
                             expires_at=now + timedelta(days=30), rotated_at=now)
    db.session.add(old_refresh)
    db.session.flush()
    db.session.add_all([
        OAuthToken(grant_id=grant.id, kind=OAuthToken.KIND_REFRESH, parent_id=old_refresh.id,
                   token_hash=f'oauth-new-{key}'.ljust(64, '0')[:64], expires_at=now + timedelta(days=30)),
        OAuthToken(grant_id=grant.id, kind=OAuthToken.KIND_ACCESS, parent_id=old_refresh.id,
                   token_hash=f'oauth-access-{key}'.ljust(64, '0')[:64], expires_at=now + timedelta(hours=1)),
        OAuthAuthorizationRequest(
            public_id=f'request-{key}'[:64], client_identifier=client_id, oauth_client_id=client.id,
            redirect_uri='https://client.example/callback', requested_scopes=['decisions:read'],
            state=f'state-{key}', code_challenge='c' * 43, resource=resource,
            expires_at=now + timedelta(minutes=10), user_id=user.id, tenant_id=tenant.id,
            granted_scopes=['decisions:read'], decision=OAuthAuthorizationRequest.DECISION_APPROVED,
            decided_at=now, code_hash=f'oauth-code-{key}'.ljust(64, '0')[:64],
            code_expires_at=now + timedelta(minutes=2), code_used_at=now, grant_id=grant.id),
        # A consent request still waiting for a decision
        OAuthAuthorizationRequest(
            public_id=f'open-request-{key}'[:64], client_identifier=client_id,
            redirect_uri='https://client.example/callback', requested_scopes=['decisions:read'],
            code_challenge='c' * 43, resource=resource, expires_at=now + timedelta(minutes=10),
            user_id=user.id),
    ])
    db.session.flush()
    return grant


def snapshot(exclude=()):
    """Every row of every table, as {table: [row tuples ordered by primary key]}."""
    db.session.rollback()
    result = {}
    for table in db.metadata.sorted_tables:
        if table.name in exclude:
            continue
        order = list(table.primary_key.columns) or list(table.columns)
        rows = db.session.execute(sa.select(table).order_by(*order)).all()
        result[table.name] = [tuple(row) for row in rows]
    db.session.rollback()
    return result
