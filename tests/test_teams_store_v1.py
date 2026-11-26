"""
The Teams app as it is submitted to the Teams store (version 1).

What is covered here, each through the real routes of the real app:

- organisations are keyed on the Microsoft tenant ID, so a tenant that only
  has an `onmicrosoft.com` domain can use the app, and no Microsoft tenant
  lands in another's organisation
- guests, personal accounts and accounts of other organisations are refused
- the audience and scope a Teams single sign-on token must carry
- the bot answers every message, sends its welcome once and forgets a
  conversation when the app is removed
- the links in cards and in the tab's answers exist in the web app
- "Connect Teams" takes the Microsoft tenant from a verified sign-in (S6)
- the web sign-ins identify people by sign-in name, not the email claim (S7)
- the sign-in window the tab falls back to
- only the Teams tab pages may be framed by Microsoft Teams
- the manifest and the package

Teams sign-in tokens are signed with a key generated in the test run (see
tests/test_teams_tab_auth.py, whose helpers are used here). Nothing leaves
the machine: replies the bot would send to Microsoft are captured.
"""
import json
import os
import re
import sys
import time
import zipfile
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    db, User, Tenant, TenantMembership, Space, ArchitectureDecision, AuthConfig,
    GlobalRole, SystemConfig, TeamsWorkspace, TeamsUserMapping, TeamsConversationReference
)
from tests.test_teams_tab_auth import (  # noqa: F401  (real_app and client are fixtures)
    real_app, client, sso_token, sso_claims, make_org, make_decision, sign_in, tab_headers,
    row_counts, APP_ID, MS_TENANT_A, MS_TENANT_B, MS_TENANT_UNKNOWN, DOMAIN_A, DOMAIN_B, ALICE, BOB,
    APP_HOST, SITE_HOST, EE_TESTS_ENABLED,
)

pytestmark = pytest.mark.skipif(
    not EE_TESTS_ENABLED,
    reason="Enterprise Edition tests require DECISION_RECORDS_EDITION=enterprise and EE modules",
)

if EE_TESTS_ENABLED:
    import microsoft_identity
    from ee.backend.teams import teams_security, teams_cards
    from ee.backend.teams.teams_service import TeamsService

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEAMS_APP_DIR = os.path.join(REPO_ROOT, 'ee', 'teams-app')

MS_TENANT_REVIEW = 'dddddddd-0000-4000-8000-000000000004'
REVIEW_DOMAIN = 'reviewlab.onmicrosoft.com'
REVIEW_ADMIN = f'admin@{REVIEW_DOMAIN}'
REVIEW_MEMBER = f'megan@{REVIEW_DOMAIN}'
SERVICE_URL = 'https://smba.trafficmanager.net/emea/'


def oid(n):
    return f'00000000-0000-4000-8000-{n:012d}'


def role_of(email):
    user = User.query.filter_by(email=email).first()
    membership = TenantMembership.query.filter_by(user_id=user.id).first()
    return membership.global_role


def body_of(response):
    return response.get_json(silent=True) or {}


# ============================================================================
# A3. ORGANISATIONS ARE KEYED ON THE MICROSOFT TENANT ID
# ============================================================================

class TestOnmicrosoftTenantGetsAnOrganisation:
    """Store reviewers use tenants that have only an onmicrosoft.com domain."""

    def test_first_person_creates_the_organisation_and_administers_it(self, client, real_app):
        response = sign_in(client, sso_token(REVIEW_ADMIN, tid=MS_TENANT_REVIEW, oid=oid(1)))

        assert response.status_code == 200, response.get_data(as_text=True)
        body = response.get_json()
        assert body['tenant_domain'] == REVIEW_DOMAIN
        assert body['user']['email'] == REVIEW_ADMIN
        tenant = Tenant.query.filter_by(domain=REVIEW_DOMAIN).one()
        assert tenant.name == 'Reviewlab'
        assert role_of(REVIEW_ADMIN) == GlobalRole.PROVISIONAL_ADMIN
        assert User.query.filter_by(email=REVIEW_ADMIN).one().is_admin is True
        # The Microsoft tenant is now linked to the organisation
        workspace = TeamsWorkspace.query.filter_by(ms_tenant_id=MS_TENANT_REVIEW).one()
        assert workspace.tenant_id == tenant.id and workspace.is_active
        # Set up like every new organisation: sign-in options and a default space
        assert AuthConfig.query.filter_by(domain=REVIEW_DOMAIN).count() == 1
        assert Space.query.filter_by(tenant_id=tenant.id, is_default=True).count() == 1

    def test_second_person_joins_the_same_organisation_as_a_member(self, client, real_app):
        sign_in(client, sso_token(REVIEW_ADMIN, tid=MS_TENANT_REVIEW, oid=oid(1)))

        response = sign_in(client, sso_token(REVIEW_MEMBER, tid=MS_TENANT_REVIEW, oid=oid(2)))

        assert response.status_code == 200, response.get_data(as_text=True)
        assert response.get_json()['tenant_domain'] == REVIEW_DOMAIN
        assert Tenant.query.count() == 1
        assert role_of(REVIEW_MEMBER) == GlobalRole.USER
        assert not User.query.filter_by(email=REVIEW_MEMBER).one().is_admin

    def test_the_new_account_can_use_the_tab_straight_away(self, client, real_app):
        token = sign_in(client, sso_token(REVIEW_ADMIN, tid=MS_TENANT_REVIEW, oid=oid(1))).get_json()['tab_auth_token']

        created = client.post('/api/teams/tab/decisions', headers=tab_headers(token),
                              json={'title': 'Review the supplier list each quarter'})
        listing = client.get('/api/teams/tab/decisions', headers=tab_headers(token))

        assert created.status_code == 201, created.get_data(as_text=True)
        assert [d['title'] for d in listing.get_json()] == ['Review the supplier list each quarter']

    def test_the_bare_onmicrosoft_domain_is_not_an_organisation(self, client, real_app):
        response = sign_in(client, sso_token('someone@onmicrosoft.com', tid=MS_TENANT_REVIEW, oid=oid(1)))

        assert response.status_code == 403
        assert Tenant.query.count() == 0 and User.query.count() == 0


