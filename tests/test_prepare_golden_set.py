import unittest

from prepare_golden_set import estimate_expert_score, select_stratified


class PrepareGoldenSetTests(unittest.TestCase):
    def test_select_stratified_includes_red_cases(self):
        rows = []
        for i in range(20):
            rows.append(
                {
                    "repo": f"repo-{i}",
                    "total_score": float(i + 1),
                    "data_quality_status": "red" if i < 5 else "green",
                }
            )

        selected = select_stratified(rows, size=10)
        self.assertEqual(len(selected), 10)
        red_count = sum(
            1
            for item in selected
            if str(item.get("data_quality_status", "")).lower() == "red"
        )
        self.assertGreaterEqual(red_count, 4)

    def test_estimate_expert_score_penalizes_red_quality(self):
        green = {
            "total_score": 24.0,
            "data_quality_status": "green",
            "data_coverage_percent": 95.0,
            "cicd": 1.0,
            "readme": 3.0,
            "test_coverage": 3.0,
            "vulnerabilities": 3.0,
        }
        red = dict(green)
        red["data_quality_status"] = "red"

        self.assertLess(estimate_expert_score(red), estimate_expert_score(green))


if __name__ == "__main__":
    unittest.main()
