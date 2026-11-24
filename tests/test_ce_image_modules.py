"""Tests for the Community image module guard.

v2.1.0 was published with ``decision_relationships.py`` missing from the image:
``models.py`` imported it, ``Dockerfile.community`` did not copy it, and pytest
could not notice because it runs from the repository root. These tests pin the
static guard that catches that class of failure, and the workflow wiring that
boots the real image before anything is published.
"""

from pathlib import Path

import pytest

import scripts.check_ce_image_modules as image_check


REPO_ROOT = Path(__file__).resolve().parents[1]

# The runtime stage of Dockerfile.community exactly as tagged for v2.1.0.
V2_1_0_DOCKERFILE = """\
FROM node:22-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build -- --configuration=community

FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Core application
COPY app.py models.py version.py feature_flags.py migrations.py ./

# Core modules (these do NOT import from ee/)
COPY auth.py governance.py notifications.py security.py webauthn_auth.py crypto.py ./

COPY templates/ ./templates/
COPY static/ ./static/
COPY --from=frontend-builder /app/frontend/dist/frontend/browser ./frontend/dist/frontend/browser
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]
"""

# The root .dockerignore that applied to the v2.1.0 build.
V2_1_0_DOCKERIGNORE = """\
.git
.gitignore
__pycache__
*.py[cod]
venv/
.pytest_cache/
*.db
Dockerfile
docker-compose.yml
.dockerignore
"""


def write_repo(root: Path, files: dict[str, str]) -> Path:
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


class TestRealRepository:
    def test_current_dockerfile_ships_every_imported_module(self):
        assert image_check.find_errors() == []

    def test_entry_module_closure_includes_known_core_modules(self):
        closure = image_check.first_party_import_closure(REPO_ROOT)

        assert {"app", "models", "decision_relationships", "decision_templates", "crypto", "migrations"} <= set(closure)
        assert closure["decision_relationships"] == "models.py"
        assert "ee" not in closure

    def test_v2_1_0_dockerfile_is_rejected_for_missing_decision_relationships(self):
        """Regression: the guard would have blocked the broken v2.1.0 image."""
        errors = image_check.find_errors(
            dockerfile_text=V2_1_0_DOCKERFILE,
            dockerignore_text=V2_1_0_DOCKERIGNORE,
        )

        # That Dockerfile listed root modules by hand, so it also lacks every
        # module added since (retention.py, data_export.py, decision_templates.py).
        # Each one is reported the same way.
        assert sorted(error.split(" ", 1)[0] for error in errors) == [
            "data_export.py", "decision_relationships.py", "decision_templates.py", "retention.py"]
        relationships_error = next(e for e in errors if e.startswith("decision_relationships.py"))
        assert relationships_error.startswith(
            "decision_relationships.py is imported by models.py but Dockerfile.community does not ship it."
        )
        assert all("ModuleNotFoundError" in error for error in errors)

    def test_glob_copy_without_context_allowlist_would_ship_local_runner(self):
        """The Dockerfile-specific ignore file is what keeps run_local.py out."""
        dockerfile_text = (REPO_ROOT / "Dockerfile.community").read_text(encoding="utf-8")

        errors = image_check.find_errors(
            dockerfile_text=dockerfile_text,
            dockerignore_text=V2_1_0_DOCKERIGNORE,
        )

        assert any(error.startswith("run_local.py would be copied") for error in errors)

    def test_forbidden_paths_are_not_shipped(self):
        manifest = image_check.ImageManifest(
            (REPO_ROOT / "Dockerfile.community").read_text(encoding="utf-8"),
            image_check.read_dockerignore(REPO_ROOT),
        )

        for probe in image_check.FORBIDDEN_IMAGE_PROBES:
            assert manifest.image_path(probe) is None, probe
        assert manifest.image_path("templates/base.html") == "/app/templates/base.html"
        assert manifest.image_path("static/css/app.css") == "/app/static/css/app.css"
        assert manifest.image_path("requirements.txt") == "/app/requirements.txt"


