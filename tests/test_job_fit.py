import tempfile
import unittest
from pathlib import Path

from portfolio_fit.job_fit import (
    analyze_job_fit,
    extract_skills_from_repo_result,
    parse_job_description,
)


class JobFitTests(unittest.TestCase):
    def test_parse_job_description_extracts_must_nice_and_seniority(self):
        jd = """
        We are looking for a Senior Python backend engineer.
        Must have: FastAPI, Docker, SQL, CI/CD.
        Nice to have: Kubernetes and AWS.
        """
        parsed = parse_job_description(jd)

        self.assertEqual(parsed["seniority"], "senior")
        self.assertIn("python", parsed["must_have"])
        self.assertIn("fastapi", parsed["must_have"])
        self.assertIn("docker", parsed["must_have"])
        self.assertIn("sql", parsed["must_have"])
        self.assertIn("ci_cd", parsed["must_have"])
        self.assertIn("kubernetes", parsed["nice_to_have"])
        self.assertIn("cloud", parsed["nice_to_have"])

    def test_analyze_job_fit_reports_missing_must_have(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo-a"
            repo_path.mkdir(parents=True)
            (repo_path / "README.md").write_text(
                "Python FastAPI service with Docker and GitHub Actions.",
                encoding="utf-8",
            )

            result = {
                "repo": "repo-a",
                "path": str(repo_path),
                "test_coverage": 2.0,
                "cicd": 1.0,
                "docker": 2.0,
                "vulnerabilities": 3.0,
                "criteria_meta": {},
            }

            jd = (
                "Must have Python, FastAPI, SQL and security scanning. "
                "Nice to have Kubernetes."
            )
            report = analyze_job_fit([result], jd)

            self.assertIn("fit_score_percent", report)
            self.assertIn("matching", report)
            self.assertIn("sql", report["matching"]["must_have_missing"])
            self.assertIn("kubernetes", report["matching"]["nice_to_have_missing"])

    def test_extract_skills_from_repo_result_uses_repo_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo-b"
            repo_path.mkdir(parents=True)
            (repo_path / "requirements.txt").write_text(
                "fastapi\nuvicorn\npytest\n", encoding="utf-8"
            )

            result = {
                "repo": "repo-b",
                "path": str(repo_path),
                "cicd": 0.0,
                "docker": 0.0,
                "test_coverage": 0.0,
                "vulnerabilities": 0.0,
            }

            skills = extract_skills_from_repo_result(result)
            self.assertIn("fastapi", skills)
            self.assertIn("python", skills)
            self.assertIn("testing", skills)


if __name__ == "__main__":
    unittest.main()
