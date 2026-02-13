import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from portfolio_fit.calibration import spearman_correlation
from portfolio_fit.scoring import EvaluationConstants


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def load_labels(csv_path: Path) -> Dict[str, float]:
    if not csv_path.exists():
        raise FileNotFoundError(f"labels file not found: {csv_path}")

    labels: Dict[str, float] = {}
    with open(csv_path, "r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            repo = str(row.get("repo", "")).strip()
            if not repo:
                continue
            raw_score = row.get("expert_score")
            try:
                labels[repo] = float(str(raw_score))
            except (TypeError, ValueError):
                continue
    return labels


def load_results(json_path: Path) -> Dict[str, Dict[str, Any]]:
    if not json_path.exists():
        raise FileNotFoundError(f"results file not found: {json_path}")

    data = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("results JSON must be a list")

    return {
        str(item.get("repo")): item
        for item in data
        if isinstance(item, dict) and item.get("repo")
    }


def _criterion_ratio(result: Dict[str, Any], criterion: str) -> Optional[float]:
    score_raw = result.get(criterion)
    if score_raw is None:
        return None
    criteria_meta = result.get("criteria_meta", {})
    if not isinstance(criteria_meta, dict):
        return None
    meta = criteria_meta.get(criterion, {})
    if not isinstance(meta, dict):
        return None
    if str(meta.get("status", "known")) == "unknown":
        return None
    max_score = _to_float(meta.get("max_score"), 0.0)
    if max_score <= 0:
        return None
    score = _to_float(score_raw)
    return max(0.0, min(1.0, score / max_score))


def suggest_criterion_max_scores(
    labels: Dict[str, float],
    results_map: Dict[str, Dict[str, Any]],
    min_samples: int = 8,
) -> Dict[str, Any]:
    common_repos = sorted(set(labels).intersection(results_map))
    if not common_repos:
        raise ValueError("no overlapping repositories between labels and results")

    criterion_keys = list(EvaluationConstants.CRITERION_MAX_SCORES.keys())
    criterion_stats: List[Dict[str, Any]] = []

    correlation_values: List[float] = []
    by_criterion_correlation: Dict[str, Optional[float]] = {}
    by_criterion_samples: Dict[str, int] = {}

    for criterion in criterion_keys:
        x_values: List[float] = []
        y_values: List[float] = []
        for repo in common_repos:
            result = results_map[repo]
            ratio = _criterion_ratio(result, criterion)
            if ratio is None:
                continue
            x_values.append(ratio)
            y_values.append(labels[repo] / 50.0)

        sample_count = len(x_values)
        corr: Optional[float] = None
        if sample_count >= min_samples:
            corr = spearman_correlation(x_values, y_values)
            if corr is not None:
                correlation_values.append(corr)

        by_criterion_correlation[criterion] = corr
        by_criterion_samples[criterion] = sample_count

    median_corr = 0.45
    if correlation_values:
        sorted_corr = sorted(correlation_values)
        median_corr = sorted_corr[len(sorted_corr) // 2]

    raw_suggested: Dict[str, float] = {}
    for criterion in criterion_keys:
        old_max = _to_float(EvaluationConstants.CRITERION_MAX_SCORES[criterion], 0.0)
        corr = by_criterion_correlation.get(criterion)
        sample_count = by_criterion_samples.get(criterion, 0)

        if corr is None:
            factor = 0.92 if sample_count >= min_samples else 0.85
        else:
            factor = 1.0 + (corr - median_corr) * 0.45
            factor = max(0.75, min(1.30, factor))

        raw_suggested[criterion] = old_max * factor

    # Normalize within each block to preserve block totals.
    normalized: Dict[str, float] = {}
    for block_key, block_total in EvaluationConstants.BLOCK_MAX_SCORES.items():
        block_criteria = [
            key
            for key, criterion_block in EvaluationConstants.CRITERION_BLOCK.items()
            if criterion_block == block_key
        ]
        raw_total = sum(raw_suggested[key] for key in block_criteria)
        if raw_total <= 0:
            for key in block_criteria:
                normalized[key] = _to_float(
                    EvaluationConstants.CRITERION_MAX_SCORES[key], 0.0
                )
            continue

        scale = _to_float(block_total, 0.0) / raw_total
        for key in block_criteria:
            normalized[key] = round(raw_suggested[key] * scale, 3)

    for criterion in criterion_keys:
        old_max = _to_float(EvaluationConstants.CRITERION_MAX_SCORES[criterion], 0.0)
        new_max = normalized.get(criterion, old_max)
        corr = by_criterion_correlation.get(criterion)
        criterion_stats.append(
            {
                "criterion": criterion,
                "samples": by_criterion_samples.get(criterion, 0),
                "spearman": round(corr, 4) if corr is not None else None,
                "old_max": round(old_max, 3),
                "suggested_max": round(new_max, 3),
                "delta_max": round(new_max - old_max, 3),
            }
        )

    criterion_stats.sort(key=lambda row: abs(_to_float(row["delta_max"])), reverse=True)

    return {
        "sample_size": len(common_repos),
        "median_spearman_used": round(median_corr, 4),
        "criterion_stats": criterion_stats,
        "suggested_criterion_max_scores": {
            key: normalized[key] for key in criterion_keys if key in normalized
        },
    }


def save_tuning_report(report: Dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def apply_suggested_scores_to_config(
    suggested_scores: Dict[str, float], config_path: Path
) -> Dict[str, Any]:
    existing: Dict[str, Any] = {}
    if config_path.exists():
        try:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                existing = raw
        except (ValueError, OSError):
            existing = {}

    max_scores = existing.get("CRITERION_MAX_SCORES", {})
    if not isinstance(max_scores, dict):
        max_scores = {}
    max_scores.update(suggested_scores)
    existing["CRITERION_MAX_SCORES"] = max_scores
    config_path.write_text(
        json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return existing
