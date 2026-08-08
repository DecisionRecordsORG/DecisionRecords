#!/usr/bin/env python3
"""List open delivery obligations derived from contracts, tags, and deploy runs."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    from scripts.delivery_contracts import (
        format_contract_statuses_markdown,
        gather_contract_statuses,
        load_config,
        load_contracts,
        status_to_json,
        validate_config,
        validate_contract_set,
    )
except ImportError:  # pragma: no cover - CLI fallback when run as a script
    from delivery_contracts import (
        format_contract_statuses_markdown,
        gather_contract_statuses,
        load_config,
        load_contracts,
        status_to_json,
        validate_config,
        validate_contract_set,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="List open delivery obligations.")
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output format.",
    )
    parser.add_argument(
        "--include-resolved",
        action="store_true",
        help="Include fully resolved contracts in the output.",
    )
    parser.add_argument(
        "--json-output",
        help="Optional path to write the full JSON payload.",
    )
    parser.add_argument(
        "--write-summary",
        action="store_true",
        help="Write markdown output to $GITHUB_STEP_SUMMARY when available.",
    )
    args = parser.parse_args()

    config = load_config()
    errors = [*validate_config(config), *validate_contract_set(load_contracts())]
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    github_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    statuses = gather_contract_statuses(load_contracts(), config, github_token=github_token)
    payload = {
        "contracts": [status_to_json(status) for status in statuses],
    }

    if args.json_output:
        Path(args.json_output).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    markdown = format_contract_statuses_markdown(statuses, include_resolved=args.include_resolved)
    if args.write_summary and os.environ.get("GITHUB_STEP_SUMMARY"):
        Path(os.environ["GITHUB_STEP_SUMMARY"]).write_text(markdown, encoding="utf-8")

    if args.format == "json":
        print(json.dumps(payload, indent=2))
    else:
        print(markdown)

    return 0


if __name__ == "__main__":
    sys.exit(main())
