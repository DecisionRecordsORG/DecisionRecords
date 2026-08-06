"""Helpers for loading the real Flask app in isolated test mode."""

from __future__ import annotations

import importlib
import os
import sys
from types import ModuleType


def load_test_app(
    *,
    secret_key: str,
    database_url: str = "sqlite:///:memory:",
) -> tuple[ModuleType, object]:
    """Load or reload the Flask app module with deterministic test settings."""
    os.environ["FLASK_ENV"] = "testing"
    os.environ["TESTING"] = "True"
    os.environ["DATABASE_URL"] = database_url
    os.environ["SECRET_KEY"] = secret_key
    os.environ["FLASK_SECRET_KEY"] = secret_key

    if "app" in sys.modules:
        app_module = importlib.reload(sys.modules["app"])
    else:
        import app as app_module

    test_app = app_module.app
    app_module._db_initialized = False
    test_app.config["TESTING"] = True
    test_app.config["SECRET_KEY"] = secret_key
    test_app.config["SESSION_COOKIE_SAMESITE"] = None
    test_app.config["SESSION_COOKIE_HTTPONLY"] = False
    return app_module, test_app
