"""
Notification emails: wording, recipients and links.

The emails describe "decisions" and "decision records" for any kind of team.
They carry no "[ADR]" prefix and refer to a decision by the display ID shown
in the app.
"""
import inspect
from unittest.mock import patch

import pytest

import notifications
from models import ArchitectureDecision, AuthConfig, EmailConfig, Subscription, User, db

DOMAIN = 'example.com'
OLD_WORDING = ('[ADR]', 'ADR-', 'Architecture Decision', 'architecture decision',
               'architectural decision', 'Architecture Decisions')


@pytest.fixture
def email_config(session):
    config = EmailConfig(
        domain='system', smtp_server='smtp.example.test', smtp_port=587,
        smtp_username='mailer', smtp_password='secret', from_email='noreply@example.test',
        enabled=True)
    session.add(config)
    session.commit()
    return config


def make_user(session, email, **subscription):
    user = User(email=email, sso_domain=email.split('@')[1], auth_type='local')
    user.set_name(full_name=email.split('@')[0].title())
    session.add(user)
    session.flush()
    if subscription:
        session.add(Subscription(user_id=user.id, **subscription))
    session.commit()
    return user


def make_decision(session, author, *, number=7, prefix='XMP', status='proposed', **extra):
    if prefix and not AuthConfig.query.filter_by(domain=DOMAIN).first():
        session.add(AuthConfig(domain=DOMAIN, tenant_prefix=prefix))
    decision = ArchitectureDecision(
        title='Raise list prices by 4%', context='Supplier costs rose.',
        decision='Raise prices from March.', consequences='Some customers may churn.',
        status=status, domain=DOMAIN, created_by_id=author.id, updated_by_id=author.id,
        decision_number=number, **extra)
    session.add(decision)
    session.commit()
    return decision


@pytest.fixture
def sent():
    """Every email handed to send_email, as dicts."""
    calls = []

    def record(email_config, to_email, subject, html_content, text_content=None):
        calls.append({'to': to_email, 'subject': subject, 'html': html_content, 'text': text_content})
        return True

    with patch.object(notifications, 'send_email', side_effect=record):
        yield calls


def assert_no_old_wording(message):
    for part in ('subject', 'html', 'text'):
        for phrase in OLD_WORDING:
            assert phrase not in message[part], f'{phrase!r} found in {part}'


class TestNewDecisionEmail:

    def test_subject_and_body_use_decision_wording(self, session, email_config, sent):
        author = make_user(session, f'author@{DOMAIN}')
        make_user(session, f'reader@{DOMAIN}', notify_on_create=True)
        decision = make_decision(session, author)

        notifications.notify_subscribers_new_decision(db, decision, email_config)

        assert len(sent) == 1
        message = sent[0]
        assert message['to'] == f'reader@{DOMAIN}'
        assert message['subject'] == 'New decision: Raise list prices by 4%'
        assert '<h2>New decision record</h2>' in message['html']
        assert 'New decision record' in message['text']
        for body in (message['html'], message['text']):
            assert 'XMP-007: Raise list prices by 4%' in body
            assert 'Supplier costs rose.' in body
            assert 'Raise prices from March.' in body
            assert 'Some customers may churn.' in body
            assert 'Proposed' in body
            assert 'Author' in body
        assert_no_old_wording(message)

    def test_creator_and_other_tenants_are_not_notified(self, session, email_config, sent):
        author = make_user(session, f'author@{DOMAIN}', notify_on_create=True)
        make_user(session, 'reader@other.test', notify_on_create=True)
        make_user(session, f'quiet@{DOMAIN}', notify_on_create=False)
        decision = make_decision(session, author)

        notifications.notify_subscribers_new_decision(db, decision, email_config)

        assert sent == []

    def test_nothing_is_sent_without_enabled_email(self, session, email_config, sent):
        author = make_user(session, f'author@{DOMAIN}')
        make_user(session, f'reader@{DOMAIN}', notify_on_create=True)
        decision = make_decision(session, author)
        email_config.enabled = False

        notifications.notify_subscribers_new_decision(db, decision, email_config)
        notifications.notify_subscribers_new_decision(db, decision, None)

        assert sent == []