class TestImportClosure:
    def test_follows_transitive_lazy_and_dynamic_imports(self, tmp_path):
        repo = write_repo(
            tmp_path,
            {
                "app.py": "import flask\nfrom models import db\n\ndef view():\n    from lazy_helper import run\n",
                "models.py": "import os\nfrom relationships import catalog\n",
                "relationships.py": "import importlib\nplugin = importlib.import_module('dynamic_mod')\n",
                "lazy_helper.py": "try:\n    from ee.backend import thing\nexcept ImportError:\n    thing = None\n",
                "dynamic_mod.py": "",
                "unused.py": "",
                "ee/__init__.py": "",
            },
        )

        closure = image_check.first_party_import_closure(repo)

        assert closure == {
            "app": "image entrypoint",
            "models": "app.py",
            "lazy_helper": "app.py",
            "relationships": "models.py",
            "dynamic_mod": "relationships.py",
        }

    def test_package_imports_are_followed(self, tmp_path):
        repo = write_repo(
            tmp_path,
            {
                "app.py": "from services import mailer\n",
                "services/__init__.py": "",
                "services/mailer.py": "import smtp_config\n",
                "smtp_config.py": "",
            },
        )

        closure = image_check.first_party_import_closure(repo)

        assert closure["services"] == "app.py"
        assert closure["smtp_config"] == "services/mailer.py"

    def test_missing_entry_module_is_an_error(self, tmp_path):
        with pytest.raises(image_check.ImageCheckError):
            image_check.first_party_import_closure(tmp_path)


class TestFindErrors:
    def test_reports_module_missing_from_explicit_copy_list(self, tmp_path):
        repo = write_repo(
            tmp_path,
            {"app.py": "import models\n", "models.py": "import helper\n", "helper.py": ""},
        )
        dockerfile = "FROM python:3.11-slim\nWORKDIR /app\nCOPY app.py models.py ./\n"

        errors = image_check.find_errors(repo, dockerfile_text=dockerfile, dockerignore_text="")

        assert errors == [
            "helper.py is imported by models.py but Dockerfile.community does not ship it. "
            "The image would fail at startup with ModuleNotFoundError."
        ]

    def test_reports_module_excluded_by_dockerignore(self, tmp_path):
        repo = write_repo(tmp_path, {"app.py": "import helper\n", "helper.py": ""})
        dockerfile = "FROM python:3.11-slim\nWORKDIR /app\nCOPY *.py ./\n"

        dockerignore = "*\n!app.py\n"

        errors = image_check.find_errors(repo, dockerfile_text=dockerfile, dockerignore_text=dockerignore)

        assert len(errors) == 1
        assert errors[0].startswith("helper.py is imported by app.py")

    def test_reports_module_copied_outside_the_import_path(self, tmp_path):
        repo = write_repo(tmp_path, {"app.py": "import helper\n", "helper.py": ""})
        dockerfile = "FROM python:3.11-slim\nWORKDIR /app\nCOPY app.py ./\nCOPY helper.py ./lib/\n"

        errors = image_check.find_errors(repo, dockerfile_text=dockerfile, dockerignore_text="")

        assert errors == [
            "helper.py is imported by app.py but Dockerfile.community copies it to "
            "/app/lib/helper.py instead of /app/helper.py, where Python cannot import it."
        ]

    def test_copy_everything_ships_private_and_local_files(self, tmp_path):
        repo = write_repo(tmp_path, {"app.py": ""})
        dockerfile = "FROM python:3.11-slim\nWORKDIR /app\nCOPY . .\n"

        errors = image_check.find_errors(repo, dockerfile_text=dockerfile, dockerignore_text="")

        shipped = {error.split(" would be copied")[0] for error in errors}
        assert {"run_local.py", ".env", "ee/backend/__init__.py", "tests/test_auth.py", "test.db"} <= shipped

    def test_only_final_stage_context_copies_count(self, tmp_path):
        repo = write_repo(tmp_path, {"app.py": "import helper\n", "helper.py": ""})
        dockerfile = (
            "FROM python:3.11-slim AS builder\nWORKDIR /src\nCOPY helper.py ./\n"
            "FROM python:3.11-slim\nWORKDIR /app\nCOPY app.py ./\n"
            "COPY --from=builder /src/helper.py ./helper.py\n"
        )

        errors = image_check.find_errors(repo, dockerfile_text=dockerfile, dockerignore_text="")

        assert len(errors) == 1
        assert errors[0].startswith("helper.py is imported by app.py")

    def test_json_form_copy_is_refused_rather_than_guessed(self, tmp_path):
        repo = write_repo(tmp_path, {"app.py": ""})
        dockerfile = 'FROM python:3.11-slim\nWORKDIR /app\nCOPY ["app.py", "./"]\n'

        with pytest.raises(image_check.ImageCheckError):
            image_check.find_errors(repo, dockerfile_text=dockerfile, dockerignore_text="")


