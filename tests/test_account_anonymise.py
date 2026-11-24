"""
After an account is anonymised, nothing in the database names the person.

The product says a deleted member's contributions are kept and attributed to
"Former Member". These tests give one person a row in every place that holds a
name, an email address or an IP address, anonymise the account, and then read
every text, JSON and binary column of every table looking for the person.

Two things keep this honest as the schema grows:

* the search reads the tables from the models, so a new column is searched
  without being listed anywhere;
* `retention.ACCOUNT_TEXT_RULES` must name every text column of every table
  and say what anonymisation does with it, so a new column cannot be added
  without deciding. A column marked 'cleared' must be filled by the test data,
  or the test that proves it is cleared fails.

They use the shared `app` fixture, so CI also runs them on PostgreSQL.
"""
import json
import os
import sys
from datetime import timedelta

import pytest
import sqlalchemy as sa

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import retention
from models import (
    db, User, TenantMembership, AuditLog, LoginHistory, Inquiry, UserConsent, DomainApproval,
    WebAuthnCredential, Subscription, ArchitectureDecision, DecisionHistory, DecisionComment,
    AccessRequest, RoleRequest, SetupToken, EmailVerification, SlackUserMapping, TeamsUserMapping,
    TeamsConversationReference, AIApiKey, AIInteractionLog, Tenant, RetentionErasure, RetentionRun,
)
from tests.personal_data_test_data import make_organisation, make_person, find_everywhere, text_columns
from tests.retention_test_data import naive_now

DOMAIN = 'scan.test'


@pytest.fixture
def people(app):
    """Zebedee (to be anonymised) and Ottoline (a colleague), each with data everywhere; Barnaby elsewhere."""
    organisation = make_organisation(DOMAIN, 'alpha')
    elsewhere = make_organisation('elsewhere.test', 'omega')
    zebedee = make_person(organisation, 'Zebedee', 'Quillfeather', 'alpha', '198.51.100.77', first_requester=True)
    ottoline = make_person(organisation, 'Ottoline', 'Wrenfield', 'bravo', '198.51.100.88')
    barnaby = make_person(elsewhere, 'Barnaby', 'Thistlewood', 'omega', '198.51.100.99', first_requester=True)
    return {'organisation': organisation, 'zebedee': zebedee, 'ottoline': ottoline, 'barnaby': barnaby}


# ==================== The rules cover the schema ====================

class TestEveryTextColumnHasARule:

    def _columns(self):
        return {f'{table.name}.{column.name}'
                for table in db.metadata.sorted_tables for column in text_columns(table)}

    def test_no_column_is_missing_a_rule(self, app):
        missing = sorted(self._columns() - set(retention.ACCOUNT_TEXT_RULES))

        assert not missing, (
            'Decide what account anonymisation does with these columns and add them to '
            f'retention.ACCOUNT_TEXT_RULES: {missing}')

    def test_no_rule_names_a_column_that_is_gone(self, app):
        assert not sorted(set(retention.ACCOUNT_TEXT_RULES) - self._columns())

    def test_every_rule_is_one_of_the_known_kinds(self, app):
        kinds = {rule for rule in retention.ACCOUNT_TEXT_RULES.values()}

        assert kinds <= {retention.CLEARED, retention.CONTENT, retention.NOT_THE_PERSON}

    def test_the_test_data_fills_every_column_that_must_be_cleared(self, people):
        """A 'cleared' column the test data does not fill would pass the scan without being tested."""
        found = find_everywhere(people['zebedee'].needles)
        # A password hash cannot carry a name; that it is emptied is checked on its own below
        cleared = {column for column, rule in retention.ACCOUNT_TEXT_RULES.items()
                   if rule == retention.CLEARED} - {'users.password_hash'}

        not_filled = sorted(cleared - set(found))

        assert not not_filled, f'personal_data_test_data.make_person does not fill: {not_filled}'

    def test_the_test_data_names_the_person_only_where_the_rules_say_it_is_cleared(self, people):
        found = find_everywhere(people['zebedee'].needles)

        unexpected = sorted(column for column in found
                            if retention.ACCOUNT_TEXT_RULES.get(column) != retention.CLEARED)

        assert not unexpected, f'the test data names the person in kept columns: {unexpected}'