class TestTheMicrosoftTenantDecidesTheOrganisation:

    def test_a_second_domain_of_the_same_microsoft_tenant_joins_the_same_organisation(self, client, real_app):
        """A Microsoft tenant can have several domains; its people belong together."""
        sign_in(client, sso_token(REVIEW_ADMIN, tid=MS_TENANT_REVIEW, oid=oid(1)))

        response = sign_in(client, sso_token('kim@reviewlab.example', tid=MS_TENANT_REVIEW, oid=oid(3)))

        assert response.status_code == 200, response.get_data(as_text=True)
        assert response.get_json()['tenant_domain'] == REVIEW_DOMAIN
        assert Tenant.query.count() == 1
        assert User.query.filter_by(email='kim@reviewlab.example').one().sso_domain == REVIEW_DOMAIN

    def test_another_microsoft_tenant_cannot_enter_by_naming_the_same_domain(self, client, real_app):
        sign_in(client, sso_token(REVIEW_ADMIN, tid=MS_TENANT_REVIEW, oid=oid(1)))
        before = row_counts()

        response = sign_in(client, sso_token(f'mallory@{REVIEW_DOMAIN}', tid=MS_TENANT_UNKNOWN, oid=oid(9)))

        assert response.status_code == 403, response.get_data(as_text=True)
        assert body_of(response)['code'] == 'other_microsoft_tenant'
        assert 'tab_auth_token' not in body_of(response)
        assert row_counts() == before

    def test_a_name_on_another_organisations_domain_gets_no_account_anywhere(self, client, real_app):
        """Tenant B's token naming an address of organisation A's domain creates nothing."""
        make_org(DOMAIN_A, MS_TENANT_A, members=[ALICE])
        make_org(DOMAIN_B, MS_TENANT_B, members=[BOB])
        before = row_counts()

        response = sign_in(client, sso_token(f'ceo@{DOMAIN_A}', tid=MS_TENANT_B, oid=oid(9)))

        assert response.status_code == 403
        assert row_counts() == before
        assert User.query.filter_by(email=f'ceo@{DOMAIN_A}').first() is None

    def test_an_existing_organisation_of_the_same_domain_is_joined_as_a_member(self, client, real_app):
        """The organisation signed up on the web; its Microsoft tenant is linked at the first Teams sign-in."""
        tenant = make_org(DOMAIN_A, members=[ALICE])
        assert TeamsWorkspace.query.count() == 0

        response = sign_in(client, sso_token(f'newhire@{DOMAIN_A}', tid=MS_TENANT_A, oid=oid(4)))

        assert response.status_code == 200, response.get_data(as_text=True)
        assert response.get_json()['tenant_domain'] == DOMAIN_A
        assert role_of(f'newhire@{DOMAIN_A}') == GlobalRole.USER
        assert not User.query.filter_by(email=f'newhire@{DOMAIN_A}').one().is_admin
        assert TeamsWorkspace.query.filter_by(ms_tenant_id=MS_TENANT_A).one().tenant_id == tenant.id

    def test_once_linked_the_organisation_refuses_every_other_microsoft_tenant(self, client, real_app):
        make_org(DOMAIN_A, members=[ALICE])
        sign_in(client, sso_token(f'newhire@{DOMAIN_A}', tid=MS_TENANT_A, oid=oid(4)))

        response = sign_in(client, sso_token(f'intruder@{DOMAIN_A}', tid=MS_TENANT_B, oid=oid(5)))

        assert response.status_code == 403
        assert User.query.filter_by(email=f'intruder@{DOMAIN_A}').first() is None

    def test_an_account_of_another_organisation_is_not_moved(self, client, real_app):
        """The address already has an account elsewhere: it stays there, and no token is issued."""
        make_org(DOMAIN_B, members=[f'kim@{DOMAIN_B}'])
        sign_in(client, sso_token(REVIEW_ADMIN, tid=MS_TENANT_REVIEW, oid=oid(1)))
        # The address's own organisation disappears from the picture only if it has no tenant row:
        # here it has one, so the name is refused before the account is looked at
        response = sign_in(client, sso_token(f'kim@{DOMAIN_B}', tid=MS_TENANT_REVIEW, oid=oid(6)))

        assert response.status_code == 403
        assert User.query.filter_by(email=f'kim@{DOMAIN_B}').one().sso_domain == DOMAIN_B

    def test_an_account_left_over_in_another_organisation_is_refused_with_its_reason(self, client, real_app):
        sign_in(client, sso_token(REVIEW_ADMIN, tid=MS_TENANT_REVIEW, oid=oid(1)))
        stray = User(email='kim@reviewlab.example', sso_domain='elsewhere.example', auth_type='local')
        db.session.add(stray)
        db.session.commit()

        response = sign_in(client, sso_token('kim@reviewlab.example', tid=MS_TENANT_REVIEW, oid=oid(6)))

        assert response.status_code == 403
        assert body_of(response)['code'] == 'account_in_other_organisation'
        assert User.query.filter_by(email='kim@reviewlab.example').one().sso_domain == 'elsewhere.example'

    def test_a_renamed_person_keeps_their_account(self, client, real_app):
        first = sign_in(client, sso_token(REVIEW_MEMBER, tid=MS_TENANT_REVIEW, oid=oid(2))).get_json()

        renamed = sign_in(client, sso_token(f'megan.bowen@{REVIEW_DOMAIN}', tid=MS_TENANT_REVIEW, oid=oid(2)))

        assert renamed.status_code == 200
        assert renamed.get_json()['user']['id'] == first['user']['id']
        assert User.query.count() == 1

    def test_the_same_object_id_in_another_microsoft_tenant_is_another_person(self, client, real_app):
        make_org(DOMAIN_A, MS_TENANT_A, members=[])
        make_org(DOMAIN_B, MS_TENANT_B, members=[])
        a = sign_in(client, sso_token(f'pat@{DOMAIN_A}', tid=MS_TENANT_A, oid=oid(7))).get_json()
        b = sign_in(client, sso_token(f'pat@{DOMAIN_B}', tid=MS_TENANT_B, oid=oid(7))).get_json()

        assert a['user']['id'] != b['user']['id']
        assert (a['tenant_domain'], b['tenant_domain']) == (DOMAIN_A, DOMAIN_B)

    def test_user_limit_holds(self, client, real_app):
        sign_in(client, sso_token(REVIEW_ADMIN, tid=MS_TENANT_REVIEW, oid=oid(1)))
        SystemConfig.set(SystemConfig.KEY_MAX_USERS_PER_TENANT, 1)
        before = row_counts()

        response = sign_in(client, sso_token(REVIEW_MEMBER, tid=MS_TENANT_REVIEW, oid=oid(2)))

        assert response.status_code == 403
        assert body_of(response)['code'] == 'user_limit'
        assert body_of(response)['error'] == 'User limit reached'
        assert row_counts() == before
        # The person already in the organisation still signs in
        assert sign_in(client, sso_token(REVIEW_ADMIN, tid=MS_TENANT_REVIEW, oid=oid(1))).status_code == 200

    def test_a_disconnected_microsoft_tenant_cannot_sign_in(self, client, real_app):
        sign_in(client, sso_token(REVIEW_ADMIN, tid=MS_TENANT_REVIEW, oid=oid(1)))
        workspace = TeamsWorkspace.query.one()
        workspace.is_active, workspace.status, workspace.tenant_id = False, TeamsWorkspace.STATUS_DISCONNECTED, None
        db.session.commit()

        response = sign_in(client, sso_token(REVIEW_ADMIN, tid=MS_TENANT_REVIEW, oid=oid(1)))

        assert response.status_code == 403
        assert body_of(response)['code'] == 'teams_disconnected'
        assert TeamsWorkspace.query.one().tenant_id is None


class TestWhoIsRefused:

    @pytest.mark.parametrize('claims', [
        {'idp': f'https://sts.windows.net/{MS_TENANT_B}/'},
        {'idp': 'live.com'},
        {'acct': 1},
    ], ids=['home tenant is another tenant', 'personal account invited as guest', 'acct says guest'])
    def test_guests_are_refused_and_link_nothing(self, client, real_app, claims):
        """A guest's token names the tenant they visit and their home address."""
        make_org(DOMAIN_A, members=[ALICE])
        before = row_counts()

        response = sign_in(client, sso_token(ALICE, tid=MS_TENANT_UNKNOWN, oid=oid(8), **claims))

        assert response.status_code == 403, response.get_data(as_text=True)
        assert body_of(response)['code'] == 'guest_account'
        assert row_counts() == before
        assert TeamsWorkspace.query.count() == 0

    def test_a_guest_user_principal_name_is_refused(self, client, real_app):
        response = sign_in(client, sso_token(
            None, tid=MS_TENANT_REVIEW, oid=oid(8), upn=f'alice_acme.test#EXT#@{REVIEW_DOMAIN}'))

        assert response.status_code == 403
        assert body_of(response)['code'] == 'guest_account'

    def test_the_identity_provider_claim_of_a_member_is_accepted(self, client, real_app):
        response = sign_in(client, sso_token(
            REVIEW_ADMIN, tid=MS_TENANT_REVIEW, oid=oid(1),
            idp=f'https://login.microsoftonline.com/{MS_TENANT_REVIEW}/v2.0'))

        assert response.status_code == 200

    def test_personal_microsoft_accounts_are_refused(self, client, real_app):
        response = sign_in(client, sso_token(
            'someone@contoso.example', tid=microsoft_identity.PERSONAL_ACCOUNT_TENANT_ID, oid=oid(8)))

        assert response.status_code == 403
        assert body_of(response)['code'] == 'personal_account'
        assert User.query.count() == 0

    def test_the_email_claim_does_not_choose_the_account(self, client, real_app):
        """An administrator of any Microsoft tenant can set a person's mail to any address."""
        make_org(DOMAIN_A, MS_TENANT_A, members=[ALICE])

        response = sign_in(client, sso_token(
            f'mallory@{REVIEW_DOMAIN}', tid=MS_TENANT_REVIEW, oid=oid(9), email=ALICE))

        assert response.status_code == 200
        assert response.get_json()['user']['email'] == f'mallory@{REVIEW_DOMAIN}'
        assert response.get_json()['tenant_domain'] == REVIEW_DOMAIN


