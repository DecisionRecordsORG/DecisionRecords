"""
The automatic retention run: claiming a day's run in the database, the
once-a-day rule, interrupted runs and the per-worker thread.

Claims are tested with real concurrent connections: PostgreSQL when
TEST_DATABASE_URL is set (CI), otherwise a SQLite file. The in-memory SQLite
database the other tests use has a single shared connection, which cannot
show a race.
"""

import threading
import time
from datetime import timedelta

import pytest
from flask import Flask

import retention
from models import db, LoginHistory, RetentionRun, RetentionErasure, SystemConfig
from tests.conftest import fixture_database_url
from tests.retention_test_data import naive_now

WORKERS = 8


@pytest.fixture(autouse=True)
def utc_database_session(request, monkeypatch):
    """Run as on a database session set to UTC (what CI and the images use).

    A PostgreSQL session in another zone makes retention wait some hours past
    every due date (retention.safety_margin), which the to-the-second tests
    below would trip over. Tests that ask for `real_session_offset` get the
    real behaviour.
    """
    if 'real_session_offset' not in request.fixturenames:
        monkeypatch.setattr(retention, '_session_utc_offset_seconds', lambda: 0)


@pytest.fixture
def concurrent_app(tmp_path):
    url = fixture_database_url()
    if url.startswith('sqlite'):
        url = f"sqlite:///{tmp_path / 'retention.db'}"
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'test-secret-key'
    db.init_app(app)
    with app.app_context():
        db.create_all()
        yield app
        retention.stop_scheduler()
        db.session.remove()
        db.drop_all()


