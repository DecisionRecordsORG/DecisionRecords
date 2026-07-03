#!/usr/bin/env python3
"""Verify local Git hook wiring without mutating the real index."""

from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PRE_COMMIT_HOOK = REPO_ROOT / ".githooks" / "pre-commit"


def run(
    command: list[str],
    *,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    process_env = os.environ.copy()
    if env:
        process_env.update(env)

    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=process_env,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if check and result.returncode != 0:
        print(result.stdout, end="")
        raise SystemExit(result.returncode)
    return result


def require(condition: bool, message: str) -> None:
    if not condition:
        print(f"hooks: {message}")
        raise SystemExit(1)


def verify_hook_config() -> None:
    require(PRE_COMMIT_HOOK.exists(), ".githooks/pre-commit is missing")
    mode = PRE_COMMIT_HOOK.stat().st_mode
    require(bool(mode & stat.S_IXUSR), ".githooks/pre-commit is not executable")

    hooks_path = run(["git", "config", "--get", "core.hooksPath"], check=False).stdout.strip()
    require(
        hooks_path == ".githooks",
        "core.hooksPath is not set to .githooks; run: git config core.hooksPath .githooks",
    )

    print("hooks: core.hooksPath is .githooks")


def prepare_index(index_path: str) -> dict[str, str]:
    env = {"GIT_INDEX_FILE": index_path}
    run(["git", "read-tree", "HEAD"], env=env)
    return env


def verify_positive_hook_run() -> None:
    with tempfile.TemporaryDirectory(prefix="decisionrecords-hooks-") as temp_dir:
        env = prepare_index(str(Path(temp_dir) / "index"))
        result = run([str(PRE_COMMIT_HOOK)], env=env)

    require("commit checks passed" in result.stdout, "pre-commit hook did not report a clean pass")
    print("hooks: clean pre-commit run passed")


def verify_private_artifact_rejection() -> None:
    with tempfile.TemporaryDirectory(prefix="decisionrecords-hooks-") as temp_dir:
        env = prepare_index(str(Path(temp_dir) / "index"))
        blob = run(["git", "hash-object", "-w", "--stdin"], input_text="{}\n").stdout.strip()
        run(
            [
                "git",
                "update-index",
                "--add",
                "--cacheinfo",
                f"100644,{blob},infra/snapshots/should-not-be-public.json",
            ],
            env=env,
        )
        result = run([str(PRE_COMMIT_HOOK)], env=env, check=False)

    require(result.returncode != 0, "pre-commit hook allowed a fake public infra artifact")
    require(
        "Open-source artifact check failed" in result.stdout,
        "pre-commit hook failed for the wrong reason during negative artifact test",
    )
    print("hooks: private artifact rejection test passed")


def main() -> int:
    verify_hook_config()
    verify_positive_hook_run()
    verify_private_artifact_rejection()
    print("hooks: verification passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
