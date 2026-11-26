"""
What the server sends to the analytics service, and for whom.

Two promises are pinned here, against the real application and a client that
records what it is handed instead of sending it:

1. The "Analytics" switch on the profile page is real. With it off (or never
   switched on) a signed-in person's events and error reports still count,
   but carry no code for the person and none for their organisation.
2. An event never carries what was typed: no decision title or text, no
   name, no email address, not in a property and not inside an address or an
   error message.
"""

import json

import pytest

from models import (
    db, User, Tenant, TenantMembership, GlobalRole, MaturityState, UserConsent, ArchitectureDecision,
)
from tests.app_test_utils import load_test_app

try:
    from ee.backend.analytics import analytics
    EE_AVAILABLE = True
except ImportError:
    EE_AVAILABLE = False

import os

pytestmark = pytest.mark.skipif(
    not EE_AVAILABLE or os.environ.get('DECISION_RECORDS_EDITION', 'community') != 'enterprise',
    reason="Enterprise Edition tests require DECISION_RECORDS_EDITION=enterprise and EE modules",
)

PASSWORD = 'a-long-test-password'
DOMAIN = 'quietco.test'
TITLE = 'Acquire Northwind Traders for 40 million'
BODY = 'Zebedee Quince negotiated the Northwind price down'
FIRST, LAST = 'Zebedee', 'Quince'


class RecordingClient:
    """Stands in for the PostHog client: keeps every capture, sends nothing."""

    def __init__(self):
        self.events = []

    def capture(self, distinct_id=None, event=None, properties=None, **extra):
        self.events.append({'distinct_id': distinct_id, 'event': event, 'properties': dict(properties or {}),
                            'extra': extra})

    def flush(self):
        pass

    def shutdown(self):
        pass


@pytest.fixture
def app_module_and_app():
    app_module, test_app = load_test_app(secret_key='test-secret-key-analytics-privacy-12345')
    with test_app.app_context():
        db.create_all()
        app_module.init_database()
        yield app_module, test_app
        db.session.remove()
        db.drop_all()
        app_module._db_initialized = False


@pytest.fixture
def api_app(app_module_and_app):
    return app_module_and_app[1]


@pytest.fixture
def recorded(api_app, monkeypatch):
    """Analytics switched on for the installation, with a recording client."""
    client = RecordingClient()
    config = {
        'enabled': True, 'host': 'https://analytics.invalid', 'api_key': 'phc_test',
        'person_profiling': True, 'exception_capture': True,
        'event_mappings': dict(analytics.DEFAULT_EVENT_MAPPINGS), 'posthog_client': client,
    }
    # A super admin can map any endpoint to an event. Map the ones whose
    # address holds an identifier or an email address, so they are exercised.
    config['event_mappings'].update({
        'api_get_decision': 'decision_viewed',
        'api_update_decision': 'decision_updated',
        '_api_check_user_exists_impl': 'user_existence_checked',
    })
    monkeypatch.setattr(analytics, '_get_analytics_config', lambda: config)
    return client.events


def make_member(local='zebedee', first=FIRST, last=LAST):
    tenant = Tenant.query.filter_by(domain=DOMAIN).first()
    if tenant is None:
        tenant = Tenant(domain=DOMAIN, name='Quiet Co', status='active', maturity_state=MaturityState.BOOTSTRAP)
        db.session.add(tenant)
        db.session.commit()
    user = User(email=f'{local}@{DOMAIN}', sso_domain=DOMAIN, auth_type='local', email_verified=True)
    user.set_name(first_name=first, last_name=last)
    user.set_password(PASSWORD)
    db.session.add(user)
    db.session.flush()
    db.session.add(TenantMembership(user_id=user.id, tenant_id=tenant.id, global_role=GlobalRole.ADMIN))
    db.session.commit()
    return user


def sign_in(api_app, user):
    client = api_app.test_client()
    response = client.post('/api/auth/login', json={'email': user.email, 'password': PASSWORD})
    assert response.status_code == 200, response.data
    token = response.headers.get('X-CSRF-Token') or client.get('/api/auth/csrf-token').get_json()['csrf_token']
    client.environ_base['HTTP_X_CSRF_TOKEN'] = token
    return client


def switch(user, granted):
    db.session.add(UserConsent(user_id=user.id, consent_type=UserConsent.CONSENT_ANALYTICS, granted=granted))
    db.session.commit()


def personal_codes(user):
    person = analytics.generate_distinct_id(user.id, DOMAIN)
    import hashlib
    organisation = hashlib.sha256(DOMAIN.encode()).hexdigest()[:16]
    return person, organisation


