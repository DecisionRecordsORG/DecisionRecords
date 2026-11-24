"""
Tests for changing a decision's status through MCP and the AI REST API
(Enterprise Edition).

Covers:
1. The update_decision_status tool definition in ee/backend/ai/mcp/tools.py
2. MCPToolHandler.execute_tool('update_decision_status', ...) in ee/backend/ai/mcp/server.py
3. The JSON-RPC error format for the tool through handle_mcp_request and /api/mcp
4. PUT /api/ai/decisions/<id>/status in ee/backend/ai/api/routes.py
5. Parity with the web app's PUT /api/decisions/<id> route in app.py

Note: These tests require Enterprise Edition modules from ee/backend/ai/
"""
import json
import os
import sys
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    db, User, Tenant, TenantMembership, SystemConfig, GlobalRole, MaturityState,
    ArchitectureDecision, DecisionHistory, DecisionRelationship
)

# Enterprise Edition imports - skip tests if not available
try:
    from ee.backend.ai import AIApiKeyService
    from ee.backend.ai.mcp.tools import get_tools, get_tool_by_name, validate_tool_input
    from ee.backend.ai.mcp.server import MCPToolHandler, handle_mcp_request
    from ee.backend.ai.decision_status import (
        change_decision_status, DecisionStatusError, SETTABLE_STATUSES
    )
    EE_AVAILABLE = True
except ImportError:
    EE_AVAILABLE = False
    AIApiKeyService = None
    get_tools = None
    get_tool_by_name = None
    validate_tool_input = None
    MCPToolHandler = None
    handle_mcp_request = None
    change_decision_status = None
    DecisionStatusError = None
    SETTABLE_STATUSES = None

EE_TESTS_ENABLED = EE_AVAILABLE and os.environ.get('DECISION_RECORDS_EDITION', 'community') == 'enterprise'
pytestmark = pytest.mark.skipif(
    not EE_TESTS_ENABLED,
    reason="Enterprise Edition tests require DECISION_RECORDS_EDITION=enterprise and EE modules",
)

TOOL = 'update_decision_status'
SLACK_HOOK = 'ee.backend.slack.slack_service.notify_decision_status_changed'
EMAIL_HOOK = 'notifications.notify_subscribers_decision_updated'


def _history(decision_id):
    return DecisionHistory.query.filter_by(decision_id=decision_id).order_by(DecisionHistory.id).all()


def _make_decision(tenant, user, number, status='proposed', title=None):
    decision = ArchitectureDecision(
        title=title or f'Decision {number}',
        context='Context',
        decision='What was decided',
        consequences='Consequences',
        status=status,
        domain=tenant.domain,
        tenant_id=tenant.id,
        created_by_id=user.id,
        decision_number=number,
    )
    db.session.add(decision)
    db.session.commit()
    return decision


def _make_other_tenant():
    """A second organization with its own user and one accepted decision."""
    tenant = Tenant(
        domain='other.org', name='Other Org', status='active',
        maturity_state=MaturityState.BOOTSTRAP, ai_features_enabled=True,
        ai_log_interactions=False,
    )
    db.session.add(tenant)
    db.session.flush()
    user = User(email='someone@other.org', sso_domain='other.org', auth_type='local', email_verified=True)
    user.set_name(first_name='Other', last_name='Person')
    db.session.add(user)
    db.session.flush()
    db.session.add(TenantMembership(user_id=user.id, tenant_id=tenant.id, global_role=GlobalRole.ADMIN))
    db.session.commit()
    # Same decision number as the caller's own decision, different primary key.
    decision = _make_decision(tenant, user, 1, status='accepted', title='Other org decision')
    return tenant, user, decision


# ============================================================================
# TOOL DEFINITION
# ============================================================================

