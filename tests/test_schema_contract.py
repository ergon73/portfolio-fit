import tempfile
import unittest
from pathlib import Path

from portfolio_fit.reporting import enrich_result_with_insights
from portfolio_fit.schema_contract import (
    CRITERION_KEYS,
    RESULT_REQUIRED_FIELDS,
    build_portfolio_evaluation_schema,
    validate_results_contract,
)
from portfolio_fit.scoring import EnhancedRepositoryEvaluator


class SchemaContractTests(unittest.TestCase):
    def _build_enriched_result(self) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir(parents=True, exist_ok=True)
            (repo / ".git").mkdir()
            (repo / "main.py").write_text(
                "def add(a: int, b: int) -> int:\n    return a + b\n",
                encoding="utf-8",
            )
            evaluator = EnhancedRepositoryEvaluator(repo)
            result = evaluator.evaluate_all()
            return enrich_result_with_insights(result)

    def test_schema_contains_expected_required_fields(self):
        schema = build_portfolio_evaluation_schema()
        self.assertEqual(schema.get("type"), "array")
        item_schema = schema.get("items", {})
        required = item_schema.get("required", [])
        self.assertTrue(all(field in required for field in RESULT_REQUIRED_FIELDS))
        for criterion in CRITERION_KEYS:
            self.assertIn(
                criterion,
                item_schema.get("properties", {}),
            )

    def test_validation_passes_for_real_enriched_result(self):
        enriched = self._build_enriched_result()
        errors = validate_results_contract([enriched])
        self.assertEqual(errors, [])

    def test_validation_reports_missing_required_field(self):
        enriched = self._build_enriched_result()
        enriched.pop("total_score", None)
        errors = validate_results_contract([enriched])
        self.assertTrue(
            any("missing required field 'total_score'" in error for error in errors)
        )

    def test_validation_reports_out_of_range_coverage(self):
        enriched = self._build_enriched_result()
        enriched["data_coverage_percent"] = 120.0
        errors = validate_results_contract([enriched])
        self.assertTrue(
            any(
                "field 'data_coverage_percent' must be in [0, 100]" in error
                for error in errors
            )
        )


if __name__ == "__main__":
    unittest.main()
