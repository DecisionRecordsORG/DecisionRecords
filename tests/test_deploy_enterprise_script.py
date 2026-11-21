"""Failure paths of scripts/deploy_enterprise_image.sh.

The Enterprise deploy cannot be run outside production, so the script that
publishes the image, restarts the VM and rolls back is exercised here against
stand-ins for ``docker``, ``az`` and ``curl``. Each stand-in records its calls
and plays back a scripted sequence of results.

What these tests prove is the control flow: what is called, in which order, and
what the script reports. They do not prove the real commands behave as the
stand-ins do.
"""

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "deploy_enterprise_image.sh"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash is not available")

REPO = "registry.example.test/decision-records"
TAG = "0123456789abcdef0123456789abcdef01234567"
NEW = f"{REPO}:{TAG}"
LATEST = f"{REPO}:latest"
PREVIOUS_DIGEST = f"{REPO}@sha256:{'a' * 64}"
PREVIOUS_LOCAL = f"deploy-rollback/previous:{TAG}"
HEALTH_URL = "https://app.example.test/health"

DOCKER_STUB = r"""#!/usr/bin/env bash
echo "docker $*" >> "$STUB_STATE/calls.log"
count() {  # count <name>: increment and print a per-name call counter
  local file="$STUB_STATE/count.$1" n=0
  [ -f "$file" ] && n="$(cat "$file")"
  n=$((n + 1)); echo "$n" > "$file"; echo "$n"
}
case "$1" in
  image)
    ref="${@: -1}"
    if [ "$3" = "--format" ]; then
      case "$ref" in
        *:latest) [ -n "${STUB_NO_DIGEST:-}" ] || echo "$STUB_REPO@sha256:$(printf 'a%.0s' $(seq 1 64))" ;;
        *) echo "$STUB_REPO@sha256:$(printf 'b%.0s' $(seq 1 64))" ;;
      esac
      exit 0
    fi
    [ -z "${STUB_NEW_IMAGE_MISSING:-}" ] || exit 1
    exit 0 ;;
  pull) [ -z "${STUB_PULL_FAILS:-}" ] || { echo "pull access denied" >&2; exit 1; } ;;
  tag) exit 0 ;;
  push)
    case "$2" in *:latest) name=latest ;; *) name=commit ;; esac
    n="$(count "push.$name")"
    case " ${STUB_FAIL_PUSH:-} " in *" $name#$n "*) echo "push failed" >&2; exit 1 ;; esac
    exit 0 ;;
esac
"""

AZ_STUB = r"""#!/usr/bin/env bash
echo "az $*" >> "$STUB_STATE/calls.log"
file="$STUB_STATE/count.az"; n=0
[ -f "$file" ] && n="$(cat "$file")"
n=$((n + 1)); echo "$n" > "$file"
read -r -a results <<< "${STUB_AZ:-ok}"
result="${results[$((n - 1))]:-${results[${#results[@]}-1]}}"
case "$result" in
  ok) printf 'Enable succeeded: \n[stdout]\nlatest: Pulling from app\nDEPLOY_VM_STEP_OK\n\n[stderr]\n' ;;
  vm-failed) printf 'Enable succeeded: \n[stdout]\n\n[stderr]\nError response from daemon: manifest unknown\n' ;;
  az-error) echo "ERROR: (AuthorizationFailed) The client does not have authorization" >&2; exit 1 ;;
esac
"""

CURL_STUB = r"""#!/usr/bin/env bash
echo "curl ${@: -1}" >> "$STUB_STATE/calls.log"
file="$STUB_STATE/count.curl"; n=0
[ -f "$file" ] && n="$(cat "$file")"
n=$((n + 1)); echo "$n" > "$file"
read -r -a results <<< "${STUB_HEALTH:-healthy}"
result="${results[$((n - 1))]:-${results[${#results[@]}-1]}}"
case "$result" in
  healthy) echo '{"database":"connected","status":"healthy","timestamp":"2026-11-21T00:00:00+00:00"}' ;;
  liveness-only) echo '{"server":"running","status":"ok","timestamp":"2026-11-21T00:00:00+00:00"}' ;;
  no-database) echo '{"status":"healthy"}' ;;
  unhealthy) exit 22 ;;
  down) exit 7 ;;
esac
"""


