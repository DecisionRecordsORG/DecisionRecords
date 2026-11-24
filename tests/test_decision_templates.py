"""
Decision templates: the catalogue (five templates and the NACE Rev. 2.1
industry sections that suggest one), a tenant's choice of template and
industry, the optional type on a decision, and assigning types in bulk.

Switching template must never read or rewrite a decision; a stored type
that the new template lacks is kept as it is.
"""
import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import decision_relationships as dr
import decision_templates as dt
from models import (
    db, User, Tenant, TenantMembership, TenantSettings, GlobalRole, MaturityState, AuditLog,
    ArchitectureDecision, DecisionHistory, DEFAULT_MASTER_PASSWORD, DEFAULT_MASTER_USERNAME,
)
from tests.app_test_utils import load_test_app


PASSWORD = 'testpassword123'
CATALOG_URL = '/api/decision-templates/catalog'
URL = '/api/tenant/decision-template'
NOTICE_URL = '/api/tenant/decision-template/dismiss-notice'
BULK_URL = '/api/tenant/decisions/bulk-type'

# NACE Rev. 2.1 sections as published by Eurostat. Written out here on purpose:
# the test fails if a title in the catalogue is reworded.
NACE_REV_2_1 = [
    ('A', 'Agriculture, forestry and fishing'),
    ('B', 'Mining and quarrying'),
    ('C', 'Manufacturing'),
    ('D', 'Electricity, gas, steam and air conditioning supply'),
    ('E', 'Water supply; sewerage, waste management and remediation activities'),
    ('F', 'Construction'),
    ('G', 'Wholesale and retail trade'),
    ('H', 'Transportation and storage'),
    ('I', 'Accommodation and food service activities'),
    ('J', 'Publishing, broadcasting, and content production and distribution activities'),
    ('K', 'Telecommunication, computer programming, consulting, computing infrastructure '
          'and other information service activities'),
    ('L', 'Financial and insurance activities'),
    ('M', 'Real estate activities'),
    ('N', 'Professional, scientific and technical activities'),
    ('O', 'Administrative and support service activities'),
    ('P', 'Public administration and defence; compulsory social security'),
    ('Q', 'Education'),
    ('R', 'Human health and social work activities'),
    ('S', 'Arts, sports and recreation'),
    ('T', 'Other service activities'),
    ('U', 'Activities of households as employers and undifferentiated goods- and '
          'service-producing activities of households for own use'),
    ('V', 'Activities of extraterritorial organisations and bodies'),
]

EXPECTED_SUGGESTIONS = {
    **{letter: 'controlled_change' for letter in 'BCDEF'},
    'K': 'software',
    'L': 'investment',
    **{letter: 'governance' for letter in 'PQRV'},
    **{letter: 'general' for letter in 'AGHIJMNOSTU'},
}

GUARANTEE = (
    'Changing the template changes headings and prompts only. '
    'Your decisions are not altered, and you can change back at any time.'
)


# ==================== Catalogue (no database) ====================

