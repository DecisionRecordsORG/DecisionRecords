"""
External AI API Routes.

REST API endpoints for external AI tools like Custom GPTs and AI agents.
Authentication is via API key in Authorization header.
"""

import logging
from datetime import datetime, timezone
from functools import wraps
from typing import Tuple, Optional, Dict, Any

from flask import request, jsonify, Blueprint

from models import (
    db, ArchitectureDecision, DecisionHistory, User, Tenant,
    AIApiKey, AIChannel, AIAction
)
from ai.config import AIConfig
from ai.api_keys import AIApiKeyService
from ai.interaction_log import AIInteractionLogger

logger = logging.getLogger(__name__)

# Create Blueprint for AI API routes
ai_api = Blueprint('ai_api', __name__, url_prefix='/api/ai')


def require_ai_api_key(required_scopes=None):
    """
    Decorator to require and validate AI API key authentication.

    Args:
        required_scopes: List of scopes required for the endpoint (e.g., ['read'], ['write'])
    """
    if required_scopes is None:
        required_scopes = ['read']

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check system-level availability
            if not AIConfig.get_system_ai_enabled():
                return jsonify({'error': 'AI features are not enabled'}), 503

            if not AIConfig.get_system_external_api_enabled():
                return jsonify({'error': 'External AI API is not enabled'}), 503

            # Get API key from Authorization header
            auth_header = request.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer '):
                return jsonify({
                    'error': 'Missing or invalid Authorization header',
                    'hint': 'Use: Authorization: Bearer <api_key>'
                }), 401

            api_key_value = auth_header[7:]  # Remove 'Bearer ' prefix

            # Validate API key
            api_key = AIApiKeyService.validate_key(api_key_value)
            if not api_key:
                return jsonify({'error': 'Invalid or expired API key'}), 401

            # Get user and tenant
            user = User.query.get(api_key.user_id)
            tenant = Tenant.query.get(api_key.tenant_id)

            if not user or not tenant:
                return jsonify({'error': 'User or tenant not found'}), 401

            # Check tenant AI settings
            if not tenant.ai_features_enabled:
                return jsonify({'error': 'AI features are not enabled for this organization'}), 403

            if not tenant.ai_external_access_enabled:
                return jsonify({'error': 'External AI access is not enabled for this organization'}), 403

            # Check user opt-out
            if AIConfig.get_user_ai_opt_out(user, tenant):
                return jsonify({'error': 'User has opted out of AI features'}), 403

            # Check required scopes
            for scope in required_scopes:
                if not AIApiKeyService.has_scope(api_key, scope):
                    return jsonify({
                        'error': f'API key does not have required scope: {scope}'
                    }), 403

            # Add context to request
            request.ai_api_key = api_key
            request.ai_user = user
            request.ai_tenant = tenant

            return f(*args, **kwargs)

        return decorated_function
    return decorator


# --- Search Endpoint ---

