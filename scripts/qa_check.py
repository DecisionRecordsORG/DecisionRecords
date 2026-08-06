#!/usr/bin/env python3
"""Run local QA checks used by Git hooks and release prep."""

from __future__ import annotations

import argparse
import fnmatch
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = REPO_ROOT / "frontend"

FORBIDDEN_STAGED_PATTERNS = (
    ".env",
    ".env.*",
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    "*.pyc",
    "__pycache__/*",
    "instance/*",
    "frontend/dist/*",
    "frontend/node_modules/*",
    ".venv/*",
)

FRONTEND_QA_PREFIXES = (
    "frontend/src/",
    "frontend/public/",
)

FRONTEND_QA_FILES = (
    "frontend/angular.json",
    "frontend/package.json",
    "frontend/package-lock.json",
    "frontend/prerender-routes.txt",
    "frontend/tsconfig.json",
    "frontend/tsconfig.app.json",
    "frontend/tsconfig.app.ce.json",
    "frontend/tsconfig.ce.json",
)

COMMUNITY_TEST_ENV = {
    "DECISION_RECORDS_EDITION": "community",
    "DATABASE_URL": "sqlite:///test.db",
    "SECRET_KEY": "test-secret-key",
    "FLASK_ENV": "testing",
    "AZURE_KEYVAULT_URL": "",
}


def run(command: list[str], cwd: Path = REPO_ROOT, env: dict[str, str] | None = None) -> None:
    display = " ".join(command)
    if cwd != REPO_ROOT:
        display = f"(cd {cwd.relative_to(REPO_ROOT)} && {display})"
    print(f"qa: {display}")
    process_env = os.environ.copy()
    if env:
        process_env.update(env)
    subprocess.run(command, cwd=cwd, env=process_env, check=True)


def output(command: list[str], cwd: Path = REPO_ROOT) -> str:
    return subprocess.check_output(command, cwd=cwd, text=True)


def staged_files() -> list[str]:
    files = output(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"]).splitlines()
    return [path for path in files if path]


def path_matches(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def check_forbidden_files(files: list[str]) -> None:
    blocked = [path for path in files if path_matches(path, FORBIDDEN_STAGED_PATTERNS)]
    if blocked:
        print("qa: refusing to commit generated, local, or secret-like files:")
        for path in blocked:
            print(f"  - {path}")
        raise SystemExit(1)


def check_staged_whitespace() -> None:
    run(["git", "diff", "--cached", "--check"])


def check_ce_boundary() -> None:
    run(["uv", "run", "python", "scripts/check_ce_boundary.py"])


def check_public_artifacts() -> None:
    run(["uv", "run", "python", "scripts/check_public_artifacts.py", "--mode", "staged"])


def staged_python_files(files: list[str]) -> list[str]:
    return [path for path in files if path.endswith(".py") and Path(REPO_ROOT / path).exists()]


def frontend_changed(files: list[str]) -> bool:
    for path in files:
        if path in FRONTEND_QA_FILES:
            return True
        if path.startswith(FRONTEND_QA_PREFIXES) and Path(path).suffix in {".ts", ".html", ".scss", ".css", ".json"}:
            return True
    return False


def check_python_compile(files: list[str]) -> None:
    python_files = staged_python_files(files)
    if python_files:
        run(["uv", "run", "python", "-m", "py_compile", *python_files])


def check_frontend_typecheck(files: list[str]) -> None:
    if not frontend_changed(files):
        return

    if not (FRONTEND_ROOT / "node_modules").exists():
        print("qa: frontend files changed, but frontend/node_modules is missing.")
        print("qa: run 'cd frontend && npm ci' before committing frontend changes.")
        raise SystemExit(1)

    run(["npx", "tsc", "-p", "tsconfig.app.ce.json", "--noEmit"], cwd=FRONTEND_ROOT)


def run_commit_checks() -> None:
    files = staged_files()
    check_forbidden_files(files)
    check_public_artifacts()
    check_staged_whitespace()
    check_ce_boundary()
    check_python_compile(files)
    check_frontend_typecheck(files)


def run_full_checks() -> None:
    run_commit_checks()
    run(["uv", "run", "python", "scripts/check_release_metadata.py"])
    run(["uv", "run", "pytest", "tests/", "-q", "--tb=short"], env=COMMUNITY_TEST_ENV)
    run(["npx", "tsc", "-p", "tsconfig.app.ce.json", "--noEmit"], cwd=FRONTEND_ROOT)
    run(["npm", "run", "build", "--", "--configuration=community", "--progress=false"], cwd=FRONTEND_ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Decision Records QA checks.")
    parser.add_argument(
        "--mode",
        choices=("commit", "full"),
        default="commit",
        help="commit runs fast staged checks; full also runs tests and production frontend build.",
    )
    args = parser.parse_args()

    if args.mode == "commit" and os.environ.get("SKIP_COMMIT_QA") == "1":
        print("qa: SKIP_COMMIT_QA=1 set, skipping commit QA checks.")
        return 0

    try:
        if args.mode == "full":
            run_full_checks()
        else:
            run_commit_checks()
    except subprocess.CalledProcessError as error:
        return error.returncode

    print(f"qa: {args.mode} checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
