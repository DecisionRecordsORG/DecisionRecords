from pathlib import Path

import scripts.check_release_metadata as release_metadata


def test_read_version_accepts_current_version_file():
    version = release_metadata.read_version()

    assert release_metadata.SEMVER_RE.match(version)


def test_validate_changelog_rejects_stale_unreleased_link(tmp_path: Path):
    current_version = release_metadata.read_version()
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        f"""# Changelog

## [{current_version}] - 2026-03-03

[Unreleased]: https://github.com/DecisionRecordsORG/DecisionRecords/compare/v2.0.27...HEAD
""",
        encoding="utf-8",
    )

    errors = release_metadata.validate_changelog(current_version, changelog)

    assert errors == [
        f"{changelog} [Unreleased] compare link points to 2.0.27, expected {current_version}"
    ]


def test_validate_docs_rejects_stale_release_examples(tmp_path: Path, monkeypatch):
    current_version = release_metadata.read_version()
    repo_root = tmp_path / "repo"
    docs_root = repo_root / "docs"
    docs_root.mkdir(parents=True)

    (repo_root / "README.md").write_text(
        "For a pinned install, prefer a version tag such as `v2.0.27` once that release is published.\n",
        encoding="utf-8",
    )
    (docs_root / "configuration.md").write_text(
        '### Version Endpoint\n\n```json\n{"version": "2.0.27"}\n```\n',
        encoding="utf-8",
    )
    (docs_root / "self-hosting.md").write_text(
        """docker pull ghcr.io/decisionrecordsorg/decisionrecords:v2.0.27

If upgrading from a version before `v2.0.27`, start the new Community Edition image.
""",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        release_metadata,
        "DOC_VERSION_CHECKS",
        (
            (
                repo_root / "README.md",
                "README pinned release example",
                release_metadata.DOC_VERSION_CHECKS[0][2],
            ),
            (
                docs_root / "configuration.md",
                "configuration version endpoint example",
                release_metadata.DOC_VERSION_CHECKS[1][2],
            ),
            (
                docs_root / "self-hosting.md",
                "self-hosting pinned docker pull example",
                release_metadata.DOC_VERSION_CHECKS[2][2],
            ),
            (
                docs_root / "self-hosting.md",
                "self-hosting upgrade note",
                release_metadata.DOC_VERSION_CHECKS[3][2],
            ),
        ),
    )

    errors = release_metadata.validate_docs(current_version)

    assert errors == [
        f"README pinned release example in {repo_root / 'README.md'} uses 2.0.27, expected {current_version}",
        f"configuration version endpoint example in {docs_root / 'configuration.md'} uses 2.0.27, expected {current_version}",
        f"self-hosting pinned docker pull example in {docs_root / 'self-hosting.md'} uses 2.0.27, expected {current_version}",
        f"self-hosting upgrade note in {docs_root / 'self-hosting.md'} uses 2.0.27, expected {current_version}",
    ]