# ============================================================================
# A1/A2. AUDIENCE AND SCOPE OF THE SINGLE SIGN-ON TOKEN
# ============================================================================

class TestAudienceAndScope:

    @pytest.mark.parametrize('audience', [
        APP_ID,                                   # requestedAccessTokenVersion 2: always the bare ID
        f'api://{APP_ID}',                        # the Application ID URI Entra has today
        f'api://{SITE_HOST}/{APP_ID}',            # the URI Teams tab single sign-on requires
        f'api://{SITE_HOST}/botid-{APP_ID}',      # Microsoft's form for an app with a bot and a tab
        f'api://{APP_HOST}/{APP_ID}',
    ])
    def test_every_form_microsoft_issues_for_this_application_is_accepted(self, client, real_app, audience):
        response = sign_in(client, sso_token(REVIEW_ADMIN, tid=MS_TENANT_REVIEW, oid=oid(1), aud=audience))

        assert response.status_code == 200, response.get_data(as_text=True)

    @pytest.mark.parametrize('audience', [
        '99999999-0000-4000-8000-000000000000',
        f'api://evil.example/{APP_ID}',
        f'api://{SITE_HOST}.evil.example/{APP_ID}',
        f'api://{SITE_HOST}/99999999-0000-4000-8000-000000000000',
        f'https://{SITE_HOST}/{APP_ID}',
        [APP_ID, '99999999-0000-4000-8000-000000000000'],
    ])
    def test_a_token_for_anything_else_is_refused(self, client, real_app, audience):
        response = sign_in(client, sso_token(REVIEW_ADMIN, tid=MS_TENANT_REVIEW, oid=oid(1), aud=audience))

        assert response.status_code == 401
        assert User.query.count() == 0

    @pytest.mark.parametrize('scope', [None, '', 'User.Read', 'access_as_userx', 123])
    def test_a_token_without_the_scope_teams_requests_is_refused(self, client, real_app, scope):
        """An ID token issued to the application has the same audience and no scope."""
        response = sign_in(client, sso_token(REVIEW_ADMIN, tid=MS_TENANT_REVIEW, oid=oid(1), scp=scope))

        assert response.status_code == 401
        assert User.query.count() == 0

    def test_the_scope_may_be_one_of_several(self, client, real_app):
        response = sign_in(client, sso_token(
            REVIEW_ADMIN, tid=MS_TENANT_REVIEW, oid=oid(1), scp='User.Read access_as_user'))

        assert response.status_code == 200


# ============================================================================
# B1, B5, S8. THE BOT
# ============================================================================

class Bot:
    """Delivers activities to the webhook as Teams would, and keeps what the bot sends back."""

    def __init__(self, client, monkeypatch):
        self.client = client
        self.sent = []
        self.roster = {}
        monkeypatch.setattr(teams_security, 'validate_teams_jwt',
                            lambda header, service_url=None: {'serviceurl': service_url})

        bot = self

        async def send_reply(service, activity, card, as_reply=True):
            bot.sent.append(card)
            return True

        async def get_member_info(service, activity):
            sender = activity.get('from') or {}
            return dict(bot.roster.get(sender.get('aadObjectId'), sender))

        async def no_network(*args, **kwargs):
            raise AssertionError('the bot must not call Microsoft in tests')

        monkeypatch.setattr(TeamsService, 'send_reply', send_reply)
        monkeypatch.setattr(TeamsService, 'update_message', send_reply)
        monkeypatch.setattr(TeamsService, 'get_member_info', get_member_info)
        monkeypatch.setattr(TeamsService, 'get_bot_token', no_network)

    def person(self, object_id, upn, name='Megan Bowen', ms_tenant=MS_TENANT_REVIEW, role='user'):
        self.roster[object_id] = {
            'id': f'29:{object_id}', 'aadObjectId': object_id, 'name': name,
            'userPrincipalName': upn, 'tenantId': ms_tenant, 'userRole': role,
        }
        return object_id

    def activity(self, kind, sender=None, ms_tenant=MS_TENANT_REVIEW, conversation='19:personal-1',
                 conversation_type='personal', **fields):
        body = {
            'type': kind,
            'id': f'activity-{len(self.sent)}-{time.time_ns()}',
            'channelId': 'msteams',
            'serviceUrl': SERVICE_URL,
            'channelData': {'tenant': {'id': ms_tenant}},
            'conversation': {'id': conversation, 'tenantId': ms_tenant, 'conversationType': conversation_type},
            'from': {'id': f'29:{sender}', 'aadObjectId': sender, 'name': 'Megan Bowen'} if sender else {'id': '29:x'},
            'recipient': {'id': f'28:{APP_ID}', 'name': 'Decision Records'},
        }
        body.update(fields)
        return body

    def deliver(self, activity):
        self.sent.clear()
        response = self.client.post('/api/teams/webhook', json=activity,
                                    headers={'Authorization': 'Bearer checked-elsewhere'})
        return response

    def say(self, text, sender, **fields):
        response = self.deliver(self.activity('message', sender=sender, text=text, **fields))
        assert response.status_code == 200, response.get_data(as_text=True)
        assert len(self.sent) == 1, f'{text!r} must get exactly one reply, got {len(self.sent)}'
        return json.dumps(self.sent[0])


@pytest.fixture
def bot(client, real_app, monkeypatch):
    return Bot(client, monkeypatch)


@pytest.fixture
def megan(bot):
    return bot.person(oid(2), REVIEW_MEMBER)


class TestBotAnswersEverything:

    def test_first_message_from_an_unknown_tenant_is_answered_and_sets_the_organisation_up(self, bot, megan):
        """No install event was seen first; the bot still answers."""
        reply = bot.say('help', megan)

        assert 'Messages I understand' in reply
        assert Tenant.query.filter_by(domain=REVIEW_DOMAIN).count() == 1
        assert TeamsWorkspace.query.filter_by(ms_tenant_id=MS_TENANT_REVIEW).one().tenant_id is not None
        assert role_of(REVIEW_MEMBER) == GlobalRole.PROVISIONAL_ADMIN

    @pytest.mark.parametrize('text', [
        'help', 'Help', '/help', 'hi', 'Hello', 'hey', 'create', 'list', 'list accepted', 'search supplier',
        'search', 'view 1', 'view', 'view GYH-001', 'view nonsense', 'asdf qwerty', '???', '', '   ',
        '<at>Decision Records</at> list', 'x' * 5000, '🙂', 'DROP TABLE users;', 'view 99999999999999999999',
    ])
    def test_every_message_gets_one_answer_and_no_error(self, bot, megan, text):
        reply = bot.say(text, megan)

        assert 'Something went wrong' not in reply
        assert 'AdaptiveCard' in reply

    def test_nonsense_gets_the_help_card_with_every_command(self, bot, megan):
        reply = bot.say('florble the wug', megan)

        for command in ('help', 'create', 'list', 'search', 'view'):
            assert f'"title": "{command}' in reply
        assert 'Messages I understand' in reply

    def test_help_and_greeting_do_not_lead_out_of_teams(self, bot, megan):
        for text in ('help', 'hi', 'something else'):
            assert 'Action.OpenUrl' not in bot.say(text, megan)

    def test_commands_work_end_to_end(self, bot, megan):
        bot.say('hi', megan)
        tenant = Tenant.query.filter_by(domain=REVIEW_DOMAIN).one()
        decision = make_decision(tenant, 'Review suppliers every quarter', REVIEW_MEMBER)

        assert 'Review suppliers every quarter' in bot.say('list', megan)
        assert 'Review suppliers every quarter' in bot.say('search suppliers', megan)
        assert 'Review suppliers every quarter' in bot.say('view 1', megan)
        assert 'Review suppliers every quarter' in bot.say('view #1', megan)
        assert 'Not Found' in bot.say('view 7', megan)
        assert 'task/fetch' in bot.say('create', megan)
        assert decision.id

    def test_a_mention_in_a_channel_is_understood(self, bot, megan):
        bot.say('hi', megan)
        make_decision(Tenant.query.one(), 'Channel decision', REVIEW_MEMBER)

        reply = bot.say('<at>Decision Records</at> list', megan, conversation='19:channel-1',
                        conversation_type='channel',
                        entities=[{'type': 'mention', 'text': '<at>Decision Records</at>',
                                   'mentioned': {'id': f'28:{APP_ID}', 'name': 'Decision Records'}}])

        assert 'Channel decision' in reply

    def test_a_failure_while_answering_is_still_answered(self, bot, megan, monkeypatch):
        async def broken(self, args, user, activity):
            raise RuntimeError('database went away')
        monkeypatch.setattr(TeamsService, '_handle_list', broken)

        assert 'Something went wrong' in bot.say('list', megan)

    def test_activities_that_are_not_from_teams_are_acknowledged_and_ignored(self, bot, megan):
        activity = bot.activity('message', sender=megan, text='list', channelId='webchat')

        response = bot.deliver(activity)

        assert response.status_code == 200
        assert bot.sent == [] and TeamsWorkspace.query.count() == 0

    @pytest.mark.parametrize('kind', ['typing', 'messageReaction', 'event', 'somethingNew'])
    def test_other_activity_types_are_acknowledged(self, bot, megan, kind):
        response = bot.deliver(bot.activity(kind, sender=megan))

        assert response.status_code == 200 and bot.sent == []

    def test_a_disconnected_organisation_is_told_so(self, bot, megan):
        bot.say('hi', megan)
        workspace = TeamsWorkspace.query.one()
        workspace.is_active, workspace.status, workspace.tenant_id = False, TeamsWorkspace.STATUS_DISCONNECTED, None
        db.session.commit()

        reply = bot.say('list', megan)

        assert 'disconnected' in reply


