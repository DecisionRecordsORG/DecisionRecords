from pathlib import Path

import scripts.delivery_contracts as delivery_contracts


def make_contract(
    *,
    contract_id: str = "2026-08-08-example",
    change_type: str = "bugfix",
    surfaces: tuple[str, ...] = ("shared_core",),
    enterprise_app: str = "required",
    community_release: str = "candidate",
    community_release_level: str = "patch",
    marketing_website: str = "none",
    tracked_commit: str | None = None,
    marketing_target_sha: str | None = None,
) -> delivery_contracts.DeliveryContract:
    return delivery_contracts.DeliveryContract(
        path=Path(f"/tmp/{contract_id}.toml"),
        contract_id=contract_id,
        title="Example contract",
        summary="Example summary",
        change_type=change_type,
        surfaces=surfaces,
        artifacts=delivery_contracts.ArtifactDecision(
            enterprise_app=enterprise_app,
            community_release=community_release,
            community_release_level=community_release_level,
            marketing_website=marketing_website,
        ),
        tracked_commit=tracked_commit,
        marketing_target_sha=marketing_target_sha,
    )


def test_classify_changed_paths_separates_shared_core_private_and_ops():
    classification = delivery_contracts.classify_changed_paths(
        ["app.py", "docs/deployment.md", "ee", ".delivery/changes/2026-08-08-example.toml"]
    )

    assert classification.shared_core == ("app.py",)
    assert classification.private_boundary == ("ee",)
    assert classification.ops_docs == ("docs/deployment.md",)
    assert classification.unclassified == ()


def test_validate_contract_rules_require_ce_release_for_shared_core_security_fix():
    contract = make_contract(
        change_type="security_fix",
        enterprise_app="required",
        community_release="none",
        community_release_level="none",
    )

    errors = delivery_contracts.validate_contract_rules(contract)

    assert any("artifacts.community_release cannot be none" in error for error in errors)
    assert any("shared_core security_fix" in error for error in errors)


def test_validate_current_contract_against_paths_requires_shared_core_surface():
    contract = make_contract(surfaces=("ops_docs_only",), enterprise_app="none", community_release="none", community_release_level="none")
    classification = delivery_contracts.classify_changed_paths(["security.py"])

    errors = delivery_contracts.validate_current_contract_against_paths(contract, classification)

    assert any("must declare shared_core" in error for error in errors)


def test_validate_contract_rules_require_marketing_target_sha():
    contract = make_contract(
        surfaces=("marketing_only",),
        enterprise_app="none",
        community_release="none",
        community_release_level="none",
        marketing_website="required",
    )

    errors = delivery_contracts.validate_contract_rules(contract)

    assert any("marketing_target_sha is required" in error for error in errors)


def test_validate_contract_set_rejects_duplicate_ids():
    first = make_contract(contract_id="2026-08-08-duplicate")
    second = make_contract(contract_id="2026-08-08-duplicate")

    errors = delivery_contracts.validate_contract_set([first, second])

    assert any("duplicate delivery contract id" in error for error in errors)


def test_resolve_required_status_marks_descendant_reference(monkeypatch):
    references = [
        delivery_contracts.ReferencePoint(name="v2.0.2", commit_sha="bbbbbbbb"),
        delivery_contracts.ReferencePoint(name="v2.0.3", commit_sha="cccccccc"),
    ]

    monkeypatch.setattr(
        delivery_contracts,
        "is_ancestor",
        lambda ancestor, descendant, repo_root: (ancestor, descendant) == ("aaaaaaaa", "bbbbbbbb"),
    )

    status = delivery_contracts.resolve_required_status(
        "community_release",
        "aaaaaaaa",
        references,
        repo_root=Path("/tmp"),
        requirement="required",
    )

    assert status.state == "resolved"
    assert status.resolved_by is not None
    assert status.resolved_by.name == "v2.0.2"