# ==================== The scan ====================

class TestNothingNamesTheFormerMember:

    def test_before_anonymisation_the_person_is_found_in_many_places(self, people):
        found = find_everywhere(people['zebedee'].needles)

        assert len(found) > 30
        assert 'decision_comments.author_display' in found
        assert 'audit_logs.details' in found

    def test_after_anonymisation_no_column_of_any_table_names_the_person(self, people):
        zebedee = people['zebedee']

        assert retention.anonymize_user(zebedee.id) is True

        assert find_everywhere(zebedee.needles) == {}

    def test_the_automatic_retention_run_leaves_nothing_either(self, people, monkeypatch):
        """Same result through the daily run, whose erasure record must not name the person."""
        monkeypatch.setattr(retention, '_session_utc_offset_seconds', lambda: 0)
        zebedee = people['zebedee']
        now = naive_now()
        user = db.session.get(User, zebedee.id)
        user.deletion_requested_at = now - timedelta(days=8)
        user.deletion_scheduled_at = now - timedelta(hours=1)
        db.session.commit()

        run = retention.run_retention(RetentionRun.TRIGGER_AUTOMATIC, categories=[retention.ACCOUNTS], now=now)

        assert run['results']['accounts']['affected'] == 1
        assert find_everywhere(zebedee.needles) == {}
        record = RetentionErasure.query.filter_by(category=retention.ACCOUNTS).one()
        assert record.entity_id == zebedee.id
        assert all(isinstance(value, int) for value in record.counts.values())

    def test_colleagues_and_other_organisations_are_untouched(self, people):
        ottoline, barnaby = people['ottoline'], people['barnaby']
        before = (find_everywhere(ottoline.needles), find_everywhere(barnaby.needles))

        retention.anonymize_user(people['zebedee'].id)

        assert (find_everywhere(ottoline.needles), find_everywhere(barnaby.needles)) == before

    def test_anonymising_twice_changes_nothing_more(self, people):
        zebedee = people['zebedee']
        retention.anonymize_user(zebedee.id)
        email_after = db.session.get(User, zebedee.id).email

        assert retention.anonymize_user(zebedee.id) is False
        assert db.session.get(User, zebedee.id).email == email_after


# ==================== What is kept, and how ====================