def use_the_product(client):
    """A few ordinary requests: create, read, list and change a decision."""
    created = client.post('/api/decisions', json={
        'title': TITLE, 'context': BODY, 'decision': BODY, 'consequences': BODY, 'status': 'proposed'})
    assert created.status_code in (200, 201), created.data
    decision_id = created.get_json()['id']
    assert client.get(f'/api/decisions/{decision_id}').status_code == 200
    assert client.get('/api/decisions').status_code == 200
    assert client.put(f'/api/decisions/{decision_id}', json={'status': 'accepted'}).status_code == 200
    assert client.get('/api/user/me').status_code == 200
    return decision_id


class TestTheAnalyticsSwitch:

    def test_switched_off_events_are_counted_but_tied_to_no_one(self, api_app, recorded):
        user = make_member()
        switch(user, False)
        client = sign_in(api_app, user)
        recorded.clear()

        use_the_product(client)

        person, organisation = personal_codes(user)
        assert len(recorded) >= 4, 'the events are still sent: totals stay right'
        for event in recorded:
            assert event['distinct_id'] == 'anonymous'
            assert 'tenant_hash' not in event['properties']
            assert event['properties']['$process_person_profile'] is False
            assert event['properties']['user_type'] == 'authenticated'
            dumped = json.dumps(event)
            assert person not in dumped and organisation not in dumped
        assert {'decision_created', 'decision_viewed', 'decisions_listed', 'decision_updated'} <= {
            event['event'] for event in recorded}

    def test_never_switched_on_is_the_same_as_off(self, api_app, recorded):
        user = make_member()
        client = sign_in(api_app, user)
        recorded.clear()

        use_the_product(client)

        person, _ = personal_codes(user)
        assert recorded and all(event['distinct_id'] == 'anonymous' for event in recorded)
        assert person not in json.dumps(recorded)

    def test_switched_on_events_carry_the_persons_code(self, api_app, recorded):
        user = make_member()
        switch(user, True)
        client = sign_in(api_app, user)
        recorded.clear()

        use_the_product(client)

        person, organisation = personal_codes(user)
        assert recorded
        for event in recorded:
            assert event['distinct_id'] == person
            assert event['properties']['tenant_hash'] == organisation
            assert '$process_person_profile' not in event['properties']

    def test_switching_off_takes_effect_on_the_next_request(self, api_app, recorded):
        user = make_member()
        switch(user, True)
        client = sign_in(api_app, user)
        person, _ = personal_codes(user)

        client.get('/api/decisions')
        assert recorded[-1]['distinct_id'] == person

        assert client.post('/api/user/consents', json={'consent_type': 'analytics', 'granted': False}).status_code == 200
        recorded.clear()
        client.get('/api/decisions')

        assert recorded and all(event['distinct_id'] == 'anonymous' for event in recorded)

    def test_one_persons_switch_does_not_change_a_colleagues(self, api_app, recorded):
        off, on = make_member('off', 'Olga', 'Off'), make_member('on', 'Omar', 'On')
        switch(off, False)
        switch(on, True)
        off_client, on_client = sign_in(api_app, off), sign_in(api_app, on)
        recorded.clear()

        off_client.get('/api/decisions')
        on_client.get('/api/decisions')

        assert [event['distinct_id'] for event in recorded] == [
            'anonymous', analytics.generate_distinct_id(on.id, DOMAIN)]

    def test_signed_out_requests_stay_anonymous(self, api_app, recorded):
        api_app.test_client().get('/api/version')
        api_app.test_client().get('/api/auth/csrf-token')

        assert all(event['distinct_id'] == 'anonymous' and event['properties']['user_type'] == 'anonymous'
                   for event in recorded)

    def test_an_error_report_for_a_person_who_switched_off_is_anonymous(self, api_app, recorded):
        user = make_member()
        switch(user, False)
        person, organisation = personal_codes(user)

        with api_app.test_request_context('/api/decisions'):
            from flask import g
            g.current_user = db.session.get(User, user.id)
            try:
                raise RuntimeError('boom')
            except RuntimeError as error:
                analytics.capture_exception(error, endpoint_name='api_decisions_list')

        report = recorded[-1]
        assert report['event'] == '$exception'
        assert report['distinct_id'] == 'anonymous'
        assert 'tenant_hash' not in report['properties']
        assert report['properties']['$process_person_profile'] is False
        assert person not in json.dumps(report) and organisation not in json.dumps(report)

    def test_an_error_report_for_a_person_who_switched_on_carries_their_code(self, api_app, recorded):
        user = make_member()
        switch(user, True)

        with api_app.test_request_context('/api/decisions'):
            from flask import g
            g.current_user = db.session.get(User, user.id)
            try:
                raise RuntimeError('boom')
            except RuntimeError as error:
                analytics.capture_exception(error, endpoint_name='api_decisions_list')

        assert recorded[-1]['distinct_id'] == personal_codes(user)[0]

    def test_a_failure_to_read_the_switch_counts_as_off(self, api_app, recorded, monkeypatch):
        user = make_member()
        switch(user, True)

        def broken(*args, **kwargs):
            raise RuntimeError('database is away')

        monkeypatch.setattr(UserConsent, 'is_granted', classmethod(lambda cls, *a, **k: broken()))
        with api_app.test_request_context('/api/decisions'):
            from flask import g
            g.current_user = db.session.get(User, user.id)
            analytics.track_event('api_decisions_list')

        assert recorded[-1]['distinct_id'] == 'anonymous'


