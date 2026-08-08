#!/usr/bin/env python3
"""Validate delivery contracts for staged changes, pull requests, or the whole repo."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from scripts.delivery_contracts import (
        classify_changed_paths,
        changed_contract_paths,
        changed_files_for_pr,
        changed_files_for_staged,
        load_config,
        load_contracts,
        validate_config,
        validate_contract_set,
        validate_current_contract_against_paths,
    )
except ImportError:  # pragma: no cover - CLI fallback when run as a script
    from delivery_contracts import (
        classify_changed_paths,
        changed_contract_paths,
        changed_files_for_pr,
        changed_files_for_staged,
        load_config,
        load_contracts,
        validate_config,
        validate_contract_set,
        validate_current_contract_against_paths,
    )


def current_contracts(paths: list[Path]) -> list[str]:
    contracts = [contract for contract in load_contracts() if contract.path in paths]
    return [contract.contract_id for contract in contracts if not contract.is_backfill]


def contract_map() -> dict[Path, object]:
    return {contract.path: contract for contract in load_contracts()}


def validate_repo() -> list[str]:
    config = load_config()
    errors = [*validate_config(config), *validate_contract_set(load_contracts())]
    if not load_contracts():
        errors.append("delivery-contract: no contracts found under .delivery/changes")
    return errors


def validate_changed_paths(paths: list[str]) -> list[str]:
    contracts_by_path = contract_map()
    contract_paths = changed_contract_paths(paths)
    changed_non_contract = [path for path in paths if not path.startswith(".delivery/changes/")]

    current = [contracts_by_path[path] for path in contract_paths if path in contracts_by_path and not contracts_by_path[path].is_backfill]

    errors: list[str] = []
    if changed_non_contract and not current:
        errors.append(
            "delivery-contract: changed files require exactly one current delivery contract, but none was updated in .delivery/changes/"
        )

    if changed_non_contract and len(current) != 1:
        errors.append(
            "delivery-contract: keep one current delivery contract per PR; additional backfill contracts may set tracked_commit, but current changes must map to exactly one contract"
        )

    if not current:
        return errors

    classification = classify_changed_paths(changed_non_contract)
    contract = current[0]
    errors.extend(validate_current_contract_against_paths(contract, classification))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Decision Records delivery contracts.")
    parser.add_argument(
        "--mode",
        choices=("staged", "pr", "repo"),
        default="staged",
        help="staged validates the index, pr validates a git diff range, repo validates the full contract set.",
    )
    parser.add_argument("--base-ref", help="Base ref for --mode pr, for example refs/remotes/origin/main")
    parser.add_argument("--head-ref", default="HEAD", help="Head ref for --mode pr (default: HEAD)")
    args = parser.parse_args()

    errors = validate_repo()

    if args.mode == "staged":
        changed_paths = changed_files_for_staged()
        errors.extend(validate_changed_paths(changed_paths))
        if changed_paths:
            print(f"delivery-contract: validated staged changes across {len(changed_paths)} path(s)")
    elif args.mode == "pr":
        if not args.base_ref:
            print("delivery-contract: --base-ref is required in pr mode", file=sys.stderr)
            return 1
        changed_paths = changed_files_for_pr(args.base_ref, args.head_ref)
        errors.extend(validate_changed_paths(changed_paths))
        print(
            f"delivery-contract: validated PR diff {args.base_ref}...{args.head_ref} across {len(changed_paths)} path(s)"
        )
    else:
        print(f"delivery-contract: validated {len(load_contracts())} contract file(s)")

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    changed_contract_ids = current_contracts(changed_contract_paths(changed_files_for_staged())) if args.mode == "staged" else []
    if changed_contract_ids:
        print("delivery-contract: current contract(s): " + ", ".join(f"`{contract_id}`" for contract_id in changed_contract_ids))
    return 0


if __name__ == "__main__":
    sys.exit(main())