class TestUpdateDecisionStatusToolDefinition:
    """The tool an MCP client sees in tools/list."""

    def test_tool_is_listed(self, app, session):
        assert TOOL in [tool['name'] for tool in get_tools()]

    def test_tool_schema(self, app, session):
        tool = get_tool_by_name(TOOL)
        schema = tool['inputSchema']
        assert schema['type'] == 'object'
        assert schema['required'] == ['id', 'status']
        assert set(schema['properties']) == {'id', 'status', 'reason'}
        assert schema['properties']['id']['type'] == 'string'
        assert schema['properties']['status']['type'] == 'string'
        assert schema['properties']['reason']['type'] == 'string'
        assert schema['properties']['reason']['maxLength'] == 500

    def test_status_enum_is_every_valid_status_except_superseded(self, app, session):
        enum = get_tool_by_name(TOOL)['inputSchema']['properties']['status']['enum']
        expected = [s for s in ArchitectureDecision.VALID_STATUSES if s != 'superseded']
        assert enum == expected == SETTABLE_STATUSES

    def test_descriptions_point_at_each_other(self, app, session):
        assert 'supersede_decision' in get_tool_by_name(TOOL)['description']
        assert TOOL in get_tool_by_name('supersede_decision')['description']

    def test_description_states_write_scope(self, app, session):
        assert 'write scope' in get_tool_by_name(TOOL)['description']

    def test_existing_tools_keep_names_and_schemas(self, app, session):
        """Rewording descriptions must not rename tools or change what they accept."""
        tools = {tool['name']: tool for tool in get_tools()}
        expected_properties = {
            'search_decisions': {'query', 'status', 'limit'},
            'get_decision': {'id'},
            'list_decisions': {'status', 'limit', 'offset', 'order_by', 'order'},
            'create_decision': {'title', 'context', 'decision', 'consequences', 'status', 'supersedes_id'},
            'get_decision_history': {'id', 'limit'},
            'list_decision_comments': {'id', 'limit', 'order'},
            'add_decision_comment': {'id', 'body'},
            'get_relationship_catalog': set(),
            'list_decision_relationships': {'id'},
            'link_decisions': {'source_decision_id', 'target_decision_id', 'relationship_type', 'notes'},
            'supersede_decision': {'source_decision_id', 'target_decision_id', 'notes'},
        }
        added_properties = {
            'search_decisions': {'decision_type', 'offset'},
            'list_decisions': {'decision_type'},
            'create_decision': {'decision_type'},
            'get_decision_history': {'offset'},
            'list_decision_comments': {'offset'},
        }
        for name, properties in expected_properties.items():
            actual = set(tools[name]['inputSchema']['properties'])
            assert actual == properties | added_properties.get(name, set()), name
        # What was added is optional: a call that was valid before is still valid.
        for name, added in added_properties.items():
            assert not added & set(tools[name]['inputSchema'].get('required', [])), name
        assert tools['search_decisions']['inputSchema']['required'] == ['query']
        assert tools['create_decision']['inputSchema']['required'] == ['title', 'context', 'decision', 'consequences']
        assert tools['create_decision']['inputSchema']['properties']['status']['enum'] == ['proposed', 'accepted']

    def test_no_tool_description_limits_the_product_to_architecture(self, app, session):
        for tool in get_tools():
            assert 'architecture decision' not in tool['description'].lower(), tool['name']

    def test_adr_stays_an_accepted_synonym(self, app, session):
        assert 'ADR' in get_tool_by_name('search_decisions')['description']
        assert 'ADR-42' in get_tool_by_name('get_decision')['description']

    def test_validate_requires_id_and_status(self, app, session):
        assert validate_tool_input(TOOL, {'status': 'accepted'}) == 'Missing required field: id'
        assert validate_tool_input(TOOL, {'id': 'ADR-1'}) == 'Missing required field: status'

    def test_validate_rejects_unknown_status(self, app, session):
        error = validate_tool_input(TOOL, {'id': 'ADR-1', 'status': 'done'})
        assert error == "Field 'status' must be one of: proposed, accepted, archived"

    def test_validate_rejects_long_reason(self, app, session):
        error = validate_tool_input(TOOL, {'id': 'ADR-1', 'status': 'accepted', 'reason': 'x' * 501})
        assert error == "Field 'reason' exceeds maximum length of 500"


# ============================================================================
# HANDLER
# ============================================================================

