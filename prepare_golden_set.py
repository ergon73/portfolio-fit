#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Set


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare a stratified golden-set CSV from portfolio evaluation JSON."
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
        default="calibration/golden_set.csv",
        help="Output CSV path",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=36,
        help="Target number of repositories in golden set",
    )
    parser.add_argument(
        "--autofill",
        action="store_true",
        help="Autofill expert_score with Codex provisional estimates",
    )
    return parser.parse_args()


def load_results(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"results not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("results JSON must be a list")
    return [item for item in data if isinstance(item, dict) and item.get("repo")]


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def select_evenly_spaced(
    items: List[Dict[str, Any]], size: int
) -> List[Dict[str, Any]]:
    if size <= 0 or not items:
        return []
    if size >= len(items):
        return items[:]

    selected_indices: Set[int] = set()
    for i in range(size):
        idx = round(i * (len(items) - 1) / max(1, size - 1))
        selected_indices.add(int(idx))

    selected = [items[idx] for idx in sorted(selected_indices)]

    if len(selected) < size:
        for idx in range(len(items)):
            if idx not in selected_indices:
                selected.append(items[idx])
            if len(selected) >= size:
                break
    return selected[:size]


def select_stratified(results: List[Dict[str, Any]], size: int) -> List[Dict[str, Any]]:
    ordered = sorted(results, key=lambda item: _to_float(item.get("total_score"), 0.0))
    base = select_evenly_spaced(ordered, size)

    # Ensure red data-quality cases are represented.
    red_cases = [
        item
        for item in ordered
        if str(item.get("data_quality_status", "")).lower() == "red"
    ]
    red_target = min(max(4, size // 5), len(red_cases))
    selected_by_repo = {str(item["repo"]): item for item in base}
    for item in red_cases[:red_target]:
        selected_by_repo[str(item["repo"])] = item

    selected = list(selected_by_repo.values())
    if len(selected) > size:
        selected = select_evenly_spaced(
            sorted(selected, key=lambda item: _to_float(item.get("total_score"), 0.0)),
            size,
        )

    return sorted(selected, key=lambda item: _to_float(item.get("total_score"), 0.0))


def estimate_expert_score(item: Dict[str, Any]) -> float:
    """
    Provisional Codex estimate for initial calibration bootstrap.
    This is intentionally conservative and should be manually reviewed.
    """
    model_score = _to_float(item.get("total_score"), 0.0)
    quality = str(item.get("data_quality_status", "green")).lower()
    coverage = _to_float(item.get("data_coverage_percent"), 0.0)

    adjustment = 0.0
    if quality == "red":
        adjustment -= 3.0
    elif quality == "yellow":
        adjustment -= 1.5

    if coverage >= 95:
        adjustment += 1.0
    elif coverage < 80:
        adjustment -= 1.0

    if _to_float(item.get("cicd"), 0.0) >= 1.0:
        adjustment += 1.0
    if _to_float(item.get("readme"), 0.0) >= 3.0:
        adjustment += 1.0

    test_coverage = item.get("test_coverage")
    if test_coverage is not None:
        if _to_float(test_coverage) >= 4.0:
            adjustment += 0.8
        elif _to_float(test_coverage) < 2.0:
            adjustment -= 0.8

    vulnerabilities = item.get("vulnerabilities")
    if vulnerabilities is not None:
        if _to_float(vulnerabilities) >= 4.0:
            adjustment += 0.8
        elif _to_float(vulnerabilities) < 2.0:
            adjustment -= 1.0

    expert_score = max(0.0, min(50.0, model_score + adjustment))
    return round(expert_score, 1)


def write_golden_set(
    rows: List[Dict[str, Any]], output_path: Path, autofill: bool = False
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "repo",
        "expert_score",
        "model_score",
        "data_quality_status",
        "data_coverage_percent",
        "category",
        "label_source",
        "notes",
    ]

    with open(output_path, "w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for item in rows:
            writer.writerow(
                {
                    "repo": item["repo"],
                    "expert_score": (
                        f"{estimate_expert_score(item):.1f}" if autofill else ""
                    ),
                    "model_score": f"{_to_float(item.get('total_score'), 0.0):.2f}",
                    "data_quality_status": item.get("data_quality_status", "unknown"),
                    "data_coverage_percent": f"{_to_float(item.get('data_coverage_percent'), 0.0):.2f}",
                    "category": item.get("category", ""),
                    "label_source": (
                        "codex_provisional_v1" if autofill else "manual_required"
                    ),
                    "notes": "review_required",
                }
            )


def main() -> None:
    args = parse_arguments()
    results = load_results(Path(args.results))
    selected = select_stratified(results, size=max(1, args.sample_size))

    output_path = Path(args.output)
    write_golden_set(selected, output_path=output_path, autofill=args.autofill)

    print(
        f"Golden set saved: {output_path} | repos={len(selected)} | autofill={args.autofill}"
    )
    red_count = sum(
        1
        for item in selected
        if str(item.get("data_quality_status", "")).lower() == "red"
    )
    print(f"Data quality red cases included: {red_count}")


if __name__ == "__main__":
    main()