class TestBotRefusesWhoTheTabRefuses:

    def test_a_guest_gets_help_but_no_data_and_no_account(self, bot, megan):
        bot.say('hi', megan)
        make_decision(Tenant.query.one(), 'Internal decision', REVIEW_MEMBER)
        guest = bot.person(oid(8), f'gary_fabrikam.example#EXT#@{REVIEW_DOMAIN}', role='guest')
        users_before = User.query.count()

        listing = bot.say('list', guest)
        help_card = bot.say('help', guest)

        assert 'Internal decision' not in listing
        assert 'Guest accounts' in listing
        assert 'Messages I understand' in help_card
        assert User.query.count() == users_before

    def test_a_member_of_another_microsoft_tenant_in_the_conversation_is_refused(self, bot, megan):
        """S8: the roster is Microsoft's record of the member and must name the workspace's tenant."""
        bot.say('hi', megan)
        make_decision(Tenant.query.one(), 'Internal decision', REVIEW_MEMBER)
        visitor = bot.person(oid(9), 'vera@fabrikam.example', ms_tenant=MS_TENANT_B)
        users_before = User.query.count()

        reply = bot.say('list', visitor)

        assert 'Internal decision' not in reply
        assert User.query.count() == users_before
        assert TeamsUserMapping.query.filter_by(aad_object_id=visitor).count() == 0

    def test_a_guest_cannot_create_through_the_message_action(self, bot, megan):
        bot.say('hi', megan)
        guest = bot.person(oid(8), f'gary_fabrikam.example#EXT#@{REVIEW_DOMAIN}', role='guest')

        response = bot.deliver(bot.activity(
            'invoke', sender=guest, name='composeExtension/submitAction',
            value={'data': {'action': 'submit_decision', 'title': 'Sneaked in'}}))

        assert response.status_code == 200
        assert 'Guest accounts' in json.dumps(response.get_json())
        assert ArchitectureDecision.query.count() == 0

    def test_the_user_limit_is_explained(self, bot, megan):
        bot.say('hi', megan)
        SystemConfig.set(SystemConfig.KEY_MAX_USERS_PER_TENANT, 1)
        colleague = bot.person(oid(3), f'alex@{REVIEW_DOMAIN}', name='Alex Wilber')

        reply = bot.say('list', colleague)

        assert 'User Limit Reached' in reply
        assert User.query.count() == 1


class TestWelcomeOnceAndUninstall:

    def install(self, bot, megan, conversation='19:personal-1', **fields):
        return bot.deliver(bot.activity('installationUpdate', sender=megan, action='add',
                                        conversation=conversation, **fields))

    def bot_added(self, bot, megan, conversation='19:personal-1'):
        return bot.deliver(bot.activity(
            'conversationUpdate', sender=megan, conversation=conversation,
            membersAdded=[{'id': f'28:{APP_ID}'}, {'id': f'29:{megan}', 'aadObjectId': megan}]))

    def test_install_sends_the_welcome_message(self, bot, megan):
        response = self.install(bot, megan)

        assert response.status_code == 200
        assert len(bot.sent) == 1
        welcome = json.dumps(bot.sent[0])
        assert 'Welcome to Decision Records' in welcome
        for command in ('help', 'create', 'list', 'search', 'view'):
            assert f'"title": "{command}' in welcome
        assert 'Action.OpenUrl' not in welcome

    def test_both_install_events_together_send_one_welcome(self, bot, megan):
        """Teams sends installationUpdate and a conversationUpdate naming the bot (28:<app ID>)."""
        self.install(bot, megan)
        first = len(bot.sent)
        self.bot_added(bot, megan)
        second = len(bot.sent)

        assert (first, second) == (1, 0)

    def test_the_other_order_also_sends_one_welcome(self, bot, megan):
        self.bot_added(bot, megan)
        first = len(bot.sent)
        self.install(bot, megan)

        assert (first, len(bot.sent)) == (1, 0)

    def test_messages_and_help_never_send_the_welcome_again(self, bot, megan):
        self.install(bot, megan)

        for text in ('help', 'hi', 'list'):
            assert 'Welcome to Decision Records' not in bot.say(text, megan)

    def test_a_member_joining_gets_no_welcome(self, bot, megan):
        self.install(bot, megan)

        bot.deliver(bot.activity('conversationUpdate', sender=megan,
                                 membersAdded=[{'id': '29:someone-else', 'aadObjectId': oid(5)}]))

        assert bot.sent == []

    def test_a_team_install_gets_the_channel_wording(self, bot, megan):
        self.install(bot, megan, conversation='19:general@thread.tacv2', conversation_type='channel',
                     channelData={'tenant': {'id': MS_TENANT_REVIEW}, 'team': {'id': '19:team'},
                                  'channel': {'id': '19:general@thread.tacv2'}})

        assert 'Mention me' in json.dumps(bot.sent[0])
        assert TeamsConversationReference.query.one().context_type == 'channel'

    def test_uninstall_forgets_the_conversation_and_keeps_the_organisations_data(self, bot, megan):
        self.install(bot, megan)
        bot.say('hi', megan)
        make_decision(Tenant.query.one(), 'Kept decision', REVIEW_MEMBER)
        assert TeamsConversationReference.query.count() == 1

        response = bot.deliver(bot.activity('installationUpdate', sender=megan, action='remove'))

        assert response.status_code == 200 and bot.sent == []
        assert TeamsConversationReference.query.count() == 0
        assert ArchitectureDecision.query.count() == 1 and User.query.count() == 1
        assert TeamsWorkspace.query.one().is_active

    def test_reinstalling_sends_the_welcome_again(self, bot, megan):
        self.install(bot, megan)
        bot.deliver(bot.activity('installationUpdate', sender=megan, action='remove'))

        self.install(bot, megan)

        assert len(bot.sent) == 1 and 'Welcome to Decision Records' in json.dumps(bot.sent[0])

    def test_an_upgrade_says_nothing(self, bot, megan):
        self.install(bot, megan)

        bot.deliver(bot.activity('installationUpdate', sender=megan, action='add-upgrade'))

        assert bot.sent == []


# ============================================================================
# B2, B5. LINKS AND WORDING
# ============================================================================

