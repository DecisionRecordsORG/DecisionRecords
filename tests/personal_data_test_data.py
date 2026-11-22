"""
Test data: a person with something in every place the application keeps
personal data, used by the anonymisation scan and the data export tests.

Each person has an unusual first and last name. Their name, email address or
IP address is written to every column that can hold one, and to nothing else:
the text of decisions and comments carries a neutral `key` instead, so a
search for the name finds only the places that name the person.
"""

import json
from datetime import timedelta

import sqlalchemy as sa

from models import (
    db, User, Tenant, TenantMembership, TenantSettings, AuditLog, LoginHistory, Inquiry, UserConsent,
    DomainApproval, WebAuthnCredential, Subscription, ArchitectureDecision, DecisionHistory,
    DecisionComment, AccessRequest, RoleRequest, RequestedRole, SetupToken, EmailVerification,
    SlackWorkspace, SlackUserMapping, TeamsWorkspace, TeamsUserMapping, TeamsConversationReference,
    AIApiKey, AIInteractionLog, AIChannel, AIAction, GlobalRole, MaturityState,
)
from tests.retention_test_data import naive_now


class Person:
    """What was created for one person, and how to recognise them in the database."""

    def __init__(self, user, first, last, key, ip):
        self.user = user
        self.id = user.id
        self.first = first
        self.last = last
        self.key = key
        self.ip = ip
        self.email = user.email
        self.full_name = f'{first} {last}'
        self.aad_object_id = user.aad_object_id

    @property
    def needles(self):
        """Lower-case fragments that appear wherever this person is named."""
        return [self.first.lower(), self.last.lower(), self.ip]


def make_organisation(domain, key):
    """A tenant with an administrator (neutrally named), a Slack and a Teams workspace."""
    tenant = Tenant(domain=domain, name=f'{key} organisation', status='active',
                    maturity_state=MaturityState.BOOTSTRAP)
    db.session.add(tenant)
    db.session.flush()
    admin = User(email=f'administrator@{domain}', sso_domain=domain, auth_type='local', email_verified=True,
                 is_admin=True)
    admin.set_name(first_name='Organisation', last_name='Administrator')
    db.session.add(admin)
    db.session.flush()
    slack = SlackWorkspace(workspace_id=f'T{key}', bot_token_encrypted='token', tenant_id=tenant.id)
    teams = TeamsWorkspace(ms_tenant_id=f'ms-{key}', tenant_id=tenant.id)
    db.session.add_all([
        TenantSettings(tenant_id=tenant.id, tenant_prefix=key[:3].upper()),
        TenantMembership(user_id=admin.id, tenant_id=tenant.id, global_role=GlobalRole.ADMIN),
        slack, teams,
    ])
    db.session.commit()
    return {'tenant': tenant, 'admin': admin, 'slack': slack, 'teams': teams}


