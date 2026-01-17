#!/usr/bin/env python3
"""
РАСШИРЕННЫЙ СКРИПТ ОЦЕНКИ ПОРТФОЛИО / ENHANCED PORTFOLIO EVALUATION SCRIPT
18 Критериев / 50 Баллов - Production Readiness Score v2
18 Criteria / 50 Points - Production Readiness Score v2

Методика / Methodology: Weighted Rubric Scoring с измерением КАЧЕСТВА кода
                        Weighted Rubric Scoring with code QUALITY measurement
Дата / Date: 10 января 2026 / January 10, 2026
Версия / Version: 2.2 (Enhanced & Fixed + GitHub Integration)

Блоки / Blocks:
  1. CODE QUALITY & STABILITY (15 баллов / points)
  2. SECURITY & DEPENDENCIES (10 баллов / points)
  3. MAINTENANCE & MATURITY (10 баллов / points)
  4. ARCHITECTURE & ENGINEERING (10 баллов / points)
  5. DOCUMENTATION & UX (10 баллов / points)
  6. DEPLOYMENT & DEVOPS (5 баллов / points)
  
ИТОГО / TOTAL: 50 баллов / points

Использование / Usage:
  1. Локальная папка / Local folder:
     python enhanced_evaluate_portfolio.py
     
  2. GitHub аккаунт / GitHub account:
     python enhanced_evaluate_portfolio.py --github username
     python enhanced_evaluate_portfolio.py -g username
     
  3. С указанием папки для клонирования / With clone directory:
     python enhanced_evaluate_portfolio.py --github username --output ./repos
"""

