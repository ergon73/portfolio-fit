import json
import tempfile
import unittest
from pathlib import Path

from enhanced_evaluate_portfolio import (
    EnhancedRepositoryEvaluator,
    discover_python_repos,
)


class ScoringEngineTests(unittest.TestCase):
    def test_make_result_clamps_values_and_handles_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            evaluator = EnhancedRepositoryEvaluator(Path(tmp))
            docker_max = float(evaluator.constants.CRITERION_MAX_SCORES["docker"])

            clamped = evaluator._make_result("docker", 99.0, method="heuristic")
            self.assertEqual(clamped.score, docker_max)
            self.assertEqual(clamped.status, "known")
            self.assertEqual(clamped.max_score, docker_max)

            unknown = evaluator._make_result(
                "docker", None, method="heuristic", note="no data"
            )
            self.assertIsNone(unknown.score)
            self.assertEqual(unknown.status, "unknown")
            self.assertEqual(unknown.confidence, 0.0)
            self.assertEqual(unknown.note, "no data")

    def test_vulnerability_score_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            evaluator = EnhancedRepositoryEvaluator(Path(tmp))
            self.assertEqual(evaluator._vuln_count_to_score(0), 5.0)
            self.assertEqual(evaluator._vuln_count_to_score(2), 4.0)
            self.assertEqual(evaluator._vuln_count_to_score(3), 3.0)
            self.assertEqual(evaluator._vuln_count_to_score(8), 2.0)
            self.assertEqual(evaluator._vuln_count_to_score(11), 0.0)

    def test_pip_audit_parser_supports_common_shapes(self):
        with tempfile.TemporaryDirectory() as tmp:
            evaluator = EnhancedRepositoryEvaluator(Path(tmp))

            list_shape = json.dumps(
                [
                    {
                        "name": "a",
                        "version": "1.0",
                        "vulns": [{"id": "X"}, {"id": "Y"}],
                    },
                    {"name": "b", "version": "2.0", "vulns": []},
                ]
            )
            self.assertEqual(evaluator._count_pip_audit_vulns(list_shape), 2)

            dict_shape = json.dumps(
                {
                    "dependencies": [
                        {"name": "a", "vulns": [{"id": "X"}]},
                        {"name": "b", "vulnerabilities": [{"id": "Y"}, {"id": "Z"}]},
                    ]
                }
            )
            self.assertEqual(evaluator._count_pip_audit_vulns(dict_shape), 3)

    def test_evaluate_vulnerabilities_uses_local_pip_audit_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "requirements.txt").write_text(
                "requests==2.31.0\n", encoding="utf-8"
            )
            (repo / "pip-audit-report.json").write_text(
                json.dumps(
                    [
                        {
                            "name": "requests",
                            "version": "2.31.0",
                            "vulns": [{"id": "A"}, {"id": "B"}, {"id": "C"}],
                        }
                    ]
                ),
                encoding="utf-8",
            )

            evaluator = EnhancedRepositoryEvaluator(repo)
            result = evaluator.evaluate_vulnerabilities()

            self.assertEqual(result.method, "measured")
            self.assertEqual(result.status, "known")
            self.assertEqual(result.score, 3.0)
            self.assertIn("pip-audit report vulnerabilities: 3", result.note)

    def test_evaluate_test_coverage_reads_coverage_xml(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            coverage_xml = """<?xml version="1.0" ?>
<coverage branch-rate="0" line-rate="0.81" version="7.0"></coverage>
"""
            (repo / "coverage.xml").write_text(coverage_xml, encoding="utf-8")

            evaluator = EnhancedRepositoryEvaluator(repo)
            result = evaluator.evaluate_test_coverage()

            self.assertEqual(result.method, "measured")
            self.assertEqual(result.status, "known")
            self.assertEqual(result.score, 5.0)
            self.assertIn("coverage report found", result.note)

    def test_evaluate_all_returns_bounded_score_and_full_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "README.md").write_text(
                "# Test project\n\nUsage example\n", encoding="utf-8"
            )
            (repo / "main.py").write_text(
                "def add(x: int, y: int) -> int:\n"
                '    """Add numbers."""\n'
                "    return x + y\n",
                encoding="utf-8",
            )

            evaluator = EnhancedRepositoryEvaluator(repo)
            result = evaluator.evaluate_all()

            self.assertGreaterEqual(result["total_score"], 0.0)
            self.assertLessEqual(result["total_score"], 50.0)
            self.assertGreaterEqual(result["data_coverage_percent"], 0.0)
            self.assertLessEqual(result["data_coverage_percent"], 100.0)
            self.assertEqual(len(result["criteria_meta"]), 17)
            self.assertIn("blocks_meta", result)
            self.assertIn("block1_code_quality", result["blocks_meta"])
            self.assertIn("data_quality_warnings", result)
            self.assertIsInstance(result["data_quality_warnings"], list)
            self.assertIn(result["data_quality_status"], {"green", "yellow", "red"})

    def test_discover_python_repos_top_level_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            top_repo = root / "repo_top"
            nested_repo = root / "group" / "repo_nested"

            (top_repo / ".git").mkdir(parents=True)
            (top_repo / "main.py").write_text("print('ok')\n", encoding="utf-8")

            (nested_repo / ".git").mkdir(parents=True)
            (nested_repo / "main.py").write_text("print('nested')\n", encoding="utf-8")

            discovered = discover_python_repos(root, recursive=False)
            self.assertEqual([p.name for p in discovered], ["repo_top"])

    def test_discover_python_repos_recursive_finds_nested(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            top_repo = root / "repo_top"
            nested_repo = root / "mono" / "services" / "repo_nested"
            non_python_repo = root / "mono" / "static_repo"

            (top_repo / ".git").mkdir(parents=True)
            (top_repo / "src").mkdir(parents=True)
            (top_repo / "src" / "a.py").write_text("print('a')\n", encoding="utf-8")

            (nested_repo / ".git").mkdir(parents=True)
            (nested_repo / "app.py").write_text("print('b')\n", encoding="utf-8")

            (non_python_repo / ".git").mkdir(parents=True)
            (non_python_repo / "README.md").write_text("not python\n", encoding="utf-8")

            discovered = discover_python_repos(root, recursive=True)
            discovered_names = [p.name for p in discovered]
            self.assertIn("repo_top", discovered_names)
            self.assertIn("repo_nested", discovered_names)
            self.assertNotIn("static_repo", discovered_names)


if __name__ == "__main__":
    unittest.main()