class TestLinksAndWording:

    @pytest.fixture
    def decision(self, real_app):
        tenant = make_org(DOMAIN_A, MS_TENANT_A, members=[ALICE])
        return make_decision(tenant, 'Review suppliers every quarter', ALICE)

    def urls_in(self, card):
        return re.findall(r'"url": "([^"]+)"', json.dumps(card))

    def test_cards_link_to_the_decision_page_of_the_web_app(self, decision):
        expected = f'https://{APP_HOST}/{DOMAIN_A}/decision/{decision.id}'

        assert self.urls_in(teams_cards.build_decision_detail_card(decision)) == [expected]
        assert self.urls_in(teams_cards.build_creation_notification_card(
            decision.id, decision.decision_number, decision.title, decision.status, DOMAIN_A)) == [expected]
        assert self.urls_in(teams_cards.build_decision_list_card([decision])) == [f'https://{APP_HOST}/{DOMAIN_A}']

    def test_the_decision_page_route_exists_in_the_web_app(self):
        routes = open(os.path.join(REPO_ROOT, 'frontend', 'src', 'app', 'app.routes.ts')).read()

        assert "path: ':tenant/decision/:id'" in routes
        assert "path: ':tenant'," in routes

    def test_the_tab_is_given_the_same_address(self, client, decision):
        token = sign_in(client, sso_token(ALICE)).get_json()['tab_auth_token']
        expected = f'https://{APP_HOST}/{DOMAIN_A}/decision/{decision.id}'

        listing = client.get('/api/teams/tab/decisions', headers=tab_headers(token)).get_json()
        detail = client.get(f'/api/teams/tab/decisions/{decision.id}', headers=tab_headers(token)).get_json()

        assert listing[0]['web_url'] == expected and detail['web_url'] == expected

    def test_the_display_id_uses_the_organisations_own_prefix(self, decision):
        db.session.add(AuthConfig(domain=DOMAIN_A, auth_method='local', tenant_prefix='GYH'))
        db.session.commit()

        cards = json.dumps([
            teams_cards.build_decision_detail_card(decision),
            teams_cards.build_decision_list_card([decision]),
            teams_cards.build_success_card('Decision Created', 'Done', decision=decision),
            teams_cards.build_status_change_form_card(decision),
        ])

        assert 'GYH-001' in cards and 'ADR-' not in cards

    def test_no_card_says_architecture_or_promises_notifications_or_account_linking(self, decision):
        cards = json.dumps([
            teams_cards.build_help_card(), teams_cards.build_welcome_card(), teams_cards.build_welcome_card(False),
            teams_cards.build_greeting_card('Megan'), teams_cards.build_create_prompt_card(),
            teams_cards.build_menu_card(), teams_cards.build_create_decision_form_card(),
            teams_cards.build_decision_detail_card(decision), teams_cards.build_decision_list_card([decision]),
        ]).lower()

        for phrase in ('architecture', 'notif', 'link your', 'link my account', 'beta'):
            assert phrase not in cards, phrase
        assert not hasattr(teams_cards, 'build_link_account_card')

    def test_the_confirmation_in_the_conversation_names_who_recorded_it(self, decision):
        card = teams_cards.build_creation_notification_card(
            decision.id, 1, decision.title, 'proposed', DOMAIN_A, display_id='GYH-001', created_by='Megan Bowen')

        assert 'Decision recorded by Megan Bowen' in json.dumps(card) and 'GYH-001' in json.dumps(card)

    def test_bot_commands_in_the_cards_are_the_ones_the_bot_handles_and_the_manifest_lists(self):
        manifest = json.load(open(os.path.join(TEAMS_APP_DIR, 'manifest.json')))
        listed = [c['title'] for c in manifest['bots'][0]['commandLists'][0]['commands']]
        in_cards = [command.split()[0] for command, _ in teams_cards.BOT_COMMANDS]

        assert listed == in_cards == ['help', 'create', 'list', 'search', 'view']


class TestTabApi:

    @pytest.fixture
    def signed_in(self, client, real_app):
        tenant = make_org(DOMAIN_A, MS_TENANT_A, members=[ALICE])
        return tenant, tab_headers(sign_in(client, sso_token(ALICE)).get_json()['tab_auth_token'])

    def test_decisions_can_be_filtered_by_one_of_the_organisations_spaces(self, client, signed_in):
        tenant, headers = signed_in
        other_space = Space(tenant_id=tenant.id, name='Operations')
        db.session.add(other_space)
        db.session.commit()
        client.post('/api/teams/tab/decisions', headers=headers, json={'title': 'In general'})
        client.post('/api/teams/tab/decisions', headers=headers,
                    json={'title': 'In operations', 'space_id': other_space.id})

        everything = client.get('/api/teams/tab/decisions', headers=headers).get_json()
        filtered = client.get(f'/api/teams/tab/decisions?space_id={other_space.id}', headers=headers).get_json()
        unknown = client.get('/api/teams/tab/decisions?space_id=99999', headers=headers).get_json()

        assert sorted(d['title'] for d in everything) == ['In general', 'In operations']
        assert [d['title'] for d in filtered] == ['In operations']
        assert unknown == []

    def test_a_space_of_another_organisation_filters_to_nothing(self, client, signed_in):
        _, headers = signed_in
        other = make_org(DOMAIN_B, MS_TENANT_B, members=[BOB])
        make_decision(other, 'Globex secret', BOB)
        foreign_space = Space.query.filter_by(tenant_id=other.id).first()

        response = client.get(f'/api/teams/tab/decisions?space_id={foreign_space.id}', headers=headers)

        assert response.get_json() == []

    @pytest.mark.parametrize('body,status', [
        ({'title': 'Fine', 'status': 'accepted'}, 201),
        ({'title': 'Fine'}, 201),
        ({'title': 'Bad status', 'status': 'deprecated'}, 400),
        ({'title': 'Bad status', 'status': {'a': 1}}, 400),
        ({'title': 'x' * 256}, 400),
        ({'title': '   '}, 400),
        ({'title': 'Odd fields', 'context': 5, 'decision': None, 'consequences': ['a']}, 201),
    ])
    def test_create_validates_what_it_is_given(self, client, signed_in, body, status):
        _, headers = signed_in

        response = client.post('/api/teams/tab/decisions', headers=headers, json=body)

        assert response.status_code == status, response.get_data(as_text=True)

    def test_spaces_are_listed_with_the_default_marked(self, client, signed_in):
        _, headers = signed_in

        spaces = client.get('/api/teams/tab/spaces', headers=headers).get_json()['spaces']

        assert [s['is_default'] for s in spaces] == [True]


# ============================================================================
# A4. THE SIGN-IN WINDOW
# ============================================================================

def id_claims(username, *, tid=MS_TENANT_REVIEW, object_id=None, audience=APP_ID, **overrides):
    """Claims of an ID token as Microsoft's token endpoint returns it for the app."""
    claims = sso_claims(username, tid=tid, oid=object_id or oid(1), aud=audience)
    claims.pop('scp', None)
    claims.update(overrides)
    return claims


