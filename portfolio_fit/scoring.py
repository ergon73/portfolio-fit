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
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

# Настройка логирования / Logging configuration
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


STACK_PROFILE_AUTO = "auto"
STACK_PROFILES = (
    STACK_PROFILE_AUTO,
    "python_backend",
    "python_fullstack_react",
    "python_django_templates",
    "node_frontend",
    "mixed_unknown",
)
NON_AUTO_STACK_PROFILES = tuple(
    profile for profile in STACK_PROFILES if profile != STACK_PROFILE_AUTO
)

# Criteria that are currently Python-specific and should not penalize non-Python stacks.
CRITERION_NOT_APPLICABLE_PROFILES: Dict[str, Set[str]] = {
    "test_coverage": {"mixed_unknown"},
    "code_complexity": {"node_frontend", "mixed_unknown"},
    "type_hints": {"mixed_unknown"},
    "vulnerabilities": {"mixed_unknown"},
    "dep_health": {"mixed_unknown"},
    "security_scanning": {"mixed_unknown"},
    "docstrings": {"node_frontend", "mixed_unknown"},
    "logging": {"node_frontend", "mixed_unknown"},
    "api_docs": {"node_frontend", "mixed_unknown"},
}

FRONTEND_CODE_EXTENSIONS = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")
FRONTEND_TEMPLATE_EXTENSIONS = (".html",)
FRONTEND_STYLE_EXTENSIONS = (".css", ".scss", ".sass", ".less")
FRONTEND_QUALITY_MAX_SCORE = 5.0


def _safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except (IOError, OSError, PermissionError):
        return ""


