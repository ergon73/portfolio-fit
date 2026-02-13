# Scoring engine extracted from enhanced_evaluate_portfolio.py

import ast
import json
import logging
import re
import shutil
import subprocess
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Настройка логирования / Logging configuration
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class CriterionResult:
    """Результат одного критерия / Single criterion result"""

    score: Optional[float]
    max_score: float
    status: str  # known | unknown
    method: str  # measured | heuristic
    confidence: float  # 0..1
    note: str = ""


# Константы / Constants
class EvaluationConstants:
    """Константы для оценки / Evaluation constants"""

    # Минимальная длина CHANGELOG / Minimum CHANGELOG length
    MIN_CHANGELOG_LENGTH = 500

    # Минимальная длина README / Minimum README length
    MIN_README_LENGTH_FULL = 500
    MIN_README_LENGTH_PARTIAL = 200

    # Пороги для зависимостей / Dependency thresholds
    MAX_HEALTHY_DEPENDENCIES = 20
    MEDIUM_DEPENDENCIES = 50
    HIGH_DEPENDENCIES = 100

    # Пороги для покрытия / Coverage thresholds
    COVERAGE_EXCELLENT = 90
    COVERAGE_GOOD = 70
    COVERAGE_MEDIUM = 50
    COVERAGE_LOW = 30

    # Пороги для активности (дни) / Activity thresholds (days)
    ACTIVITY_VERY_ACTIVE = 7
    ACTIVITY_ACTIVE = 30
    ACTIVITY_MODERATE = 90
    ACTIVITY_LOW = 180

    # Максимальные баллы блоков / Block max scores
    BLOCK_MAX_SCORES = OrderedDict(
        {
            "block1_code_quality": 15.0,
            "block2_security": 10.0,
            "block3_maintenance": 10.0,
            "block4_architecture": 10.0,
            "block5_documentation": 10.0,
            "block6_devops": 5.0,
        }
    )

    # Максимальные баллы критериев / Criterion max scores
    CRITERION_MAX_SCORES = {
        "test_coverage": 5.0,
        "code_complexity": 5.0,
        "type_hints": 5.0,
        "vulnerabilities": 5.0,
        "dep_health": 3.0,
        "security_scanning": 2.0,
        "project_activity": 5.0,
        "version_stability": 3.0,
        "changelog": 2.0,
        "docstrings": 5.0,
        "logging": 3.0,
        "structure": 2.0,
        "readme": 5.0,
        "api_docs": 3.0,
        "getting_started": 2.0,
        "docker": 3.0,
        "cicd": 2.0,
    }

    # Привязка критериев к блокам / Criterion to block mapping
    CRITERION_BLOCK = {
        "test_coverage": "block1_code_quality",
        "code_complexity": "block1_code_quality",
        "type_hints": "block1_code_quality",
        "vulnerabilities": "block2_security",
        "dep_health": "block2_security",
        "security_scanning": "block2_security",
        "project_activity": "block3_maintenance",
        "version_stability": "block3_maintenance",
        "changelog": "block3_maintenance",
        "docstrings": "block4_architecture",
        "logging": "block4_architecture",
        "structure": "block4_architecture",
        "readme": "block5_documentation",
        "api_docs": "block5_documentation",
        "getting_started": "block5_documentation",
        "docker": "block6_devops",
        "cicd": "block6_devops",
    }

    # Базовый метод расчета / Default calculation method
    CRITERION_METHOD = {
        "test_coverage": "measured",
        "code_complexity": "measured",
        "type_hints": "measured",
        "vulnerabilities": "heuristic",
        "dep_health": "measured",
        "security_scanning": "heuristic",
        "project_activity": "measured",
        "version_stability": "measured",
        "changelog": "heuristic",
        "docstrings": "measured",
        "logging": "heuristic",
        "structure": "heuristic",
        "readme": "heuristic",
        "api_docs": "heuristic",
        "getting_started": "heuristic",
        "docker": "heuristic",
        "cicd": "heuristic",
    }

    # Итоговая шкала / Total max score
    TOTAL_MAX_SCORE = 50.0
    RAW_TOTAL_MAX_SCORE = float(sum(CRITERION_MAX_SCORES.values()))

    # Таймауты внешних инструментов (сек) / External tool timeouts (sec)
    SECURITY_TOOL_TIMEOUT_SEC = 60


def _apply_external_scoring_config() -> None:
    """
    Загружает внешний JSON-конфиг и применяет известные параметры.
    Loads external JSON config and applies known parameters.
    """
    config_path = Path(__file__).with_name("scoring_config.json")
    if not config_path.exists():
        return

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as e:
        logger.warning(f"Failed to read scoring config '{config_path}': {e}")
        return

    if not isinstance(data, dict):
        logger.warning(f"Scoring config '{config_path}' must be a JSON object")
        return

    # Dict-like settings
    for dict_attr in (
        "BLOCK_MAX_SCORES",
        "CRITERION_MAX_SCORES",
        "CRITERION_BLOCK",
        "CRITERION_METHOD",
    ):
        cfg_val = data.get(dict_attr)
        current_val = getattr(EvaluationConstants, dict_attr, None)
        if isinstance(cfg_val, dict) and isinstance(current_val, dict):
            merged = current_val.copy()
            merged.update(cfg_val)
            setattr(EvaluationConstants, dict_attr, merged)

    # Scalar settings
    for key, value in data.items():
        if key in (
            "BLOCK_MAX_SCORES",
            "CRITERION_MAX_SCORES",
            "CRITERION_BLOCK",
            "CRITERION_METHOD",
        ):
            continue
        if hasattr(EvaluationConstants, key):
            setattr(EvaluationConstants, key, value)

    # Keep derived total in sync with effective criterion max values
    try:
        EvaluationConstants.RAW_TOTAL_MAX_SCORE = float(
            sum(EvaluationConstants.CRITERION_MAX_SCORES.values())
        )
    except Exception as e:
        logger.warning(f"Failed to recompute RAW_TOTAL_MAX_SCORE from config: {e}")


_apply_external_scoring_config()