class TestUpdateDecisionStatusHandler:
    """MCPToolHandler.execute_tool('update_decision_status', ...)."""

    @pytest.fixture
    def ai_enabled_tenant(self, session, sample_tenant):
        sample_tenant.ai_features_enabled = True
        sample_tenant.ai_log_interactions = False
        session.commit()
        return sample_tenant

    @pytest.fixture
    def handler_with_write(self, session, sample_user, ai_enabled_tenant, sample_membership):
        api_key, _ = AIApiKeyService.create_key(
            sample_user, ai_enabled_tenant, 'Write Key', scopes=['read', 'search', 'write']
        )
        return MCPToolHandler(api_key, ai_enabled_tenant, sample_user)

    @pytest.fixture
    def handler_read_only(self, session, sample_user, ai_enabled_tenant, sample_membership):
        api_key, _ = AIApiKeyService.create_key(
            sample_user, ai_enabled_tenant, 'Read Key', scopes=['read', 'search']
        )
        return MCPToolHandler(api_key, ai_enabled_tenant, sample_user)

    # --- transitions -------------------------------------------------------

    @pytest.mark.parametrize('start,target', [
        ('proposed', 'accepted'),
        ('proposed', 'archived'),
        ('accepted', 'proposed'),
        ('accepted', 'archived'),
        ('archived', 'proposed'),
        ('archived', 'accepted'),
        ('superseded', 'proposed'),
        ('superseded', 'accepted'),
        ('superseded', 'archived'),
    ])
    def test_each_valid_transition(self, app, session, handler_with_write, sample_decision, start, target):
        sample_decision.status = start
        session.commit()

        success, result = handler_with_write.execute_tool(TOOL, {'id': str(sample_decision.id), 'status': target})

        assert success is True
        assert result['changed'] is True
        assert result['previous_status'] == start
        assert result['status'] == target
        assert result['decision']['status'] == target
        assert db.session.get(ArchitectureDecision, sample_decision.id).status == target
        history = _history(sample_decision.id)
        assert len(history) == 1
        assert history[0].status == start

    def test_result_carries_the_get_decision_shape_and_previous_status(
        self, app, session, handler_with_write, sample_decision
    ):
        success, result = handler_with_write.execute_tool(TOOL, {'id': 'ADR-1', 'status': 'accepted'})
        _, fetched = handler_with_write.execute_tool('get_decision', {'id': 'ADR-1'})

        assert success is True
        assert result['decision'] == fetched
        assert result['decision_id'] == sample_decision.id
        assert result['display_id'] == fetched['display_id']
        assert result['previous_status'] == 'proposed'
        assert result['message'] == f"Status of {fetched['display_id']} changed from proposed to accepted"

    @pytest.mark.parametrize('identifier', ['ADR-1', 'ADR-001', 'XYZ-001', 'adr-1'])
    def test_accepts_display_ids(self, app, session, handler_with_write, sample_decision, identifier):
        success, result = handler_with_write.execute_tool(TOOL, {'id': identifier, 'status': 'accepted'})
        assert success is True
        assert result['decision_id'] == sample_decision.id
        assert result['status'] == 'accepted'

    def test_accepts_numeric_id(self, app, session, handler_with_write, sample_decision):
        success, result = handler_with_write.execute_tool(TOOL, {'id': str(sample_decision.id), 'status': 'archived'})
        assert success is True
        assert result['decision_id'] == sample_decision.id

    # --- history -----------------------------------------------------------

    def test_history_entry_fields(self, app, session, handler_with_write, sample_decision, sample_user):
        before = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)

        handler_with_write.execute_tool(
            TOOL, {'id': 'ADR-1', 'status': 'accepted', 'reason': 'Agreed in the planning meeting'}
        )

        history = _history(sample_decision.id)
        assert len(history) == 1
        entry = history[0]
        # Like the web app, history holds the state before the change.
        assert entry.status == 'proposed'
        assert entry.title == sample_decision.title
        assert entry.context == sample_decision.context
        assert entry.decision_text == sample_decision.decision
        assert entry.consequences == sample_decision.consequences
        assert entry.change_reason == 'Agreed in the planning meeting'
        assert entry.changed_by_id == sample_user.id
        assert entry.changed_at.replace(tzinfo=None) >= before
        assert sample_decision.status == 'accepted'
        assert sample_decision.updated_by_id == sample_user.id

    def test_history_is_visible_through_get_decision_history(self, app, session, handler_with_write, sample_decision):
        handler_with_write.execute_tool(TOOL, {'id': 'ADR-1', 'status': 'accepted', 'reason': 'Team agreed'})
        _, result = handler_with_write.execute_tool('get_decision_history', {'id': 'ADR-1'})
        assert len(result['history']) == 1
        assert result['history'][0]['status'] == 'proposed'
        assert result['history'][0]['change_reason'] == 'Team agreed'

    def test_reason_is_optional(self, app, session, handler_with_write, sample_decision):
        handler_with_write.execute_tool(TOOL, {'id': 'ADR-1', 'status': 'accepted'})
        assert _history(sample_decision.id)[0].change_reason is None

    def test_blank_reason_is_stored_as_none(self, app, session, handler_with_write, sample_decision):
        handler_with_write.execute_tool(TOOL, {'id': 'ADR-1', 'status': 'accepted', 'reason': '   '})
        assert _history(sample_decision.id)[0].change_reason is None

    def test_reason_is_sanitized(self, app, session, handler_with_write, sample_decision):
        handler_with_write.execute_tool(
            TOOL, {'id': 'ADR-1', 'status': 'accepted', 'reason': 'Agreed <script>alert(1)</script>'}
        )
        assert '<script' not in _history(sample_decision.id)[0].change_reason

    def test_reason_over_500_characters_is_refused(self, app, session, handler_with_write, sample_decision):
        success, result = handler_with_write.execute_tool(
            TOOL, {'id': 'ADR-1', 'status': 'accepted', 'reason': 'x' * 501}
        )
        assert success is False
        assert result['error'] == "Field 'reason' exceeds maximum length of 500"
        assert sample_decision.status == 'proposed'
        assert _history(sample_decision.id) == []

    # --- no-op -------------------------------------------------------------

    def test_same_status_is_a_noop_that_says_so(self, app, session, handler_with_write, sample_decision):
        updated_at = sample_decision.updated_at
        with patch(SLACK_HOOK) as slack, patch(EMAIL_HOOK) as email, \
                patch('feature_flags.is_slack_enabled', return_value=True):
            success, result = handler_with_write.execute_tool(
                TOOL, {'id': 'ADR-1', 'status': 'proposed', 'reason': 'No reason'}
            )

        assert success is True
        assert result['changed'] is False
        assert result['previous_status'] == 'proposed'
        assert result['status'] == 'proposed'
        assert 'No change' in result['message']
        assert result['decision']['status'] == 'proposed'
        assert _history(sample_decision.id) == []
        assert sample_decision.updated_at == updated_at
        assert sample_decision.updated_by_id is None
        slack.assert_not_called()
        email.assert_not_called()

    # --- invalid status ----------------------------------------------------

    @pytest.mark.parametrize('status', ['done', 'Accepted', 'rejected', ''])
    def test_invalid_status_is_refused(self, app, session, handler_with_write, sample_decision, status):
        success, result = handler_with_write.execute_tool(TOOL, {'id': 'ADR-1', 'status': status})
        assert success is False
        assert result['error'] == "Field 'status' must be one of: proposed, accepted, archived"
        assert sample_decision.status == 'proposed'
        assert _history(sample_decision.id) == []

    def test_non_string_status_is_refused(self, app, session, handler_with_write, sample_decision):
        success, result = handler_with_write.execute_tool(TOOL, {'id': 'ADR-1', 'status': 2})
        assert success is False
        assert result['error'] == "Field 'status' must be a string"
        assert sample_decision.status == 'proposed'

    def test_missing_status_is_refused(self, app, session, handler_with_write, sample_decision):
        success, result = handler_with_write.execute_tool(TOOL, {'id': 'ADR-1'})
        assert success is False
        assert result['error'] == 'Missing required field: status'

    # --- superseded --------------------------------------------------------

    def test_superseded_is_refused_and_names_supersede_decision(
        self, app, session, handler_with_write, sample_decision
    ):
        with patch(SLACK_HOOK) as slack, patch('feature_flags.is_slack_enabled', return_value=True):
            success, result = handler_with_write.execute_tool(TOOL, {'id': 'ADR-1', 'status': 'superseded'})

        assert success is False
        assert 'supersede_decision' in result['error']
        assert 'archived' in result['error']
        assert sample_decision.status == 'proposed'
        assert _history(sample_decision.id) == []
        slack.assert_not_called()

    def test_superseded_is_refused_even_for_an_unknown_decision(self, app, session, handler_with_write):
        """The refusal does not depend on the decision, so it reveals nothing about it."""
        success, result = handler_with_write.execute_tool(TOOL, {'id': '99999', 'status': 'superseded'})
        assert success is False
        assert 'supersede_decision' in result['error']

    def test_supersede_decision_still_sets_superseded(
        self, app, session, handler_with_write, sample_decision, ai_enabled_tenant, sample_user
    ):
        newer = _make_decision(ai_enabled_tenant, sample_user, 2, status='accepted')
        success, _ = handler_with_write.execute_tool(
            'supersede_decision', {'source_decision_id': str(newer.id), 'target_decision_id': str(sample_decision.id)}
        )
        assert success is True
        assert sample_decision.status == 'superseded'

    def test_moving_out_of_superseded_keeps_the_relationship_like_the_web_app(
        self, app, session, handler_with_write, sample_decision, ai_enabled_tenant, sample_user
    ):
        """The web route changes the status and leaves relationships alone; so does the tool."""
        newer = _make_decision(ai_enabled_tenant, sample_user, 2, status='accepted')
        handler_with_write.execute_tool(
            'supersede_decision', {'source_decision_id': str(newer.id), 'target_decision_id': str(sample_decision.id)}
        )

        success, result = handler_with_write.execute_tool(TOOL, {'id': str(sample_decision.id), 'status': 'accepted'})

        assert success is True
        assert result['previous_status'] == 'superseded'
        assert sample_decision.status == 'accepted'
        active = DecisionRelationship.query.filter_by(
            target_decision_id=sample_decision.id, relationship_type='supersedes', deleted_at=None
        ).count()
        assert active == 1

    # --- not found / tenant isolation --------------------------------------

    def test_unknown_id_is_not_found(self, app, session, handler_with_write, sample_decision):
        success, result = handler_with_write.execute_tool(TOOL, {'id': '99999', 'status': 'accepted'})
        # Same format as the other tools: a refused call with a message for the model.
        assert success is False
        assert set(result) == {'error'}
        assert result['error'].startswith('Decision not found: 99999. ')
        assert 'search_decisions' in result['error']
        assert sample_decision.status == 'proposed'

    def test_id_without_a_number_is_not_found(self, app, session, handler_with_write, sample_decision):
        success, result = handler_with_write.execute_tool(TOOL, {'id': 'the pricing one', 'status': 'accepted'})
        assert success is False
        assert result['error'].startswith('Decision not found: the pricing one. ')
        assert sample_decision.status == 'proposed'

    def test_other_tenant_id_is_indistinguishable_from_unknown_and_changes_nothing(
        self, app, session, handler_with_write, sample_decision
    ):
        _, _, foreign = _make_other_tenant()
        assert foreign.id != sample_decision.id

        with patch(SLACK_HOOK) as slack, patch(EMAIL_HOOK) as email, \
                patch('feature_flags.is_slack_enabled', return_value=True):
            foreign_outcome = handler_with_write.execute_tool(TOOL, {'id': str(foreign.id), 'status': 'archived'})
            unknown_outcome = handler_with_write.execute_tool(TOOL, {'id': '99999', 'status': 'archived'})

        assert foreign_outcome[0] is False and unknown_outcome[0] is False
        assert foreign_outcome[1]['error'].startswith(f'Decision not found: {foreign.id}. ')
        # Nothing about the other organization's decision is in the answer: apart
        # from the ID that was asked for, the two answers are the same text.
        assert 'Other org decision' not in json.dumps(foreign_outcome[1])
        assert foreign_outcome[1].keys() == unknown_outcome[1].keys() == {'error'}
        assert (
            foreign_outcome[1]['error'].replace(f'Decision not found: {foreign.id}.', '')
            == unknown_outcome[1]['error'].replace('Decision not found: 99999.', '')
        )

        refreshed = db.session.get(ArchitectureDecision, foreign.id)
        assert refreshed.status == 'accepted'
        assert refreshed.updated_by_id is None
        assert _history(foreign.id) == []
        slack.assert_not_called()
        email.assert_not_called()

    def test_display_id_resolves_only_inside_the_callers_tenant(
        self, app, session, handler_with_write, sample_decision
    ):
        """Both organizations have a decision number 1; the caller's own one is changed."""
        _, _, foreign = _make_other_tenant()

        success, result = handler_with_write.execute_tool(TOOL, {'id': 'ADR-1', 'status': 'archived'})

        assert success is True
        assert result['decision_id'] == sample_decision.id
        assert db.session.get(ArchitectureDecision, foreign.id).status == 'accepted'
        assert _history(foreign.id) == []

    def test_deleted_decision_is_refused_like_an_unknown_one(self, app, session, handler_with_write, sample_decision):
        sample_decision.deleted_at = datetime.now(timezone.utc)
        session.commit()

        for identifier in (str(sample_decision.id), 'ADR-1'):
            success, result = handler_with_write.execute_tool(TOOL, {'id': identifier, 'status': 'accepted'})
            assert success is False
            assert result['error'].startswith(f'Decision not found: {identifier}. ')

        assert db.session.get(ArchitectureDecision, sample_decision.id).status == 'proposed'
        assert _history(sample_decision.id) == []

    # --- permission --------------------------------------------------------

    def test_read_only_key_is_refused(self, app, session, handler_read_only, sample_decision):
        with patch(SLACK_HOOK) as slack, patch('feature_flags.is_slack_enabled', return_value=True):
            success, result = handler_read_only.execute_tool(TOOL, {'id': 'ADR-1', 'status': 'accepted'})

        assert success is False
        assert result['error'].startswith('This API key does not have write permission')
        assert sample_decision.status == 'proposed'
        assert _history(sample_decision.id) == []
        slack.assert_not_called()

    def test_read_only_key_learns_nothing_about_other_decisions(self, app, session, handler_read_only, sample_decision):
        """The scope refusal comes before the lookup, so it is the same for any ID."""
        known = handler_read_only.execute_tool(TOOL, {'id': 'ADR-1', 'status': 'accepted'})
        unknown = handler_read_only.execute_tool(TOOL, {'id': '99999', 'status': 'accepted'})
        assert known == unknown

    def test_member_with_the_plain_user_role_may_change_status(
        self, app, session, handler_with_write, sample_decision, sample_membership
    ):
        """The web route has no role requirement for editing a decision; neither has the tool."""
        assert sample_membership.global_role == GlobalRole.USER
        success, result = handler_with_write.execute_tool(TOOL, {'id': 'ADR-1', 'status': 'accepted'})
        assert success is True
        assert result['status'] == 'accepted'

    def test_caller_outside_the_decisions_organization_is_refused(
        self, app, session, ai_enabled_tenant, sample_decision
    ):
        """The web route only finds decisions in the signed-in user's own organization."""
        _, outsider, _ = _make_other_tenant()
        api_key, _ = AIApiKeyService.create_key(
            outsider, ai_enabled_tenant, 'Stale Key', scopes=['read', 'search', 'write']
        )
        handler = MCPToolHandler(api_key, ai_enabled_tenant, outsider)

        with patch(SLACK_HOOK) as slack, patch('feature_flags.is_slack_enabled', return_value=True):
            success, result = handler.execute_tool(TOOL, {'id': 'ADR-1', 'status': 'accepted'})

        assert success is False
        assert result['error'].startswith('Not permitted')
        assert sample_decision.status == 'proposed'
        assert _history(sample_decision.id) == []
        slack.assert_not_called()

    def test_service_refuses_a_missing_actor(self, app, session, sample_decision):
        with pytest.raises(DecisionStatusError) as raised:
            change_decision_status(sample_decision, 'accepted', None)
        assert raised.value.code == DecisionStatusError.NOT_PERMITTED
        assert sample_decision.status == 'proposed'

    # --- notifications -----------------------------------------------------

    def test_slack_hook_is_called_once_on_change(self, app, session, handler_with_write, sample_decision):
        with patch(SLACK_HOOK) as slack, patch('feature_flags.is_slack_enabled', return_value=True):
            handler_with_write.execute_tool(TOOL, {'id': 'ADR-1', 'status': 'accepted'})

        slack.assert_called_once()
        notified = slack.call_args.args[0]
        assert notified.id == sample_decision.id
        assert notified.status == 'accepted'

    def test_slack_hook_is_not_called_when_slack_is_disabled(self, app, session, handler_with_write, sample_decision):
        with patch(SLACK_HOOK) as slack, patch('feature_flags.is_slack_enabled', return_value=False):
            handler_with_write.execute_tool(TOOL, {'id': 'ADR-1', 'status': 'accepted'})
        slack.assert_not_called()

    def test_subscriber_email_hook_is_called_once_as_a_status_change(
        self, app, session, handler_with_write, sample_decision
    ):
        with patch(EMAIL_HOOK) as email:
            handler_with_write.execute_tool(TOOL, {'id': 'ADR-1', 'status': 'accepted', 'reason': 'Team agreed'})

        email.assert_called_once()
        args = email.call_args.args
        assert args[1].id == sample_decision.id
        assert args[3] == 'Team agreed'  # change_reason
        assert args[4] is True           # status_changed

    def test_a_failing_notification_does_not_undo_or_fail_the_change(
        self, app, session, handler_with_write, sample_decision
    ):
        with patch(SLACK_HOOK, side_effect=RuntimeError('slack down')), \
                patch(EMAIL_HOOK, side_effect=RuntimeError('smtp down')), \
                patch('feature_flags.is_slack_enabled', return_value=True):
            success, result = handler_with_write.execute_tool(TOOL, {'id': 'ADR-1', 'status': 'accepted'})

        assert success is True
        assert result['status'] == 'accepted'
        assert db.session.get(ArchitectureDecision, sample_decision.id).status == 'accepted'

    # --- interaction log ---------------------------------------------------

    def test_interaction_is_logged_as_an_mcp_update(
        self, app, session, handler_with_write, sample_decision, ai_enabled_tenant
    ):
        from models import AIInteractionLog, AIChannel, AIAction
        ai_enabled_tenant.ai_log_interactions = True
        session.commit()

        handler_with_write.execute_tool(TOOL, {'id': 'ADR-1', 'status': 'accepted'})

        log = AIInteractionLog.query.filter_by(tenant_id=ai_enabled_tenant.id).one()
        assert log.channel == AIChannel.MCP
        assert log.action == AIAction.UPDATE
        assert log.user_id == handler_with_write.user.id


