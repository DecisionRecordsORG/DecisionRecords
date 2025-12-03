import os
from flask import Flask, render_template, request, jsonify, abort
from models import db, ArchitectureDecision, DecisionHistory, save_history

app = Flask(__name__)

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///architecture_decisions.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Initialize database
db.init_app(app)

# Create tables on startup
with app.app_context():
    db.create_all()


# ==================== Web Routes ====================

@app.route('/')
def index():
    """Home page - list all architecture decisions."""
    return render_template('index.html')


@app.route('/decision/<int:decision_id>')
def view_decision(decision_id):
    """View a single architecture decision."""
    return render_template('decision.html', decision_id=decision_id)


@app.route('/decision/new')
def new_decision():
    """Create a new architecture decision."""
    return render_template('decision.html', decision_id=None)


# ==================== API Routes ====================

@app.route('/api/decisions', methods=['GET'])
def api_list_decisions():
    """List all architecture decisions."""
    decisions = ArchitectureDecision.query.order_by(ArchitectureDecision.id.desc()).all()
    return jsonify([d.to_dict() for d in decisions])


@app.route('/api/decisions', methods=['POST'])
def api_create_decision():
    """Create a new architecture decision."""
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Validate required fields
    required_fields = ['title', 'context', 'decision', 'consequences']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'Missing required field: {field}'}), 400

    # Validate status if provided
    status = data.get('status', 'proposed')
    if status not in ArchitectureDecision.VALID_STATUSES:
        return jsonify({'error': f'Invalid status. Must be one of: {", ".join(ArchitectureDecision.VALID_STATUSES)}'}), 400

    decision = ArchitectureDecision(
        title=data['title'],
        context=data['context'],
        decision=data['decision'],
        status=status,
        consequences=data['consequences']
    )

    db.session.add(decision)
    db.session.commit()

    return jsonify(decision.to_dict()), 201


@app.route('/api/decisions/<int:decision_id>', methods=['GET'])
def api_get_decision(decision_id):
    """Get a single architecture decision with its history."""
    decision = ArchitectureDecision.query.get_or_404(decision_id)
    return jsonify(decision.to_dict_with_history())


@app.route('/api/decisions/<int:decision_id>', methods=['PUT'])
def api_update_decision(decision_id):
    """Update an architecture decision."""
    decision = ArchitectureDecision.query.get_or_404(decision_id)
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Validate status if provided
    if 'status' in data and data['status'] not in ArchitectureDecision.VALID_STATUSES:
        return jsonify({'error': f'Invalid status. Must be one of: {", ".join(ArchitectureDecision.VALID_STATUSES)}'}), 400

    # Check if there are actual changes
    has_changes = False
    for field in ['title', 'context', 'decision', 'status', 'consequences']:
        if field in data and data[field] != getattr(decision, field):
            has_changes = True
            break

    if not has_changes:
        return jsonify(decision.to_dict_with_history())

    # Save current state to history before updating
    change_reason = data.get('change_reason', None)
    save_history(decision, change_reason)

    # Update fields
    if 'title' in data:
        decision.title = data['title']
    if 'context' in data:
        decision.context = data['context']
    if 'decision' in data:
        decision.decision = data['decision']
    if 'status' in data:
        decision.status = data['status']
    if 'consequences' in data:
        decision.consequences = data['consequences']

    db.session.commit()

    return jsonify(decision.to_dict_with_history())


@app.route('/api/decisions/<int:decision_id>', methods=['DELETE'])
def api_delete_decision(decision_id):
    """Delete an architecture decision and its history."""
    decision = ArchitectureDecision.query.get_or_404(decision_id)

    # Delete associated history
    DecisionHistory.query.filter_by(decision_id=decision_id).delete()

    db.session.delete(decision)
    db.session.commit()

    return jsonify({'message': 'Decision deleted successfully'})


@app.route('/api/decisions/<int:decision_id>/history', methods=['GET'])
def api_get_decision_history(decision_id):
    """Get the update history for a decision."""
    decision = ArchitectureDecision.query.get_or_404(decision_id)
    history = DecisionHistory.query.filter_by(decision_id=decision_id).order_by(DecisionHistory.changed_at.desc()).all()
    return jsonify([h.to_dict() for h in history])


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
