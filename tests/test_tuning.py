import unittest

from portfolio_fit.scoring import EvaluationConstants
from portfolio_fit.tuning import suggest_criterion_max_scores


class TuningTests(unittest.TestCase):
    def test_suggested_scores_preserve_block_totals(self):
        labels = {}
        results_map = {}
        criterion_max = EvaluationConstants.CRITERION_MAX_SCORES

        for i in range(12):
            repo = f"repo-{i}"
            expert_score = 8.0 + i * 3.0
            labels[repo] = expert_score

            criteria_meta = {}
            result = {"repo": repo}
            base_ratio = min(1.0, max(0.0, expert_score / 50.0))

            for key, max_score in criterion_max.items():
                ratio = base_ratio
                if key in {"readme", "cicd"}:
                    ratio = min(1.0, ratio + 0.15)
                elif key in {"changelog", "structure"}:
                    ratio = max(0.0, ratio - 0.1)

                result[key] = round(ratio * max_score, 3)
                criteria_meta[key] = {
                    "max_score": float(max_score),
                    "status": "known",
                    "method": "measured",
                    "confidence": 0.8,
                    "note": "",
                }

            result["criteria_meta"] = criteria_meta
            results_map[repo] = result

        report = suggest_criterion_max_scores(
            labels=labels, results_map=results_map, min_samples=6
        )

        self.assertEqual(report["sample_size"], 12)
        suggested = report["suggested_criterion_max_scores"]
        self.assertEqual(set(suggested), set(criterion_max))

        for block, block_total in EvaluationConstants.BLOCK_MAX_SCORES.items():
            block_criteria = [
                key
                for key, criterion_block in EvaluationConstants.CRITERION_BLOCK.items()
                if criterion_block == block
            ]
            total = sum(suggested[key] for key in block_criteria)
            self.assertAlmostEqual(total, float(block_total), places=2)


if __name__ == "__main__":
    unittest.main()
