#!/usr/bin/env python3
import argparse
from pathlib import Path

from portfolio_fit.tuning import (
    apply_suggested_scores_to_config,
    load_labels,
    load_results,
    save_tuning_report,
    suggest_criterion_max_scores,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Suggest scoring weight updates from expert-labeled golden set."
    )
    parser.add_argument(
        "--labels",
        type=str,
        required=True,
        help="Path to golden set CSV with repo,expert_score",
    )
    parser.add_argument(
        "--results",
        type=str,
        required=True,
        help="Path to portfolio_evaluation_*.json",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="calibration/scoring_config_patch.json",
        help="Output path for tuning report JSON",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=8,
        help="Minimum repository samples per criterion for correlation",
    )
    parser.add_argument(
        "--apply-config",
        type=str,
        default="",
        help="Optional path to scoring_config.json to apply suggested scores",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    labels = load_labels(Path(args.labels))
    results = load_results(Path(args.results))

    report = suggest_criterion_max_scores(
        labels=labels, results_map=results, min_samples=max(2, args.min_samples)
    )
    output_path = Path(args.output)
    save_tuning_report(report, output_path)

    print(f"Tuning report saved: {output_path}")
    print(
        f"Sample size: {report['sample_size']} | "
        f"median spearman: {report['median_spearman_used']}"
    )

    top_changes = report.get("criterion_stats", [])[:5]
    if top_changes:
        print("Top suggested max-score changes:")
        for row in top_changes:
            print(
                f"  - {row['criterion']}: {row['old_max']} -> {row['suggested_max']} "
                f"(delta {row['delta_max']}, spearman={row['spearman']})"
            )

    if args.apply_config:
        updated = apply_suggested_scores_to_config(
            report["suggested_criterion_max_scores"], Path(args.apply_config)
        )
        print(
            f"Applied suggested scores to {args.apply_config} "
            f"({len(updated.get('CRITERION_MAX_SCORES', {}))} criteria in config)"
        )


if __name__ == "__main__":
    main()
