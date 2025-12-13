"""
OpenTelemetry Log Forwarding Module

This module provides configurable log forwarding using OpenTelemetry Protocol (OTLP).
Logs can be forwarded to any OTLP-compatible backend (Grafana Loki, Datadog, New Relic, etc.)

Features:
- Configurable OTLP export to any compatible endpoint
- Non-blocking async log forwarding via batch processor
- Thread-safe cached configuration with 5-minute TTL
- Graceful fallback to stdout if OTLP fails
- Multiple authentication methods (API key, Bearer, custom header, none)
"""

import json
import logging
import os
from datetime import datetime
from threading import Lock
from typing import Optional

logger = logging.getLogger(__name__)

# Configuration cache (same pattern as analytics.py)
_config_cache = {
    'enabled': None,
    'endpoint_url': None,
    'auth_type': None,
    'auth_header_name': None,
    'api_key': None,
    'log_level_threshold': None,
    'service_name': None,
    'environment': None,
    'custom_headers': None,
    'last_refresh': None,
    'logger_provider': None,
    'handler': None,
}
_cache_lock = Lock()
CACHE_TTL_SECONDS = 300  # 5 minutes

# Log level mapping
LOG_LEVELS = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
}

# Valid auth types
VALID_AUTH_TYPES = ['api_key', 'bearer', 'header', 'none']


def _get_log_forwarding_config():
    """
    Get log forwarding configuration with caching.
    Uses same pattern as analytics.py for consistency.
    """
    global _config_cache

    with _cache_lock:
        now = datetime.utcnow()

        # Check cache validity
        if _config_cache['last_refresh']:
            age = (now - _config_cache['last_refresh']).total_seconds()
            if age < CACHE_TTL_SECONDS and _config_cache['enabled'] is not None:
                return _config_cache

        # Import here to avoid circular imports
        from models import SystemConfig

        try:
            _config_cache['enabled'] = SystemConfig.get_bool(
                SystemConfig.KEY_LOG_FORWARDING_ENABLED,
                SystemConfig.DEFAULT_LOG_FORWARDING_ENABLED
            )
            _config_cache['endpoint_url'] = SystemConfig.get(
                SystemConfig.KEY_LOG_FORWARDING_ENDPOINT_URL
            )
            _config_cache['auth_type'] = SystemConfig.get(
                SystemConfig.KEY_LOG_FORWARDING_AUTH_TYPE,
                SystemConfig.DEFAULT_LOG_FORWARDING_AUTH_TYPE
            )
            _config_cache['auth_header_name'] = SystemConfig.get(
                SystemConfig.KEY_LOG_FORWARDING_AUTH_HEADER_NAME,
                'Authorization'
            )
            _config_cache['log_level_threshold'] = SystemConfig.get(
                SystemConfig.KEY_LOG_FORWARDING_LOG_LEVEL,
                SystemConfig.DEFAULT_LOG_FORWARDING_LOG_LEVEL
            )
            _config_cache['service_name'] = SystemConfig.get(
                SystemConfig.KEY_LOG_FORWARDING_SERVICE_NAME,
                SystemConfig.DEFAULT_LOG_FORWARDING_SERVICE_NAME
            )
            _config_cache['environment'] = SystemConfig.get(
                SystemConfig.KEY_LOG_FORWARDING_ENVIRONMENT,
                SystemConfig.DEFAULT_LOG_FORWARDING_ENVIRONMENT
            )

            # Parse custom headers (JSON)
            custom_headers_str = SystemConfig.get(
                SystemConfig.KEY_LOG_FORWARDING_CUSTOM_HEADERS,
                '{}'
            )
            try:
                _config_cache['custom_headers'] = json.loads(custom_headers_str) if custom_headers_str else {}
            except json.JSONDecodeError:
                _config_cache['custom_headers'] = {}
                logger.warning("Invalid JSON in log forwarding custom headers, using empty dict")

            _config_cache['last_refresh'] = now

        except Exception as e:
            logger.error(f"Error loading log forwarding config: {e}")
            # Use defaults on error
            _config_cache['enabled'] = False
            _config_cache['last_refresh'] = now

        return _config_cache


