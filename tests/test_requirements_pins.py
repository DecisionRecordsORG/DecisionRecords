"""Runtime dependencies must be exact pins.

``requirements.txt`` used to pin Flask-SQLAlchemy but not SQLAlchemy, which it
installs. A fresh image build months later resolved a new SQLAlchemy release
line with a different PostgreSQL driver and production could not start. The
file is now a complete, exact list; these tests keep it that way.
"""

import os
import re
from importlib import metadata
from pathlib import Path

import pytest
from packaging.requirements import Requirement

REPO_ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = REPO_ROOT / "requirements.txt"
PIN = re.compile(r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)==(?P<version>[A-Za-z0-9][A-Za-z0-9.!+_-]*)$")

# Imported by the application or run as its server; a missing line here means
# the package would be installed at whatever version is newest on build day.
REQUIRED_PINS = (
    "flask", "flask-sqlalchemy", "flask-limiter", "flask-talisman", "flask-cors",
    "werkzeug", "jinja2", "markupsafe", "itsdangerous", "click", "blinker",
    "sqlalchemy", "psycopg2-binary", "psycopg", "greenlet", "gunicorn",
    "authlib", "webauthn", "cbor2", "cryptography", "pyopenssl", "cffi",
    "requests", "urllib3", "certifi", "idna", "charset-normalizer",
    "bleach", "limits", "free-email-domains", "disposable-email-domains",
)


def require_pinned_environment(problems, description: str) -> None:
    """Fail in CI, where the environment is a fresh install of requirements.txt.

    A developer virtualenv created before a pin moved is merely stale, so
    locally the same finding is reported as a skip that says how to fix it.
    """
    if not problems:
        return
    message = f"{description}: {problems}"
    if os.environ.get("CI"):
        pytest.fail(message)
    pytest.skip(f"{message}. Run `pip install -r requirements.txt` to match the pinned set.")


def normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def requirement_lines(text: str) -> list[str]:
    lines = []
    for raw in text.splitlines():
        line = raw.split(" #", 1)[0].strip()
        if line and not line.startswith("#"):
            lines.append(line)
    return lines


def parse_pins(text: str) -> dict[str, str]:
    pins = {}
    for line in requirement_lines(text):
        match = PIN.match(line)
        assert match, f"requirements.txt line is not an exact pin (name==version): {line!r}"
        name = normalise(match["name"])
        assert name not in pins, f"{name} is pinned twice in requirements.txt"
        pins[name] = match["version"]
    return pins


@pytest.fixture(scope="module")
def pins() -> dict[str, str]:
    return parse_pins(REQUIREMENTS.read_text(encoding="utf-8"))


class TestPinParsing:
    @pytest.mark.parametrize("line", [
        "SQLAlchemy>=2.0",
        "cryptography>=41.0.0",
        "SQLAlchemy~=2.0.52",
        "SQLAlchemy",
        "SQLAlchemy==2.0.*",
        "-r other.txt",
        "https://example.test/packages/pkg-1.0.tar.gz",
    ])
    def test_rejects_anything_but_an_exact_pin(self, line):
        with pytest.raises(AssertionError, match="not an exact pin"):
            parse_pins(f"Flask==3.0.0\n{line}\n")

    def test_rejects_duplicate_pins(self):
        with pytest.raises(AssertionError, match="pinned twice"):
            parse_pins("typing_extensions==4.16.0\ntyping-extensions==4.15.0\n")

    def test_ignores_comments_and_blank_lines(self):
        text = "# heading\n\nFlask==3.0.0  # web framework\n"

        assert parse_pins(text) == {"flask": "3.0.0"}


class TestRequirementsFile:
    def test_every_line_is_an_exact_pin(self, pins):
        assert len(pins) >= len(REQUIRED_PINS)

    @pytest.mark.parametrize("name", REQUIRED_PINS)
    def test_runtime_package_is_pinned(self, pins, name):
        assert name in pins, f"{name} must have an exact pin in requirements.txt"

    def test_sqlalchemy_stays_on_the_2_0_line(self, pins):
        """SQLAlchemy 2.1 selects psycopg (v3) for postgresql:// URLs. Moving
        to it is a driver migration, not a routine version bump."""
        assert pins["sqlalchemy"].startswith("2.0.")

    def test_installed_packages_match_the_pins(self, pins):
        """The environment the tests run in is the pinned set, so a green test
        run says something about the versions the image will contain."""
        mismatched = {}
        for name, version in pins.items():
            try:
                installed = metadata.version(name)
            except metadata.PackageNotFoundError:
                continue
            if installed != version:
                mismatched[name] = f"installed {installed}, pinned {version}"

        require_pinned_environment(mismatched, "installed versions differ from requirements.txt")

    def test_installed_dependencies_of_pinned_packages_are_pinned(self, pins):
        """A package pulled in by a pinned package, but missing from the file,
        is exactly how SQLAlchemy went unpinned."""
        missing = set()
        for name in pins:
            try:
                requires = metadata.requires(name) or []
            except metadata.PackageNotFoundError:
                continue
            for requirement in requires:
                parsed = Requirement(requirement)
                if parsed.marker is not None and not parsed.marker.evaluate({"extra": ""}):
                    continue  # an optional extra, or another platform or interpreter
                dependency = normalise(parsed.name)
                try:
                    metadata.version(dependency)
                except metadata.PackageNotFoundError:
                    continue
                if dependency not in pins:
                    missing.add(f"{dependency} (required by {name})")

        require_pinned_environment(sorted(missing), "installed dependencies without a pin in requirements.txt")


class TestImagesInstallOnlyPinnedPackages:
    def test_community_dockerfile_installs_nothing_outside_requirements(self):
        dockerfile = (REPO_ROOT / "Dockerfile.community").read_text(encoding="utf-8")
        installs = [
            line.strip() for line in dockerfile.splitlines()
            if "pip install" in line and not line.lstrip().startswith("#")
        ]

        assert installs == ["RUN pip install --no-cache-dir -r requirements.txt"]

    def test_gunicorn_is_pinned_for_the_image_command(self, pins):
        dockerfile = (REPO_ROOT / "Dockerfile.community").read_text(encoding="utf-8")

        assert 'CMD ["gunicorn"' in dockerfile
        assert "gunicorn" in pins
