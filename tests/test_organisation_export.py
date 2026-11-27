"""
The export of a whole organisation (POST /api/tenant/export).

Published (Terms): "You may export your data at any time." Administrators can
export their organisation's decisions as one ZIP file (JSON and Markdown) from
Organisation settings; each person can export their own data from their
profile (tests/test_personal_data_export.py).

Two organisations, each with a member who has a row in every place that holds
personal data (tests/personal_data_test_data.py), plus decisions with history,
comments, links and spaces. The export of one must hold its content and must
not hold anything of the other, nor anything that lets someone sign in or act.

`build_organisation_export` is tested on the shared `app` fixture, so CI also
runs it on PostgreSQL. The endpoint is tested through the real app.
"""
import io
import json
import os
import sys
import zipfile
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import organisation_export
from organisation_export import build_organisation_export, slugify
from models import (
    db, User, Tenant, TenantMembership, TenantSettings, AuditLog, AuthConfig, ArchitectureDecision,
    DecisionComment, DecisionHistory, DecisionRelationship, DecisionSpace, Space, GlobalRole, SSOConfig,
    EmailConfig, MasterAccount,
)
from tests.app_test_utils import load_test_app
from tests.personal_data_test_data import make_organisation, make_person

DOMAIN_A = 'alpha-export.test'
DOMAIN_B = 'omega-export.test'
SSO_SECRET = 'sso-client-secret-alpha-9f2c'
SMTP_SECRET = 'smtp-password-alpha-77e1'


def _naive(value):
    return value.replace(tzinfo=None)


