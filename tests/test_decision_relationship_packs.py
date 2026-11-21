"""
Built-in decision relationship packs.

Packs for non-technical teams (People & Policy, Finance & Procurement,
Product & Customer) sit beside the original ones. Adding packs must not change
what any existing tenant has enabled, and must not break a tenant whose own
custom class happens to use a key that a new built-in type now uses.
"""
import json

import pytest

import decision_relationships as dr
from models import TenantSettings, db, get_tenant_relationship_catalog

ORIGINAL_PACKS = {
    'core': ['supersedes', 'amends', 'depends_on', 'related_to', 'conflicts_with'],
    'software': ['implements', 'blocks', 'duplicates', 'derived_from'],
    'data': ['feeds', 'derived_from', 'depends_on', 'governs'],
    'security': ['mitigates', 'accepts_risk_from', 'governs', 'conflicts_with'],
    'operations': ['blocks', 'informs', 'depends_on', 'governs'],
}
ORIGINAL_TYPE_KEYS = {
    'supersedes', 'amends', 'depends_on', 'related_to', 'conflicts_with', 'implements', 'blocks',
    'duplicates', 'derived_from', 'feeds', 'governs', 'mitigates', 'accepts_risk_from', 'informs',
}
NEW_PACKS = {
    'people': 'People & Policy',
    'finance': 'Finance & Procurement',
    'product': 'Product & Customer',
}


def pack(pack_id):
    return dr.PACK_INDEX[pack_id]


class TestPackCatalog:

    def test_original_packs_are_unchanged(self):
        for pack_id, type_keys in ORIGINAL_PACKS.items():
            assert pack(pack_id)['relationship_types'] == type_keys

    def test_original_packs_keep_their_order_and_new_packs_follow(self):
        assert [item['id'] for item in dr.RELATIONSHIP_PACKS] == list(ORIGINAL_PACKS) + list(NEW_PACKS)

    @pytest.mark.parametrize('pack_id,label', NEW_PACKS.items())
    def test_new_pack_follows_the_existing_structure(self, pack_id, label):
        new_pack = pack(pack_id)

        assert new_pack['label'] == label
        assert set(new_pack) == {'id', 'label', 'description', 'relationship_types'}
        assert new_pack['description'].startswith('Useful for ')
        assert new_pack['description'].endswith(' decisions.')
        assert 4 <= len(new_pack['relationship_types']) <= 6
        assert len(set(new_pack['relationship_types'])) == len(new_pack['relationship_types'])
        for type_key in new_pack['relationship_types']:
            assert type_key in dr.BUILTIN_RELATIONSHIP_TYPES

    def test_every_new_pack_adds_classes_of_its_own(self):
        for pack_id in NEW_PACKS:
            assert set(pack(pack_id)['relationship_types']) - ORIGINAL_TYPE_KEYS

    def test_every_type_definition_is_complete_and_belongs_to_a_pack(self):
        for key, definition in dr.BUILTIN_RELATIONSHIP_TYPES.items():
            assert definition['key'] == key
            assert dr.CUSTOM_RELATIONSHIP_KEY_PATTERN.match(key)
            assert set(definition) == {
                'key', 'label', 'inverse_label', 'description', 'builtin', 'directional', 'has_status_effect'}
            assert definition['label'] and definition['inverse_label'] and definition['description']
            assert definition['builtin'] is True
            assert definition['directional'] is (definition['label'] != definition['inverse_label'])
            assert dr._collect_pack_ids_for_type(key), f'{key} is in no pack'

    def test_only_supersedes_changes_a_decision_status(self):
        with_effect = [key for key, item in dr.BUILTIN_RELATIONSHIP_TYPES.items() if item['has_status_effect']]

        assert with_effect == ['supersedes']

    def test_new_types_are_exactly_the_overridable_ones(self):
        assert set(dr.BUILTIN_RELATIONSHIP_TYPES) - ORIGINAL_TYPE_KEYS == set(dr.TENANT_OVERRIDABLE_BUILTIN_TYPE_KEYS)

    def test_no_pack_wording_assumes_a_software_team_by_default(self):
        assert 'architecture' not in pack('core')['description'].lower()
        for pack_id in NEW_PACKS:
            text = json.dumps(pack(pack_id)).lower()
            assert 'architecture' not in text and 'software' not in text

    def test_available_catalog_offers_the_new_packs(self):
        catalog = dr.get_core_relationship_catalog()

        assert [item['id'] for item in catalog['packs']][-3:] == list(NEW_PACKS)
        types = {item['key']: item for item in catalog['types']}
        assert types['funds']['pack_ids'] == ['finance']
        assert types['exception_to']['pack_ids'] == ['people', 'finance']
        assert types['constrains']['pack_ids'] == ['finance', 'product']
        assert types['governs']['pack_ids'] == ['data', 'security', 'operations', 'people']


