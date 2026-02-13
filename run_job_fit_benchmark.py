#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from portfolio_fit.job_fit_benchmark import (
    load_jd_files,
    run_job_fit_benchmark,
    save_job_fit_benchmark,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run portfolio-to-job-fit benchmark on multiple JD files."
    )
    parser.add_argument(
        "--evaluation-json",
        type=str,
        required=True,
        help="Path to portfolio_evaluation_*.json",
    )
    parser.add_argument(
        "--jd-dir",
        type=str,
        required=True,
        help="Directory with JD *.txt files",
    )
    parser.add_argument(
        "--output-prefix",
        type=str,
        default="job_fit_benchmark",
        help="Output prefix for benchmark JSON/TXT",
    )
    return parser.parse_args()


def load_evaluation(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"evaluation json not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("evaluation json must contain list[dict]")
    return [item for item in data if isinstance(item, dict)]


def main() -> None:
    args = parse_arguments()
    evaluation_results = load_evaluation(Path(args.evaluation_json))
    jd_map = load_jd_files(Path(args.jd_dir))

    benchmark = run_job_fit_benchmark(evaluation_results, jd_map)
    json_path, txt_path = save_job_fit_benchmark(benchmark, args.output_prefix)

    print(f"Job fit benchmark JSON saved to {json_path}")
    print(f"Job fit benchmark TXT saved to {txt_path}")
    print(
        "Summary: "
        f"jds={benchmark['jd_count']} | "
        f"avg_fit={benchmark['avg_fit_score_percent']}% | "
        f"avg_must={benchmark['avg_must_have_coverage_percent']}% | "
        f"avg_nice={benchmark['avg_nice_to_have_coverage_percent']}%"
    )


if __name__ == "__main__":
    main()