class TestContributionsAreKeptAsFormerMember:

    @pytest.fixture
    def after(self, people):
        people['counts'] = retention._anonymise_user_record(db.session.get(User, people['zebedee'].id))
        db.session.commit()
        return people

    def test_account_row_remains_as_former_member(self, after):
        user = db.session.get(User, after['zebedee'].id)

        assert user.name == 'Former Member'
        assert user.get_full_name() == 'Former Member'
        assert user.email.endswith('@anonymized.local')
        assert (user.first_name, user.last_name, user.password_hash, user.sso_subject, user.aad_object_id) == (
            None, None, None, None, None)
        assert user.is_anonymized is True

    def test_comments_stay_and_are_attributed_to_former_member(self, after):
        comments = DecisionComment.query.filter_by(user_id=after['zebedee'].id).order_by(DecisionComment.id).all()

        assert [comment.body for comment in comments] == ['Comment body alpha', 'Second comment body alpha']
        assert [comment.author_display for comment in comments] == ['Former Member', 'Former Member']
        assert [comment.to_dict()['author'] for comment in comments] == ['Former Member', 'Former Member']
        assert after['counts']['comments_reattributed'] == 3

    def test_comment_recorded_by_address_without_an_account_is_reattributed_too(self, after):
        comment = DecisionComment.query.filter_by(body='Comment by address alpha').one()

        assert comment.user_id is None
        assert comment.author_display == 'Former Member'

    def test_a_colleague_s_comment_keeps_its_author(self, after):
        ottoline = after['ottoline']
        comment = DecisionComment.query.filter_by(body='Comment body bravo').one()

        assert comment.author_display == ottoline.full_name
        assert comment.to_dict()['author'] == ottoline.full_name

    def test_decisions_and_their_history_stay(self, after):
        own = ArchitectureDecision.query.filter_by(title='Decision written by alpha').one()
        owned = ArchitectureDecision.query.filter_by(title='Decision owned by alpha').one()

        assert (own.context, own.decision, own.consequences) == (
            'Context alpha', 'Outcome alpha', 'Consequences alpha')
        assert (own.created_by_id, own.owner_id, own.owner_email) == (None, None, None)
        assert owned.owner_email is None
        history = DecisionHistory.query.filter_by(decision_id=own.id).one()
        assert history.change_reason == 'Reworded alpha'
        assert history.changed_by_id == after['zebedee'].id  # by reference: shown as Former Member

    def test_audit_entries_stay_with_the_person_redacted(self, after):
        tenant_id = after['organisation']['tenant'].id
        joined = AuditLog.query.filter_by(tenant_id=tenant_id, action_type='user_joined',
                                          actor_user_id=after['zebedee'].id).one()
        promoted = AuditLog.query.filter_by(tenant_id=tenant_id, action_type='promote_user',
                                            target_id=after['zebedee'].id).one()

        assert joined.details == {'email': 'deleted-user', 'note': 'Former Member joined',
                                  'history': [{'address': 'deleted-user'}, 7, None]}
        assert promoted.details == {'promoted': 'Former Member', 'new_role': 'steward'}

    def test_audit_entry_about_a_colleague_is_not_rewritten(self, after):
        ottoline = after['ottoline']
        joined = AuditLog.query.filter_by(action_type='user_joined', actor_user_id=ottoline.id).one()

        assert joined.details['email'] == ottoline.email
        assert joined.details['note'] == f'{ottoline.full_name} joined'

    def test_sign_in_history_stays_without_the_address_including_failed_attempts(self, after):
        tenant_domain = after['organisation']['tenant'].domain
        rows = LoginHistory.query.filter(LoginHistory.email.like('deleted-%')).all()

        assert len(rows) == 2  # the successful sign-in and the failed attempt recorded by address
        assert {row.tenant_domain for row in rows} == {tenant_domain}
        assert all(row.ip_address is None and row.user_agent is None for row in rows)
        assert after['counts']['login_history_redacted'] == 2

    def test_messages_stay_without_name_address_and_text(self, after):
        redacted = Inquiry.query.filter(Inquiry.redacted_at.isnot(None)).all()

        assert len(redacted) == 2
        assert all((row.name, row.email, row.message, row.user_id) == (None, None, None, None) for row in redacted)

    def test_domain_request_keeps_its_status_without_the_requester(self, after):
        approval = DomainApproval.query.filter_by(domain=DOMAIN).one()

        assert approval.status == 'approved'
        assert (approval.requested_by_email, approval.requested_by_name) == (None, None)
        elsewhere = DomainApproval.query.filter_by(domain='elsewhere.test').one()
        assert elsewhere.requested_by_name == after['barnaby'].full_name

    def test_team_profile_answer_stays_with_the_organisation(self, after):
        tenant = db.session.get(Tenant, after['organisation']['tenant'].id)

        assert tenant.team_focus == 'Clinical protocols'
        assert tenant.team_profile_answered_by_id is None

    def test_api_key_is_revoked_and_loses_the_name_the_person_gave_it(self, after):
        key = AIApiKey.query.filter_by(user_id=after['zebedee'].id).one()

        assert key.revoked_at is not None
        assert key.name == 'Deleted key'
        assert key.description is None
        colleague = AIApiKey.query.filter_by(user_id=after['ottoline'].id).one()
        assert colleague.revoked_at is None and colleague.name == "Ottoline's laptop key"

    def test_ai_usage_record_stays_without_the_query(self, after):
        log = AIInteractionLog.query.filter_by(user_id=after['zebedee'].id).one()

        assert log.query_text is None
        assert log.decision_count == 1
        assert after['counts']['ai_queries_cleared'] == 1
        assert AIInteractionLog.query.filter_by(user_id=after['ottoline'].id).one().query_text

    def test_teams_channel_conversation_stays_usable_without_the_person(self, after):
        references = TeamsConversationReference.query.filter(sa.or_(
            TeamsConversationReference.conversation_id.like('%alpha%'),
            TeamsConversationReference.conversation_id.like('%zebedee%'))).all()

        assert [reference.context_type for reference in references] == ['channel']
        reference = json.loads(references[0].reference_json)
        assert 'user' not in reference
        # What a proactive message needs is still there
        assert reference['serviceUrl'] == 'https://smba.example/emea/'
        assert reference['conversation']['id'] == '19:channel-alpha@thread.tacv2'
        assert after['counts']['teams_conversations'] == 2

    def test_teams_conversations_of_a_colleague_are_untouched(self, after):
        references = TeamsConversationReference.query.filter(
            TeamsConversationReference.reference_json.like('%aad-ottoline-0001%')).all()

        assert sorted(reference.context_type for reference in references) == ['channel', 'personal']
        assert all(json.loads(reference.reference_json)['user']['name'] == 'Ottoline Wrenfield'
                   for reference in references)

    def test_rows_that_only_described_the_person_are_gone(self, after):
        user_id = after['zebedee'].id

        for model in (TenantMembership, WebAuthnCredential, Subscription, SetupToken, RoleRequest,
                      SlackUserMapping, TeamsUserMapping):
            assert model.query.filter_by(user_id=user_id).count() == 0, model.__name__
        assert UserConsent.query.filter_by(user_id=user_id).count() == 2  # the choices stay, the IP goes
        assert all(consent.ip_address is None for consent in UserConsent.query.filter_by(user_id=user_id))

    def test_rows_keyed_by_the_address_are_gone_whatever_its_case(self, after):
        address = after['zebedee'].email

        assert AccessRequest.query.filter(sa.func.lower(AccessRequest.email) == address).count() == 0
        assert EmailVerification.query.filter(sa.func.lower(EmailVerification.email) == address).count() == 0
        assert SetupToken.query.filter(sa.func.lower(SetupToken.email) == address).count() == 0
        assert SlackUserMapping.query.filter(sa.func.lower(SlackUserMapping.slack_email) == address).count() == 0
        # the colleague's are all still there
        other = after['ottoline'].email
        assert AccessRequest.query.filter(sa.func.lower(AccessRequest.email) == other).count() == 1
        assert SlackUserMapping.query.filter(sa.func.lower(SlackUserMapping.slack_email) == other).count() == 2

    def test_counts_are_numbers_only(self, after):
        counts = after['counts']

        assert all(isinstance(value, int) for value in counts.values()), counts
        assert counts['role_requests'] == 1
        assert counts['slack_user_mappings'] == 2
        assert counts['audit_entries_redacted'] == 2
        assert counts['domain_approvals_redacted'] == 1