import json
import subprocess
import re
import logging
import argparse
import shutil
import tempfile
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# Настройка логирования / Logging configuration
logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


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
            if pattern.endswith('/'):
                dir_name = pattern.rstrip('/')
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
                content = file_path.read_text(errors='ignore').lower()
                if any(kw.lower() in content for kw in keywords):
                    return True
        except (IOError, OSError, PermissionError) as e:
            logger.warning(f"Error reading file {file_pattern}: {e}")
        return False
    
    # ========== БЛОК 1 / BLOCK 1: CODE QUALITY & STABILITY (15 баллов / points) ==========
    
    def evaluate_test_coverage(self) -> float:
        """
        Оценка: Test Coverage % (макс 5 баллов)
        Evaluation: Test Coverage % (max 5 points)
        """
        score = 0.0
        
        try:
            # Пытаемся найти .coverage файл
            # Try to find .coverage file
            if self.check_file_exists(".coverage", "htmlcov/status.json"):
                # Есть тесты - минимум 1 балл
                # Tests exist - minimum 1 point
                score = 1.0
                
            # Пытаемся запустить pytest если есть
            # Try to run pytest if available
            if self.check_file_exists("tests/**/*.py", "test_*.py"):
                score = max(score, 2.0)  # Есть тесты = минимум 2 балла / Tests exist = min 2 points
                
        except (IOError, OSError) as e:
            logger.warning(f"Error checking test coverage: {e}")
        
        # Без подробного запуска pytest даём оценку по наличию файлов
        # Without running pytest, we evaluate based on file presence
        # В реальном скрипте нужно будет запустить: pytest --cov
        # In real script, need to run: pytest --cov
        return min(score, 5.0)
    
    def evaluate_code_complexity(self) -> float:
        """
        Оценка: Code Complexity (макс 5 баллов)
        Evaluation: Code Complexity (max 5 points)
        """
        score = 0.0
        
        # Проверяем наличие линтеров (косвенный показатель)
        # Check for linters (indirect indicator)
        if self.check_content_contains("requirements*.txt", ["pylint", "radon"]):
            score = 3.0
        elif self.check_file_exists("src/**/*.py", "*.py"):
            # Базовая оценка за наличие кода
            # Basic score for code presence
            score = 1.0
        
        # Хорошая практика: функции не больше 50 строк = сложность низкая
        # Good practice: functions no more than 50 lines = low complexity
        # Это требует глубокого анализа кода
        # This requires deep code analysis
        return min(score, 5.0)
    
    def evaluate_type_hints(self) -> float:
        """
        Оценка: Type Hints Coverage % (макс 5 баллов)
        Evaluation: Type Hints Coverage % (max 5 points)
        """
        score = 0.0
        
        # Проверяем наличие mypy конфига
        # Check for mypy config
        if self.check_file_exists("mypy.ini", "pyrightconfig.json", ".pyright.json"):
            score = 2.0
        
        # Проверяем использование type hints в коде
        # Check for type hints usage in code
        try:
            total_files = 0
            type_hint_files = 0
            
            for py_file in self.repo_path.glob("src/**/*.py"):
                content = py_file.read_text(errors='ignore')
                total_files += 1
                
                # Ищем type hints (-> Type)
                # Look for type hints (-> Type)
                if " -> " in content and "def " in content:
                    type_hint_files += 1
            
            if total_files > 0:
                coverage_percent = (type_hint_files / total_files) * 100
                if coverage_percent >= self.constants.COVERAGE_EXCELLENT:
                    score = 5.0
                elif coverage_percent >= self.constants.COVERAGE_GOOD:
                    score = 4.0
                elif coverage_percent >= self.constants.COVERAGE_MEDIUM:
                    score = 3.0
                elif coverage_percent >= self.constants.COVERAGE_LOW:
                    score = 2.0
                else:
                    score = max(score, 0.5)
        except (IOError, OSError, PermissionError) as e:
            logger.warning(f"Error evaluating type hints: {e}")
        
        return min(score, 5.0)
    
    # ========== БЛОК 2 / BLOCK 2: SECURITY & DEPENDENCIES (10 баллов / points) ==========
    
    def evaluate_vulnerabilities(self) -> float:
        """
        Оценка: Dependency Vulnerabilities (макс 5 баллов)
        Evaluation: Dependency Vulnerabilities (max 5 points)
        """
        score = 5.0  # По умолчанию считаем что нет / Default: assume none
        
        # Проверяем наличие bandit и safety конфигов
        # Check for bandit and safety configs
        if self.check_file_exists(".bandit", ".safety.json"):
            score = 4.0  # Есть сканирование = меньше уязвимостей / Scanning = fewer vulnerabilities
        
        # Проверяем requirements на очень старые пакеты
        # Check requirements for very old packages
        if self.check_file_exists("requirements*.txt"):
            try:
                for req_file in self.repo_path.glob("requirements*.txt"):
                    content = req_file.read_text(errors='ignore').lower()
                    # Очень старые пакеты = красный флаг
                    # Very old packages = red flag
                    if "flask==0.9" in content or "django==1.0" in content:
                        score = 1.0
                        break
            except (IOError, OSError, PermissionError) as e:
                logger.warning(f"Error checking vulnerabilities: {e}")
        
        return min(score, 5.0)
    
    def evaluate_dependency_health(self) -> float:
        """
        Оценка: Dependency Health (макс 3 балла)
        Evaluation: Dependency Health (max 3 points)
        """
        score = 1.0
        
        try:
            for req_file in self.repo_path.glob("requirements*.txt"):
                lines = len(req_file.read_text(errors='ignore').split('\n'))
                
                if lines < self.constants.MAX_HEALTHY_DEPENDENCIES:
                    score = 3.0
                elif lines < self.constants.MEDIUM_DEPENDENCIES:
                    score = 2.5
                elif lines < self.constants.HIGH_DEPENDENCIES:
                    score = 2.0
                else:
                    score = 1.0
                break
        except (IOError, OSError, PermissionError) as e:
            logger.warning(f"Error evaluating dependency health: {e}")
        
        return min(score, 3.0)
    
    def evaluate_security_scanning(self) -> float:
        """
        Оценка: Security Scanning (макс 2 балла)
        Evaluation: Security Scanning (max 2 points)
        """
        score = 0.0
        
        # Проверяем наличие инструментов безопасности
        # Check for security tools
        has_dependabot = self.check_file_exists(".github/dependabot.yml")
        has_bandit = self.check_content_contains(".github/workflows/*.yml", ["bandit"])
        has_safety = self.check_content_contains(".github/workflows/*.yml", ["safety"])
        
        if has_dependabot and (has_bandit or has_safety):
            score = 2.0
        elif has_dependabot or has_bandit or has_safety:
            score = 1.0
        
        return min(score, 2.0)
    
    # ========== БЛОК 3 / BLOCK 3: MAINTENANCE & MATURITY (10 баллов / points) ==========
    
    def evaluate_project_activity(self) -> float:
        """
        Оценка: Project Activity (макс 5 баллов)
        Evaluation: Project Activity (max 5 points)
        """
        score = 0.0
        
        try:
            # Проверяем дату последнего коммита
            # Check last commit date
            result = subprocess.run(
                ['git', 'log', '-1', '--format=%ci'],  # %ci - ISO 8601 format
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0 and result.stdout.strip():
                date_str = result.stdout.strip()
                # Парсим формат git ISO: "2024-01-10 12:34:56 +0300"
                # Parse git ISO format: "2024-01-10 12:34:56 +0300"
                try:
                    # Убираем timezone для простоты парсинга
                    # Remove timezone for simpler parsing
                    date_part = date_str.split(' +')[0].split(' -')[0]
                    last_commit_date = datetime.strptime(date_part.strip(), "%Y-%m-%d %H:%M:%S")
                    days_ago = (datetime.now() - last_commit_date).days
                except (ValueError, AttributeError, IndexError) as e:
                    # Если парсинг не удался, считаем что проект старый
                    # If parsing failed, assume project is old
                    logger.warning(f"Error parsing date '{date_str}': {e}")
                    days_ago = 999
                
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
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError) as e:
            # Если нет .git или ошибка - даём оценку по файлам
            # If no .git or error - evaluate by files
            logger.warning(f"Git command failed: {e}")
            if self.check_file_exists("**/*.py"):
                score = 1.0
        
        return min(score, 5.0)
    
    def _extract_version_score(self, content: str) -> float:
        """
        Извлекает оценку из версии в файле
        Extracts score from version in file
        """
        match = re.search(r'version\s*=\s*["\']([0-9.]+)["\']', content)
        if match:
            version = match.group(1)
            try:
                major = int(version.split('.')[0])
                
                if major >= 1:
                    return 3.0
                elif major == 0 and len(version.split('.')) > 1:
                    minor = int(version.split('.')[1])
                    if minor >= 5:
                        return 2.0
                    else:
                        return 1.0
            except (ValueError, IndexError):
                pass
        return 0.0
    
    def evaluate_version_stability(self) -> float:
        """
        Оценка: Version Stability (макс 3 балла)
        Evaluation: Version Stability (max 3 points)
        """
        score = 0.0
        
        try:
            # Проверяем setup.py
            # Check setup.py
            if self.check_file_exists("setup.py"):
                content = Path(self.repo_path / "setup.py").read_text(errors='ignore')
                score = max(score, self._extract_version_score(content))
            
            # Проверяем pyproject.toml
            # Check pyproject.toml
            if self.check_file_exists("pyproject.toml"):
                content = Path(self.repo_path / "pyproject.toml").read_text(errors='ignore')
                score = max(score, self._extract_version_score(content))
                
        except (IOError, OSError, PermissionError) as e:
            logger.warning(f"Error evaluating version stability: {e}")
        
        return min(score, 3.0)
    
    def evaluate_changelog(self) -> float:
        """
        Оценка: CHANGELOG (макс 2 балла)
        Evaluation: CHANGELOG (max 2 points)
        """
        score = 0.0
        
        if self.check_file_exists("CHANGELOG.md", "CHANGELOG.txt", "HISTORY.md"):
            try:
                # Пытаемся найти CHANGELOG файл
                # Try to find CHANGELOG file
                changelog_files = list(self.repo_path.glob("CHANGELOG*")) + \
                                 list(self.repo_path.glob("HISTORY.md"))
                if changelog_files:
                    changelog_path = changelog_files[0]
                    content = changelog_path.read_text(errors='ignore')
                    
                    # Проверяем полноту CHANGELOG
                    # Check CHANGELOG completeness
                    if len(content) > self.constants.MIN_CHANGELOG_LENGTH and "version" in content.lower():
                        score = 2.0
                    else:
                        score = 1.0
            except (IOError, OSError, PermissionError) as e:
                logger.warning(f"Error reading changelog: {e}")
                score = 0.5  # Минимальная оценка за наличие файла / Minimum score for file presence
        
        return min(score, 2.0)
    
    # ========== БЛОК 4 / BLOCK 4: ARCHITECTURE & ENGINEERING (10 баллов / points) ==========
    
    def evaluate_docstrings(self) -> float:
        """
        Оценка: Docstring Coverage (макс 5 баллов)
        Evaluation: Docstring Coverage (max 5 points)
        """
        score = 0.0
        
        try:
            total_functions = 0
            documented_functions = 0
            
            for py_file in self.repo_path.glob("src/**/*.py"):
                content = py_file.read_text(errors='ignore')
                
                # Считаем функции (def )
                # Count functions (def )
                total_functions += len(re.findall(r'def \w+', content))
                
                # Считаем docstrings - улучшенный паттерн
                # Count docstrings - improved pattern
                # Ищем def с последующим docstring на следующей строке
                # Look for def followed by docstring on next line
                docstring_pattern = r'def \w+[^:]*:\s*\n\s*(?:"""|\'\'\').*?(?:"""|\'\'\')'
                documented_functions += len(re.findall(docstring_pattern, content, re.DOTALL))
            
            if total_functions > 0:
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
                    score = 0.5
        except (IOError, OSError, PermissionError) as e:
            logger.warning(f"Error evaluating docstrings: {e}")
        
        return min(score, 5.0)
    
    def evaluate_logging(self) -> float:
        """
        Оценка: Error Handling & Logging (макс 3 балла)
        Evaluation: Error Handling & Logging (max 3 points)
        """
        score = 0.0
        
        try:
            total_files = 0
            logging_files = 0
            
            for py_file in self.repo_path.glob("src/**/*.py"):
                content = py_file.read_text(errors='ignore')
                total_files += 1
                
                if 'import logging' in content or 'from logging' in content or \
                   'logger.' in content or 'logging.' in content:
                    logging_files += 1
            
            if total_files > 0:
                logging_percent = (logging_files / total_files) * 100
                
                if logging_percent >= 80:
                    score = 3.0
                elif logging_percent >= 50:
                    score = 2.0
                else:
                    score = 1.0
        except (IOError, OSError, PermissionError) as e:
            logger.warning(f"Error evaluating logging: {e}")
        
        return min(score, 3.0)
    
    def evaluate_project_structure(self) -> float:
        """
        Оценка: Project Structure (макс 2 балла)
        Evaluation: Project Structure (max 2 points)
        """
        score = 0.0
        
        has_src = self.check_file_exists("src/")
        has_tests = self.check_file_exists("tests/", "test_*.py")
        has_docs = self.check_file_exists("docs/", "*.md")
        
        if has_src and has_tests and has_docs:
            score = 2.0
        elif has_src and has_tests:
            score = 1.5
        elif has_src or has_tests:
            score = 1.0
        
        return min(score, 2.0)
    
    # ========== БЛОК 5 / BLOCK 5: DOCUMENTATION & UX (10 баллов / points) ==========
    
    def evaluate_readme_quality(self) -> float:
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
                    content = readme_path.read_text(errors='ignore').lower()
                    
                    # Считаем наличие ключевых секций
                    # Count key sections presence
                    sections = 0
                    if "install" in content or "setup" in content:
                        sections += 1
                    if "usage" in content or "example" in content or "quickstart" in content:
                        sections += 1
                    if "screenshot" in content or "demo" in content:
                        sections += 1
                    if "troubleshoot" in content or "faq" in content or "issue" in content:
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
            except (IOError, OSError, PermissionError) as e:
                logger.warning(f"Error reading README: {e}")
        
        return min(score, 5.0)
    
    def evaluate_api_documentation(self) -> float:
        """
        Оценка: API Documentation (макс 3 балла)
        Evaluation: API Documentation (max 3 points)
        """
        score = 0.0
        
        has_fastapi = self.check_content_contains("*.py", ["fastapi"])
        has_postman = self.check_file_exists("*.postman_collection.json")
        has_openapi = self.check_file_exists("openapi.json", "openapi.yaml")
        
        if (has_fastapi or has_postman) and has_openapi:
            score = 3.0
        elif has_fastapi or has_postman:
            score = 2.0
        elif has_openapi:
            score = 1.5
        elif self.check_content_contains("*.py", ["Args:", "Returns:", "Raises:"]):
            score = 1.0
        
        return min(score, 3.0)
    
    def evaluate_getting_started(self) -> float:
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
        elif self.check_content_contains("README*.md", ["docker-compose up", "python main.py"]):
            score = 1.0
        
        return min(score, 2.0)
    
    # ========== БЛОК 6 / BLOCK 6: DEPLOYMENT & DEVOPS (5 баллов / points) ==========
    
    def evaluate_docker(self) -> float:
        """
        Оценка: Docker & Containerization (макс 3 балла)
        Evaluation: Docker & Containerization (max 3 points)
        """
        score = 0.0
        
        has_dockerfile = self.check_file_exists("Dockerfile")
        has_compose = self.check_file_exists("docker-compose.yml", "docker-compose.yaml")
        has_dockerignore = self.check_file_exists(".dockerignore")
        
        if has_dockerfile and has_compose and has_dockerignore:
            # Проверяем качество Dockerfile
            # Check Dockerfile quality
            try:
                dockerfile = Path(self.repo_path / "Dockerfile")
                content = dockerfile.read_text(errors='ignore')
                
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
        
        return min(score, 3.0)
    
    def evaluate_cicd(self) -> float:
        """
        Оценка: CI/CD Pipeline (макс 2 балла)
        Evaluation: CI/CD Pipeline (max 2 points)
        """
        score = 0.0
        
        if self.check_file_exists(".github/workflows/*.yml", ".github/workflows/*.yaml"):
            try:
                workflow_files = list(self.repo_path.glob(".github/workflows/*.yml")) + \
                               list(self.repo_path.glob(".github/workflows/*.yaml"))
                
                if workflow_files:
                    content = workflow_files[0].read_text(errors='ignore').lower()
                    
                    # Проверяем полноту CI/CD
                    # Check CI/CD completeness
                    checks = 0
                    if "lint" in content or "ruff" in content or "black" in content:
                        checks += 1
                    if "test" in content or "pytest" in content:
                        checks += 1
                    if "coverage" in content:
                        checks += 1
                    if "deploy" in content or "push" in content:
                        checks += 1
                    
                    if checks >= 3:
                        score = 2.0
                    elif checks >= 2:
                        score = 1.0
                    else:
                        score = 0.5
            except (IOError, OSError, PermissionError) as e:
                logger.warning(f"Error reading workflow files: {e}")
                score = 0.5
        
        return min(score, 2.0)
    
    # ========== ГЛАВНАЯ ФУНКЦИЯ ОЦЕНКИ / MAIN EVALUATION FUNCTION ==========
    
    def evaluate_all(self) -> Dict:
        """
        Полная оценка репозитория по 18 критериям
        Full repository evaluation by 18 criteria
        """
        
        # БЛОК 1 / BLOCK 1: CODE QUALITY & STABILITY (15 баллов / points)
        test_coverage = self.evaluate_test_coverage()
        complexity = self.evaluate_code_complexity()
        type_hints = self.evaluate_type_hints()
        
        # БЛОК 2 / BLOCK 2: SECURITY & DEPENDENCIES (10 баллов / points)
        vulnerabilities = self.evaluate_vulnerabilities()
        dep_health = self.evaluate_dependency_health()
        security_scanning = self.evaluate_security_scanning()
        
        # БЛОК 3 / BLOCK 3: MAINTENANCE & MATURITY (10 баллов / points)
        activity = self.evaluate_project_activity()
        version = self.evaluate_version_stability()
        changelog = self.evaluate_changelog()
        
        # БЛОК 4 / BLOCK 4: ARCHITECTURE & ENGINEERING (10 баллов / points)
        docstrings = self.evaluate_docstrings()
        logging_score = self.evaluate_logging()
        structure = self.evaluate_project_structure()
        
        # БЛОК 5 / BLOCK 5: DOCUMENTATION & UX (10 баллов / points)
        readme = self.evaluate_readme_quality()
        api_docs = self.evaluate_api_documentation()
        getting_started = self.evaluate_getting_started()
        
        # БЛОК 6 / BLOCK 6: DEPLOYMENT & DEVOPS (5 баллов / points)
        docker = self.evaluate_docker()
        cicd = self.evaluate_cicd()
        
        # Итоговый балл / Total score
        total_score = (
            test_coverage + complexity + type_hints +  # 15
            vulnerabilities + dep_health + security_scanning +  # 10
            activity + version + changelog +  # 10
            docstrings + logging_score + structure +  # 10
            readme + api_docs + getting_started +  # 10
            docker + cicd  # 5
        )
        
        results = {
            "repo": self.repo_name,
            "path": str(self.repo_path),
            "total_score": round(total_score, 2),
            "max_score": 50,
            
            # БЛОК 1 / BLOCK 1
            "block1_code_quality": round(test_coverage + complexity + type_hints, 2),
            "test_coverage": round(test_coverage, 2),
            "code_complexity": round(complexity, 2),
            "type_hints": round(type_hints, 2),
            
            # БЛОК 2 / BLOCK 2
            "block2_security": round(vulnerabilities + dep_health + security_scanning, 2),
            "vulnerabilities": round(vulnerabilities, 2),
            "dep_health": round(dep_health, 2),
            "security_scanning": round(security_scanning, 2),
            
            # БЛОК 3 / BLOCK 3
            "block3_maintenance": round(activity + version + changelog, 2),
            "project_activity": round(activity, 2),
            "version_stability": round(version, 2),
            "changelog": round(changelog, 2),
            
            # БЛОК 4 / BLOCK 4
            "block4_architecture": round(docstrings + logging_score + structure, 2),
            "docstrings": round(docstrings, 2),
            "logging": round(logging_score, 2),
            "structure": round(structure, 2),
            
            # БЛОК 5 / BLOCK 5
            "block5_documentation": round(readme + api_docs + getting_started, 2),
            "readme": round(readme, 2),
            "api_docs": round(api_docs, 2),
            "getting_started": round(getting_started, 2),
            
            # БЛОК 6 / BLOCK 6
            "block6_devops": round(docker + cicd, 2),
            "docker": round(docker, 2),
            "cicd": round(cicd, 2),
            
            "category": self._categorize(total_score)
        }
        
        return results
    
    @staticmethod
    def _categorize(score: float) -> str:
        """
        Категоризация по баллам
        Categorization by score
        """
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


