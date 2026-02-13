#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from portfolio_fit.job_fit import analyze_job_fit, save_job_fit_report


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze portfolio-to-job fit from evaluation JSON and job description."
    )
    parser.add_argument(
        "--evaluation-json",
        type=str,
        required=True,
        help="Path to portfolio_evaluation_*.json",
    )
    parser.add_argument(
        "--jd-file",
        type=str,
        required=True,
        help="Path to job description text file",
    )
    parser.add_argument(
        "--output-prefix",
        type=str,
        default="job_fit_report",
        help="Output prefix for JSON/TXT reports",
    )
    return parser.parse_args()


def load_evaluation(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"evaluation json not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("evaluation json must contain a list")
    return [item for item in data if isinstance(item, dict)]


def main() -> None:
    args = parse_arguments()
    evaluation_results = load_evaluation(Path(args.evaluation_json))
    jd_text = Path(args.jd_file).read_text(encoding="utf-8", errors="ignore")

    report = analyze_job_fit(evaluation_results, jd_text)
    json_path, txt_path = save_job_fit_report(report, args.output_prefix)

    print(f"Job fit JSON saved to {json_path}")
    print(f"Job fit TXT saved to {txt_path}")
    print(
        "Summary: "
        f"fit={report['fit_score_percent']}% ({report['fit_category']}) | "
        f"must={report['must_have_coverage_percent']}% | "
        f"nice={report['nice_to_have_coverage_percent']}%"
    )


if __name__ == "__main__":
    main()
