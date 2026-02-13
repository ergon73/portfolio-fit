#!/usr/bin/env python3
import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from portfolio_fit.calibration import (
    build_calibration_report,
    load_expert_labels,
    load_model_scores,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calibrate portfolio score against expert-labeled golden set"
    )
    parser.add_argument(
        "--labels",
        type=str,
        required=True,
        help="Path to expert labels CSV (columns: repo, expert_score)",
    )
    parser.add_argument(
        "--results",
        type=str,
        required=True,
        help="Path to portfolio_evaluation_*.json file",
    )
    parser.add_argument(
        "--output-prefix",
        type=str,
        default="calibration_report",
        help="Output file prefix (default: calibration_report)",
    )
    return parser.parse_args()


def save_report(report: Dict[str, Any], output_prefix: str) -> None:
    json_path = Path(f"{output_prefix}.json")
    txt_path = Path(f"{output_prefix}.txt")

    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    metrics = report.get("metrics", {})
    warnings = report.get("warnings", [])
    with open(txt_path, "w", encoding="utf-8") as file:
        file.write("=" * 100 + "\n")
        file.write("SCORING CALIBRATION REPORT\n")
        file.write("=" * 100 + "\n\n")
        file.write(f"Generated: {datetime.now().isoformat(timespec='seconds')}\n")
        file.write(f"Labels source: {report.get('labels_source')}\n")
        file.write(f"Results source: {report.get('results_source')}\n")
        file.write(f"Sample size: {report.get('sample_size')}\n")
        file.write(f"Quality band: {report.get('quality_band')}\n\n")
        file.write("Metrics:\n")
        file.write(f"  Spearman: {metrics.get('spearman')}\n")
        file.write(f"  Pearson: {metrics.get('pearson')}\n")
        file.write(f"  MAE: {metrics.get('mae')}\n\n")

        if isinstance(warnings, list) and warnings:
            file.write("Warnings:\n")
            for warning in warnings:
                file.write(f"  - {warning}\n")
            file.write("\n")

        file.write("Top sample deltas:\n")
        pairs = report.get("pairs", [])
        if isinstance(pairs, list):
            sorted_pairs = sorted(
                [item for item in pairs if isinstance(item, dict)],
                key=lambda item: abs(float(item.get("delta", 0.0))),
                reverse=True,
            )
            for item in sorted_pairs[:20]:
                file.write(
                    f"  - {item.get('repo')}: expert={item.get('expert_score')} "
                    f"model={item.get('model_score')} delta={item.get('delta')}\n"
                )

    print(f"Calibration JSON saved to {json_path}")
    print(f"Calibration TXT saved to {txt_path}")


def main() -> None:
    args = parse_arguments()
    labels_path = Path(args.labels)
    results_path = Path(args.results)

    labels = load_expert_labels(labels_path)
    scores = load_model_scores(results_path)

    report = build_calibration_report(
        labels,
        scores,
        labels_source=str(labels_path),
        results_source=str(results_path),
    )
    save_report(report, args.output_prefix)

    metrics = report.get("metrics", {})
    print(
        "Summary: "
        f"sample={report.get('sample_size')} | "
        f"spearman={metrics.get('spearman')} | "
        f"pearson={metrics.get('pearson')} | "
        f"mae={metrics.get('mae')}"
    )


if __name__ == "__main__":
    main()
