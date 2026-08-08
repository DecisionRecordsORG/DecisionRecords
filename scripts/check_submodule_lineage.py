#!/usr/bin/env python3
"""Validate that nested submodule pointers resolve on the child repository main branch."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PUBLIC_ROOT = Path(__file__).resolve().parents[1]
EE_ROOT = PUBLIC_ROOT / "ee"
MARKETING_ROOT = EE_ROOT / "marketing"
REMOTE_MAIN_REF = "refs/remotes/origin/main"


class LineageError(RuntimeError):
    """Raised when a submodule pointer is not durable on the child main branch."""


REPO_CONFIG = {
    "public": {
        "parent_root": PUBLIC_ROOT,
        "child_root": EE_ROOT,
        "gitlink_path": "ee",
        "child_label": "ee",
        "parent_label": "public",
    },
    "ee": {
        "parent_root": EE_ROOT,
        "child_root": MARKETING_ROOT,
        "gitlink_path": "marketing",
        "child_label": "marketing",
        "parent_label": "ee",
    },
}


def git_result(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def git_output(args: list[str], cwd: Path) -> str:
    result = git_result(args, cwd)
    if result.returncode != 0:
        raise LineageError(result.stderr.strip() or result.stdout.strip() or "git command failed")
    return result.stdout.strip()


def fetch_origin_main(repo_root: Path) -> None:
    result = git_result(
        ["git", "fetch", "--quiet", "--no-tags", "origin", f"+refs/heads/main:{REMOTE_MAIN_REF}"],
        cwd=repo_root,
    )
    if result.returncode != 0:
        raise LineageError(
            f"Unable to fetch origin/main in {repo_root}.\n"
            f"Git said: {result.stderr.strip() or result.stdout.strip()}"
        )


def require_repo(repo_root: Path, label: str) -> None:
    result = git_result(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo_root)
    if result.returncode != 0 or result.stdout.strip() != "true":
        raise LineageError(f"Expected {label} at {repo_root}, but it is not an initialized Git repository.")


def read_gitlink(parent_root: Path, path: str, source: str) -> str:
    spec = f"HEAD:{path}" if source == "head" else f":{path}"
    result = git_result(["git", "rev-parse", spec], cwd=parent_root)
    if result.returncode != 0:
        guidance = "commit or check out the parent revision first" if source == "head" else f"stage `{path}` first"
        raise LineageError(
            f"Unable to resolve the {source} gitlink for `{path}` in {parent_root}.\n"
            f"Next step: {guidance}."
        )
    return result.stdout.strip()


def require_commit_present(repo_root: Path, commit_sha: str, label: str) -> None:
    result = git_result(["git", "cat-file", "-e", f"{commit_sha}^{{commit}}"], cwd=repo_root)
    if result.returncode != 0:
        raise LineageError(
            f"The {label} repository does not contain commit {commit_sha}.\n"
            "Next step: initialize the submodule recursively or fetch the missing child repository history."
        )


def require_remote_main(repo_root: Path, label: str) -> None:
    result = git_result(["git", "rev-parse", "--verify", "--quiet", REMOTE_MAIN_REF], cwd=repo_root)
    if result.returncode != 0:
        raise LineageError(
            f"{label} does not have {REMOTE_MAIN_REF} locally.\n"
            "Next step: fetch origin/main before running the lineage check."
        )


def require_commit_reachable_from_main(repo_root: Path, commit_sha: str, child_label: str, parent_label: str) -> None:
    result = git_result(["git", "merge-base", "--is-ancestor", commit_sha, REMOTE_MAIN_REF], cwd=repo_root)
    if result.returncode == 0:
        return

    remote_branches = git_output(["git", "branch", "-r", "--contains", commit_sha], cwd=repo_root)
    reachable = ", ".join(branch.strip() for branch in remote_branches.splitlines() if branch.strip()) or "none"
    raise LineageError(
        f"The {parent_label} repo points at {child_label} commit {commit_sha}, but that commit is not on {child_label} origin/main.\n"
        f"Remote refs containing the commit: {reachable}\n"
        "Next step: merge the child PR with a commit-preserving strategy (rebase or merge commit), or update the parent pointer after child main advances.\n"
        "Do not rely on squash-only child merges for submodule pointers."
    )


def check_lineage(repo_name: str, *, source: str, fetch: bool) -> None:
    config = REPO_CONFIG[repo_name]
    parent_root = config["parent_root"]
    child_root = config["child_root"]
    gitlink_path = config["gitlink_path"]
    child_label = config["child_label"]
    parent_label = config["parent_label"]

    require_repo(parent_root, parent_label)
    require_repo(child_root, child_label)

    commit_sha = read_gitlink(parent_root, gitlink_path, source)
    require_commit_present(child_root, commit_sha, child_label)
    if fetch:
        fetch_origin_main(child_root)
    require_remote_main(child_root, child_label)
    require_commit_reachable_from_main(child_root, commit_sha, child_label, parent_label)

    print(f"submodule-lineage: {parent_label} -> {child_label} commit {commit_sha} is reachable from {REMOTE_MAIN_REF}.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check that submodule gitlinks point to child main history.")
    parser.add_argument("--repo", choices=sorted(REPO_CONFIG), required=True)
    parser.add_argument("--source", choices=("head", "staged"), default="head")
    parser.add_argument("--fetch", action="store_true", help="Fetch origin/main in the child repository before validating.")
    args = parser.parse_args()

    try:
        check_lineage(args.repo, source=args.source, fetch=args.fetch)
    except LineageError as error:
        print(f"submodule-lineage: {error}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
