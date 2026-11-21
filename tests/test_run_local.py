"""Tests for the local development runner's edition selection.

``run_local.py`` used to default to Enterprise Edition and crash on the first
``ee`` import in a public checkout, where the private submodule is absent.
The runner is exercised as a subprocess against a stub ``app`` module so the
real application, database and environment are never touched.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

STUB_APP = """\
import os


class _App:
    def run(self, **kwargs):
        print("EDITION=" + os.environ["DECISION_RECORDS_EDITION"])


app = _App()
"""


def run_runner(tmp_path: Path, *args: str, with_ee: bool) -> subprocess.CompletedProcess:
    shutil.copy(REPO_ROOT / "run_local.py", tmp_path / "run_local.py")
    (tmp_path / "app.py").write_text(STUB_APP, encoding="utf-8")
    if with_ee:
        (tmp_path / "ee" / "backend").mkdir(parents=True)
        (tmp_path / "ee" / "backend" / "__init__.py").write_text("", encoding="utf-8")

    env = {key: value for key, value in os.environ.items() if key != "DECISION_RECORDS_EDITION"}
    return subprocess.run(
        [sys.executable, "run_local.py", *args],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


class TestRunLocalEditionSelection:
    def test_defaults_to_community_when_ee_is_not_checked_out(self, tmp_path):
        result = run_runner(tmp_path, with_ee=False)

        assert result.returncode == 0, result.stderr
        assert "EDITION=community" in result.stdout
        assert "running Community Edition" in result.stdout

    def test_empty_ee_directory_counts_as_not_checked_out(self, tmp_path):
        (tmp_path / "ee").mkdir()

        result = run_runner(tmp_path, with_ee=False)

        assert result.returncode == 0, result.stderr
        assert "EDITION=community" in result.stdout

    def test_defaults_to_enterprise_when_ee_is_checked_out(self, tmp_path):
        result = run_runner(tmp_path, with_ee=True)

        assert result.returncode == 0, result.stderr
        assert "EDITION=enterprise" in result.stdout

    def test_community_flag_wins_when_ee_is_checked_out(self, tmp_path):
        result = run_runner(tmp_path, "--community", with_ee=True)

        assert result.returncode == 0, result.stderr
        assert "EDITION=community" in result.stdout
        assert "Enterprise modules not found" not in result.stdout