class TestSignInWindow:

    @pytest.fixture
    def exchange(self, monkeypatch):
        """Stands in for the call to Microsoft's token endpoint."""
        calls = []

        def fake(code, redirect_uri):
            calls.append((code, redirect_uri))
            return fake.claims, 'access-token'
        fake.claims = None
        fake.calls = calls
        monkeypatch.setattr(teams_security, 'exchange_teams_oidc_code', fake)
        return fake

    def start(self, client, query=''):
        response = client.get(f'/teams/auth-start{query}')
        assert response.status_code == 302, response.get_data(as_text=True)
        location = urlparse(response.headers['Location'])
        return location, {name: values[0] for name, values in parse_qs(location.query).items()}

    def result_of(self, response):
        page = response.get_data(as_text=True)
        return json.loads(re.search(r'var result = (\{.*?\});\n', page).group(1)), page

    def test_start_goes_to_microsofts_sign_in_page_for_the_tenant_teams_runs_in(self, client, real_app):
        location, query = self.start(client, f'?tid={MS_TENANT_REVIEW}&hint={REVIEW_ADMIN}')

        assert location.netloc == 'login.microsoftonline.com'
        assert location.path == f'/{MS_TENANT_REVIEW}/oauth2/v2.0/authorize'
        assert query['client_id'] == APP_ID and query['response_type'] == 'code'
        assert query['redirect_uri'] == f'https://{SITE_HOST}/teams/auth-end'
        assert query['login_hint'] == REVIEW_ADMIN
        assert set(query['scope'].split()) == {'openid', 'profile'}
        assert teams_security.verify_tab_sign_in_state(query['state'])

    @pytest.mark.parametrize('tid', ['', 'common', '../evil', 'not-a-guid', MS_TENANT_REVIEW + '/x'])
    def test_start_never_puts_anything_but_a_tenant_id_in_the_address(self, client, real_app, tid):
        location, query = self.start(client, f'?tid={tid}&hint=not an address')

        assert location.path == '/organizations/oauth2/v2.0/authorize'
        assert 'login_hint' not in query

    def test_end_signs_the_person_in_and_hands_the_tab_a_working_session(self, client, real_app, exchange):
        _, query = self.start(client)
        exchange.claims = id_claims(REVIEW_ADMIN)

        response = client.get(f"/teams/auth-end?code=abc&state={query['state']}")

        result, page = self.result_of(response)
        assert response.status_code == 200 and result['ok'] is True
        assert result['session']['user']['email'] == REVIEW_ADMIN
        assert result['session']['tenantDomain'] == REVIEW_DOMAIN
        assert 'notifySuccess' in page and '/assets/MicrosoftTeams.min.js' in page
        assert exchange.calls == [('abc', f'https://{SITE_HOST}/teams/auth-end')]
        listing = client.get('/api/teams/tab/decisions', headers=tab_headers(result['session']['tabAuthToken']))
        assert listing.status_code == 200
        assert response.headers['Cache-Control'].startswith('no-')

    @pytest.mark.parametrize('query,code', [
        ('?code=abc', 'invalid_state'),
        ('?code=abc&state=forged', 'invalid_state'),
        ('?error=access_denied&state=x', 'consent_declined'),
        ('?error=server_error', 'microsoft_error'),
    ])
    def test_end_reports_failure_to_the_tab_and_signs_nobody_in(self, client, real_app, exchange, query, code):
        exchange.claims = id_claims(REVIEW_ADMIN)

        result, page = self.result_of(client.get(f'/teams/auth-end{query}'))

        assert result == {'ok': False, 'code': code, 'message': result['message']}
        assert 'notifyFailure' in page
        assert exchange.calls == [] and User.query.count() == 0

    def test_end_needs_a_code(self, client, real_app, exchange):
        _, query = self.start(client)

        result, _ = self.result_of(client.get(f"/teams/auth-end?state={query['state']}"))

        assert result['code'] == 'missing_code' and User.query.count() == 0

    def test_a_state_made_for_another_flow_is_not_accepted(self, client, real_app, exchange):
        exchange.claims = id_claims(REVIEW_ADMIN)
        other_state = teams_security.generate_teams_oidc_state()

        result, _ = self.result_of(client.get(f'/teams/auth-end?code=abc&state={other_state}'))

        assert result['code'] == 'invalid_state' and User.query.count() == 0

    @pytest.mark.parametrize('claims,code', [
        ({'aud': '99999999-0000-4000-8000-000000000000'}, 'invalid_identity'),
        ({'exp': 1}, 'invalid_identity'),
        ({'iss': f'https://login.microsoftonline.com/{MS_TENANT_B}/v2.0'}, 'invalid_identity'),
        ({'idp': 'live.com'}, 'guest_account'),
        ({'oid': None}, 'invalid_identity'),
    ])
    def test_end_applies_the_same_rules_as_single_sign_on(self, client, real_app, exchange, claims, code):
        _, query = self.start(client)
        exchange.claims = id_claims(REVIEW_ADMIN, **claims)

        result, _ = self.result_of(client.get(f"/teams/auth-end?code=abc&state={query['state']}"))

        assert (result['ok'], result['code']) == (False, code)
        assert User.query.count() == 0 and Tenant.query.count() == 0

    def test_a_failed_exchange_signs_nobody_in(self, client, real_app, exchange):
        _, query = self.start(client)

        result, _ = self.result_of(client.get(f"/teams/auth-end?code=abc&state={query['state']}"))

        assert result['code'] == 'microsoft_error'

    def test_what_the_page_embeds_cannot_break_out_of_its_script(self, client, real_app, exchange):
        _, query = self.start(client)
        exchange.claims = id_claims(REVIEW_ADMIN, name='</script><script>alert(1)</script>')

        page = client.get(f"/teams/auth-end?code=abc&state={query['state']}").get_data(as_text=True)

        assert '</script><script>alert(1)' not in page
        assert page.count('<script') == 2


# ============================================================================
# S6. CONNECTING TEAMS FROM THE ORGANISATION SETTINGS
# ============================================================================

class TestConnectTeamsTakesTheTenantFromAVerifiedSignIn:

    @pytest.fixture
    def org(self, real_app):
        tenant = make_org(DOMAIN_A, members=[ALICE])
        admin = User.query.filter_by(email=ALICE).one()
        admin.is_admin = True
        db.session.commit()
        return tenant, admin

    @pytest.fixture
    def exchange(self, monkeypatch):
        calls = []

        def fake(code, redirect_uri):
            calls.append((code, redirect_uri))
            return fake.claims, 'access-token'
        fake.claims = None
        fake.calls = calls
        monkeypatch.setattr(teams_security, 'exchange_teams_oidc_code', fake)
        return fake

    def state_for(self, tenant, admin):
        return teams_security.generate_teams_oauth_state(tenant.id, admin.id)

    def callback(self, client, **query):
        return client.get('/api/teams/oauth/callback', query_string=query)

    def test_a_tenant_id_in_the_query_string_connects_nothing(self, client, org, exchange):
        """What the callback used to trust: ?tenant=<any Microsoft tenant>&admin_consent=True."""
        tenant, admin = org

        response = self.callback(client, tenant=MS_TENANT_B, admin_consent='True',
                                 state=self.state_for(tenant, admin))

        assert response.status_code == 302 and 'teams_error=missing_code' in response.headers['Location']
        assert TeamsWorkspace.query.count() == 0
        assert exchange.calls == []

    def test_the_tenant_comes_from_the_sign_in_whatever_the_query_says(self, client, org, exchange):
        tenant, admin = org
        exchange.claims = id_claims(ALICE, tid=MS_TENANT_A)

        response = self.callback(client, code='abc', tenant=MS_TENANT_B, state=self.state_for(tenant, admin))

        assert 'teams_success=connected' in response.headers['Location']
        workspace = TeamsWorkspace.query.one()
        assert (workspace.ms_tenant_id, workspace.tenant_id) == (MS_TENANT_A, tenant.id)
        assert workspace.status == TeamsWorkspace.STATUS_ACTIVE and workspace.consent_granted_by_id == admin.id
        assert exchange.calls == [('abc', f'https://{SITE_HOST}/api/teams/oauth/callback')]

    def test_a_sign_in_name_on_another_domain_connects_nothing(self, client, org, exchange):
        """An administrator here who is an ordinary member of some other Microsoft tenant."""
        tenant, admin = org
        exchange.claims = id_claims('alice@bigcorp.example', tid=MS_TENANT_B)

        response = self.callback(client, code='abc', state=self.state_for(tenant, admin))

        assert 'teams_error=domain_mismatch' in response.headers['Location']
        assert TeamsWorkspace.query.count() == 0

    @pytest.mark.parametrize('claims,error', [
        ({'idp': f'https://sts.windows.net/{MS_TENANT_B}/'}, 'guest_account'),
        ({'aud': '99999999-0000-4000-8000-000000000000'}, 'invalid_identity'),
        ({'exp': 1}, 'invalid_identity'),
    ])
    def test_guests_and_tokens_for_other_applications_connect_nothing(self, client, org, exchange, claims, error):
        tenant, admin = org
        exchange.claims = id_claims(ALICE, tid=MS_TENANT_A, **claims)

        response = self.callback(client, code='abc', state=self.state_for(tenant, admin))

        assert f'teams_error={error}' in response.headers['Location']
        assert TeamsWorkspace.query.count() == 0

    def test_a_microsoft_tenant_another_organisation_holds_cannot_be_taken(self, client, org, exchange):
        tenant, admin = org
        other = make_org(DOMAIN_B, MS_TENANT_B, members=[BOB])
        exchange.claims = id_claims(ALICE, tid=MS_TENANT_B)

        response = self.callback(client, code='abc', state=self.state_for(tenant, admin))

        assert 'teams_error=workspace_already_claimed' in response.headers['Location']
        assert TeamsWorkspace.query.one().tenant_id == other.id

    def test_a_disconnected_tenant_is_reconnected_only_by_its_own_organisation(self, client, org, exchange):
        tenant, admin = org
        db.session.add(TeamsWorkspace(ms_tenant_id=MS_TENANT_A, is_active=False,
                                      status=TeamsWorkspace.STATUS_DISCONNECTED))
        db.session.commit()
        exchange.claims = id_claims(ALICE, tid=MS_TENANT_A)

        response = self.callback(client, code='abc', state=self.state_for(tenant, admin))

        assert 'teams_success=connected' in response.headers['Location']
        workspace = TeamsWorkspace.query.one()
        assert workspace.tenant_id == tenant.id and workspace.is_active

    def test_the_person_who_started_it_must_still_be_an_administrator(self, client, org, exchange):
        tenant, admin = org
        state = self.state_for(tenant, admin)
        admin.is_admin = False
        db.session.commit()
        exchange.claims = id_claims(ALICE, tid=MS_TENANT_A)

        response = self.callback(client, code='abc', state=state)

        assert 'teams_error=not_allowed' in response.headers['Location']
        assert TeamsWorkspace.query.count() == 0

    def test_a_forged_state_connects_nothing(self, client, org, exchange):
        exchange.claims = id_claims(ALICE, tid=MS_TENANT_A)

        response = self.callback(client, code='abc', state='forged')

        assert 'teams_error=invalid_state' in response.headers['Location']
        assert TeamsWorkspace.query.count() == 0

    def test_start_sends_the_administrator_to_sign_in_not_to_a_consent_page(self, client, org):
        tenant, admin = org
        admin.auth_type = 'sso'   # needs no local credential to use the app
        db.session.commit()
        with client.session_transaction() as session:
            session['user_id'] = admin.id
            session['_expires_at'] = '2999-01-01T00:00:00+00:00'

        response = client.get('/api/teams/oauth/start')

        assert response.status_code == 302, response.get_data(as_text=True)
        location = urlparse(response.headers['Location'])
        query = parse_qs(location.query)
        assert location.path == '/organizations/oauth2/v2.0/authorize'
        assert 'adminconsent' not in response.headers['Location']
        assert query['redirect_uri'] == [f'https://{SITE_HOST}/api/teams/oauth/callback']
        assert query['response_type'] == ['code']