class Deploy:
    def __init__(self, tmp_path):
        self.state = tmp_path / "state"
        self.bin = tmp_path / "bin"
        self.state.mkdir()
        self.bin.mkdir()
        for name, body in (("docker", DOCKER_STUB), ("az", AZ_STUB), ("curl", CURL_STUB)):
            path = self.bin / name
            path.write_text(body, encoding="utf-8")
            path.chmod(path.stat().st_mode | stat.S_IXUSR)
        self.summary = tmp_path / "summary.md"

    def run(self, **overrides):
        env = {
            "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}",
            "STUB_STATE": str(self.state),
            "STUB_REPO": REPO,
            "IMAGE_REPO": REPO,
            "IMAGE_TAG": TAG,
            "RESOURCE_GROUP": "example-group",
            "VM_NAME": "example-vm",
            "DB_HEALTH_URL": HEALTH_URL,
            "HEALTH_ATTEMPTS": "2",
            "HEALTH_INTERVAL": "0",
            "BASELINE_ATTEMPTS": "1",
            "GITHUB_STEP_SUMMARY": str(self.summary),
        }
        env.update(overrides)
        self.result = subprocess.run(
            ["bash", str(SCRIPT)], env=env, capture_output=True, text=True, timeout=60
        )
        self.output = self.result.stdout + self.result.stderr
        return self.result

    @property
    def calls(self):
        log = self.state / "calls.log"
        return log.read_text(encoding="utf-8").splitlines() if log.exists() else []

    def calls_starting(self, prefix):
        return [call for call in self.calls if call.startswith(prefix)]

    def index(self, prefix, occurrence=1):
        matches = [i for i, call in enumerate(self.calls) if call.startswith(prefix)]
        assert len(matches) >= occurrence, f"expected call #{occurrence} of {prefix!r} in {self.calls}"
        return matches[occurrence - 1]


@pytest.fixture
def deploy(tmp_path):
    return Deploy(tmp_path)


class TestSuccessfulDeploy:
    def test_publishes_commit_tag_then_latest_then_restarts_and_verifies(self, deploy):
        result = deploy.run()

        assert result.returncode == 0, deploy.output
        order = [
            deploy.index(f"curl {HEALTH_URL}"),          # production checked first
            deploy.index(f"docker pull {LATEST}"),       # previous image recorded
            deploy.index(f"docker tag {LATEST} {PREVIOUS_LOCAL}"),
            deploy.index(f"docker push {NEW}"),          # commit tag before latest
            deploy.index(f"docker tag {NEW} {LATEST}"),
            deploy.index(f"docker push {LATEST}"),
            deploy.index("az vm run-command invoke"),
            deploy.index(f"curl {HEALTH_URL}", 2),       # verified after the restart
        ]
        assert order == sorted(order)
        assert len(deploy.calls_starting("az ")) == 1
        assert len(deploy.calls_starting(f"docker push {LATEST}")) == 1
        assert f"previous image: {PREVIOUS_DIGEST}" in deploy.output
        assert "Enterprise deploy succeeded" in deploy.summary.read_text(encoding="utf-8")

    def test_vm_command_pulls_latest_and_restarts_the_service(self, deploy):
        deploy.run(SERVICE_NAME="example-service")

        (az_call,) = deploy.calls_starting("az ")
        assert "--resource-group example-group" in az_call
        assert "--name example-vm" in az_call
        assert f"docker pull {LATEST} && systemctl restart example-service && echo" in az_call
        # The success marker must not appear verbatim in the command text, or an
        # echoed command line could be mistaken for the command having succeeded.
        assert "DEPLOY_VM_STEP_OK" not in az_call

    def test_health_probe_is_not_cacheable(self, deploy):
        deploy.run()

        probes = deploy.calls_starting("curl ")
        assert all(probe.startswith(f"curl {HEALTH_URL}?deploy={TAG}-") for probe in probes)

    def test_health_url_with_a_query_string_keeps_it(self, deploy):
        deploy.run(DB_HEALTH_URL=f"{HEALTH_URL}?probe=1")

        assert deploy.result.returncode == 0, deploy.output
        assert deploy.calls_starting("curl ")[0].startswith(f"curl {HEALTH_URL}?probe=1&deploy={TAG}-")

    def test_waits_for_a_slow_start(self, deploy):
        result = deploy.run(STUB_HEALTH="healthy down unhealthy healthy", HEALTH_ATTEMPTS="5")

        assert result.returncode == 0, deploy.output
        assert "after deploy: healthy on attempt 3/5" in deploy.output
        assert len(deploy.calls_starting("az ")) == 1


