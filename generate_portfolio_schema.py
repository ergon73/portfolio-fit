#!/usr/bin/env python3
import argparse
from pathlib import Path

from portfolio_fit.schema_contract import save_portfolio_evaluation_schema


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate JSON schema for portfolio_evaluation_*.json results."
    )
    parser.add_argument(
        "--output",
        type=str,
        default="schemas/portfolio_evaluation.schema.json",
        help="Output path for generated schema JSON.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    output_path = save_portfolio_evaluation_schema(Path(args.output))
    print(f"Schema generated: {output_path}")


if __name__ == "__main__":
    main()
