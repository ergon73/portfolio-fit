import csv
import json
import tempfile
import unittest
from pathlib import Path

from portfolio_fit.recalibration import (
    build_profile_paths,
    prepare_profile_labels,
    run_profile_recalibration,
    slugify_profile_name,
)
from portfolio_fit.scoring import EvaluationConstants


def _build_result(repo: str, total_score: float) -> dict:
    criteria_meta: dict[str, dict[str, object]] = {}
    result = {
        "repo": repo,
        "total_score": total_score,
        "data_quality_status": "green",
        "data_coverage_percent": 95.0,
        "category": "test",
        "criteria_meta": criteria_meta,
    }

    ratio = max(0.0, min(1.0, total_score / 50.0))
    for key, max_score in EvaluationConstants.CRITERION_MAX_SCORES.items():
        score = round(float(max_score) * ratio, 3)
        result[key] = score
        criteria_meta[key] = {
            "max_score": float(max_score),
            "status": "known",
            "method": "measured",
            "confidence": 0.8,
            "note": "",
        }
    return result


class RecalibrationTests(unittest.TestCase):
    def test_slugify_profile_name(self):
        self.assertEqual(
            slugify_profile_name("Recruiter Vision 2026"), "recruiter-vision-2026"
        )
        self.assertEqual(slugify_profile_name(""), "default")

    def test_prepare_and_run_profile_recalibration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "profiles"
            results_path = root / "results.json"
            base_config_path = root / "base_config.json"
            apply_config_path = root / "active" / "scoring_config.json"

            results = [
                _build_result("repo-a", 10.0),
                _build_result("repo-b", 20.0),
                _build_result("repo-c", 30.0),
                _build_result("repo-d", 40.0),
            ]
            results_path.write_text(
                json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            base_config_path.write_text(
                json.dumps({"MIN_CHANGELOG_LENGTH": 500}, indent=2),
                encoding="utf-8",
            )

            profile_paths = build_profile_paths(workspace, "recruiter-view")
            created = prepare_profile_labels(
                results_path=results_path,
                labels_csv_path=profile_paths.labels_csv,
                sample_size=4,
                autofill=False,
                force_overwrite=True,
            )
            self.assertTrue(created)

            rows = []
            with open(
                profile_paths.labels_csv, "r", encoding="utf-8", newline=""
            ) as file:
                reader = csv.DictReader(file)
                for row in reader:
                    row["expert_score"] = row.get("model_score", "0")
                    rows.append(row)

            with open(
                profile_paths.labels_csv, "w", encoding="utf-8", newline=""
            ) as file:
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
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                for row in rows:
                    writer.writerow(row)

            summary = run_profile_recalibration(
                profile_paths=profile_paths,
                results_path=results_path,
                min_samples=2,
                base_config_path=base_config_path,
                apply_to_config_path=apply_config_path,
            )

            self.assertEqual(summary["profile"], "recruiter-view")
            self.assertEqual(summary["sample_size"], 4)
            self.assertTrue(profile_paths.calibration_json.exists())
            self.assertTrue(profile_paths.calibration_txt.exists())
            self.assertTrue(profile_paths.tuning_patch_json.exists())
            self.assertTrue(profile_paths.profile_config_json.exists())
            self.assertTrue(profile_paths.summary_json.exists())
            self.assertTrue(profile_paths.summary_txt.exists())
            self.assertTrue(apply_config_path.exists())


if __name__ == "__main__":
    unittest.main()
