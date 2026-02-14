import logging
from pathlib import Path
from typing import Dict, List, Optional

from portfolio_fit.scoring import (
    STACK_PROFILE_AUTO,
    EnhancedRepositoryEvaluator,
    detect_stack_profile,
)

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


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


def is_python_repo_dir(repo_path: Path) -> bool:
    """
    Проверяет, является ли директория Python-репозиторием.
    Checks if a directory is a Python repository.
    """
    if not repo_path.is_dir() or not (repo_path / ".git").exists():
        return False

    has_py_files = (
        any(repo_path.glob("*.py"))
        or any(repo_path.glob("**/*.py"))
        or (repo_path / "src").is_dir()
        or (repo_path / "app").is_dir()
        or (repo_path / "main.py").exists()
    )
    return has_py_files


def is_supported_repo_dir(repo_path: Path) -> bool:
    """
    Checks if a directory looks like a supported repository (Python/JS/TS/HTML/CSS).
    """
    if not repo_path.is_dir() or not (repo_path / ".git").exists():
        return False

    marker_files = (
        "pyproject.toml",
        "requirements.txt",
        "setup.py",
        "manage.py",
        "package.json",
        "tsconfig.json",
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
    )
    if any((repo_path / marker).exists() for marker in marker_files):
        return True

    code_patterns = ("*.py", "*.js", "*.ts", "*.tsx", "*.jsx", "*.html", "*.css")
    for pattern in code_patterns:
        if any(repo_path.glob(pattern)) or any(repo_path.glob(f"**/{pattern}")):
            return True
    return False


def discover_supported_repos(repos_dir: Path, recursive: bool = False) -> List[Path]:
    """
    Finds repositories that can be evaluated by current stack detection rules.
    """
    discovered: List[Path] = []
    seen: set = set()

    if recursive:
        if is_supported_repo_dir(repos_dir):
            resolved_root = str(repos_dir.resolve())
            discovered.append(repos_dir)
            seen.add(resolved_root)

        for git_dir in repos_dir.rglob(".git"):
            repo_candidate = git_dir.parent
            try:
                resolved = str(repo_candidate.resolve())
            except OSError:
                continue

            if resolved in seen:
                continue

            if is_supported_repo_dir(repo_candidate):
                discovered.append(repo_candidate)
                seen.add(resolved)
    else:
        for item in repos_dir.iterdir():
            if item.is_dir() and is_supported_repo_dir(item):
                discovered.append(item)

    return sorted(discovered)


def discover_python_repos(repos_dir: Path, recursive: bool = False) -> List[Path]:
    """
    Находит Python-репозитории по заданным правилам.
    Finds Python repositories using defined discovery rules.
    """
    supported = discover_supported_repos(repos_dir, recursive=recursive)
    return [repo for repo in supported if is_python_repo_dir(repo)]


def evaluate_repos(
    repos_dir: Path,
    github_username: Optional[str] = None,
    recursive: bool = False,
    stack_profile: str = STACK_PROFILE_AUTO,
) -> List[Dict]:
    """
    Оценивает все репозитории в директории
    Evaluates all repositories in directory

    Args:
        repos_dir: Directory with repositories / Директория с репозиториями
        github_username: GitHub username (for output) / Имя пользователя GitHub (для вывода)
        recursive: Recursive repository discovery / Рекурсивный поиск репозиториев
        stack_profile: Stack profile override (`auto` by default)

    Returns:
        List of evaluation results / Список результатов оценки
    """
    # Найти все поддерживаемые репозитории
    # Find all supported repositories
    repos = discover_supported_repos(repos_dir, recursive=recursive)

    if not repos:
        print(
            "❌ Поддерживаемые репозитории не найдены / No supported repositories found"
        )
        return []

    discovery_mode = "recursive" if recursive else "top-level"
    profile_note = stack_profile if stack_profile != STACK_PROFILE_AUTO else "auto"
    print(
        f"\n📊 Оценка {len(repos)} репозиториев / Evaluating {len(repos)} repositories..."
    )
    print(f"   mode={discovery_mode}, stack_profile={profile_note}")
    print("-" * 80)

    # Оценить каждый / Evaluate each
    results = []
    for i, repo_path in enumerate(sorted(repos), 1):
        evaluator = EnhancedRepositoryEvaluator(repo_path, stack_profile=stack_profile)
        result = evaluator.evaluate_all()

        # Добавляем информацию о GitHub если есть
        # Add GitHub info if available
        if github_username:
            result["github_username"] = github_username
            result["github_url"] = (
                f"https://github.com/{github_username}/{result['repo']}"
            )

        results.append(result)

        score = result["total_score"]
        category = result["category"]
        coverage = result.get("data_coverage_percent", 0.0)
        resolved_stack = result.get("stack_profile", detect_stack_profile(repo_path))
        print(
            f"{i:2}. {result['repo']:40} {score:6.2f}/50 | {category} | data {coverage:5.1f}% | stack {resolved_stack}"
        )

    return results
