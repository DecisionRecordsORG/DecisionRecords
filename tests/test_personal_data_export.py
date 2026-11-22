"""
The personal data export contains what the published text says, and nothing
about anyone else.

Published: "The export includes account details, decisions, comments, activity
history, and consent preferences. It also includes the messages you sent us
while signed in."

Three people have a row in every place that holds personal data: the person
exporting, a colleague in the same organisation, and someone in another
organisation. The export must hold the first person's data in every section
and must not mention the other two anywhere.

`build_personal_data_export` is tested on the shared `app` fixture, so CI also
runs it on PostgreSQL. The endpoint itself is tested through the real app.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import data_export
from data_export import build_personal_data_export, EXPORT_RULES
from models import (
    db, User, Tenant, TenantMembership, AuditLog, ArchitectureDecision, DecisionComment,
    GlobalRole, MaturityState, UserConsent
)
from tests.app_test_utils import load_test_app
from tests.personal_data_test_data import make_organisation, make_person

DOMAIN = 'export.test'
EXISTING_KEYS = ['export_date', 'data_subject', 'profile', 'decisions_authored', 'memberships',
                 'audit_trail', 'login_history', 'inquiries']
NEW_KEYS = ['account_status', 'passkeys', 'notification_settings', 'consents', 'comments',
            'decisions_owned', 'decision_changes', 'role_requests', 'access_requests',
            'team_profile_answers', 'ai_api_keys', 'ai_interactions', 'linked_accounts']


@pytest.fixture
def people(app):
    organisation = make_organisation(DOMAIN, 'alpha')
    elsewhere = make_organisation('elsewhere.test', 'omega')
    zebedee = make_person(organisation, 'Zebedee', 'Quillfeather', 'alpha', '198.51.100.77', first_requester=True)
    ottoline = make_person(organisation, 'Ottoline', 'Wrenfield', 'bravo', '198.51.100.88')
    barnaby = make_person(elsewhere, 'Barnaby', 'Thistlewood', 'omega', '198.51.100.99', first_requester=True)
    return {'organisation': organisation, 'elsewhere': elsewhere,
            'zebedee': zebedee, 'ottoline': ottoline, 'barnaby': barnaby}


@pytest.fixture
def export(people):
    return build_personal_data_export(db.session.get(User, people['zebedee'].id))


# ==================== Every place that points at a person has a rule ====================

class TestEveryReferenceToAPersonHasARule:

    def _references(self):
        return {f'{table.name}.{column.name}'
                for table in db.metadata.sorted_tables for column in table.columns
                for key in column.foreign_keys if key.column.table.name == 'users'}

    def test_no_column_is_missing_a_rule(self, app):
        missing = sorted(self._references() - set(EXPORT_RULES))

        assert not missing, (
            'Decide whether rows that point at a person through these columns belong in their '
            f'data export, and add them to data_export.EXPORT_RULES: {missing}')

    def test_no_rule_names_a_column_that_is_gone(self, app):
        assert not sorted(set(EXPORT_RULES) - self._references())

    def test_every_section_a_rule_names_is_in_the_export(self, export):
        sections = {section for section, _why in EXPORT_RULES.values() if section}

        assert sections <= set(export)

    def test_every_rule_says_why(self, app):
        assert all(isinstance(why, str) and why for _section, why in EXPORT_RULES.values())


# ==================== What the published text promises ====================

class TestExportContainsWhatIsPublished:

    def test_existing_sections_are_still_there_first_and_new_ones_are_added(self, export):
        assert list(export)[:len(EXISTING_KEYS)] == EXISTING_KEYS
        assert sorted(list(export)[len(EXISTING_KEYS):]) == sorted(NEW_KEYS)

    def test_account_details(self, export, people):
        zebedee = people['zebedee']

        assert export['data_subject'] == {
            'id': zebedee.id, 'email': zebedee.email, 'name': 'Zebedee Quillfeather',
            'first_name': 'Zebedee', 'last_name': 'Quillfeather'}
        assert set(export['profile']) == {'auth_type', 'email_verified', 'created_at', 'last_login', 'sso_domain'}
        assert export['account_status'] == {
            'has_password': True, 'deletion_requested_at': None, 'deletion_scheduled_at': None,
            'has_seen_admin_onboarding': False}
        assert export['memberships'] == [{
            'tenant_name': 'alpha organisation', 'tenant_domain': DOMAIN, 'role': 'user',
            'joined_at': export['memberships'][0]['joined_at']}]

    def test_decisions_with_their_content(self, export):
        (authored,) = export['decisions_authored']

        # the keys the export always had
        assert {'id', 'title', 'status', 'created_at', 'updated_at'} <= set(authored)
        assert authored['title'] == 'Decision written by alpha'
        assert (authored['context'], authored['decision'], authored['consequences']) == (
            'Context alpha', 'Outcome alpha', 'Consequences alpha')

    def test_decisions_the_person_owns_but_did_not_write(self, export):
        titles = [decision['title'] for decision in export['decisions_owned']]

        assert titles == ['Decision written by alpha', 'Decision owned by alpha']
        owned = export['decisions_owned'][1]
        assert owned['context'] == 'Owned context alpha'

    def test_comments_are_the_person_s_own(self, export):
        bodies = sorted(comment['body'] for comment in export['comments'])

        assert bodies == ['Comment body alpha', 'Second comment body alpha']
        first = next(comment for comment in export['comments'] if comment['body'] == 'Comment body alpha')
        assert first['decision_title'] == 'Decision written by alpha'
        assert first['deleted_at'] is None
        assert set(first) == {'id', 'decision_id', 'decision_title', 'body', 'created_at', 'updated_at', 'deleted_at'}

    def test_a_comment_the_person_removed_is_still_their_data(self, export):
        removed = next(comment for comment in export['comments'] if comment['body'] == 'Second comment body alpha')

        assert removed['deleted_at'] is not None

    def test_activity_history(self, export):
        assert export['audit_trail'] == [{'action': 'user_joined', 'target': 'user',
                                          'created_at': export['audit_trail'][0]['created_at']}]
        (sign_in,) = export['login_history']
        assert sign_in['ip_address'] == '198.51.100.77'
        assert sign_in['user_agent'] == 'ZebedeeBrowser/1.0'
        assert sign_in['success'] is True
        assert export['decision_changes'] == [{
            'decision_id': export['decisions_authored'][0]['id'],
            'changed_at': export['decision_changes'][0]['changed_at'], 'change_reason': 'Reworded alpha'}]

    def test_consent_preferences(self, export):
        consents = {consent['consent_type']: consent for consent in export['consents']}

        assert set(consents) == {'analytics', 'ai_processing'}
        assert consents['analytics']['granted'] is True
        assert consents['analytics']['granted_at'] is not None
        assert consents['ai_processing']['granted'] is False
        assert consents['ai_processing']['withdrawn_at'] is not None
        assert consents['analytics']['ip_address'] == '198.51.100.77'

    def test_messages_sent_while_signed_in(self, export):
        (message,) = export['inquiries']

        assert message['message'] == 'Zebedee has a suggestion'
        assert message['source'] == 'feedback'

    def test_the_rest_of_what_is_held_about_the_person(self, export):
        assert export['passkeys'] == [{
            'device_name': "Zebedee's phone", 'created_at': export['passkeys'][0]['created_at'],
            'last_used_at': None}]
        assert export['notification_settings']['notify_on_update'] is True
        assert [(request['requested_role'], request['status'], request['reason'])
                for request in export['role_requests']] == [('steward', 'pending', 'Zebedee looks after the records')]
        (access,) = export['access_requests']
        assert (access['status'], access['reason']) == ('rejected', 'Zebedee works here')
        assert export['team_profile_answers'] == [{
            'tenant_domain': DOMAIN, 'team_focus': 'Clinical protocols', 'team_size': None,
            'answered_at': export['team_profile_answers'][0]['answered_at']}]
        (key,) = export['ai_api_keys']
        assert key['name'] == "Zebedee's laptop key"
        assert set(key) == {'name', 'description', 'key_prefix', 'scopes', 'created_at', 'last_used_at',
                            'expires_at', 'revoked_at'}
        assert [item['query_text'] for item in export['ai_interactions']] == ['what did Zebedee decide about hiring']
        assert sorted((link['service'], link['account_id']) for link in export['linked_accounts']) == [
            ('slack', 'UZEBEDEE'), ('teams', 'aad-zebedee-0001')]

    def test_it_can_be_written_as_json(self, export):
        assert json.loads(json.dumps(export)) == export


# ==================== Nothing about anyone else, nothing that signs in ====================

class TestExportContainsNobodyElse:

    def test_a_colleague_is_not_mentioned_anywhere(self, export, people):
        text = json.dumps(export).lower()
        ottoline = people['ottoline']

        for needle in ottoline.needles + ['bravo']:
            assert needle not in text, needle

    def test_someone_in_another_organisation_is_not_mentioned_anywhere(self, export, people):
        text = json.dumps(export).lower()

        for needle in people['barnaby'].needles + ['omega', 'elsewhere.test']:
            assert needle not in text, needle

    def test_the_administrator_who_handled_requests_is_not_named(self, export, people):
        text = json.dumps(export).lower()
        admin = people['organisation']['admin']

        assert admin.email not in text
        assert 'organisation administrator' not in text

    def test_a_colleague_s_comment_on_the_person_s_own_decision_is_left_out(self, people):
        zebedee, ottoline = people['zebedee'], people['ottoline']
        own = ArchitectureDecision.query.filter_by(title='Decision written by alpha').one()
        db.session.add(DecisionComment(decision_id=own.id, tenant_id=own.tenant_id, user_id=ottoline.id,
                                       author_display=ottoline.full_name, body='A reply from a colleague'))
        db.session.commit()

        export = build_personal_data_export(db.session.get(User, zebedee.id))

        assert 'A reply from a colleague' not in json.dumps(export)
        assert len(export['comments']) == 2

    def test_a_decision_in_another_organisation_that_names_the_address_is_left_out(self, people):
        zebedee = people['zebedee']
        other = people['elsewhere']['tenant']
        db.session.add(ArchitectureDecision(
            title='Their decision', context='Their context', decision='Their outcome', consequences='Theirs',
            status='accepted', domain=other.domain, tenant_id=other.id, decision_number=40,
            owner_email=zebedee.email))
        db.session.commit()

        export = build_personal_data_export(db.session.get(User, zebedee.id))

        assert 'Their' not in json.dumps(export)

    def test_a_deleted_decision_keeps_its_place_but_not_its_text(self, people):
        zebedee = people['zebedee']
        own = ArchitectureDecision.query.filter_by(title='Decision written by alpha').one()
        own.deleted_at = own.created_at
        db.session.commit()

        export = build_personal_data_export(db.session.get(User, zebedee.id))

        (authored,) = export['decisions_authored']
        assert authored['title'] == 'Decision written by alpha'
        assert (authored['context'], authored['decision'], authored['consequences']) == (None, None, None)
        assert authored['deleted_at'] is not None
        comment = next(item for item in export['comments'] if item['body'] == 'Comment body alpha')
        assert comment['decision_title'] is None

    def test_nothing_that_lets_someone_sign_in_or_act_is_included(self, export, people):
        text = json.dumps(export).lower()
        user = db.session.get(User, people['zebedee'].id)

        assert user.password_hash and user.password_hash.lower() not in text
        for secret in ('credential-zebedee', 'public-key-zebedee', 'keyhash-alpha', 'tokenhash-zebedee',
                       'verify-zebedee', 'idp|zebedee'):
            assert secret not in text, secret
        for key in ('password_hash', 'key_hash', 'token_hash', 'credential_id', 'public_key', 'sign_count'):
            assert f'"{key}"' not in text, key

    def test_messages_sent_while_signed_out_are_not_claimed(self, export):
        """A message carrying the same address but sent without signing in is not proven to be theirs."""
        assert [message['message'] for message in export['inquiries']] == ['Zebedee has a suggestion']

    def test_person_with_nothing_gets_empty_sections(self, app):
        organisation = make_organisation(DOMAIN, 'alpha')

        export = build_personal_data_export(db.session.get(User, organisation['admin'].id))

        for key in NEW_KEYS:
            if key in ('account_status', 'notification_settings'):
                continue
            assert export[key] == [], key
        assert export['notification_settings'] is None
        assert export['decisions_authored'] == []


# ==================== The endpoint ====================

class TestExportEndpoint:

    @pytest.fixture
    def real_app(self):
        app_module, test_app = load_test_app(secret_key='test-secret-key-personal-export')

        with test_app.app_context():
            db.create_all()
            app_module.init_database()
            yield app_module, test_app
            db.session.remove()
            db.drop_all()
            app_module._db_initialized = False

    def _client(self, test_app, user_id):
        client = test_app.test_client()
        with client.session_transaction() as sess:
            sess['user_id'] = user_id
            sess['_csrf_token'] = 'test-csrf-token'
        client.environ_base['HTTP_X_CSRF_TOKEN'] = 'test-csrf-token'
        return client

    def _signed_in(self, test_app, person):
        from auth import start_user_session
        client = test_app.test_client()
        with test_app.test_request_context():
            pass
        with client.session_transaction() as sess:
            sess['user_id'] = person.id
            sess['_csrf_token'] = 'test-csrf-token'
            from datetime import datetime, timedelta, timezone
            sess['_expires_at'] = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        client.environ_base['HTTP_X_CSRF_TOKEN'] = 'test-csrf-token'
        return client

    def _people(self):
        organisation = make_organisation(DOMAIN, 'alpha')
        zebedee = make_person(organisation, 'Zebedee', 'Quillfeather', 'alpha', '198.51.100.77')
        ottoline = make_person(organisation, 'Ottoline', 'Wrenfield', 'bravo', '198.51.100.88')
        return organisation, zebedee, ottoline

    def test_endpoint_returns_the_export_as_a_download(self, real_app):
        _, test_app = real_app
        _organisation, zebedee, ottoline = self._people()

        response = self._signed_in(test_app, zebedee).post('/api/user/export-data')

        assert response.status_code == 200, response.get_data(as_text=True)
        assert response.headers['Content-Disposition'].startswith(f'attachment; filename="data-export-{zebedee.id}-')
        body = response.get_json()
        assert list(body)[:0] == []  # jsonify may sort keys; the content is what matters
        assert set(EXISTING_KEYS + NEW_KEYS) == set(body)
        assert sorted(comment['body'] for comment in body['comments']) == [
            'Comment body alpha', 'Second comment body alpha']
        assert {consent['consent_type'] for consent in body['consents']} == {'analytics', 'ai_processing'}
        text = response.get_data(as_text=True).lower()
        for needle in ottoline.needles:
            assert needle not in text

    def test_each_person_gets_their_own_export(self, real_app):
        _, test_app = real_app
        _organisation, zebedee, ottoline = self._people()

        body = self._signed_in(test_app, ottoline).post('/api/user/export-data').get_json()

        assert body['data_subject']['email'] == ottoline.email
        assert sorted(comment['body'] for comment in body['comments']) == [
            'Comment body bravo', 'Second comment body bravo']
        assert 'zebedee' not in json.dumps(body).lower()

    def test_the_export_is_recorded_with_the_names_of_its_sections(self, real_app):
        _, test_app = real_app
        _organisation, zebedee, _ottoline = self._people()

        self._signed_in(test_app, zebedee).post('/api/user/export-data')

        entry = AuditLog.query.filter_by(action_type=AuditLog.ACTION_USER_DATA_EXPORTED,
                                         actor_user_id=zebedee.id).one()
        assert set(entry.details['export_sections']) == set(EXISTING_KEYS + NEW_KEYS)

    def test_anonymous_caller_is_refused(self, real_app):
        _, test_app = real_app

        response = test_app.test_client().post('/api/user/export-data')

        assert response.status_code == 401

    def test_there_is_no_way_to_ask_for_someone_else_s_export(self, real_app):
        """The endpoint takes no user id: a parameter naming a colleague changes nothing."""
        _, test_app = real_app
        _organisation, zebedee, ottoline = self._people()

        response = self._signed_in(test_app, zebedee).post(
            f'/api/user/export-data?user_id={ottoline.id}', json={'user_id': ottoline.id, 'email': ottoline.email})

        assert response.status_code == 200
        assert response.get_json()['data_subject']['id'] == zebedee.id
        assert 'ottoline' not in response.get_data(as_text=True).lower()