# ==================== Names that could be mistaken ====================

class TestRedactionDoesNotOverreach:

    def test_a_short_name_inside_another_word_is_not_replaced(self, app):
        organisation = make_organisation(DOMAIN, 'alpha')
        al = make_person(organisation, 'Al', 'Ng', 'charlie', '198.51.100.11')
        tenant_id = organisation['tenant'].id
        db.session.add(AuditLog(tenant_id=tenant_id, actor_user_id=organisation['admin'].id,
                                action_type='update_setting', details={'note': 'Always sign in, Al Ng said'}))
        db.session.commit()

        retention.anonymize_user(al.id)

        note = AuditLog.query.filter_by(action_type='update_setting').one().details['note']
        assert note == 'Always sign in, Former Member said'

    def test_an_account_with_no_name_is_anonymised(self, app):
        organisation = make_organisation(DOMAIN, 'alpha')
        user = User(email=f'nameless@{DOMAIN}', sso_domain=DOMAIN, auth_type='local')
        db.session.add(user)
        db.session.flush()
        db.session.add(DecisionComment(
            decision_id=self._decision(organisation).id, tenant_id=organisation['tenant'].id,
            user_id=user.id, author_display=user.email, body='A remark'))
        db.session.commit()

        assert retention.anonymize_user(user.id) is True

        assert find_everywhere(['nameless']) == {}
        assert DecisionComment.query.filter_by(body='A remark').one().author_display == 'Former Member'

    def _decision(self, organisation):
        decision = ArchitectureDecision(
            title='A decision', context='c', decision='d', consequences='q', status='accepted',
            domain=organisation['tenant'].domain, tenant_id=organisation['tenant'].id, decision_number=1,
            created_by_id=organisation['admin'].id)
        db.session.add(decision)
        db.session.flush()
        return decision