class TestCatalogue:

    def test_industry_list_is_nace_rev_2_1_verbatim(self):
        assert [(s['code'], s['title']) for s in dt.NACE_SECTIONS] == NACE_REV_2_1
        assert len(dt.NACE_SECTIONS) == 22

    def test_every_section_suggests_an_existing_template(self):
        catalog = dt.get_decision_template_catalog()
        template_ids = {template['id'] for template in catalog['templates']}
        suggestions = {i['code']: i['suggested_template_id'] for i in catalog['industries']}

        assert suggestions == EXPECTED_SUGGESTIONS
        assert set(suggestions.values()) <= template_ids
        assert set(dt.SECTION_TEMPLATE_IDS) <= set(dt.NACE_SECTION_INDEX)

    def test_no_section_and_unknown_section_suggest_general(self):
        assert dt.suggested_template_id(None) == 'general'
        assert dt.suggested_template_id('') == 'general'
        assert dt.suggested_template_id('Z') == 'general'

    def test_the_five_templates(self):
        assert [(t['id'], t['label']) for t in dt.DECISION_TEMPLATES] == [
            ('general', 'General'),
            ('software', 'Software and technology'),
            ('controlled_change', 'Controlled change'),
            ('governance', 'Governance and committee'),
            ('investment', 'Investment and approval'),
        ]
        assert dt.DEFAULT_TEMPLATE_ID == 'general'

    def test_section_headings(self):
        headings = {
            t['id']: tuple(t['sections'][key]['label'] for key in dt.SECTION_KEYS)
            for t in dt.DECISION_TEMPLATES
        }
        assert headings == {
            'general': ('Context', 'Decision', 'Consequences'),
            'software': ('Context', 'Decision', 'Consequences'),
            'controlled_change': ('Change and reason', 'Decision and approval', 'Impact and follow-up'),
            'governance': ('Matter and background', 'Decision and reasons',
                           'Alternatives, interests and implications'),
            'investment': ('Proposal and assessment', 'Decision and conditions', 'Risks and monitoring'),
        }

    def test_every_template_is_complete(self):
        for template in dt.DECISION_TEMPLATES:
            assert set(template['sections']) == set(dt.SECTION_KEYS)
            for field in [template['title'], *template['sections'].values()]:
                assert field['placeholder'].strip() and field['hint'].strip()
            types = template['decision_types']
            assert types and len(types) == len(set(types))
            assert all(0 < len(t) <= dt.DECISION_TYPE_MAX_LENGTH and t == t.strip() for t in types)
            assert len(template['example_titles']) == 2
            assert template['title']['placeholder'] == f"For example: {template['example_titles'][0]}"

    def test_suggested_packs_exist_and_include_core(self):
        for template in dt.DECISION_TEMPLATES:
            assert template['suggested_pack_ids'][0] == 'core'
            assert set(template['suggested_pack_ids']) <= set(dr.PACK_INDEX)
        labels = {
            t['id']: [p['label'] for p in t['suggested_packs']]
            for t in dt.get_decision_template_catalog()['templates']
        }
        assert labels['general'] == ['Core', 'People & Policy', 'Finance & Procurement', 'Product & Customer']
        assert labels['software'] == [
            'Core', 'Software Delivery', 'Data & Analytics', 'Security & Risk', 'Operations & Service']
        assert labels['controlled_change'] == ['Core', 'Operations & Service', 'Security & Risk']
        assert labels['governance'] == ['Core', 'People & Policy', 'Finance & Procurement']
        assert labels['investment'] == ['Core', 'Finance & Procurement', 'Security & Risk']

    def test_the_two_cautions(self):
        cautions = {t['id']: t['caution'] for t in dt.DECISION_TEMPLATES}
        assert cautions == {
            'general': None,
            'software': None,
            'controlled_change': 'This layout follows common change-record practice. '
                                 'It does not replace your quality or safety management system.',
            'governance': 'Do not record decisions about identifiable patients, pupils or service users here.',
            'investment': None,
        }

    def test_no_claim_of_regulatory_compliance(self):
        text = repr(dt.get_decision_template_catalog()).lower()
        for claim in ('compliant', 'compliance', 'gxp', 'certified', 'meets regulation', 'iso '):
            assert claim not in text

    def test_general_equals_the_copy_the_form_had_before_templates(self):
        """A tenant that chooses nothing must see no change: General is the old form copy."""
        general = dt.TEMPLATE_INDEX['general']
        assert general['title'] == {
            'placeholder': 'For example: Move to quarterly pricing reviews',
            'hint': 'A short name people will recognise in a list.',
        }
        assert general['sections'] == {
            'context': {
                'label': 'Context',
                'placeholder': 'What prompted this decision? Describe the situation, the problem and '
                               'anything that limits your options.',
                'hint': 'The background someone needs to understand why this came up.',
            },
            'decision': {
                'label': 'Decision',
                'placeholder': 'What did you decide? State the choice plainly and mention the options '
                               'you turned down.',
                'hint': 'What was decided, in words that make sense on their own.',
            },
            'consequences': {
                'label': 'Consequences',
                'placeholder': 'What changes because of this? Include the benefits, the costs and the '
                               'risks you accept.',
                'hint': 'What follows from the decision, good and bad.',
            },
        }

    def test_general_equals_the_fallback_copy_in_the_web_app(self):
        """The web app keeps one fallback (used until the template has loaded); it must not drift."""
        source = (Path(__file__).resolve().parent.parent
                  / 'frontend/src/app/components/shared/decision-form-copy.ts').read_text()
        general = dt.TEMPLATE_INDEX['general']
        fields = {'title': general['title'], **general['sections']}
        for key, expected in fields.items():
            block = re.search(rf"\n  {key}: \{{(.*?)\n  \}}", source, re.S)
            assert block, key
            for name in ('placeholder', 'hint'):
                value = re.search(rf"{name}: '((?:[^'\\]|\\.)*)'", block.group(1))
                assert value and value.group(1) == expected[name], (key, name)
            if key != 'title':
                label = re.search(r"label: '([^']*)'", block.group(1))
                assert label and label.group(1) == expected['label'], key

    def test_guarantee_and_credit_wording(self):
        catalog = dt.get_decision_template_catalog()
        assert catalog['guarantee'] == GUARANTEE
        assert catalog['industry_credit'] == 'Industry sections: NACE Rev. 2.1, Eurostat, CC BY 4.0'

    def test_catalogue_is_a_copy(self):
        dt.get_decision_template_catalog()['templates'][0]['sections']['context']['label'] = 'Changed'
        assert dt.TEMPLATE_INDEX['general']['sections']['context']['label'] == 'Context'


