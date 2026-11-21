"""Text-level checks that the PostgreSQL gates and the deploy order stay wired.

A workflow refactor must not be able to silently drop the checks added after
the 2026-11-21 outage: images are started against PostgreSQL before anything is
published, and the Enterprise deploy publishes nothing before its pre-flight.
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO_ROOT / ".github" / "workflows"


def read(*parts: str) -> str:
    return REPO_ROOT.joinpath(*parts).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def ci() -> str:
    return (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def release() -> str:
    return (WORKFLOWS / "release.yml").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def deploy_job() -> str:
    workflow = (WORKFLOWS / "deploy-enterprise.yml").read_text(encoding="utf-8")
    return workflow[workflow.index("\n  deploy:\n"):]


@pytest.fixture(scope="module")
def smoke() -> str:
    return read("scripts", "smoke_test_ce_image.sh")


def step(job: str, name: str) -> str:
    """Return the text of one workflow step, from its name to the next step."""
    start = job.index(f"- name: {name}")
    following = job.find("\n      - ", start + 1)
    return job[start:] if following == -1 else job[start:following]


class TestCommunityImageRunsAgainstPostgres:
    def test_ci_boots_the_image_on_sqlite_and_on_postgres(self, ci):
        sqlite_run = ci.index("- name: Smoke test Community image\n")
        postgres_step = step(ci, "Smoke test Community image against PostgreSQL")

        assert sqlite_run < ci.index("- name: Smoke test Community image against PostgreSQL")
        assert "SMOKE_DATABASE: postgres" in postgres_step
        assert "scripts/smoke_test_ce_image.sh decision-records:community" in postgres_step

    def test_release_boots_on_postgres_before_any_registry_step(self, release):
        postgres_step_at = release.index("- name: Smoke test release candidate image against PostgreSQL")
        postgres_step = step(release, "Smoke test release candidate image against PostgreSQL")

        assert "SMOKE_DATABASE: postgres" in postgres_step
        assert "scripts/smoke_test_ce_image.sh decision-records:release-candidate" in postgres_step
        assert postgres_step_at < release.index("docker/login-action")
        assert postgres_step_at < release.index("push: true")

    def test_release_keeps_the_sqlite_run(self, release):
        sqlite_step = step(release, "Smoke test release candidate image\n")

        assert "SMOKE_DATABASE" not in sqlite_step
        assert "scripts/smoke_test_ce_image.sh decision-records:release-candidate" in sqlite_step


class TestSmokeScriptPostgresMode:
    def test_starts_postgres_and_passes_a_postgresql_url(self, smoke):
        assert 'DATABASE="${SMOKE_DATABASE:-sqlite}"' in smoke
        assert "docker network create" in smoke
        assert "DATABASE_URL=postgresql://${PG_USER}:${PG_PASSWORD}@${PG_CONTAINER}:5432/${PG_DATABASE}" in smoke

    def test_requires_a_connected_database_not_only_liveness(self, smoke):
        assert '"${BASE_URL}/health"' in smoke
        assert '"database": ?"connected"' in smoke
        assert '"status": ?"healthy"' in smoke

    def test_requires_the_schema_to_exist_in_postgres(self, smoke):
        assert "information_schema.tables" in smoke
        assert "schema_migrations" in smoke

    def test_fails_on_start_up_errors_the_app_survives(self, smoke):
        assert '"Database initialization failed"' in smoke
        assert '"Schema migration check failed"' in smoke
        # The markers must be the messages app.py really logs.
        app_source = read("app.py")
        assert "Database initialization failed" in app_source
        assert "Schema migration check failed" in app_source

    def test_enterprise_profile_boots_without_azure_or_cloudflare(self, smoke):
        assert "-e AZURE_KEYVAULT_URL= -e SKIP_CLOUDFLARE_CHECK=true" in smoke

    def test_cleans_up_the_database_container_and_network(self, smoke):
        cleanup = smoke[smoke.index("cleanup() {"):smoke.index("trap cleanup EXIT")]

        assert 'docker rm -f "$PG_CONTAINER"' in cleanup
        assert 'docker network rm "$NETWORK"' in cleanup


class TestBackendTestsRunOnPostgres:
    def test_ci_has_a_postgres_backed_test_job(self, ci):
        job = ci[ci.index("\n  test-backend-postgres:\n"):ci.index("\n  # Frontend Build\n")]

        assert "image: postgres:" in job
        assert "TEST_DATABASE_URL: postgresql://" in job
        assert "/decisions_test" in job
        assert "python -m pytest tests/" in job

    def test_postgres_job_is_part_of_the_quality_gate(self, ci):
        gate = ci[ci.index("\n  quality-gate:\n"):]

        assert "test-backend-postgres" in gate.split("needs:", 1)[1].split("\n", 1)[0]
        assert 'needs.test-backend-postgres.result }}" != "success"' in gate


class TestEnterpriseDeployOrder:
    def test_nothing_is_published_before_the_preflight(self, deploy_job):
        order = [
            deploy_job.index("- name: Build Enterprise image (commit tag only)"),
            deploy_job.index("- name: Pre-flight - import the app with a PostgreSQL URL"),
            deploy_job.index("- name: Pre-flight - boot the image against PostgreSQL"),
            deploy_job.index("uses: azure/login@"),
            deploy_job.index("az acr login"),
            deploy_job.index("scripts/deploy_enterprise_image.sh"),
        ]

        assert order == sorted(order)

    def test_workflow_itself_never_pushes_or_touches_the_vm(self, deploy_job):
        """Publishing and the VM restart live in the deploy script, where the
        rollback is; a stray push in the workflow would bypass both gates."""
        commands = "\n".join(
            line for line in deploy_job.splitlines() if not line.lstrip().startswith(("#", "echo"))
        )

        assert "docker push" not in commands
        assert "az vm run-command" not in commands

    def test_build_does_not_tag_latest(self, deploy_job):
        build = step(deploy_job, "Build Enterprise image (commit tag only)")

        assert ':$GITHUB_SHA"' in build
        assert ":latest" not in build

    def test_import_check_always_runs_with_a_postgresql_url(self, deploy_job):
        check = step(deploy_job, "Pre-flight - import the app with a PostgreSQL URL")

        assert "\n        if:" not in check
        assert "-e DATABASE_URL=postgresql://" in check
        assert "-e AZURE_KEYVAULT_URL= " in check
        assert "import app" in check
        assert "app.db.engine.driver" in check

    def test_boot_preflight_uses_the_enterprise_profile_on_postgres(self, deploy_job):
        boot = step(deploy_job, "Pre-flight - boot the image against PostgreSQL")

        assert "SMOKE_PROFILE: enterprise" in boot
        assert "SMOKE_DATABASE: postgres" in boot
        assert "scripts/smoke_test_ce_image.sh" in boot
        assert "if: ${{ !inputs.skip_postgres_preflight }}" in boot

    def test_bypasses_are_explicit_inputs_that_default_to_off(self):
        workflow = (WORKFLOWS / "deploy-enterprise.yml").read_text(encoding="utf-8")
        inputs = workflow[workflow.index("workflow_dispatch:"):workflow.index("\nconcurrency:")]

        for name in ("skip_postgres_preflight", "deploy_when_unhealthy"):
            block = inputs[inputs.index(f"{name}:"):]
            assert "type: boolean" in block.split("default:", 1)[0]
            assert block.split("default:", 1)[1].split("\n", 1)[0].strip() == "false"

    def test_deploy_is_verified_on_the_database_health_route(self, deploy_job):
        line = next(line for line in deploy_job.splitlines() if line.strip().startswith("DB_HEALTH_URL:"))

        assert "/health'" in line
        assert "/api/health" not in line

    def test_deploy_script_is_executable(self):
        import os

        assert os.access(REPO_ROOT / "scripts" / "deploy_enterprise_image.sh", os.X_OK)
        assert os.access(REPO_ROOT / "scripts" / "smoke_test_ce_image.sh", os.X_OK)