def validate_path(path_str: str) -> Optional[Path]:
    """
    Валидация и нормализация пути
    Path validation and normalization
    """
    if not path_str or not path_str.strip():
        return Path(".")
    
    path = Path(path_str.strip())
    
    # Проверяем на недопустимые символы (Windows)
    # Check for invalid characters (Windows)
    invalid_chars = '<>"|?*'
    if any(char in str(path) for char in invalid_chars):
        logger.error(f"Invalid characters in path: {path}")
        return None
    
    return path


class GitHubRepoFetcher:
    """
    Класс для получения и клонирования репозиториев с GitHub
    Class for fetching and cloning repositories from GitHub
    """
    
    GITHUB_API_URL = "https://api.github.com"
    
    def __init__(self, username: str, output_dir: Optional[Path] = None, token: Optional[str] = None):
        """
        Инициализация / Initialization
        
        Args:
            username: GitHub username / Имя пользователя GitHub
            output_dir: Directory to clone repos / Директория для клонирования
            token: GitHub API token (optional) / Токен GitHub API (опционально)
        """
        self.username = username
        self.output_dir = output_dir or Path(tempfile.mkdtemp(prefix=f"github_{username}_"))
        self.token = token
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            self.headers["Authorization"] = f"token {token}"
    
    def get_user_repos(self) -> List[Dict]:
        """
        Получает список репозиториев пользователя через GitHub API
        Gets list of user repositories via GitHub API
        
        Returns:
            List of repository info dicts / Список словарей с информацией о репозиториях
        """
        repos = []
        page = 1
        per_page = 100
        
        print(f"\n🔍 Получение списка репозиториев для {self.username}...", flush=True)
        print(f"   Fetching repository list for {self.username}...", flush=True)
        
        while True:
            url = f"{self.GITHUB_API_URL}/users/{self.username}/repos?page={page}&per_page={per_page}&type=owner"
            
            try:
                request = Request(url, headers=self.headers)
                with urlopen(request, timeout=30) as response:
                    data = json.loads(response.read().decode('utf-8'))
                    
                    if not data:
                        break
                    
                    repos.extend(data)
                    
                    if len(data) < per_page:
                        break
                    
                    page += 1
                    
            except HTTPError as e:
                if e.code == 404:
                    logger.error(f"User '{self.username}' not found on GitHub")
                    print(f"❌ Пользователь '{self.username}' не найден на GitHub", flush=True)
                    print(f"   User '{self.username}' not found on GitHub", flush=True)
                elif e.code == 403:
                    logger.error("GitHub API rate limit exceeded. Use --token option.")
                    print("❌ Превышен лимит запросов GitHub API. Используйте --token", flush=True)
                    print("   GitHub API rate limit exceeded. Use --token option.", flush=True)
                else:
                    logger.error(f"HTTP Error: {e.code} - {e.reason}")
                    print(f"❌ HTTP ошибка {e.code}: {e.reason}", flush=True)
                    print(f"   HTTP error {e.code}: {e.reason}", flush=True)
                return []
            except URLError as e:
                logger.error(f"Network error: {e.reason}")
                print(f"❌ Ошибка сети: {e.reason}", flush=True)
                print(f"   Network error: {e.reason}", flush=True)
                return []
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                print(f"❌ Ошибка при разборе ответа GitHub API: {e}", flush=True)
                print(f"   Error parsing GitHub API response: {e}", flush=True)
                return []
        
        print(f"✅ Найдено {len(repos)} репозиториев / Found {len(repos)} repositories", flush=True)
        return repos
    
    def filter_python_repos(self, repos: List[Dict]) -> List[Dict]:
        """
        Фильтрует только Python репозитории
        Filters only Python repositories
        """
        python_repos = []
        for repo in repos:
            language = repo.get('language')
            # Проверяем явно на None и пустую строку
            if language is None or language == '':
                # Включим для проверки при клонировании / Include for check on clone
                python_repos.append(repo)
            elif isinstance(language, str) and language.lower() == 'python':
                python_repos.append(repo)
        
        print(f"🐍 Python репозиториев: {len(python_repos)} / Python repositories: {len(python_repos)}", flush=True)
        return python_repos
    
    def clone_repo(self, repo: Dict) -> Optional[Path]:
        """
        Клонирует репозиторий
        Clones repository
        
        Args:
            repo: Repository info dict / Словарь с информацией о репозитории
            
        Returns:
            Path to cloned repo or None / Путь к клонированному репозиторию или None
        """
        repo_name = repo['name']
        clone_url = repo['clone_url']
        repo_path = self.output_dir / repo_name
        
        if repo_path.exists():
            print(f"  ⏭️  {repo_name} - уже существует / already exists")
            return repo_path
        
        try:
            result = subprocess.run(
                ['git', 'clone', '--depth', '1', clone_url, str(repo_path)],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                print(f"  ✅ {repo_name} - клонирован / cloned")
                return repo_path
            else:
                logger.warning(f"Failed to clone {repo_name}: {result.stderr}")
                print(f"  ❌ {repo_name} - ошибка клонирования / clone error")
                return None
                
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout cloning {repo_name}")
            print(f"  ⏱️  {repo_name} - таймаут / timeout")
            return None
        except FileNotFoundError:
            logger.error("Git is not installed or not in PATH")
            print("❌ Git не установлен или не в PATH / Git is not installed or not in PATH")
            return None
    
    def clone_all_repos(self, repos: List[Dict], max_repos: int = 100) -> List[Path]:
        """
        Клонирует все репозитории
        Clones all repositories
        
        Args:
            repos: List of repository info dicts / Список словарей с информацией
            max_repos: Maximum repos to clone (0 = all) / Максимум репозиториев для клонирования (0 = все)
            
        Returns:
            List of paths to cloned repos / Список путей к клонированным репозиториям
        """
        print(f"\n📥 Клонирование репозиториев в {self.output_dir}", flush=True)
        print(f"   Cloning repositories to {self.output_dir}", flush=True)
        print("-" * 60, flush=True)
        
        cloned_paths = []
        # Если max_repos = 0, клонируем все / If max_repos = 0, clone all
        if max_repos == 0:
            repos_to_clone = repos
            print(f"   Клонирование всех {len(repos)} репозиториев / Cloning all {len(repos)} repositories", flush=True)
        else:
            repos_to_clone = repos[:max_repos]
            print(f"   Клонирование {len(repos_to_clone)} из {len(repos)} репозиториев / Cloning {len(repos_to_clone)} of {len(repos)} repositories", flush=True)
        
        for i, repo in enumerate(repos_to_clone, 1):
            print(f"[{i}/{len(repos_to_clone)}] ", end="")
            path = self.clone_repo(repo)
            if path:
                # Проверяем что это действительно Python проект
                # Verify it's actually a Python project
                has_python = any(path.glob("*.py")) or \
                            any(path.glob("**/*.py")) or \
                            (path / "setup.py").exists() or \
                            (path / "pyproject.toml").exists()
                
                if has_python:
                    cloned_paths.append(path)
                else:
                    print(f"      ⚠️  {repo['name']} - не Python проект / not a Python project")
        
        print("-" * 60)
        print(f"✅ Успешно клонировано Python проектов: {len(cloned_paths)}")
        print(f"   Successfully cloned Python projects: {len(cloned_paths)}")
        
        return cloned_paths
    
    def cleanup(self):
        """
        Удаляет временную директорию с клонированными репозиториями
        Removes temporary directory with cloned repositories
        """
        if self.output_dir.exists() and str(self.output_dir).startswith(tempfile.gettempdir()):
            shutil.rmtree(self.output_dir, ignore_errors=True)
            print(f"🧹 Временные файлы удалены / Temporary files removed")


def evaluate_repos(repos_dir: Path, github_username: Optional[str] = None) -> List[Dict]:
    """
    Оценивает все репозитории в директории
    Evaluates all repositories in directory
    
    Args:
        repos_dir: Directory with repositories / Директория с репозиториями
        github_username: GitHub username (for output) / Имя пользователя GitHub (для вывода)
        
    Returns:
        List of evaluation results / Список результатов оценки
    """
    # Найти все Python репозитории
    # Find all Python repositories
    python_repos = []
    for item in repos_dir.iterdir():
        if item.is_dir() and (item / ".git").exists():
            # Проверяем наличие Python файлов или директорий
            # Check for Python files or directories
            has_py_files = any(item.glob("*.py")) or \
                          any(item.glob("**/*.py")) or \
                          (item / "src").is_dir() or \
                          (item / "app").is_dir() or \
                          (item / "main.py").exists()
            if has_py_files:
                python_repos.append(item)
    
    if not python_repos:
        print("❌ Python репозитории не найдены / No Python repositories found")
        return []
    
    print(f"\n📊 Оценка {len(python_repos)} Python репозиториев...")
    print(f"   Evaluating {len(python_repos)} Python repositories...")
    print("-" * 80)
    
    # Оценить каждый / Evaluate each
    results = []
    for i, repo_path in enumerate(sorted(python_repos), 1):
        evaluator = EnhancedRepositoryEvaluator(repo_path)
        result = evaluator.evaluate_all()
        
        # Добавляем информацию о GitHub если есть
        # Add GitHub info if available
        if github_username:
            result['github_username'] = github_username
            result['github_url'] = f"https://github.com/{github_username}/{result['repo']}"
        
        results.append(result)
        
        score = result['total_score']
        category = result['category']
        print(f"{i:2}. {result['repo']:40} {score:6.2f}/50 | {category}")
    
    return results


def save_text_report(results: List[Dict], github_username: Optional[str] = None) -> str:
    """
    Сохраняет полный текстовый отчет с отсортированным списком всех репозиториев
    Saves full text report with sorted list of all repositories
    """
    if not results:
        return ""
    
    # Сортировать по баллам / Sort by score
    sorted_results = sorted(results, key=lambda x: x['total_score'], reverse=True)
    
    report_file = f"portfolio_report_{github_username or 'local'}.txt"
    
    with open(report_file, "w", encoding="utf-8") as f:
        # Заголовок / Header
        f.write("=" * 120 + "\n")
        if github_username:
            f.write(f"ПОЛНЫЙ ОТЧЕТ ОЦЕНКИ ПОРТФОЛИО @{github_username}\n")
            f.write(f"FULL PORTFOLIO EVALUATION REPORT @{github_username}\n")
        else:
            f.write("ПОЛНЫЙ ОТЧЕТ ОЦЕНКИ ПОРТФОЛИО / FULL PORTFOLIO EVALUATION REPORT\n")
        f.write("(по Product Readiness Score v2.2 / by Product Readiness Score v2.2)\n")
        f.write("=" * 120 + "\n\n")
        
        # Общая статистика / General statistics
        f.write("ОБЩАЯ СТАТИСТИКА / GENERAL STATISTICS\n")
        f.write("-" * 120 + "\n")
        f.write(f"Всего репозиториев / Total repositories: {len(sorted_results)}\n")
        
        categories = {
            "⭐⭐⭐⭐⭐ Идеальный / Perfect": 0,
            "⭐⭐⭐⭐ Отличный / Excellent": 0,
            "⭐⭐⭐ Хороший / Good": 0,
            "⭐⭐ Средний / Average": 0,
            "⭐ Парковка / Parking": 0
        }
        
        for result in sorted_results:
            categories[result['category']] += 1
        
        f.write("\nРаспределение по категориям / Distribution by categories:\n")
        for cat, count in categories.items():
            percentage = count * 100 // len(sorted_results) if sorted_results else 0
            f.write(f"  {cat:45} : {count:3} ({percentage:3}%)\n")
        
        avg_score = sum(r['total_score'] for r in sorted_results) / len(sorted_results)
        f.write(f"\nСредний балл / Average score: {avg_score:.2f}/50\n")
        f.write(f"Максимальный балл / Maximum score: {max(r['total_score'] for r in sorted_results):.2f}/50\n")
        f.write(f"Минимальный балл / Minimum score: {min(r['total_score'] for r in sorted_results):.2f}/50\n")
        
        # Полный список репозиториев / Full repository list
        f.write("\n" + "=" * 120 + "\n")
        f.write("ПОЛНЫЙ СПИСОК РЕПОЗИТОРИЕВ (отсортирован по баллам)\n")
        f.write("FULL REPOSITORY LIST (sorted by score)\n")
        f.write("=" * 120 + "\n\n")
        
        for i, result in enumerate(sorted_results, 1):
            repo_name = result['repo']
            if github_username:
                repo_url = f"https://github.com/{github_username}/{repo_name}"
            else:
                repo_url = result.get('github_url', repo_name)
            
            f.write(f"{'=' * 120}\n")
            f.write(f"#{i}. {repo_name}\n")
            f.write(f"{'-' * 120}\n")
            f.write(f"URL: {repo_url}\n")
            f.write(f"Общий балл / Total Score: {result['total_score']:.2f}/50\n")
            f.write(f"Категория / Category: {result['category']}\n")
            f.write(f"\nДетальная оценка / Detailed Evaluation:\n")
            f.write(f"  БЛОК 1 - Качество кода / CODE QUALITY: {result['block1_code_quality']:.2f}/15\n")
            f.write(f"    • Покрытие тестами / Test Coverage: {result['test_coverage']:.2f}/5\n")
            f.write(f"    • Сложность кода / Code Complexity: {result['code_complexity']:.2f}/5\n")
            f.write(f"    • Type Hints / Type Hints: {result['type_hints']:.2f}/5\n")
            f.write(f"  БЛОК 2 - Безопасность / SECURITY: {result['block2_security']:.2f}/10\n")
            f.write(f"    • Уязвимости / Vulnerabilities: {result['vulnerabilities']:.2f}/5\n")
            f.write(f"    • Здоровье зависимостей / Dependency Health: {result['dep_health']:.2f}/3\n")
            f.write(f"    • Сканирование безопасности / Security Scanning: {result['security_scanning']:.2f}/2\n")
            f.write(f"  БЛОК 3 - Поддержка / MAINTENANCE: {result['block3_maintenance']:.2f}/10\n")
            f.write(f"    • Активность проекта / Project Activity: {result['project_activity']:.2f}/5\n")
            f.write(f"    • Стабильность версии / Version Stability: {result['version_stability']:.2f}/3\n")
            f.write(f"    • CHANGELOG / CHANGELOG: {result['changelog']:.2f}/2\n")
            f.write(f"  БЛОК 4 - Архитектура / ARCHITECTURE: {result['block4_architecture']:.2f}/10\n")
            f.write(f"    • Docstrings / Docstrings: {result['docstrings']:.2f}/5\n")
            f.write(f"    • Логирование / Logging: {result['logging']:.2f}/3\n")
            f.write(f"    • Структура проекта / Project Structure: {result['structure']:.2f}/2\n")
            f.write(f"  БЛОК 5 - Документация / DOCUMENTATION: {result['block5_documentation']:.2f}/10\n")
            f.write(f"    • README / README: {result['readme']:.2f}/5\n")
            f.write(f"    • API документация / API Documentation: {result['api_docs']:.2f}/3\n")
            f.write(f"    • Простота запуска / Getting Started: {result['getting_started']:.2f}/2\n")
            f.write(f"  БЛОК 6 - DevOps / DEVOPS: {result['block6_devops']:.2f}/5\n")
            f.write(f"    • Docker / Docker: {result['docker']:.2f}/3\n")
            f.write(f"    • CI/CD / CI/CD: {result['cicd']:.2f}/2\n")
            f.write("\n")
        
        # Рекомендации / Recommendations
        f.write("\n" + "=" * 120 + "\n")
        f.write("РЕКОМЕНДАЦИИ / RECOMMENDATIONS\n")
        f.write("=" * 120 + "\n\n")
        
        excellent_repos = [r for r in sorted_results if r['total_score'] >= 30]
        good_repos = [r for r in sorted_results if 20 <= r['total_score'] < 30]
        
        if excellent_repos:
            f.write(f"🌟 Отличные проекты для портфолио ({len(excellent_repos)} проектов):\n")
            f.write(f"   Excellent projects for portfolio ({len(excellent_repos)} projects):\n")
            for r in excellent_repos:
                url = r.get('github_url', f"{github_username}/{r['repo']}" if github_username else r['repo'])
                f.write(f"   • {url} - {r['total_score']:.1f}/50\n")
            f.write("\n")
        
        if good_repos:
            f.write(f"⭐ Хорошие проекты ({len(good_repos)} проектов):\n")
            f.write(f"   Good projects ({len(good_repos)} projects):\n")
            for r in good_repos[:10]:  # Показываем топ-10 хороших
                url = r.get('github_url', f"{github_username}/{r['repo']}" if github_username else r['repo'])
                f.write(f"   • {url} - {r['total_score']:.1f}/50\n")
        
        f.write("\n" + "=" * 120 + "\n")
        f.write(f"Отчет создан / Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 120 + "\n")
    
    return report_file


def print_results(results: List[Dict], github_username: Optional[str] = None):
    """
    Выводит результаты оценки
    Prints evaluation results
    """
    if not results:
        return
    
    # Сортировать по баллам / Sort by score
    results.sort(key=lambda x: x['total_score'], reverse=True)
    
    # Вывести топ-20 / Output top-20
    print("\n" + "=" * 120)
    if github_username:
        print(f"ТОП-20 ПРОЕКТОВ ДЛЯ ПОРТФОЛИО @{github_username}")
        print(f"TOP-20 PROJECTS FOR PORTFOLIO @{github_username}")
    else:
        print("ТОП-20 ПРОЕКТОВ ДЛЯ ПОРТФОЛИО / TOP-20 PROJECTS FOR PORTFOLIO")
    print("(по Product Readiness Score v2.2 / by Product Readiness Score v2.2)")
    print("=" * 120 + "\n")
    
    for i, result in enumerate(results[:20], 1):
        repo_info = result['repo']
        if github_username:
            repo_info = f"github.com/{github_username}/{result['repo']}"
        print(f"{i:2}. {repo_info:50} {result['total_score']:6.2f}/50 | {result['category']}")
    
    # Сохранить полные результаты в JSON / Save full results to JSON
    json_file = f"portfolio_evaluation_{github_username or 'local'}.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Полные результаты (JSON) сохранены в {json_file}")
    print(f"   Full results (JSON) saved to {json_file}")
    
    # Сохранить текстовый отчет / Save text report
    report_file = save_text_report(results, github_username)
    if report_file:
        print(f"✅ Полный текстовый отчет сохранен в {report_file}")
        print(f"   Full text report saved to {report_file}")
    
    # Вывести статистику / Output statistics
    print("\n" + "=" * 120)
    print("СТАТИСТИКА / STATISTICS")
    print("=" * 120)
    
    categories = {
        "⭐⭐⭐⭐⭐ Идеальный / Perfect": 0,
        "⭐⭐⭐⭐ Отличный / Excellent": 0,
        "⭐⭐⭐ Хороший / Good": 0,
        "⭐⭐ Средний / Average": 0,
        "⭐ Парковка / Parking": 0
    }
    
    for result in results:
        categories[result['category']] += 1
    
    for cat, count in categories.items():
        percentage = count * 100 // len(results) if results else 0
        print(f"  {cat:40} : {count:3} проектов/projects ({percentage}%)")
    
    avg_score = sum(r['total_score'] for r in results) / len(results)
    print(f"\n  Средний балл / Average score: {avg_score:.2f}/50")
    
    # Рекомендации / Recommendations
    print("\n" + "=" * 120)
    print("РЕКОМЕНДАЦИИ / RECOMMENDATIONS")
    print("=" * 120)
    
    excellent_repos = [r for r in results if r['total_score'] >= 30]
    if excellent_repos:
        print(f"\n🌟 Рекомендуемые для портфолио ({len(excellent_repos)} проектов):")
        print(f"   Recommended for portfolio ({len(excellent_repos)} projects):")
        for r in excellent_repos[:5]:
            url = r.get('github_url', r['repo'])
            print(f"   • {url} ({r['total_score']:.1f}/50)")


def parse_arguments() -> argparse.Namespace:
    """
    Парсинг аргументов командной строки
    Parse command line arguments
    """
    parser = argparse.ArgumentParser(
        description="Enhanced Portfolio Evaluation Script v2.2\n"
                    "Расширенный скрипт оценки портфолио v2.2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования / Usage examples:
  %(prog)s                           # Интерактивный режим / Interactive mode
  %(prog)s --github username         # Оценка GitHub аккаунта / Evaluate GitHub account
  %(prog)s -g username -o ./repos    # С указанием папки / With output directory
  %(prog)s --path ./my_repos         # Локальная папка / Local folder
        """
    )
    
    parser.add_argument(
        '-g', '--github',
        type=str,
        metavar='USERNAME',
        help='GitHub username для оценки / GitHub username to evaluate'
    )
    
    parser.add_argument(
        '-o', '--output',
        type=str,
        metavar='DIR',
        help='Директория для клонирования репозиториев / Directory to clone repos'
    )
    
    parser.add_argument(
        '-p', '--path',
        type=str,
        metavar='DIR',
        help='Путь к локальной папке с репозиториями / Path to local repos folder'
    )
    
    parser.add_argument(
        '-t', '--token',
        type=str,
        metavar='TOKEN',
        help='GitHub API token (для увеличения лимита запросов) / GitHub API token'
    )
    
    parser.add_argument(
        '-m', '--max-repos',
        type=int,
        default=100,
        metavar='N',
        help='Максимум репозиториев для клонирования (по умолчанию 100, 0 = все) / Max repos to clone (default 100, 0 = all)'
    )
    
    parser.add_argument(
        '--keep-repos',
        action='store_true',
        help='Не удалять клонированные репозитории / Keep cloned repositories'
    )
    
    return parser.parse_args()


def main():
    """
    Основной скрипт
    Main script
    """
    # Принудительная очистка буфера для PowerShell
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        # Для старых версий Python
        pass
    
    # Явный вывод в самом начале для диагностики
    sys.stdout.write("=" * 120 + "\n")
    sys.stdout.flush()
    sys.stdout.write("РАСШИРЕННЫЙ СКРИПТ ОЦЕНКИ ПОРТФОЛИО v2.2 / ENHANCED PORTFOLIO EVALUATION SCRIPT v2.2\n")
    sys.stdout.flush()
    sys.stdout.write("18 Критериев / 50 Баллов - Production Readiness Score Enhanced\n")
    sys.stdout.flush()
    sys.stdout.write("18 Criteria / 50 Points - Production Readiness Score Enhanced\n")
    sys.stdout.flush()
    sys.stdout.write("=" * 120 + "\n\n")
    sys.stdout.flush()
    
    try:
        args = parse_arguments()
    
        # Режим GitHub / GitHub mode
        if args.github:
            output_dir = Path(args.output) if args.output else None
            
            fetcher = GitHubRepoFetcher(
                username=args.github,
                output_dir=output_dir,
                token=args.token
            )
            
            try:
                # Получаем список репозиториев / Get repository list
                repos = fetcher.get_user_repos()
                if not repos:
                    print(f"\n⚠️  Не найдено репозиториев для пользователя '{args.github}'", flush=True)
                    print(f"   No repositories found for user '{args.github}'", flush=True)
                    print(f"   Возможные причины / Possible reasons:", flush=True)
                    print(f"   - Пользователь не существует / User doesn't exist", flush=True)
                    print(f"   - Нет публичных репозиториев / No public repositories", flush=True)
                    print(f"   - Ошибка при обращении к GitHub API / Error accessing GitHub API", flush=True)
                    return
                
                # Фильтруем Python репозитории / Filter Python repos
                python_repos = fetcher.filter_python_repos(repos)
                
                # Клонируем / Clone
                cloned_paths = fetcher.clone_all_repos(python_repos, max_repos=args.max_repos)
                
                if not cloned_paths:
                    print("❌ Нет репозиториев для оценки / No repositories to evaluate", flush=True)
                    return
                
                # Оцениваем / Evaluate
                results = evaluate_repos(fetcher.output_dir, github_username=args.github)
                
                # Выводим результаты / Print results
                print_results(results, github_username=args.github)
                
            finally:
                # Очистка если не указано --keep-repos / Cleanup if not --keep-repos
                if not args.keep_repos and not args.output:
                    fetcher.cleanup()
                else:
                    print(f"\n📁 Репозитории сохранены в: {fetcher.output_dir}", flush=True)
                    print(f"   Repositories saved to: {fetcher.output_dir}", flush=True)
            
            return
        
        # Режим локальной папки / Local folder mode
        if args.path:
            repos_dir = validate_path(args.path)
        else:
            # Интерактивный режим / Interactive mode
            print("\nВыберите режим / Choose mode:", flush=True)
            print("  1. Локальная папка / Local folder", flush=True)
            print("  2. GitHub аккаунт / GitHub account", flush=True)
            
            choice = input("\nВаш выбор / Your choice (1/2): ").strip()
            
            if choice == "2":
                github_username = input("Введите GitHub username / Enter GitHub username: ").strip()
                if github_username:
                    # Рекурсивный вызов с аргументами / Recursive call with args
                    sys.argv = [sys.argv[0], '--github', github_username]
                    main()
                    return
            
            path_input = input("\nВведите путь к папке с репозиториями (или Enter для текущей): \n"
                               "Enter path to repositories folder (or Enter for current): ").strip()
            repos_dir = validate_path(path_input)
        
        if repos_dir is None:
            print("❌ Ошибка: некорректный путь! / Error: invalid path!", flush=True)
            return
        
        if not repos_dir.exists():
            print(f"❌ Ошибка: папка {repos_dir} не найдена! / Error: folder {repos_dir} not found!", flush=True)
            return
        
        # Оцениваем / Evaluate
        results = evaluate_repos(repos_dir)
        
        # Выводим результаты / Print results
        print_results(results)
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Прервано пользователем / Interrupted by user", flush=True)
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА / CRITICAL ERROR: {e}", flush=True, file=sys.stderr)
        print(f"   {type(e).__name__}: {str(e)}", flush=True, file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