def in_parallel(app, work):
    """Run `work` in WORKERS threads at the same moment, each with its own session."""
    barrier = threading.Barrier(WORKERS)
    results, failures = [], []

    def target():
        with app.app_context():
            try:
                barrier.wait(timeout=10)
                results.append(work())
            except Exception as exc:  # pragma: no cover - reported by the assertion below
                failures.append(exc)
            finally:
                db.session.remove()

    threads = [threading.Thread(target=target) for _ in range(WORKERS)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert failures == []
    assert len(results) == WORKERS
    return results


def add_old_logins(count=3):
    db.session.add_all([
        LoginHistory(email=f'old{i}@example.com', login_method='password', success=True,
                     created_at=naive_now() - timedelta(days=120))
        for i in range(count)
    ])
    db.session.commit()


# ==================== Claiming ====================

def test_a_day_can_be_claimed_once(concurrent_app):
    now = naive_now()
    first = retention.claim_automatic_run(now)
    assert first is not None and first.claim_key == f'auto:{now.date().isoformat()}'
    assert first.trigger == 'automatic' and first.status == 'running'

    assert retention.claim_automatic_run(now) is None
    assert retention.claim_automatic_run(now + timedelta(minutes=1)) is None or now.date() != (
        now + timedelta(minutes=1)).date()

    tomorrow = retention.claim_automatic_run(now + timedelta(days=1))
    assert tomorrow is not None and tomorrow.id != first.id
    assert RetentionRun.query.count() == 2


def test_concurrent_claims_give_the_day_to_exactly_one_worker(concurrent_app):
    now = naive_now()

    def claim():
        run = retention.claim_automatic_run(now)
        return run.id if run is not None else None

    results = in_parallel(concurrent_app, claim)

    winners = [result for result in results if result is not None]
    assert len(winners) == 1
    assert RetentionRun.query.count() == 1
    assert RetentionRun.query.one().id == winners[0]


def test_concurrent_workers_run_the_days_work_exactly_once(concurrent_app):
    add_old_logins(3)
    now = naive_now()

    results = in_parallel(concurrent_app, lambda: retention.run_automatic_if_due(now))

    ran = [result for result in results if result is not None]
    assert len(ran) == 1
    assert ran[0]['results']['login_history']['affected'] == 3
    assert RetentionRun.query.count() == 1
    assert RetentionErasure.query.count() == 1
    assert LoginHistory.query.count() == 0


# ==================== Once a day ====================

def test_runs_once_a_day_and_again_the_next_day(concurrent_app):
    now = naive_now()
    first = retention.run_automatic_if_due(now)
    assert first['trigger'] == 'automatic' and first['status'] == 'completed'
    assert RetentionRun.query.one().claim_key == retention.automatic_claim_key(now)

    assert retention.run_automatic_if_due(now) is None
    assert retention.run_automatic_if_due(now.replace(hour=23, minute=59)) is None
    assert RetentionRun.query.count() == 1

    assert retention.run_automatic_if_due(now + timedelta(days=1)) is not None
    assert RetentionRun.query.count() == 2


def test_turned_off_in_settings_does_nothing(concurrent_app):
    add_old_logins(1)
    retention.save_settings({'auto_run_enabled': False})

    assert retention.run_automatic_if_due() is None

    assert RetentionRun.query.count() == 0 and LoginHistory.query.count() == 1
    retention.save_settings({'auto_run_enabled': True})
    assert retention.run_automatic_if_due() is not None


def test_turned_off_by_environment_does_nothing(concurrent_app, monkeypatch):
    add_old_logins(1)
    monkeypatch.setenv('RETENTION_AUTO_RUN', 'false')

    assert retention.run_automatic_if_due() is None
    assert RetentionRun.query.count() == 0 and LoginHistory.query.count() == 1


def test_the_automatic_run_obeys_the_limits(concurrent_app):
    from tests.retention_test_data import make_user
    SystemConfig.set(SystemConfig.KEY_RETENTION_LIMIT_ACCOUNTS, 1)
    for name in ('a', 'b'):
        make_user('team.example', name).deletion_scheduled_at = naive_now() - timedelta(hours=1)
    db.session.commit()

    run = retention.run_automatic_if_due()

    assert run['status'] == 'held_back'
    assert run['results']['accounts'] == {
        'status': 'held_back', 'affected': 0, 'waiting': 2, 'limit': 1, 'hold_reason': 'over_limit', 'errors': []}


# ==================== Interrupted runs ====================

def test_a_run_that_crashed_yesterday_is_marked_interrupted_and_does_not_block_today(concurrent_app):
    now = naive_now()
    yesterday = now - timedelta(days=1)
    crashed = RetentionRun(claim_key=retention.automatic_claim_key(yesterday), trigger='automatic',
                           status='running', started_at=yesterday)
    db.session.add(crashed)
    db.session.commit()
    crashed_id = crashed.id
    add_old_logins(2)

    run = retention.run_automatic_if_due(now)

    assert run is not None and run['results']['login_history']['affected'] == 2
    stale = db.session.get(RetentionRun, crashed_id)
    assert stale.status == 'interrupted' and stale.finished_at is not None and stale.error


def test_a_run_that_crashed_today_is_not_repeated_today_but_tomorrow_runs(concurrent_app):
    now = naive_now().replace(hour=12, minute=0)
    crashed = RetentionRun(claim_key=retention.automatic_claim_key(now), trigger='automatic',
                           status='running', started_at=now - timedelta(hours=7))
    db.session.add(crashed)
    db.session.commit()
    add_old_logins(1)

    assert retention.run_automatic_if_due(now) is None
    assert db.session.get(RetentionRun, crashed.id).status == 'interrupted'

    tomorrow = retention.run_automatic_if_due(now + timedelta(days=1))
    assert tomorrow is not None and tomorrow['results']['login_history']['affected'] == 1


def test_waits_while_another_run_is_going_without_using_up_the_day(concurrent_app):
    now = naive_now()
    manual = RetentionRun(trigger='super_admin', status='running', started_at=now - timedelta(minutes=2))
    db.session.add(manual)
    db.session.commit()

    assert retention.run_automatic_if_due(now) is None
    assert RetentionRun.query.count() == 1
    assert retention.run_in_progress(now).id == manual.id

    manual.status = 'completed'
    db.session.commit()
    assert retention.run_automatic_if_due(now) is not None


def test_a_recent_running_run_is_not_marked_interrupted(concurrent_app):
    now = naive_now()
    db.session.add(RetentionRun(trigger='automatic', status='running', started_at=now - timedelta(hours=5)))
    db.session.commit()
    assert retention.mark_interrupted_runs(now) == 0
    assert retention.mark_interrupted_runs(now + timedelta(hours=2)) == 1


# ==================== The thread ====================

def wait_for(condition, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.05)
    return False


def test_thread_is_not_started_under_tests(concurrent_app):
    assert retention.ensure_scheduler(concurrent_app) is None
    assert retention._scheduler_thread is None


def test_thread_is_not_started_when_the_environment_turns_it_off(concurrent_app, monkeypatch):
    concurrent_app.config['TESTING'] = False
    monkeypatch.delenv('FLASK_ENV', raising=False)
    monkeypatch.delenv('TESTING', raising=False)
    monkeypatch.setenv('RETENTION_AUTO_RUN', 'off')
    assert retention.ensure_scheduler(concurrent_app) is None


def test_thread_does_the_days_run_once_and_keeps_checking(concurrent_app):
    add_old_logins(2)
    db.session.remove()

    thread = retention.ensure_scheduler(concurrent_app, force=True, interval=0.05, first_delay=0)
    try:
        assert thread is not None and thread.daemon and thread.is_alive()
        assert retention.ensure_scheduler(concurrent_app, force=True) is thread

        def finished():
            db.session.rollback()
            run = RetentionRun.query.first()
            return run is not None and run.status == 'completed'

        assert wait_for(finished)
        time.sleep(0.5)  # many more checks happen; none may run again
        db.session.rollback()
        assert RetentionRun.query.count() == 1
        assert RetentionRun.query.one().results['login_history']['affected'] == 2
        assert LoginHistory.query.count() == 0
        assert thread.is_alive()
    finally:
        retention.stop_scheduler()
    assert not thread.is_alive()
    assert retention._scheduler_thread is None


def test_thread_survives_a_failing_check(concurrent_app, monkeypatch):
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError('database not reachable')

    monkeypatch.setattr(retention, 'run_automatic_if_due', flaky)
    thread = retention.ensure_scheduler(concurrent_app, force=True, interval=0.02, first_delay=0)
    try:
        assert wait_for(lambda: len(calls) >= 3)
        assert thread.is_alive()
    finally:
        retention.stop_scheduler()


def test_a_new_process_starts_its_own_thread(concurrent_app, monkeypatch):
    monkeypatch.setattr(retention, 'run_automatic_if_due', lambda: None)
    first = retention.ensure_scheduler(concurrent_app, force=True, interval=60, first_delay=60)
    try:
        # A forked worker inherits the module state but not the thread
        monkeypatch.setattr(retention.os, 'getpid', lambda: -1)
        second = retention.ensure_scheduler(concurrent_app, force=True, interval=60, first_delay=60)
        assert second is not first and second.is_alive()
    finally:
        retention.stop_scheduler()
        first.join(0)