def make_world():
    """Organisations A and B with content; returns what the tests look for."""
    now = _naive(datetime.now(timezone.utc))
    a = make_organisation(DOMAIN_A, 'alpha')
    b = make_organisation(DOMAIN_B, 'omega')
    zebedee = make_person(a, 'Zebedee', 'Quillfeather', 'alpha', '198.51.100.77')
    barnaby = make_person(b, 'Barnaby', 'Thistlewood', 'omega', '198.51.100.99')
    tenant_a = a['tenant']
    admin_a = a['admin']
    for organisation in (a, b):
        organisation['admin'].set_password('a-long-test-password')

    db.session.add_all([
        AuthConfig(domain=DOMAIN_A, tenant_prefix='ZQL'),
        AuthConfig(domain=DOMAIN_B, tenant_prefix='BTW'),
        SSOConfig(domain=DOMAIN_A, provider_name='Alpha IdP', client_id='alpha-client',
                  client_secret=SSO_SECRET, discovery_url='https://idp.alpha-export.test/.well-known'),
        EmailConfig(domain=DOMAIN_A, smtp_server='smtp.alpha-export.test', smtp_port=587,
                    smtp_username='mailer', smtp_password=SMTP_SECRET, from_email='noreply@alpha-export.test'),
    ])
    settings = TenantSettings.query.filter_by(tenant_id=tenant_a.id).one()
    settings.decision_template_id = 'governance'

    steward = User(email=f'steward@{DOMAIN_A}', sso_domain=DOMAIN_A, auth_type='local', email_verified=True)
    steward.set_name(first_name='Stella', last_name='Steward')
    steward.set_password('a-long-test-password')
    member = User(email=f'member@{DOMAIN_A}', sso_domain=DOMAIN_A, auth_type='local', email_verified=True)
    member.set_name(first_name='Mo', last_name='Member')
    member.set_password('a-long-test-password')
    db.session.add_all([steward, member])
    db.session.flush()
    db.session.add_all([
        TenantMembership(user_id=steward.id, tenant_id=tenant_a.id, global_role=GlobalRole.STEWARD),
        TenantMembership(user_id=member.id, tenant_id=tenant_a.id, global_role=GlobalRole.USER),
    ])

    general = Space(tenant_id=tenant_a.id, name='General', is_default=True, created_by_id=admin_a.id)
    hiring = Space(tenant_id=tenant_a.id, name='Hiring', description='People decisions')
    db.session.add_all([general, hiring])
    db.session.flush()

    rich = ArchitectureDecision(
        title='Hire a second nurse for nights: Ünïcode & more', context='Nights are short of staff',
        decision='Hire one more nurse', consequences='Higher payroll, safer nights', status='accepted',
        decision_type='Policy', domain=DOMAIN_A, tenant_id=tenant_a.id, decision_number=10,
        created_by_id=admin_a.id, updated_by_id=member.id, owner_id=member.id)
    older = ArchitectureDecision(
        title='One nurse for nights', context='Old context', decision='Keep one nurse',
        consequences='Cheaper', status='superseded', domain=DOMAIN_A, tenant_id=tenant_a.id,
        decision_number=11, created_by_id=admin_a.id)
    gone = ArchitectureDecision(
        title='Deleted decision alpha', context='Deleted context alpha', decision='Deleted outcome alpha',
        consequences='Deleted consequences alpha', status='proposed', domain=DOMAIN_A, tenant_id=tenant_a.id,
        decision_number=12, created_by_id=admin_a.id, deleted_at=now, deleted_by_id=admin_a.id)
    db.session.add_all([rich, older, gone])
    db.session.flush()

    db.session.add_all([
        DecisionHistory(decision_id=rich.id, title='Hire a nurse', context='Before', decision_text='Maybe hire',
                        status='proposed', consequences='Unknown', change_reason='Agreed at the board',
                        changed_by_id=member.id, changed_at=now - timedelta(days=2)),
        DecisionComment(decision_id=rich.id, tenant_id=tenant_a.id, user_id=member.id,
                        body='We should start in March', created_at=now - timedelta(days=1)),
        DecisionComment(decision_id=rich.id, tenant_id=tenant_a.id, user_id=None,
                        author_display='Slack person', body='From Slack: agreed', created_at=now),
        DecisionComment(decision_id=rich.id, tenant_id=tenant_a.id, user_id=member.id,
                        body='Removed comment alpha', deleted_at=now, deleted_by_id=admin_a.id),
        DecisionComment(decision_id=gone.id, tenant_id=tenant_a.id, user_id=member.id,
                        body='Comment on a deleted decision alpha'),
        DecisionRelationship(tenant_id=tenant_a.id, source_decision_id=rich.id, target_decision_id=older.id,
                             relationship_type='supersedes', notes='Replaces the old staffing rule'),
        DecisionRelationship(tenant_id=tenant_a.id, source_decision_id=rich.id, target_decision_id=gone.id,
                             relationship_type='related_to', notes='Link to deleted alpha'),
        DecisionRelationship(tenant_id=tenant_a.id, source_decision_id=older.id, target_decision_id=rich.id,
                             relationship_type='related_to', notes='Removed link alpha', deleted_at=now),
        DecisionSpace(decision_id=rich.id, space_id=general.id),
        DecisionSpace(decision_id=rich.id, space_id=hiring.id),
        DecisionSpace(decision_id=gone.id, space_id=hiring.id),
    ])
    db.session.commit()
    return {
        'tenant_a': tenant_a, 'tenant_b': b['tenant'], 'admin_a': admin_a, 'admin_b': b['admin'],
        'steward': steward, 'member': member, 'zebedee': zebedee, 'barnaby': barnaby,
        'rich': rich, 'older': older, 'gone': gone, 'general': general, 'hiring': hiring,
    }


def unzip(content):
    archive = zipfile.ZipFile(io.BytesIO(content))
    return {name: archive.read(name).decode('utf-8') for name in archive.namelist()}


def all_text(files):
    return '\n'.join(files.values())


def secrets_of(world):
    """Values that let someone sign in or act, and sign-in details: never in an export."""
    values = [SSO_SECRET, SMTP_SECRET, 'keyhash-alpha', 'tokenhash-', 'verify-zebedee', 'credential-zebedee',
              'public-key-zebedee', 'idp|zebedee', '198.51.100.77', 'ZebedeeBrowser', 'oauth-']
    for user in (world['admin_a'], world['member'], world['steward'], world['zebedee'].user):
        values.append(user.password_hash)
    return values


def other_organisation(world):
    barnaby = world['barnaby']
    return [DOMAIN_B, 'omega', barnaby.first.lower(), barnaby.last.lower(), barnaby.ip, 'btw-']