class EnhancedRepositoryEvaluator:
    """
    Расширенный оценивающий класс с 18 критериями
    Enhanced evaluator class with 18 criteria
    """

    def __init__(self, repo_path: Path):
        self.repo_path = Path(repo_path)
        self.repo_name = self.repo_path.name
        self.constants = EvaluationConstants()

    def check_file_exists(self, *patterns) -> bool:
        """
        Проверяет наличие файлов по паттернам или директорий
        Checks for files by patterns or directories
        """
        for pattern in patterns:
            # Если паттерн заканчивается на / - это директория
            # If pattern ends with / - it's a directory
            if pattern.endswith("/"):
                dir_name = pattern.rstrip("/")
                if (self.repo_path / dir_name).is_dir():
                    return True
            # Проверяем через glob для файлов
            # Check via glob for files
            elif list(self.repo_path.glob(pattern)):
                return True
        return False

    def check_content_contains(self, file_pattern: str, keywords: List[str]) -> bool:
        """
        Проверяет содержит ли файл ключевые слова
        Checks if file contains keywords
        """
        try:
            for file_path in self.repo_path.glob(file_pattern):
                content = file_path.read_text(errors="ignore").lower()
                if any(kw.lower() in content for kw in keywords):
                    return True
        except (IOError, OSError, PermissionError) as e:
            logger.warning(f"Error reading file {file_pattern}: {e}")
        return False

    def _make_result(
        self,
        key: str,
        score: Optional[float],
        status: str = "known",
        method: Optional[str] = None,
        confidence: Optional[float] = None,
        note: str = "",
    ) -> CriterionResult:
        """
        Стандартизированный результат критерия
        Standardized criterion result
        """
        max_score = float(self.constants.CRITERION_MAX_SCORES[key])
        resolved_method = method or self.constants.CRITERION_METHOD.get(
            key, "heuristic"
        )

        if score is None:
            status = "unknown"
            resolved_confidence = (
                0.0 if confidence is None else max(0.0, min(float(confidence), 1.0))
            )
            return CriterionResult(
                score=None,
                max_score=max_score,
                status=status,
                method=resolved_method,
                confidence=resolved_confidence,
                note=note,
            )

        normalized_score = max(0.0, min(float(score), max_score))
        if confidence is None:
            confidence = 0.85 if resolved_method == "measured" else 0.6
        resolved_confidence = max(0.0, min(float(confidence), 1.0))

        return CriterionResult(
            score=normalized_score,
            max_score=max_score,
            status=status,
            method=resolved_method,
            confidence=resolved_confidence,
            note=note,
        )

    def _iter_python_files(self, include_tests: bool = True) -> List[Path]:
        """
        Возвращает Python-файлы проекта с фильтрацией служебных директорий.
        Returns project Python files with service-directory filtering.
        """
        excluded_dirs = {
            ".git",
            ".hg",
            ".svn",
            ".venv",
            "venv",
            "env",
            "__pycache__",
            "site-packages",
            "dist",
            "build",
            ".mypy_cache",
            ".pytest_cache",
            ".tox",
            "node_modules",
        }
        result: List[Path] = []
        for py_file in self.repo_path.rglob("*.py"):
            try:
                rel_parts = py_file.relative_to(self.repo_path).parts
            except ValueError:
                continue

            if any(part in excluded_dirs for part in rel_parts):
                continue

            if not include_tests:
                if "tests" in rel_parts or py_file.name.startswith("test_"):
                    continue

            result.append(py_file)
        return result

    def _python_content_contains(
        self, keywords: List[str], include_tests: bool = True
    ) -> bool:
        """
        Проверяет наличие ключевых слов в Python-коде проекта.
        Checks keyword presence across project Python code.
        """
        lowered = [kw.lower() for kw in keywords]
        for py_file in self._iter_python_files(include_tests=include_tests):
            try:
                content = py_file.read_text(errors="ignore").lower()
            except (IOError, OSError, PermissionError):
                continue
            if any(kw in content for kw in lowered):
                return True
        return False

    def _extract_coverage_percent(self) -> Optional[float]:
        """
        Пытается извлечь % покрытия из coverage-артефактов.
        Tries to extract coverage percentage from coverage artifacts.
        """
        # coverage.xml
        coverage_xml = self.repo_path / "coverage.xml"
        if coverage_xml.exists():
            try:
                import xml.etree.ElementTree as ET  # stdlib

                root = ET.parse(coverage_xml).getroot()
                line_rate = root.attrib.get("line-rate")
                if line_rate is not None:
                    return float(line_rate) * 100.0
            except (ValueError, IOError, OSError, ET.ParseError) as e:
                logger.warning(f"Error parsing coverage.xml: {e}")

        # htmlcov/status.json
        status_json = self.repo_path / "htmlcov" / "status.json"
        if status_json.exists():
            try:
                data = json.loads(status_json.read_text(errors="ignore"))
                totals = data.get("totals", {}) if isinstance(data, dict) else {}
                if isinstance(totals, dict):
                    if "percent_covered" in totals:
                        return float(totals["percent_covered"])
                    display_val = totals.get("percent_covered_display")
                    if display_val is not None:
                        return float(str(display_val).replace("%", "").strip())
            except (ValueError, IOError, OSError, TypeError) as e:
                logger.warning(f"Error parsing htmlcov/status.json: {e}")

        return None

    def _run_tool(
        self, command: List[str], timeout_sec: int
    ) -> Tuple[bool, str, str, Optional[str]]:
        """
        Безопасный запуск внешнего инструмента с таймаутом.
        Safe external tool runner with timeout.
        """
        try:
            result = subprocess.run(
                command,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )
            return result.returncode == 0, result.stdout, result.stderr, None
        except subprocess.TimeoutExpired:
            return False, "", "", f"timeout after {timeout_sec}s"
        except FileNotFoundError:
            return False, "", "", "tool not found"
        except (subprocess.SubprocessError, OSError) as e:
            return False, "", "", f"{type(e).__name__}: {e}"

    @staticmethod
    def _count_pip_audit_vulns(raw_output: str) -> Optional[int]:
        """
        Пытается извлечь количество уязвимостей из JSON pip-audit.
        Tries to extract vulnerability count from pip-audit JSON output.
        """
        try:
            data = json.loads(raw_output)
        except (ValueError, TypeError):
            return None

        total = 0
        if isinstance(data, list):
            # Expected shapes:
            # [{"name": "...", "version": "...", "vulns": [...]}]
            # [{"name": "...", "vulnerabilities": [...]}]
            for item in data:
                if isinstance(item, dict):
                    vulns = item.get("vulns")
                    if isinstance(vulns, list):
                        total += len(vulns)
                    else:
                        vulnerabilities = item.get("vulnerabilities")
                        if isinstance(vulnerabilities, list):
                            total += len(vulnerabilities)
        elif isinstance(data, dict):
            # Alternative shape: {"dependencies": [{"vulns": [...]}]}
            deps = data.get("dependencies")
            if isinstance(deps, list):
                for dep in deps:
                    if isinstance(dep, dict):
                        vulns = dep.get("vulns")
                        if isinstance(vulns, list):
                            total += len(vulns)
                        else:
                            vulnerabilities = dep.get("vulnerabilities")
                            if isinstance(vulnerabilities, list):
                                total += len(vulnerabilities)
            # Rare shape: {"vulnerabilities": [...]}
            vulnerabilities = data.get("vulnerabilities")
            if isinstance(vulnerabilities, list):
                total += len(vulnerabilities)
        else:
            return None

        return total

    @staticmethod
    def _count_safety_vulns(raw_output: str) -> Optional[int]:
        """
        Пытается извлечь количество уязвимостей из JSON safety.
        Tries to extract vulnerability count from safety JSON output.
        """
        try:
            data = json.loads(raw_output)
        except (ValueError, TypeError):
            return None

        if isinstance(data, list):
            # Old safety format may be list of vulnerabilities
            return len(data)

        if not isinstance(data, dict):
            return None

        vulnerabilities = data.get("vulnerabilities")
        if isinstance(vulnerabilities, list):
            return len(vulnerabilities)

        issues = data.get("issues")
        if isinstance(issues, list):
            return len(issues)

        return None

    @staticmethod
    def _vuln_count_to_score(vuln_count: int) -> float:
        """
        Нормализация количества уязвимостей в 0..5.
        Maps vulnerability count to 0..5 score.
        """
        if vuln_count <= 0:
            return 5.0
        if vuln_count <= 2:
            return 4.0
        if vuln_count <= 5:
            return 3.0
        if vuln_count <= 10:
            return 2.0
        return 0.0

    @staticmethod
    def _estimate_function_complexity(func_node: ast.AST) -> int:
        """
        Прокси-оценка цикломатической сложности функции (AST).
        Proxy estimate of function cyclomatic complexity (AST).
        """
        complexity = 1
        for child in ast.walk(func_node):
            if isinstance(
                child,
                (
                    ast.If,
                    ast.For,
                    ast.AsyncFor,
                    ast.While,
                    ast.ExceptHandler,
                    ast.IfExp,
                ),
            ):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += max(1, len(getattr(child, "values", [])) - 1)
        return complexity

    # ========== БЛОК 1 / BLOCK 1: CODE QUALITY & STABILITY (15 баллов / points) ==========

    def evaluate_test_coverage(self) -> CriterionResult:
        """
        Оценка: Test Coverage % (макс 5 баллов)
        Evaluation: Test Coverage % (max 5 points)
        """
        coverage_percent = self._extract_coverage_percent()
        if coverage_percent is not None:
            if coverage_percent >= 80:
                score = 5.0
            elif coverage_percent >= 60:
                score = 4.0
            elif coverage_percent >= 40:
                score = 3.0
            elif coverage_percent >= 20:
                score = 2.0
            else:
                score = 0.0
            return self._make_result(
                "test_coverage",
                score,
                status="known",
                method="measured",
                confidence=0.9,
                note=f"coverage report found ({coverage_percent:.1f}%)",
            )

        has_tests = self.check_file_exists("tests/**/*.py", "test_*.py")
        if has_tests:
            return self._make_result(
                "test_coverage",
                1.5,
                status="known",
                method="heuristic",
                confidence=0.45,
                note="tests detected but no coverage report",
            )

        return self._make_result(
            "test_coverage",
            0.0,
            status="known",
            method="heuristic",
            confidence=0.55,
            note="no tests or coverage artifacts detected",
        )

    def evaluate_code_complexity(self) -> CriterionResult:
        """
        Оценка: Code Complexity (макс 5 баллов)
        Evaluation: Code Complexity (max 5 points)
        """
        py_files = self._iter_python_files(include_tests=False)
        if not py_files:
            return self._make_result(
                "code_complexity",
                None,
                method="measured",
                note="no Python files found to measure complexity",
            )

        complexities: List[int] = []
        parse_errors = 0
        for py_file in py_files:
            try:
                tree = ast.parse(py_file.read_text(errors="ignore"))
            except (SyntaxError, ValueError, IOError, OSError):
                parse_errors += 1
                continue

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    complexities.append(self._estimate_function_complexity(node))

        if not complexities:
            note = "no functions found for complexity analysis"
            if parse_errors:
                note += f"; parse errors: {parse_errors}"
            return self._make_result(
                "code_complexity", None, method="measured", note=note
            )

        avg_complexity = sum(complexities) / len(complexities)
        if avg_complexity <= 5:
            score = 5.0
        elif avg_complexity <= 10:
            score = 4.0
        elif avg_complexity <= 20:
            score = 3.0
        elif avg_complexity <= 50:
            score = 1.0
        else:
            score = 0.0

        note = f"avg function complexity: {avg_complexity:.2f} ({len(complexities)} functions)"
        if parse_errors:
            note += f"; parse errors: {parse_errors}"

        return self._make_result(
            "code_complexity",
            score,
            status="known",
            method="measured",
            confidence=0.8,
            note=note,
        )

    def evaluate_type_hints(self) -> CriterionResult:
        """
        Оценка: Type Hints Coverage % (макс 5 баллов)
        Evaluation: Type Hints Coverage % (max 5 points)
        """
        py_files = self._iter_python_files(include_tests=False)
        if not py_files:
            return self._make_result(
                "type_hints",
                None,
                method="measured",
                note="no Python files found to measure type hints",
            )

        total_functions = 0
        hinted_functions = 0
        parse_errors = 0

        for py_file in py_files:
            try:
                tree = ast.parse(py_file.read_text(errors="ignore"))
            except (SyntaxError, ValueError, IOError, OSError):
                parse_errors += 1
                continue

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    total_functions += 1
                    args = node.args
                    arg_annotations = []
                    arg_annotations.extend(
                        [a.annotation is not None for a in args.posonlyargs]
                    )
                    arg_annotations.extend(
                        [
                            a.annotation is not None
                            for a in args.args
                            if a.arg not in ("self", "cls")
                        ]
                    )
                    arg_annotations.extend(
                        [a.annotation is not None for a in args.kwonlyargs]
                    )

                    args_ok = all(arg_annotations) if arg_annotations else True
                    return_ok = node.returns is not None
                    if args_ok and return_ok:
                        hinted_functions += 1

        if total_functions == 0:
            note = "no functions found to compute type-hints coverage"
            if parse_errors:
                note += f"; parse errors: {parse_errors}"
            return self._make_result("type_hints", None, method="measured", note=note)

        coverage_percent = (hinted_functions / total_functions) * 100
        if coverage_percent >= self.constants.COVERAGE_EXCELLENT:
            score = 5.0
        elif coverage_percent >= self.constants.COVERAGE_GOOD:
            score = 4.0
        elif coverage_percent >= self.constants.COVERAGE_MEDIUM:
            score = 3.0
        elif coverage_percent >= self.constants.COVERAGE_LOW:
            score = 2.0
        else:
            score = 0.0

        note = f"hinted functions: {hinted_functions}/{total_functions} ({coverage_percent:.1f}%)"
        if parse_errors:
            note += f"; parse errors: {parse_errors}"
        has_type_checker = self.check_file_exists(
            "mypy.ini", "pyrightconfig.json", ".pyright.json"
        )
        if has_type_checker:
            note += "; type checker config detected"

        return self._make_result(
            "type_hints",
            score,
            status="known",
            method="measured",
            confidence=0.85,
            note=note,
        )

    # ========== БЛОК 2 / BLOCK 2: SECURITY & DEPENDENCIES (10 баллов / points) ==========

    def evaluate_vulnerabilities(self) -> CriterionResult:
        """
        Оценка: Dependency Vulnerabilities (макс 5 баллов)
        Evaluation: Dependency Vulnerabilities (max 5 points)
        """
        dep_files = list(self.repo_path.glob("requirements*.txt"))
        has_manifest = bool(dep_files) or self.check_file_exists(
            "pyproject.toml", "Pipfile", "poetry.lock"
        )

        if not has_manifest:
            return self._make_result(
                "vulnerabilities",
                None,
                method="heuristic",
                note="no dependency manifest found",
            )

        # 1) Попытка использовать готовый отчет pip-audit
        # 1) Try to consume existing pip-audit report if present
        pip_audit_report = self.repo_path / "pip-audit-report.json"
        if pip_audit_report.exists():
            try:
                report_data = json.loads(pip_audit_report.read_text(errors="ignore"))
                if isinstance(report_data, list):
                    # Support generated report as list[dependency] with vuln lists
                    vuln_count = 0
                    for item in report_data:
                        if isinstance(item, dict):
                            vulns = item.get("vulns")
                            if isinstance(vulns, list):
                                vuln_count += len(vulns)
                            else:
                                vulnerabilities = item.get("vulnerabilities")
                                if isinstance(vulnerabilities, list):
                                    vuln_count += len(vulnerabilities)
                elif isinstance(report_data, dict):
                    vuln_count = 0
                    vulnerabilities = report_data.get("vulnerabilities")
                    if isinstance(vulnerabilities, list):
                        vuln_count += len(vulnerabilities)
                    deps = report_data.get("dependencies")
                    if isinstance(deps, list):
                        for dep in deps:
                            if isinstance(dep, dict):
                                vulns = dep.get("vulns")
                                if isinstance(vulns, list):
                                    vuln_count += len(vulns)
                else:
                    vuln_count = 0

                score = self._vuln_count_to_score(vuln_count)
                return self._make_result(
                    "vulnerabilities",
                    score,
                    status="known",
                    method="measured",
                    confidence=0.9,
                    note=f"pip-audit report vulnerabilities: {vuln_count}",
                )
            except (ValueError, IOError, OSError, TypeError) as e:
                logger.warning(f"Error parsing pip-audit report: {e}")

        # 2) Попытка запустить pip-audit, если инструмент установлен
        # 2) Try to run pip-audit, if available
        pip_audit_path = shutil.which("pip-audit")
        if pip_audit_path and dep_files:
            total_vulns = 0
            parsed_any = False
            scan_errors: List[str] = []
            for req_file in dep_files:
                command = [pip_audit_path, "-r", str(req_file), "--format", "json"]
                ok, stdout, stderr, error = self._run_tool(
                    command, timeout_sec=self.constants.SECURITY_TOOL_TIMEOUT_SEC
                )
                if not ok:
                    reason = error or (
                        stderr.strip()[:200] if stderr else "unknown scan error"
                    )
                    scan_errors.append(f"{req_file.name}: {reason}")
                    continue
                parsed_vuln_count = self._count_pip_audit_vulns(stdout)
                if parsed_vuln_count is None:
                    scan_errors.append(
                        f"{req_file.name}: invalid pip-audit JSON output"
                    )
                    continue
                parsed_any = True
                total_vulns += parsed_vuln_count

            if parsed_any:
                score = self._vuln_count_to_score(total_vulns)
                note = f"pip-audit scan vulnerabilities: {total_vulns}"
                if scan_errors:
                    note += f"; partial errors: {' | '.join(scan_errors[:3])}"
                return self._make_result(
                    "vulnerabilities",
                    score,
                    status="known",
                    method="measured",
                    confidence=0.9,
                    note=note,
                )

        # 3) Попытка запустить safety, если установлен
        # 3) Try to run safety, if available
        safety_path = shutil.which("safety")
        if safety_path and dep_files:
            total_vulns = 0
            parsed_any = False
            scan_errors = []
            for req_file in dep_files:
                command = [safety_path, "check", "--json", "--file", str(req_file)]
                ok, stdout, stderr, error = self._run_tool(
                    command, timeout_sec=self.constants.SECURITY_TOOL_TIMEOUT_SEC
                )
                # safety may return non-zero when vulnerabilities found; still try parsing stdout
                raw_output = stdout if stdout.strip() else stderr
                parsed_vuln_count = self._count_safety_vulns(raw_output)
                if parsed_vuln_count is None:
                    reason = error or (
                        stderr.strip()[:200] if stderr else "invalid safety JSON output"
                    )
                    scan_errors.append(f"{req_file.name}: {reason}")
                    continue
                parsed_any = True
                total_vulns += parsed_vuln_count

            if parsed_any:
                score = self._vuln_count_to_score(total_vulns)
                note = f"safety scan vulnerabilities: {total_vulns}"
                if scan_errors:
                    note += f"; partial errors: {' | '.join(scan_errors[:3])}"
                return self._make_result(
                    "vulnerabilities",
                    score,
                    status="known",
                    method="measured",
                    confidence=0.85,
                    note=note,
                )

        # 4) Heuristic fallback without claiming perfect security
        score = 2.5
        fallback_reason = []
        if not pip_audit_path:
            fallback_reason.append("pip-audit not installed")
        if not safety_path:
            fallback_reason.append("safety not installed")
        note = "dependency manifest found; CVE scan not available"
        if fallback_reason:
            note += f" ({', '.join(fallback_reason)})"
        try:
            for req_file in dep_files:
                content = req_file.read_text(errors="ignore").lower()
                if "flask==0.9" in content or "django==1.0" in content:
                    score = 1.0
                    note = "very old dependency version detected (heuristic red flag)"
                    break
        except (IOError, OSError, PermissionError) as e:
            logger.warning(f"Error checking vulnerabilities: {e}")
            note = f"dependency files unreadable: {e}"

        return self._make_result(
            "vulnerabilities",
            score,
            status="known",
            method="heuristic",
            confidence=0.4,
            note=note,
        )

    def evaluate_dependency_health(self) -> CriterionResult:
        """
        Оценка: Dependency Health (макс 3 балла)
        Evaluation: Dependency Health (max 3 points)
        """
        dep_files = list(self.repo_path.glob("requirements*.txt"))
        if not dep_files:
            return self._make_result(
                "dep_health",
                None,
                method="measured",
                note="no requirements file found for dependency count",
            )

        try:
            dep_count = 0
            for req_file in dep_files:
                for line in req_file.read_text(errors="ignore").splitlines():
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#"):
                        dep_count += 1

            if dep_count < self.constants.MAX_HEALTHY_DEPENDENCIES:
                score = 3.0
            elif dep_count < self.constants.MEDIUM_DEPENDENCIES:
                score = 2.5
            elif dep_count < self.constants.HIGH_DEPENDENCIES:
                score = 2.0
            else:
                score = 1.0

            return self._make_result(
                "dep_health",
                score,
                status="known",
                method="measured",
                confidence=0.8,
                note=f"dependency lines counted: {dep_count}",
            )
        except (IOError, OSError, PermissionError) as e:
            logger.warning(f"Error evaluating dependency health: {e}")
            return self._make_result(
                "dep_health", None, method="measured", note=f"read error: {e}"
            )

    def evaluate_security_scanning(self) -> CriterionResult:
        """
        Оценка: Security Scanning (макс 2 балла)
        Evaluation: Security Scanning (max 2 points)
        """
        # Проверяем наличие инструментов безопасности
        # Check for security tools
        has_dependabot = self.check_file_exists(".github/dependabot.yml")
        has_bandit = self.check_content_contains(".github/workflows/*.yml", ["bandit"])
        has_safety = self.check_content_contains(".github/workflows/*.yml", ["safety"])

        if has_dependabot and (has_bandit or has_safety):
            score = 2.0
        elif has_dependabot or has_bandit or has_safety:
            score = 1.0
        else:
            score = 0.0

        return self._make_result(
            "security_scanning",
            score,
            status="known",
            method="heuristic",
            confidence=0.65,
            note=f"dependabot={has_dependabot}, bandit={has_bandit}, safety={has_safety}",
        )

    # ========== БЛОК 3 / BLOCK 3: MAINTENANCE & MATURITY (10 баллов / points) ==========

    def evaluate_project_activity(self) -> CriterionResult:
        """
        Оценка: Project Activity (макс 5 баллов)
        Evaluation: Project Activity (max 5 points)
        """
        try:
            # Проверяем дату последнего коммита
            # Check last commit date
            result = subprocess.run(
                ["git", "log", "-1", "--format=%ci"],  # %ci - ISO 8601 format
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0 and result.stdout.strip():
                date_str = result.stdout.strip()
                # Парсим формат git ISO: "2024-01-10 12:34:56 +0300"
                # Parse git ISO format: "2024-01-10 12:34:56 +0300"
                try:
                    # Убираем timezone для простоты парсинга
                    # Remove timezone for simpler parsing
                    date_part = date_str.split(" +")[0].split(" -")[0]
                    last_commit_date = datetime.strptime(
                        date_part.strip(), "%Y-%m-%d %H:%M:%S"
                    )
                    days_ago = (datetime.now() - last_commit_date).days
                except (ValueError, AttributeError, IndexError) as e:
                    logger.warning(f"Error parsing date '{date_str}': {e}")
                    return self._make_result(
                        "project_activity",
                        None,
                        method="measured",
                        note=f"cannot parse git date: {date_str}",
                    )

                if days_ago < self.constants.ACTIVITY_VERY_ACTIVE:
                    score = 5.0
                elif days_ago < self.constants.ACTIVITY_ACTIVE:
                    score = 4.0
                elif days_ago < self.constants.ACTIVITY_MODERATE:
                    score = 3.0
                elif days_ago < self.constants.ACTIVITY_LOW:
                    score = 2.0
                else:
                    score = 0.0

                return self._make_result(
                    "project_activity",
                    score,
                    status="known",
                    method="measured",
                    confidence=0.9,
                    note=f"last commit {days_ago} days ago",
                )

            return self._make_result(
                "project_activity",
                None,
                method="measured",
                note="git log returned no commit date",
            )
        except (
            subprocess.TimeoutExpired,
            subprocess.SubprocessError,
            FileNotFoundError,
        ) as e:
            logger.warning(f"Git command failed: {e}")
            return self._make_result(
                "project_activity",
                None,
                method="measured",
                note=f"git activity unavailable: {type(e).__name__}",
            )

    def _extract_version_score(self, content: str) -> float:
        """
        Извлекает оценку из версии в файле
        Extracts score from version in file
        """
        match = re.search(r'version\s*=\s*["\']([0-9.]+)["\']', content)
        if match:
            version = match.group(1)
            try:
                major = int(version.split(".")[0])

                if major >= 1:
                    return 3.0
                elif major == 0 and len(version.split(".")) > 1:
                    minor = int(version.split(".")[1])
                    if minor >= 5:
                        return 2.0
                    else:
                        return 1.0
            except (ValueError, IndexError):
                pass
        return 0.0

    def evaluate_version_stability(self) -> CriterionResult:
        """
        Оценка: Version Stability (макс 3 балла)
        Evaluation: Version Stability (max 3 points)
        """
        score = 0.0
        evidence_found = False
        try:
            # Проверяем setup.py
            # Check setup.py
            if self.check_file_exists("setup.py"):
                content = Path(self.repo_path / "setup.py").read_text(errors="ignore")
                score = max(score, self._extract_version_score(content))
                evidence_found = True

            # Проверяем pyproject.toml
            # Check pyproject.toml
            if self.check_file_exists("pyproject.toml"):
                content = Path(self.repo_path / "pyproject.toml").read_text(
                    errors="ignore"
                )
                score = max(score, self._extract_version_score(content))
                evidence_found = True

        except (IOError, OSError, PermissionError) as e:
            logger.warning(f"Error evaluating version stability: {e}")
            return self._make_result(
                "version_stability", None, method="measured", note=f"read error: {e}"
            )

        if not evidence_found:
            return self._make_result(
                "version_stability",
                None,
                method="measured",
                note="no setup.py/pyproject version metadata found",
            )

        return self._make_result(
            "version_stability",
            score,
            status="known",
            method="measured",
            confidence=0.8,
            note="version metadata parsed from project files",
        )

    def evaluate_changelog(self) -> CriterionResult:
        """
        Оценка: CHANGELOG (макс 2 балла)
        Evaluation: CHANGELOG (max 2 points)
        """
        if self.check_file_exists("CHANGELOG.md", "CHANGELOG.txt", "HISTORY.md"):
            try:
                # Пытаемся найти CHANGELOG файл
                # Try to find CHANGELOG file
                changelog_files = list(self.repo_path.glob("CHANGELOG*")) + list(
                    self.repo_path.glob("HISTORY.md")
                )
                if changelog_files:
                    changelog_path = changelog_files[0]
                    content = changelog_path.read_text(errors="ignore")

                    # Проверяем полноту CHANGELOG
                    # Check CHANGELOG completeness
                    if (
                        len(content) > self.constants.MIN_CHANGELOG_LENGTH
                        and "version" in content.lower()
                    ):
                        score = 2.0
                    else:
                        score = 1.0
                    return self._make_result(
                        "changelog",
                        score,
                        status="known",
                        method="heuristic",
                        confidence=0.7,
                        note=f"changelog length: {len(content)} chars",
                    )
            except (IOError, OSError, PermissionError) as e:
                logger.warning(f"Error reading changelog: {e}")
                return self._make_result(
                    "changelog",
                    0.5,
                    status="known",
                    method="heuristic",
                    confidence=0.4,
                    note=f"changelog exists but cannot be fully read: {e}",
                )

        return self._make_result(
            "changelog",
            0.0,
            status="known",
            method="heuristic",
            confidence=0.7,
            note="changelog file not found",
        )

    # ========== БЛОК 4 / BLOCK 4: ARCHITECTURE & ENGINEERING (10 баллов / points) ==========

    def evaluate_docstrings(self) -> CriterionResult:
        """
        Оценка: Docstring Coverage (макс 5 баллов)
        Evaluation: Docstring Coverage (max 5 points)
        """
        py_files = self._iter_python_files(include_tests=False)
        if not py_files:
            return self._make_result(
                "docstrings",
                None,
                method="measured",
                note="no Python files found for docstring analysis",
            )

        total_functions = 0
        documented_functions = 0
        parse_errors = 0

        for py_file in py_files:
            try:
                tree = ast.parse(py_file.read_text(errors="ignore"))
            except (SyntaxError, ValueError, IOError, OSError):
                parse_errors += 1
                continue

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    total_functions += 1
                    if ast.get_docstring(node):
                        documented_functions += 1

        if total_functions == 0:
            note = "no functions found for docstring coverage"
            if parse_errors:
                note += f"; parse errors: {parse_errors}"
            return self._make_result("docstrings", None, method="measured", note=note)

        coverage_percent = (documented_functions / total_functions) * 100
        if coverage_percent >= self.constants.COVERAGE_EXCELLENT:
            score = 5.0
        elif coverage_percent >= self.constants.COVERAGE_GOOD:
            score = 4.0
        elif coverage_percent >= self.constants.COVERAGE_MEDIUM:
            score = 3.0
        elif coverage_percent >= self.constants.COVERAGE_LOW:
            score = 2.0
        else:
            score = 0.0

        note = f"docstrings: {documented_functions}/{total_functions} ({coverage_percent:.1f}%)"
        if parse_errors:
            note += f"; parse errors: {parse_errors}"
        return self._make_result(
            "docstrings",
            score,
            status="known",
            method="measured",
            confidence=0.85,
            note=note,
        )

    def evaluate_logging(self) -> CriterionResult:
        """
        Оценка: Error Handling & Logging (макс 3 балла)
        Evaluation: Error Handling & Logging (max 3 points)
        """
        py_files = self._iter_python_files(include_tests=False)
        if not py_files:
            return self._make_result(
                "logging",
                None,
                method="heuristic",
                note="no Python files found for logging analysis",
            )

        total_files = 0
        logging_files = 0
        for py_file in py_files:
            try:
                content = py_file.read_text(errors="ignore")
            except (IOError, OSError, PermissionError):
                continue
            total_files += 1
            if (
                "import logging" in content
                or "from logging" in content
                or "logger." in content
                or "logging." in content
            ):
                logging_files += 1

        if total_files == 0:
            return self._make_result(
                "logging", None, method="heuristic", note="Python files unreadable"
            )

        logging_percent = (logging_files / total_files) * 100
        if logging_percent >= 80:
            score = 3.0
        elif logging_percent >= 50:
            score = 2.0
        elif logging_percent > 0:
            score = 1.0
        else:
            score = 0.0

        return self._make_result(
            "logging",
            score,
            status="known",
            method="heuristic",
            confidence=0.7,
            note=f"files with logging signals: {logging_files}/{total_files} ({logging_percent:.1f}%)",
        )

    def evaluate_project_structure(self) -> CriterionResult:
        """
        Оценка: Project Structure (макс 2 балла)
        Evaluation: Project Structure (max 2 points)
        """
        score = 0.0
        has_src = self.check_file_exists("src/")
        has_tests = self.check_file_exists("tests/", "test_*.py")
        has_docs = self.check_file_exists("docs/") or self.check_file_exists(
            "mkdocs.yml"
        )

        if has_src and has_tests and has_docs:
            score = 2.0
        elif has_src and has_tests:
            score = 1.5
        elif has_src or has_tests:
            score = 1.0

        return self._make_result(
            "structure",
            score,
            status="known",
            method="heuristic",
            confidence=0.75,
            note=f"src={has_src}, tests={has_tests}, docs={has_docs}",
        )

    # ========== БЛОК 5 / BLOCK 5: DOCUMENTATION & UX (10 баллов / points) ==========

    def evaluate_readme_quality(self) -> CriterionResult:
        """
        Оценка: README Quality (макс 5 баллов)
        Evaluation: README Quality (max 5 points)
        """
        score = 0.0
        if self.check_file_exists("README.md", "README.txt", "README.rst"):
            try:
                readme_files = list(self.repo_path.glob("README*"))
                if readme_files:
                    readme_path = readme_files[0]
                    content = readme_path.read_text(errors="ignore").lower()

                    # Считаем наличие ключевых секций
                    # Count key sections presence
                    sections = 0
                    if "install" in content or "setup" in content:
                        sections += 1
                    if (
                        "usage" in content
                        or "example" in content
                        or "quickstart" in content
                    ):
                        sections += 1
                    if "screenshot" in content or "demo" in content:
                        sections += 1
                    if (
                        "troubleshoot" in content
                        or "faq" in content
                        or "issue" in content
                    ):
                        sections += 1

                    # Длина README (полный README минимум 300 символов)
                    # README length (full README minimum 300 characters)
                    if len(content) > self.constants.MIN_README_LENGTH_FULL:
                        if sections >= 3:
                            score = 5.0
                        elif sections >= 2:
                            score = 4.0
                        else:
                            score = 3.0
                    elif len(content) > self.constants.MIN_README_LENGTH_PARTIAL:
                        score = 2.0
                    else:
                        score = 1.0
                    return self._make_result(
                        "readme",
                        score,
                        status="known",
                        method="heuristic",
                        confidence=0.75,
                        note=f"sections matched: {sections}; length: {len(content)}",
                    )
            except (IOError, OSError, PermissionError) as e:
                logger.warning(f"Error reading README: {e}")
                return self._make_result(
                    "readme", None, method="heuristic", note=f"README read error: {e}"
                )

        return self._make_result(
            "readme",
            0.0,
            status="known",
            method="heuristic",
            confidence=0.8,
            note="README file not found",
        )

    def evaluate_api_documentation(self) -> CriterionResult:
        """
        Оценка: API Documentation (макс 3 балла)
        Evaluation: API Documentation (max 3 points)
        """
        has_fastapi = self._python_content_contains(["fastapi"])
        has_postman = self.check_file_exists("*.postman_collection.json")
        has_openapi = self.check_file_exists("openapi.json", "openapi.yaml")

        if (has_fastapi or has_postman) and has_openapi:
            score = 3.0
        elif has_fastapi or has_postman:
            score = 2.0
        elif has_openapi:
            score = 1.5
        elif self._python_content_contains(["Args:", "Returns:", "Raises:"]):
            score = 1.0
        else:
            score = 0.0

        py_files_exist = bool(self._iter_python_files(include_tests=True))
        if not py_files_exist and not has_postman and not has_openapi:
            return self._make_result(
                "api_docs",
                None,
                method="heuristic",
                note="no API/documentation artifacts found to evaluate",
            )

        return self._make_result(
            "api_docs",
            score,
            status="known",
            method="heuristic",
            confidence=0.65,
            note=f"fastapi={has_fastapi}, postman={has_postman}, openapi={has_openapi}",
        )

    def evaluate_getting_started(self) -> CriterionResult:
        """
        Оценка: Getting Started Ease (макс 2 балла)
        Evaluation: Getting Started Ease (max 2 points)
        """
        score = 0.0

        # Можно ли запустить за 1-2 команды?
        # Can it be run in 1-2 commands?
        if self.check_file_exists("Makefile"):
            score = 2.0
        elif self.check_file_exists("docker-compose.yml", "docker-compose.yaml"):
            score = 2.0
        elif self.check_file_exists("run.sh", "start.sh"):
            score = 1.5
        elif self.check_content_contains(
            "README*.md", ["docker-compose up", "python main.py"]
        ):
            score = 1.0

        return self._make_result(
            "getting_started",
            score,
            status="known",
            method="heuristic",
            confidence=0.7,
            note="quick-start artifacts scanned",
        )

    # ========== БЛОК 6 / BLOCK 6: DEPLOYMENT & DEVOPS (5 баллов / points) ==========

    def evaluate_docker(self) -> CriterionResult:
        """
        Оценка: Docker & Containerization (макс 3 балла)
        Evaluation: Docker & Containerization (max 3 points)
        """
        score = 0.0

        has_dockerfile = self.check_file_exists("Dockerfile")
        has_compose = self.check_file_exists(
            "docker-compose.yml", "docker-compose.yaml"
        )
        has_dockerignore = self.check_file_exists(".dockerignore")

        if has_dockerfile and has_compose and has_dockerignore:
            # Проверяем качество Dockerfile
            # Check Dockerfile quality
            try:
                dockerfile = Path(self.repo_path / "Dockerfile")
                content = dockerfile.read_text(errors="ignore")

                if "FROM" in content and "HEALTHCHECK" in content:
                    score = 3.0
                else:
                    score = 2.5
            except (IOError, OSError, PermissionError) as e:
                logger.warning(f"Error reading Dockerfile: {e}")
                score = 2.5
        elif has_dockerfile and has_compose:
            score = 2.0
        elif has_dockerfile:
            score = 1.0

        return self._make_result(
            "docker",
            score,
            status="known",
            method="heuristic",
            confidence=0.75,
            note=f"dockerfile={has_dockerfile}, compose={has_compose}, dockerignore={has_dockerignore}",
        )

    def evaluate_cicd(self) -> CriterionResult:
        """
        Оценка: CI/CD Pipeline (макс 2 балла)
        Evaluation: CI/CD Pipeline (max 2 points)
        """
        score = 0.0

        workflow_files = list(self.repo_path.glob(".github/workflows/*.yml")) + list(
            self.repo_path.glob(".github/workflows/*.yaml")
        )
        if workflow_files:
            try:
                merged_content = ""
                for wf in workflow_files:
                    merged_content += "\n" + wf.read_text(errors="ignore").lower()

                # Проверяем полноту CI/CD
                # Check CI/CD completeness
                checks = 0
                if (
                    "lint" in merged_content
                    or "ruff" in merged_content
                    or "black" in merged_content
                ):
                    checks += 1
                if "test" in merged_content or "pytest" in merged_content:
                    checks += 1
                if "coverage" in merged_content:
                    checks += 1
                if (
                    "deploy" in merged_content
                    or "push" in merged_content
                    or "release" in merged_content
                ):
                    checks += 1

                if checks >= 3:
                    score = 2.0
                elif checks >= 2:
                    score = 1.0
                else:
                    score = 0.5
                note = (
                    f"workflow files: {len(workflow_files)}, checks matched: {checks}/4"
                )
            except (IOError, OSError, PermissionError) as e:
                logger.warning(f"Error reading workflow files: {e}")
                score = 0.5
                note = f"workflow files exist but read failed: {e}"
        else:
            note = "no workflow files found"

        return self._make_result(
            "cicd",
            score,
            status="known",
            method="heuristic",
            confidence=0.75,
            note=note,
        )

    def _build_data_quality_warnings(
        self, criteria: Dict[str, CriterionResult], data_coverage_percent: float
    ) -> List[str]:
        """
        Формирует предупреждения о качестве данных.
        Builds data-quality warnings for insufficient evidence.
        """
        warnings: List[str] = []
        core_criteria = ("test_coverage", "code_complexity", "vulnerabilities")

        if data_coverage_percent < 40:
            warnings.append(
                "critical: data coverage below 40%; final score has low reliability"
            )
        elif data_coverage_percent < 60:
            warnings.append(
                "warning: data coverage below 60%; conclusions may be unstable"
            )

        unknown_core = [
            key
            for key in core_criteria
            if key in criteria
            and (
                criteria[key].status == "unknown"
                or criteria[key].score is None
                or criteria[key].confidence <= 0.0
            )
        ]
        if unknown_core:
            warnings.append(
                "critical: missing core evidence for " + ", ".join(sorted(unknown_core))
            )

        known_confidences = [
            item.confidence
            for item in criteria.values()
            if item.score is not None and item.status != "unknown"
        ]
        if known_confidences:
            avg_confidence = sum(known_confidences) / len(known_confidences)
            if avg_confidence < 0.65:
                warnings.append(
                    f"warning: average criterion confidence is low ({avg_confidence:.2f})"
                )
        else:
            warnings.append("critical: no measurable criteria available")

        return warnings

    # ========== ГЛАВНАЯ ФУНКЦИЯ ОЦЕНКИ / MAIN EVALUATION FUNCTION ==========

    def evaluate_all(self) -> Dict[str, Any]:
        """
        Полная оценка репозитория по 18 критериям
        Full repository evaluation by 18 criteria
        """
        criteria = OrderedDict(
            {
                "test_coverage": self.evaluate_test_coverage(),
                "code_complexity": self.evaluate_code_complexity(),
                "type_hints": self.evaluate_type_hints(),
                "vulnerabilities": self.evaluate_vulnerabilities(),
                "dep_health": self.evaluate_dependency_health(),
                "security_scanning": self.evaluate_security_scanning(),
                "project_activity": self.evaluate_project_activity(),
                "version_stability": self.evaluate_version_stability(),
                "changelog": self.evaluate_changelog(),
                "docstrings": self.evaluate_docstrings(),
                "logging": self.evaluate_logging(),
                "structure": self.evaluate_project_structure(),
                "readme": self.evaluate_readme_quality(),
                "api_docs": self.evaluate_api_documentation(),
                "getting_started": self.evaluate_getting_started(),
                "docker": self.evaluate_docker(),
                "cicd": self.evaluate_cicd(),
            }
        )

        blocks_meta: Dict[str, Dict[str, Optional[float]]] = {}
        for block_key, block_max in self.constants.BLOCK_MAX_SCORES.items():
            block_criteria = [
                key
                for key, criterion_block in self.constants.CRITERION_BLOCK.items()
                if criterion_block == block_key
            ]
            known_items = [
                criteria[key]
                for key in block_criteria
                if criteria[key].score is not None and criteria[key].status != "unknown"
            ]

            known_score = sum(
                item.score for item in known_items if item.score is not None
            )
            known_max = sum(item.max_score for item in known_items)
            block_score = (
                (known_score / known_max) * block_max if known_max > 0 else None
            )
            coverage_percent = (known_max / block_max) * 100 if block_max > 0 else 0.0

            blocks_meta[block_key] = {
                "score": round(block_score, 2) if block_score is not None else None,
                "known_score": round(known_score, 2),
                "known_max": round(known_max, 2),
                "max_score": round(block_max, 2),
                "data_coverage_percent": round(coverage_percent, 2),
            }

        known_total_score = sum(
            criterion.score
            for criterion in criteria.values()
            if criterion.score is not None and criterion.status != "unknown"
        )
        known_total_max = sum(
            criterion.max_score
            for criterion in criteria.values()
            if criterion.score is not None and criterion.status != "unknown"
        )

        if known_total_max > 0:
            total_score = (
                known_total_score / known_total_max
            ) * self.constants.TOTAL_MAX_SCORE
        else:
            total_score = 0.0

        data_coverage_percent = (
            known_total_max / self.constants.RAW_TOTAL_MAX_SCORE
        ) * 100

        results: Dict[str, Any] = {
            "repo": self.repo_name,
            "path": str(self.repo_path),
            "total_score": round(total_score, 2),
            "max_score": self.constants.TOTAL_MAX_SCORE,
            "raw_max_score": self.constants.RAW_TOTAL_MAX_SCORE,
            "known_score": round(known_total_score, 2),
            "known_max_score": round(known_total_max, 2),
            "data_coverage_percent": round(data_coverage_percent, 2),
            "criteria_meta": {},
            "blocks_meta": blocks_meta,
        }

        # Совместимость с предыдущим плоским форматом / Backward-compatible flat fields
        for block_key in self.constants.BLOCK_MAX_SCORES:
            results[block_key] = blocks_meta[block_key]["score"]

        for key, criterion in criteria.items():
            results[key] = (
                round(criterion.score, 2) if criterion.score is not None else None
            )
            results["criteria_meta"][key] = {
                "max_score": criterion.max_score,
                "status": criterion.status,
                "method": criterion.method,
                "confidence": round(criterion.confidence, 2),
                "note": criterion.note,
            }

        quality_warnings = self._build_data_quality_warnings(
            criteria, data_coverage_percent
        )
        if any(item.startswith("critical:") for item in quality_warnings):
            data_quality_status = "red"
        elif quality_warnings:
            data_quality_status = "yellow"
        else:
            data_quality_status = "green"
        results["data_quality_warnings"] = quality_warnings
        results["data_quality_status"] = data_quality_status

        results["category"] = self._categorize(
            results["total_score"], results["data_coverage_percent"]
        )
        return results

    @staticmethod
    def _categorize(score: float, data_coverage_percent: float) -> str:
        """
        Категоризация по баллам
        Categorization by score
        """
        if data_coverage_percent < 40:
            return "⚪ Недостаточно данных / Insufficient data"
        if score >= 40:
            return "⭐⭐⭐⭐⭐ Идеальный / Perfect"
        elif score >= 30:
            return "⭐⭐⭐⭐ Отличный / Excellent"
        elif score >= 20:
            return "⭐⭐⭐ Хороший / Good"
        elif score >= 10:
            return "⭐⭐ Средний / Average"
        else:
            return "⭐ Парковка / Parking"
