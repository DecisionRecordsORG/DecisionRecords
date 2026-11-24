"""
The PostHog client must start with the library version we install.

In November 2026 an unpinned `posthog` moved to a release that removed an
argument we passed. The client raised at start-up, the error was only logged,
and analytics recorded nothing in production for three days. These tests build
the real client, so an incompatible library version fails CI.
"""
import pytest

try:
    from ee.backend.analytics import analytics
    EE_AVAILABLE = True
except ImportError:
    EE_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not EE_AVAILABLE,
    reason="Enterprise Edition modules not available"
)


@pytest.fixture
def analytics_cache():
    """Give the test a private copy of the analytics cache and restore it."""
    saved = dict(analytics._config_cache)
    analytics._config_cache['api_key'] = 'phc_test_key_not_real'
    analytics._config_cache['host'] = 'https://eu.i.posthog.com'
    analytics._config_cache['posthog_client'] = None
    yield analytics._config_cache
    client = analytics._config_cache.get('posthog_client')
    if client is not None:
        try:
            client.shutdown()
        except Exception:
            pass
    analytics._config_cache.clear()
    analytics._config_cache.update(saved)


class TestPosthogClientStarts:
    def test_client_is_created_with_installed_library(self, analytics_cache):
        """The client is built with the arguments the app passes."""
        analytics._init_posthog_client()

        assert analytics_cache['posthog_client'] is not None

    def test_start_up_logs_no_error(self, analytics_cache, caplog):
        """A failed start is only logged, so the log is what we check."""
        with caplog.at_level('ERROR', logger=analytics.logger.name):
            analytics._init_posthog_client()

        assert 'Failed to initialize PostHog' not in caplog.text

    def test_capture_accepts_the_arguments_the_app_uses(self, analytics_cache):
        """capture() is called with distinct_id, event and properties."""
        analytics._init_posthog_client()
        client = analytics_cache['posthog_client']
        client.send = False  # queue only; nothing leaves the machine

        client.capture(
            distinct_id='test-distinct-id',
            event='test_event',
            properties={'endpoint': 'api_test'},
        )

    def test_failed_start_leaves_client_unset(self, analytics_cache, monkeypatch):
        """If the library rejects our arguments, analytics is off, not broken."""
        import posthog

        def boom(*args, **kwargs):
            raise TypeError("unexpected keyword argument")

        monkeypatch.setattr(posthog, 'Posthog', boom)
        analytics._init_posthog_client()

        assert analytics_cache['posthog_client'] is None


class TestEnterpriseRequirementsArePinned:
    def test_every_enterprise_requirement_is_an_exact_pin(self):
        """A range lets a new upstream release reach production untested."""
        from pathlib import Path
        from tests.test_requirements_pins import parse_pins

        path = Path(__file__).resolve().parent.parent / 'ee' / 'requirements.txt'
        pins = parse_pins(path.read_text(encoding='utf-8'))

        assert 'posthog' in pins