# ==================== Accounts anonymised before this was fixed ====================

class TestStartUpMigrationCleansEarlierAnonymisations:
    """Accounts anonymised by an older version keep what that version left behind until start-up."""

    def _old_style_anonymised(self, people):
        """Zebedee as the previous version left him: account anonymised, comment author text kept."""
        zebedee = people['zebedee']
        user = db.session.get(User, zebedee.id)
        user.email = 'deleted-0000@anonymized.local'
        user.name = 'Former Member'
        user.first_name = user.last_name = None
        user.is_anonymized = True
        db.session.commit()
        return zebedee

    def test_comment_author_text_api_key_names_role_requests_and_ai_queries_are_cleaned(self, people):
        import migrations
        zebedee = self._old_style_anonymised(people)

        changes = migrations.migrate_2_5_0(db)

        db.session.expire_all()
        assert changes > 0
        comments = DecisionComment.query.filter_by(user_id=zebedee.id).all()
        assert [comment.author_display for comment in comments] == ['Former Member', 'Former Member']
        key = AIApiKey.query.filter_by(user_id=zebedee.id).one()
        assert (key.name, key.description) == ('Deleted key', None)
        assert RoleRequest.query.filter_by(user_id=zebedee.id).count() == 0
        assert AIInteractionLog.query.filter_by(user_id=zebedee.id).one().query_text is None

    def test_accounts_that_are_not_anonymised_are_left_alone(self, people):
        import migrations
        self._old_style_anonymised(people)
        ottoline = people['ottoline']

        migrations.migrate_2_5_0(db)

        db.session.expire_all()
        assert DecisionComment.query.filter_by(body='Comment body bravo').one().author_display == ottoline.full_name
        assert AIApiKey.query.filter_by(user_id=ottoline.id).one().name == "Ottoline's laptop key"
        assert RoleRequest.query.filter_by(user_id=ottoline.id).count() == 1
        assert AIInteractionLog.query.filter_by(user_id=ottoline.id).one().query_text

    def test_running_it_again_changes_nothing(self, people):
        import migrations
        self._old_style_anonymised(people)
        migrations.migrate_2_5_0(db)

        assert migrations.migrate_2_5_0(db) == 0

    def test_it_is_registered_to_run_at_start_up(self, app):
        import migrations

        versions = [migration['version'] for migration in migrations.MIGRATIONS]
        assert '2.5.0' in versions
        assert versions == sorted(versions, key=lambda v: tuple(int(part) for part in v.split('.')))
