import json
import tempfile
import unittest
from pathlib import Path

from enhanced_evaluate_portfolio import (
    EnhancedRepositoryEvaluator,
    discover_python_repos,
)
from portfolio_fit.discovery import discover_supported_repos
from portfolio_fit.scoring import detect_stack_profile


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

    def test_evaluate_vulnerabilities_uses_local_npm_audit_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "package.json").write_text(
                '{"name":"frontend","version":"1.0.0","dependencies":{"react":"18.2.0"}}',
                encoding="utf-8",
            )
            (repo / "npm-audit-report.json").write_text(
                json.dumps(
                    {
                        "metadata": {
                            "vulnerabilities": {
                                "info": 0,
                                "low": 1,
                                "moderate": 2,
                                "high": 1,
                                "critical": 0,
                                "total": 4,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            evaluator = EnhancedRepositoryEvaluator(repo, stack_profile="node_frontend")
            result = evaluator.evaluate_vulnerabilities()

            self.assertEqual(result.method, "measured")
            self.assertEqual(result.status, "known")
            self.assertEqual(result.score, 3.0)
            self.assertIn("npm audit report vulnerabilities: 4", result.note)

    def test_evaluate_dependency_health_uses_package_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "package.json").write_text(
                json.dumps(
                    {
                        "name": "frontend",
                        "version": "1.0.0",
                        "dependencies": {"react": "18.2.0", "axios": "1.6.0"},
                        "devDependencies": {
                            "typescript": "5.2.0",
                            "vite": "5.0.0",
                            "vitest": "1.0.0",
                        },
                    }
                ),
                encoding="utf-8",
            )
            evaluator = EnhancedRepositoryEvaluator(repo, stack_profile="node_frontend")
            result = evaluator.evaluate_dependency_health()

            self.assertEqual(result.status, "known")
            self.assertEqual(result.method, "measured")
            self.assertEqual(
                result.score, evaluator.constants.CRITERION_MAX_SCORES["dep_health"]
            )
            self.assertIn("dependency entries counted (node): 5", result.note)

    def test_getting_started_scores_package_scripts_quality(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "package.json").write_text(
                json.dumps(
                    {
                        "name": "frontend",
                        "version": "1.0.0",
                        "scripts": {
                            "lint": "eslint src",
                            "test": "vitest",
                            "build": "vite build",
                            "typecheck": "tsc --noEmit",
                        },
                    }
                ),
                encoding="utf-8",
            )
            evaluator = EnhancedRepositoryEvaluator(repo, stack_profile="node_frontend")
            result = evaluator.evaluate_getting_started()

            self.assertEqual(result.status, "known")
            self.assertEqual(result.method, "heuristic")
            self.assertEqual(
                result.score,
                evaluator.constants.CRITERION_MAX_SCORES["getting_started"],
            )
            self.assertIn("package scripts:", result.note)

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

    def test_evaluate_test_coverage_reads_frontend_coverage_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "coverage").mkdir(parents=True, exist_ok=True)
            (repo / "coverage" / "coverage-summary.json").write_text(
                json.dumps({"total": {"lines": {"pct": 76.2}}}),
                encoding="utf-8",
            )

            evaluator = EnhancedRepositoryEvaluator(repo, stack_profile="node_frontend")
            result = evaluator.evaluate_test_coverage()

            self.assertEqual(result.method, "measured")
            self.assertEqual(result.status, "known")
            self.assertEqual(result.score, 4.0)
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
            self.assertIn("frontend_quality", result)
            self.assertIn("frontend_quality_meta", result)
            self.assertIsInstance(result["frontend_quality_meta"], dict)
            self.assertIn(
                result["frontend_quality_meta"].get("status"),
                {"known", "unknown", "not_applicable"},
            )
            self.assertIn("data_layer_quality", result)
            self.assertIn("data_layer_quality_meta", result)
            self.assertIsInstance(result["data_layer_quality_meta"], dict)
            self.assertIn("api_contract_maturity", result)
            self.assertIn("api_contract_maturity_meta", result)
            self.assertIsInstance(result["api_contract_maturity_meta"], dict)
            self.assertIn("fullstack_maturity", result)
            self.assertIn("fullstack_maturity_meta", result)
            self.assertIsInstance(result["fullstack_maturity_meta"], dict)
            self.assertIn("data_quality_warnings", result)
            self.assertIsInstance(result["data_quality_warnings"], list)
            self.assertIn(result["data_quality_status"], {"green", "yellow", "red"})
            self.assertIn(
                result["stack_profile"],
                {
                    "python_backend",
                    "python_fullstack_react",
                    "python_django_templates",
                    "node_frontend",
                    "mixed_unknown",
                },
            )

    def test_frontend_quality_scores_react_typescript_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / ".git").mkdir()
            (repo / "package.json").write_text(
                json.dumps(
                    {
                        "name": "frontend",
                        "version": "1.0.0",
                        "dependencies": {"react": "18.2.0"},
                        "devDependencies": {"tailwindcss": "3.4.0"},
                    }
                ),
                encoding="utf-8",
            )
            (repo / "src").mkdir(parents=True, exist_ok=True)
            (repo / "src" / "App.tsx").write_text(
                "<main><section><img alt='hero' src='/hero.png' /></section></main>\n",
                encoding="utf-8",
            )
            (repo / "index.html").write_text(
                (
                    "<html lang='en'><head>"
                    "<meta charset='utf-8'>"
                    "<meta name='viewport' content='width=device-width, initial-scale=1'>"
                    "<title>Demo</title></head>"
                    "<body><header></header><main></main><footer></footer></body></html>"
                ),
                encoding="utf-8",
            )
            (repo / "src" / "styles.module.css").write_text(
                ":root { --color-primary: #123456; }\n"
                ".hero__title--big { color: var(--color-primary); }\n",
                encoding="utf-8",
            )

            evaluator = EnhancedRepositoryEvaluator(repo, stack_profile="node_frontend")
            result = evaluator.evaluate_all()

            self.assertEqual(result["frontend_quality_meta"]["status"], "known")
            self.assertIsNotNone(result["frontend_quality"])
            self.assertGreaterEqual(float(result["frontend_quality"]), 3.0)
            self.assertLessEqual(float(result["frontend_quality"]), 5.0)
            self.assertIn("frameworks=", result["frontend_quality_meta"]["note"])

    def test_frontend_quality_handles_django_templates_without_spa_penalty(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / ".git").mkdir()
            (repo / "manage.py").write_text("print('django')\n", encoding="utf-8")
            (repo / "requirements.txt").write_text("Django==5.0.0\n", encoding="utf-8")
            (repo / "templates").mkdir(parents=True, exist_ok=True)
            (repo / "templates" / "base.html").write_text(
                (
                    "<html lang='en'><head><meta charset='utf-8'><title>Site</title></head>"
                    "<body><header></header><main><form><label>Name</label>"
                    "<input aria-label='name' /></form></main><footer></footer></body></html>"
                ),
                encoding="utf-8",
            )
            (repo / "static" / "css").mkdir(parents=True, exist_ok=True)
            (repo / "static" / "css" / "site.css").write_text(
                ":root { --brand: #0a0a0a; }\n.page__title--main { color: var(--brand); }\n",
                encoding="utf-8",
            )

            evaluator = EnhancedRepositoryEvaluator(
                repo, stack_profile="python_django_templates"
            )
            frontend_quality = evaluator.evaluate_frontend_quality()

            self.assertEqual(frontend_quality["status"], "known")
            self.assertIsNotNone(frontend_quality["score"])
            self.assertGreaterEqual(float(frontend_quality["score"]), 2.5)
            self.assertIn("django_templates", frontend_quality["signals"]["frameworks"])

    def test_data_layer_quality_scores_migrations_and_constraints(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / ".git").mkdir()
            (repo / "manage.py").write_text("print('django')\n", encoding="utf-8")
            (repo / "app").mkdir(parents=True, exist_ok=True)
            (repo / "app" / "models.py").write_text(
                (
                    "from django.db import models\n"
                    "class Customer(models.Model):\n"
                    "    email = models.EmailField(unique=True)\n"
                    "    name = models.CharField(max_length=120, db_index=True)\n"
                ),
                encoding="utf-8",
            )
            (repo / "app" / "migrations").mkdir(parents=True, exist_ok=True)
            (repo / "app" / "migrations" / "0001_initial.py").write_text(
                "from django.db import migrations\n",
                encoding="utf-8",
            )
            (repo / ".env.example").write_text(
                "DATABASE_URL=postgres://demo\nDB_HOST=localhost\n",
                encoding="utf-8",
            )

            evaluator = EnhancedRepositoryEvaluator(repo)
            data_quality = evaluator.evaluate_data_layer_quality()

            self.assertEqual(data_quality["status"], "known")
            self.assertIsNotNone(data_quality["score"])
            self.assertGreaterEqual(float(data_quality["score"]), 2.5)
            self.assertGreaterEqual(data_quality["signals"]["migrations"], 1)
            self.assertTrue(data_quality["signals"]["env_example"])

    def test_api_contract_maturity_scores_openapi_versioning_and_contract_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / ".git").mkdir()
            (repo / "main.py").write_text(
                (
                    "from fastapi import FastAPI\n"
                    "app = FastAPI()\n"
                    "@app.get('/api/v1/users')\n"
                    "def users():\n"
                    "    return []\n"
                ),
                encoding="utf-8",
            )
            (repo / "openapi.yaml").write_text(
                "openapi: 3.0.0\ninfo:\n  title: demo\n  version: 1.0.0\n",
                encoding="utf-8",
            )
            (repo / "tests").mkdir(parents=True, exist_ok=True)
            (repo / "tests" / "test_contract_schema.py").write_text(
                "def test_contract():\n    assert True\n",
                encoding="utf-8",
            )
            (repo / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
            (repo / ".github" / "workflows" / "ci.yml").write_text(
                (
                    "name: ci\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
                    "    steps:\n      - run: schemathesis run openapi.yaml\n"
                ),
                encoding="utf-8",
            )

            evaluator = EnhancedRepositoryEvaluator(repo)
            api_maturity = evaluator.evaluate_api_contract_maturity()

            self.assertEqual(api_maturity["status"], "known")
            self.assertIsNotNone(api_maturity["score"])
            self.assertGreaterEqual(float(api_maturity["score"]), 3.0)
            self.assertTrue(api_maturity["signals"]["openapi"])
            self.assertTrue(api_maturity["signals"]["versioning"])

    def test_fullstack_maturity_scores_mixed_backend_frontend_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / ".git").mkdir()
            (repo / "backend").mkdir(parents=True, exist_ok=True)
            (repo / "backend" / "api.py").write_text(
                (
                    "from fastapi import APIRouter\n"
                    "from fastapi.middleware.cors import CORSMiddleware\n"
                    "router = APIRouter(prefix='/api')\n"
                ),
                encoding="utf-8",
            )
            (repo / "frontend").mkdir(parents=True, exist_ok=True)
            (repo / "frontend" / "app.ts").write_text(
                "const API_URL='/api/v1'; fetch(API_URL);\n",
                encoding="utf-8",
            )
            (repo / "package.json").write_text(
                json.dumps({"name": "mono", "workspaces": ["frontend"]}),
                encoding="utf-8",
            )
            (repo / "docker-compose.yml").write_text(
                (
                    "services:\n"
                    "  backend:\n    image: python:3.12\n"
                    "  frontend:\n    image: node:20\n"
                    "  db:\n    image: postgres:16\n"
                ),
                encoding="utf-8",
            )
            (repo / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
            (repo / ".github" / "workflows" / "ci.yml").write_text(
                (
                    "jobs:\n  test:\n    steps:\n"
                    "      - run: pytest\n"
                    "      - run: npm test\n"
                ),
                encoding="utf-8",
            )

            evaluator = EnhancedRepositoryEvaluator(
                repo, stack_profile="python_fullstack_react"
            )
            fullstack = evaluator.evaluate_fullstack_maturity()

            self.assertEqual(fullstack["status"], "known")
            self.assertIsNotNone(fullstack["score"])
            self.assertGreaterEqual(float(fullstack["score"]), 3.0)
            self.assertTrue(fullstack["signals"]["compose"])
            self.assertTrue(fullstack["signals"]["mixed_ci"])

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

    def test_discover_supported_repos_includes_frontend_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            py_repo = root / "repo_py"
            fe_repo = root / "repo_fe"

            (py_repo / ".git").mkdir(parents=True)
            (py_repo / "main.py").write_text("print('ok')\n", encoding="utf-8")

            (fe_repo / ".git").mkdir(parents=True)
            (fe_repo / "package.json").write_text(
                '{"name":"fe","version":"1.0.0","dependencies":{"react":"18.0.0"}}',
                encoding="utf-8",
            )

            discovered = discover_supported_repos(root, recursive=False)
            names = [path.name for path in discovered]
            self.assertIn("repo_py", names)
            self.assertIn("repo_fe", names)

    def test_discover_python_repos_includes_notebook_only_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nb_repo = root / "repo_nb"
            (nb_repo / ".git").mkdir(parents=True)
            (nb_repo / "analysis.ipynb").write_text(
                json.dumps(
                    {
                        "cells": [
                            {
                                "cell_type": "code",
                                "source": [
                                    "def add(x: int, y: int) -> int:\n",
                                    "    return x + y\n",
                                ],
                            }
                        ],
                        "metadata": {},
                        "nbformat": 4,
                        "nbformat_minor": 5,
                    }
                ),
                encoding="utf-8",
            )

            discovered = discover_python_repos(root, recursive=False)
            self.assertEqual([path.name for path in discovered], ["repo_nb"])

    def test_detect_stack_profile_for_common_layouts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            backend = root / "backend"
            (backend / ".git").mkdir(parents=True)
            (backend / "main.py").write_text("print('x')\n", encoding="utf-8")
            self.assertEqual(detect_stack_profile(backend), "python_backend")

            fullstack = root / "fullstack"
            (fullstack / ".git").mkdir(parents=True)
            (fullstack / "app.py").write_text("print('x')\n", encoding="utf-8")
            (fullstack / "package.json").write_text(
                '{"name":"full","dependencies":{"react":"18.0.0"}}',
                encoding="utf-8",
            )
            self.assertEqual(detect_stack_profile(fullstack), "python_fullstack_react")

            frontend = root / "frontend"
            (frontend / ".git").mkdir(parents=True)
            (frontend / "package.json").write_text(
                '{"name":"frontend","version":"1.0.0"}', encoding="utf-8"
            )
            self.assertEqual(detect_stack_profile(frontend), "node_frontend")

    def test_detect_stack_profile_notebook_only_repo_is_python_backend(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / ".git").mkdir(parents=True)
            (repo / "eda.ipynb").write_text(
                json.dumps(
                    {
                        "cells": [
                            {
                                "cell_type": "code",
                                "source": [
                                    "print('hello')\n",
                                ],
                            }
                        ],
                        "metadata": {},
                        "nbformat": 4,
                        "nbformat_minor": 5,
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(detect_stack_profile(repo), "python_backend")

    def test_node_frontend_marks_python_specific_criteria_not_applicable(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / ".git").mkdir()
            (repo / "package.json").write_text(
                (
                    '{"name":"frontend","version":"1.0.0","scripts":{"build":"vite build"},'
                    '"dependencies":{"react":"18.2.0"}}'
                ),
                encoding="utf-8",
            )
            (repo / "tsconfig.json").write_text(
                '{"compilerOptions":{"strict":true,"noImplicitAny":true,"strictNullChecks":true}}',
                encoding="utf-8",
            )
            (repo / "src").mkdir(parents=True, exist_ok=True)
            (repo / "src" / "app.ts").write_text(
                "export const answer: number = 42;\n", encoding="utf-8"
            )
            (repo / "README.md").write_text("# Frontend\n", encoding="utf-8")
            (repo / "npm-audit-report.json").write_text(
                json.dumps({"metadata": {"vulnerabilities": {"total": 0}}}),
                encoding="utf-8",
            )

            evaluator = EnhancedRepositoryEvaluator(repo, stack_profile="node_frontend")
            result = evaluator.evaluate_all()

            criteria_meta = result["criteria_meta"]
            self.assertEqual(result["stack_profile"], "node_frontend")
            self.assertEqual(
                criteria_meta["code_complexity"]["status"], "not_applicable"
            )
            self.assertEqual(criteria_meta["type_hints"]["status"], "known")
            self.assertEqual(criteria_meta["vulnerabilities"]["status"], "known")
            self.assertEqual(criteria_meta["docstrings"]["status"], "not_applicable")
            self.assertEqual(criteria_meta["api_docs"]["status"], "not_applicable")
            self.assertLessEqual(result["data_coverage_percent"], 100.0)

    def test_type_hints_for_tsconfig_strictness(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "package.json").write_text(
                '{"name":"frontend","version":"1.0.0"}', encoding="utf-8"
            )
            (repo / "tsconfig.json").write_text(
                '{"compilerOptions":{"strict":true,"noImplicitAny":true,"strictNullChecks":true}}',
                encoding="utf-8",
            )
            (repo / "src").mkdir(parents=True, exist_ok=True)
            (repo / "src" / "index.ts").write_text(
                "export const x: number = 1;\n", encoding="utf-8"
            )

            evaluator = EnhancedRepositoryEvaluator(repo, stack_profile="node_frontend")
            result = evaluator.evaluate_type_hints()

            self.assertEqual(result.status, "known")
            self.assertEqual(result.method, "measured")
            self.assertEqual(result.score, 5.0)
            self.assertIn("tsconfig strictness", result.note)

    def test_type_hints_js_only_is_not_applicable(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "package.json").write_text(
                '{"name":"frontend","version":"1.0.0"}', encoding="utf-8"
            )
            (repo / "src").mkdir(parents=True, exist_ok=True)
            (repo / "src" / "index.js").write_text(
                "export const x = 1;\n", encoding="utf-8"
            )

            evaluator = EnhancedRepositoryEvaluator(repo, stack_profile="node_frontend")
            result = evaluator.evaluate_type_hints()

            self.assertEqual(result.status, "not_applicable")
            self.assertIsNone(result.score)

    def test_type_hints_uses_jupyter_notebook_code_cells(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "analysis.ipynb").write_text(
                json.dumps(
                    {
                        "cells": [
                            {
                                "cell_type": "code",
                                "source": [
                                    "%matplotlib inline\n",
                                    "def add(x: int, y: int) -> int:\n",
                                    "    return x + y\n",
                                ],
                            }
                        ],
                        "metadata": {},
                        "nbformat": 4,
                        "nbformat_minor": 5,
                    }
                ),
                encoding="utf-8",
            )

            evaluator = EnhancedRepositoryEvaluator(repo)
            result = evaluator.evaluate_type_hints()

            self.assertEqual(result.status, "known")
            self.assertEqual(result.method, "measured")
            self.assertEqual(result.score, 5.0)
            self.assertIn("hinted functions: 1/1", result.note)


if __name__ == "__main__":
    unittest.main()
