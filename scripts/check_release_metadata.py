#!/usr/bin/env python3
"""Validate community release metadata before tagging or publishing."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = REPO_ROOT / "version.py"
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
VERSION_PATTERN = re.compile(r'^__version__ = "([^"]+)"$', re.MULTILINE)


def read_version() -> str:
    content = VERSION_FILE.read_text(encoding="utf-8")
    match = VERSION_PATTERN.search(content)
    if not match:
        raise ValueError(f"Could not find __version__ in {VERSION_FILE}")
    version = match.group(1)
    if not SEMVER_RE.match(version):
        raise ValueError(f"Version '{version}' is not MAJOR.MINOR.PATCH")
    return version


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Decision Records release metadata.")
    parser.add_argument(
        "--tag",
        help="Expected release tag, for example v2.0.28.",
    )
    args = parser.parse_args()

    version = read_version()
    print(f"release-check: version.py reports {version}")

    if args.tag:
        expected_tag = f"v{version}"
        if args.tag != expected_tag:
            print(
                f"release-check: tag/version mismatch: expected {expected_tag}, got {args.tag}",
                file=sys.stderr,
            )
            return 1
        print(f"release-check: tag matches version.py ({args.tag})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