@pytest.fixture
def world(app):
    return make_world()


@pytest.fixture
def files(world):
    content, _summary = build_organisation_export(world['tenant_a'], world['admin_a'])
    return unzip(content)


# ==================== What the ZIP holds ====================

class TestContents:

    def test_the_files(self, files):
        names = set(files)
        assert set(organisation_export.FILES) <= names
        markdown = sorted(name for name in names if name.startswith('decisions/'))
        assert markdown == [
            'decisions/ZQL-001-decision-written-by-alpha.md',
            'decisions/ZQL-002-decision-owned-by-alpha.md',
            'decisions/ZQL-010-hire-a-second-nurse-for-nights-unicode-more.md',
            'decisions/ZQL-011-one-nurse-for-nights.md',
        ]
        assert names == set(organisation_export.FILES) | set(markdown)

    def test_every_decision_that_was_not_deleted(self, files, world):
        decisions = json.loads(files['decisions.json'])['decisions']
        assert [d['display_id'] for d in decisions] == ['ZQL-001', 'ZQL-002', 'ZQL-010', 'ZQL-011']
        assert 'Deleted' not in files['decisions.json']
        assert all('deleted' not in text.lower() for name, text in files.items() if name.startswith('decisions/'))

    def test_display_id_is_the_one_the_app_shows(self, files, world):
        decisions = {d['id']: d for d in json.loads(files['decisions.json'])['decisions']}
        for decision_id in (world['rich'].id, world['older'].id):
            decision = db.session.get(ArchitectureDecision, decision_id)
            assert decisions[decision_id]['display_id'] == decision.get_display_id()

    def test_a_decision_with_history_comments_links_and_spaces_round_trips(self, files, world):
        decisions = {d['id']: d for d in json.loads(files['decisions.json'])['decisions']}
        rich = decisions[world['rich'].id]
        member, admin = world['member'], world['admin_a']

        assert {key: rich[key] for key in ('title', 'status', 'decision_type', 'context', 'decision',
                                           'consequences', 'decision_number')} == {
            'title': 'Hire a second nurse for nights: Ünïcode & more', 'status': 'accepted',
            'decision_type': 'Policy', 'context': 'Nights are short of staff', 'decision': 'Hire one more nurse',
            'consequences': 'Higher payroll, safer nights', 'decision_number': 10}
        assert rich['owner'] == {'id': member.id, 'name': 'Mo Member'}
        assert rich['created_by'] == {'id': admin.id, 'name': 'Organisation Administrator'}
        assert rich['updated_by'] == {'id': member.id, 'name': 'Mo Member'}
        assert rich['owner_email'] is None
        assert rich['created_at'] and rich['updated_at']
        assert [space['name'] for space in rich['spaces']] == ['General', 'Hiring']

        assert [(c['author'], c['author_display'], c['body']) for c in rich['comments']] == [
            ({'id': member.id, 'name': 'Mo Member'}, None, 'We should start in March'),
            (None, 'Slack person', 'From Slack: agreed')]
        (change,) = rich['history']
        assert change['changed_by'] == {'id': member.id, 'name': 'Mo Member'}
        assert (change['title'], change['decision'], change['change_reason']) == (
            'Hire a nurse', 'Maybe hire', 'Agreed at the board')

        (link,) = rich['relationships']
        assert (link['direction'], link['relationship_type'], link['notes']) == (
            'outgoing', 'supersedes', 'Replaces the old staffing rule')
        assert link['decision'] == {'id': world['older'].id, 'display_id': 'ZQL-011', 'title': 'One nurse for nights'}
        (incoming,) = decisions[world['older'].id]['relationships']
        assert incoming['direction'] == 'incoming'
        assert incoming['decision']['id'] == world['rich'].id

        assert rich['markdown_file'] == 'decisions/ZQL-010-hire-a-second-nurse-for-nights-unicode-more.md'

    def test_people_are_named_by_id_and_name_only(self, files, world):
        decisions = json.loads(files['decisions.json'])['decisions']
        people = [d[key] for d in decisions for key in ('owner', 'created_by', 'updated_by') if d[key]]
        people += [c['author'] for d in decisions for c in d['comments'] if c['author']]
        assert people and all(set(person) == {'id', 'name'} for person in people)

    def test_removed_comments_and_links_to_deleted_decisions_are_left_out(self, files):
        text = all_text(files)
        assert 'Removed comment alpha' not in text
        assert 'Comment on a deleted decision alpha' not in text
        assert 'Link to deleted alpha' not in text
        assert 'Removed link alpha' not in text

    def test_markdown_uses_the_template_headings(self, files, world):
        markdown = files['decisions/ZQL-010-hire-a-second-nurse-for-nights-unicode-more.md']
        from decision_templates import get_template
        sections = get_template('governance')['sections']
        assert markdown.startswith('# ZQL-010: Hire a second nurse for nights: Ünïcode & more\n')
        for key in ('context', 'decision', 'consequences'):
            assert f"## {sections[key]['label']}\n" in markdown
        assert '- Status: accepted' in markdown
        assert '- Owner: Mo Member' in markdown
        assert '- Spaces: General, Hiring' in markdown
        assert 'Higher payroll, safer nights' in markdown
        assert '## Related decisions' in markdown and 'ZQL-011: One nurse for nights' in markdown
        assert '**Mo Member**' in markdown and 'We should start in March' in markdown
        assert '**Slack person**' in markdown
        assert 'Agreed at the board' in markdown

    def test_spaces(self, files, world):
        spaces = {s['name']: s for s in json.loads(files['spaces.json'])['spaces']}
        assert set(spaces) == {'General', 'Hiring'}
        assert spaces['General']['is_default'] is True
        assert spaces['General']['created_by'] == {'id': world['admin_a'].id, 'name': 'Organisation Administrator'}
        # The deleted decision is in Hiring in the database, not in the export
        assert spaces['Hiring']['decision_ids'] == [world['rich'].id]

    def test_template(self, files):
        templates = json.loads(files['templates.json'])
        assert templates['decision_template']['id'] == 'governance'
        assert templates['decision_template']['chosen_by_organisation'] is True
        assert set(templates['decision_template']['template']['sections']) == {'context', 'decision', 'consequences'}
        assert any(item['key'] == 'supersedes' for item in templates['relationship_types'])

    def test_members(self, files, world):
        members = {m['email']: m for m in json.loads(files['members.json'])['members']}
        assert set(members) == {f'administrator@{DOMAIN_A}', f'steward@{DOMAIN_A}', f'member@{DOMAIN_A}',
                                world['zebedee'].email}
        assert members[f'steward@{DOMAIN_A}']['role'] == 'steward'
        assert members[f'administrator@{DOMAIN_A}']['role'] == 'admin'
        assert members[f'member@{DOMAIN_A}'] == {
            'id': world['member'].id, 'name': 'Mo Member', 'email': f'member@{DOMAIN_A}', 'role': 'user',
            'joined_at': members[f'member@{DOMAIN_A}']['joined_at']}
        assert members[f'member@{DOMAIN_A}']['joined_at']

    def test_a_removed_account_is_not_a_member(self, world):
        world['member'].deleted_at = _naive(datetime.now(timezone.utc))
        world['member'].is_anonymized = True
        db.session.commit()
        content, _ = build_organisation_export(world['tenant_a'], world['admin_a'])
        emails = [m['email'] for m in json.loads(unzip(content)['members.json'])['members']]
        assert f'member@{DOMAIN_A}' not in emails

    def test_audit_log(self, files, world):
        entries = json.loads(files['audit-log.json'])['entries']
        actions = [entry['action'] for entry in entries]
        assert 'user_joined' in actions and 'promote_user' in actions
        joined = next(entry for entry in entries if entry['action'] == 'user_joined')
        assert joined['actor'] == {'id': world['zebedee'].id, 'name': 'Zebedee Quillfeather'}

    def test_audit_details_never_carry_a_secret_key(self, world):
        db.session.add(AuditLog(tenant_id=world['tenant_a'].id, actor_user_id=world['admin_a'].id,
                                action_type='change_setting', target_entity='tenant_settings',
                                details={'setting': 'sso', 'client_secret': 'leaked-secret-1',
                                         'nested': {'api_key': 'leaked-secret-2', 'kept': 'visible'},
                                         'list': [{'access_token': 'leaked-secret-3'}]}))
        db.session.commit()
        content, _ = build_organisation_export(world['tenant_a'], world['admin_a'])
        text = unzip(content)['audit-log.json']
        assert 'leaked-secret' not in text
        assert 'visible' in text and '"setting": "sso"' in text

    def test_readme_says_what_when_who_and_what_is_left_out(self, world):
        made = datetime(2026, 11, 27, 9, 30, tzinfo=timezone.utc)
        content, _ = build_organisation_export(world['tenant_a'], world['admin_a'], now=made)
        readme = unzip(content)['README.txt']
        assert '2026-11-27T09:30:00+00:00' in readme
        assert f'Organisation Administrator (administrator@{DOMAIN_A})' in readme
        for name in ('decisions.json', 'decisions/', 'spaces.json', 'templates.json', 'members.json',
                     'audit-log.json'):
            assert name in readme
        for left_out in ('Sign-in history', 'API keys', 'tokens', 'secrets', 'Server logs',
                         'another organisation'):
            assert left_out in readme

    def test_an_organisation_with_nothing(self, app):
        tenant = Tenant(domain='empty-export.test', name='Empty')
        db.session.add(tenant)
        db.session.flush()
        admin = User(email='admin@empty-export.test', sso_domain='empty-export.test', is_admin=True)
        db.session.add(admin)
        db.session.commit()

        content, summary = build_organisation_export(tenant, admin)
        files = unzip(content)
        assert json.loads(files['decisions.json'])['decisions'] == []
        assert summary['decisions'] == 0
        assert '/' not in ''.join(name for name in files if name.startswith('decisions/'))