class TestNormalisation:

    @pytest.mark.parametrize('raw, expected', [(None, None), ('', None), ('  ', None),
                                               ('general', 'general'), (' governance ', 'governance')])
    def test_template_id(self, raw, expected):
        assert dt.normalize_template_id(raw) == expected

    @pytest.mark.parametrize('raw', ['nope', 'General', 7, ['general'], {'id': 'general'}, True])
    def test_unknown_template_id_is_rejected(self, raw):
        with pytest.raises(ValueError):
            dt.normalize_template_id(raw)

    @pytest.mark.parametrize('raw, expected', [(None, None), ('', None), ('C', 'C'), ('c', 'C'), (' V ', 'V')])
    def test_industry(self, raw, expected):
        assert dt.normalize_industry(raw) == expected

    @pytest.mark.parametrize('raw', ['W', 'AA', 'Manufacturing', '1', 3, ['C']])
    def test_unknown_industry_is_rejected(self, raw):
        with pytest.raises(ValueError):
            dt.normalize_industry(raw)

    def test_decision_type(self):
        assert dt.normalize_decision_type(None, 'general') is None
        assert dt.normalize_decision_type('  ', 'general') is None
        assert dt.normalize_decision_type('Policy', None) == 'Policy'
        assert dt.normalize_decision_type(' Policy ', 'general') == 'Policy'
        assert dt.normalize_decision_type('Architecture', 'software') == 'Architecture'

    @pytest.mark.parametrize('raw', ['Architecture', 'policy', 'x' * 500, 5, ['Policy']])
    def test_type_outside_the_template_is_rejected(self, raw):
        with pytest.raises(ValueError):
            dt.normalize_decision_type(raw, 'general')

    def test_type_already_stored_stays_valid(self):
        assert dt.normalize_decision_type('Architecture', 'general', stored_type='Architecture') == 'Architecture'
        with pytest.raises(ValueError):
            dt.normalize_decision_type('Security', 'general', stored_type='Architecture')

    def test_unknown_stored_template_falls_back_to_general(self):
        assert dt.get_template('removed-later')['id'] == 'general'
        payload = dt.build_tenant_template_payload('removed-later', 'ZZ')
        assert payload['template_id'] == 'general' and payload['template_chosen'] is False
        assert payload['industry'] is None and payload['suggested_template_id'] == 'general'


# ==================== API ====================

@pytest.fixture
def api_app():
    app_module, test_app = load_test_app(secret_key='test-secret-key-decision-templates-1')
    with test_app.app_context():
        db.create_all()
        app_module.init_database()
        yield test_app
        db.session.remove()
        db.drop_all()
        app_module._db_initialized = False


def make_tenant(domain, name):
    tenant = Tenant(domain=domain, name=name, status='active', maturity_state=MaturityState.BOOTSTRAP)
    db.session.add(tenant)
    db.session.commit()
    return tenant


def make_user(tenant, email, role):
    user = User(email=email, sso_domain=tenant.domain, auth_type='local', email_verified=True)
    user.set_name(first_name='Test', last_name='Person')
    user.set_password(PASSWORD)
    user.is_admin = role != GlobalRole.USER
    db.session.add(user)
    db.session.flush()
    db.session.add(TenantMembership(user_id=user.id, tenant_id=tenant.id, global_role=role))
    db.session.commit()
    return user


def make_decision(tenant, title, decision_type=None, deleted=False, user=None):
    from datetime import datetime, timezone
    number = (db.session.query(db.func.max(ArchitectureDecision.decision_number))
              .filter_by(domain=tenant.domain).scalar() or 0) + 1
    decision = ArchitectureDecision(
        title=title, context=f'Context of {title}', decision=f'Decision of {title}',
        consequences=f'Consequences of {title}', status='accepted', decision_number=number,
        domain=tenant.domain, tenant_id=tenant.id, decision_type=decision_type,
        created_by_id=user.id if user else None,
        deleted_at=datetime.now(timezone.utc) if deleted else None,
    )
    db.session.add(decision)
    db.session.commit()
    return decision


def login(api_app, user):
    client = api_app.test_client()
    response = client.post('/api/auth/login', json={'email': user.email, 'password': PASSWORD})
    assert response.status_code == 200, response.data
    token = response.headers.get('X-CSRF-Token') or client.get('/api/auth/csrf-token').get_json()['csrf_token']
    client.environ_base['HTTP_X_CSRF_TOKEN'] = token
    return client


def login_master(api_app):
    client = api_app.test_client()
    response = client.post('/auth/local', json={
        'username': DEFAULT_MASTER_USERNAME, 'password': DEFAULT_MASTER_PASSWORD,
    })
    assert response.status_code == 200, response.data
    token = response.headers.get('X-CSRF-Token') or client.get('/api/auth/csrf-token').get_json()['csrf_token']
    client.environ_base['HTTP_X_CSRF_TOKEN'] = token
    return client


