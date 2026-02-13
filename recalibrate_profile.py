#!/usr/bin/env python3
import argparse
from pathlib import Path

from portfolio_fit.recalibration import (
    build_profile_paths,
    prepare_profile_labels,
    print_profile_summary,
    run_profile_recalibration,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Personal recalibration workflow. "
            "Creates per-user profile artifacts without touching baseline config by default."
        )
    )
    parser.add_argument(
        "--profile",
        type=str,
        required=True,
        help="Profile name (e.g. ivan-market-view, recruiter-view).",
    )
    parser.add_argument(
        "--results",
        type=str,
        required=True,
        help="Path to portfolio_evaluation_*.json",
    )
    parser.add_argument(
        "--workspace",
        type=str,
        default="calibration/profiles",
        help="Directory for per-profile recalibration artifacts.",
    )
    parser.add_argument(
        "--labels",
        type=str,
        default="",
        help=(
            "Optional path to labels CSV. "
            "Default: <workspace>/<profile>/labels/golden_set.csv"
        ),
    )
    parser.add_argument(
        "--prepare-golden-set",
        action="store_true",
        help="Bootstrap labels CSV for this profile from results JSON.",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=36,
        help="Golden set size for bootstrap generation.",
    )
    parser.add_argument(
        "--autofill",
        action="store_true",
        help="Prefill expert_score with provisional values for faster manual review.",
    )
    parser.add_argument(
        "--force-prepare",
        action="store_true",
        help="Overwrite existing profile labels CSV during bootstrap.",
    )
    parser.add_argument(
        "--only-prepare",
        action="store_true",
        help="Only generate labels CSV and exit.",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=8,
        help="Minimum samples per criterion for tuning correlations.",
    )
    parser.add_argument(
        "--base-config",
        type=str,
        default="portfolio_fit/scoring_config.json",
        help="Base config path used to build profile-specific config.",
    )
    parser.add_argument(
        "--apply-to",
        type=str,
        default="",
        help=(
            "Optional target config path to activate profile config "
            "(example: portfolio_fit/scoring_config.json)."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    results_path = Path(args.results)
    workspace_dir = Path(args.workspace)
    profile_paths = build_profile_paths(workspace_dir, args.profile)
    labels_path = Path(args.labels) if args.labels else profile_paths.labels_csv

    if args.prepare_golden_set:
        created = prepare_profile_labels(
            results_path=results_path,
            labels_csv_path=labels_path,
            sample_size=max(1, args.sample_size),
            autofill=args.autofill,
            force_overwrite=args.force_prepare,
        )
        if created:
            print(f"Profile labels prepared: {labels_path}")
        else:
            print(f"Profile labels already exist: {labels_path}")
            print("Use --force-prepare to overwrite.")

        if args.only_prepare:
            print("Preparation only mode complete.")
            return

    apply_to = Path(args.apply_to) if args.apply_to else None
    summary = run_profile_recalibration(
        profile_paths=profile_paths,
        results_path=results_path,
        labels_path=labels_path,
        min_samples=max(2, args.min_samples),
        base_config_path=Path(args.base_config),
        apply_to_config_path=apply_to,
    )

    print("Recalibration complete.")
    print(print_profile_summary(summary))
    print(f"Calibration report: {summary['calibration_json']}")
    print(f"Tuning patch: {summary['tuning_patch_json']}")
    print(f"Profile config: {summary['profile_config_json']}")
    print(f"Summary: {profile_paths.summary_json}")


if __name__ == "__main__":
    main()
