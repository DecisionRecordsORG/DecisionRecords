"""Helpers for loading the real Flask app in isolated test mode."""

from __future__ import annotations

import importlib
import os
import sys
from contextlib import contextmanager
from types import ModuleType
from unittest.mock import patch

# app.py looks for this folder when it is imported. With it the app serves the
# built Angular frontend; without it the app registers the legacy template
# routes instead (`index`, `settings`, `profile` and so on).
_BUILD_SUFFIX = os.path.join("frontend", "dist", "frontend", "browser")
_REAL_EXISTS = os.path.exists


def load_test_app(
    *,
    secret_key: str,
    database_url: str = "sqlite:///:memory:",
    built_frontend: str | os.PathLike | None = None,
) -> tuple[ModuleType, object]:
    """Load or reload the Flask app module with deterministic test settings.

    Whether a frontend build happens to exist in the checkout does not change
    what is loaded. By default the app is loaded as if there were no build,
    which is what CI has. Pass `built_frontend` (a folder holding an
    `index.html`) to load it the way production runs it, serving that folder.
    """
    os.environ["FLASK_ENV"] = "testing"
    os.environ["TESTING"] = "True"
    os.environ["DATABASE_URL"] = database_url
    os.environ["SECRET_KEY"] = secret_key
    os.environ["FLASK_SECRET_KEY"] = secret_key

    def exists(path):
        if str(path).endswith(_BUILD_SUFFIX):
            return built_frontend is not None
        return _REAL_EXISTS(path)

    with patch("os.path.exists", exists):
        if "app" in sys.modules:
            app_module = importlib.reload(sys.modules["app"])
        else:
            import app as app_module

    test_app = app_module.app
    if built_frontend is not None:
        app_module.FRONTEND_DIR = str(built_frontend)
        test_app.static_folder = str(built_frontend)
    app_module._db_initialized = False
    test_app.config["TESTING"] = True
    test_app.config["SECRET_KEY"] = secret_key
    test_app.config["SESSION_COOKIE_SAMESITE"] = None
    test_app.config["SESSION_COOKIE_HTTPONLY"] = False
    return app_module, test_app


@contextmanager
def website_handoff_app(
    *,
    secret_key: str,
    cookie_domain: str | None,
    oauth_base_url: str,
    app_base_url: str,
    use_https: bool = True,
):
    """Load the real app configured like production's website-to-app handoff.

    The marketing website and the app are different hosts of one site. OAuth
    callbacks run on the website host (OAUTH_BASE_URL), the session cookie is
    scoped to the parent domain (SESSION_COOKIE_DOMAIN) and the user is then
    redirected to the app host (APP_BASE_URL).

    SESSION_COOKIE_DOMAIN and USE_HTTPS are read when app.py is imported, so
    they are set before the module is (re)loaded. load_test_app() relaxes the
    SameSite and HttpOnly cookie flags for other suites; this restores the
    values app.py configures so the cookie can be asserted as shipped.

    Yields (app_module, flask_app) inside an app context with tables created.
    """
    from models import db

    overrides = {
        "SESSION_COOKIE_DOMAIN": cookie_domain,
        "OAUTH_BASE_URL": oauth_base_url,
        "APP_BASE_URL": app_base_url,
        "USE_HTTPS": "true" if use_https else "false",
    }
    previous = {name: os.environ.get(name) for name in overrides}

    def apply(values):
        for name, value in values.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    apply(overrides)
    test_app = None
    try:
        app_module, test_app = load_test_app(secret_key=secret_key)
        test_app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
        test_app.config["SESSION_COOKIE_HTTPONLY"] = True

        with test_app.app_context():
            db.create_all()
            app_module.init_database()
            try:
                yield app_module, test_app
            finally:
                db.session.remove()
                db.drop_all()
                app_module._db_initialized = False
    finally:
        apply(previous)
        if test_app is not None:
            # The module stays imported: leave it as load_test_app() would.
            test_app.config["SESSION_COOKIE_DOMAIN"] = None
            test_app.config["SESSION_COOKIE_SECURE"] = False
            test_app.config["SESSION_COOKIE_SAMESITE"] = None
            test_app.config["SESSION_COOKIE_HTTPONLY"] = False


def parse_set_cookie(response, name: str = "session") -> dict | None:
    """Return the named Set-Cookie header's attributes (keys lower-cased), or None."""
    for header in response.headers.getlist("Set-Cookie"):
        parts = [part.strip() for part in header.split(";")]
        cookie_name, _, value = parts[0].partition("=")
        if cookie_name != name:
            continue
        attributes: dict = {"value": value}
        for part in parts[1:]:
            key, _, attr_value = part.partition("=")
            attributes[key.lower()] = attr_value if attr_value else True
        return attributes
    return None