# ==================== Nothing that is not the organisation's ====================

class TestNothingElse:

    def test_nothing_that_lets_someone_sign_in_or_act(self, files, world):
        text = all_text(files)
        for value in secrets_of(world):
            assert value not in text, value
        assert '"password' not in text and 'key_hash' not in text and 'token_hash' not in text

    def test_no_sign_in_history(self, files):
        assert 'login_history' not in all_text(files)
        assert 'Browser/1.0' not in all_text(files)

    def test_nothing_of_the_other_organisation(self, files, world):
        text = all_text(files).lower()
        for needle in other_organisation(world):
            assert needle.lower() not in text, needle

    def test_each_organisation_gets_its_own(self, world):
        content, _ = build_organisation_export(world['tenant_b'], world['admin_b'])
        text = all_text(unzip(content)).lower()
        assert 'omega' in text
        for needle in ('alpha', 'zebedee', 'quillfeather', 'nurse', DOMAIN_A):
            assert needle not in text, needle

    def test_a_person_of_another_organisation_is_never_named(self, world):
        """Should a row point at someone outside the organisation, they are shown as nobody."""
        rich = db.session.get(ArchitectureDecision, world['rich'].id)
        rich.owner_id = world['barnaby'].id
        db.session.add(DecisionComment(decision_id=rich.id, tenant_id=world['tenant_a'].id,
                                       user_id=world['barnaby'].id, body='Odd comment'))
        db.session.commit()

        content, _ = build_organisation_export(world['tenant_a'], world['admin_a'])
        files = unzip(content)
        decision = next(d for d in json.loads(files['decisions.json'])['decisions'] if d['id'] == rich.id)
        assert decision['owner'] is None
        assert next(c for c in decision['comments'] if c['body'] == 'Odd comment')['author'] is None
        assert 'thistlewood' not in all_text(files).lower() and 'barnaby' not in all_text(files).lower()

    def test_a_link_into_another_organisation_is_left_out(self, world):
        foreign = ArchitectureDecision.query.filter_by(domain=DOMAIN_B).first()
        db.session.add(DecisionRelationship(tenant_id=world['tenant_a'].id, source_decision_id=world['rich'].id,
                                            target_decision_id=foreign.id, relationship_type='related_to',
                                            notes='Cross link'))
        db.session.commit()
        content, _ = build_organisation_export(world['tenant_a'], world['admin_a'])
        text = all_text(unzip(content))
        assert 'Cross link' not in text and foreign.title not in text


