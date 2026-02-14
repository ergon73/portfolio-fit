import csv
import json
import math
import shutil
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from portfolio_fit.calibration import (
    build_calibration_report,
    load_expert_labels,
    load_model_scores,
)
from portfolio_fit.scoring import NON_AUTO_STACK_PROFILES, detect_stack_profile
from portfolio_fit.tuning import (
    load_results,
    save_tuning_report,
    suggest_criterion_max_scores,
)

STACK_PROFILE_AUTO = "auto"
STACK_PROFILE_ALL = "all"
STACK_PROFILE_DJANGO_TEMPLATES_ALIAS = "django_templates"
STACK_PROFILE_CHOICES = (
    STACK_PROFILE_AUTO,
    STACK_PROFILE_ALL,
    "python_backend",
    "python_fullstack_react",
    STACK_PROFILE_DJANGO_TEMPLATES_ALIAS,
    "python_django_templates",
    "node_frontend",
    "mixed_unknown",
)
STACK_PROFILE_ALIASES = {
    STACK_PROFILE_DJANGO_TEMPLATES_ALIAS: "python_django_templates",
}
STACK_PROFILE_CHOICES_SET = set(STACK_PROFILE_CHOICES)

DEFAULT_STACK_SPLIT_GROUPS: Dict[str, Set[str]] = {
    "python_backend": {"python_backend"},
    "python_fullstack_react": {"python_fullstack_react"},
    STACK_PROFILE_DJANGO_TEMPLATES_ALIAS: {"python_django_templates"},
}


@dataclass
class RecalibrationProfilePaths:
    profile_name: str
    profile_slug: str
    root: Path
    labels_csv: Path
    labels_by_stack_dir: Path
    calibration_prefix: Path
    calibration_json: Path
    calibration_txt: Path
    tuning_patch_json: Path
    profile_config_json: Path
    profile_root_config_json: Path
    summary_json: Path
    summary_txt: Path
    active_config_backup_dir: Path


def slugify_profile_name(name: str) -> str:
    cleaned = "".join(
        char.lower() if (char.isalnum() or char in {"-", "_"}) else "-"
        for char in name.strip()
    )
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    cleaned = cleaned.strip("-_")
    return cleaned or "default"


def _canonical_stack_profile(value: Optional[str]) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return "mixed_unknown"
    alias_mapped = STACK_PROFILE_ALIASES.get(normalized, normalized)
    if alias_mapped in set(NON_AUTO_STACK_PROFILES):
        return alias_mapped
    return "mixed_unknown"


def _stack_slug(stack_profile: Optional[str]) -> str:
    if not stack_profile:
        return "all"
    canonical = _canonical_stack_profile(stack_profile)
    if canonical == "python_django_templates":
        return STACK_PROFILE_DJANGO_TEMPLATES_ALIAS
    return canonical


def _resolve_stack_selection(
    requested_stack_profile: str,
    stack_counts: Dict[str, int],
    strict_stack_profile: bool,
) -> Optional[str]:
    requested = str(requested_stack_profile or STACK_PROFILE_AUTO).strip().lower()
    if requested == STACK_PROFILE_ALL:
        return None

    if requested == STACK_PROFILE_AUTO:
        if not stack_counts:
            return None
        if len(stack_counts) == 1:
            return next(iter(stack_counts))
        if strict_stack_profile:
            discovered = ", ".join(
                f"{stack}={count}"
                for stack, count in sorted(
                    stack_counts.items(), key=lambda item: item[0]
                )
            )
            raise ValueError(
                "mixed stack profiles detected in overlapping labels/results "
                f"({discovered}); specify --stack-profile or disable strict mode"
            )
        return max(stack_counts.items(), key=lambda item: item[1])[0]

    canonical = _canonical_stack_profile(requested)
    if canonical == "mixed_unknown" and requested != "mixed_unknown":
        allowed = ", ".join(STACK_PROFILE_CHOICES)
        raise ValueError(
            f"unsupported stack profile '{requested_stack_profile}'. Allowed: {allowed}"
        )
    return canonical


