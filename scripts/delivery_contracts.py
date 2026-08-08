#!/usr/bin/env python3
"""Shared helpers for delivery contracts and obligation tracking."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import fnmatch
import json
import os
from pathlib import Path
import re
import subprocess
import tomllib
from typing import Any
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request


REPO_ROOT = Path(__file__).resolve().parents[1]
DELIVERY_ROOT = REPO_ROOT / ".delivery"
CONTRACTS_ROOT = DELIVERY_ROOT / "changes"
CONFIG_FILE = DELIVERY_ROOT / "config.toml"
RELEASE_TAG_PATTERN = "v*.*.*"

ALLOWED_CHANGE_TYPES = {"security_fix", "bugfix", "feature", "docs", "ops"}
ALLOWED_SURFACES = {"shared_core", "enterprise_only", "marketing_only", "ops_docs_only"}
ALLOWED_ARTIFACT_STATES = {"required", "candidate", "none"}
ALLOWED_RELEASE_LEVELS = {"patch", "minor", "major", "none"}
SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")

SHARED_CORE_PATTERNS = (
    "app.py",
    "auth.py",
    "crypto.py",
    "feature_flags.py",
    "governance.py",
    "migrations.py",
    "models.py",
    "notifications.py",
    "requirements.txt",
    "run_local.py",
    "security.py",
    "version.py",
    "webauthn_auth.py",
    "Dockerfile.community",
    "docker-compose.yml",
    "frontend/**",
    "static/**",
    "templates/**",
)

PRIVATE_BOUNDARY_PATTERNS = (
    "ee",
    "ee/**",
)

OPS_DOC_PATTERNS = (
    ".delivery/**",
    ".github/**",
    ".githooks/**",
    "AGENTS.md",
    "CHANGELOG.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "README.md",
    "SECURITY.md",
    "docs/**",
    "e2e/**",
    "scripts/**",
    "tests/**",
)


@dataclass(frozen=True)
class ArtifactDecision:
    enterprise_app: str
    community_release: str
    community_release_level: str
    marketing_website: str


@dataclass(frozen=True)
class DeliveryContract:
    path: Path
    contract_id: str
    title: str
    summary: str
    change_type: str
    surfaces: tuple[str, ...]
    artifacts: ArtifactDecision
    tracked_commit: str | None = None
    marketing_target_sha: str | None = None

    @property
    def is_backfill(self) -> bool:
        return self.tracked_commit is not None


@dataclass(frozen=True)
class ArtifactConfig:
    repo: str
    local_path: str | None = None
    workflow: str | None = None
    tag_pattern: str | None = None


@dataclass(frozen=True)
class DeliveryConfig:
    schema_version: int
    enterprise_app: ArtifactConfig
    community_release: ArtifactConfig
    marketing_website: ArtifactConfig


@dataclass(frozen=True)
class PathClassification:
    shared_core: tuple[str, ...]
    private_boundary: tuple[str, ...]
    ops_docs: tuple[str, ...]
    unclassified: tuple[str, ...]

    @property
    def non_contract_changes(self) -> tuple[str, ...]:
        return (*self.shared_core, *self.private_boundary, *self.ops_docs, *self.unclassified)


@dataclass(frozen=True)
class ReferencePoint:
    name: str
    commit_sha: str
    url: str | None = None
    created_at: str | None = None


@dataclass(frozen=True)
class ArtifactStatus:
    artifact: str
    requirement: str
    state: str
    detail: str
    resolved_by: ReferencePoint | None = None


@dataclass(frozen=True)
class ContractStatus:
    contract: DeliveryContract
    anchor_commit: str
    artifact_statuses: tuple[ArtifactStatus, ...]

    @property
    def has_open_required(self) -> bool:
        return any(status.requirement == "required" and status.state != "resolved" for status in self.artifact_statuses)

    @property
    def has_open_candidate(self) -> bool:
        return any(status.requirement == "candidate" and status.state != "resolved" for status in self.artifact_statuses)

    @property
    def has_unknown(self) -> bool:
        return any(status.state == "unknown" for status in self.artifact_statuses)


@dataclass(frozen=True)
class WorkflowRun:
    repo: str
    workflow: str
    head_sha: str
    url: str
    created_at: str


def contract_relpath(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def path_matches(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def parse_contract(path: Path) -> DeliveryContract:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))

    artifacts = raw.get("artifacts", {})
    targets = raw.get("targets", {})
    summary = raw.get("summary", "").strip()

    return DeliveryContract(
        path=path,
        contract_id=str(raw.get("id", "")).strip(),
        title=str(raw.get("title", "")).strip(),
        summary=summary,
        change_type=str(raw.get("change_type", "")).strip(),
        surfaces=tuple(str(surface).strip() for surface in raw.get("surfaces", [])),
        artifacts=ArtifactDecision(
            enterprise_app=str(artifacts.get("enterprise_app", "")).strip(),
            community_release=str(artifacts.get("community_release", "")).strip(),
            community_release_level=str(artifacts.get("community_release_level", "")).strip(),
            marketing_website=str(artifacts.get("marketing_website", "")).strip(),
        ),
        tracked_commit=str(raw.get("tracked_commit", "")).strip() or None,
        marketing_target_sha=str(targets.get("marketing_target_sha", "")).strip() or None,
    )


def load_contracts(contracts_root: Path = CONTRACTS_ROOT) -> list[DeliveryContract]:
    if not contracts_root.exists():
        return []
    return [parse_contract(path) for path in sorted(contracts_root.glob("*.toml"))]


def load_config(config_file: Path = CONFIG_FILE) -> DeliveryConfig:
    raw = tomllib.loads(config_file.read_text(encoding="utf-8"))
    artifacts = raw["artifacts"]

    def parse_artifact(name: str) -> ArtifactConfig:
        entry = artifacts[name]
        return ArtifactConfig(
            repo=str(entry.get("repo", "")).strip(),
            local_path=str(entry.get("local_path", "")).strip() or None,
            workflow=str(entry.get("workflow", "")).strip() or None,
            tag_pattern=str(entry.get("tag_pattern", "")).strip() or None,
        )

    return DeliveryConfig(
        schema_version=int(raw.get("schema_version", 0)),
        enterprise_app=parse_artifact("enterprise_app"),
        community_release=parse_artifact("community_release"),
        marketing_website=parse_artifact("marketing_website"),
    )


def validate_config(config: DeliveryConfig) -> list[str]:
    errors: list[str] = []

    if config.schema_version != 1:
        errors.append(f"{CONFIG_FILE} schema_version must be 1")

    if not config.enterprise_app.repo or not config.enterprise_app.workflow:
        errors.append("enterprise_app config must declare repo and workflow")

    if not config.community_release.repo or not config.community_release.tag_pattern:
        errors.append("community_release config must declare repo and tag_pattern")

    if not config.marketing_website.repo or not config.marketing_website.workflow:
        errors.append("marketing_website config must declare repo and workflow")

    return errors


def validate_contract_schema(contract: DeliveryContract) -> list[str]:
    errors: list[str] = []

    if contract.path.stem != contract.contract_id:
        errors.append(
            f"{contract_relpath(contract.path)} id '{contract.contract_id}' must match filename stem '{contract.path.stem}'"
        )

    if not contract.contract_id:
        errors.append(f"{contract_relpath(contract.path)} is missing id")

    if not contract.title:
        errors.append(f"{contract_relpath(contract.path)} is missing title")

    if not contract.summary:
        errors.append(f"{contract_relpath(contract.path)} is missing summary")

    if contract.change_type not in ALLOWED_CHANGE_TYPES:
        errors.append(
            f"{contract_relpath(contract.path)} change_type '{contract.change_type}' must be one of {sorted(ALLOWED_CHANGE_TYPES)}"
        )

    if not contract.surfaces:
        errors.append(f"{contract_relpath(contract.path)} must declare at least one surface")

    unknown_surfaces = sorted(set(contract.surfaces) - ALLOWED_SURFACES)
    if unknown_surfaces:
        errors.append(
            f"{contract_relpath(contract.path)} uses unknown surfaces {unknown_surfaces}; expected subset of {sorted(ALLOWED_SURFACES)}"
        )

    if len(set(contract.surfaces)) != len(contract.surfaces):
        errors.append(f"{contract_relpath(contract.path)} repeats surfaces; keep each surface only once")

    if contract.artifacts.enterprise_app not in ALLOWED_ARTIFACT_STATES:
        errors.append(
            f"{contract_relpath(contract.path)} artifacts.enterprise_app must be one of {sorted(ALLOWED_ARTIFACT_STATES)}"
        )

    if contract.artifacts.community_release not in ALLOWED_ARTIFACT_STATES:
        errors.append(
            f"{contract_relpath(contract.path)} artifacts.community_release must be one of {sorted(ALLOWED_ARTIFACT_STATES)}"
        )

    if contract.artifacts.marketing_website not in ALLOWED_ARTIFACT_STATES:
        errors.append(
            f"{contract_relpath(contract.path)} artifacts.marketing_website must be one of {sorted(ALLOWED_ARTIFACT_STATES)}"
        )

    if contract.artifacts.community_release_level not in ALLOWED_RELEASE_LEVELS:
        errors.append(
            f"{contract_relpath(contract.path)} artifacts.community_release_level must be one of {sorted(ALLOWED_RELEASE_LEVELS)}"
        )

    if contract.artifacts.community_release == "none" and contract.artifacts.community_release_level != "none":
        errors.append(
            f"{contract_relpath(contract.path)} sets community_release_level to {contract.artifacts.community_release_level}, but community_release is none"
        )

    if contract.artifacts.community_release != "none" and contract.artifacts.community_release_level == "none":
        errors.append(
            f"{contract_relpath(contract.path)} must set community_release_level when community_release is {contract.artifacts.community_release}"
        )

    if contract.tracked_commit and not SHA_RE.match(contract.tracked_commit):
        errors.append(f"{contract_relpath(contract.path)} tracked_commit '{contract.tracked_commit}' is not a valid SHA")

    if contract.marketing_target_sha and not SHA_RE.match(contract.marketing_target_sha):
        errors.append(
            f"{contract_relpath(contract.path)} targets.marketing_target_sha '{contract.marketing_target_sha}' is not a valid SHA"
        )

    return errors


def validate_contract_rules(contract: DeliveryContract) -> list[str]:
    errors: list[str] = []
    surfaces = set(contract.surfaces)

    if "shared_core" in surfaces:
        if contract.artifacts.enterprise_app != "required":
            errors.append(
                f"{contract_relpath(contract.path)} declares shared_core, so artifacts.enterprise_app must be required"
            )
        if contract.artifacts.community_release == "none":
            errors.append(
                f"{contract_relpath(contract.path)} declares shared_core, so artifacts.community_release cannot be none"
            )

    if "enterprise_only" in surfaces:
        if contract.artifacts.enterprise_app != "required":
            errors.append(
                f"{contract_relpath(contract.path)} declares enterprise_only, so artifacts.enterprise_app must be required"
            )
        if contract.artifacts.community_release != "none":
            errors.append(
                f"{contract_relpath(contract.path)} declares enterprise_only, so artifacts.community_release must be none"
            )

    if "marketing_only" in surfaces:
        if contract.artifacts.marketing_website != "required":
            errors.append(
                f"{contract_relpath(contract.path)} declares marketing_only, so artifacts.marketing_website must be required"
            )
        if contract.artifacts.community_release != "none":
            errors.append(
                f"{contract_relpath(contract.path)} declares marketing_only, so artifacts.community_release must be none"
            )
        if not contract.marketing_target_sha:
            errors.append(
                f"{contract_relpath(contract.path)} declares marketing_only, so targets.marketing_target_sha is required"
            )

    if surfaces == {"ops_docs_only"}:
        if (
            contract.artifacts.enterprise_app != "none"
            or contract.artifacts.community_release != "none"
            or contract.artifacts.marketing_website != "none"
        ):
            errors.append(
                f"{contract_relpath(contract.path)} declares ops_docs_only, so all artifact obligations must be none"
            )

    if contract.change_type == "security_fix" and "shared_core" in surfaces:
        if contract.artifacts.community_release != "required":
            errors.append(
                f"{contract_relpath(contract.path)} is a shared_core security_fix, so artifacts.community_release must be required"
            )
        if contract.artifacts.community_release_level not in {"patch", "minor", "major"}:
            errors.append(
                f"{contract_relpath(contract.path)} is a shared_core security_fix, so community_release_level must be patch, minor, or major"
            )

    if contract.change_type == "security_fix" and "enterprise_only" in surfaces and contract.artifacts.enterprise_app != "required":
        errors.append(
            f"{contract_relpath(contract.path)} is an enterprise_only security_fix, so artifacts.enterprise_app must be required"
        )

    if contract.change_type == "security_fix" and "marketing_only" in surfaces and contract.artifacts.marketing_website != "required":
        errors.append(
            f"{contract_relpath(contract.path)} is a marketing_only security_fix, so artifacts.marketing_website must be required"
        )

    return errors


def validate_contract_set(contracts: list[DeliveryContract]) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()

    for contract in contracts:
        errors.extend(validate_contract_schema(contract))
        errors.extend(validate_contract_rules(contract))

        if contract.contract_id in seen_ids:
            errors.append(f"duplicate delivery contract id '{contract.contract_id}'")
        seen_ids.add(contract.contract_id)

    return errors


def classify_changed_paths(paths: list[str]) -> PathClassification:
    shared_core: list[str] = []
    private_boundary: list[str] = []
    ops_docs: list[str] = []
    unclassified: list[str] = []

    for path in paths:
        if path_matches(path, (".delivery/**",)):
            continue
        if path_matches(path, SHARED_CORE_PATTERNS):
            shared_core.append(path)
            continue
        if path_matches(path, PRIVATE_BOUNDARY_PATTERNS):
            private_boundary.append(path)
            continue
        if path_matches(path, OPS_DOC_PATTERNS):
            ops_docs.append(path)
            continue
        unclassified.append(path)

    return PathClassification(
        shared_core=tuple(shared_core),
        private_boundary=tuple(private_boundary),
        ops_docs=tuple(ops_docs),
        unclassified=tuple(unclassified),
    )


def validate_current_contract_against_paths(contract: DeliveryContract, classification: PathClassification) -> list[str]:
    errors: list[str] = []
    surfaces = set(contract.surfaces)

    if classification.unclassified:
        errors.append(
            "delivery-contract: unclassified changed paths detected; update scripts/delivery_contracts.py path patterns first:\n"
            + "\n".join(f"  - {path}" for path in classification.unclassified)
        )

    if classification.shared_core and "shared_core" not in surfaces:
        errors.append(
            f"{contract_relpath(contract.path)} must declare shared_core because these paths changed:\n"
            + "\n".join(f"  - {path}" for path in classification.shared_core)
        )

    if classification.private_boundary and not ({"enterprise_only", "marketing_only"} & surfaces):
        errors.append(
            f"{contract_relpath(contract.path)} must declare enterprise_only or marketing_only because these private-boundary paths changed:\n"
            + "\n".join(f"  - {path}" for path in classification.private_boundary)
        )

    if classification.ops_docs and not (surfaces & {"shared_core", "enterprise_only", "marketing_only", "ops_docs_only"}):
        errors.append(
            f"{contract_relpath(contract.path)} must declare at least one known surface for these ops/docs paths:\n"
            + "\n".join(f"  - {path}" for path in classification.ops_docs)
        )

    if not classification.shared_core and not classification.private_boundary and classification.ops_docs:
        if surfaces != {"ops_docs_only"}:
            errors.append(
                f"{contract_relpath(contract.path)} only changes ops/docs paths, so surfaces should be exactly ['ops_docs_only']"
            )

    return errors


def git_result(args: list[str], cwd: Path = REPO_ROOT, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    process_env = os.environ.copy()
    if env:
        process_env.update(env)
    return subprocess.run(
        args,
        cwd=cwd,
        env=process_env,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def git_output(args: list[str], cwd: Path = REPO_ROOT) -> str:
    result = git_result(args, cwd=cwd)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise RuntimeError(message)
    return result.stdout.strip()


def changed_files_for_pr(base_ref: str, head_ref: str) -> list[str]:
    output = git_output(["git", "diff", "--name-only", "--diff-filter=ACMR", f"{base_ref}...{head_ref}"])
    return [path for path in output.splitlines() if path]


def changed_files_for_staged() -> list[str]:
    output = git_output(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"])
    return [path for path in output.splitlines() if path]


def changed_contract_paths(paths: list[str]) -> list[Path]:
    return [REPO_ROOT / path for path in paths if path.startswith(".delivery/changes/") and path.endswith(".toml")]


def introduced_commit(path: Path, repo_root: Path = REPO_ROOT) -> str:
    relative = path.relative_to(repo_root).as_posix()
    output = git_output(["git", "log", "--diff-filter=A", "--format=%H", "--reverse", "--", relative], cwd=repo_root)
    commits = [line for line in output.splitlines() if line]
    if not commits:
        raise RuntimeError(f"Could not determine introduced commit for {relative}")
    return commits[0]


def is_ancestor(ancestor_sha: str, descendant_sha: str, repo_root: Path = REPO_ROOT) -> bool:
    result = git_result(["git", "merge-base", "--is-ancestor", ancestor_sha, descendant_sha], cwd=repo_root)
    return result.returncode == 0


def list_release_tags(repo_root: Path = REPO_ROOT, pattern: str = RELEASE_TAG_PATTERN) -> list[ReferencePoint]:
    output = git_output(
        [
            "git",
            "for-each-ref",
            "--sort=creatordate",
            "--format=%(refname:short)\t%(objectname)\t%(creatordate:iso8601-strict)",
            f"refs/tags/{pattern}",
        ],
        cwd=repo_root,
    )
    tags: list[ReferencePoint] = []
    for line in output.splitlines():
        name, commit_sha, created_at = line.split("\t", 2)
        tags.append(ReferencePoint(name=name, commit_sha=commit_sha, created_at=created_at))
    return tags


def first_descendant_reference(
    target_sha: str,
    references: list[ReferencePoint],
    repo_root: Path,
) -> ReferencePoint | None:
    for reference in references:
        if is_ancestor(target_sha, reference.commit_sha, repo_root=repo_root):
            return reference
    return None


def github_headers(token: str | None) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "decisionrecords-delivery-obligations",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def github_json(url: str, token: str | None) -> dict[str, Any]:
    request = urllib_request.Request(url, headers=github_headers(token))
    try:
        with urllib_request.urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib_error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API request failed ({error.code}) for {url}: {body}") from error


def list_successful_workflow_runs(repo: str, workflow: str, token: str | None) -> list[WorkflowRun]:
    encoded_workflow = urllib_parse.quote(workflow, safe="")
    runs: list[WorkflowRun] = []
    page = 1

    while True:
        url = (
            f"https://api.github.com/repos/{repo}/actions/workflows/{encoded_workflow}/runs"
            f"?branch=main&status=success&per_page=100&page={page}"
        )
        try:
            payload = github_json(url, token)
        except RuntimeError as error:
            if token is None and ("(404)" in str(error) or "(403)" in str(error)):
                return []
            raise
        workflow_runs = payload.get("workflow_runs", [])
        for run in workflow_runs:
            runs.append(
                WorkflowRun(
                    repo=repo,
                    workflow=workflow,
                    head_sha=run["head_sha"],
                    url=run["html_url"],
                    created_at=run["created_at"],
                )
            )
        if len(workflow_runs) < 100:
            break
        page += 1

    return runs


def resolve_required_status(
    artifact: str,
    target_sha: str,
    references: list[ReferencePoint],
    repo_root: Path,
    requirement: str = "required",
) -> ArtifactStatus:
    resolved_by = first_descendant_reference(target_sha, references, repo_root=repo_root)
    if resolved_by:
        return ArtifactStatus(
            artifact=artifact,
            requirement=requirement,
            state="resolved",
            detail=f"resolved by {resolved_by.name}",
            resolved_by=resolved_by,
        )
    return ArtifactStatus(
        artifact=artifact,
        requirement=requirement,
        state="open",
        detail="waiting for a descendant ref",
        resolved_by=None,
    )


def resolve_workflow_requirement(
    artifact: str,
    target_sha: str,
    runs: list[WorkflowRun],
    repo_root: Path,
    requirement: str = "required",
) -> ArtifactStatus:
    references = [
        ReferencePoint(
            name=f"{artifact} deploy @ {run.head_sha[:7]}",
            commit_sha=run.head_sha,
            url=run.url,
            created_at=run.created_at,
        )
        for run in runs
    ]
    if not references:
        return ArtifactStatus(
            artifact=artifact,
            requirement=requirement,
            state="unknown",
            detail="no successful workflow runs were available to evaluate",
            resolved_by=None,
        )
    return resolve_required_status(artifact, target_sha, references, repo_root=repo_root, requirement=requirement)


def contract_anchor_commit(contract: DeliveryContract) -> str:
    if contract.tracked_commit:
        return contract.tracked_commit
    try:
        return introduced_commit(contract.path)
    except RuntimeError:
        return git_output(["git", "rev-parse", "HEAD"])


def contract_to_json(contract: DeliveryContract) -> dict[str, Any]:
    return {
        "path": contract_relpath(contract.path),
        "id": contract.contract_id,
        "title": contract.title,
        "summary": contract.summary,
        "change_type": contract.change_type,
        "surfaces": list(contract.surfaces),
        "tracked_commit": contract.tracked_commit,
        "marketing_target_sha": contract.marketing_target_sha,
        "artifacts": asdict(contract.artifacts),
    }


def status_to_json(status: ContractStatus) -> dict[str, Any]:
    return {
        "contract": contract_to_json(status.contract),
        "anchor_commit": status.anchor_commit,
        "artifacts": [
            {
                "artifact": artifact.artifact,
                "requirement": artifact.requirement,
                "state": artifact.state,
                "detail": artifact.detail,
                "resolved_by": None
                if artifact.resolved_by is None
                else {
                    "name": artifact.resolved_by.name,
                    "commit_sha": artifact.resolved_by.commit_sha,
                    "url": artifact.resolved_by.url,
                    "created_at": artifact.resolved_by.created_at,
                },
            }
            for artifact in status.artifact_statuses
        ],
    }


def gather_contract_statuses(
    contracts: list[DeliveryContract],
    config: DeliveryConfig,
    *,
    github_token: str | None = None,
) -> list[ContractStatus]:
    public_repo_root = REPO_ROOT
    marketing_repo_root = REPO_ROOT / config.marketing_website.local_path if config.marketing_website.local_path else None

    release_tags = list_release_tags(public_repo_root, pattern=config.community_release.tag_pattern or RELEASE_TAG_PATTERN)
    enterprise_runs = list_successful_workflow_runs(
        config.enterprise_app.repo,
        config.enterprise_app.workflow or "",
        github_token,
    )
    marketing_runs = list_successful_workflow_runs(
        config.marketing_website.repo,
        config.marketing_website.workflow or "",
        github_token,
    )

    statuses: list[ContractStatus] = []
    for contract in contracts:
        anchor_commit = contract_anchor_commit(contract)
        artifact_statuses: list[ArtifactStatus] = []

        if contract.artifacts.enterprise_app == "required":
            artifact_statuses.append(
                resolve_workflow_requirement(
                    "enterprise_app",
                    anchor_commit,
                    enterprise_runs,
                    public_repo_root,
                    requirement="required",
                )
            )
        else:
            artifact_statuses.append(
                ArtifactStatus(
                    artifact="enterprise_app",
                    requirement=contract.artifacts.enterprise_app,
                    state="not_required",
                    detail="no enterprise deployment obligation",
                )
            )

        if contract.artifacts.community_release in {"required", "candidate"}:
            artifact_statuses.append(
                resolve_required_status(
                    "community_release",
                    anchor_commit,
                    release_tags,
                    public_repo_root,
                    requirement=contract.artifacts.community_release,
                )
            )
        else:
            artifact_statuses.append(
                ArtifactStatus(
                    artifact="community_release",
                    requirement=contract.artifacts.community_release,
                    state="not_required",
                    detail="no community release obligation",
                )
            )

        if contract.artifacts.marketing_website == "required":
            if not contract.marketing_target_sha:
                artifact_statuses.append(
                    ArtifactStatus(
                        artifact="marketing_website",
                        requirement="required",
                        state="unknown",
                        detail="marketing_target_sha is missing",
                    )
                )
            elif marketing_repo_root is None or not marketing_repo_root.exists():
                artifact_statuses.append(
                    ArtifactStatus(
                        artifact="marketing_website",
                        requirement="required",
                        state="unknown",
                        detail="marketing repo checkout is unavailable locally",
                    )
                )
            else:
                artifact_statuses.append(
                    resolve_workflow_requirement(
                        "marketing_website",
                        contract.marketing_target_sha,
                        marketing_runs,
                        marketing_repo_root,
                        requirement="required",
                    )
                )
        else:
            artifact_statuses.append(
                ArtifactStatus(
                    artifact="marketing_website",
                    requirement=contract.artifacts.marketing_website,
                    state="not_required",
                    detail="no marketing deployment obligation",
                )
            )

        statuses.append(
            ContractStatus(
                contract=contract,
                anchor_commit=anchor_commit,
                artifact_statuses=tuple(artifact_statuses),
            )
        )

    return statuses


def format_contract_statuses_markdown(statuses: list[ContractStatus], *, include_resolved: bool = False) -> str:
    visible_statuses = [
        status
        for status in statuses
        if include_resolved or status.has_open_required or status.has_open_candidate or status.has_unknown
    ]

    if not visible_statuses:
        return "## Delivery Obligations\n\nNo open delivery obligations.\n"

    lines = [
        "## Delivery Obligations",
        "",
        "| Contract | Type | Surfaces | Enterprise App | Community Release | Marketing Website |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    for status in visible_statuses:
        artifact_map = {artifact.artifact: artifact for artifact in status.artifact_statuses}

        def display(artifact_name: str) -> str:
            artifact = artifact_map[artifact_name]
            if artifact.state == "resolved" and artifact.resolved_by:
                return f"{artifact.requirement}: resolved by `{artifact.resolved_by.name}`"
            return f"{artifact.requirement}: {artifact.state}"

        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{status.contract.contract_id}`",
                    status.contract.change_type,
                    ", ".join(status.contract.surfaces),
                    display("enterprise_app"),
                    display("community_release")
                    + (
                        f" ({status.contract.artifacts.community_release_level})"
                        if status.contract.artifacts.community_release != "none"
                        else ""
                    ),
                    display("marketing_website"),
                ]
            )
            + " |"
        )

    return "\n".join(lines) + "\n"
