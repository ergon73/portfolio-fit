import tempfile
import unittest
from pathlib import Path

from portfolio_fit.calibration import (
    build_calibration_report,
    load_expert_labels,
    load_model_scores,
    pearson_correlation,
    spearman_correlation,
)


class CalibrationTests(unittest.TestCase):
    def test_correlations_positive_when_rankings_match(self):
        x = [10.0, 20.0, 30.0, 40.0]
        y = [11.0, 19.0, 31.0, 39.0]

        pearson = pearson_correlation(x, y)
        spearman = spearman_correlation(x, y)

        self.assertIsNotNone(pearson)
        self.assertIsNotNone(spearman)
        self.assertGreater(pearson, 0.95)
        self.assertGreater(spearman, 0.95)

    def test_load_and_build_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            labels = root / "labels.csv"
            labels.write_text(
                "repo,expert_score,notes\n"
                "repo-a,40,strong\n"
                "repo-b,20,average\n"
                "repo-c,10,weak\n",
                encoding="utf-8",
            )

            results = root / "results.json"
            results.write_text(
                "[\n"
                '  {"repo": "repo-a", "total_score": 38.0},\n'
                '  {"repo": "repo-b", "total_score": 22.0},\n'
                '  {"repo": "repo-c", "total_score": 15.0}\n'
                "]\n",
                encoding="utf-8",
            )

            label_data = load_expert_labels(labels)
            score_data = load_model_scores(results)
            report = build_calibration_report(
                label_data,
                score_data,
                labels_source=str(labels),
                results_source=str(results),
            )

            self.assertEqual(report["sample_size"], 3)
            self.assertIn("metrics", report)
            self.assertIn("spearman", report["metrics"])
            self.assertIn("pairs", report)
            self.assertEqual(len(report["pairs"]), 3)
            self.assertIn("warnings", report)


if __name__ == "__main__":
    unittest.main()
