import tempfile
import unittest
from pathlib import Path

from portfolio_fit.job_fit_benchmark import (
    load_jd_files,
    run_job_fit_benchmark,
)


class JobFitBenchmarkTests(unittest.TestCase):
    def test_load_jd_files_reads_txt_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            jd_dir = Path(tmp)
            (jd_dir / "backend.txt").write_text(
                "Must have Python and FastAPI", encoding="utf-8"
            )
            (jd_dir / "devops.txt").write_text(
                "Must have Docker and CI/CD", encoding="utf-8"
            )

            jd_map = load_jd_files(jd_dir)
            self.assertIn("backend", jd_map)
            self.assertIn("devops", jd_map)
            self.assertEqual(len(jd_map), 2)

    def test_run_job_fit_benchmark_returns_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo-a"
            repo_path.mkdir(parents=True)
            (repo_path / "README.md").write_text(
                "Python FastAPI project with Docker and GitHub Actions",
                encoding="utf-8",
            )
            evaluation = [
                {
                    "repo": "repo-a",
                    "path": str(repo_path),
                    "test_coverage": 2.0,
                    "cicd": 1.0,
                    "docker": 2.0,
                    "vulnerabilities": 3.0,
                    "criteria_meta": {},
                }
            ]
            jd_map = {
                "backend": "Must have Python, FastAPI, SQL.",
                "devops": "Must have Docker, CI/CD, Kubernetes.",
            }
            benchmark = run_job_fit_benchmark(evaluation, jd_map)

            self.assertEqual(benchmark["jd_count"], 2)
            self.assertIn("avg_fit_score_percent", benchmark)
            self.assertIn("reports", benchmark)
            self.assertEqual(len(benchmark["reports"]), 2)
            self.assertIn("best_fit", benchmark)
            self.assertIn("worst_fit", benchmark)


if __name__ == "__main__":
    unittest.main()
