"""
The profile page's privacy switches and the correction of one's own name,
through the real application.

    GET/POST /api/user/consents   what each switch says and stores
    PUT      /api/user/profile    a person corrects their own name

and the rule behind "Email notifications": off stops the emails about
decisions (subscriptions and owner assignment); account mail is unaffected.
"""

from unittest.mock import patch

import pytest

import notifications
from auth import get_or_create_user
from models import (
    db, User, Tenant, TenantMembership, GlobalRole, MaturityState, UserConsent, Subscription,
    ArchitectureDecision, DecisionComment, EmailConfig,
)
from tests.app_test_utils import load_test_app

PASSWORD = 'a-long-test-password'
DOMAIN = 'prefs.test'


@pytest.fixture
def api_app():
    app_module, test_app = load_test_app(secret_key='test-secret-key-preferences-12345')
    with test_app.app_context():
        db.create_all()
        app_module.init_database()
        yield test_app
        db.session.remove()
        db.drop_all()
        app_module._db_initialized = False


def make_member(local, first='Pat', last='Member', role=GlobalRole.USER):
    tenant = Tenant.query.filter_by(domain=DOMAIN).first()
    if tenant is None:
        tenant = Tenant(domain=DOMAIN, name='Prefs', status='active', maturity_state=MaturityState.BOOTSTRAP)
        db.session.add(tenant)
        db.session.commit()
    user = User(email=f'{local}@{DOMAIN}', sso_domain=DOMAIN, auth_type='local', email_verified=True)
    user.set_name(first_name=first, last_name=last)
    user.set_password(PASSWORD)
    db.session.add(user)
    db.session.flush()
    db.session.add(TenantMembership(user_id=user.id, tenant_id=tenant.id, global_role=role))
    db.session.commit()
    return user


def sign_in(api_app, user):
    client = api_app.test_client()
    response = client.post('/api/auth/login', json={'email': user.email, 'password': PASSWORD})
    assert response.status_code == 200, response.data
    token = response.headers.get('X-CSRF-Token') or client.get('/api/auth/csrf-token').get_json()['csrf_token']
    client.environ_base['HTTP_X_CSRF_TOKEN'] = token
    return client


@pytest.fixture
def member(api_app):
    return make_member('pat')


@pytest.fixture
def client(api_app, member):
    return sign_in(api_app, member)


class TestSwitchDefaults:

    def test_a_person_who_never_touched_the_switches(self, client):
        consents = client.get('/api/user/consents').get_json()

        assert consents['analytics']['granted'] is False
        assert consents['ai_processing']['granted'] is False
        # Notifications are only ever sent for what the person subscribed to;
        # the switch stops them, it does not have to be turned on first
        assert consents['email_notifications']['granted'] is True
        # No stored choice: the browser can tell "never answered" from "answered"
        assert 'updated_at' not in consents['analytics']

    def test_a_stored_choice_replaces_the_default(self, client, member):
        assert client.post('/api/user/consents', json={
            'consent_type': 'email_notifications', 'granted': False}).status_code == 200
        assert client.post('/api/user/consents', json={
            'consent_type': 'analytics', 'granted': True}).status_code == 200

        consents = client.get('/api/user/consents').get_json()

        assert consents['email_notifications']['granted'] is False
        assert consents['analytics']['granted'] is True
        assert 'updated_at' in consents['analytics']
        assert UserConsent.is_granted(member.id, 'email_notifications') is False
        assert UserConsent.is_granted(member.id, 'analytics') is True

    def test_is_granted_without_a_record_uses_the_default(self, api_app, member):
        assert UserConsent.is_granted(member.id, UserConsent.CONSENT_ANALYTICS) is False
        assert UserConsent.is_granted(member.id, UserConsent.CONSENT_AI_PROCESSING) is False
        assert UserConsent.is_granted(member.id, UserConsent.CONSENT_EMAIL_NOTIFICATIONS) is True
        assert UserConsent.is_granted(None, UserConsent.CONSENT_ANALYTICS) is False

    def test_a_change_stores_when_and_from_which_address(self, client, member):
        """What is kept as the record of a choice: the choice, the time, the address it came from."""
        client.post('/api/user/consents', json={'consent_type': 'analytics', 'granted': True},
                    environ_base={'REMOTE_ADDR': '198.51.100.7'})
        granted = UserConsent.query.filter_by(user_id=member.id, consent_type='analytics').one()
        assert granted.granted is True and granted.granted_at is not None and granted.withdrawn_at is None
        assert granted.ip_address == '198.51.100.7'

        client.post('/api/user/consents', json={'consent_type': 'analytics', 'granted': False},
                    environ_base={'REMOTE_ADDR': '198.51.100.9'})
        db.session.expire_all()
        withdrawn = UserConsent.query.filter_by(user_id=member.id, consent_type='analytics').one()
        assert withdrawn.granted is False and withdrawn.withdrawn_at is not None
        # One row per switch: the address is that of the latest change
        assert withdrawn.ip_address == '198.51.100.9'
        assert UserConsent.query.filter_by(user_id=member.id).count() == 1


