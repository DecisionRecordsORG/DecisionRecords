#!/usr/bin/env python3
"""Reject private production artifacts from the public CE repository.

This check intentionally scans Git blobs instead of only the working tree so a
pre-commit hook reviews the exact content being committed.
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import re
import subprocess
import sys
from dataclasses import dataclass


FORBIDDEN_PUBLIC_PATH_PATTERNS = (
    ".azure/**",
    "infra/**",
    "backups/**",
    "*.bak",
    "*.crt",
    "*.dump",
    "*.key",
    "*.p12",
    "*.pem",
    "*.pfx",
    "*.publishsettings",
    "*.sql",
    "credentials.json",
    "local_secrets.py",
    "secrets.json",
)

PRIVATE_RESOURCE_PATTERNS = (
    (re.compile(r"\badrregistry2024eu\b", re.IGNORECASE), "production Azure Container Registry name"),
    (re.compile(r"\badr-keyvault-eu\b", re.IGNORECASE), "production Key Vault name"),
    (re.compile(r"\badr-postgres-eu-restore2\b", re.IGNORECASE), "production PostgreSQL server name"),
    (re.compile(r"\badr-postgres-restore2-pe\b", re.IGNORECASE), "production PostgreSQL private endpoint name"),
    (re.compile(r"\badr-vm-eu\b", re.IGNORECASE), "production VM name"),
    (re.compile(r"\badr-vm-ip\b", re.IGNORECASE), "production VM public IP resource name"),
    (re.compile(r"\badr-vnet\b", re.IGNORECASE), "production VNet name"),
    (re.compile(r"\badr-logs-workspace\b", re.IGNORECASE), "production Log Analytics workspace name"),
    (re.compile(r"\badr-resources-eu\b", re.IGNORECASE), "production Azure resource group"),
    (re.compile(r"\badr-app-aca\b", re.IGNORECASE), "production ACA app name"),
    (re.compile(r"\badr-aca-env-eu\b", re.IGNORECASE), "production ACA environment name"),
    (re.compile(r"\badr-aca-app-mi\b", re.IGNORECASE), "production ACA managed identity name"),
    (re.compile(r"\bdecisionrecords-marketing\b", re.IGNORECASE), "production Static Web App resource name"),
    (re.compile(r"\b52\.157\.83\.52\b"), "production VM public IP address"),
    (re.compile(r"\b10\.0\.4\.100\b"), "production VM private IP address"),
    (re.compile(r"\b10\.0\.0\.0/16\b"), "production VNet address space"),
    (re.compile(r"\b10\.0\.[0-5]\.0/24\b"), "production subnet address space"),
    (re.compile(r"\b55dd53366f300d407b322ff4d9be173d\b", re.IGNORECASE), "production Cloudflare zone id"),
)

SECRET_VALUE_PATTERNS = (
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key material"),
    (
        re.compile(
            r"(?i)\b(?:client_secret|clientSecret|sharedAccessKey|accountKey)\b"
            r"\s*[:=]\s*['\"][A-Za-z0-9+/=._~:-]{24,}"
        ),
        "credential value",
    ),
    (
        re.compile(
            r"(?i)\b(?:slack|teams|cloudflare|google|microsoft|azure)[A-Z0-9_-]*"
            r"(?:token|secret|password|key)\b\s*[:=]\s*['\"][A-Za-z0-9+/=._~:-]{24,}"
        ),
        "service token or secret value",
    ),
    (
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
        "JWT-like token value",
    ),
)

PLACEHOLDER_MARKERS = (
    "${{ secrets.",
    "<",
    "...",
    "change-me",
    "example",
    "placeholder",
    "test-secret",
    "your-",
)


@dataclass(frozen=True)
class Blob:
    path: str
    data: bytes


def git_output(command: list[str]) -> str:
    return subprocess.check_output(command, text=True)


def git_blob(ref: str, path: str) -> bytes | None:
    blob_ref = f":{path}" if ref == ":" else f"{ref}:{path}"
    result = subprocess.run(
        ["git", "show", blob_ref],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def staged_paths() -> list[str]:
    output = git_output(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"])
    return [path for path in output.splitlines() if path]


def tracked_paths() -> list[str]:
    output = subprocess.check_output(["git", "ls-files", "-z"])
    return [path for path in output.decode("utf-8").split("\0") if path]


def is_private_submodule_path(path: str) -> bool:
    return path == "ee" or path.startswith("ee/")


def iter_blobs(mode: str) -> list[Blob]:
    paths = staged_paths() if mode == "staged" else tracked_paths()
    blobs: list[Blob] = []

    for path in paths:
        if is_private_submodule_path(path):
            continue

        if mode == "staged":
            data = git_blob(":", path)
        elif os.path.islink(path):
            data = os.readlink(path).encode("utf-8")
        else:
            try:
                with open(path, "rb") as file:
                    data = file.read()
            except FileNotFoundError:
                data = None

        if data is None:
            continue
        blobs.append(Blob(path=path, data=data))

    return blobs


def path_matches(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def decode_text(data: bytes) -> str | None:
    if b"\0" in data[:8192]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def is_placeholder_line(line: str) -> bool:
    normalized = line.lower()
    return any(marker in normalized for marker in PLACEHOLDER_MARKERS)


def check_blob(blob: Blob) -> list[str]:
    errors: list[str] = []

    if path_matches(blob.path, FORBIDDEN_PUBLIC_PATH_PATTERNS):
        errors.append(f"{blob.path}: path belongs in the private repo or local runtime state")

    text = decode_text(blob.data)
    if text is None:
        return errors

    for line_number, line in enumerate(text.splitlines(), start=1):
        for pattern, description in PRIVATE_RESOURCE_PATTERNS:
            if pattern.search(line):
                errors.append(f"{blob.path}:{line_number}: contains {description}")

        if is_placeholder_line(line):
            continue

        for pattern, description in SECRET_VALUE_PATTERNS:
            if pattern.search(line):
                errors.append(f"{blob.path}:{line_number}: contains {description}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Check public repository artifacts.")
    parser.add_argument(
        "--mode",
        choices=("staged", "all"),
        default="staged",
        help="staged checks the index for pre-commit; all checks tracked HEAD blobs for CI.",
    )
    args = parser.parse_args()

    errors: list[str] = []
    for blob in iter_blobs(args.mode):
        errors.extend(check_blob(blob))

    if errors:
        print("Open-source artifact check failed:\n")
        for error in errors:
            print(f"- {error}")
        print("\nMove production infra, snapshots, and proprietary artifacts into the private ee repo.")
        return 1

    print("Open-source artifact check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