# ==================== Size guard ====================

class TestSizeGuard:

    def test_refused_before_reading_when_the_stored_text_is_too_large(self, world, monkeypatch):
        monkeypatch.setattr(organisation_export, 'MAX_EXPORT_BYTES', 100)
        collected = []
        monkeypatch.setattr(organisation_export, '_collect', lambda tenant: collected.append(tenant))

        with pytest.raises(organisation_export.ExportTooLarge):
            build_organisation_export(world['tenant_a'], world['admin_a'])
        assert collected == []

    def test_refused_while_writing_when_the_files_are_too_large(self, world, monkeypatch):
        monkeypatch.setattr(organisation_export, 'estimate_size', lambda tenant: 0)
        monkeypatch.setattr(organisation_export, 'MAX_EXPORT_BYTES', 2000)

        with pytest.raises(organisation_export.ExportTooLarge):
            build_organisation_export(world['tenant_a'], world['admin_a'])

    def test_estimate_counts_the_text(self, world):
        size = organisation_export.estimate_size(world['tenant_a'])
        assert size >= 2 * len('Nights are short of staff')
        assert organisation_export.MAX_EXPORT_BYTES == 100 * 1024 * 1024


def test_slugify():
    assert slugify('Hire a nurse: Ünïcode & more!') == 'hire-a-nurse-unicode-more'
    assert slugify('') == 'untitled'
    assert slugify('***') == 'untitled'
    assert len(slugify('x' * 200)) == 60