class TestNothingIsChangedWhen:
    def assert_untouched(self, deploy):
        assert deploy.result.returncode == 1
        assert deploy.calls_starting("docker push") == []
        assert deploy.calls_starting("az ") == []
        assert "Nothing was published or deployed" in deploy.output

    def test_required_variable_is_missing(self, deploy):
        result = deploy.run(DB_HEALTH_URL="")

        assert result.returncode != 0
        assert "DB_HEALTH_URL is required" in deploy.output
        assert deploy.calls == []

    def test_new_image_was_not_built(self, deploy):
        deploy.run(STUB_NEW_IMAGE_MISSING="1")

        self.assert_untouched(deploy)

    def test_production_is_unhealthy_beforehand(self, deploy):
        deploy.run(STUB_HEALTH="unhealthy")

        self.assert_untouched(deploy)
        assert deploy.calls_starting("docker pull") == []
        assert "deploy_when_unhealthy" in deploy.output

    def test_previous_image_cannot_be_pulled(self, deploy):
        deploy.run(STUB_PULL_FAILS="1")

        self.assert_untouched(deploy)
        assert "no image to roll back to" in deploy.output

    def test_previous_image_digest_is_unknown(self, deploy):
        deploy.run(STUB_NO_DIGEST="1")

        self.assert_untouched(deploy)

    def test_commit_tag_push_fails(self, deploy):
        result = deploy.run(STUB_FAIL_PUSH="commit#1")

        assert result.returncode == 1
        assert deploy.calls_starting(f"docker push {LATEST}") == []
        assert deploy.calls_starting("az ") == []
        assert "'latest' was not moved and the VM was not touched" in deploy.output


class TestHealthBodyMustProveTheDatabase:
    @pytest.mark.parametrize("body", ["liveness-only", "no-database", "unhealthy", "down"])
    def test_baseline_rejects(self, deploy, body):
        """A liveness answer ("status": "ok") says nothing about the database."""
        result = deploy.run(STUB_HEALTH=body)

        assert result.returncode == 1
        assert deploy.calls_starting("docker push") == []

    def test_liveness_only_answer_after_deploy_triggers_rollback(self, deploy):
        result = deploy.run(STUB_HEALTH="healthy liveness-only liveness-only healthy")

        assert result.returncode == 1
        assert "ROLLBACK RESTORED SERVICE" in deploy.output