class TestEmailNotificationsSwitch:

    @pytest.fixture
    def email_config(self, api_app):
        config = EmailConfig(domain='system', smtp_server='smtp.example.test', smtp_port=587,
                             smtp_username='mailer', smtp_password='secret',
                             from_email='noreply@example.test', enabled=True)
        db.session.add(config)
        db.session.commit()
        return config

    @pytest.fixture
    def sent(self):
        calls = []

        def record(email_config, to_email, subject, html_content, text_content=None):
            calls.append(to_email)
            return True

        with patch.object(notifications, 'send_email', side_effect=record):
            yield calls

    def subscriber(self, local, switch=None):
        user = make_member(local)
        db.session.add(Subscription(user_id=user.id, notify_on_create=True, notify_on_update=True,
                                    notify_on_status_change=True))
        if switch is not None:
            db.session.add(UserConsent(user_id=user.id, consent_type='email_notifications', granted=switch))
        db.session.commit()
        return user

    def decision(self, author):
        decision = ArchitectureDecision(
            title='Close the Leeds office', context='c', decision='d', consequences='q', status='proposed',
            domain=DOMAIN, created_by_id=author.id, updated_by_id=author.id, decision_number=1)
        db.session.add(decision)
        db.session.commit()
        return decision

    def test_new_decision_email_skips_only_the_person_who_switched_off(self, api_app, email_config, sent):
        author = make_member('author')
        self.subscriber('untouched')
        self.subscriber('on', switch=True)
        self.subscriber('off', switch=False)

        notifications.notify_subscribers_new_decision(db, self.decision(author), email_config)

        assert sorted(sent) == [f'on@{DOMAIN}', f'untouched@{DOMAIN}']

    def test_update_and_status_emails_skip_the_person_who_switched_off(self, api_app, email_config, sent):
        author = make_member('author')
        self.subscriber('untouched')
        self.subscriber('off', switch=False)
        decision = self.decision(author)

        notifications.notify_subscribers_decision_updated(db, decision, email_config, 'reworded', False)
        notifications.notify_subscribers_decision_updated(db, decision, email_config, None, True)

        assert sent == [f'untouched@{DOMAIN}', f'untouched@{DOMAIN}']

    def test_switching_back_on_resumes_the_emails(self, api_app, email_config, sent):
        author = make_member('author')
        reader = self.subscriber('reader', switch=False)
        client = sign_in(api_app, reader)

        client.post('/api/user/consents', json={'consent_type': 'email_notifications', 'granted': True})
        notifications.notify_subscribers_new_decision(db, self.decision(author), email_config)

        assert sent == [f'reader@{DOMAIN}']

    def test_owner_email_is_not_sent_to_an_owner_who_switched_off(self, api_app, email_config, sent):
        author = make_member('author')
        owner = make_member('owner')
        db.session.add(UserConsent(user_id=owner.id, consent_type='email_notifications', granted=False))
        db.session.commit()

        result = notifications.notify_decision_owner(
            email_config, self.decision(author), 'Owner@' + DOMAIN.upper(), 'Olu Owner')

        assert result is False and sent == []

    def test_owner_email_is_sent_by_default_and_to_an_owner_without_an_account(
            self, api_app, email_config, sent):
        author = make_member('author')
        make_member('owner')
        decision = self.decision(author)

        assert notifications.notify_decision_owner(email_config, decision, f'owner@{DOMAIN}') is True
        assert notifications.notify_decision_owner(email_config, decision, 'outsider@elsewhere.test') is True
        assert sent == [f'owner@{DOMAIN}', 'outsider@elsewhere.test']

    def test_account_mail_does_not_look_at_the_switch(self, api_app, email_config, sent):
        """Set-up and recovery links are always sent: they go straight to send_email."""
        person = make_member('locked')
        db.session.add(UserConsent(user_id=person.id, consent_type='email_notifications', granted=False))
        db.session.commit()

        assert notifications.send_account_recovery_email(
            email_config, 'Pat', person.email, 'https://app.example.test/recover', 2) is True
        assert notifications.send_account_setup_email(
            email_config, 'Pat', person.email, 'https://app.example.test/setup', 48) is True
        assert sent == [person.email, person.email]


