#!/usr/bin/env python3
"""Validate community release metadata before tagging or publishing."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = REPO_ROOT / "version.py"
CHANGELOG_FILE = REPO_ROOT / "CHANGELOG.md"
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
VERSION_PATTERN = re.compile(r'^__version__ = "([^"]+)"$', re.MULTILINE)
CHANGELOG_HEADING_PATTERN = re.compile(r"^## \[([0-9]+\.[0-9]+\.[0-9]+)\]", re.MULTILINE)
UNRELEASED_LINK_PATTERN = re.compile(r"^\[Unreleased\]: .*?/compare/v([0-9]+\.[0-9]+\.[0-9]+)\.\.\.HEAD$", re.MULTILINE)

DOC_VERSION_CHECKS = (
    (
        REPO_ROOT / "README.md",
        "README pinned release example",
        re.compile(r"For a pinned install, prefer a version tag such as `v([0-9]+\.[0-9]+\.[0-9]+)` once that release is published\."),
    ),
    (
        REPO_ROOT / "docs" / "configuration.md",
        "configuration version endpoint example",
        re.compile(r'### Version Endpoint.*?"version": "([0-9]+\.[0-9]+\.[0-9]+)"', re.DOTALL),
    ),
    (
        REPO_ROOT / "docs" / "self-hosting.md",
        "self-hosting pinned docker pull example",
        re.compile(r"docker pull ghcr\.io/decisionrecordsorg/decisionrecords:v([0-9]+\.[0-9]+\.[0-9]+)"),
    ),
    (
        REPO_ROOT / "docs" / "self-hosting.md",
        "self-hosting upgrade note",
        re.compile(r"If upgrading from a version before `v([0-9]+\.[0-9]+\.[0-9]+)`"),
    ),
)


def read_version(version_file: Path = VERSION_FILE) -> str:
    content = version_file.read_text(encoding="utf-8")
    match = VERSION_PATTERN.search(content)
    if not match:
        raise ValueError(f"Could not find __version__ in {version_file}")
    version = match.group(1)
    if not SEMVER_RE.match(version):
        raise ValueError(f"Version '{version}' is not MAJOR.MINOR.PATCH")
    return version


def validate_changelog(version: str, changelog_file: Path = CHANGELOG_FILE) -> list[str]:
    content = changelog_file.read_text(encoding="utf-8")
    errors: list[str] = []

    heading_match = CHANGELOG_HEADING_PATTERN.search(content)
    if not heading_match:
        errors.append(f"{changelog_file} does not contain any release headings")
    elif heading_match.group(1) != version:
        errors.append(
            f"{changelog_file} latest release heading is {heading_match.group(1)}, expected {version}"
        )

    unreleased_match = UNRELEASED_LINK_PATTERN.search(content)
    if not unreleased_match:
        errors.append(f"{changelog_file} is missing the [Unreleased] compare link")
    elif unreleased_match.group(1) != version:
        errors.append(
            f"{changelog_file} [Unreleased] compare link points to {unreleased_match.group(1)}, expected {version}"
        )

    return errors


def validate_docs(version: str) -> list[str]:
    errors: list[str] = []

    for path, label, pattern in DOC_VERSION_CHECKS:
        content = path.read_text(encoding="utf-8")
        match = pattern.search(content)
        if not match:
            errors.append(f"{label} marker not found in {path}")
            continue
        found_version = match.group(1)
        if found_version != version:
            errors.append(f"{label} in {path} uses {found_version}, expected {version}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Decision Records release metadata.")
    parser.add_argument(
        "--tag",
        help="Expected release tag, for example v2.0.28.",
    )
    args = parser.parse_args()

    version = read_version()
    print(f"release-check: version.py reports {version}")

    errors = [*validate_changelog(version), *validate_docs(version)]

    if args.tag:
        expected_tag = f"v{version}"
        if args.tag != expected_tag:
            errors.append(f"tag/version mismatch: expected {expected_tag}, got {args.tag}")
        else:
            print(f"release-check: tag matches version.py ({args.tag})")

    if errors:
        for error in errors:
            print(f"release-check: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