class TestDefaultEnablement:

    def test_only_core_is_selected_by_default(self):
        assert dr.DEFAULT_SELECTED_PACK_IDS == ['core']
        assert [item['id'] for item in dr.RELATIONSHIP_PACKS if item.get('default_selected')] == ['core']
        assert dr.get_core_relationship_catalog()['default_selected_pack_ids'] == ['core']

    def test_tenant_that_never_saved_settings_still_gets_core_only(self):
        config = dr.normalize_relationship_settings(None)

        assert config['selected_pack_ids'] == ['core']
        assert config['enabled_relationship_types'] == ORIGINAL_PACKS['core']
        assert config['custom_relationship_types'] == []

    def test_new_pack_types_are_not_valid_until_the_pack_is_selected(self):
        assert not dr.is_valid_relationship_type('funds')
        assert not dr.is_valid_relationship_type('funds', {'selected_pack_ids': ['core', 'security']})
        assert dr.is_valid_relationship_type('funds', {'selected_pack_ids': ['core', 'finance']})

    def test_selecting_a_new_pack_enables_its_types(self):
        config = dr.normalize_relationship_settings({'selected_pack_ids': ['core', 'people']})

        assert config['enabled_relationship_types'] == ORIGINAL_PACKS['core'] + [
            'governs', 'implements', 'exception_to', 'sets_precedent_for']
        catalog = dr.get_effective_relationship_catalog(config)
        assert catalog['type_map']['exception_to']['label'] == 'Exception to'
        assert catalog['type_map']['exception_to']['inverse_label'] == 'Has exception'

    def test_unknown_pack_is_still_rejected(self):
        with pytest.raises(ValueError, match='Unknown relationship pack: marketing'):
            dr.normalize_relationship_settings({'selected_pack_ids': ['marketing']})


STORED_CONFIG = {
    'selected_pack_ids': ['core', 'security'],
    'enabled_relationship_types': ['supersedes', 'related_to', 'mitigates', 'requires_signoff'],
    'custom_relationship_types': [{
        'key': 'requires_signoff', 'label': 'Requires signoff from',
        'inverse_label': 'Signs off on', 'description': 'Needs another owner to agree',
    }],
}


def store(session, sample_tenant, config):
    """Write settings the way an earlier version stored them: raw JSON columns."""
    settings = TenantSettings(
        tenant_id=sample_tenant.id,
        decision_relationship_pack_ids=json.dumps(config['selected_pack_ids']),
        decision_relationship_enabled_types=json.dumps(config['enabled_relationship_types']),
        decision_relationship_custom_types=json.dumps(config['custom_relationship_types']),
    )
    session.add(settings)
    session.commit()
    return settings


class TestExistingTenantsAreUntouched:

    def test_stored_settings_read_back_exactly(self, session, sample_tenant):
        settings = store(session, sample_tenant, STORED_CONFIG)

        assert settings.get_decision_relationship_config() == STORED_CONFIG
        effective = get_tenant_relationship_catalog(sample_tenant.id)
        assert [item['id'] for item in effective['packs']] == ['core', 'security']
        assert [item['key'] for item in effective['types']] == [
            'supersedes', 'related_to', 'mitigates', 'requires_signoff']

    def test_reading_settings_does_not_rewrite_the_stored_columns(self, session, sample_tenant):
        settings = store(session, sample_tenant, STORED_CONFIG)
        before = (settings.decision_relationship_pack_ids, settings.decision_relationship_enabled_types,
                  settings.decision_relationship_custom_types)

        settings.get_decision_relationship_settings_payload()
        get_tenant_relationship_catalog(sample_tenant.id)
        session.commit()
        session.refresh(settings)

        assert (settings.decision_relationship_pack_ids, settings.decision_relationship_enabled_types,
                settings.decision_relationship_custom_types) == before

    def test_new_packs_are_offered_but_not_selected(self, session, sample_tenant):
        settings = store(session, sample_tenant, STORED_CONFIG)

        payload = settings.get_decision_relationship_settings_payload()

        assert {item['id'] for item in payload['available_catalog']['packs']} >= set(NEW_PACKS)
        assert payload['config']['selected_pack_ids'] == ['core', 'security']
        assert not set(NEW_PACKS) & {item['id'] for item in payload['effective_catalog']['packs']}


class TestCustomClassWithAKeyThatIsNowBuiltIn:
    """A tenant may already have a custom class called, say, `approves`."""

    CUSTOM_APPROVES = {
        'key': 'approves', 'label': 'Signed off by board for',
        'inverse_label': 'Board sign-off from', 'description': 'Our board approval step',
    }

    def config(self, pack_ids):
        return {
            'selected_pack_ids': pack_ids,
            'enabled_relationship_types': None,
            'custom_relationship_types': [dict(self.CUSTOM_APPROVES)],
        }

    def test_stored_custom_class_still_loads(self, session, sample_tenant):
        settings = store(session, sample_tenant, {
            'selected_pack_ids': ['core'],
            'enabled_relationship_types': ['supersedes', 'approves'],
            'custom_relationship_types': [self.CUSTOM_APPROVES],
        })

        config = settings.get_decision_relationship_config()
        effective = get_tenant_relationship_catalog(sample_tenant.id)

        assert config['custom_relationship_types'] == [self.CUSTOM_APPROVES]
        approves = [item for item in effective['types'] if item['key'] == 'approves']
        assert len(approves) == 1
        assert approves[0]['label'] == 'Signed off by board for'
        assert approves[0]['builtin'] is False

    def test_custom_class_wins_when_the_pack_with_the_same_key_is_selected(self):
        catalog = dr.get_effective_relationship_catalog(self.config(['core', 'finance']))

        keys = [item['key'] for item in catalog['types']]
        assert keys.count('approves') == 1
        assert catalog['type_map']['approves']['label'] == 'Signed off by board for'
        assert catalog['type_map']['approves']['pack_ids'] == ['custom']
        # The rest of the pack is still available
        assert catalog['type_map']['funds']['builtin'] is True

    def test_enabled_types_list_the_shared_key_once(self):
        config = dr.normalize_relationship_settings(self.config(['core', 'finance']))

        assert config['enabled_relationship_types'].count('approves') == 1

    def test_custom_class_cannot_take_an_original_built_in_key(self):
        config = self.config(['core'])
        config['custom_relationship_types'][0]['key'] = 'supersedes'

        with pytest.raises(ValueError, match="conflicts with a built-in relationship type"):
            dr.normalize_relationship_settings(config)