class TestRollback:
    def assert_rolled_back_through_vm(self, deploy):
        """latest re-pointed to the previous image, then the VM restarted again."""
        retag = deploy.index(f"docker tag {PREVIOUS_LOCAL} {LATEST}")
        repush = deploy.index(f"docker push {LATEST}", 2)
        second_restart = deploy.index("az vm run-command invoke", 2)
        assert deploy.index(f"docker push {LATEST}") < retag < repush < second_restart
        assert len(deploy.calls_starting("az ")) == 2

    def test_unhealthy_after_deploy_then_healthy_after_rollback(self, deploy):
        result = deploy.run(STUB_HEALTH="healthy unhealthy unhealthy healthy")

        assert result.returncode == 1, "a rolled back deploy must still fail the workflow"
        self.assert_rolled_back_through_vm(deploy)
        assert "ROLLBACK RESTORED SERVICE" in deploy.output
        assert PREVIOUS_DIGEST in deploy.output
        assert "::error title=Enterprise deploy failed::" in deploy.output
        assert "ROLLBACK RESTORED SERVICE" in deploy.summary.read_text(encoding="utf-8")

    def test_unhealthy_after_deploy_and_after_rollback(self, deploy):
        result = deploy.run(STUB_HEALTH="healthy unhealthy")

        assert result.returncode == 1
        self.assert_rolled_back_through_vm(deploy)
        assert "ROLLBACK DID NOT RESTORE SERVICE" in deploy.output
        assert "PRODUCTION IS DOWN" in deploy.output
        assert "ROLLBACK RESTORED SERVICE" not in deploy.output

    def test_vm_reports_pull_or_restart_failure(self, deploy):
        """az exits 0 although the command on the VM failed: no marker, no deploy."""
        result = deploy.run(STUB_AZ="vm-failed ok")

        assert result.returncode == 1
        self.assert_rolled_back_through_vm(deploy)
        assert "could not pull or restart on the new image" in deploy.output
        assert "ROLLBACK RESTORED SERVICE" in deploy.output

    def test_az_command_itself_fails(self, deploy):
        result = deploy.run(STUB_AZ="az-error ok")

        assert result.returncode == 1
        self.assert_rolled_back_through_vm(deploy)
        assert "ROLLBACK RESTORED SERVICE" in deploy.output

    def test_rollback_restart_unconfirmed_still_checks_health(self, deploy):
        result = deploy.run(STUB_AZ="ok az-error", STUB_HEALTH="healthy unhealthy unhealthy healthy")

        assert result.returncode == 1
        assert "did not confirm success; checking health anyway" in deploy.output
        assert "ROLLBACK RESTORED SERVICE" in deploy.output

    def test_latest_push_fails_before_the_vm_is_touched(self, deploy):
        result = deploy.run(STUB_FAIL_PUSH="latest#1")

        assert result.returncode == 1
        assert deploy.calls_starting("az ") == [], "the VM must not be restarted"
        retag = deploy.index(f"docker tag {PREVIOUS_LOCAL} {LATEST}")
        assert retag < deploy.index(f"docker push {LATEST}", 2)
        assert "The VM was never restarted" in deploy.output
        assert "Production is unchanged and healthy" in deploy.output

    def test_registry_refuses_the_rollback_push(self, deploy):
        result = deploy.run(STUB_HEALTH="healthy unhealthy", STUB_FAIL_PUSH="latest#2")

        assert result.returncode == 1
        assert "ROLLBACK FAILED" in deploy.output
        assert "PRODUCTION IS STILL ON THE FAILED IMAGE" in deploy.output
        assert len(deploy.calls_starting("az ")) == 1, "no second restart onto the same failed image"

    def test_failed_image_stays_available_by_commit_tag(self, deploy):
        deploy.run(STUB_HEALTH="healthy unhealthy unhealthy healthy")

        assert f"still in the registry as {NEW}" in deploy.output


class TestDeployingOntoAnUnhealthyService:
    def test_proceeds_when_explicitly_allowed(self, deploy):
        result = deploy.run(STUB_HEALTH="unhealthy healthy", DEPLOY_WHEN_UNHEALTHY="true")

        assert result.returncode == 0, deploy.output
        assert "::warning title=Deploying onto an unhealthy service::" in deploy.output
        assert len(deploy.calls_starting("az ")) == 1

    def test_still_fails_when_the_fix_does_not_help(self, deploy):
        result = deploy.run(STUB_HEALTH="unhealthy", DEPLOY_WHEN_UNHEALTHY="true")

        assert result.returncode == 1
        assert "ROLLBACK DID NOT RESTORE SERVICE" in deploy.output