# ==================== The endpoint ====================

class TestEndpoint:

    @pytest.fixture
    def real_app(self):
        app_module, test_app = load_test_app(secret_key='test-secret-key-organisation-export')
        with test_app.app_context():
            db.create_all()
            app_module.init_database()
            yield test_app
            db.session.remove()
            db.drop_all()
            app_module._db_initialized = False

    @pytest.fixture
    def people(self, real_app):
        return make_world()

    def signed_in(self, test_app, user, csrf=True):
        client = test_app.test_client()
        with client.session_transaction() as sess:
            sess['user_id'] = user.id
            sess['_csrf_token'] = 'test-csrf-token'
            sess['_expires_at'] = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        if csrf:
            client.environ_base['HTTP_X_CSRF_TOKEN'] = 'test-csrf-token'
        return client

    def test_an_administrator_downloads_the_zip(self, real_app, people):
        response = self.signed_in(real_app, people['admin_a']).post('/api/tenant/export')

        assert response.status_code == 200, response.get_data(as_text=True)
        assert response.mimetype == 'application/zip'
        disposition = response.headers['Content-Disposition']
        assert disposition.startswith(f'attachment; filename="decision-records-{DOMAIN_A}-')
        assert disposition.endswith('.zip"')
        assert response.headers['Cache-Control'] == 'no-store'
        files = unzip(response.data)
        assert len(json.loads(files['decisions.json'])['decisions']) == 4
        text = all_text(files).lower()
        for needle in other_organisation(people):
            assert needle.lower() not in text

    def test_the_export_is_audit_logged(self, real_app, people):
        self.signed_in(real_app, people['admin_a']).post('/api/tenant/export')

        entry = AuditLog.query.filter_by(action_type='organisation_data_exported').one()
        assert (entry.tenant_id, entry.actor_user_id, entry.target_entity) == (
            people['tenant_a'].id, people['admin_a'].id, 'tenant')
        assert entry.details['decisions'] == 4 and entry.details['files'] == 10

    def test_a_promoted_administrator_without_the_legacy_flag_can_export(self, real_app, people):
        membership = TenantMembership.query.filter_by(user_id=people['member'].id).one()
        membership.global_role = GlobalRole.ADMIN
        db.session.commit()

        assert self.signed_in(real_app, people['member']).post('/api/tenant/export').status_code == 200

    @pytest.mark.parametrize('who', ['steward', 'member'])
    def test_a_member_who_is_not_an_administrator_is_refused(self, real_app, people, who):
        response = self.signed_in(real_app, people[who]).post('/api/tenant/export')

        assert response.status_code == 403
        assert 'administrators' in response.get_json()['error']
        assert AuditLog.query.filter_by(action_type='organisation_data_exported').count() == 0

    def test_an_administrator_of_a_cannot_export_b(self, real_app, people):
        """The request names no organisation: whatever it says, the caller's own is exported."""
        client = self.signed_in(real_app, people['admin_a'])
        response = client.post(f'/api/tenant/export?domain={DOMAIN_B}&tenant_id={people["tenant_b"].id}',
                               json={'domain': DOMAIN_B, 'tenant_id': people['tenant_b'].id})

        assert response.status_code == 200
        text = all_text(unzip(response.data)).lower()
        assert 'omega' not in text and DOMAIN_B not in text
        assert 'nurse' in text

    def test_an_administrator_of_b_gets_b_only(self, real_app, people):
        response = self.signed_in(real_app, people['admin_b']).post('/api/tenant/export')

        text = all_text(unzip(response.data)).lower()
        assert 'omega' in text and 'nurse' not in text and 'alpha' not in text

    def test_an_administrator_flag_of_another_domain_does_not_count(self, real_app, people):
        """A membership of another organisation gives no right to export this one."""
        db.session.add(TenantMembership(user_id=people['member'].id, tenant_id=people['tenant_b'].id,
                                        global_role=GlobalRole.ADMIN))
        db.session.commit()

        assert self.signed_in(real_app, people['member']).post('/api/tenant/export').status_code == 403

    def test_anonymous_caller_is_refused(self, real_app, people):
        assert real_app.test_client().post('/api/tenant/export').status_code == 401

    def test_get_is_not_allowed(self, real_app, people):
        assert self.signed_in(real_app, people['admin_a']).get('/api/tenant/export').status_code == 405

    def test_without_the_csrf_token_it_is_refused(self, real_app, people):
        response = self.signed_in(real_app, people['admin_a'], csrf=False).post('/api/tenant/export')

        assert response.status_code == 403
        assert 'CSRF' in response.get_json()['error']

    def test_a_super_admin_is_refused(self, real_app, people):
        master = MasterAccount(username='export-master', name='Master')
        master.set_password('a-long-master-password')
        db.session.add(master)
        db.session.commit()
        client = real_app.test_client()
        with client.session_transaction() as sess:
            sess['is_master'] = True
            sess['master_id'] = master.id
            sess['_csrf_token'] = 'test-csrf-token'
            sess['_expires_at'] = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        client.environ_base['HTTP_X_CSRF_TOKEN'] = 'test-csrf-token'

        assert client.post('/api/tenant/export').status_code == 403

    def test_too_large_is_refused_with_a_clear_message(self, real_app, people, monkeypatch):
        monkeypatch.setattr(organisation_export, 'MAX_EXPORT_BYTES', 100)

        response = self.signed_in(real_app, people['admin_a']).post('/api/tenant/export')

        assert response.status_code == 413
        assert 'Contact support' in response.get_json()['error']
        assert AuditLog.query.filter_by(action_type='organisation_data_exported').count() == 0

    def test_an_organisation_is_exported_at_most_ten_times_an_hour(self, real_app, people):
        client = self.signed_in(real_app, people['admin_a'])
        for _ in range(organisation_export.EXPORTS_PER_HOUR):
            assert client.post('/api/tenant/export').status_code == 200

        response = client.post('/api/tenant/export')
        assert response.status_code == 429
        assert response.headers['Retry-After'] == '3600'
        # Counted per organisation: another organisation is not affected
        assert self.signed_in(real_app, people['admin_b']).post('/api/tenant/export').status_code == 200

    def test_exports_older_than_an_hour_do_not_count(self, real_app, people):
        old = _naive(datetime.now(timezone.utc) - timedelta(hours=2))
        for _ in range(organisation_export.EXPORTS_PER_HOUR):
            db.session.add(AuditLog(tenant_id=people['tenant_a'].id, actor_user_id=people['admin_a'].id,
                                    action_type='organisation_data_exported', created_at=old))
        db.session.commit()

        assert self.signed_in(real_app, people['admin_a']).post('/api/tenant/export').status_code == 200