def _safe_load_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except (ValueError, IOError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def _strip_json_comments_and_trailing_commas(raw: str) -> str:
    without_block_comments = re.sub(r"/\*.*?\*/", "", raw, flags=re.DOTALL)
    without_line_comments = re.sub(
        r"(^|[^:\\])//.*?$",
        lambda match: str(match.group(1)),
        without_block_comments,
        flags=re.MULTILINE,
    )
    return re.sub(r",\s*([}\]])", r"\1", without_line_comments)


def detect_stack_profile(repo_path: Path) -> str:
    """
    Auto-detect repository stack profile from common project artifacts.
    """
    path = Path(repo_path)

    has_python_files = any(path.glob("*.py")) or any(path.glob("**/*.py"))
    has_python_manifests = any(
        (path / file_name).exists()
        for file_name in (
            "pyproject.toml",
            "requirements.txt",
            "requirements-dev.txt",
            "setup.py",
            "manage.py",
            "Pipfile",
            "poetry.lock",
        )
    )
    has_python = has_python_files or has_python_manifests

    package_json = _safe_load_json(path / "package.json")
    has_node_artifacts = any(
        (path / file_name).exists()
        for file_name in (
            "package.json",
            "tsconfig.json",
            "vite.config.ts",
            "vite.config.js",
            "next.config.js",
            "next.config.mjs",
            "webpack.config.js",
            "webpack.config.ts",
            "yarn.lock",
            "pnpm-lock.yaml",
        )
    )
    has_node_code = (
        any(path.glob("*.js"))
        or any(path.glob("*.ts"))
        or any(path.glob("**/*.js"))
        or any(path.glob("**/*.ts"))
    )
    has_node = has_node_artifacts or has_node_code

    dep_names: Set[str] = set()
    if package_json:
        for section in ("dependencies", "devDependencies", "peerDependencies"):
            section_value = package_json.get(section)
            if isinstance(section_value, dict):
                dep_names.update(str(name).lower() for name in section_value.keys())

    has_react_like_frontend = any(
        dep in dep_names
        for dep in ("react", "next", "vue", "@angular/core", "svelte", "nuxt")
    ) or any(
        (path / file_name).exists()
        for file_name in (
            "next.config.js",
            "next.config.mjs",
            "vite.config.ts",
            "vite.config.js",
            "nuxt.config.ts",
            "nuxt.config.js",
        )
    )

    has_django_signal = (path / "manage.py").exists()
    if not has_django_signal:
        requirements_text = "".join(
            _safe_read_text(req_file) for req_file in path.glob("requirements*.txt")
        ).lower()
        pyproject_text = _safe_read_text(path / "pyproject.toml").lower()
        has_django_signal = "django" in requirements_text or "django" in pyproject_text
    has_templates = (path / "templates").is_dir() and (
        any((path / "templates").glob("*.html"))
        or any((path / "templates").glob("**/*.html"))
    )

    if has_python and has_node and has_react_like_frontend:
        return "python_fullstack_react"
    if has_python and has_django_signal and has_templates:
        return "python_django_templates"
    if has_python:
        return "python_backend"
    if has_node:
        return "node_frontend"
    return "mixed_unknown"


@dataclass
class CriterionResult:
    """Результат одного критерия / Single criterion result"""

    score: Optional[float]
    max_score: float
    status: str  # known | unknown | not_applicable
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

    def __init__(self, repo_path: Path, stack_profile: str = STACK_PROFILE_AUTO):
        self.repo_path = Path(repo_path)
        resolved_name = self.repo_path.name
        if not resolved_name:
            try:
                resolved_name = self.repo_path.resolve().name
            except OSError:
                resolved_name = ""
        self.repo_name = resolved_name or str(self.repo_path)
        self.constants = EvaluationConstants()
        self.stack_profile = self._resolve_stack_profile(stack_profile)

    def _resolve_stack_profile(self, stack_profile: str) -> str:
        requested_profile = str(stack_profile or STACK_PROFILE_AUTO).strip().lower()
        if requested_profile == STACK_PROFILE_AUTO:
            return detect_stack_profile(self.repo_path)
        if requested_profile in NON_AUTO_STACK_PROFILES:
            return requested_profile
        logger.warning(
            "Unknown stack profile '%s', falling back to auto-detection",
            requested_profile,
        )
        return detect_stack_profile(self.repo_path)

    def _is_criterion_applicable(self, criterion_key: str) -> bool:
        not_applicable_profiles = CRITERION_NOT_APPLICABLE_PROFILES.get(
            criterion_key, set()
        )
        return self.stack_profile not in not_applicable_profiles

    def _make_not_applicable_result(self, key: str) -> CriterionResult:
        return self._make_result(
            key,
            None,
            status="not_applicable",
            confidence=1.0,
            note=f"not applicable for stack profile '{self.stack_profile}'",
        )

    def _evaluate_criterion(
        self, criterion_key: str, evaluator: Callable[[], CriterionResult]
    ) -> CriterionResult:
        if not self._is_criterion_applicable(criterion_key):
            return self._make_not_applicable_result(criterion_key)
        return evaluator()

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

        if status == "not_applicable":
            resolved_confidence = (
                1.0 if confidence is None else max(0.0, min(float(confidence), 1.0))
            )
            return CriterionResult(
                score=None,
                max_score=max_score,
                status="not_applicable",
                method=resolved_method,
                confidence=resolved_confidence,
                note=note,
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

    def _iter_frontend_files(
        self, include_tests: bool = True, typescript_only: bool = False
    ) -> List[Path]:
        """
        Returns JS/TS source files with service-directory filtering.
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
            "coverage",
        }
        allowed_ext = (
            {".ts", ".tsx"} if typescript_only else set(FRONTEND_CODE_EXTENSIONS)
        )
        result: List[Path] = []
        for file_path in self.repo_path.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in allowed_ext:
                continue

            try:
                rel_parts = file_path.relative_to(self.repo_path).parts
            except ValueError:
                continue
            if any(part in excluded_dirs for part in rel_parts):
                continue

            file_name = file_path.name.lower()
            rel_lower = "/".join(part.lower() for part in rel_parts)
            if not include_tests and (
                "__tests__" in rel_lower
                or "/tests/" in rel_lower
                or file_name.endswith(".test.ts")
                or file_name.endswith(".test.tsx")
                or file_name.endswith(".test.js")
                or file_name.endswith(".test.jsx")
                or file_name.endswith(".spec.ts")
                or file_name.endswith(".spec.tsx")
                or file_name.endswith(".spec.js")
                or file_name.endswith(".spec.jsx")
            ):
                continue

            result.append(file_path)
        return result

    def _repo_has_frontend_code(self) -> bool:
        return bool(self._iter_frontend_files(include_tests=True))

    def _repo_has_typescript(self) -> bool:
        return bool(self._iter_frontend_files(include_tests=True, typescript_only=True))

    def _load_package_json(self) -> Dict[str, Any]:
        return _safe_load_json(self.repo_path / "package.json") or {}

    def _count_node_dependencies(self) -> int:
        package_json = self._load_package_json()
        dep_count = 0
        for section in ("dependencies", "devDependencies", "peerDependencies"):
            section_value = package_json.get(section)
            if isinstance(section_value, dict):
                dep_count += len(section_value)
        return dep_count

    def _has_package_script(self, *keywords: str) -> bool:
        package_json = self._load_package_json()
        scripts = package_json.get("scripts", {})
        if not isinstance(scripts, dict):
            return False
        lowered_keywords = [keyword.lower() for keyword in keywords]
        for key, value in scripts.items():
            key_lower = str(key).lower()
            value_lower = str(value).lower()
            if any(
                keyword in key_lower or keyword in value_lower
                for keyword in lowered_keywords
            ):
                return True
        return False

    def _read_tsconfig_compiler_options(
        self,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        tsconfig = self.repo_path / "tsconfig.json"
        if not tsconfig.exists():
            return None, "tsconfig.json not found"

        raw = _safe_read_text(tsconfig)
        if not raw.strip():
            return None, "tsconfig.json is empty"

        parsed: Optional[Dict[str, Any]] = None
        try:
            data = json.loads(raw)
            parsed = data if isinstance(data, dict) else None
        except ValueError:
            sanitized = _strip_json_comments_and_trailing_commas(raw)
            try:
                data = json.loads(sanitized)
                parsed = data if isinstance(data, dict) else None
            except ValueError as exc:
                return None, f"cannot parse tsconfig.json: {exc}"

        if not isinstance(parsed, dict):
            return None, "tsconfig.json is not a JSON object"

        compiler_options = parsed.get("compilerOptions", {})
        if isinstance(compiler_options, dict):
            return compiler_options, None
        return {}, None

    def _extract_frontend_coverage_percent(self) -> Optional[float]:
        """
        Tries to extract JS/TS coverage percentage from common frontend artifacts.
        """
        json_candidates = (
            self.repo_path / "coverage" / "coverage-summary.json",
            self.repo_path / "coverage-summary.json",
            self.repo_path / ".nyc_output" / "coverage-summary.json",
        )
        for candidate in json_candidates:
            if not candidate.exists():
                continue
            try:
                payload = json.loads(
                    candidate.read_text(encoding="utf-8", errors="ignore")
                )
            except (ValueError, IOError, OSError):
                continue
            if not isinstance(payload, dict):
                continue
            total = payload.get("total", {})
            if isinstance(total, dict):
                lines = total.get("lines", {})
                if isinstance(lines, dict) and "pct" in lines:
                    return float(lines["pct"])
                if "pct" in total:
                    return float(total["pct"])

        lcov_candidates = (
            self.repo_path / "coverage" / "lcov.info",
            self.repo_path / "lcov.info",
        )
        for lcov_path in lcov_candidates:
            if not lcov_path.exists():
                continue
            try:
                raw = lcov_path.read_text(encoding="utf-8", errors="ignore")
            except (IOError, OSError):
                continue
            total_found = 0.0
            total_hit = 0.0
            for line in raw.splitlines():
                try:
                    if line.startswith("LF:"):
                        total_found += float(line.split(":", 1)[1].strip() or 0)
                    elif line.startswith("LH:"):
                        total_hit += float(line.split(":", 1)[1].strip() or 0)
                except (ValueError, IndexError):
                    continue
            if total_found > 0:
                return (total_hit / total_found) * 100.0

        return None

    def _has_frontend_tests(self) -> bool:
        if self.check_file_exists(
            "tests/",
            "__tests__/",
            "**/*.test.ts",
            "**/*.test.tsx",
            "**/*.test.js",
            "**/*.test.jsx",
            "**/*.spec.ts",
            "**/*.spec.tsx",
            "**/*.spec.js",
            "**/*.spec.jsx",
            "vitest.config.ts",
            "vitest.config.js",
            "jest.config.js",
            "jest.config.ts",
        ):
            return True
        scripts = self._load_package_json().get("scripts", {})
        if not isinstance(scripts, dict):
            return False
        for key, value in scripts.items():
            script_key = str(key).lower()
            script_val = str(value).lower()
            if script_key == "test" or "vitest" in script_val or "jest" in script_val:
                return True
        return False

    def _iter_non_ignored_files_by_extensions(
        self, extensions: Tuple[str, ...]
    ) -> List[Path]:
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
            "coverage",
        }
        allowed_ext = {extension.lower() for extension in extensions}
        result: List[Path] = []
        for file_path in self.repo_path.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in allowed_ext:
                continue
            try:
                rel_parts = file_path.relative_to(self.repo_path).parts
            except ValueError:
                continue
            if any(part in excluded_dirs for part in rel_parts):
                continue
            result.append(file_path)
        return result

    def _iter_frontend_markup_files(self) -> List[Path]:
        return self._iter_non_ignored_files_by_extensions(FRONTEND_TEMPLATE_EXTENSIONS)

    def _iter_frontend_style_files(self) -> List[Path]:
        return self._iter_non_ignored_files_by_extensions(FRONTEND_STYLE_EXTENSIONS)

    def _detect_frontend_frameworks(self) -> Set[str]:
        package_json = self._load_package_json()
        dep_names: Set[str] = set()
        for section in ("dependencies", "devDependencies", "peerDependencies"):
            section_value = package_json.get(section)
            if isinstance(section_value, dict):
                dep_names.update(str(name).lower() for name in section_value.keys())

        detected: Set[str] = set()
        if "react" in dep_names:
            detected.add("react")
        if "next" in dep_names or self.check_file_exists(
            "next.config.js", "next.config.mjs"
        ):
            detected.add("nextjs")
        if "vue" in dep_names or self.check_file_exists(
            "vite.config.ts", "vite.config.js"
        ):
            detected.add("vue")
        if "nuxt" in dep_names or self.check_file_exists(
            "nuxt.config.ts", "nuxt.config.js"
        ):
            detected.add("nuxt")
        if "tailwindcss" in dep_names or self.check_file_exists(
            "tailwind.config.js",
            "tailwind.config.ts",
        ):
            detected.add("tailwind")
        if "styled-components" in dep_names:
            detected.add("styled-components")
        if any(dep.startswith("@emotion/") for dep in dep_names):
            detected.add("emotion")

        templates_dir = self.repo_path / "templates"
        if self.stack_profile == "python_django_templates" or templates_dir.is_dir():
            detected.add("django_templates")

        return detected

    def _scan_accessibility_artifacts(self) -> Tuple[bool, bool]:
        candidate_dirs = [
            self.repo_path,
            self.repo_path / "reports",
            self.repo_path / "report",
            self.repo_path / "artifacts",
            self.repo_path / "audit",
        ]
        patterns = (
            "*lighthouse*.json",
            "*lighthouse*.html",
            "*axe*.json",
            "*pa11y*.json",
            "*a11y*.json",
            "*accessibility*.json",
            "*accessibility*.txt",
        )

        seen_paths: Set[Path] = set()
        has_artifact = False
        has_contrast_warnings = False

        for base in candidate_dirs:
            if not base.exists() or not base.is_dir():
                continue
            for pattern in patterns:
                for candidate in base.glob(pattern):
                    if not candidate.is_file() or candidate in seen_paths:
                        continue
                    seen_paths.add(candidate)
                    content = _safe_read_text(candidate).lower()
                    candidate_name = candidate.name.lower()
                    if any(
                        token in candidate_name or token in content
                        for token in (
                            "lighthouse",
                            "accessibility",
                            "axe",
                            "pa11y",
                            "a11y",
                        )
                    ):
                        has_artifact = True
                    if "color-contrast" in content and any(
                        signal in content
                        for signal in ("warning", "fail", "error", "violation")
                    ):
                        has_contrast_warnings = True

        return has_artifact, has_contrast_warnings

    def _evaluate_html_semantics_signal(
        self, markup_files: List[Path], html_files: List[Path]
    ) -> Tuple[Optional[float], str, Dict[str, Any]]:
        semantic_tags = ("header", "main", "nav", "footer", "section", "article")
        detected_semantic: Set[str] = set()
        form_count = 0
        label_count = 0
        aria_label_count = 0
        img_count = 0
        img_with_alt_count = 0

        if not markup_files:
            return (
                None,
                "no HTML/JSX markup files detected",
                {
                    "semantic_tags": 0,
                    "forms": 0,
                    "labels": 0,
                    "aria_labels": 0,
                    "images": 0,
                    "images_with_alt": 0,
                    "meta_signals": 0,
                },
            )

        for markup_file in markup_files:
            content = _safe_read_text(markup_file).lower()
            if not content:
                continue
            for tag in semantic_tags:
                if f"<{tag}" in content:
                    detected_semantic.add(tag)
            form_count += len(re.findall(r"<form\b", content))
            label_count += len(re.findall(r"<label\b", content))
            aria_label_count += len(re.findall(r"aria-label\s*=", content))
            img_count += len(re.findall(r"<img\b", content))
            img_with_alt_count += len(re.findall(r"<img\b[^>]*\balt\s*=", content))

        meta_charset = False
        meta_viewport = False
        meta_description = False
        has_title = False
        for html_file in html_files:
            content = _safe_read_text(html_file).lower()
            if not content:
                continue
            if re.search(r"<meta[^>]+charset", content):
                meta_charset = True
            if re.search(
                r"<meta[^>]+name\s*=\s*[\"']viewport[\"']",
                content,
            ):
                meta_viewport = True
            if re.search(
                r"<meta[^>]+name\s*=\s*[\"']description[\"']",
                content,
            ):
                meta_description = True
            if "<title" in content:
                has_title = True

        meta_signal_count = sum(
            int(flag)
            for flag in (meta_charset, meta_viewport, meta_description, has_title)
        )

        score = 0.0
        semantic_count = len(detected_semantic)
        if semantic_count >= 4:
            score += 2.0
        elif semantic_count >= 2:
            score += 1.5
        elif semantic_count >= 1:
            score += 1.0

        if form_count == 0:
            score += 1.0
        else:
            if label_count + aria_label_count >= form_count:
                score += 1.5
            elif label_count > 0 or aria_label_count > 0:
                score += 1.0

        if meta_signal_count >= 3:
            score += 1.0
        elif meta_signal_count >= 1:
            score += 0.5

        if len(html_files) >= 3:
            score += 0.5
        elif len(html_files) >= 1 or len(markup_files) >= 2:
            score += 0.25

        score = max(0.0, min(FRONTEND_QUALITY_MAX_SCORE, score))
        note = (
            f"semantic tags={semantic_count}, forms={form_count}, labels={label_count}, "
            f"meta signals={meta_signal_count}"
        )
        details = {
            "semantic_tags": semantic_count,
            "forms": form_count,
            "labels": label_count,
            "aria_labels": aria_label_count,
            "images": img_count,
            "images_with_alt": img_with_alt_count,
            "meta_signals": meta_signal_count,
        }
        return score, note, details

    def _evaluate_css_quality_signal(
        self, style_files: List[Path], framework_signals: Set[str]
    ) -> Tuple[Optional[float], str, Dict[str, Any]]:
        has_stylelint_config = self.check_file_exists(
            ".stylelintrc",
            ".stylelintrc.json",
            ".stylelintrc.yaml",
            ".stylelintrc.yml",
            ".stylelintrc.js",
            "stylelint.config.js",
            "stylelint.config.cjs",
            "stylelint.config.mjs",
        )

        if not style_files:
            style_from_framework = any(
                framework in framework_signals
                for framework in ("tailwind", "styled-components", "emotion")
            )
            if style_from_framework:
                note = (
                    "styling appears in framework tooling "
                    "(tailwind/styled-components/emotion)"
                )
                return (
                    3.5,
                    note,
                    {
                        "style_files": 0,
                        "stylelint_config": has_stylelint_config,
                        "token_count": 0,
                        "module_files": 0,
                        "bem_hits": 0,
                        "framework_styling": True,
                    },
                )

            return (
                None,
                "no standalone CSS/SCSS files detected",
                {
                    "style_files": 0,
                    "stylelint_config": has_stylelint_config,
                    "token_count": 0,
                    "module_files": 0,
                    "bem_hits": 0,
                    "framework_styling": False,
                },
            )

        token_count = 0
        module_files = 0
        bem_hits = 0
        for style_file in style_files:
            file_name = style_file.name.lower()
            if ".module." in file_name:
                module_files += 1
            content = _safe_read_text(style_file).lower()
            if not content:
                continue
            token_count += len(re.findall(r"--[a-z0-9_-]+\s*:", content))
            bem_hits += len(
                re.findall(r"\.[a-z0-9]+(?:__[a-z0-9]+)?(?:--[a-z0-9]+)?", content)
            )

        has_style_dirs = self.check_file_exists(
            "styles/",
            "src/styles/",
            "assets/styles/",
            "static/css/",
        )

        score = 0.0
        if has_stylelint_config:
            score += 1.5
        if token_count >= 3:
            score += 1.5
        elif token_count >= 1:
            score += 1.0
        if module_files >= 1 or bem_hits >= 3 or has_style_dirs:
            score += 1.0
        if len(style_files) >= 3:
            score += 1.0
        else:
            score += 0.5
        if "tailwind" in framework_signals:
            score += 0.5

        score = max(0.0, min(FRONTEND_QUALITY_MAX_SCORE, score))
        note = (
            f"styles={len(style_files)}, tokens={token_count}, modules={module_files}, "
            f"stylelint={has_stylelint_config}"
        )
        details = {
            "style_files": len(style_files),
            "stylelint_config": has_stylelint_config,
            "token_count": token_count,
            "module_files": module_files,
            "bem_hits": bem_hits,
            "framework_styling": "tailwind" in framework_signals,
        }
        return score, note, details

    def _evaluate_accessibility_signal(
        self, markup_files: List[Path], html_files: List[Path]
    ) -> Tuple[Optional[float], str, Dict[str, Any]]:
        has_a11y_artifact, contrast_warnings = self._scan_accessibility_artifacts()
        if not markup_files and not has_a11y_artifact:
            return (
                None,
                "no markup or accessibility artifacts detected",
                {
                    "html_lang": False,
                    "images": 0,
                    "images_with_alt": 0,
                    "aria_attributes": 0,
                    "forms": 0,
                    "labels": 0,
                    "has_a11y_artifact": False,
                    "contrast_warnings": False,
                },
            )

        html_lang = False
        for html_file in html_files:
            content = _safe_read_text(html_file).lower()
            if re.search(r"<html[^>]*\blang\s*=", content):
                html_lang = True
                break

        img_count = 0
        img_with_alt_count = 0
        aria_attribute_count = 0
        form_count = 0
        label_count = 0
        for markup_file in markup_files:
            content = _safe_read_text(markup_file).lower()
            if not content:
                continue
            img_count += len(re.findall(r"<img\b", content))
            img_with_alt_count += len(re.findall(r"<img\b[^>]*\balt\s*=", content))
            aria_attribute_count += len(re.findall(r"\baria-[a-z-]+\s*=", content))
            form_count += len(re.findall(r"<form\b", content))
            label_count += len(re.findall(r"<label\b", content))

        if not markup_files and has_a11y_artifact:
            score = 3.0 if not contrast_warnings else 2.0
            note = "accessibility score estimated from artifact report only"
            return (
                score,
                note,
                {
                    "html_lang": html_lang,
                    "images": img_count,
                    "images_with_alt": img_with_alt_count,
                    "aria_attributes": aria_attribute_count,
                    "forms": form_count,
                    "labels": label_count,
                    "has_a11y_artifact": has_a11y_artifact,
                    "contrast_warnings": contrast_warnings,
                },
            )

        score = 0.0
        if html_lang:
            score += 1.0

        if img_count == 0:
            score += 1.0
        else:
            alt_ratio = img_with_alt_count / max(1, img_count)
            if alt_ratio >= 0.9:
                score += 1.5
            elif alt_ratio >= 0.5:
                score += 1.0
            elif img_with_alt_count > 0:
                score += 0.5

        if aria_attribute_count >= 5:
            score += 1.5
        elif aria_attribute_count >= 1:
            score += 1.0

        if form_count == 0:
            score += 1.0
        elif label_count >= form_count:
            score += 1.0
        elif label_count > 0:
            score += 0.5

        if has_a11y_artifact and not contrast_warnings:
            score += 0.5
        elif contrast_warnings:
            score -= 0.5

        score = max(0.0, min(FRONTEND_QUALITY_MAX_SCORE, score))
        note = (
            f"lang={html_lang}, img_alt={img_with_alt_count}/{img_count}, "
            f"aria attrs={aria_attribute_count}, contrast warnings={contrast_warnings}"
        )
        details = {
            "html_lang": html_lang,
            "images": img_count,
            "images_with_alt": img_with_alt_count,
            "aria_attributes": aria_attribute_count,
            "forms": form_count,
            "labels": label_count,
            "has_a11y_artifact": has_a11y_artifact,
            "contrast_warnings": contrast_warnings,
        }
        return score, note, details

    def evaluate_frontend_quality(self) -> Dict[str, Any]:
        """
        Standalone frontend quality signal (HTML/CSS/accessibility) on a 0..5 scale.
        This signal is reported separately from the core 50-point score.
        """
        frontend_files = self._iter_frontend_files(include_tests=True)
        html_files = self._iter_frontend_markup_files()
        style_files = self._iter_frontend_style_files()
        jsx_markup_files = [
            file_path
            for file_path in frontend_files
            if file_path.suffix.lower() in {".jsx", ".tsx"}
        ]
        markup_files = html_files + jsx_markup_files
        framework_signals = self._detect_frontend_frameworks()

        has_frontend_artifacts = bool(
            frontend_files or html_files or style_files or framework_signals
        )
        if not has_frontend_artifacts:
            return {
                "score": None,
                "max_score": FRONTEND_QUALITY_MAX_SCORE,
                "status": "not_applicable",
                "method": "heuristic",
                "confidence": 1.0,
                "note": "no frontend artifacts for HTML/CSS/a11y evaluation",
                "signals": {
                    "frameworks": [],
                    "html_semantics": {},
                    "css_quality": {},
                    "accessibility": {},
                },
            }

        html_score, html_note, html_details = self._evaluate_html_semantics_signal(
            markup_files, html_files
        )
        css_score, css_note, css_details = self._evaluate_css_quality_signal(
            style_files, framework_signals
        )
        a11y_score, a11y_note, a11y_details = self._evaluate_accessibility_signal(
            markup_files, html_files
        )

        component_scores: Dict[str, Optional[float]] = {
            "html_semantics": html_score,
            "css_quality": css_score,
            "accessibility": a11y_score,
        }
        component_notes = {
            "html_semantics": html_note,
            "css_quality": css_note,
            "accessibility": a11y_note,
        }
        weights = {"html_semantics": 0.4, "css_quality": 0.3, "accessibility": 0.3}

        weighted_sum = 0.0
        weight_sum = 0.0
        known_components = 0
        for component, value in component_scores.items():
            if value is None:
                continue
            weight = weights[component]
            weighted_sum += value * weight
            weight_sum += weight
            known_components += 1

        if weight_sum <= 0:
            note = "frontend artifacts detected but insufficient evidence for scoring"
            if framework_signals:
                note += f" (frameworks: {', '.join(sorted(framework_signals))})"
            return {
                "score": None,
                "max_score": FRONTEND_QUALITY_MAX_SCORE,
                "status": "unknown",
                "method": "heuristic",
                "confidence": 0.0,
                "note": note,
                "signals": {
                    "frameworks": sorted(framework_signals),
                    "html_semantics": html_details,
                    "css_quality": css_details,
                    "accessibility": a11y_details,
                },
            }

        base_score = weighted_sum / weight_sum
        framework_bonus = 0.0
        if any(
            framework in framework_signals
            for framework in ("react", "nextjs", "vue", "nuxt", "django_templates")
        ):
            framework_bonus += 0.4
        if any(
            framework in framework_signals
            for framework in ("tailwind", "styled-components", "emotion")
        ):
            framework_bonus += 0.2

        final_score = min(
            FRONTEND_QUALITY_MAX_SCORE,
            max(0.0, base_score + min(framework_bonus, 0.6)),
        )
        confidence = min(
            0.92,
            0.55
            + known_components * 0.11
            + (0.05 if a11y_details.get("has_a11y_artifact") else 0.0),
        )

        score_parts = ", ".join(
            f"{component}={value:.2f}"
            for component, value in component_scores.items()
            if value is not None
        )
        frameworks_note = ", ".join(sorted(framework_signals)) or "none"
        note = (
            f"{score_parts}; frameworks={frameworks_note}; "
            f"details: html[{component_notes['html_semantics']}], "
            f"css[{component_notes['css_quality']}], "
            f"a11y[{component_notes['accessibility']}]"
        )

        return {
            "score": round(final_score, 2),
            "max_score": FRONTEND_QUALITY_MAX_SCORE,
            "status": "known",
            "method": "heuristic",
            "confidence": round(confidence, 2),
            "note": note,
            "signals": {
                "frameworks": sorted(framework_signals),
                "html_semantics": html_details,
                "css_quality": css_details,
                "accessibility": a11y_details,
            },
        }

    def _frontend_content_contains(
        self, keywords: List[str], include_tests: bool = True
    ) -> bool:
        lowered = [keyword.lower() for keyword in keywords]
        for file_path in self._iter_frontend_files(include_tests=include_tests):
            content = _safe_read_text(file_path).lower()
            if any(keyword in content for keyword in lowered):
                return True
        for file_path in self._iter_frontend_markup_files():
            content = _safe_read_text(file_path).lower()
            if any(keyword in content for keyword in lowered):
                return True
        return False

    def _read_all_workflow_content(self) -> str:
        workflow_files = list(self.repo_path.glob(".github/workflows/*.yml")) + list(
            self.repo_path.glob(".github/workflows/*.yaml")
        )
        merged = ""
        for workflow in workflow_files:
            merged += "\n" + _safe_read_text(workflow).lower()
        return merged

    def _detect_backend_frameworks(self) -> Set[str]:
        detected: Set[str] = set()
        if self._python_content_contains(["fastapi", "from fastapi"]):
            detected.add("fastapi")
        if self._python_content_contains(["django", "manage.py", "models.model"]):
            detected.add("django")
        if self._python_content_contains(["flask", "from flask"]):
            detected.add("flask")
        if self._python_content_contains(
            ["sqlalchemy", "sqlmodel", "declarative_base", "sessionmaker"]
        ):
            detected.add("sqlalchemy")
        if self._python_content_contains(["peewee", "tortoise", "ormar"]):
            detected.add("orm")
        return detected

    def _iter_sql_files(self) -> List[Path]:
        return self._iter_non_ignored_files_by_extensions((".sql",))

    def _iter_migration_files(self) -> List[Path]:
        migration_files: List[Path] = []
        for py_file in self._iter_python_files(include_tests=True):
            try:
                rel_parts = [
                    part.lower() for part in py_file.relative_to(self.repo_path).parts
                ]
            except ValueError:
                continue
            if py_file.name == "__init__.py":
                continue
            if "migrations" in rel_parts:
                migration_files.append(py_file)
                continue
            if "alembic" in rel_parts and "versions" in rel_parts:
                migration_files.append(py_file)
        return migration_files

    def _find_potential_secret_files(self) -> List[str]:
        candidate_names = {
            ".env",
            ".env.local",
            ".env.production",
            ".env.development",
            "secrets.yml",
            "secrets.yaml",
            "credentials.json",
            "id_rsa",
            "id_dsa",
        }
        safe_env_names = {".env.example", ".env.sample", ".env.template", ".env.dist"}
        secret_tokens = ("password=", "secret=", "api_key", "token=", "private_key")
        found: Set[str] = set()
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
            "coverage",
        }
        for file_path in self.repo_path.rglob("*"):
            if not file_path.is_file():
                continue
            try:
                rel_path = file_path.relative_to(self.repo_path)
            except ValueError:
                continue
            rel_parts = [part.lower() for part in rel_path.parts]
            if any(part in excluded_dirs for part in rel_parts):
                continue
            file_name = file_path.name.lower()
            if file_name in safe_env_names or file_name not in candidate_names:
                continue
            content = _safe_read_text(file_path).lower()
            if any(token in content for token in secret_tokens):
                found.add(str(rel_path))
        return sorted(found)

    def _read_env_template_content(self) -> str:
        for file_name in (".env.example", ".env.sample", ".env.template", ".env.dist"):
            path = self.repo_path / file_name
            if path.exists() and path.is_file():
                return _safe_read_text(path).lower()
        return ""

    def _has_settings_split_signal(self) -> bool:
        return any(
            (
                (self.repo_path / "settings" / "base.py").exists()
                and (self.repo_path / "settings" / "dev.py").exists()
                and (self.repo_path / "settings" / "prod.py").exists(),
                (self.repo_path / "settings" / "base.py").exists()
                and (self.repo_path / "settings" / "development.py").exists()
                and (self.repo_path / "settings" / "production.py").exists(),
                (self.repo_path / "config" / "dev.py").exists()
                and (self.repo_path / "config" / "prod.py").exists(),
                self.check_file_exists(
                    "**/settings/base.py",
                    "**/settings/dev.py",
                    "**/settings/prod.py",
                ),
            )
        )

    def evaluate_data_layer_quality(self) -> Dict[str, Any]:
        """
        Standalone data-layer quality signal (SQL/ORM/migrations/config) on a 0..5 scale.
        """
        backend_frameworks = self._detect_backend_frameworks()
        migration_files = self._iter_migration_files()
        sql_files = self._iter_sql_files()
        has_alembic = self.check_file_exists(
            "alembic.ini", "alembic/versions/*.py", "**/alembic/versions/*.py"
        )
        has_orm_signal = bool(
            {"django", "sqlalchemy", "orm"}.intersection(backend_frameworks)
        )
        has_model_signal = self._python_content_contains(
            [
                "models.model",
                "foreignkey(",
                "relationship(",
                "mapped[",
                "declarative_base",
            ],
            include_tests=False,
        )
        has_migrations = bool(migration_files) or has_alembic

        py_files = self._iter_python_files(include_tests=False)
        index_hits = 0
        constraint_hits = 0
        for py_file in py_files:
            content = _safe_read_text(py_file).lower()
            if not content:
                continue
            index_hits += len(
                re.findall(r"(db_index\s*=\s*true|index\s*=\s*true|index\()", content)
            )
            constraint_hits += len(
                re.findall(
                    (
                        r"(uniqueconstraint|checkconstraint|foreignkey\(|"
                        r"primarykeyconstraint|constraints\s*=)"
                    ),
                    content,
                )
            )

        for sql_file in sql_files:
            content = _safe_read_text(sql_file).lower()
            if not content:
                continue
            index_hits += len(re.findall(r"(create\s+index|unique\s+index)", content))
            constraint_hits += len(
                re.findall(
                    r"(foreign\s+key|references\s+[a-z0-9_]+|check\s*\(|not\s+null)",
                    content,
                )
            )

        has_env_example = self.check_file_exists(
            ".env.example", ".env.sample", ".env.template", ".env.dist"
        )
        env_template_content = self._read_env_template_content()
        has_db_env_signal = any(
            token in env_template_content
            for token in ("database_url", "db_host", "db_name", "postgres", "mysql")
        )
        has_settings_split = self._has_settings_split_signal()
        secret_files = self._find_potential_secret_files()

        has_backend_or_data_artifacts = bool(
            py_files
            or backend_frameworks
            or migration_files
            or sql_files
            or has_alembic
        )
        if not has_backend_or_data_artifacts:
            return {
                "score": None,
                "max_score": FRONTEND_QUALITY_MAX_SCORE,
                "status": "not_applicable",
                "method": "heuristic",
                "confidence": 1.0,
                "note": "no backend/data artifacts for SQL and migration evaluation",
                "signals": {
                    "backend_frameworks": [],
                    "migrations": 0,
                    "sql_files": 0,
                    "index_hits": 0,
                    "constraint_hits": 0,
                    "env_example": False,
                    "db_env_signal": False,
                    "settings_split": False,
                    "secret_files": [],
                },
            }

        score = 0.0
        if has_orm_signal or has_model_signal:
            score += 1.2
        if has_migrations:
            score += 1.3
        if len(migration_files) >= 5:
            score += 0.7
        elif len(migration_files) >= 1:
            score += 0.4
        if index_hits >= 2:
            score += 0.8
        elif index_hits == 1:
            score += 0.4
        if constraint_hits >= 3:
            score += 0.9
        elif constraint_hits >= 1:
            score += 0.5
        if has_env_example:
            score += 0.5
        if has_db_env_signal:
            score += 0.4
        if has_settings_split:
            score += 0.5
        if secret_files:
            score -= 1.0

        score = max(0.0, min(FRONTEND_QUALITY_MAX_SCORE, score))
        evidence_count = sum(
            int(flag)
            for flag in (
                bool(backend_frameworks),
                has_orm_signal or has_model_signal,
                has_migrations,
                index_hits > 0,
                constraint_hits > 0,
                has_env_example,
                has_settings_split,
            )
        )
        confidence = min(0.9, 0.45 + evidence_count * 0.07)
        note = (
            f"frameworks={','.join(sorted(backend_frameworks)) or 'none'}, "
            f"migrations={len(migration_files)}, sql_files={len(sql_files)}, "
            f"index_hits={index_hits}, constraint_hits={constraint_hits}, "
            f"env_example={has_env_example}, settings_split={has_settings_split}, "
            f"secret_files={len(secret_files)}"
        )

        return {
            "score": round(score, 2),
            "max_score": FRONTEND_QUALITY_MAX_SCORE,
            "status": "known",
            "method": "heuristic",
            "confidence": round(confidence, 2),
            "note": note,
            "signals": {
                "backend_frameworks": sorted(backend_frameworks),
                "migrations": len(migration_files),
                "sql_files": len(sql_files),
                "index_hits": index_hits,
                "constraint_hits": constraint_hits,
                "env_example": has_env_example,
                "db_env_signal": has_db_env_signal,
                "settings_split": has_settings_split,
                "secret_files": secret_files,
            },
        }

    def evaluate_api_contract_maturity(self) -> Dict[str, Any]:
        """
        Standalone API contract maturity signal (OpenAPI/versioning/contract checks) on 0..5.
        """
        backend_frameworks = self._detect_backend_frameworks()
        has_fastapi = "fastapi" in backend_frameworks
        has_django = "django" in backend_frameworks
        has_openapi = self.check_file_exists(
            "openapi.json",
            "openapi.yaml",
            "openapi.yml",
            "swagger.json",
            "swagger.yaml",
            "swagger.yml",
        )
        has_postman = self.check_file_exists("*.postman_collection.json")
        has_schema_tooling = self._python_content_contains(
            [
                "drf-spectacular",
                "get_schema_view",
                "swagger_auto_schema",
                "openapi",
                "spectral",
                "schemathesis",
            ],
            include_tests=True,
        ) or self._has_package_script(
            "schemathesis", "spectral", "dredd", "openapi-diff"
        )
        has_versioning_signal = self._python_content_contains(
            ["/api/v1", "/v1/", "versioning", "default_versioning_class"],
            include_tests=True,
        ) or self._frontend_content_contains(["/api/v1", "/v1/", "api_version"])
        has_contract_tests = self.check_file_exists(
            "tests/**/*contract*.py",
            "tests/**/*schema*.py",
            "schemathesis.yaml",
            "schemathesis.yml",
            ".spectral.yaml",
            ".spectral.yml",
            "**/*contract*.test.ts",
            "**/*contract*.spec.ts",
        ) or self._has_package_script("schemathesis", "dredd", "spectral")
        workflow_content = self._read_all_workflow_content()
        has_contract_ci = any(
            token in workflow_content
            for token in ("schemathesis", "spectral", "openapi", "swagger", "dredd")
        )

        has_api_artifacts = bool(
            has_fastapi
            or has_django
            or has_openapi
            or has_postman
            or has_schema_tooling
            or self.check_file_exists("app.py", "main.py")
            and self._python_content_contains(["api", "router", "endpoint"])
        )
        if not has_api_artifacts:
            return {
                "score": None,
                "max_score": FRONTEND_QUALITY_MAX_SCORE,
                "status": "not_applicable",
                "method": "heuristic",
                "confidence": 1.0,
                "note": "no API artifacts detected for contract maturity evaluation",
                "signals": {
                    "openapi": False,
                    "postman": False,
                    "schema_tooling": False,
                    "versioning": False,
                    "contract_tests": False,
                    "contract_ci": False,
                },
            }

        score = 0.0
        if has_openapi:
            score += 2.0
        elif has_postman or has_schema_tooling:
            score += 1.2
        elif has_fastapi or has_django:
            score += 0.8

        if has_versioning_signal:
            score += 1.0
        if has_contract_tests:
            score += 1.3
        if has_contract_ci:
            score += 0.7

        score = max(0.0, min(FRONTEND_QUALITY_MAX_SCORE, score))
        evidence_count = sum(
            int(flag)
            for flag in (
                has_openapi,
                has_postman,
                has_schema_tooling,
                has_versioning_signal,
                has_contract_tests,
                has_contract_ci,
            )
        )
        confidence = min(0.9, 0.45 + evidence_count * 0.08)
        note = (
            f"openapi={has_openapi}, postman={has_postman}, schema_tooling={has_schema_tooling}, "
            f"versioning={has_versioning_signal}, contract_tests={has_contract_tests}, "
            f"contract_ci={has_contract_ci}"
        )

        return {
            "score": round(score, 2),
            "max_score": FRONTEND_QUALITY_MAX_SCORE,
            "status": "known",
            "method": "heuristic",
            "confidence": round(confidence, 2),
            "note": note,
            "signals": {
                "openapi": has_openapi,
                "postman": has_postman,
                "schema_tooling": has_schema_tooling,
                "versioning": has_versioning_signal,
                "contract_tests": has_contract_tests,
                "contract_ci": has_contract_ci,
            },
        }

    def evaluate_fullstack_maturity(self) -> Dict[str, Any]:
        """
        Standalone full-stack integration signal for repositories containing backend+frontend.
        """
        backend_frameworks = self._detect_backend_frameworks()
        has_backend = bool(
            self._iter_python_files(include_tests=False) or backend_frameworks
        )
        has_frontend = bool(
            self._iter_frontend_files(include_tests=False)
            or self._iter_frontend_markup_files()
            or self._load_package_json()
        )
        if not (has_backend and has_frontend):
            return {
                "score": None,
                "max_score": FRONTEND_QUALITY_MAX_SCORE,
                "status": "not_applicable",
                "method": "heuristic",
                "confidence": 1.0,
                "note": "full-stack maturity applies only to repositories with backend and frontend",
                "signals": {
                    "backend": has_backend,
                    "frontend": has_frontend,
                    "split_layout": False,
                    "api_link": False,
                    "compose": False,
                    "mixed_ci": False,
                    "workspace": False,
                },
            }

        has_split_layout = self.check_file_exists(
            "backend/",
            "frontend/",
            "client/",
            "server/",
            "apps/api/",
            "apps/web/",
        )
        has_api_link_signal = self._frontend_content_contains(
            ["/api/", "api_url", "axios", "fetch("], include_tests=True
        ) and self._python_content_contains(
            ["router", "api", "corsmiddleware", "include_router"],
            include_tests=True,
        )
        has_compose = False
        for compose_name in ("docker-compose.yml", "docker-compose.yaml"):
            compose_path = self.repo_path / compose_name
            if not compose_path.exists():
                continue
            compose_content = _safe_read_text(compose_path).lower()
            if "services:" not in compose_content:
                continue
            has_db_service = any(
                token in compose_content
                for token in ("postgres", "mysql", "mariadb", "mongo", "redis")
            )
            has_front_service = any(
                token in compose_content
                for token in ("frontend", "node", "nginx", "vite", "next")
            )
            has_back_service = any(
                token in compose_content
                for token in ("backend", "api", "web", "gunicorn", "uvicorn")
            )
            if has_db_service and has_front_service and has_back_service:
                has_compose = True
                break

        workflow_content = self._read_all_workflow_content()
        has_mixed_ci = any(
            token in workflow_content for token in ("pytest", "python -m unittest")
        ) and any(
            token in workflow_content for token in ("npm", "pnpm", "yarn", "vitest")
        )
        package_json = self._load_package_json()
        has_workspace = isinstance(package_json.get("workspaces"), (list, dict))

        score = 1.0
        if has_split_layout:
            score += 1.0
        if has_api_link_signal:
            score += 1.2
        if has_compose:
            score += 1.0
        if has_mixed_ci:
            score += 1.0
        if has_workspace:
            score += 0.8

        score = max(0.0, min(FRONTEND_QUALITY_MAX_SCORE, score))
        evidence_count = sum(
            int(flag)
            for flag in (
                has_split_layout,
                has_api_link_signal,
                has_compose,
                has_mixed_ci,
                has_workspace,
            )
        )
        confidence = min(0.9, 0.5 + evidence_count * 0.08)
        note = (
            f"backend={has_backend}, frontend={has_frontend}, split_layout={has_split_layout}, "
            f"api_link={has_api_link_signal}, compose={has_compose}, "
            f"mixed_ci={has_mixed_ci}, workspace={has_workspace}"
        )

        return {
            "score": round(score, 2),
            "max_score": FRONTEND_QUALITY_MAX_SCORE,
            "status": "known",
            "method": "heuristic",
            "confidence": round(confidence, 2),
            "note": note,
            "signals": {
                "backend": has_backend,
                "frontend": has_frontend,
                "split_layout": has_split_layout,
                "api_link": has_api_link_signal,
                "compose": has_compose,
                "mixed_ci": has_mixed_ci,
                "workspace": has_workspace,
            },
        }

    @staticmethod
    def _count_npm_audit_vulns(raw_output: str) -> Optional[int]:
        try:
            payload = json.loads(raw_output)
        except (ValueError, TypeError):
            return None

        if not isinstance(payload, dict):
            return None

        metadata = payload.get("metadata", {})
        if isinstance(metadata, dict):
            vulnerabilities = metadata.get("vulnerabilities", {})
            if isinstance(vulnerabilities, dict):
                total = vulnerabilities.get("total")
                if isinstance(total, (int, float)):
                    return int(total)
                sum_fields = 0
                for field in ("critical", "high", "moderate", "low", "info"):
                    val = vulnerabilities.get(field)
                    if isinstance(val, (int, float)):
                        sum_fields += int(val)
                if sum_fields > 0:
                    return sum_fields

        vulnerabilities_raw = payload.get("vulnerabilities")
        if isinstance(vulnerabilities_raw, dict):
            # npm v7+ shape: map package => advisory info
            counted = 0
            for issue in vulnerabilities_raw.values():
                if isinstance(issue, dict):
                    severity = str(issue.get("severity", "")).strip().lower()
                    if severity:
                        counted += 1
            return counted

        advisories = payload.get("advisories")
        if isinstance(advisories, dict):
            return len(advisories)

        return None

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

        frontend_coverage = self._extract_frontend_coverage_percent()
        if frontend_coverage is not None:
            return frontend_coverage

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

        has_python_tests = self.check_file_exists("tests/**/*.py", "test_*.py")
        has_frontend_tests = self._has_frontend_tests()
        if has_python_tests or has_frontend_tests:
            test_sources: List[str] = []
            if has_python_tests:
                test_sources.append("python")
            if has_frontend_tests:
                test_sources.append("frontend")
            return self._make_result(
                "test_coverage",
                1.5,
                status="known",
                method="heuristic",
                confidence=0.45,
                note=(
                    "tests detected"
                    f" ({'/'.join(test_sources)}) but no coverage report"
                ),
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
        if py_files:
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
                return self._make_result(
                    "type_hints", None, method="measured", note=note
                )

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

            note = (
                f"hinted functions: {hinted_functions}/{total_functions} "
                f"({coverage_percent:.1f}%)"
            )
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

        has_frontend = (
            self._repo_has_frontend_code() or (self.repo_path / "package.json").exists()
        )
        has_ts = (
            self._repo_has_typescript() or (self.repo_path / "tsconfig.json").exists()
        )
        if not has_frontend:
            return self._make_result(
                "type_hints",
                None,
                method="measured",
                note="no Python or frontend files found to evaluate typing discipline",
            )
        if not has_ts:
            return self._make_not_applicable_result("type_hints")

        compiler_options, parse_error = self._read_tsconfig_compiler_options()
        if parse_error:
            return self._make_result(
                "type_hints",
                None,
                method="measured",
                note=parse_error,
            )
        compiler_options = compiler_options or {}

        strict = bool(compiler_options.get("strict"))
        no_implicit_any = bool(compiler_options.get("noImplicitAny"))
        strict_null_checks = bool(compiler_options.get("strictNullChecks"))
        flags_enabled = sum(
            1 for value in (strict, no_implicit_any, strict_null_checks) if value
        )

        if strict and no_implicit_any and strict_null_checks:
            score = 5.0
        elif strict and (no_implicit_any or strict_null_checks):
            score = 4.0
        elif flags_enabled >= 2:
            score = 3.0
        elif flags_enabled == 1:
            score = 2.0
        else:
            score = 1.0

        note = (
            "tsconfig strictness: "
            f"strict={strict}, noImplicitAny={no_implicit_any}, strictNullChecks={strict_null_checks}"
        )
        return self._make_result(
            "type_hints",
            score,
            status="known",
            method="measured",
            confidence=0.8,
            note=note,
        )

    # ========== БЛОК 2 / BLOCK 2: SECURITY & DEPENDENCIES (10 баллов / points) ==========

    def evaluate_vulnerabilities(self) -> CriterionResult:
        """
        Оценка: Dependency Vulnerabilities (макс 5 баллов)
        Evaluation: Dependency Vulnerabilities (max 5 points)
        """
        dep_files = list(self.repo_path.glob("requirements*.txt"))
        has_python_manifest = bool(dep_files) or self.check_file_exists(
            "pyproject.toml", "Pipfile", "poetry.lock"
        )
        has_node_manifest = (self.repo_path / "package.json").exists()
        has_manifest = has_python_manifest or has_node_manifest

        if not has_manifest:
            return self._make_result(
                "vulnerabilities",
                None,
                method="heuristic",
                note="no dependency manifest found",
            )

        # 1) Try to consume existing pip-audit report if present.
        pip_audit_report = self.repo_path / "pip-audit-report.json"
        if pip_audit_report.exists() and has_python_manifest:
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

        # 2) Try to consume existing npm audit report if present.
        npm_audit_report = self.repo_path / "npm-audit-report.json"
        if npm_audit_report.exists() and has_node_manifest:
            raw = _safe_read_text(npm_audit_report)
            npm_vuln_count = self._count_npm_audit_vulns(raw)
            if npm_vuln_count is not None:
                return self._make_result(
                    "vulnerabilities",
                    self._vuln_count_to_score(npm_vuln_count),
                    status="known",
                    method="measured",
                    confidence=0.9,
                    note=f"npm audit report vulnerabilities: {npm_vuln_count}",
                )

        # 3) Try to run pip-audit, if available.
        pip_audit_path = shutil.which("pip-audit")
        if pip_audit_path and dep_files and has_python_manifest:
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

        # 4) Try to run safety, if available.
        safety_path = shutil.which("safety")
        if safety_path and dep_files and has_python_manifest:
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

        # 5) Try to run npm audit for Node projects.
        npm_path = shutil.which("npm")
        if npm_path and has_node_manifest:
            command = [npm_path, "audit", "--json"]
            ok, stdout, stderr, error = self._run_tool(
                command, timeout_sec=self.constants.SECURITY_TOOL_TIMEOUT_SEC
            )
            raw_output = stdout if stdout.strip() else stderr
            npm_vuln_count = self._count_npm_audit_vulns(raw_output)
            if npm_vuln_count is not None:
                note = f"npm audit vulnerabilities: {npm_vuln_count}"
                if not ok and error:
                    note += f"; command status: {error}"
                return self._make_result(
                    "vulnerabilities",
                    self._vuln_count_to_score(npm_vuln_count),
                    status="known",
                    method="measured",
                    confidence=0.88,
                    note=note,
                )

        # 6) Heuristic fallback without claiming perfect security.
        score = 2.5
        fallback_reason = []
        if has_python_manifest and not pip_audit_path:
            fallback_reason.append("pip-audit not installed")
        if has_python_manifest and not safety_path:
            fallback_reason.append("safety not installed")
        if has_node_manifest and not npm_path:
            fallback_reason.append("npm not installed")
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
        if has_node_manifest:
            dep_count = self._count_node_dependencies()
            if dep_count > self.constants.HIGH_DEPENDENCIES:
                score = min(score, 1.5)
                note = (
                    "very large npm dependency surface detected; "
                    "automatic audit not available"
                )

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
        has_node_manifest = (self.repo_path / "package.json").exists()
        if not dep_files and not has_node_manifest:
            return self._make_result(
                "dep_health",
                None,
                method="measured",
                note="no requirements/package.json file found for dependency count",
            )

        try:
            dep_count = 0
            source = "python"
            if dep_files:
                for req_file in dep_files:
                    for line in req_file.read_text(errors="ignore").splitlines():
                        stripped = line.strip()
                        if stripped and not stripped.startswith("#"):
                            dep_count += 1
            elif has_node_manifest:
                dep_count = self._count_node_dependencies()
                source = "node"

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
                note=f"dependency entries counted ({source}): {dep_count}",
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
        has_dependabot = self.check_file_exists(".github/dependabot.yml")

        workflow_files = list(self.repo_path.glob(".github/workflows/*.yml")) + list(
            self.repo_path.glob(".github/workflows/*.yaml")
        )
        workflow_content = ""
        for workflow in workflow_files:
            workflow_content += "\n" + _safe_read_text(workflow).lower()

        has_bandit = "bandit" in workflow_content
        has_safety = "safety" in workflow_content
        has_pip_audit = "pip-audit" in workflow_content
        has_npm_audit = (
            "npm audit" in workflow_content or "audit-ci" in workflow_content
        )
        has_package_audit_script = self._has_package_script("audit", "snyk")

        scanner_signal = (
            has_bandit
            or has_safety
            or has_pip_audit
            or has_npm_audit
            or has_package_audit_script
        )
        if has_dependabot and scanner_signal:
            score = 2.0
        elif has_dependabot or scanner_signal:
            score = 1.0
        else:
            score = 0.0

        return self._make_result(
            "security_scanning",
            score,
            status="known",
            method="heuristic",
            confidence=0.65,
            note=(
                "dependabot="
                f"{has_dependabot}, bandit={has_bandit}, safety={has_safety}, "
                f"pip_audit={has_pip_audit}, npm_audit={has_npm_audit}, "
                f"script_audit={has_package_audit_script}"
            ),
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

            # Проверяем package.json (для JS/TS стеков)
            # Check package.json (for JS/TS stacks)
            package_json = self.repo_path / "package.json"
            if package_json.exists():
                data = _safe_load_json(package_json) or {}
                version_raw = str(data.get("version", "")).strip()
                if version_raw:
                    score = max(
                        score, self._extract_version_score(f'version="{version_raw}"')
                    )
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
                note="no setup.py/pyproject/package.json version metadata found",
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
        has_src = self.check_file_exists("src/")
        has_python_tests = self.check_file_exists("tests/", "test_*.py")
        has_frontend_tests = self._has_frontend_tests()
        has_tests = has_python_tests or has_frontend_tests
        has_docs = self.check_file_exists("docs/") or self.check_file_exists(
            "mkdocs.yml"
        )

        python_score = 0.0
        if has_src and has_python_tests and has_docs:
            python_score = 2.0
        elif has_src and has_python_tests:
            python_score = 1.5
        elif has_src or has_python_tests:
            python_score = 1.0

        has_frontend_dirs = self.check_file_exists(
            "src/",
            "app/",
            "components/",
            "pages/",
            "public/",
        )
        has_frontend_config = self.check_file_exists(
            "package.json",
            "tsconfig.json",
            "vite.config.ts",
            "vite.config.js",
            "next.config.js",
            "next.config.mjs",
        )
        frontend_score = 0.0
        if has_frontend_dirs and has_frontend_tests and has_docs:
            frontend_score = 2.0
        elif has_frontend_dirs and has_frontend_tests:
            frontend_score = 1.5
        elif has_frontend_dirs or has_frontend_config:
            frontend_score = 1.0

        score = max(python_score, frontend_score)

        return self._make_result(
            "structure",
            score,
            status="known",
            method="heuristic",
            confidence=0.75,
            note=(
                f"src={has_src}, tests={has_tests}, docs={has_docs}, "
                f"frontend_dirs={has_frontend_dirs}, frontend_config={has_frontend_config}"
            ),
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
        notes: List[str] = []

        # Можно ли запустить за 1-2 команды?
        # Can it be run in 1-2 commands?
        if self.check_file_exists("Makefile"):
            score = 2.0
            notes.append("Makefile detected")
        elif self.check_file_exists("docker-compose.yml", "docker-compose.yaml"):
            score = 2.0
            notes.append("docker-compose detected")
        elif self.check_file_exists("run.sh", "start.sh"):
            score = 1.5
            notes.append("run/start script detected")
        elif self.check_content_contains(
            "README*.md", ["docker-compose up", "python main.py"]
        ):
            score = 1.0
            notes.append("README quick-start command detected")

        package_json = self._load_package_json()
        scripts = package_json.get("scripts", {})
        if isinstance(scripts, dict):
            script_buckets = {
                "lint": False,
                "test": False,
                "build": False,
                "typecheck": False,
            }
            for key, value in scripts.items():
                key_lower = str(key).lower()
                value_lower = str(value).lower()
                if "lint" in key_lower or "eslint" in value_lower:
                    script_buckets["lint"] = True
                if (
                    "test" in key_lower
                    or "vitest" in value_lower
                    or "jest" in value_lower
                ):
                    script_buckets["test"] = True
                if (
                    "build" in key_lower
                    or "vite build" in value_lower
                    or "next build" in value_lower
                ):
                    script_buckets["build"] = True
                if (
                    "typecheck" in key_lower
                    or "tsc --noemit" in value_lower
                    or "tsc -noemit" in value_lower
                ):
                    script_buckets["typecheck"] = True

            script_score = float(
                sum(1 for enabled in script_buckets.values() if enabled)
            )
            if script_score >= 3:
                score = max(score, 2.0)
            elif script_score == 2:
                score = max(score, 1.5)
            elif script_score == 1:
                score = max(score, 1.0)
            notes.append(
                "package scripts: "
                + ", ".join(
                    f"{name}={enabled}" for name, enabled in script_buckets.items()
                )
            )

        return self._make_result(
            "getting_started",
            score,
            status="known",
            method="heuristic",
            confidence=0.7,
            note="; ".join(notes) if notes else "quick-start artifacts scanned",
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
            and criteria[key].status != "not_applicable"
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
            if item.score is not None and item.status == "known"
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
                "test_coverage": self._evaluate_criterion(
                    "test_coverage", self.evaluate_test_coverage
                ),
                "code_complexity": self._evaluate_criterion(
                    "code_complexity", self.evaluate_code_complexity
                ),
                "type_hints": self._evaluate_criterion(
                    "type_hints", self.evaluate_type_hints
                ),
                "vulnerabilities": self._evaluate_criterion(
                    "vulnerabilities", self.evaluate_vulnerabilities
                ),
                "dep_health": self._evaluate_criterion(
                    "dep_health", self.evaluate_dependency_health
                ),
                "security_scanning": self._evaluate_criterion(
                    "security_scanning", self.evaluate_security_scanning
                ),
                "project_activity": self._evaluate_criterion(
                    "project_activity", self.evaluate_project_activity
                ),
                "version_stability": self._evaluate_criterion(
                    "version_stability", self.evaluate_version_stability
                ),
                "changelog": self._evaluate_criterion(
                    "changelog", self.evaluate_changelog
                ),
                "docstrings": self._evaluate_criterion(
                    "docstrings", self.evaluate_docstrings
                ),
                "logging": self._evaluate_criterion("logging", self.evaluate_logging),
                "structure": self._evaluate_criterion(
                    "structure", self.evaluate_project_structure
                ),
                "readme": self._evaluate_criterion(
                    "readme", self.evaluate_readme_quality
                ),
                "api_docs": self._evaluate_criterion(
                    "api_docs", self.evaluate_api_documentation
                ),
                "getting_started": self._evaluate_criterion(
                    "getting_started", self.evaluate_getting_started
                ),
                "docker": self._evaluate_criterion("docker", self.evaluate_docker),
                "cicd": self._evaluate_criterion("cicd", self.evaluate_cicd),
            }
        )

        blocks_meta: Dict[str, Dict[str, Optional[float]]] = {}
        for block_key, block_max in self.constants.BLOCK_MAX_SCORES.items():
            block_criteria = [
                key
                for key, criterion_block in self.constants.CRITERION_BLOCK.items()
                if criterion_block == block_key
            ]
            applicable_items = [
                criteria[key]
                for key in block_criteria
                if criteria[key].status != "not_applicable"
            ]
            known_items = [
                item
                for item in applicable_items
                if item.score is not None and item.status == "known"
            ]

            known_score = sum(
                item.score for item in known_items if item.score is not None
            )
            known_max = sum(item.max_score for item in known_items)
            applicable_max = sum(item.max_score for item in applicable_items)
            block_score = (
                (known_score / known_max) * block_max if known_max > 0 else None
            )
            coverage_percent = (
                (known_max / applicable_max) * 100 if applicable_max > 0 else 0.0
            )

            blocks_meta[block_key] = {
                "score": round(block_score, 2) if block_score is not None else None,
                "known_score": round(known_score, 2),
                "known_max": round(known_max, 2),
                "applicable_max": round(applicable_max, 2),
                "max_score": round(block_max, 2),
                "data_coverage_percent": round(coverage_percent, 2),
            }

        applicable_total_max = sum(
            criterion.max_score
            for criterion in criteria.values()
            if criterion.status != "not_applicable"
        )
        known_total_score = sum(
            criterion.score
            for criterion in criteria.values()
            if criterion.score is not None and criterion.status == "known"
        )
        known_total_max = sum(
            criterion.max_score
            for criterion in criteria.values()
            if criterion.score is not None and criterion.status == "known"
        )

        if known_total_max > 0:
            total_score = (
                known_total_score / known_total_max
            ) * self.constants.TOTAL_MAX_SCORE
        else:
            total_score = 0.0

        data_coverage_percent = (
            (known_total_max / applicable_total_max) * 100
            if applicable_total_max > 0
            else 0.0
        )
        frontend_quality_meta = self.evaluate_frontend_quality()
        data_layer_quality_meta = self.evaluate_data_layer_quality()
        api_contract_maturity_meta = self.evaluate_api_contract_maturity()
        fullstack_maturity_meta = self.evaluate_fullstack_maturity()

        results: Dict[str, Any] = {
            "repo": self.repo_name,
            "path": str(self.repo_path),
            "stack_profile": self.stack_profile,
            "total_score": round(total_score, 2),
            "max_score": self.constants.TOTAL_MAX_SCORE,
            "raw_max_score": round(applicable_total_max, 2),
            "known_score": round(known_total_score, 2),
            "known_max_score": round(known_total_max, 2),
            "data_coverage_percent": round(data_coverage_percent, 2),
            "frontend_quality": frontend_quality_meta.get("score"),
            "frontend_quality_meta": frontend_quality_meta,
            "data_layer_quality": data_layer_quality_meta.get("score"),
            "data_layer_quality_meta": data_layer_quality_meta,
            "api_contract_maturity": api_contract_maturity_meta.get("score"),
            "api_contract_maturity_meta": api_contract_maturity_meta,
            "fullstack_maturity": fullstack_maturity_meta.get("score"),
            "fullstack_maturity_meta": fullstack_maturity_meta,
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