# ============================================================================
# S7. THE WEB SIGN-INS
# ============================================================================

class TestWebSignInsUseTheSignInName:

    def test_sign_in_with_teams_ignores_the_email_claim(self, client, real_app, monkeypatch):
        make_org(DOMAIN_A, MS_TENANT_A, members=[ALICE])
        claims = id_claims(f'mallory@{REVIEW_DOMAIN}', email=ALICE)
        monkeypatch.setattr(teams_security, 'exchange_teams_oidc_code', lambda code, uri: (claims, 'token'))
        monkeypatch.setattr(teams_security, 'get_teams_user_info',
                            lambda token: pytest.fail('the Graph profile must not be read'))
        state = teams_security.generate_teams_oidc_state()

        response = client.get('/auth/teams/oidc/callback', query_string={'code': 'abc', 'state': state})

        assert response.status_code == 302
        assert response.headers['Location'] == f'https://{APP_HOST}/{REVIEW_DOMAIN}'
        with client.session_transaction() as session:
            signed_in = db.session.get(User, session['user_id'])
        assert signed_in.email == f'mallory@{REVIEW_DOMAIN}'
        assert signed_in.sso_domain == REVIEW_DOMAIN

    def test_sign_in_with_teams_refuses_a_token_for_another_application(self, client, real_app, monkeypatch):
        claims = id_claims(REVIEW_ADMIN, audience='99999999-0000-4000-8000-000000000000')
        monkeypatch.setattr(teams_security, 'exchange_teams_oidc_code', lambda code, uri: (claims, 'token'))
        state = teams_security.generate_teams_oidc_state()

        response = client.get('/auth/teams/oidc/callback', query_string={'code': 'abc', 'state': state})

        assert response.headers['Location'] == '/login?error=invalid_identity'
        assert User.query.count() == 0

    def test_sign_in_with_microsoft_ignores_the_mail_field_of_the_profile(self, client, real_app, monkeypatch):
        from ee.backend.oauth_providers import microsoft_oauth
        from tests.test_auth_session_oauth import unsigned_id_token
        make_org(DOMAIN_A, MS_TENANT_A, members=[ALICE])
        monkeypatch.setattr(microsoft_oauth, 'get_microsoft_client_id', lambda: 'web-client-id')
        monkeypatch.setattr(microsoft_oauth, 'get_microsoft_client_secret', lambda: 'web-client-secret')
        state = microsoft_oauth.generate_microsoft_oauth_state()
        claims = id_claims(f'mallory@{REVIEW_DOMAIN}', audience='web-client-id', email=ALICE)

        class TokenResponse:
            ok, status_code = True, 200

            def json(self):
                return {'access_token': 'token', 'id_token': unsigned_id_token(claims)}

        with patch('requests.post', return_value=TokenResponse()), \
                patch('requests.get', side_effect=AssertionError('the Graph profile must not be read')):
            response = client.get('/auth/microsoft/callback', query_string={'code': 'abc', 'state': state})

        assert response.status_code == 302
        assert response.headers['Location'] == f'https://{APP_HOST}/{REVIEW_DOMAIN}', response.headers['Location']
        with client.session_transaction() as session:
            signed_in = db.session.get(User, session['user_id'])
        assert signed_in.email == f'mallory@{REVIEW_DOMAIN}'
        alice = User.query.filter_by(email=ALICE).one()
        assert alice.id != signed_in.id and alice.sso_domain == DOMAIN_A


class TestIdentityRules:
    """microsoft_identity.identity_from_claims on its own."""

    def test_a_member_is_identified_by_tenant_object_and_sign_in_name(self, real_app):
        identity = microsoft_identity.identity_from_claims(id_claims('Megan@ReviewLab.OnMicrosoft.com'))

        assert identity == {
            'object_id': oid(1), 'ms_tenant_id': MS_TENANT_REVIEW, 'email': REVIEW_MEMBER,
            'domain': REVIEW_DOMAIN, 'name': 'Alice Example',
        }

    @pytest.mark.parametrize('claims', [
        None, 'text', {}, {'oid': 'x'}, {'oid': 'x', 'tid': 'not-a-guid'},
    ])
    def test_unusable_claims_are_refused(self, real_app, claims):
        with pytest.raises(microsoft_identity.SignInRefused) as refusal:
            microsoft_identity.identity_from_claims(claims)
        assert refusal.value.code == 'invalid_identity'

    @pytest.mark.parametrize('name', ['', 'no-at-sign', 'two@@signs.example', 'a@b', 'spa ce@x.example', '@x.example'])
    def test_names_that_are_not_addresses_are_refused(self, real_app, name):
        with pytest.raises(microsoft_identity.SignInRefused):
            microsoft_identity.identity_from_claims(id_claims(name))

    def test_the_email_claim_counts_only_when_microsoft_says_its_domain_is_verified(self, real_app):
        claims = id_claims(None, email=REVIEW_MEMBER)
        with pytest.raises(microsoft_identity.SignInRefused):
            microsoft_identity.identity_from_claims(claims)

        assert microsoft_identity.identity_from_claims({**claims, 'xms_edov': True})['email'] == REVIEW_MEMBER

    def test_an_id_token_is_read_without_a_library(self, real_app):
        from tests.test_auth_session_oauth import unsigned_id_token

        assert microsoft_identity.unverified_token_claims(unsigned_id_token({'tid': 'x'})) == {'tid': 'x'}
        for junk in (None, '', 'a.b', 'a.b.c', 'a.!!!.c', 5):
            assert microsoft_identity.unverified_token_claims(junk) is None


# ============================================================================
# B6. FRAMING
# ============================================================================