class TestNothingTypedIsSent:

    FORBIDDEN = (TITLE, 'Northwind', BODY, FIRST, LAST, 'zebedee', DOMAIN)

    def test_no_event_carries_a_title_a_text_a_name_or_an_address(self, api_app, recorded):
        user = make_member()
        switch(user, True)
        client = sign_in(api_app, user)

        use_the_product(client)
        client.put('/api/user/profile', json={'first_name': FIRST, 'last_name': LAST})
        client.get(f'/api/auth/user-exists/{user.email}')

        assert len(recorded) >= 6
        dumped = json.dumps(recorded)
        for text in self.FORBIDDEN:
            assert text not in dumped, f'{text!r} was sent to analytics'

    def test_path_is_the_route_not_the_address_requested(self, api_app, recorded):
        user = make_member()
        client = sign_in(api_app, user)
        decision_id = use_the_product(client)
        client.get(f'/api/auth/user-exists/{user.email}?note={LAST}')

        paths = {event['properties']['path'] for event in recorded}

        assert '/api/decisions/<int:decision_id>' in paths
        assert f'/api/decisions/{decision_id}' not in paths
        assert '/api/auth/user-exists/<email>' in paths
        assert not any(user.email in (path or '') or '?' in (path or '') for path in paths)

    def test_events_carry_only_the_known_properties(self, api_app, recorded):
        user = make_member()
        switch(user, True)
        client = sign_in(api_app, user)
        use_the_product(client)

        allowed = {'user_type', 'endpoint', 'path', 'method', 'tenant_hash', 'response_status',
                   '$process_person_profile'}
        for event in recorded:
            assert set(event['properties']) <= allowed, event
            assert event['extra'] == {}

    def test_a_caller_cannot_add_free_text_to_an_event(self, api_app, recorded):
        with api_app.test_request_context('/api/decisions'):
            analytics.track_event('api_decisions_create', {
                'response_status': 201, 'title': TITLE, 'user_name': f'{FIRST} {LAST}', 'email': f'z@{DOMAIN}'})

        properties = recorded[-1]['properties']
        assert properties['response_status'] == 201
        assert 'title' not in properties and 'user_name' not in properties and 'email' not in properties

    def test_an_error_report_has_the_class_and_the_place_but_not_the_message(self, api_app, recorded):
        message = f'duplicate key value: Key (email)=(zebedee@{DOMAIN}) title={TITLE!r}'

        with api_app.test_request_context(f'/api/decisions?search={LAST}'):
            try:
                raise ValueError(message)
            except ValueError as error:
                analytics.capture_exception(error, endpoint_name='api_decisions_list',
                                            extra_properties={'query': TITLE})

        report = recorded[-1]
        dumped = json.dumps(report)
        for text in self.FORBIDDEN + (message,):
            assert text not in dumped
        properties = report['properties']
        assert properties['$exception_type'] == 'ValueError'
        assert properties['$exception_message'].startswith('ValueError at test_analytics_privacy.py:')
        frames = properties['$exception_list'][0]['stacktrace']['frames']
        assert frames and all(' in ' in frame and ':' in frame for frame in frames)
        assert 'query' not in properties

    def test_a_database_error_report_does_not_quote_the_row(self, api_app, recorded):
        make_member()
        with api_app.test_request_context('/api/decisions'):
            try:
                db.session.add(User(email=f'zebedee@{DOMAIN}', sso_domain=DOMAIN, auth_type='local'))
                db.session.commit()
            except Exception as error:
                db.session.rollback()
                assert 'zebedee' in str(error), 'the raw error does quote the row'
                analytics.capture_exception(error, endpoint_name='api_decisions_create')

        report = json.dumps(recorded[-1])
        assert recorded[-1]['properties']['$exception_type'] == 'IntegrityError'
        assert 'zebedee' not in report and DOMAIN not in report

    def test_no_decision_content_in_any_default_event_name(self):
        """Event names are a fixed list of verbs; none is built from data."""
        for endpoint, event in analytics.DEFAULT_EVENT_MAPPINGS.items():
            assert event == event.lower() and ' ' not in event and '{' not in event, endpoint
