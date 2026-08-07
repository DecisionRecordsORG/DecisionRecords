#!/usr/bin/env python3
"""Guard nested-repository commit sequencing for public and private repos."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


PUBLIC_ROOT = Path(__file__).resolve().parents[1]
EE_ROOT = PUBLIC_ROOT / "ee"
MARKETING_ROOT = EE_ROOT / "marketing"


class BoundaryCheckError(RuntimeError):
    """Raised when a nested repository is in an unsafe state for the current commit."""


GIT_ENV_VARS_TO_CLEAR = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_PREFIX",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
)


def isolated_git_env() -> dict[str, str]:
    """Drop parent Git hook environment so nested repo commands resolve correctly."""
    env = os.environ.copy()
    for key in GIT_ENV_VARS_TO_CLEAR:
        env.pop(key, None)
    return env


def git_output(args: list[str], cwd: Path) -> str:
    return subprocess.check_output(args, cwd=cwd, env=isolated_git_env(), text=True).strip()


def git_result(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        env=isolated_git_env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def staged_paths(repo_root: Path) -> list[str]:
    output = git_output(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"], cwd=repo_root)
    return [line for line in output.splitlines() if line]


def repo_available(repo_root: Path) -> bool:
    result = git_result(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo_root)
    return result.returncode == 0 and result.stdout.strip() == "true"


def current_branch(repo_root: Path) -> str:
    result = git_result(["git", "symbolic-ref", "--quiet", "--short", "HEAD"], cwd=repo_root)
    return result.stdout.strip() if result.returncode == 0 else ""


def tracked_status(repo_root: Path) -> list[str]:
    output = git_output(["git", "status", "--short", "--untracked-files=no"], cwd=repo_root)
    return [line for line in output.splitlines() if line]


def current_head(repo_root: Path) -> str:
    return git_output(["git", "rev-parse", "HEAD"], cwd=repo_root)


def staged_gitlink(repo_root: Path, path: str) -> str:
    result = git_result(["git", "rev-parse", f":{path}"], cwd=repo_root)
    if result.returncode != 0:
        raise BoundaryCheckError(
            f"Unable to read staged gitlink for '{path}'. Re-stage the submodule pointer with `git add {path}`."
        )
    return result.stdout.strip()


def require_clean_named_child(
    *,
    parent_label: str,
    child_label: str,
    child_root: Path,
    missing_hint: str,
) -> str:
    if not child_root.exists() or not repo_available(child_root):
        raise BoundaryCheckError(
            f"Refusing {parent_label} commit: '{child_label}' is staged but {child_root} is not an initialized Git repo.\n"
            f"Next step: {missing_hint}"
        )

    branch = current_branch(child_root)
    if not branch:
        raise BoundaryCheckError(
            f"Refusing {parent_label} commit: '{child_label}' is staged but {child_label} is on detached HEAD.\n"
            f"Next step: create or switch to a named branch in {child_label}, then re-stage the pointer."
        )

    dirty = tracked_status(child_root)
    if dirty:
        rendered = "\n".join(f"  {line}" for line in dirty)
        raise BoundaryCheckError(
            f"Refusing {parent_label} commit: '{child_label}' is staged but {child_label} still has tracked changes or a dirty nested submodule.\n"
            f"{rendered}\n"
            f"Next step: commit inside {child_label} first, confirm it is clean, then re-stage the pointer."
        )

    return current_head(child_root)


def check_public_repo() -> None:
    if "ee" not in staged_paths(PUBLIC_ROOT):
        return

    ee_head = require_clean_named_child(
        parent_label="public",
        child_label="ee",
        child_root=EE_ROOT,
        missing_hint="run `git submodule update --init --recursive` if the private repo should be available here.",
    )
    if staged_gitlink(PUBLIC_ROOT, "ee") != ee_head:
        raise BoundaryCheckError(
            "Refusing public commit: staged `ee` pointer does not match the checked-out `ee` HEAD.\n"
            "Next step: commit/push inside `ee`, then run `git add ee` in the public repo."
        )


def check_ee_repo() -> None:
    if "marketing" not in staged_paths(EE_ROOT):
        return

    marketing_head = require_clean_named_child(
        parent_label="ee",
        child_label="marketing",
        child_root=MARKETING_ROOT,
        missing_hint="run `git submodule update --init --recursive` inside `ee` if marketing should be available here.",
    )
    if staged_gitlink(EE_ROOT, "marketing") != marketing_head:
        raise BoundaryCheckError(
            "Refusing ee commit: staged `marketing` pointer does not match the checked-out marketing HEAD.\n"
            "Next step: commit/push inside `ee/marketing`, then run `git add marketing` in `ee`."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Check nested Git repository commit boundaries.")
    parser.add_argument("--repo", choices=("public", "ee"), required=True)
    args = parser.parse_args()

    try:
        if args.repo == "public":
            check_public_repo()
        else:
            check_ee_repo()
    except BoundaryCheckError as error:
        print(f"repo-boundary: {error}")
        return 1

    print(f"repo-boundary: {args.repo} checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