class TestDockerIgnore:
    def test_allowlist_semantics_last_match_wins(self):
        ignore = image_check.DockerIgnore(
            "*\n!*.py\nrun_local.py\n!templates\n!frontend\nfrontend/node_modules\n**/*.db\n"
        )

        assert not ignore.is_ignored("app.py")
        assert ignore.is_ignored("run_local.py")
        assert ignore.is_ignored("README.md")
        assert ignore.is_ignored("tests/test_auth.py")  # root glob does not recurse
        assert ignore.is_ignored("ee/backend/__init__.py")
        assert not ignore.is_ignored("templates/base.html")
        assert not ignore.is_ignored("frontend/src/main.ts")
        assert ignore.is_ignored("frontend/node_modules/pkg/index.js")
        assert ignore.is_ignored("templates/cache.db")

    def test_comments_and_blank_lines_are_skipped(self):
        ignore = image_check.DockerIgnore("# comment\n\n*.db\n")

        assert ignore.is_ignored("local.db")
        assert not ignore.is_ignored("app.py")

    def test_dockerfile_specific_ignore_file_takes_precedence(self, tmp_path):
        write_repo(tmp_path, {".dockerignore": "root\n", "Dockerfile.community.dockerignore": "specific\n"})

        assert image_check.read_dockerignore(tmp_path) == "specific\n"


class TestWorkflowWiring:
    """Text-level checks so a refactor cannot silently drop the gates."""

    def test_ci_runs_static_guard_and_boots_the_image(self):
        ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

        assert "python scripts/check_ce_image_modules.py" in ci
        assert "load: true" in ci
        assert "scripts/smoke_test_ce_image.sh decision-records:community" in ci

    def test_release_boots_the_image_before_any_registry_step(self):
        release = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

        assert "python scripts/check_ce_image_modules.py" in release
        smoke = release.index("scripts/smoke_test_ce_image.sh")
        assert smoke < release.index("docker/login-action")
        assert smoke < release.index("push: true")
        # The only build before the smoke test must not push.
        assert "push: true" not in release[:smoke]

    def test_smoke_script_probes_the_dockerfile_healthcheck_route(self):
        dockerfile = (REPO_ROOT / "Dockerfile.community").read_text(encoding="utf-8")
        smoke = (REPO_ROOT / "scripts" / "smoke_test_ce_image.sh").read_text(encoding="utf-8")

        assert "http://localhost:8000/api/health" in dockerfile
        assert "/api/health" in smoke
        assert "docker logs" in smoke

    def test_commit_qa_runs_the_static_guard(self):
        qa = (REPO_ROOT / "scripts" / "qa_check.py").read_text(encoding="utf-8")

        assert "scripts/check_ce_image_modules.py" in qa
        assert "check_ce_image_modules()" in qa