@ai_api.route('/search', methods=['POST'])
@require_ai_api_key(required_scopes=['search'])
def api_ai_search():
    """
    Search architecture decisions.

    Request body:
    {
        "query": "search terms",
        "status": "accepted",  // optional: proposed, accepted, archived, superseded
        "limit": 10            // optional: 1-50, default 10
    }
    """
    start_time = datetime.now(timezone.utc)
    tenant = request.ai_tenant
    user = request.ai_user

    data = request.get_json() or {}
    query_text = data.get('query', '')
    status = data.get('status')
    limit = min(max(int(data.get('limit', 10)), 1), 50)

    # Build query
    query = ArchitectureDecision.query.filter(
        ArchitectureDecision.tenant_id == tenant.id,
        ArchitectureDecision.deleted_at == None
    )

    # Apply text search
    if query_text:
        pattern = f"%{query_text}%"
        query = query.filter(
            db.or_(
                ArchitectureDecision.title.ilike(pattern),
                ArchitectureDecision.context.ilike(pattern),
                ArchitectureDecision.decision.ilike(pattern),
                ArchitectureDecision.consequences.ilike(pattern)
            )
        )

    # Apply status filter
    if status:
        valid_statuses = ['proposed', 'accepted', 'archived', 'superseded']
        if status not in valid_statuses:
            return jsonify({'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}), 400
        query = query.filter(ArchitectureDecision.status == status)

    # Execute
    decisions = query.order_by(
        ArchitectureDecision.created_at.desc()
    ).limit(limit).all()

    result = {
        'query': query_text,
        'count': len(decisions),
        'decisions': [_format_decision_summary(d) for d in decisions]
    }

    # Log interaction
    duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
    if tenant.ai_log_interactions:
        AIInteractionLogger.log_interaction(
            channel=AIChannel.API,
            action=AIAction.SEARCH,
            tenant_id=tenant.id,
            user_id=user.id,
            query_text=query_text[:500],
            decision_ids=[d.id for d in decisions],
            duration_ms=duration_ms
        )

    return jsonify(result)


# --- List Decisions Endpoint ---

@ai_api.route('/decisions', methods=['GET'])
@require_ai_api_key(required_scopes=['read'])
def api_ai_list_decisions():
    """
    List architecture decisions with pagination.

    Query parameters:
    - status: Filter by status (proposed, accepted, archived, superseded)
    - limit: Max results (1-100, default 20)
    - offset: Pagination offset (default 0)
    - order_by: Sort field (created_at, updated_at, decision_number)
    - order: Sort direction (asc, desc)
    """
    start_time = datetime.now(timezone.utc)
    tenant = request.ai_tenant
    user = request.ai_user

    status = request.args.get('status')
    limit = min(max(int(request.args.get('limit', 20)), 1), 100)
    offset = max(int(request.args.get('offset', 0)), 0)
    order_by = request.args.get('order_by', 'created_at')
    order = request.args.get('order', 'desc')

    # Validate order_by
    valid_order_by = ['created_at', 'updated_at', 'decision_number']
    if order_by not in valid_order_by:
        return jsonify({'error': f'Invalid order_by. Must be one of: {", ".join(valid_order_by)}'}), 400

    # Validate order
    if order not in ['asc', 'desc']:
        return jsonify({'error': 'Invalid order. Must be asc or desc'}), 400

    # Build query
    query = ArchitectureDecision.query.filter(
        ArchitectureDecision.tenant_id == tenant.id,
        ArchitectureDecision.deleted_at == None
    )

    # Apply status filter
    if status:
        valid_statuses = ['proposed', 'accepted', 'archived', 'superseded']
        if status not in valid_statuses:
            return jsonify({'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}), 400
        query = query.filter(ArchitectureDecision.status == status)

    # Apply ordering
    order_column = getattr(ArchitectureDecision, order_by, ArchitectureDecision.created_at)
    if order == 'asc':
        query = query.order_by(order_column.asc())
    else:
        query = query.order_by(order_column.desc())

    # Get total count
    total = query.count()

    # Apply pagination
    decisions = query.offset(offset).limit(limit).all()

    result = {
        'total': total,
        'offset': offset,
        'limit': limit,
        'count': len(decisions),
        'decisions': [_format_decision_summary(d) for d in decisions]
    }

    # Log interaction
    duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
    if tenant.ai_log_interactions:
        AIInteractionLogger.log_interaction(
            channel=AIChannel.API,
            action=AIAction.SEARCH,
            tenant_id=tenant.id,
            user_id=user.id,
            decision_ids=[d.id for d in decisions],
            duration_ms=duration_ms
        )

    return jsonify(result)


# --- Get Decision Endpoint ---

@ai_api.route('/decisions/<decision_id>', methods=['GET'])
@require_ai_api_key(required_scopes=['read'])
def api_ai_get_decision(decision_id):
    """
    Get a specific architecture decision by ID.

    The decision_id can be:
    - Numeric ID (e.g., "42")
    - Display ID (e.g., "ADR-42")
    """
    import re
    start_time = datetime.now(timezone.utc)
    tenant = request.ai_tenant
    user = request.ai_user

    decision = _find_decision_by_id(decision_id, tenant.id)
    if not decision:
        return jsonify({'error': f'Decision not found: {decision_id}'}), 404

    result = _format_decision_full(decision)

    # Log interaction
    duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
    if tenant.ai_log_interactions:
        AIInteractionLogger.log_interaction(
            channel=AIChannel.API,
            action=AIAction.READ,
            tenant_id=tenant.id,
            user_id=user.id,
            decision_ids=[decision.id],
            duration_ms=duration_ms
        )

    return jsonify(result)


# --- Create Decision Endpoint ---

@ai_api.route('/decisions', methods=['POST'])
@require_ai_api_key(required_scopes=['write'])
def api_ai_create_decision():
    """
    Create a new architecture decision.

    Request body:
    {
        "title": "Decision title",          // required
        "context": "Background and forces",  // required
        "decision": "What was decided",      // required
        "consequences": "Impacts",           // required
        "status": "proposed"                 // optional: proposed, accepted
    }
    """
    start_time = datetime.now(timezone.utc)
    tenant = request.ai_tenant
    user = request.ai_user

    data = request.get_json() or {}

    # Validate required fields
    required_fields = ['title', 'context', 'decision', 'consequences']
    for field in required_fields:
        if not data.get(field, '').strip():
            return jsonify({'error': f'Missing required field: {field}'}), 400

    title = data['title'].strip()
    context = data['context'].strip()
    decision_text = data['decision'].strip()
    consequences = data['consequences'].strip()
    status = data.get('status', 'proposed')

    # Validate status
    valid_statuses = ['proposed', 'accepted']
    if status not in valid_statuses:
        return jsonify({'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}), 400

    # Validate title length
    if len(title) > 255:
        return jsonify({'error': 'Title exceeds maximum length of 255 characters'}), 400

    # Get next decision number
    max_number = db.session.query(db.func.max(ArchitectureDecision.decision_number)).filter(
        ArchitectureDecision.tenant_id == tenant.id
    ).scalar() or 0
    next_number = max_number + 1

    # Create decision
    decision = ArchitectureDecision(
        title=title,
        context=context,
        decision=decision_text,
        consequences=consequences,
        status=status,
        decision_number=next_number,
        domain=tenant.domain,
        tenant_id=tenant.id,
        created_by_id=user.id,
        updated_by_id=user.id
    )

    db.session.add(decision)
    db.session.commit()

    result = {
        'message': 'Decision created successfully',
        'decision': _format_decision_full(decision)
    }

    # Log interaction
    duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
    if tenant.ai_log_interactions:
        AIInteractionLogger.log_interaction(
            channel=AIChannel.API,
            action=AIAction.CREATE,
            tenant_id=tenant.id,
            user_id=user.id,
            decision_ids=[decision.id],
            duration_ms=duration_ms
        )

    return jsonify(result), 201


# --- Get Decision History Endpoint ---

@ai_api.route('/decisions/<decision_id>/history', methods=['GET'])
@require_ai_api_key(required_scopes=['read'])
def api_ai_get_decision_history(decision_id):
    """
    Get the change history of a decision.

    Query parameters:
    - limit: Max entries (1-100, default 20)
    """
    import re
    start_time = datetime.now(timezone.utc)
    tenant = request.ai_tenant
    user = request.ai_user

    limit = min(max(int(request.args.get('limit', 20)), 1), 100)

    decision = _find_decision_by_id(decision_id, tenant.id)
    if not decision:
        return jsonify({'error': f'Decision not found: {decision_id}'}), 404

    # Get history
    history = DecisionHistory.query.filter_by(
        decision_id=decision.id
    ).order_by(DecisionHistory.changed_at.desc()).limit(limit).all()

    display_id = decision.get_display_id() if hasattr(decision, 'get_display_id') else f"ADR-{decision.decision_number}"

    result = {
        'decision_id': decision.id,
        'display_id': display_id,
        'history': [_format_history_entry(h) for h in history]
    }

    # Log interaction
    duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
    if tenant.ai_log_interactions:
        AIInteractionLogger.log_interaction(
            channel=AIChannel.API,
            action=AIAction.READ,
            tenant_id=tenant.id,
            user_id=user.id,
            decision_ids=[decision.id],
            duration_ms=duration_ms
        )

    return jsonify(result)


# --- OpenAPI Schema Endpoint ---

@ai_api.route('/openapi.json', methods=['GET'])
def api_ai_openapi_schema():
    """
    Get OpenAPI schema for Custom GPT configuration.

    This schema describes the available endpoints for AI tools.
    No authentication required for this endpoint.
    """
    schema = _generate_openapi_schema()
    return jsonify(schema)


# --- Helper Functions ---

def _find_decision_by_id(decision_id: str, tenant_id: int) -> Optional[ArchitectureDecision]:
    """Find a decision by ID (supports ADR-XXX or numeric format)."""
    import re

    # Try as numeric ID first
    if decision_id.isdigit():
        return ArchitectureDecision.query.filter_by(
            id=int(decision_id),
            tenant_id=tenant_id,
            deleted_at=None
        ).first()

    # Try to parse ADR-XXX format
    match = re.search(r'\d+', decision_id)
    if match:
        number = int(match.group())
        return ArchitectureDecision.query.filter_by(
            decision_number=number,
            tenant_id=tenant_id,
            deleted_at=None
        ).first()

    return None


def _format_decision_summary(decision: ArchitectureDecision) -> Dict[str, Any]:
    """Format a decision for list/search results."""
    display_id = decision.get_display_id() if hasattr(decision, 'get_display_id') else f"ADR-{decision.decision_number}"
    return {
        'id': decision.id,
        'display_id': display_id,
        'title': decision.title,
        'status': decision.status,
        'created_at': decision.created_at.isoformat() if decision.created_at else None,
        'context_preview': (decision.context[:200] + '...') if decision.context and len(decision.context) > 200 else decision.context
    }


def _format_decision_full(decision: ArchitectureDecision) -> Dict[str, Any]:
    """Format a decision with full details."""
    display_id = decision.get_display_id() if hasattr(decision, 'get_display_id') else f"ADR-{decision.decision_number}"

    creator_name = None
    if decision.creator:
        creator_name = decision.creator.name or decision.creator.email

    owner_name = None
    if decision.owner:
        owner_name = decision.owner.name or decision.owner.email
    elif decision.owner_email:
        owner_name = decision.owner_email

    return {
        'id': decision.id,
        'display_id': display_id,
        'decision_number': decision.decision_number,
        'title': decision.title,
        'status': decision.status,
        'context': decision.context,
        'decision': decision.decision,
        'consequences': decision.consequences,
        'created_at': decision.created_at.isoformat() if decision.created_at else None,
        'updated_at': decision.updated_at.isoformat() if decision.updated_at else None,
        'creator': creator_name,
        'owner': owner_name,
    }


def _format_history_entry(history: DecisionHistory) -> Dict[str, Any]:
    """Format a history entry.

    DecisionHistory stores full snapshots of the decision state at each change.
    """
    changed_by = None
    if history.changed_by:
        changed_by = history.changed_by.name or history.changed_by.email

    return {
        'changed_at': history.changed_at.isoformat() if history.changed_at else None,
        'changed_by': changed_by,
        'change_reason': history.change_reason,
        'title': history.title,
        'status': history.status,
        'context': history.context[:500] if history.context else None,
        'decision': history.decision_text[:500] if history.decision_text else None,
        'consequences': history.consequences[:500] if history.consequences else None,
    }


def _generate_openapi_schema() -> Dict[str, Any]:
    """Generate OpenAPI 3.1 schema for Custom GPT configuration."""
    return {
        'openapi': '3.1.0',
        'info': {
            'title': 'Architecture Decisions AI API',
            'description': 'API for AI tools to search, read, and create architecture decision records (ADRs)',
            'version': '1.0.0',
            'contact': {
                'name': 'Architecture Decisions',
                'url': 'https://decisionrecords.org'
            }
        },
        'servers': [
            {
                'url': 'https://decisionrecords.org/api/ai',
                'description': 'Production server'
            }
        ],
        'security': [
            {'bearerAuth': []}
        ],
        'paths': {
            '/search': {
                'post': {
                    'operationId': 'searchDecisions',
                    'summary': 'Search architecture decisions',
                    'description': 'Search for decisions using keywords and optional filters',
                    'requestBody': {
                        'required': True,
                        'content': {
                            'application/json': {
                                'schema': {
                                    'type': 'object',
                                    'properties': {
                                        'query': {
                                            'type': 'string',
                                            'description': 'Search keywords'
                                        },
                                        'status': {
                                            'type': 'string',
                                            'enum': ['proposed', 'accepted', 'archived', 'superseded'],
                                            'description': 'Filter by decision status'
                                        },
                                        'limit': {
                                            'type': 'integer',
                                            'minimum': 1,
                                            'maximum': 50,
                                            'default': 10,
                                            'description': 'Maximum results to return'
                                        }
                                    },
                                    'required': ['query']
                                }
                            }
                        }
                    },
                    'responses': {
                        '200': {
                            'description': 'Search results',
                            'content': {
                                'application/json': {
                                    'schema': {'$ref': '#/components/schemas/SearchResult'}
                                }
                            }
                        }
                    }
                }
            },
            '/decisions': {
                'get': {
                    'operationId': 'listDecisions',
                    'summary': 'List architecture decisions',
                    'description': 'List decisions with optional filtering and pagination',
                    'parameters': [
                        {
                            'name': 'status',
                            'in': 'query',
                            'schema': {
                                'type': 'string',
                                'enum': ['proposed', 'accepted', 'archived', 'superseded']
                            }
                        },
                        {
                            'name': 'limit',
                            'in': 'query',
                            'schema': {'type': 'integer', 'default': 20, 'minimum': 1, 'maximum': 100}
                        },
                        {
                            'name': 'offset',
                            'in': 'query',
                            'schema': {'type': 'integer', 'default': 0, 'minimum': 0}
                        }
                    ],
                    'responses': {
                        '200': {
                            'description': 'List of decisions',
                            'content': {
                                'application/json': {
                                    'schema': {'$ref': '#/components/schemas/ListResult'}
                                }
                            }
                        }
                    }
                },
                'post': {
                    'operationId': 'createDecision',
                    'summary': 'Create a new decision',
                    'description': 'Create a new architecture decision record',
                    'requestBody': {
                        'required': True,
                        'content': {
                            'application/json': {
                                'schema': {'$ref': '#/components/schemas/CreateDecision'}
                            }
                        }
                    },
                    'responses': {
                        '201': {
                            'description': 'Decision created',
                            'content': {
                                'application/json': {
                                    'schema': {'$ref': '#/components/schemas/CreateResult'}
                                }
                            }
                        }
                    }
                }
            },
            '/decisions/{id}': {
                'get': {
                    'operationId': 'getDecision',
                    'summary': 'Get a specific decision',
                    'description': 'Get full details of a decision by ID (numeric or ADR-XXX format)',
                    'parameters': [
                        {
                            'name': 'id',
                            'in': 'path',
                            'required': True,
                            'schema': {'type': 'string'},
                            'description': 'Decision ID (e.g., "42" or "ADR-42")'
                        }
                    ],
                    'responses': {
                        '200': {
                            'description': 'Decision details',
                            'content': {
                                'application/json': {
                                    'schema': {'$ref': '#/components/schemas/Decision'}
                                }
                            }
                        },
                        '404': {
                            'description': 'Decision not found'
                        }
                    }
                }
            },
            '/decisions/{id}/history': {
                'get': {
                    'operationId': 'getDecisionHistory',
                    'summary': 'Get decision change history',
                    'description': 'Get the change history of a specific decision',
                    'parameters': [
                        {
                            'name': 'id',
                            'in': 'path',
                            'required': True,
                            'schema': {'type': 'string'}
                        },
                        {
                            'name': 'limit',
                            'in': 'query',
                            'schema': {'type': 'integer', 'default': 20, 'minimum': 1, 'maximum': 100}
                        }
                    ],
                    'responses': {
                        '200': {
                            'description': 'History entries',
                            'content': {
                                'application/json': {
                                    'schema': {'$ref': '#/components/schemas/HistoryResult'}
                                }
                            }
                        }
                    }
                }
            }
        },
        'components': {
            'securitySchemes': {
                'bearerAuth': {
                    'type': 'http',
                    'scheme': 'bearer',
                    'description': 'API key from your Architecture Decisions account'
                }
            },
            'schemas': {
                'DecisionSummary': {
                    'type': 'object',
                    'properties': {
                        'id': {'type': 'integer'},
                        'display_id': {'type': 'string'},
                        'title': {'type': 'string'},
                        'status': {'type': 'string'},
                        'created_at': {'type': 'string', 'format': 'date-time'},
                        'context_preview': {'type': 'string'}
                    }
                },
                'Decision': {
                    'type': 'object',
                    'properties': {
                        'id': {'type': 'integer'},
                        'display_id': {'type': 'string'},
                        'decision_number': {'type': 'integer'},
                        'title': {'type': 'string'},
                        'status': {'type': 'string'},
                        'context': {'type': 'string'},
                        'decision': {'type': 'string'},
                        'consequences': {'type': 'string'},
                        'created_at': {'type': 'string', 'format': 'date-time'},
                        'updated_at': {'type': 'string', 'format': 'date-time'},
                        'creator': {'type': 'string'},
                        'owner': {'type': 'string'}
                    }
                },
                'CreateDecision': {
                    'type': 'object',
                    'required': ['title', 'context', 'decision', 'consequences'],
                    'properties': {
                        'title': {'type': 'string', 'maxLength': 255},
                        'context': {'type': 'string'},
                        'decision': {'type': 'string'},
                        'consequences': {'type': 'string'},
                        'status': {
                            'type': 'string',
                            'enum': ['proposed', 'accepted'],
                            'default': 'proposed'
                        }
                    }
                },
                'SearchResult': {
                    'type': 'object',
                    'properties': {
                        'query': {'type': 'string'},
                        'count': {'type': 'integer'},
                        'decisions': {
                            'type': 'array',
                            'items': {'$ref': '#/components/schemas/DecisionSummary'}
                        }
                    }
                },
                'ListResult': {
                    'type': 'object',
                    'properties': {
                        'total': {'type': 'integer'},
                        'offset': {'type': 'integer'},
                        'limit': {'type': 'integer'},
                        'count': {'type': 'integer'},
                        'decisions': {
                            'type': 'array',
                            'items': {'$ref': '#/components/schemas/DecisionSummary'}
                        }
                    }
                },
                'CreateResult': {
                    'type': 'object',
                    'properties': {
                        'message': {'type': 'string'},
                        'decision': {'$ref': '#/components/schemas/Decision'}
                    }
                },
                'HistoryEntry': {
                    'type': 'object',
                    'properties': {
                        'changed_at': {'type': 'string', 'format': 'date-time'},
                        'changed_by': {'type': 'string'},
                        'change_reason': {'type': 'string'},
                        'title': {'type': 'string'},
                        'status': {'type': 'string'},
                        'context': {'type': 'string'},
                        'decision': {'type': 'string'},
                        'consequences': {'type': 'string'}
                    }
                },
                'HistoryResult': {
                    'type': 'object',
                    'properties': {
                        'decision_id': {'type': 'integer'},
                        'display_id': {'type': 'string'},
                        'history': {
                            'type': 'array',
                            'items': {'$ref': '#/components/schemas/HistoryEntry'}
                        }
                    }
                }
            }
        }
    }