@pytest.fixture
def acme(api_app):
    return make_tenant('acme.test', 'Acme')


@pytest.fixture
def globex(api_app):
    return make_tenant('globex.test', 'Globex')


@pytest.fixture
def admin(api_app, acme):
    return make_user(acme, 'admin@acme.test', GlobalRole.ADMIN)


@pytest.fixture
def member(api_app, acme):
    return make_user(acme, 'member@acme.test', GlobalRole.USER)


@pytest.fixture
def admin_client(api_app, admin):
    return login(api_app, admin)


@pytest.fixture
def member_client(api_app, member):
    return login(api_app, member)


def settings_of(tenant):
    db.session.expire_all()
    return TenantSettings.query.filter_by(tenant_id=tenant.id).first()


def stored(decision):
    db.session.expire_all()
    return db.session.get(ArchitectureDecision, decision.id)


def text_of(decision):
    row = stored(decision)
    return (row.title, row.context, row.decision, row.consequences, row.status, row.updated_at)


class TestCatalogueEndpoint:

    def test_catalogue_is_public_static_data(self, api_app):
        response = api_app.test_client().get(CATALOG_URL)

        assert response.status_code == 200
        body = response.get_json()
        assert body == dt.get_decision_template_catalog()
        assert [(i['code'], i['title']) for i in body['industries']] == NACE_REV_2_1
        assert len(body['templates']) == 5 and body['default_template_id'] == 'general'


class TestReadingTheTenantTemplate:

    def test_anonymous_is_refused(self, api_app, acme):
        assert api_app.test_client().get(URL).status_code == 401

    def test_super_admin_is_refused(self, api_app, acme):
        response = login_master(api_app).get(URL)
        assert response.status_code == 403

    def test_a_tenant_that_chose_nothing_gets_general(self, admin_client, acme):
        body = admin_client.get(URL).get_json()

        assert body['template_id'] == 'general'
        assert body['template_chosen'] is False
        assert body['template']['sections']['context']['label'] == 'Context'
        assert body['industry'] is None and body['industry_title'] is None
        assert body['suggested_template_id'] == 'general'
        assert body['guarantee'] == GUARANTEE
        assert body['can_manage'] is True and body['show_notice'] is True
        # Reading creates nothing
        assert settings_of(acme) is None

    def test_every_member_can_read_it_but_only_admins_get_the_notice(self, admin_client, member_client, acme):
        admin_client.put(URL, json={'template_id': 'governance'})

        body = member_client.get(URL).get_json()

        assert body['template_id'] == 'governance'
        assert body['template']['sections']['decision']['label'] == 'Decision and reasons'
        assert body['can_manage'] is False and body['show_notice'] is False

    def test_member_never_gets_the_notice(self, member_client, acme):
        assert member_client.get(URL).get_json()['show_notice'] is False