# ============================================================================
# JSON-RPC ERROR FORMAT
# ============================================================================

class TestUpdateDecisionStatusJsonRpc:
    """handle_mcp_request: the tool follows the error format of the existing tools."""

    @pytest.fixture
    def keys(self, session, sample_user, sample_tenant, sample_membership, sample_decision):
        SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
        SystemConfig.set(SystemConfig.KEY_AI_MCP_SERVER_ENABLED, 'true')
        sample_tenant.ai_features_enabled = True
        sample_tenant.ai_log_interactions = False
        session.commit()
        _, write_key = AIApiKeyService.create_key(
            sample_user, sample_tenant, 'Write', scopes=['read', 'search', 'write']
        )
        _, read_key = AIApiKeyService.create_key(sample_user, sample_tenant, 'Read', scopes=['read', 'search'])
        return write_key, read_key

    @staticmethod
    def _call(key, arguments, request_id=7):
        return handle_mcp_request({
            'jsonrpc': '2.0', 'id': request_id, 'method': 'tools/call',
            'params': {'name': TOOL, 'arguments': arguments},
        }, key)

    def test_tools_list_includes_the_tool(self, app, session, keys):
        response = handle_mcp_request({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'}, keys[0])
        listed = {tool['name']: tool for tool in response['result']['tools']}
        assert TOOL in listed
        assert listed[TOOL]['inputSchema']['properties']['status']['enum'] == ['proposed', 'accepted', 'archived']

    def test_success_is_a_text_content_result(self, app, session, keys, sample_decision):
        response = self._call(keys[0], {'id': 'ADR-1', 'status': 'accepted', 'reason': 'Agreed'})
        assert response['id'] == 7
        assert 'error' not in response
        content = json.loads(response['result']['content'][0]['text'])
        assert content['previous_status'] == 'proposed'
        assert content['decision']['status'] == 'accepted'

    @staticmethod
    def _tool_error(response):
        """The text of a tool execution error: a result with isError, not a JSON-RPC error."""
        assert 'error' not in response
        assert response['result']['isError'] is True
        assert 'structuredContent' not in response['result']
        return response['result']['content'][0]['text']

    def test_invalid_status_is_a_tool_error(self, app, session, keys):
        response = self._call(keys[0], {'id': 'ADR-1', 'status': 'done'})
        assert self._tool_error(response) == "Field 'status' must be one of: proposed, accepted, archived"

    def test_superseded_is_a_tool_error_naming_the_other_tool(self, app, session, keys):
        response = self._call(keys[0], {'id': 'ADR-1', 'status': 'superseded'})
        assert 'supersede_decision' in self._tool_error(response)

    def test_read_only_key_is_a_tool_error(self, app, session, keys, sample_decision):
        response = self._call(keys[1], {'id': 'ADR-1', 'status': 'accepted'})
        message = self._tool_error(response)
        assert message.startswith('This API key does not have write permission')
        assert 'write scope' in message
        assert sample_decision.status == 'proposed'

    def test_invalid_key_is_refused(self, app, session, keys, sample_decision):
        response = self._call('adr_not_a_real_key', {'id': 'ADR-1', 'status': 'accepted'})
        assert response['error']['code'] == 401
        assert sample_decision.status == 'proposed'

    def test_not_found_matches_get_decision(self, app, session, keys):
        """Not found is reported the way get_decision reports it."""
        mine = self._call(keys[0], {'id': '99999', 'status': 'accepted'})
        theirs = handle_mcp_request({
            'jsonrpc': '2.0', 'id': 7, 'method': 'tools/call',
            'params': {'name': 'get_decision', 'arguments': {'id': '99999'}},
        }, keys[0])
        assert mine == theirs
        assert self._tool_error(mine).startswith('Decision not found: 99999')


# ============================================================================
# REAL APP: /api/mcp, /api/ai, and parity with the web route
# ============================================================================

def _ensure_testing_env():
    if os.environ.get('FLASK_ENV') != 'testing':
        os.environ['FLASK_ENV'] = 'testing'
        os.environ['TESTING'] = 'True'


_ensure_testing_env()


class TestStatusChangeThroughTheRealApp:
    """The HTTP endpoints of app.py with the Enterprise blueprints registered."""

    @pytest.fixture
    def real_app(self):
        _ensure_testing_env()
        import app as flask_app
        flask_app.app.config['TESTING'] = True
        flask_app.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        flask_app.app.config['WTF_CSRF_ENABLED'] = False

        with flask_app.app.app_context():
            db.create_all()
            yield flask_app.app
            db.session.remove()
            db.drop_all()

    @pytest.fixture
    def client(self, real_app):
        return real_app.test_client()

    @pytest.fixture
    def setup(self, real_app):
        """A tenant with a member, a write key, a read key and two proposed decisions."""
        SystemConfig.set(SystemConfig.KEY_AI_FEATURES_ENABLED, 'true')
        SystemConfig.set(SystemConfig.KEY_AI_MCP_SERVER_ENABLED, 'true')
        SystemConfig.set(SystemConfig.KEY_AI_EXTERNAL_API_ENABLED, 'true')
        db.session.commit()

        tenant = Tenant(
            domain='status.test', name='Status Test', status='active',
            maturity_state=MaturityState.BOOTSTRAP, ai_features_enabled=True,
            ai_external_access_enabled=True, ai_log_interactions=False,
        )
        db.session.add(tenant)
        db.session.flush()
        user = User(email='member@status.test', sso_domain='status.test', auth_type='local', email_verified=True)
        user.set_name(first_name='Mem', last_name='Ber')
        db.session.add(user)
        db.session.flush()
        db.session.add(TenantMembership(user_id=user.id, tenant_id=tenant.id, global_role=GlobalRole.USER))
        db.session.commit()

        _, write_key = AIApiKeyService.create_key(user, tenant, 'Write', scopes=['read', 'search', 'write'])
        _, read_key = AIApiKeyService.create_key(user, tenant, 'Read', scopes=['read', 'search'])
        first = _make_decision(tenant, user, 1)
        second = _make_decision(tenant, user, 2)
        return {
            'tenant': tenant, 'user': user, 'write_key': write_key, 'read_key': read_key,
            'first': first, 'second': second,
        }

    @staticmethod
    def _mcp(client, key, arguments):
        return client.post(
            '/api/mcp',
            json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                  'params': {'name': TOOL, 'arguments': arguments}},
            headers={'Authorization': f'Bearer {key}'},
        )

    @staticmethod
    def _rest(client, key, decision_id, body):
        headers = {'Authorization': f'Bearer {key}'} if key else {}
        return client.put(f'/api/ai/decisions/{decision_id}/status', json=body, headers=headers)

    # --- /api/mcp ----------------------------------------------------------

    def test_mcp_endpoint_lists_the_tool(self, client, setup):
        response = client.post(
            '/api/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'},
            headers={'Authorization': f"Bearer {setup['write_key']}"},
        )
        assert response.status_code == 200
        assert TOOL in [tool['name'] for tool in response.get_json()['result']['tools']]

    def test_mcp_endpoint_changes_status(self, client, setup):
        response = self._mcp(client, setup['write_key'], {'id': 'ADR-1', 'status': 'accepted', 'reason': 'Agreed'})
        assert response.status_code == 200
        content = json.loads(response.get_json()['result']['content'][0]['text'])
        assert content['previous_status'] == 'proposed'
        assert content['status'] == 'accepted'
        assert db.session.get(ArchitectureDecision, setup['first'].id).status == 'accepted'

    def test_mcp_endpoint_without_a_key_is_refused(self, client, setup):
        response = client.post(
            '/api/mcp',
            json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                  'params': {'name': TOOL, 'arguments': {'id': 'ADR-1', 'status': 'accepted'}}},
        )
        assert response.status_code == 401
        assert db.session.get(ArchitectureDecision, setup['first'].id).status == 'proposed'

    def test_mcp_endpoint_read_only_key_is_refused(self, client, setup):
        response = self._mcp(client, setup['read_key'], {'id': 'ADR-1', 'status': 'accepted'})
        result = response.get_json()['result']
        assert result['isError'] is True
        assert result['content'][0]['text'].startswith('This API key does not have write permission')
        assert db.session.get(ArchitectureDecision, setup['first'].id).status == 'proposed'

    # --- /api/ai -----------------------------------------------------------

    def test_rest_changes_status(self, client, setup):
        response = self._rest(client, setup['write_key'], 'ADR-1', {'status': 'accepted', 'reason': 'Agreed'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['changed'] is True
        assert data['previous_status'] == 'proposed'
        assert data['decision']['status'] == 'accepted'
        assert data['decision']['id'] == setup['first'].id
        entry = _history(setup['first'].id)[0]
        assert entry.status == 'proposed'
        assert entry.change_reason == 'Agreed'
        assert entry.changed_by_id == setup['user'].id

    def test_rest_noop(self, client, setup):
        response = self._rest(client, setup['write_key'], 'ADR-1', {'status': 'proposed'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['changed'] is False
        assert 'No change' in data['message']
        assert _history(setup['first'].id) == []

    @pytest.mark.parametrize('body,fragment', [
        ({'status': 'done'}, 'Invalid status'),
        ({'status': 'superseded'}, "'superseded' cannot be set directly"),
        ({'reason': 'no status'}, 'Missing required field: status'),
        ({'status': 'accepted', 'reason': 'x' * 501}, 'exceeds maximum length'),
        ({'status': 'accepted', 'reason': 5}, 'must be a string'),
        ({}, 'No data provided'),
    ])
    def test_rest_bad_requests(self, client, setup, body, fragment):
        response = self._rest(client, setup['write_key'], 'ADR-1', body)
        assert response.status_code == 400
        assert fragment in response.get_json()['error']
        assert db.session.get(ArchitectureDecision, setup['first'].id).status == 'proposed'
        assert _history(setup['first'].id) == []

    def test_rest_unknown_and_other_tenant_ids_give_the_same_404(self, client, setup):
        _, _, foreign = _make_other_tenant()
        foreign_response = self._rest(client, setup['write_key'], str(foreign.id), {'status': 'archived'})
        unknown_response = self._rest(client, setup['write_key'], '99999', {'status': 'archived'})
        assert foreign_response.status_code == unknown_response.status_code == 404
        assert foreign_response.get_json() == {'error': f'Decision not found: {foreign.id}'}
        assert unknown_response.get_json() == {'error': 'Decision not found: 99999'}
        assert db.session.get(ArchitectureDecision, foreign.id).status == 'accepted'
        assert _history(foreign.id) == []

    def test_rest_deleted_decision_is_404(self, client, setup):
        setup['first'].deleted_at = datetime.now(timezone.utc)
        db.session.commit()
        response = self._rest(client, setup['write_key'], 'ADR-1', {'status': 'accepted'})
        assert response.status_code == 404
        assert db.session.get(ArchitectureDecision, setup['first'].id).status == 'proposed'

    def test_rest_read_only_key_is_403(self, client, setup):
        response = self._rest(client, setup['read_key'], 'ADR-1', {'status': 'accepted'})
        assert response.status_code == 403
        assert 'write' in response.get_json()['error']
        assert db.session.get(ArchitectureDecision, setup['first'].id).status == 'proposed'

    def test_rest_without_a_key_is_401(self, client, setup):
        response = self._rest(client, None, 'ADR-1', {'status': 'accepted'})
        assert response.status_code == 401
        assert db.session.get(ArchitectureDecision, setup['first'].id).status == 'proposed'

    def test_rest_notifies_once(self, client, setup):
        with patch(SLACK_HOOK) as slack, patch(EMAIL_HOOK) as email, \
                patch('feature_flags.is_slack_enabled', return_value=True):
            self._rest(client, setup['write_key'], 'ADR-1', {'status': 'accepted'})
        slack.assert_called_once()
        email.assert_called_once()

    def test_openapi_describes_the_operation(self, client, setup):
        schema = client.get('/api/ai/openapi.json').get_json()
        operation = schema['paths']['/decisions/{id}/status']['put']
        assert operation['operationId'] == 'updateDecisionStatus'
        body = schema['components']['schemas']['UpdateDecisionStatus']
        assert body['required'] == ['status']
        assert body['properties']['status']['enum'] == ['proposed', 'accepted', 'archived']
        assert 'UpdateStatusResult' in schema['components']['schemas']

    # --- parity with the web route -----------------------------------------

    def _web_update(self, real_app, user, decision_id, body):
        """Call the web app's PUT /api/decisions/<id> view as a signed-in user."""
        from flask import g
        view = real_app.view_functions['api_update_decision'].__wrapped__  # skip the session check
        with real_app.test_request_context(f'/api/decisions/{decision_id}', method='PUT', json=body):
            g.current_user = user
            response = view(decision_id)
        if isinstance(response, tuple):
            return response[0], response[1]
        return response, response.status_code

    def test_mcp_change_matches_the_web_route(self, real_app, client, setup):
        """
        The update logic lives inside the Flask route, so the MCP tool mirrors it.
        Make the same change through both and compare everything that is recorded.
        """
        user, first, second = setup['user'], setup['first'], setup['second']
        body = {'status': 'accepted', 'change_reason': 'Agreed in planning'}

        with patch('app.notify_subscribers_decision_updated') as web_email, \
                patch('app.is_slack_enabled', return_value=True), \
                patch(SLACK_HOOK) as web_slack:
            _, web_status = self._web_update(real_app, user, first.id, body)
        assert web_status == 200

        with patch(EMAIL_HOOK) as mcp_email, \
                patch('feature_flags.is_slack_enabled', return_value=True), \
                patch(SLACK_HOOK) as mcp_slack:
            response = self._mcp(
                client, setup['write_key'],
                {'id': str(second.id), 'status': 'accepted', 'reason': 'Agreed in planning'},
            )
        assert response.status_code == 200

        web_decision = db.session.get(ArchitectureDecision, first.id)
        mcp_decision = db.session.get(ArchitectureDecision, second.id)
        assert web_decision.status == mcp_decision.status == 'accepted'
        assert web_decision.updated_by_id == mcp_decision.updated_by_id == user.id

        web_history, mcp_history = _history(first.id), _history(second.id)
        assert len(web_history) == len(mcp_history) == 1
        for field in ('status', 'change_reason', 'changed_by_id', 'context', 'decision_text', 'consequences'):
            assert getattr(web_history[0], field) == getattr(mcp_history[0], field), field
        assert web_history[0].status == 'proposed'
        assert web_history[0].change_reason == 'Agreed in planning'

        # Same notifications, once each, with the same arguments after `db` and the decision.
        web_email.assert_called_once()
        mcp_email.assert_called_once()
        assert web_email.call_args.args[3:] == mcp_email.call_args.args[3:] == ('Agreed in planning', True)
        assert web_email.call_args.args[1].id == first.id
        assert mcp_email.call_args.args[1].id == second.id
        web_slack.assert_called_once()
        mcp_slack.assert_called_once()

    def test_noop_matches_the_web_route(self, real_app, client, setup):
        user, first, second = setup['user'], setup['first'], setup['second']

        with patch('app.notify_subscribers_decision_updated') as web_email:
            self._web_update(real_app, user, first.id, {'status': 'proposed', 'change_reason': 'none'})
        with patch(EMAIL_HOOK) as mcp_email:
            self._mcp(client, setup['write_key'], {'id': str(second.id), 'status': 'proposed', 'reason': 'none'})

        assert _history(first.id) == _history(second.id) == []
        web_email.assert_not_called()
        mcp_email.assert_not_called()

    def test_web_route_also_lets_a_plain_member_change_status(self, real_app, setup):
        """Pins the rule the tool copies: the route asks for no role beyond membership."""
        membership = TenantMembership.query.filter_by(user_id=setup['user'].id).one()
        assert membership.global_role == GlobalRole.USER
        with patch('app.notify_subscribers_decision_updated'):
            _, status = self._web_update(real_app, setup['user'], setup['first'].id, {'status': 'archived'})
        assert status == 200
        assert db.session.get(ArchitectureDecision, setup['first'].id).status == 'archived'

    def test_web_route_does_not_find_another_organizations_decision(self, real_app, setup):
        """Pins the rule behind NOT_PERMITTED: the route scopes decisions to the user's organization."""
        from werkzeug.exceptions import NotFound
        _, outsider, _ = _make_other_tenant()
        with pytest.raises(NotFound):
            self._web_update(real_app, outsider, setup['first'].id, {'status': 'archived'})
        assert db.session.get(ArchitectureDecision, setup['first'].id).status == 'proposed'

    def test_web_route_rejects_an_invalid_status_too(self, real_app, setup):
        response, status = self._web_update(real_app, setup['user'], setup['first'].id, {'status': 'done'})
        assert status == 400
        assert 'Invalid status' in response.get_json()['error']
