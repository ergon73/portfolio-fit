import csv
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


def load_expert_labels(csv_path: Path) -> Dict[str, float]:
    """
    Загружает экспертную разметку из CSV.
    Expected columns: repo, expert_score.
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"labels file not found: {csv_path}")

    labels: Dict[str, float] = {}
    with open(csv_path, "r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            raise ValueError("labels csv has no header")
        required = {"repo", "expert_score"}
        if not required.issubset(set(reader.fieldnames)):
            raise ValueError("labels csv must contain columns: repo, expert_score")

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


def load_model_scores(results_json_path: Path) -> Dict[str, float]:
    """
    Загружает модельные score из portfolio_evaluation_*.json.
    """
    if not results_json_path.exists():
        raise FileNotFoundError(f"results file not found: {results_json_path}")

    raw_data = json.loads(results_json_path.read_text(encoding="utf-8"))
    if not isinstance(raw_data, list):
        raise ValueError("results json must be a list of repository objects")

    scores: Dict[str, float] = {}
    for item in raw_data:
        if not isinstance(item, dict):
            continue
        repo = str(item.get("repo", "")).strip()
        if not repo:
            continue
        try:
            scores[repo] = float(item.get("total_score", 0.0))
        except (TypeError, ValueError):
            continue

    return scores


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _rank(values: Sequence[float]) -> List[float]:
    """
    Возвращает ранги со средними рангами для ties.
    """
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i
        while j + 1 < len(indexed) and indexed[j + 1][1] == indexed[i][1]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            original_index = indexed[k][0]
            ranks[original_index] = avg_rank
        i = j + 1
    return ranks


def pearson_correlation(x: Sequence[float], y: Sequence[float]) -> Optional[float]:
    """
    Считает коэффициент корреляции Пирсона.
    """
    if len(x) != len(y) or len(x) < 2:
        return None

    mean_x = _mean(x)
    mean_y = _mean(y)
    numerator = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y))
    denom_x = math.sqrt(sum((a - mean_x) ** 2 for a in x))
    denom_y = math.sqrt(sum((b - mean_y) ** 2 for b in y))
    denominator = denom_x * denom_y
    if denominator == 0:
        return None
    return numerator / denominator


def spearman_correlation(x: Sequence[float], y: Sequence[float]) -> Optional[float]:
    """
    Считает ранговую корреляцию Спирмена.
    """
    if len(x) != len(y) or len(x) < 2:
        return None
    ranks_x = _rank(x)
    ranks_y = _rank(y)
    return pearson_correlation(ranks_x, ranks_y)


def mean_absolute_error(x: Sequence[float], y: Sequence[float]) -> Optional[float]:
    if len(x) != len(y) or len(x) < 1:
        return None
    return sum(abs(a - b) for a, b in zip(x, y)) / len(x)


def match_samples(
    expert_labels: Dict[str, float], model_scores: Dict[str, float]
) -> List[Tuple[str, float, float]]:
    """
    Возвращает пары (repo, expert_score, model_score) по пересечению.
    """
    common = sorted(set(expert_labels).intersection(model_scores))
    return [(repo, expert_labels[repo], model_scores[repo]) for repo in common]


def build_calibration_report(
    expert_labels: Dict[str, float],
    model_scores: Dict[str, float],
    labels_source: Optional[str] = None,
    results_source: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Формирует calibration report.
    """
    samples = match_samples(expert_labels, model_scores)
    expert_values = [sample[1] for sample in samples]
    model_values = [sample[2] for sample in samples]

    pearson = pearson_correlation(expert_values, model_values)
    spearman = spearman_correlation(expert_values, model_values)
    mae = mean_absolute_error(expert_values, model_values)

    warnings: List[str] = []
    if len(samples) < 10:
        warnings.append(
            "small sample size (<10); calibration results are directionally useful only"
        )
    if spearman is None:
        warnings.append("unable to compute rank correlation (insufficient variance)")
    elif spearman < 0.4:
        warnings.append(
            f"low rank correlation ({spearman:.2f}); thresholds/weights need review"
        )
    if mae is not None and mae > 8.0:
        warnings.append(f"high absolute error ({mae:.2f}); score calibration is weak")

    quality_band = "good"
    if spearman is None or (spearman is not None and spearman < 0.4):
        quality_band = "poor"
    elif spearman < 0.7:
        quality_band = "moderate"

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "labels_source": labels_source,
        "results_source": results_source,
        "sample_size": len(samples),
        "metrics": {
            "spearman": round(spearman, 4) if spearman is not None else None,
            "pearson": round(pearson, 4) if pearson is not None else None,
            "mae": round(mae, 4) if mae is not None else None,
        },
        "quality_band": quality_band,
        "warnings": warnings,
        "pairs": [
            {
                "repo": repo,
                "expert_score": round(expert_score, 3),
                "model_score": round(model_score, 3),
                "delta": round(model_score - expert_score, 3),
            }
            for repo, expert_score, model_score in samples
        ],
    }
