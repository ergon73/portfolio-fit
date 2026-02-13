import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from portfolio_fit.job_fit import analyze_job_fit


def load_jd_files(jd_dir: Path) -> Dict[str, str]:
    if not jd_dir.exists() or not jd_dir.is_dir():
        raise FileNotFoundError(f"JD directory not found: {jd_dir}")

    jd_map: Dict[str, str] = {}
    for jd_file in sorted(jd_dir.glob("*.txt")):
        jd_map[jd_file.stem] = jd_file.read_text(encoding="utf-8", errors="ignore")
    if not jd_map:
        raise ValueError(f"No *.txt JD files found in {jd_dir}")
    return jd_map


def run_job_fit_benchmark(
    evaluation_results: List[Dict[str, Any]], jd_map: Dict[str, str]
) -> Dict[str, Any]:
    reports: List[Dict[str, Any]] = []

    for jd_name, jd_text in jd_map.items():
        report = analyze_job_fit(evaluation_results, jd_text)
        reports.append(
            {
                "jd_name": jd_name,
                "fit_score_percent": report["fit_score_percent"],
                "fit_category": report["fit_category"],
                "must_have_coverage_percent": report["must_have_coverage_percent"],
                "nice_to_have_coverage_percent": report[
                    "nice_to_have_coverage_percent"
                ],
                "missing_must_have": report["matching"]["must_have_missing"],
                "missing_nice_to_have": report["matching"]["nice_to_have_missing"],
                "gap_count": len(report["gaps"]),
                "roadmap": report["roadmap"],
            }
        )

    avg_fit = (
        sum(float(item["fit_score_percent"]) for item in reports) / len(reports)
        if reports
        else 0.0
    )
    avg_must = (
        sum(float(item["must_have_coverage_percent"]) for item in reports)
        / len(reports)
        if reports
        else 0.0
    )
    avg_nice = (
        sum(float(item["nice_to_have_coverage_percent"]) for item in reports)
        / len(reports)
        if reports
        else 0.0
    )

    reports_sorted = sorted(
        reports, key=lambda item: float(item["fit_score_percent"]), reverse=True
    )
    return {
        "jd_count": len(reports),
        "avg_fit_score_percent": round(avg_fit, 2),
        "avg_must_have_coverage_percent": round(avg_must, 2),
        "avg_nice_to_have_coverage_percent": round(avg_nice, 2),
        "best_fit": reports_sorted[0] if reports_sorted else None,
        "worst_fit": reports_sorted[-1] if reports_sorted else None,
        "reports": reports_sorted,
    }


def save_job_fit_benchmark(
    benchmark: Dict[str, Any], output_prefix: str
) -> Tuple[str, str]:
    json_path = f"{output_prefix}.json"
    txt_path = f"{output_prefix}.txt"

    with open(json_path, "w", encoding="utf-8") as file:
        json.dump(benchmark, file, indent=2, ensure_ascii=False)

    with open(txt_path, "w", encoding="utf-8") as file:
        file.write("=" * 100 + "\n")
        file.write("JOB FIT BENCHMARK REPORT\n")
        file.write("=" * 100 + "\n\n")
        file.write(f"JD count: {benchmark.get('jd_count')}\n")
        file.write(f"Average fit score: {benchmark.get('avg_fit_score_percent')}%\n")
        file.write(
            "Average must-have coverage: "
            f"{benchmark.get('avg_must_have_coverage_percent')}%\n"
        )
        file.write(
            "Average nice-to-have coverage: "
            f"{benchmark.get('avg_nice_to_have_coverage_percent')}%\n\n"
        )

        best = benchmark.get("best_fit")
        worst = benchmark.get("worst_fit")
        if isinstance(best, dict):
            file.write(
                f"Best fit: {best.get('jd_name')} ({best.get('fit_score_percent')}%)\n"
            )
        if isinstance(worst, dict):
            file.write(
                f"Worst fit: {worst.get('jd_name')} ({worst.get('fit_score_percent')}%)\n"
            )

        file.write("\nPer-JD summary:\n")
        for item in benchmark.get("reports", []):
            if not isinstance(item, dict):
                continue
            file.write(
                f"- {item.get('jd_name')}: fit={item.get('fit_score_percent')}% "
                f"(must={item.get('must_have_coverage_percent')}%, "
                f"nice={item.get('nice_to_have_coverage_percent')}%, "
                f"gaps={item.get('gap_count')})\n"
            )
            missing = item.get("missing_must_have", [])
            if missing:
                file.write(f"  missing must-have: {', '.join(missing)}\n")

    return json_path, txt_path
