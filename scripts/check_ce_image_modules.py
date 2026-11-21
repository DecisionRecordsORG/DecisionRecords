#!/usr/bin/env python3
"""Validate that the Community image ships every module the app imports.

``Dockerfile.community`` decides which files reach the published image, while
pytest always runs from the repository root where every module exists. A root
module that ``app.py`` imports but the Dockerfile does not copy therefore
passes every test and still crashes the published image at startup with
``ModuleNotFoundError``.

This check is static so it can run in hooks and CI without Docker:

1. Walk the first-party import graph starting from the image entry module.
2. Work out which build-context paths the final Dockerfile stage copies, after
   applying the Dockerfile-specific (or root) ``.dockerignore``.
3. Fail when an imported first-party module is not shipped, or when a file that
   must never be in the image (tests, local runner, env files, databases,
   private modules) would be shipped.

The real image is still booted by the CI and release smoke tests
(``scripts/smoke_test_ce_image.sh``). This check is the fast early warning.
"""

from __future__ import annotations

import argparse
import ast
import re
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


REPO_ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE_NAME = "Dockerfile.community"

# Module named by the image CMD (``gunicorn ... app:app``).
ENTRY_MODULES = ("app",)

# Top-level packages that are intentionally absent from the Community image.
# Imports of these are policed by scripts/check_ce_boundary.py instead.
EXCLUDED_TOP_LEVEL_PACKAGES = {"ee"}

# Paths that must never be shipped. They are probes, not a file listing: the
# check asks "would this be copied if it existed in the build context?" so it
# also protects local builds where these files do exist.
FORBIDDEN_IMAGE_PROBES = (
    "run_local.py",
    "local_secrets.py",
    "conftest.py",
    ".env",
    ".env.local",
    ".env.production",
    "architecture_decisions.db",
    "test.db",
    "instance/architecture_decisions.db",
    "instance/decisions.db",
    "tests/__init__.py",
    "tests/test_auth.py",
    "e2e/tests/decisions.spec.ts",
    "ee/__init__.py",
    "ee/backend/__init__.py",
    "scripts/qa_check.py",
    ".git/config",
    ".venv/pyvenv.cfg",
)


class ImageCheckError(Exception):
    """Raised when the Dockerfile cannot be analysed reliably."""


@dataclass(frozen=True)
class CopyInstruction:
    sources: tuple[str, ...]
    destination: str
    line_number: int


def _logical_lines(text: str) -> list[tuple[int, str]]:
    """Join backslash continuations and drop comments and blank lines."""
    lines: list[tuple[int, str]] = []
    buffer = ""
    start = 0
    for number, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not buffer and (not stripped or stripped.startswith("#")):
            continue
        if buffer and stripped.startswith("#"):
            continue
        if not buffer:
            start = number
        if stripped.endswith("\\"):
            buffer += stripped[:-1] + " "
            continue
        buffer += stripped
        lines.append((start, buffer))
        buffer = ""
    if buffer:
        lines.append((start, buffer))
    return lines


def parse_final_stage_copies(dockerfile_text: str) -> list[CopyInstruction]:
    """Return build-context COPY/ADD instructions of the final image stage."""
    copies: list[CopyInstruction] = []
    seen_from = False

    for line_number, line in _logical_lines(dockerfile_text):
        instruction, _, rest = line.partition(" ")
        keyword = instruction.upper()

        if keyword == "FROM":
            seen_from = True
            copies = []
            continue
        if keyword not in {"COPY", "ADD"}:
            continue

        rest = rest.strip()
        if rest.startswith("["):
            raise ImageCheckError(
                f"{DOCKERFILE_NAME}:{line_number} uses JSON-form {keyword}; "
                "check_ce_image_modules.py only understands the shell form."
            )

        tokens = shlex.split(rest)
        flags = [token for token in tokens if token.startswith("--")]
        paths = [token for token in tokens if not token.startswith("--")]
        if any(flag.startswith("--from") for flag in flags):
            continue  # copied from another stage, not from the build context
        if len(paths) < 2:
            raise ImageCheckError(f"{DOCKERFILE_NAME}:{line_number} has a {keyword} without a destination.")

        copies.append(
            CopyInstruction(
                sources=tuple(paths[:-1]),
                destination=paths[-1],
                line_number=line_number,
            )
        )

    if not seen_from:
        raise ImageCheckError(f"{DOCKERFILE_NAME} has no FROM instruction.")
    return copies


