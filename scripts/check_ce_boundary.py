#!/usr/bin/env python3
"""Validate the public Community Edition / private EE boundary.

The public repository must be able to build and test without the private
``ee`` submodule. This script keeps that contract visible in CI.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = REPO_ROOT / "frontend" / "src"
STUB_ROOT = FRONTEND_ROOT / "stubs"

FRONTEND_EE_IMPORT_RE = re.compile(r"@ee/([^'\"\s)]+)")
PYTHON_EE_IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+ee(?:\.|\s|$)")

# Current public compatibility gateways. New backend EE imports should be moved
# into the private ee repo instead of expanding this list.
ALLOWED_BACKEND_EE_IMPORT_FILES = {
    REPO_ROOT / "app.py",
    REPO_ROOT / "crypto.py",
    REPO_ROOT / "notifications.py",
}

EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "dist",
    "ee",
    "__pycache__",
}


def iter_files(root: Path, suffixes: tuple[str, ...]):
    for path in root.rglob("*"):
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if path.is_file() and path.suffix in suffixes:
            yield path


def check_frontend_stubs() -> list[str]:
    errors: list[str] = []

    for path in iter_files(FRONTEND_ROOT, (".ts", ".html")):
        if "stubs" in path.parts:
            continue

        text = path.read_text(encoding="utf-8")
        for match in FRONTEND_EE_IMPORT_RE.finditer(text):
            ee_path = match.group(1)
            stub_path = STUB_ROOT / f"{ee_path}.ts"
            if not stub_path.exists():
                errors.append(
                    f"{path.relative_to(REPO_ROOT)} imports @ee/{ee_path}, "
                    f"but {stub_path.relative_to(REPO_ROOT)} is missing"
                )

    return errors


def check_backend_imports() -> list[str]:
    errors: list[str] = []

    for path in iter_files(REPO_ROOT, (".py",)):
        if "tests" in path.parts:
            continue
        if path in ALLOWED_BACKEND_EE_IMPORT_FILES:
            continue

        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if PYTHON_EE_IMPORT_RE.search(line):
                errors.append(
                    f"{path.relative_to(REPO_ROOT)}:{line_number} imports ee.* directly. "
                    "Move the implementation behind the private ee module boundary."
                )

    return errors


def main() -> int:
    errors = check_frontend_stubs()
    errors.extend(check_backend_imports())

    if errors:
        print("Community/Enterprise boundary check failed:\n")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Community/Enterprise boundary check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
