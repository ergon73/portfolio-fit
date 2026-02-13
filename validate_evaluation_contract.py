#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from portfolio_fit.schema_contract import validate_results_contract


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate portfolio_evaluation JSON against project contract."
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Path to portfolio_evaluation_*.json",
    )
    parser.add_argument(
        "--errors-output",
        type=str,
        default="",
        help="Optional path to save validation errors as text file.",
    )
    return parser.parse_args()


def load_results(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"input file not found: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("expected top-level JSON array")
    return [item for item in raw if isinstance(item, dict)]


def main() -> None:
    args = parse_arguments()
    input_path = Path(args.input)
    results = load_results(input_path)
    errors = validate_results_contract(results)

    if errors:
        print(f"Contract validation failed: {len(errors)} issue(s)")
        for issue in errors[:25]:
            print(f"  - {issue}")
        if len(errors) > 25:
            print(f"  ... and {len(errors) - 25} more")

        if args.errors_output:
            output_path = Path(args.errors_output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text("\n".join(errors) + "\n", encoding="utf-8")
            print(f"Saved issues to: {output_path}")
        raise SystemExit(1)

    print(f"Contract validation passed: {input_path}")


if __name__ == "__main__":
    main()
