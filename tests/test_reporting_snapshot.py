import tempfile
import unittest
from pathlib import Path

from portfolio_fit.reporting import save_text_report

CRITERIA_KEYS = [
    "test_coverage",
    "code_complexity",
    "type_hints",
    "vulnerabilities",
    "dep_health",
    "security_scanning",
    "project_activity",
    "version_stability",
    "changelog",
    "docstrings",
    "logging",
    "structure",
    "readme",
    "api_docs",
    "getting_started",
    "docker",
    "cicd",
]


def build_sample_result() -> dict:
    criteria_meta = {
        key: {
            "max_score": (
                5.0
                if key
                in {
                    "test_coverage",
                    "code_complexity",
                    "type_hints",
                    "vulnerabilities",
                    "project_activity",
                    "docstrings",
                    "readme",
                }
                else 3.0
            ),
            "status": "known",
            "method": "heuristic",
            "confidence": 0.7,
            "note": f"sample note for {key}",
        }
        for key in CRITERIA_KEYS
    }
    criteria_meta["dep_health"]["max_score"] = 3.0
    criteria_meta["security_scanning"]["max_score"] = 2.0
    criteria_meta["version_stability"]["max_score"] = 3.0
    criteria_meta["changelog"]["max_score"] = 2.0
    criteria_meta["logging"]["max_score"] = 3.0
    criteria_meta["structure"]["max_score"] = 2.0
    criteria_meta["api_docs"]["max_score"] = 3.0
    criteria_meta["getting_started"]["max_score"] = 2.0
    criteria_meta["docker"]["max_score"] = 3.0
    criteria_meta["cicd"]["max_score"] = 2.0

    return {
        "repo": "sample-repo",
        "path": "C:/sample/repo",
        "total_score": 27.5,
        "max_score": 50.0,
        "raw_max_score": 60.0,
        "known_score": 33.0,
        "known_max_score": 60.0,
        "data_coverage_percent": 80.0,
        "category": "⭐⭐⭐ Хороший / Good",
        "block1_code_quality": 8.0,
        "block2_security": 5.0,
        "block3_maintenance": 4.0,
        "block4_architecture": 4.0,
        "block5_documentation": 4.5,
        "block6_devops": 2.0,
        "test_coverage": 3.0,
        "code_complexity": 3.0,
        "type_hints": 2.0,
        "vulnerabilities": 2.5,
        "dep_health": 2.0,
        "security_scanning": 0.5,
        "project_activity": 2.0,
        "version_stability": 1.0,
        "changelog": 1.0,
        "docstrings": 2.0,
        "logging": 1.0,
        "structure": 1.0,
        "readme": 2.5,
        "api_docs": 1.0,
        "getting_started": 1.0,
        "docker": 1.0,
        "cicd": 1.0,
        "criteria_meta": criteria_meta,
        "blocks_meta": {
            "block1_code_quality": {
                "score": 8.0,
                "known_score": 8.0,
                "known_max": 15.0,
                "max_score": 15.0,
                "data_coverage_percent": 100.0,
            },
            "block2_security": {
                "score": 5.0,
                "known_score": 5.0,
                "known_max": 10.0,
                "max_score": 10.0,
                "data_coverage_percent": 100.0,
            },
            "block3_maintenance": {
                "score": 4.0,
                "known_score": 4.0,
                "known_max": 10.0,
                "max_score": 10.0,
                "data_coverage_percent": 100.0,
            },
            "block4_architecture": {
                "score": 4.0,
                "known_score": 4.0,
                "known_max": 10.0,
                "max_score": 10.0,
                "data_coverage_percent": 100.0,
            },
            "block5_documentation": {
                "score": 4.5,
                "known_score": 4.5,
                "known_max": 10.0,
                "max_score": 10.0,
                "data_coverage_percent": 100.0,
            },
            "block6_devops": {
                "score": 2.0,
                "known_score": 2.0,
                "known_max": 5.0,
                "max_score": 5.0,
                "data_coverage_percent": 100.0,
            },
        },
    }


class ReportingSnapshotTests(unittest.TestCase):
    def test_report_excerpt_snapshot(self):
        snapshot_path = Path("tests/snapshots/report_excerpt_snapshot.txt")
        expected_excerpt = (
            snapshot_path.read_text(encoding="utf-8").replace("\r\n", "\n").strip()
        )

        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path.cwd()
            try:
                # Write report into temporary workspace to avoid polluting repository.
                import os

                os.chdir(tmp)
                report_file = save_text_report(
                    [build_sample_result()], github_username="snapshot-user"
                )
                content = (
                    Path(report_file).read_text(encoding="utf-8").replace("\r\n", "\n")
                )
            finally:
                os.chdir(cwd)

        excerpt = "\n".join(content.splitlines()[:18]).strip()
        self.assertEqual(excerpt, expected_excerpt)


if __name__ == "__main__":
    unittest.main()