class TestChoosingATemplate:

    @pytest.mark.parametrize('role', [GlobalRole.ADMIN, GlobalRole.STEWARD, GlobalRole.PROVISIONAL_ADMIN])
    def test_admin_level_roles_may_choose(self, api_app, acme, role):
        client = login(api_app, make_user(acme, 'lead@acme.test', role))

        response = client.put(URL, json={'template_id': 'controlled_change', 'industry': 'C'})

        assert response.status_code == 200
        body = response.get_json()
        assert body['message'] == 'Decision template saved'
        assert body['template_id'] == 'controlled_change' and body['template_chosen'] is True
        assert body['industry'] == 'C' and body['industry_title'] == 'Manufacturing'
        assert body['suggested_template_id'] == 'controlled_change'
        assert body['template']['caution'].startswith('This layout follows common change-record practice.')
        assert body['show_notice'] is False and body['added_pack_ids'] == []
        assert settings_of(acme).decision_template_id == 'controlled_change'
        assert db.session.get(Tenant, acme.id).industry == 'C'

    def test_ordinary_member_is_refused(self, member_client, acme):
        response = member_client.put(URL, json={'template_id': 'software'})

        assert response.status_code == 403
        assert response.get_json() == {'error': 'Permission denied. Admin or Steward role required.'}
        assert settings_of(acme) is None

    def test_super_admin_and_anonymous_are_refused(self, api_app, acme):
        assert login_master(api_app).put(URL, json={'template_id': 'software'}).status_code == 403
        assert api_app.test_client().put(URL, json={'template_id': 'software'}).status_code == 401
        assert settings_of(acme) is None

    def test_save_needs_a_csrf_token(self, admin_client, acme):
        admin_client.environ_base.pop('HTTP_X_CSRF_TOKEN')

        response = admin_client.put(URL, json={'template_id': 'software'})

        assert response.status_code == 403
        assert settings_of(acme) is None

    @pytest.mark.parametrize('body', [
        {'template_id': 'nope'}, {'template_id': 7}, {'industry': 'W'}, {'industry': 'Manufacturing'},
        {'industry': 3}, {'template_id': 'software', 'industry': 'ZZ'},
        {'template_id': 'software', 'enable_suggested_packs': 'yes'},
    ])
    def test_unknown_values_are_rejected_and_nothing_is_saved(self, admin_client, acme, body):
        response = admin_client.put(URL, json=body)

        assert response.status_code == 400
        assert 'error' in response.get_json()
        assert settings_of(acme) is None
        assert db.session.get(Tenant, acme.id).industry is None

    @pytest.mark.parametrize('body', [None, [], 'text'])
    def test_body_must_be_an_object(self, admin_client, body):
        assert admin_client.put(URL, json=body).status_code == 400

    def test_industry_only_suggests_any_template_may_be_chosen(self, admin_client, acme):
        body = admin_client.put(URL, json={'industry': 'L', 'template_id': 'software'}).get_json()

        assert body['industry'] == 'L' and body['suggested_template_id'] == 'investment'
        assert body['template_id'] == 'software'

    def test_industry_alone_does_not_change_the_template(self, admin_client, acme):
        body = admin_client.put(URL, json={'industry': 'q'}).get_json()

        assert body['industry'] == 'Q' and body['industry_title'] == 'Education'
        assert body['template_id'] == 'general' and body['template_chosen'] is False

    def test_fields_left_out_keep_their_value_and_null_clears(self, admin_client, acme):
        admin_client.put(URL, json={'template_id': 'investment', 'industry': 'L'})

        body = admin_client.put(URL, json={'template_id': 'governance'}).get_json()
        assert (body['template_id'], body['industry']) == ('governance', 'L')

        body = admin_client.put(URL, json={'template_id': None, 'industry': None}).get_json()
        assert (body['template_id'], body['template_chosen'], body['industry']) == ('general', False, None)
        assert settings_of(acme).decision_template_id is None

    def test_change_is_written_to_the_audit_log(self, admin_client, acme, admin):
        admin_client.put(URL, json={'template_id': 'governance', 'industry': 'P'})
        admin_client.put(URL, json={'template_id': 'governance', 'industry': 'P'})  # no change, no entry

        entries = AuditLog.query.filter_by(tenant_id=acme.id, action_type='update_decision_template').all()
        assert len(entries) == 1
        assert entries[0].actor_user_id == admin.id
        assert entries[0].details == {
            'template_id': 'governance', 'previous_template_id': None,
            'industry': 'P', 'previous_industry': None, 'added_pack_ids': [],
        }

    def test_switching_never_touches_a_decision(self, admin_client, acme):
        decision = make_decision(acme, 'Adopt policy', decision_type='Policy')
        before = text_of(decision)

        for template_id in ('governance', 'controlled_change', 'general', None):
            assert admin_client.put(URL, json={'template_id': template_id}).status_code == 200

        assert text_of(decision) == before
        assert stored(decision).decision_type == 'Policy'
        assert DecisionHistory.query.count() == 0

    def test_tenants_are_separate(self, api_app, admin_client, acme, globex):
        other_client = login(api_app, make_user(globex, 'admin@globex.test', GlobalRole.ADMIN))

        admin_client.put(URL, json={'template_id': 'investment', 'industry': 'L'})

        other = other_client.get(URL).get_json()
        assert other['template_id'] == 'general' and other['industry'] is None
        assert db.session.get(Tenant, globex.id).industry is None
        assert settings_of(globex) is None


class TestSuggestedPacks:

    def config(self, tenant):
        return settings_of(tenant).get_decision_relationship_config()

    def test_packs_are_not_switched_on_unless_asked(self, admin_client, acme):
        admin_client.put(URL, json={'template_id': 'governance'})

        assert self.config(acme)['selected_pack_ids'] == ['core']

    def test_ticking_the_box_adds_the_suggested_packs(self, admin_client, acme):
        body = admin_client.put(URL, json={'template_id': 'governance', 'enable_suggested_packs': True}).get_json()

        assert body['added_pack_ids'] == ['people', 'finance']
        config = self.config(acme)
        assert config['selected_pack_ids'] == ['core', 'people', 'finance']
        for type_id in ('supersedes', 'governs', 'funds', 'approves'):
            assert type_id in config['enabled_relationship_types']

    def test_packs_are_never_switched_off_and_disabled_classes_stay_disabled(self, admin_client, acme):
        admin_client.put('/api/tenant/decision-relationships/config', json={
            'selected_pack_ids': ['core', 'software'],
            'enabled_relationship_types': ['supersedes', 'implements'],
            'custom_relationship_types': [],
        })

        body = admin_client.put(URL, json={'template_id': 'investment', 'enable_suggested_packs': True}).get_json()

        assert body['added_pack_ids'] == ['finance', 'security']
        config = self.config(acme)
        assert config['selected_pack_ids'] == ['core', 'software', 'finance', 'security']
        enabled = config['enabled_relationship_types']
        assert 'implements' in enabled and 'funds' in enabled and 'mitigates' in enabled
        # Classes the tenant had switched off are not switched back on
        assert 'amends' not in enabled and 'blocks' not in enabled

    def test_nothing_to_add_changes_nothing(self, admin_client, acme):
        admin_client.put(URL, json={'template_id': 'governance', 'enable_suggested_packs': True})

        body = admin_client.put(URL, json={'template_id': 'governance', 'enable_suggested_packs': True}).get_json()

        assert body['added_pack_ids'] == []