def make_person(organisation, first, last, key, ip, *, first_requester=False):
    """A member of `organisation` with a row in every place that holds personal data.

    `key` is a neutral word used for unique values and for the text of the
    person's contributions. `first_requester` also makes them the person who
    asked for the organisation's domain and who answered its team profile.
    """
    tenant = organisation['tenant']
    admin = organisation['admin']
    domain = tenant.domain
    now = naive_now()
    email = f'{first}.{last}@{domain}'.lower()
    shouted = email.upper()  # the same address as some other system wrote it
    full_name = f'{first} {last}'
    aad_object_id = f'aad-{first.lower()}-0001'

    user = User(email=email, sso_domain=domain, auth_type='local', email_verified=True,
                sso_subject=f'idp|{first.lower()}', aad_object_id=aad_object_id)
    user.set_name(first_name=first, last_name=last)
    user.set_password('a-long-test-password')
    db.session.add(user)
    db.session.flush()

    own = ArchitectureDecision(
        title=f'Decision written by {key}', context=f'Context {key}', decision=f'Outcome {key}',
        consequences=f'Consequences {key}', status='accepted', domain=domain, tenant_id=tenant.id,
        decision_number=ArchitectureDecision.query.filter_by(tenant_id=tenant.id).count() + 1,
        created_by_id=user.id, updated_by_id=user.id, owner_id=user.id, owner_email=email)
    db.session.add(own)
    db.session.flush()
    owned_by_address = ArchitectureDecision(
        title=f'Decision owned by {key}', context=f'Owned context {key}', decision=f'Owned outcome {key}',
        consequences=f'Owned consequences {key}', status='proposed', domain=domain, tenant_id=tenant.id,
        decision_number=own.decision_number + 1, created_by_id=admin.id, owner_email=shouted)
    db.session.add(owned_by_address)
    db.session.flush()

    api_key = AIApiKey(user_id=user.id, tenant_id=tenant.id, key_hash=f'keyhash-{key}'.ljust(64, '0'),
                       key_prefix=f'dr_{key}'[:8], name=f"{first}'s laptop key",
                       description=f'Key that {full_name} uses')
    db.session.add(api_key)
    db.session.flush()

    personal_reference = {
        'activityId': '1', 'bot': {'id': '28:bot', 'name': 'Decision Records'}, 'channelId': 'msteams',
        'conversation': {'id': f'a:personal-{first.lower()}', 'conversationType': 'personal'},
        'serviceUrl': 'https://smba.example/emea/',
        'user': {'id': f'29:{key}', 'name': full_name, 'aadObjectId': aad_object_id},
    }
    channel_reference = dict(personal_reference, conversation={'id': f'19:channel-{key}@thread.tacv2'})

    db.session.add_all([
        TenantMembership(user_id=user.id, tenant_id=tenant.id, global_role=GlobalRole.USER),
        WebAuthnCredential(user_id=user.id, credential_id=f'credential-{first.lower()}'.encode(),
                           public_key=f'public-key-{first.lower()}'.encode(), device_name=f"{first}'s phone",
                           transports=json.dumps(['internal', f'hybrid-{first.lower()}'])),
        Subscription(user_id=user.id, notify_on_create=True, notify_on_update=True),
        UserConsent(user_id=user.id, consent_type='analytics', granted=True, granted_at=now, ip_address=ip),
        UserConsent(user_id=user.id, consent_type='ai_processing', granted=False, withdrawn_at=now, ip_address=ip),
        SetupToken(user_id=user.id, email=email, token_hash=f'tokenhash-{first.lower()}-1',
                   expires_at=now + timedelta(days=1)),
        SetupToken(email=shouted, token_hash=f'tokenhash-{first.lower()}-2', expires_at=now + timedelta(days=1)),
        EmailVerification(email=shouted, name=full_name, token=f'verify-{first.lower()}', domain=domain,
                          purpose='access_request', access_request_reason=f'{first} would like to join',
                          expires_at=now + timedelta(days=1)),
        AccessRequest(email=shouted, name=full_name, domain=domain, reason=f'{first} works here',
                      status='rejected', rejection_reason=f'{last} is not on the list',
                      processed_by_id=admin.id, processed_at=now),
        LoginHistory(user_id=user.id, email=email, tenant_domain=domain, login_method='password',
                     ip_address=ip, user_agent=f'{first}Browser/1.0', success=True, created_at=now),
        LoginHistory(email=shouted, tenant_domain=domain, login_method='password', ip_address=ip,
                     user_agent=f'{first}Browser/1.0', success=False, failure_reason='Invalid password',
                     created_at=now),
        Inquiry(source='feedback', name=full_name, email=email, message=f'{first} has a suggestion',
                user_id=user.id, tenant_domain=domain, contact_consent=True, created_at=now),
        Inquiry(source='contact', name=full_name, email=shouted, message=f'{last} asks a question',
                created_at=now),
        DecisionHistory(decision_id=own.id, title='Earlier title', context='c', decision_text='d',
                        status='proposed', consequences='q', change_reason=f'Reworded {key}',
                        changed_by_id=user.id),
        DecisionComment(decision_id=own.id, tenant_id=tenant.id, user_id=user.id, author_display=full_name,
                        body=f'Comment body {key}'),
        DecisionComment(decision_id=owned_by_address.id, tenant_id=tenant.id, user_id=user.id,
                        author_display=email, body=f'Second comment body {key}', deleted_at=now,
                        deleted_by_id=admin.id),
        # Recorded with the address as its only author, as an integration without an account does
        DecisionComment(decision_id=own.id, tenant_id=tenant.id, user_id=None, author_display=shouted,
                        body=f'Comment by address {key}'),
        RoleRequest(user_id=user.id, tenant_id=tenant.id, requested_role=RequestedRole.STEWARD,
                    reason=f'{first} looks after the records', rejection_reason=f'Not yet, {first}',
                    reviewed_by_id=admin.id, reviewed_at=now),
        AuditLog(tenant_id=tenant.id, actor_user_id=user.id, action_type='user_joined', target_entity='user',
                 target_id=user.id, details={'email': email, 'note': f'{full_name} joined',
                                             'history': [{'address': shouted}, 7, None]}),
        AuditLog(tenant_id=tenant.id, actor_user_id=admin.id, action_type='promote_user', target_entity='user',
                 target_id=user.id, details={'promoted': full_name.upper(), 'new_role': 'steward'}),
        AIInteractionLog(channel=AIChannel.MCP, action=AIAction.SEARCH, user_id=user.id, tenant_id=tenant.id,
                         api_key_id=api_key.id, query_text=f'what did {first} decide about hiring',
                         decision_count=1),
        SlackUserMapping(slack_workspace_id=organisation['slack'].id, slack_user_id=f'U{first.upper()}',
                         slack_email=email, user_id=user.id, link_method='auto_email', linked_at=now),
        SlackUserMapping(slack_workspace_id=organisation['slack'].id, slack_user_id=f'W{first.upper()}',
                         slack_email=shouted),
        TeamsUserMapping(teams_workspace_id=organisation['teams'].id, aad_object_id=aad_object_id,
                         aad_user_principal_name=email, aad_email=email, aad_display_name=full_name,
                         user_id=user.id, link_method='auto_email', linked_at=now),
        TeamsConversationReference(teams_workspace_id=organisation['teams'].id,
                                   conversation_id=f'a:personal-{first.lower()}', context_type='personal',
                                   reference_json=json.dumps(personal_reference)),
        TeamsConversationReference(teams_workspace_id=organisation['teams'].id,
                                   conversation_id=f'19:channel-{key}@thread.tacv2', channel_id=f'19:channel-{key}',
                                   team_id=f'team-{key}', context_type='channel',
                                   reference_json=json.dumps(channel_reference)),
    ])

    if first_requester:
        db.session.add(DomainApproval(domain=domain, status='approved', requested_by_email=shouted,
                                      requested_by_name=full_name, auto_approved=True))
        tenant.team_focus = 'Clinical protocols'
        tenant.team_size = None
        tenant.team_profile_answered_by_id = user.id
        tenant.team_profile_answered_at = now

    db.session.commit()
    return Person(user, first, last, key, ip)


# ==================== Searching the whole database ====================

def text_columns(table):
    """Columns that can hold text: strings, text, JSON and binary. Enums hold fixed codes."""
    return [column for column in table.columns
            if isinstance(column.type, (sa.String, sa.Text, sa.JSON, sa.LargeBinary))
            and not isinstance(column.type, sa.Enum)]


def as_text(value):
    if value is None:
        return ''
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).decode('latin-1')
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def find_everywhere(needles):
    """Where any of `needles` occurs: {'table.column': number of rows}.

    Reads every row of every table and looks in every text, JSON and binary
    column, whatever the column is called, so a column added later is searched
    without anyone remembering to list it.
    """
    db.session.rollback()
    found = {}
    for table in db.metadata.sorted_tables:
        columns = text_columns(table)
        if not columns:
            continue
        for row in db.session.execute(sa.select(*columns)).all():
            for column, value in zip(columns, row):
                text = as_text(value).lower()
                if any(needle in text for needle in needles):
                    name = f'{table.name}.{column.name}'
                    found[name] = found.get(name, 0) + 1
    db.session.rollback()
    return found