class TestOnlyTheTeamsPagesMayBeFramedByTeams:

    TEAMS_HOSTS = (
        'https://teams.microsoft.com', 'https://*.teams.microsoft.com', 'https://*.cloud.microsoft',
        'https://*.microsoft365.com', 'https://*.office.com', 'https://outlook.office.com',
        'https://outlook.office365.com', 'https://outlook-sdf.office.com', 'https://outlook-sdf.office365.com',
    )

    def ancestors(self, response):
        policy = response.headers['Content-Security-Policy']
        assert policy.count('frame-ancestors') == 1
        return policy.split('frame-ancestors')[1].split(';')[0].split()

    @pytest.mark.parametrize('path', [
        '/teams/tab', '/teams/decision/5', '/teams/create', '/teams/auth-start', '/teams/auth-end',
    ])
    def test_teams_pages_admit_the_hosts_microsoft_documents_and_nothing_wider(self, client, real_app, path):
        response = client.get(path)

        assert self.ancestors(response) == ["'self'", *self.TEAMS_HOSTS]
        assert 'X-Frame-Options' not in response.headers
        # Never the whole of microsoft.com, which anyone with an Azure-hosted page could be under
        assert 'https://*.microsoft.com' not in response.headers['Content-Security-Policy']

    @pytest.mark.parametrize('path', [
        '/', '/login', '/api/version', '/api/teams/tab/decisions', '/api/teams/sso/validate', '/teamsx/tab',
        '/teams', f'/{DOMAIN_A}/decision/5', '/superadmin', '/auth/teams/oidc', '/settings',
    ])
    def test_every_other_page_can_only_be_framed_by_the_app_itself(self, client, real_app, path):
        response = client.get(path)

        assert self.ancestors(response) == ["'self'"]
        assert response.headers['X-Frame-Options'] == 'SAMEORIGIN'

    @pytest.mark.parametrize('path', ['/oauth/consent', '/oauth/authorize', '/api/oauth/pending'])
    def test_the_consent_pages_still_cannot_be_framed_at_all(self, client, real_app, path):
        response = client.get(path)

        assert self.ancestors(response) == ["'none'"]
        assert response.headers['X-Frame-Options'] == 'DENY'

    def test_the_web_app_does_not_load_the_teams_sdk_on_every_page(self):
        index = open(os.path.join(REPO_ROOT, 'frontend', 'src', 'index.html')).read()

        assert 'MicrosoftTeams' not in index
        assert os.path.isfile(os.path.join(REPO_ROOT, 'frontend', 'src', 'assets', 'MicrosoftTeams.min.js'))


# ============================================================================
# B7. THE MANIFEST AND THE PACKAGE
# ============================================================================

def load_build_package():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'teams_build_package', os.path.join(TEAMS_APP_DIR, 'build_package.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestManifestAndPackage:

    @pytest.fixture(scope='class')
    def package(self):
        return load_build_package()

    @pytest.fixture
    def manifest(self, package):
        return package.load_manifest()

    def test_the_manifest_passes_microsofts_schema_the_store_rules_and_the_icon_checks(self, package):
        assert package.validate() == []

    def test_there_is_one_manifest(self):
        found = []
        for folder, _dirs, files in os.walk(os.path.join(REPO_ROOT, 'ee')):
            if 'node_modules' in folder or '/marketing' in folder or '/.git' in folder:
                continue
            found += [os.path.join(folder, name) for name in files
                      if 'manifest' in name.lower() and name.endswith('.json') and 'teams' in folder.lower()]
        assert found == [os.path.join(TEAMS_APP_DIR, 'manifest.json')]
        assert not os.path.exists(os.path.join(REPO_ROOT, 'ee', 'config', 'teams-app-manifest.json'))

    def test_the_ids_are_the_right_way_round(self, manifest):
        teams_app_id, entra_app_id = 'dba4ee3c-6966-47a2-b55c-04269b7ee4ba', 'a140ddfe-c8cc-4378-9d43-936d619e4423'

        assert manifest['id'] == teams_app_id
        assert manifest['bots'][0]['botId'] == entra_app_id
        assert manifest['composeExtensions'][0]['botId'] == entra_app_id
        assert manifest['webApplicationInfo'] == {
            'id': entra_app_id, 'resource': f'api://decisionrecords.org/{entra_app_id}'}

    def test_version_one_declares_only_what_works(self, manifest):
        assert 'configurableTabs' not in manifest
        tabs = [tab for tab in manifest['staticTabs'] if tab.get('contentUrl')]
        assert [(tab['contentUrl'], tab['scopes']) for tab in tabs] == [
            ('https://decisionrecords.org/teams/tab', ['personal'])]
        text = json.dumps({key: value for key, value in manifest.items() if key != 'bots'}).lower()
        text += json.dumps(manifest['bots'][0]['commandLists']).lower()
        for phrase in ('notif', 'beta', 'terms-of-service', 'dev.decisionrecords'):
            assert phrase not in text, phrase

    def test_links_and_domains(self, manifest):
        assert manifest['developer'] == {
            'name': 'DecisionRecords.org',
            'websiteUrl': 'https://decisionrecords.org',
            'privacyUrl': 'https://decisionrecords.org/privacy',
            'termsOfUseUrl': 'https://decisionrecords.org/terms',
        }
        assert manifest['validDomains'] == ['decisionrecords.org']
        assert 'https://decisionrecords.org/support' in manifest['description']['full']

    def test_the_resource_host_is_one_the_server_accepts_in_production(self, manifest, monkeypatch):
        """Production serves OAuth callbacks and the tab on decisionrecords.org (OAUTH_BASE_URL)."""
        from ee.backend.oauth_providers import microsoft_oauth
        monkeypatch.setenv('APP_BASE_URL', 'https://app.decisionrecords.org')
        monkeypatch.setenv('OAUTH_BASE_URL', 'https://decisionrecords.org')
        entra_app_id = manifest['webApplicationInfo']['id']

        accepted = microsoft_oauth.teams_sso_accepted_audiences(entra_app_id)

        assert manifest['webApplicationInfo']['resource'] in accepted
        assert {entra_app_id, f'api://{entra_app_id}'} <= accepted

    def test_the_validator_catches_what_it_is_there_for(self, package, manifest):
        def problems(change):
            broken = json.loads(json.dumps(manifest))
            change(broken)
            return ' | '.join(package.validate(broken))

        assert 'botId' in problems(lambda m: m['bots'][0].update(botId=m['id']))
        assert 'configurableTabs' in problems(lambda m: m.update(configurableTabs=[]))
        assert 'validDomains' in problems(lambda m: m.update(validDomains=['*.decisionrecords.org']))
        assert 'name' in problems(lambda m: m['name'].update(full='Decision Records Beta'))
        assert 'longer than 80' in problems(lambda m: m['description'].update(short='x' * 81))
        assert 'resource' in problems(lambda m: m['webApplicationInfo'].update(resource=f"api://{m['id']}"))
        assert 'not a property' in problems(lambda m: m.update(packageName='org.decisionrecords'))
        assert 'https' in problems(lambda m: m['developer'].update(privacyUrl='http://decisionrecords.org/privacy'))
        assert 'help' in problems(lambda m: m['bots'][0]['commandLists'][0]['commands'].pop(0))
        assert "'accentColor' is required" in problems(lambda m: m.pop('accentColor'))

    def test_the_package_holds_the_manifest_and_two_icons_and_nothing_else(self, package, tmp_path):
        target = package.build(out_dir=tmp_path)

        with zipfile.ZipFile(target) as built:
            assert sorted(built.namelist()) == ['color-192x192.png', 'manifest.json', 'outline-32x32.png']
            assert json.loads(built.read('manifest.json')) == package.load_manifest()
        again = package.build(out_dir=tmp_path / 'again')
        assert open(target, 'rb').read() == open(again, 'rb').read()

    def test_nothing_stale_is_left_beside_the_manifest(self):
        present = sorted(name for name in os.listdir(TEAMS_APP_DIR) if name not in ('build', '__pycache__'))

        assert present == [
            'README.md', 'TESTING_NOTES.md', 'build_package.py', 'color-192x192.png', 'generate-icons.py',
            'logo-outline-white.svg', 'manifest.json', 'outline-32x32.png', 'schema',
        ]