class TestNotice:

    def test_dismissing_ends_it_for_every_admin_of_the_tenant(self, api_app, admin_client, acme):
        steward_client = login(api_app, make_user(acme, 'steward@acme.test', GlobalRole.STEWARD))
        assert steward_client.get(URL).get_json()['show_notice'] is True

        response = admin_client.post(NOTICE_URL)

        assert response.status_code == 200 and response.get_json()['show_notice'] is False
        assert steward_client.get(URL).get_json()['show_notice'] is False
        assert settings_of(acme).decision_template_id is None

    def test_choosing_a_template_ends_it(self, admin_client, acme):
        admin_client.put(URL, json={'template_id': 'general'})

        assert admin_client.get(URL).get_json()['show_notice'] is False

    def test_member_cannot_dismiss(self, member_client, admin_client, acme):
        assert member_client.post(NOTICE_URL).status_code == 403
        assert admin_client.get(URL).get_json()['show_notice'] is True

    def test_other_tenants_keep_their_notice(self, api_app, admin_client, acme, globex):
        other_client = login(api_app, make_user(globex, 'admin@globex.test', GlobalRole.ADMIN))

        admin_client.post(NOTICE_URL)

        assert other_client.get(URL).get_json()['show_notice'] is True


def new_decision(**extra):
    return {'title': 'A decision', 'context': 'c', 'decision': 'd', 'consequences': 'q', **extra}


class TestDecisionType:

    def test_untyped_is_valid_and_the_field_is_in_every_response(self, member_client, acme):
        response = member_client.post('/api/decisions', json=new_decision())

        assert response.status_code == 201
        created = response.get_json()
        assert created['decision_type'] is None
        assert member_client.get('/api/decisions').get_json()[0]['decision_type'] is None
        assert member_client.get(f"/api/decisions/{created['id']}").get_json()['decision_type'] is None

    def test_any_member_who_can_edit_can_set_a_type(self, member_client, acme):
        created = member_client.post('/api/decisions', json=new_decision(decision_type='Policy')).get_json()
        assert created['decision_type'] == 'Policy'

        updated = member_client.put(f"/api/decisions/{created['id']}", json={'decision_type': 'Spending'})

        assert updated.status_code == 200 and updated.get_json()['decision_type'] == 'Spending'
        # The earlier state is kept in the history, type included
        history = updated.get_json()['history']
        assert len(history) == 1 and history[0]['decision_type'] == 'Policy'

    @pytest.mark.parametrize('bad', ['Architecture', 'policy', 5, ['Policy'], 'x' * 300])
    def test_type_outside_the_tenant_template_is_rejected(self, member_client, acme, bad):
        response = member_client.post('/api/decisions', json=new_decision(decision_type=bad))

        assert response.status_code == 400
        assert ArchitectureDecision.query.count() == 0

    def test_update_rejects_an_unknown_type_and_changes_nothing(self, member_client, acme):
        decision = make_decision(acme, 'Typed', decision_type='Policy')

        response = member_client.put(
            f'/api/decisions/{decision.id}', json={'title': 'Renamed', 'decision_type': 'Architecture'})

        assert response.status_code == 400
        assert stored(decision).title == 'Typed' and stored(decision).decision_type == 'Policy'

    def test_types_follow_the_tenant_template(self, admin_client, acme):
        admin_client.put(URL, json={'template_id': 'software'})

        assert admin_client.post('/api/decisions', json=new_decision(decision_type='Policy')).status_code == 400
        response = admin_client.post('/api/decisions', json=new_decision(decision_type='Architecture'))
        assert response.status_code == 201 and response.get_json()['decision_type'] == 'Architecture'

    def test_type_is_kept_when_the_template_changes(self, admin_client, acme):
        admin_client.put(URL, json={'template_id': 'software'})
        created = admin_client.post('/api/decisions', json=new_decision(decision_type='Architecture')).get_json()

        admin_client.put(URL, json={'template_id': 'governance'})

        url = f"/api/decisions/{created['id']}"
        assert admin_client.get(url).get_json()['decision_type'] == 'Architecture'
        # Editing the decision with its old type still in the form keeps it
        edited = admin_client.put(url, json={'title': 'Renamed', 'decision_type': 'Architecture'})
        assert edited.status_code == 200
        assert edited.get_json()['decision_type'] == 'Architecture' and edited.get_json()['title'] == 'Renamed'
        # An edit that does not mention the type keeps it too
        assert admin_client.put(url, json={'title': 'Renamed again'}).get_json()['decision_type'] == 'Architecture'
        # Another type of the old template is no longer offered; one of the new template is
        assert admin_client.put(url, json={'decision_type': 'Security'}).status_code == 400
        assert admin_client.put(url, json={'decision_type': 'Appointment'}).get_json()['decision_type'] == 'Appointment'

    @pytest.mark.parametrize('empty', [None, '', '   '])
    def test_type_can_be_cleared(self, member_client, acme, empty):
        decision = make_decision(acme, 'Typed', decision_type='Policy')

        response = member_client.put(f'/api/decisions/{decision.id}', json={'decision_type': empty})

        assert response.status_code == 200 and response.get_json()['decision_type'] is None

    def test_same_type_is_not_a_change(self, member_client, acme):
        decision = make_decision(acme, 'Typed', decision_type='Policy')

        member_client.put(f'/api/decisions/{decision.id}', json={'decision_type': 'Policy'})

        assert DecisionHistory.query.count() == 0

    def test_cannot_type_another_tenants_decision(self, member_client, acme, globex):
        foreign = make_decision(globex, 'Foreign')

        response = member_client.put(f'/api/decisions/{foreign.id}', json={'decision_type': 'Policy'})

        assert response.status_code == 404
        assert stored(foreign).decision_type is None