def _get_otlp_api_key():
    """
    Get the OTLP API key.
    Priority: Key Vault > SystemConfig > Environment variable
    """
    try:
        from keyvault_client import keyvault_client

        # Try Key Vault first
        api_key = keyvault_client.get_log_forwarding_api_key()
        if api_key:
            return api_key
    except Exception as e:
        logger.debug(f"Key Vault not available for log forwarding API key: {e}")

    # Fall back to SystemConfig
    try:
        from models import SystemConfig
        api_key = SystemConfig.get(SystemConfig.KEY_LOG_FORWARDING_API_KEY)
        if api_key:
            return api_key
    except Exception as e:
        logger.debug(f"SystemConfig not available for log forwarding API key: {e}")

    # Fall back to environment variable
    return os.environ.get('LOG_FORWARDING_API_KEY')


def _build_auth_headers(config):
    """
    Build authentication headers based on auth type.

    Auth types:
    - api_key: Authorization: Api-Key <key>
    - bearer: Authorization: Bearer <key>
    - header: <custom_header_name>: <key>
    - none: No auth headers
    """
    api_key = _get_otlp_api_key()
    auth_type = config.get('auth_type', 'api_key')
    auth_header_name = config.get('auth_header_name', 'Authorization')

    headers = {}

    if auth_type == 'none' or not api_key:
        pass  # No auth headers
    elif auth_type == 'api_key':
        headers['Authorization'] = f'Api-Key {api_key}'
    elif auth_type == 'bearer':
        headers['Authorization'] = f'Bearer {api_key}'
    elif auth_type == 'header':
        headers[auth_header_name] = api_key

    # Add custom headers
    custom_headers = config.get('custom_headers', {})
    if custom_headers and isinstance(custom_headers, dict):
        headers.update(custom_headers)

    return headers


def _init_otel_logger_provider(app):
    """
    Initialize the OpenTelemetry logger provider and attach to Flask app.
    Uses BatchLogRecordProcessor for non-blocking async export.
    """
    global _config_cache

    config = _get_log_forwarding_config()

    if not config['enabled']:
        logger.debug("Log forwarding is disabled")
        return False

    if not config['endpoint_url']:
        logger.warning("Log forwarding enabled but no endpoint URL configured")
        return False

    try:
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
        from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
        from version import __version__

        # Build headers
        headers = _build_auth_headers(config)

        # Create resource with service info
        resource = Resource.create({
            SERVICE_NAME: config['service_name'],
            SERVICE_VERSION: __version__,
            'deployment.environment': config['environment'],
        })

        # Create OTLP exporter
        exporter = OTLPLogExporter(
            endpoint=config['endpoint_url'],
            headers=headers,
        )

        # Create provider with batch processor
        provider = LoggerProvider(resource=resource)
        provider.add_log_record_processor(BatchLogRecordProcessor(exporter))

        # Get log level
        log_level = LOG_LEVELS.get(config['log_level_threshold'], logging.INFO)

        # Create handler
        handler = LoggingHandler(level=log_level, logger_provider=provider)

        # Remove existing OTLP handler if any (for reconfiguration)
        if _config_cache.get('handler'):
            try:
                app.logger.removeHandler(_config_cache['handler'])
            except Exception:
                pass

        # Attach to Flask logger
        app.logger.addHandler(handler)

        # Store references for cleanup
        _config_cache['logger_provider'] = provider
        _config_cache['handler'] = handler

        logger.info(f"Log forwarding initialized: {config['endpoint_url']} (level: {config['log_level_threshold']})")
        return True

    except ImportError as e:
        logger.warning(f"OpenTelemetry packages not installed: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to initialize log forwarding: {e}")
        return False


def setup_log_forwarding(app):
    """
    Set up log forwarding for the Flask application.
    Called during app initialization.
    """
    config = _get_log_forwarding_config()

    if not config['enabled']:
        logger.debug("Log forwarding is disabled, skipping setup")
        return

    _init_otel_logger_provider(app)


def reconfigure(app):
    """
    Reconfigure log forwarding after settings change.
    Call this after updating log forwarding settings.
    """
    shutdown()
    invalidate_cache()
    setup_log_forwarding(app)


def invalidate_cache():
    """Invalidate the configuration cache to force reload."""
    global _config_cache

    with _cache_lock:
        _config_cache['last_refresh'] = None