class TestCorrectingOnesOwnName:

    def test_a_person_corrects_their_name(self, client, member):
        response = client.put('/api/user/profile', json={'first_name': ' Patricia ', 'last_name': 'Membre'})

        assert response.status_code == 200
        body = response.get_json()
        assert body['message'] == 'Name updated'
        assert (body['user']['name'], body['user']['first_name'], body['user']['last_name']) == (
            'Patricia Membre', 'Patricia', 'Membre')
        db.session.expire_all()
        stored = db.session.get(User, member.id)
        assert (stored.first_name, stored.last_name, stored.name) == ('Patricia', 'Membre', 'Patricia Membre')
        assert stored.name_edited_at is not None
        assert client.get('/api/user/me').get_json()['name'] == 'Patricia Membre'

    def test_one_name_is_enough(self, client, member):
        assert client.put('/api/user/profile', json={'first_name': 'Cher', 'last_name': ''}).status_code == 200
        db.session.expire_all()
        stored = db.session.get(User, member.id)
        assert (stored.first_name, stored.last_name, stored.get_full_name()) == ('Cher', None, 'Cher')

    @pytest.mark.parametrize('payload, message', [
        ({'first_name': '', 'last_name': '   '}, 'A name is required'),
        ({'first_name': None, 'last_name': None}, 'A name is required'),
        ({}, 'Give a first name or a last name'),
        ({'email': 'someone@else.test'}, 'Give a first name or a last name'),
        ({'first_name': 'x' * 101, 'last_name': 'Y'}, 'A name can be at most 100 characters'),
        ({'first_name': 7, 'last_name': 'Y'}, 'first_name must be text'),
        ({'first_name': '<b></b>', 'last_name': ''}, 'A name is required'),
    ])
    def test_refused_input_changes_nothing(self, client, member, payload, message):
        response = client.put('/api/user/profile', json=payload)

        assert response.status_code == 400
        assert response.get_json()['error'] == message
        db.session.expire_all()
        stored = db.session.get(User, member.id)
        assert (stored.first_name, stored.last_name, stored.name_edited_at) == ('Pat', 'Member', None)

    def test_markup_is_removed_from_a_name(self, client, member):
        client.put('/api/user/profile', json={'first_name': '<script>alert(1)</script>Pat', 'last_name': '<i>Lee</i>'})

        db.session.expire_all()
        stored = db.session.get(User, member.id)
        assert '<' not in stored.first_name and '<' not in stored.last_name
        assert stored.last_name == 'Lee'

    def test_the_email_address_cannot_be_changed_here(self, client, member):
        client.put('/api/user/profile', json={
            'first_name': 'Pat', 'last_name': 'Member', 'email': 'pat@other.test', 'sso_domain': 'other.test',
            'is_admin': True})

        db.session.expire_all()
        stored = db.session.get(User, member.id)
        assert (stored.email, stored.sso_domain, stored.is_admin) == (f'pat@{DOMAIN}', DOMAIN, False)

    def test_only_ones_own_name(self, api_app, client, member):
        colleague = make_member('colleague', first='Col', last='League')

        client.put('/api/user/profile', json={'first_name': 'New', 'last_name': 'Name', 'id': colleague.id,
                                              'user_id': colleague.id})

        db.session.expire_all()
        assert db.session.get(User, colleague.id).name == 'Col League'
        assert db.session.get(User, member.id).name == 'New Name'

    def test_signed_out_is_refused(self, api_app):
        response = api_app.test_client().put('/api/user/profile', json={'first_name': 'A', 'last_name': 'B'})

        assert response.status_code in (401, 403)

    def test_the_copy_of_the_name_on_own_comments_follows(self, client, member):
        colleague = make_member('colleague', first='Col', last='League')
        tenant = Tenant.query.filter_by(domain=DOMAIN).one()
        decision = ArchitectureDecision(title='t', context='c', decision='d', consequences='q', status='proposed',
                                        domain=DOMAIN, tenant_id=tenant.id, created_by_id=member.id,
                                        decision_number=1)
        db.session.add(decision)
        db.session.flush()
        own = DecisionComment(decision_id=decision.id, tenant_id=tenant.id, user_id=member.id, body='mine',
                              author_display='Pat Member')
        theirs = DecisionComment(decision_id=decision.id, tenant_id=tenant.id, user_id=colleague.id, body='theirs',
                                 author_display='Col League')
        db.session.add_all([own, theirs])
        db.session.commit()
        own_id, their_id = own.id, theirs.id

        client.put('/api/user/profile', json={'first_name': 'Patricia', 'last_name': 'Membre'})

        db.session.expire_all()
        assert db.session.get(DecisionComment, own_id).author_display == 'Patricia Membre'
        assert db.session.get(DecisionComment, their_id).author_display == 'Col League'


class TestSignInKeepsACorrectedName:
    """Signing in through an identity provider used to overwrite the name every time."""

    def test_the_provider_name_no_longer_replaces_a_corrected_name(self, client, member):
        client.put('/api/user/profile', json={'first_name': 'Patricia', 'last_name': 'Membre'})

        get_or_create_user(member.email, 'Pat Member', 'subject-1', DOMAIN)
        get_or_create_user(member.email, None, 'subject-1', DOMAIN, first_name='Pat', last_name='Member')

        db.session.expire_all()
        stored = db.session.get(User, member.id)
        assert (stored.first_name, stored.last_name, stored.name) == ('Patricia', 'Membre', 'Patricia Membre')

    def test_a_name_never_corrected_still_follows_the_provider(self, api_app, member):
        get_or_create_user(member.email, 'Patrick Memberson', 'subject-1', DOMAIN)

        db.session.expire_all()
        assert db.session.get(User, member.id).name == 'Patrick Memberson'