def parse_workdir(dockerfile_text: str) -> str:
    """Return the WORKDIR in effect at the end of the final stage."""
    workdir = "/"
    for _, line in _logical_lines(dockerfile_text):
        instruction, _, rest = line.partition(" ")
        keyword = instruction.upper()
        if keyword == "FROM":
            workdir = "/"
        elif keyword == "WORKDIR":
            value = rest.strip()
            workdir = value if value.startswith("/") else str(PurePosixPath(workdir) / value)
    return workdir


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Translate a Docker (Go filepath.Match plus ``**``) pattern to a regex."""
    parts: list[str] = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if pattern.startswith("**/", index):
            parts.append("(?:.*/)?")
            index += 3
            continue
        if pattern.startswith("**", index):
            parts.append(".*")
            index += 2
            continue
        if char == "*":
            parts.append("[^/]*")
        elif char == "?":
            parts.append("[^/]")
        elif char == "[":
            end = pattern.find("]", index + 1)
            if end == -1:
                parts.append(re.escape(char))
            else:
                # Go character classes negate with ``^``, the same as regex.
                body = pattern[index + 1:end].replace("\\", "\\\\")
                parts.append(f"[{body}]")
                index = end
        else:
            parts.append(re.escape(char))
        index += 1
    return re.compile("^" + "".join(parts) + "$")


def _normalise(path: str) -> str:
    path = path.strip()
    while path.startswith("./"):
        path = path[2:]
    path = path.strip("/")
    return "" if path == "." else path


def _path_and_parents(path: str) -> list[str]:
    parts = _normalise(path).split("/")
    return ["/".join(parts[:end]) for end in range(1, len(parts) + 1)]


class DockerIgnore:
    """Minimal .dockerignore matcher: ordered patterns, last match wins."""

    def __init__(self, text: str):
        self.rules: list[tuple[bool, re.Pattern[str]]] = []
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            negated = line.startswith("!")
            if negated:
                line = line[1:].strip()
            pattern = _normalise(line)
            if pattern:
                self.rules.append((negated, _glob_to_regex(pattern)))

    def is_ignored(self, path: str) -> bool:
        candidates = _path_and_parents(path)
        ignored = False
        for negated, regex in self.rules:
            if any(regex.match(candidate) for candidate in candidates):
                ignored = not negated
        return ignored


class ImageManifest:
    """Answers whether a build-context path lands in the final image stage."""

    def __init__(self, dockerfile_text: str, dockerignore_text: str = ""):
        self.copies = parse_final_stage_copies(dockerfile_text)
        self.workdir = parse_workdir(dockerfile_text)
        self.dockerignore = DockerIgnore(dockerignore_text)

    def _destination_dir(self, destination: str) -> str:
        if destination.startswith("/"):
            absolute = PurePosixPath(destination)
        else:
            absolute = PurePosixPath(self.workdir) / destination
        return str(absolute).rstrip("/") or "/"

    def image_path(self, context_path: str) -> str | None:
        """Return the absolute image path for a context file, or None if not shipped."""
        path = _normalise(context_path)
        if self.dockerignore.is_ignored(path):
            return None

        candidates = _path_and_parents(path)
        for copy in self.copies:
            destination = self._destination_dir(copy.destination)
            for source in copy.sources:
                source_pattern = _normalise(source)
                if not source_pattern:  # ``COPY . dest`` ships the whole context
                    return f"{destination.rstrip('/')}/{path}"
                regex = _glob_to_regex(source_pattern)
                for candidate in candidates:
                    if not regex.match(candidate):
                        continue
                    if candidate == path:
                        # A file source is placed in the destination directory.
                        return f"{destination.rstrip('/')}/{path.rsplit('/', 1)[-1]}"
                    # A directory source: its contents are placed under the destination.
                    remainder = path[len(candidate) + 1:]
                    return f"{destination.rstrip('/')}/{remainder}"
        return None

    def ships(self, context_path: str) -> bool:
        return self.image_path(context_path) is not None


def _module_file(repo_root: Path, module: str) -> str | None:
    """Return the repo-relative file for a first-party top-level module."""
    if module in EXCLUDED_TOP_LEVEL_PACKAGES:
        return None
    if (repo_root / f"{module}.py").is_file():
        return f"{module}.py"
    if (repo_root / module / "__init__.py").is_file():
        return f"{module}/__init__.py"
    return None


def _imported_top_level_names(source: str, filename: str) -> set[str]:
    names: set[str] = set()
    tree = ast.parse(source, filename=filename)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            # importlib.import_module("name") / __import__("name") with a literal
            func = node.func
            func_name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if func_name in {"import_module", "__import__"} and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    names.add(first.value.split(".")[0])
    return names


def first_party_import_closure(
    repo_root: Path, entry_modules: tuple[str, ...] = ENTRY_MODULES
) -> dict[str, str]:
    """Map every first-party module reachable from the entry modules to its importer.

    Imports anywhere in a module count, including ones nested inside functions
    or ``try`` blocks, because a lazily imported module still has to be in the
    image when the code path runs.
    """
    imported_by: dict[str, str] = {}
    queue: list[str] = []

    for module in entry_modules:
        if _module_file(repo_root, module) is None:
            raise ImageCheckError(f"Entry module '{module}' was not found in {repo_root}.")
        imported_by[module] = "image entrypoint"
        queue.append(module)

    while queue:
        module = queue.pop()
        module_file = _module_file(repo_root, module)
        if module_file is None:
            continue

        if module_file.endswith("__init__.py"):
            package_dir = repo_root / module
            sources = sorted(path for path in package_dir.rglob("*.py") if "__pycache__" not in path.parts)
        else:
            sources = [repo_root / module_file]

        for source_path in sources:
            relative = source_path.relative_to(repo_root).as_posix()
            for name in sorted(_imported_top_level_names(source_path.read_text(encoding="utf-8"), relative)):
                if name in imported_by or _module_file(repo_root, name) is None:
                    continue
                imported_by[name] = relative
                queue.append(name)

    return imported_by


def find_errors(
    repo_root: Path = REPO_ROOT,
    dockerfile_text: str | None = None,
    dockerignore_text: str | None = None,
) -> list[str]:
    """Return human-readable problems with the Community image file set."""
    if dockerfile_text is None:
        dockerfile_text = (repo_root / DOCKERFILE_NAME).read_text(encoding="utf-8")
    if dockerignore_text is None:
        dockerignore_text = read_dockerignore(repo_root)

    manifest = ImageManifest(dockerfile_text, dockerignore_text)
    workdir = manifest.workdir.rstrip("/")
    errors: list[str] = []

    closure = first_party_import_closure(repo_root)
    for module in sorted(closure):
        module_file = _module_file(repo_root, module)
        assert module_file is not None
        expected = f"{workdir}/{module_file}"
        actual = manifest.image_path(module_file)
        if actual is None:
            errors.append(
                f"{module_file} is imported by {closure[module]} but {DOCKERFILE_NAME} does not ship it. "
                "The image would fail at startup with ModuleNotFoundError."
            )
        elif actual != expected:
            errors.append(
                f"{module_file} is imported by {closure[module]} but {DOCKERFILE_NAME} copies it to "
                f"{actual} instead of {expected}, where Python cannot import it."
            )

    for probe in FORBIDDEN_IMAGE_PROBES:
        shipped_at = manifest.image_path(probe)
        if shipped_at is not None:
            errors.append(
                f"{probe} would be copied into the Community image at {shipped_at}. "
                f"Exclude it in {DOCKERFILE_NAME}.dockerignore or narrow the COPY instruction."
            )

    return errors


def read_dockerignore(repo_root: Path) -> str:
    """BuildKit prefers ``<Dockerfile>.dockerignore`` over the root ``.dockerignore``."""
    for name in (f"{DOCKERFILE_NAME}.dockerignore", ".dockerignore"):
        path = repo_root / name
        if path.is_file():
            return path.read_text(encoding="utf-8")
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--list",
        action="store_true",
        help="print the first-party modules the image must ship and where they land",
    )
    args = parser.parse_args()

    try:
        errors = find_errors()
        if args.list:
            manifest = ImageManifest(
                (REPO_ROOT / DOCKERFILE_NAME).read_text(encoding="utf-8"),
                read_dockerignore(REPO_ROOT),
            )
            for module, importer in sorted(first_party_import_closure(REPO_ROOT).items()):
                module_file = _module_file(REPO_ROOT, module)
                print(f"{module_file} (imported by {importer}) -> {manifest.image_path(module_file)}")
    except ImageCheckError as error:
        print(f"Community image module check could not run: {error}")
        return 1

    if errors:
        print("Community image module check failed:\n")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Community image module check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
