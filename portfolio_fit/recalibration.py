import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from portfolio_fit.calibration import (
    build_calibration_report,
    load_expert_labels,
    load_model_scores,
)
from portfolio_fit.tuning import (
    load_labels,
    load_results,
    save_tuning_report,
    suggest_criterion_max_scores,
)


@dataclass
class RecalibrationProfilePaths:
    profile_name: str
    profile_slug: str
    root: Path
    labels_csv: Path
    calibration_prefix: Path
    calibration_json: Path
    calibration_txt: Path
    tuning_patch_json: Path
    profile_config_json: Path
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


def build_profile_paths(
    workspace_dir: Path, profile_name: str
) -> RecalibrationProfilePaths:
    slug = slugify_profile_name(profile_name)
    root = workspace_dir / slug
    labels_dir = root / "labels"
    artifacts_dir = root / "artifacts"
    configs_dir = root / "configs"

    labels_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    configs_dir.mkdir(parents=True, exist_ok=True)

    calibration_prefix = artifacts_dir / "calibration_report"
    return RecalibrationProfilePaths(
        profile_name=profile_name,
        profile_slug=slug,
        root=root,
        labels_csv=labels_dir / "golden_set.csv",
        calibration_prefix=calibration_prefix,
        calibration_json=Path(f"{calibration_prefix}.json"),
        calibration_txt=Path(f"{calibration_prefix}.txt"),
        tuning_patch_json=artifacts_dir / "scoring_config_patch.json",
        profile_config_json=configs_dir / "scoring_config.profile.json",
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
) -> bool:
    if labels_csv_path.exists() and not force_overwrite:
        return False

    # Local import to avoid CLI dependencies at package import time.
    import prepare_golden_set as golden_set

    results = golden_set.load_results(results_path)
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


def build_profile_config(
    suggested_scores: Dict[str, float],
    base_config_path: Path,
    profile_slug: str,
    labels_source: str,
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
    with open(output_txt, "w", encoding="utf-8") as file:
        file.write("=" * 100 + "\n")
        file.write("RECALIBRATION SUMMARY\n")
        file.write("=" * 100 + "\n\n")
        file.write(f"Profile: {summary.get('profile')}\n")
        file.write(f"Generated at: {summary.get('generated_at')}\n")
        file.write(f"Results: {summary.get('results_path')}\n")
        file.write(f"Labels: {summary.get('labels_path')}\n\n")

        file.write("Calibration metrics:\n")
        file.write(f"  sample_size: {summary.get('sample_size')}\n")
        file.write(f"  spearman: {calibration_metrics.get('spearman')}\n")
        file.write(f"  pearson: {calibration_metrics.get('pearson')}\n")
        file.write(f"  mae: {calibration_metrics.get('mae')}\n\n")

        file.write("Artifacts:\n")
        file.write(f"  calibration_json: {summary.get('calibration_json')}\n")
        file.write(f"  calibration_txt: {summary.get('calibration_txt')}\n")
        file.write(f"  tuning_patch_json: {summary.get('tuning_patch_json')}\n")
        file.write(f"  profile_config_json: {summary.get('profile_config_json')}\n")
        file.write(f"  applied_config_path: {summary.get('applied_config_path')}\n")
        file.write(f"  backup_config_path: {summary.get('backup_config_path')}\n")


def run_profile_recalibration(
    *,
    profile_paths: RecalibrationProfilePaths,
    results_path: Path,
    labels_path: Optional[Path] = None,
    min_samples: int = 8,
    base_config_path: Path = Path("portfolio_fit/scoring_config.json"),
    apply_to_config_path: Optional[Path] = None,
) -> Dict[str, Any]:
    resolved_labels = labels_path or profile_paths.labels_csv
    if not resolved_labels.exists():
        raise FileNotFoundError(
            "labels file not found: "
            f"{resolved_labels}. Run with --prepare-golden-set first."
        )

    labels = load_expert_labels(resolved_labels)
    scores = load_model_scores(results_path)
    calibration_report = build_calibration_report(
        labels,
        scores,
        labels_source=str(resolved_labels),
        results_source=str(results_path),
    )
    _save_calibration_report(calibration_report, profile_paths.calibration_prefix)

    tuning_labels = load_labels(resolved_labels)
    tuning_results = load_results(results_path)
    tuning_report = suggest_criterion_max_scores(
        labels=tuning_labels,
        results_map=tuning_results,
        min_samples=max(2, min_samples),
    )
    save_tuning_report(tuning_report, profile_paths.tuning_patch_json)

    profile_config = build_profile_config(
        tuning_report.get("suggested_criterion_max_scores", {}),
        base_config_path=base_config_path,
        profile_slug=profile_paths.profile_slug,
        labels_source=str(resolved_labels),
    )
    profile_paths.profile_config_json.write_text(
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
        "sample_size": calibration_report.get("sample_size"),
        "calibration_quality_band": calibration_report.get("quality_band"),
        "calibration_metrics": calibration_report.get("metrics", {}),
        "calibration_json": str(profile_paths.calibration_json),
        "calibration_txt": str(profile_paths.calibration_txt),
        "tuning_patch_json": str(profile_paths.tuning_patch_json),
        "profile_config_json": str(profile_paths.profile_config_json),
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
        f"sample={summary.get('sample_size')} | "
        f"spearman={metrics.get('spearman')} | "
        f"pearson={metrics.get('pearson')} | "
        f"mae={metrics.get('mae')}"
    )