class TestBulkType:

    def test_sets_a_type_on_many_decisions_and_leaves_their_text_alone(self, admin_client, acme, admin):
        decisions = [make_decision(acme, f'Decision {n}') for n in range(3)]
        typed = make_decision(acme, 'Already typed', decision_type='Policy')
        before = [text_of(d) for d in decisions + [typed]]
        ids = [d.id for d in decisions] + [typed.id]

        response = admin_client.post(BULK_URL, json={'decision_ids': ids, 'decision_type': 'Policy'})

        assert response.status_code == 200
        assert response.get_json() == {
            'message': 'Decision type set', 'decision_type': 'Policy',
            'updated': 3, 'unchanged': 1, 'skipped_ids': [],
        }
        assert [stored(d).decision_type for d in decisions] == ['Policy'] * 3
        # Titles, text, status and the last-updated date are exactly as they were
        assert [text_of(d) for d in decisions + [typed]] == before
        assert DecisionHistory.query.count() == 0

        entry = AuditLog.query.filter_by(tenant_id=acme.id, action_type='bulk_set_decision_type').one()
        assert entry.actor_user_id == admin.id
        assert entry.details == {
            'decision_type': 'Policy',
            'decision_ids': [d.id for d in decisions],
            'previous_types': {str(d.id): None for d in decisions},
        }

    def test_clears_types(self, admin_client, acme):
        decisions = [make_decision(acme, f'Decision {n}', decision_type='Spending') for n in range(2)]

        response = admin_client.post(BULK_URL, json={'decision_ids': [d.id for d in decisions], 'decision_type': None})

        assert response.status_code == 200
        assert response.get_json()['message'] == 'Decision type cleared' and response.get_json()['updated'] == 2
        assert [stored(d).decision_type for d in decisions] == [None, None]
        entry = AuditLog.query.filter_by(action_type='bulk_set_decision_type').one()
        assert set(entry.details['previous_types'].values()) == {'Spending'}

    def test_ids_of_other_tenants_deleted_and_unknown_decisions_are_skipped(self, admin_client, acme, globex):
        own = make_decision(acme, 'Own')
        foreign = make_decision(globex, 'Foreign')
        deleted = make_decision(acme, 'Deleted', deleted=True)

        response = admin_client.post(BULK_URL, json={
            'decision_ids': [own.id, foreign.id, deleted.id, 999999], 'decision_type': 'Policy'})

        assert response.status_code == 200
        body = response.get_json()
        assert body['updated'] == 1 and body['skipped_ids'] == [foreign.id, deleted.id, 999999]
        assert stored(own).decision_type == 'Policy'
        assert stored(foreign).decision_type is None and stored(deleted).decision_type is None
        assert AuditLog.query.filter_by(tenant_id=globex.id).count() == 0

    def test_only_foreign_ids_changes_nothing_and_logs_nothing(self, admin_client, acme, globex):
        foreign = make_decision(globex, 'Foreign')

        response = admin_client.post(BULK_URL, json={'decision_ids': [foreign.id], 'decision_type': 'Policy'})

        assert response.status_code == 200
        assert response.get_json()['updated'] == 0 and response.get_json()['skipped_ids'] == [foreign.id]
        assert AuditLog.query.filter_by(action_type='bulk_set_decision_type').count() == 0

    def test_batch_size_is_capped(self, api_app, admin_client, acme):
        import app as app_module
        cap = app_module.BULK_DECISION_TYPE_MAX
        decision = make_decision(acme, 'Own')

        too_many = admin_client.post(BULK_URL, json={
            'decision_ids': [decision.id] + list(range(100000, 100000 + cap)), 'decision_type': 'Policy'})

        assert cap == 200
        assert too_many.status_code == 400
        assert too_many.get_json() == {'error': 'At most 200 decisions can be changed at once'}
        assert stored(decision).decision_type is None

        at_the_cap = admin_client.post(BULK_URL, json={
            'decision_ids': [decision.id] + list(range(100000, 100000 + cap - 1)), 'decision_type': 'Policy'})
        assert at_the_cap.status_code == 200 and at_the_cap.get_json()['updated'] == 1

    def test_repeated_ids_count_once(self, admin_client, acme):
        decision = make_decision(acme, 'Own')

        response = admin_client.post(BULK_URL, json={'decision_ids': [decision.id] * 500, 'decision_type': 'Policy'})

        assert response.status_code == 200 and response.get_json()['updated'] == 1

    @pytest.mark.parametrize('body', [
        None, {}, {'decision_ids': [], 'decision_type': 'Policy'}, {'decision_ids': 'all', 'decision_type': 'Policy'},
        {'decision_ids': ['1'], 'decision_type': 'Policy'}, {'decision_ids': [True], 'decision_type': 'Policy'},
        {'decision_ids': [1.5], 'decision_type': 'Policy'}, {'decision_ids': [1]},
        {'decision_ids': [1], 'decision_type': 'Architecture'}, {'decision_ids': [1], 'decision_type': 9},
    ])
    def test_bad_requests_are_rejected(self, admin_client, acme, body):
        decision = make_decision(acme, 'Own')
        assert decision.id == 1

        response = admin_client.post(BULK_URL, json=body)

        assert response.status_code == 400 and 'error' in response.get_json()
        assert stored(decision).decision_type is None

    def test_type_must_be_in_the_current_template(self, admin_client, acme):
        decision = make_decision(acme, 'Own', decision_type='Policy')
        admin_client.put(URL, json={'template_id': 'software'})

        refused = admin_client.post(BULK_URL, json={'decision_ids': [decision.id], 'decision_type': 'Policy'})
        accepted = admin_client.post(BULK_URL, json={'decision_ids': [decision.id], 'decision_type': 'Security'})

        assert refused.status_code == 400
        assert accepted.status_code == 200 and stored(decision).decision_type == 'Security'

    def test_ordinary_member_super_admin_and_anonymous_are_refused(self, api_app, member_client, acme):
        decision = make_decision(acme, 'Own')
        body = {'decision_ids': [decision.id], 'decision_type': 'Policy'}

        assert member_client.post(BULK_URL, json=body).status_code == 403
        assert login_master(api_app).post(BULK_URL, json=body).status_code == 403
        assert api_app.test_client().post(BULK_URL, json=body).status_code == 401
        assert stored(decision).decision_type is None

    @pytest.mark.parametrize('role', [GlobalRole.STEWARD, GlobalRole.PROVISIONAL_ADMIN])
    def test_stewards_and_provisional_admins_may(self, api_app, acme, role):
        decision = make_decision(acme, 'Own')
        client = login(api_app, make_user(acme, 'lead@acme.test', role))

        response = client.post(BULK_URL, json={'decision_ids': [decision.id], 'decision_type': 'Policy'})

        assert response.status_code == 200 and stored(decision).decision_type == 'Policy'


class TestIndustryStaysOutOfAnalytics:

    def test_industry_is_not_in_the_user_or_tenant_payloads(self, admin_client, acme):
        admin_client.put(URL, json={'template_id': 'governance', 'industry': 'P'})

        me = admin_client.get('/api/user/me').get_json()

        assert 'industry' not in me and 'industry' not in (me.get('tenant_info') or {})
        assert 'industry' not in db.session.get(Tenant, acme.id).to_dict()

    def test_no_analytics_call_mentions_the_industry(self):
        """The industry answer is read in one place: the tenant's own template payload."""
        source = (Path(__file__).resolve().parent.parent / 'app.py').read_text()
        lines = [line for line in source.splitlines() if 'industry' in line.lower()]
        assert lines
        for line in lines:
            assert 'posthog' not in line.lower() and 'track_' not in line and 'capture(' not in line
        for endpoint in ('api_get_tenant_decision_template', 'api_update_tenant_decision_template',
                         'api_get_decision_template_catalog'):
            definition = source.index(f'def {endpoint}(')
            decorators = source[source.rfind('@app.route', 0, definition):definition]
            assert 'track_endpoint' not in decorators