def _load_label_rows(labels_csv_path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    if not labels_csv_path.exists():
        raise FileNotFoundError(f"labels file not found: {labels_csv_path}")

    with open(labels_csv_path, "r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        fieldnames = list(reader.fieldnames or [])
        if not fieldnames:
            raise ValueError("labels csv has no header")
        rows = [dict(row) for row in reader if row.get("repo")]
    return fieldnames, rows


def _write_label_rows(
    output_path: Path,
    fieldnames: Sequence[str],
    rows: Sequence[Dict[str, str]],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _infer_result_stack_profile(result_item: Dict[str, Any]) -> str:
    stack_raw = result_item.get("stack_profile")
    canonical = _canonical_stack_profile(stack_raw)
    if canonical != "mixed_unknown":
        return canonical

    path_raw = result_item.get("path")
    if isinstance(path_raw, str) and path_raw.strip():
        candidate = Path(path_raw)
        if candidate.exists() and candidate.is_dir():
            return _canonical_stack_profile(detect_stack_profile(candidate))

    return "mixed_unknown"


def build_results_stack_map(results_map: Dict[str, Dict[str, Any]]) -> Dict[str, str]:
    stack_map: Dict[str, str] = {}
    for repo, item in results_map.items():
        stack_map[repo] = _infer_result_stack_profile(item)
    return stack_map


def split_profile_labels_by_stack(
    *,
    labels_csv_path: Path,
    results_path: Path,
    output_dir: Path,
    include_additional_stacks: bool = False,
) -> Dict[str, Any]:
    fieldnames, rows = _load_label_rows(labels_csv_path)
    results_map = load_results(results_path)
    stack_map = build_results_stack_map(results_map)

    rows_by_group: Dict[str, List[Dict[str, str]]] = {
        group_name: [] for group_name in DEFAULT_STACK_SPLIT_GROUPS
    }
    missing_repos: List[str] = []

    if include_additional_stacks:
        additional_stacks = set(stack_map.values()).difference(
            set().union(*DEFAULT_STACK_SPLIT_GROUPS.values())
        )
        for stack_name in sorted(additional_stacks):
            rows_by_group[stack_name] = []

    for row in rows:
        repo = str(row.get("repo", "")).strip()
        if not repo:
            continue
        stack_profile = stack_map.get(repo)
        if not stack_profile:
            missing_repos.append(repo)
            continue
        appended = False
        for group_name, stack_values in DEFAULT_STACK_SPLIT_GROUPS.items():
            if stack_profile in stack_values:
                rows_by_group[group_name].append(row)
                appended = True
                break
        if not appended and include_additional_stacks:
            rows_by_group.setdefault(stack_profile, []).append(row)

    output_dir.mkdir(parents=True, exist_ok=True)
    written_files: Dict[str, str] = {}
    counts: Dict[str, int] = {}
    for group_name, group_rows in rows_by_group.items():
        if not group_rows:
            continue
        output_path = output_dir / f"golden_set_{group_name}.csv"
        _write_label_rows(output_path, fieldnames, group_rows)
        written_files[group_name] = str(output_path)
        counts[group_name] = len(group_rows)

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "labels_path": str(labels_csv_path),
        "results_path": str(results_path),
        "output_dir": str(output_dir),
        "groups": counts,
        "files": written_files,
        "missing_repos": sorted(set(missing_repos)),
    }
    summary_path = output_dir / "split_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return summary


def build_profile_paths(
    workspace_dir: Path, profile_name: str
) -> RecalibrationProfilePaths:
    slug = slugify_profile_name(profile_name)
    root = workspace_dir / slug
    labels_dir = root / "labels"
    labels_by_stack_dir = labels_dir / "by_stack"
    artifacts_dir = root / "artifacts"
    configs_dir = root / "configs"

    labels_dir.mkdir(parents=True, exist_ok=True)
    labels_by_stack_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    configs_dir.mkdir(parents=True, exist_ok=True)

    calibration_prefix = artifacts_dir / "calibration_report"
    return RecalibrationProfilePaths(
        profile_name=profile_name,
        profile_slug=slug,
        root=root,
        labels_csv=labels_dir / "golden_set.csv",
        labels_by_stack_dir=labels_by_stack_dir,
        calibration_prefix=calibration_prefix,
        calibration_json=Path(f"{calibration_prefix}.json"),
        calibration_txt=Path(f"{calibration_prefix}.txt"),
        tuning_patch_json=artifacts_dir / "scoring_config_patch.json",
        profile_config_json=configs_dir / "scoring_config.profile.json",
        profile_root_config_json=root / "scoring_config.json",
        summary_json=artifacts_dir / "recalibration_summary.json",
        summary_txt=artifacts_dir / "recalibration_summary.txt",
        active_config_backup_dir=configs_dir / "active_config_backups",
    )


def prepare_profile_labels(
    *,
    results_path: Path,
    labels_csv_path: Path,
    sample_size: int = 36,
    autofill: bool = False,
    force_overwrite: bool = False,
    stack_profile: str = STACK_PROFILE_ALL,
) -> bool:
    if labels_csv_path.exists() and not force_overwrite:
        return False

    # Local import to avoid CLI dependencies at package import time.
    import prepare_golden_set as golden_set

    results = golden_set.load_results(results_path)
    requested_stack = str(stack_profile or STACK_PROFILE_ALL).strip().lower()
    if requested_stack not in STACK_PROFILE_CHOICES_SET:
        allowed = ", ".join(STACK_PROFILE_CHOICES)
        raise ValueError(
            f"unsupported stack profile for prepare: '{stack_profile}'. Allowed: {allowed}"
        )

    if requested_stack not in {STACK_PROFILE_ALL, STACK_PROFILE_AUTO}:
        target_stack = _canonical_stack_profile(requested_stack)
        results = [
            item
            for item in results
            if _canonical_stack_profile(item.get("stack_profile")) == target_stack
        ]
        if not results:
            raise ValueError(
                f"no repositories in results for stack profile '{stack_profile}'"
            )

    selected = golden_set.select_stratified(results, size=max(1, sample_size))
    golden_set.write_golden_set(
        selected, output_path=labels_csv_path, autofill=autofill
    )
    return True


def _save_calibration_report(report: Dict[str, Any], output_prefix: Path) -> None:
    json_path = Path(f"{output_prefix}.json")
    txt_path = Path(f"{output_prefix}.txt")

    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    metrics = report.get("metrics", {})
    warnings = report.get("warnings", [])
    stack_breakdown = report.get("stack_profile_breakdown", {})
    with open(txt_path, "w", encoding="utf-8") as file:
        file.write("=" * 100 + "\n")
        file.write("SCORING CALIBRATION REPORT\n")
        file.write("=" * 100 + "\n\n")
        file.write(f"Generated: {datetime.now().isoformat(timespec='seconds')}\n")
        file.write(f"Labels source: {report.get('labels_source')}\n")
        file.write(f"Results source: {report.get('results_source')}\n")
        file.write(f"Requested stack: {report.get('requested_stack_profile')}\n")
        file.write(f"Resolved stack: {report.get('resolved_stack_profile')}\n")
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

        if isinstance(stack_breakdown, dict) and stack_breakdown:
            file.write("Stack profile breakdown:\n")
            for stack_name, stack_stats in stack_breakdown.items():
                if not isinstance(stack_stats, dict):
                    continue
                correlation = stack_stats.get("correlation", {})
                rank_correlation = stack_stats.get("rank_correlation", {})
                error_bands = stack_stats.get("error_bands", {})
                file.write(
                    f"  - {stack_name}: sample={stack_stats.get('sample_size')}, "
                    f"quality={stack_stats.get('quality_band')}, "
                    f"pearson={correlation.get('pearson')}, "
                    f"spearman={rank_correlation.get('spearman')}, "
                    f"mae={error_bands.get('mae')}, "
                    f"p90_abs_error={error_bands.get('p90_abs_error')}\n"
                )
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


def build_profile_config(
    suggested_scores: Dict[str, float],
    base_config_path: Path,
    profile_slug: str,
    labels_source: str,
    requested_stack_profile: str,
    resolved_stack_profile: Optional[str],
    stack_breakdown: Dict[str, Any],
) -> Dict[str, Any]:
    base_config: Dict[str, Any] = {}
    if base_config_path.exists():
        try:
            raw = json.loads(base_config_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                base_config = raw
        except (ValueError, OSError):
            base_config = {}

    max_scores = base_config.get("CRITERION_MAX_SCORES", {})
    if not isinstance(max_scores, dict):
        max_scores = {}
    max_scores.update(suggested_scores)
    base_config["CRITERION_MAX_SCORES"] = max_scores
    base_config["CALIBRATION_PROFILE"] = {
        "profile": profile_slug,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "labels_source": labels_source,
        "requested_stack_profile": requested_stack_profile,
        "resolved_stack_profile": resolved_stack_profile or STACK_PROFILE_ALL,
        "stack_profile_breakdown": stack_breakdown,
    }
    return base_config


def backup_file_if_exists(target_path: Path, backup_dir: Path) -> Optional[Path]:
    if not target_path.exists():
        return None

    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{target_path.name}.backup.{timestamp}"
    shutil.copy2(target_path, backup_path)
    return backup_path


def save_recalibration_summary(
    *,
    output_json: Path,
    output_txt: Path,
    summary: Dict[str, Any],
) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    calibration_metrics = summary.get("calibration_metrics", {})
    stack_breakdown = summary.get("stack_profile_breakdown", {})
    with open(output_txt, "w", encoding="utf-8") as file:
        file.write("=" * 100 + "\n")
        file.write("RECALIBRATION SUMMARY\n")
        file.write("=" * 100 + "\n\n")
        file.write(f"Profile: {summary.get('profile')}\n")
        file.write(f"Generated at: {summary.get('generated_at')}\n")
        file.write(f"Results: {summary.get('results_path')}\n")
        file.write(f"Labels: {summary.get('labels_path')}\n")
        file.write(f"Requested stack: {summary.get('requested_stack_profile')}\n")
        file.write(f"Resolved stack: {summary.get('resolved_stack_profile')}\n")
        file.write(f"Strict stack mode: {summary.get('strict_stack_profile')}\n\n")

        file.write("Calibration metrics:\n")
        file.write(f"  sample_size: {summary.get('sample_size')}\n")
        file.write(f"  spearman: {calibration_metrics.get('spearman')}\n")
        file.write(f"  pearson: {calibration_metrics.get('pearson')}\n")
        file.write(f"  mae: {calibration_metrics.get('mae')}\n\n")

        overlap_counts = summary.get("overlap_stack_counts", {})
        filtered_counts = summary.get("filtered_stack_counts", {})
        if isinstance(overlap_counts, dict):
            file.write("Overlap stack counts:\n")
            for stack_name, count in overlap_counts.items():
                file.write(f"  - {stack_name}: {count}\n")
            file.write("\n")
        if isinstance(filtered_counts, dict):
            file.write("Filtered stack counts:\n")
            for stack_name, count in filtered_counts.items():
                file.write(f"  - {stack_name}: {count}\n")
            file.write("\n")

        if isinstance(stack_breakdown, dict) and stack_breakdown:
            file.write("Stack profile breakdown:\n")
            for stack_name, stats in stack_breakdown.items():
                if not isinstance(stats, dict):
                    continue
                correlation = stats.get("correlation", {})
                rank_correlation = stats.get("rank_correlation", {})
                error_bands = stats.get("error_bands", {})
                file.write(
                    f"  - {stack_name}: sample={stats.get('sample_size')}, "
                    f"quality={stats.get('quality_band')}, "
                    f"pearson={correlation.get('pearson')}, "
                    f"spearman={rank_correlation.get('spearman')}, "
                    f"mae={error_bands.get('mae')}, "
                    f"p90_abs_error={error_bands.get('p90_abs_error')}\n"
                )
            file.write("\n")

        file.write("Artifacts:\n")
        file.write(f"  calibration_json: {summary.get('calibration_json')}\n")
        file.write(f"  calibration_txt: {summary.get('calibration_txt')}\n")
        file.write(f"  tuning_patch_json: {summary.get('tuning_patch_json')}\n")
        file.write(f"  profile_config_json: {summary.get('profile_config_json')}\n")
        file.write(
            f"  profile_stack_config_json: {summary.get('profile_stack_config_json')}\n"
        )
        file.write(
            f"  profile_root_config_json: {summary.get('profile_root_config_json')}\n"
        )
        file.write(f"  applied_config_path: {summary.get('applied_config_path')}\n")
        file.write(f"  backup_config_path: {summary.get('backup_config_path')}\n")


def _percentile(sorted_values: Sequence[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    bounded_q = max(0.0, min(1.0, float(q)))
    position = (len(sorted_values) - 1) * bounded_q
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return float(sorted_values[lower])
    lower_val = float(sorted_values[lower])
    upper_val = float(sorted_values[upper])
    return lower_val + (upper_val - lower_val) * (position - lower)


def _compute_error_bands(pairs: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    abs_errors = sorted(
        abs(float(item.get("delta", 0.0)))
        for item in pairs
        if isinstance(item, dict) and item.get("delta") is not None
    )
    if not abs_errors:
        return {
            "mae": None,
            "p50_abs_error": None,
            "p75_abs_error": None,
            "p90_abs_error": None,
            "max_abs_error": None,
        }
    return {
        "mae": round(sum(abs_errors) / len(abs_errors), 4),
        "p50_abs_error": round(_percentile(abs_errors, 0.50), 4),
        "p75_abs_error": round(_percentile(abs_errors, 0.75), 4),
        "p90_abs_error": round(_percentile(abs_errors, 0.90), 4),
        "max_abs_error": round(max(abs_errors), 4),
    }


def _build_stack_profile_breakdown(
    labels: Dict[str, float],
    scores: Dict[str, float],
    repo_stack_map: Dict[str, str],
) -> Dict[str, Dict[str, Any]]:
    breakdown: Dict[str, Dict[str, Any]] = {}
    overlap_repos = sorted(set(labels).intersection(scores))
    if not overlap_repos:
        return breakdown

    by_stack: Dict[str, List[str]] = {}
    for repo in overlap_repos:
        stack = repo_stack_map.get(repo, "mixed_unknown")
        by_stack.setdefault(stack, []).append(repo)

    for stack, repos in sorted(by_stack.items()):
        stack_labels = {repo: labels[repo] for repo in repos}
        stack_scores = {repo: scores[repo] for repo in repos}
        stack_report = build_calibration_report(stack_labels, stack_scores)
        pairs = stack_report.get("pairs", [])
        breakdown[stack] = {
            "sample_size": stack_report.get("sample_size"),
            "quality_band": stack_report.get("quality_band"),
            "correlation": {
                "pearson": stack_report.get("metrics", {}).get("pearson"),
            },
            "rank_correlation": {
                "spearman": stack_report.get("metrics", {}).get("spearman"),
            },
            "error_bands": _compute_error_bands(
                pairs if isinstance(pairs, list) else []
            ),
        }

    return breakdown


def run_profile_recalibration(
    *,
    profile_paths: RecalibrationProfilePaths,
    results_path: Path,
    labels_path: Optional[Path] = None,
    min_samples: int = 8,
    base_config_path: Path = Path("portfolio_fit/scoring_config.json"),
    apply_to_config_path: Optional[Path] = None,
    stack_profile: str = STACK_PROFILE_AUTO,
    strict_stack_profile: bool = True,
) -> Dict[str, Any]:
    resolved_labels = labels_path or profile_paths.labels_csv
    if not resolved_labels.exists():
        raise FileNotFoundError(
            "labels file not found: "
            f"{resolved_labels}. Run with --prepare-golden-set first."
        )

    labels = load_expert_labels(resolved_labels)
    scores = load_model_scores(results_path)
    results_map = load_results(results_path)
    repo_stack_map = build_results_stack_map(results_map)

    overlap_repos = sorted(set(labels).intersection(scores).intersection(results_map))
    if not overlap_repos:
        raise ValueError("no overlapping repositories between labels and results")

    overlap_stack_counts = Counter(
        repo_stack_map.get(repo, "mixed_unknown") for repo in overlap_repos
    )
    requested_stack_profile = str(stack_profile or STACK_PROFILE_AUTO).strip().lower()
    if requested_stack_profile not in STACK_PROFILE_CHOICES_SET:
        allowed = ", ".join(STACK_PROFILE_CHOICES)
        raise ValueError(
            f"unsupported stack profile '{stack_profile}'. Allowed: {allowed}"
        )
    resolved_stack_profile = _resolve_stack_selection(
        requested_stack_profile=requested_stack_profile,
        stack_counts=dict(overlap_stack_counts),
        strict_stack_profile=strict_stack_profile,
    )

    filtered_repos = overlap_repos
    if resolved_stack_profile is not None:
        filtered_repos = [
            repo
            for repo in overlap_repos
            if repo_stack_map.get(repo) == resolved_stack_profile
        ]
        if strict_stack_profile and requested_stack_profile == STACK_PROFILE_AUTO:
            out_of_scope = {
                stack: count
                for stack, count in overlap_stack_counts.items()
                if stack != resolved_stack_profile
            }
            if out_of_scope:
                discovered = ", ".join(
                    f"{stack}={count}" for stack, count in sorted(out_of_scope.items())
                )
                raise ValueError(
                    "strict stack mode rejected mixed samples; "
                    f"target={resolved_stack_profile}, out_of_scope={discovered}. "
                    "Use --strict-stack false or --stack-profile all."
                )
        if not filtered_repos:
            raise ValueError(
                f"no overlapping repositories after stack filter '{resolved_stack_profile}'"
            )

    filtered_labels = {repo: labels[repo] for repo in filtered_repos}
    filtered_scores = {repo: scores[repo] for repo in filtered_repos}
    filtered_results_map = {repo: results_map[repo] for repo in filtered_repos}
    filtered_repo_stack_map = {repo: repo_stack_map[repo] for repo in filtered_repos}
    filtered_stack_counts = dict(
        Counter(
            filtered_repo_stack_map.get(repo, "mixed_unknown")
            for repo in filtered_repos
        )
    )

    calibration_report = build_calibration_report(
        filtered_labels,
        filtered_scores,
        labels_source=str(resolved_labels),
        results_source=str(results_path),
    )
    stack_breakdown = _build_stack_profile_breakdown(
        filtered_labels,
        filtered_scores,
        filtered_repo_stack_map,
    )
    calibration_report["requested_stack_profile"] = requested_stack_profile
    calibration_report["resolved_stack_profile"] = (
        resolved_stack_profile or STACK_PROFILE_ALL
    )
    calibration_report["strict_stack_profile"] = bool(strict_stack_profile)
    calibration_report["overlap_stack_counts"] = dict(overlap_stack_counts)
    calibration_report["filtered_stack_counts"] = filtered_stack_counts
    calibration_report["stack_profile_breakdown"] = stack_breakdown
    _save_calibration_report(calibration_report, profile_paths.calibration_prefix)

    tuning_report = suggest_criterion_max_scores(
        labels=filtered_labels,
        results_map=filtered_results_map,
        min_samples=max(2, min_samples),
    )
    tuning_report["requested_stack_profile"] = requested_stack_profile
    tuning_report["resolved_stack_profile"] = (
        resolved_stack_profile or STACK_PROFILE_ALL
    )
    tuning_report["overlap_stack_counts"] = dict(overlap_stack_counts)
    tuning_report["filtered_stack_counts"] = filtered_stack_counts
    tuning_report["stack_profile_breakdown"] = stack_breakdown
    save_tuning_report(tuning_report, profile_paths.tuning_patch_json)

    profile_config = build_profile_config(
        tuning_report.get("suggested_criterion_max_scores", {}),
        base_config_path=base_config_path,
        profile_slug=profile_paths.profile_slug,
        labels_source=str(resolved_labels),
        requested_stack_profile=requested_stack_profile,
        resolved_stack_profile=resolved_stack_profile,
        stack_breakdown=stack_breakdown,
    )

    stack_slug = _stack_slug(resolved_stack_profile)
    profile_stack_config_json = profile_paths.root / f"scoring_config.{stack_slug}.json"
    profile_paths.profile_config_json.write_text(
        json.dumps(profile_config, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    profile_paths.profile_root_config_json.write_text(
        json.dumps(profile_config, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    profile_stack_config_json.write_text(
        json.dumps(profile_config, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    backup_path: Optional[Path] = None
    if apply_to_config_path is not None:
        backup_path = backup_file_if_exists(
            apply_to_config_path, profile_paths.active_config_backup_dir
        )
        apply_to_config_path.parent.mkdir(parents=True, exist_ok=True)
        apply_to_config_path.write_text(
            json.dumps(profile_config, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    summary: Dict[str, Any] = {
        "profile": profile_paths.profile_slug,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "results_path": str(results_path),
        "labels_path": str(resolved_labels),
        "requested_stack_profile": requested_stack_profile,
        "resolved_stack_profile": resolved_stack_profile or STACK_PROFILE_ALL,
        "strict_stack_profile": bool(strict_stack_profile),
        "sample_size": calibration_report.get("sample_size"),
        "calibration_quality_band": calibration_report.get("quality_band"),
        "calibration_metrics": calibration_report.get("metrics", {}),
        "overlap_stack_counts": dict(overlap_stack_counts),
        "filtered_stack_counts": filtered_stack_counts,
        "stack_profile_breakdown": stack_breakdown,
        "calibration_json": str(profile_paths.calibration_json),
        "calibration_txt": str(profile_paths.calibration_txt),
        "tuning_patch_json": str(profile_paths.tuning_patch_json),
        "profile_config_json": str(profile_paths.profile_config_json),
        "profile_stack_config_json": str(profile_stack_config_json),
        "profile_root_config_json": str(profile_paths.profile_root_config_json),
        "applied_config_path": (
            str(apply_to_config_path) if apply_to_config_path is not None else None
        ),
        "backup_config_path": str(backup_path) if backup_path is not None else None,
    }
    save_recalibration_summary(
        output_json=profile_paths.summary_json,
        output_txt=profile_paths.summary_txt,
        summary=summary,
    )
    return summary


def print_profile_summary(summary: Dict[str, Any]) -> str:
    metrics = summary.get("calibration_metrics", {})
    return (
        f"profile={summary.get('profile')} | "
        f"stack={summary.get('resolved_stack_profile')} | "
        f"sample={summary.get('sample_size')} | "
        f"spearman={metrics.get('spearman')} | "
        f"pearson={metrics.get('pearson')} | "
        f"mae={metrics.get('mae')}"
    )