class TestDecisionUpdatedEmail:

    def test_update_subject_and_body(self, session, email_config, sent):
        author = make_user(session, f'author@{DOMAIN}')
        make_user(session, f'reader@{DOMAIN}', notify_on_update=True)
        decision = make_decision(session, author)

        notifications.notify_subscribers_decision_updated(
            db, decision, email_config, change_reason='New supplier quote')

        assert len(sent) == 1
        message = sent[0]
        assert message['subject'] == 'Decision updated: Raise list prices by 4%'
        assert '<h2>Decision record updated</h2>' in message['html']
        for body in (message['html'], message['text']):
            assert 'XMP-007: Raise list prices by 4%' in body
            assert 'New supplier quote' in body
        assert_no_old_wording(message)

    def test_status_change_subject_reaches_status_subscribers(self, session, email_config, sent):
        author = make_user(session, f'author@{DOMAIN}')
        make_user(session, f'status@{DOMAIN}', notify_on_update=False, notify_on_status_change=True)
        make_user(session, f'neither@{DOMAIN}', notify_on_update=False, notify_on_status_change=False)
        decision = make_decision(session, author, status='accepted')

        notifications.notify_subscribers_decision_updated(db, decision, email_config, status_changed=True)

        assert [message['to'] for message in sent] == [f'status@{DOMAIN}']
        assert sent[0]['subject'] == 'Decision status changed: Raise list prices by 4% is now Accepted'
        assert_no_old_wording(sent[0])

    def test_plain_update_skips_status_only_subscribers_and_the_editor(self, session, email_config, sent):
        author = make_user(session, f'author@{DOMAIN}', notify_on_update=True)
        make_user(session, f'status@{DOMAIN}', notify_on_update=False, notify_on_status_change=True)
        decision = make_decision(session, author)

        notifications.notify_subscribers_decision_updated(db, decision, email_config)

        assert sent == []


class TestDecisionOwnerEmail:

    def test_owner_email_is_sent_with_display_id_and_link(self, session, email_config, sent):
        author = make_user(session, f'author@{DOMAIN}')
        decision = make_decision(session, author)

        result = notifications.notify_decision_owner(
            email_config, decision, f'owner@{DOMAIN}', 'Olu Owner', 'https://app.example.test')

        assert result is True
        message = sent[0]
        assert message['to'] == f'owner@{DOMAIN}'
        assert message['subject'] == "You've been assigned as the owner of: Raise list prices by 4%"
        link = f'https://app.example.test/{DOMAIN}/decision/{decision.id}'
        for body in (message['html'], message['text']):
            assert 'Hi Olu Owner,' in body
            assert 'XMP-007: Raise list prices by 4%' in body
            assert link in body
            assert 'for the following decision:' in body.replace('<strong>', '').replace('</strong>', '')
        assert_no_old_wording(message)

    def test_owner_email_without_base_url_has_no_link(self, session, email_config, sent):
        author = make_user(session, f'author@{DOMAIN}')
        decision = make_decision(session, author)

        notifications.notify_decision_owner(email_config, decision, f'owner@{DOMAIN}')

        assert 'Hi owner,' in sent[0]['text']
        assert 'View decision' not in sent[0]['text']
        assert 'href=' not in sent[0]['html']

    def test_owner_email_not_sent_without_enabled_email(self, session, sent):
        author = make_user(session, f'author@{DOMAIN}')
        decision = make_decision(session, author)

        assert notifications.notify_decision_owner(None, decision, f'owner@{DOMAIN}') is False
        assert sent == []


class TestDecisionHeading:

    def test_tenant_without_prefix_uses_fallback_display_id(self, session):
        author = make_user(session, f'author@{DOMAIN}')
        decision = make_decision(session, author, prefix=None)

        assert notifications.decision_heading(decision) == f'{decision.get_display_id()}: Raise list prices by 4%'

    def test_decision_without_a_number_uses_title_only(self, session):
        author = make_user(session, f'author@{DOMAIN}')
        decision = make_decision(session, author, number=None)

        assert notifications.decision_heading(decision) == 'Raise list prices by 4%'


class TestAccountEmailsUseProductName:

    @pytest.mark.parametrize('function_name', [
        'send_setup_token_email', 'send_account_setup_email', 'send_account_recovery_email',
        'send_feedback_email', 'send_contact_email', 'send_sponsorship_inquiry_email',
    ])
    def test_app_name_defaults_to_decision_records(self, function_name):
        function = getattr(notifications, function_name)

        assert inspect.signature(function).parameters['app_name'].default == 'Decision Records'

    def test_account_setup_email_names_the_product(self, session, email_config, sent):
        notifications.send_account_setup_email(
            email_config, 'New Comer', f'newcomer@{DOMAIN}',
            'https://app.example.test/example.com/setup?token=abc', 48, tenant_name=DOMAIN)

        message = sent[0]
        assert message['subject'] == 'Complete Your Decision Records Account Setup'
        assert 'https://app.example.test/example.com/setup?token=abc' in message['html']
        assert 'https://app.example.test/example.com/setup?token=abc' in message['text']
        assert_no_old_wording(message)

    def test_recovery_email_names_the_product(self, session, email_config, sent):
        notifications.send_account_recovery_email(
            email_config, 'Pat', f'pat@{DOMAIN}', 'https://app.example.test/recover?token=abc', 2)

        message = sent[0]
        assert message['subject'] == 'Reset Your Decision Records Credentials'
        assert 'https://app.example.test/recover?token=abc' in message['text']
        assert_no_old_wording(message)
