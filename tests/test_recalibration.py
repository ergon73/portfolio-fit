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
    split_profile_labels_by_stack,
)
from portfolio_fit.scoring import EvaluationConstants


def _build_result(
    repo: str,
    total_score: float,
    stack_profile: str = "python_backend",
) -> dict:
    criteria_meta: dict[str, dict[str, object]] = {}
    result = {
        "repo": repo,
        "total_score": total_score,
        "data_quality_status": "green",
        "data_coverage_percent": 95.0,
        "category": "test",
        "criteria_meta": criteria_meta,
        "stack_profile": stack_profile,
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


def _write_labels_csv(
    labels_path: Path,
    rows: list[dict[str, str]],
) -> None:
    with open(labels_path, "w", encoding="utf-8", newline="") as file:
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
            self.assertEqual(summary["resolved_stack_profile"], "python_backend")
            self.assertTrue(profile_paths.calibration_json.exists())
            self.assertTrue(profile_paths.calibration_txt.exists())
            self.assertTrue(profile_paths.tuning_patch_json.exists())
            self.assertTrue(profile_paths.profile_config_json.exists())
            self.assertTrue(profile_paths.summary_json.exists())
            self.assertTrue(profile_paths.summary_txt.exists())
            self.assertTrue(apply_config_path.exists())
            self.assertTrue(Path(summary["profile_stack_config_json"]).exists())

    def test_run_profile_recalibration_rejects_mixed_auto_strict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "profiles"
            results_path = root / "results.json"

            results = [
                _build_result("backend-a", 12.0, "python_backend"),
                _build_result("backend-b", 18.0, "python_backend"),
                _build_result("frontend-a", 28.0, "python_fullstack_react"),
                _build_result("frontend-b", 34.0, "python_fullstack_react"),
            ]
            results_path.write_text(
                json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
            )

            profile_paths = build_profile_paths(workspace, "mixed-view")
            _write_labels_csv(
                profile_paths.labels_csv,
                [
                    {
                        "repo": item["repo"],
                        "expert_score": f"{float(item['total_score']):.1f}",
                        "model_score": f"{float(item['total_score']):.1f}",
                        "data_quality_status": "green",
                        "data_coverage_percent": "95.0",
                        "category": "test",
                        "label_source": "manual",
                        "notes": "",
                    }
                    for item in results
                ],
            )

            with self.assertRaises(ValueError):
                run_profile_recalibration(
                    profile_paths=profile_paths,
                    results_path=results_path,
                    stack_profile="auto",
                    strict_stack_profile=True,
                )

    def test_run_profile_recalibration_with_explicit_stack_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "profiles"
            results_path = root / "results.json"

            results = [
                _build_result("backend-a", 12.0, "python_backend"),
                _build_result("backend-b", 18.0, "python_backend"),
                _build_result("frontend-a", 28.0, "python_fullstack_react"),
                _build_result("frontend-b", 34.0, "python_fullstack_react"),
            ]
            results_path.write_text(
                json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
            )

            profile_paths = build_profile_paths(workspace, "backend-view")
            _write_labels_csv(
                profile_paths.labels_csv,
                [
                    {
                        "repo": item["repo"],
                        "expert_score": f"{float(item['total_score']):.1f}",
                        "model_score": f"{float(item['total_score']):.1f}",
                        "data_quality_status": "green",
                        "data_coverage_percent": "95.0",
                        "category": "test",
                        "label_source": "manual",
                        "notes": "",
                    }
                    for item in results
                ],
            )

            summary = run_profile_recalibration(
                profile_paths=profile_paths,
                results_path=results_path,
                stack_profile="python_backend",
                strict_stack_profile=True,
            )

            self.assertEqual(summary["resolved_stack_profile"], "python_backend")
            self.assertEqual(summary["sample_size"], 2)
            self.assertEqual(summary["filtered_stack_counts"], {"python_backend": 2})
            self.assertEqual(
                sorted(summary["stack_profile_breakdown"].keys()),
                ["python_backend"],
            )

    def test_split_profile_labels_by_stack(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            labels_path = root / "golden_set.csv"
            results_path = root / "results.json"
            output_dir = root / "by_stack"

            _write_labels_csv(
                labels_path,
                [
                    {
                        "repo": "repo-backend",
                        "expert_score": "10",
                        "model_score": "10",
                        "data_quality_status": "green",
                        "data_coverage_percent": "95.0",
                        "category": "test",
                        "label_source": "manual",
                        "notes": "",
                    },
                    {
                        "repo": "repo-fullstack",
                        "expert_score": "20",
                        "model_score": "20",
                        "data_quality_status": "green",
                        "data_coverage_percent": "95.0",
                        "category": "test",
                        "label_source": "manual",
                        "notes": "",
                    },
                    {
                        "repo": "repo-django",
                        "expert_score": "30",
                        "model_score": "30",
                        "data_quality_status": "green",
                        "data_coverage_percent": "95.0",
                        "category": "test",
                        "label_source": "manual",
                        "notes": "",
                    },
                    {
                        "repo": "repo-node",
                        "expert_score": "40",
                        "model_score": "40",
                        "data_quality_status": "green",
                        "data_coverage_percent": "95.0",
                        "category": "test",
                        "label_source": "manual",
                        "notes": "",
                    },
                ],
            )

            results = [
                _build_result("repo-backend", 10.0, "python_backend"),
                _build_result("repo-fullstack", 20.0, "python_fullstack_react"),
                _build_result("repo-django", 30.0, "python_django_templates"),
                _build_result("repo-node", 40.0, "node_frontend"),
            ]
            results_path.write_text(
                json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
            )

            summary = split_profile_labels_by_stack(
                labels_csv_path=labels_path,
                results_path=results_path,
                output_dir=output_dir,
                include_additional_stacks=True,
            )

            self.assertEqual(summary["groups"]["python_backend"], 1)
            self.assertEqual(summary["groups"]["python_fullstack_react"], 1)
            self.assertEqual(summary["groups"]["django_templates"], 1)
            self.assertEqual(summary["groups"]["node_frontend"], 1)
            self.assertTrue((output_dir / "golden_set_python_backend.csv").exists())
            self.assertTrue(
                (output_dir / "golden_set_python_fullstack_react.csv").exists()
            )
            self.assertTrue((output_dir / "golden_set_django_templates.csv").exists())
            self.assertTrue((output_dir / "golden_set_node_frontend.csv").exists())
            self.assertTrue((output_dir / "split_summary.json").exists())


if __name__ == "__main__":
    unittest.main()
