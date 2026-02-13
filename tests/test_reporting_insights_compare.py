import unittest
from typing import Any, Dict

from portfolio_fit.reporting import (
    build_comparison,
    build_portfolio_quick_fixes,
    enrich_result_with_insights,
)


def make_result(
    repo: str,
    total_score: float,
    coverage: float,
    test_coverage_score: float,
    cicd_score: float,
) -> Dict[str, Any]:
    return {
        "repo": repo,
        "total_score": total_score,
        "data_coverage_percent": coverage,
        "category": "⭐⭐⭐ Хороший / Good",
        "test_coverage": test_coverage_score,
        "cicd": cicd_score,
        "criteria_meta": {
            "test_coverage": {
                "max_score": 5.0,
                "status": "known",
                "method": "measured",
                "confidence": 0.9,
                "note": f"coverage signal for {repo}",
            },
            "cicd": {
                "max_score": 2.0,
                "status": "known",
                "method": "heuristic",
                "confidence": 0.7,
                "note": f"cicd signal for {repo}",
            },
        },
        "blocks_meta": {},
    }


class ReportingInsightsCompareTests(unittest.TestCase):
    def test_enrich_result_adds_explainability_recommendations_and_quick_fixes(self):
        raw = make_result(
            repo="demo",
            total_score=18.0,
            coverage=75.0,
            test_coverage_score=2.0,
            cicd_score=0.0,
        )
        enriched = enrich_result_with_insights(raw)

        self.assertIn("criteria_explainability", enriched)
        self.assertIn("recommendations", enriched)
        self.assertIn("quick_fixes", enriched)
        self.assertIn("test_coverage", enriched["criteria_explainability"])

        rec_criteria = [item["criterion"] for item in enriched["recommendations"]]
        self.assertIn("test_coverage", rec_criteria)
        self.assertIn("cicd", rec_criteria)
        self.assertTrue(enriched["quick_fixes"])

        matrix = build_portfolio_quick_fixes([enriched])
        self.assertTrue(matrix)
        matrix_criteria = [row["criterion"] for row in matrix]
        self.assertIn("cicd", matrix_criteria)

    def test_build_comparison_reports_improved_new_and_removed(self):
        previous_results = [
            make_result("repo-a", 20.0, 60.0, test_coverage_score=2.0, cicd_score=0.0),
            make_result("repo-b", 21.0, 55.0, test_coverage_score=2.5, cicd_score=0.0),
        ]
        current_results = [
            make_result("repo-a", 25.0, 75.0, test_coverage_score=4.0, cicd_score=1.5),
            make_result("repo-c", 19.0, 70.0, test_coverage_score=3.0, cicd_score=0.5),
        ]

        comparison = build_comparison(
            previous_results, current_results, baseline_source="baseline.json"
        )

        summary = comparison["summary"]
        self.assertEqual(summary["comparable"], 1)
        self.assertEqual(summary["improved"], 1)
        self.assertEqual(summary["declined"], 0)
        self.assertEqual(summary["new"], 1)
        self.assertEqual(summary["removed"], 1)

        repo_a = next(item for item in comparison["repos"] if item["repo"] == "repo-a")
        self.assertEqual(repo_a["status"], "improved")
        self.assertEqual(repo_a["delta_score"], 5.0)
        delta_keys = [delta["criterion"] for delta in repo_a["criterion_deltas"]]
        self.assertIn("test_coverage", delta_keys)


if __name__ == "__main__":
    unittest.main()