def get_config_for_api():
    """
    Get configuration safe for API response (no sensitive data).
    """
    config = _get_log_forwarding_config()
    api_key = _get_otlp_api_key()

    return {
        'enabled': config['enabled'],
        'endpoint_url': config['endpoint_url'] or '',
        'auth_type': config['auth_type'],
        'auth_header_name': config['auth_header_name'],
        'has_api_key': bool(api_key),
        'log_level': config['log_level_threshold'],
        'service_name': config['service_name'],
        'environment': config['environment'],
        'custom_headers': json.dumps(config['custom_headers']) if config['custom_headers'] else '{}',
    }


def test_connection():
    """
    Test the OTLP connection by sending a test log.
    Returns (success: bool, message: str)
    """
    config = _get_log_forwarding_config()

    if not config['enabled']:
        return False, "Log forwarding is not enabled"

    if not config['endpoint_url']:
        return False, "No endpoint URL configured"

    try:
        from opentelemetry.sdk._logs import LoggerProvider
        from opentelemetry.sdk._logs.export import SimpleLogRecordProcessor
        from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME
        from opentelemetry._logs import set_logger_provider, get_logger
        from version import __version__

        # Build headers
        headers = _build_auth_headers(config)

        # Create resource
        resource = Resource.create({
            SERVICE_NAME: config['service_name'],
            'deployment.environment': config['environment'],
        })

        # Create exporter with shorter timeout for testing
        exporter = OTLPLogExporter(
            endpoint=config['endpoint_url'],
            headers=headers,
            timeout=10,  # 10 second timeout for test
        )

        # Create provider with SimpleLogRecordProcessor for immediate export
        provider = LoggerProvider(resource=resource)
        provider.add_log_record_processor(SimpleLogRecordProcessor(exporter))

        # Get logger and emit test log
        test_logger = provider.get_logger(__name__)
        test_logger.emit(
            test_logger.create_log_record(
                body="Test log from Architecture Decisions - connection verified",
                severity_text="INFO",
            )
        )

        # Force flush
        provider.force_flush(timeout_millis=5000)

        # Cleanup
        provider.shutdown()

        return True, "Connection successful - test log sent"

    except ImportError as e:
        return False, f"OpenTelemetry packages not installed: {e}"
    except Exception as e:
        return False, f"Connection failed: {str(e)}"


def shutdown():
    """
    Gracefully shutdown the log forwarding provider.
    Flushes any pending logs before shutdown.
    """
    global _config_cache

    with _cache_lock:
        provider = _config_cache.get('logger_provider')
        if provider:
            try:
                provider.force_flush(timeout_millis=5000)
                provider.shutdown()
                logger.info("Log forwarding shut down gracefully")
            except Exception as e:
                logger.error(f"Error shutting down log forwarding: {e}")

            _config_cache['logger_provider'] = None
            _config_cache['handler'] = None


def validate_settings(settings: dict) -> tuple:
    """
    Validate log forwarding settings.
    Returns (is_valid: bool, errors: list)
    """
    errors = []

    # Validate endpoint URL
    endpoint_url = settings.get('endpoint_url', '')
    if settings.get('enabled') and not endpoint_url:
        errors.append("Endpoint URL is required when log forwarding is enabled")
    elif endpoint_url and not (endpoint_url.startswith('http://') or endpoint_url.startswith('https://')):
        errors.append("Endpoint URL must start with http:// or https://")

    # Validate auth type
    auth_type = settings.get('auth_type', 'api_key')
    if auth_type not in VALID_AUTH_TYPES:
        errors.append(f"Invalid auth type. Must be one of: {', '.join(VALID_AUTH_TYPES)}")

    # Validate log level
    log_level = settings.get('log_level', 'INFO')
    if log_level not in LOG_LEVELS:
        errors.append(f"Invalid log level. Must be one of: {', '.join(LOG_LEVELS.keys())}")

    # Validate custom headers JSON
    custom_headers = settings.get('custom_headers', '{}')
    if custom_headers:
        try:
            parsed = json.loads(custom_headers)
            if not isinstance(parsed, dict):
                errors.append("Custom headers must be a JSON object")
        except json.JSONDecodeError:
            errors.append("Custom headers must be valid JSON")

    return len(errors) == 0, errors
