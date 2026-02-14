import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from portfolio_fit.scoring import detect_stack_profile

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class GitHubRepoFetcher:
    """
    Класс для получения и клонирования репозиториев с GitHub
    Class for fetching and cloning repositories from GitHub
    """

    GITHUB_API_URL = "https://api.github.com"
    SUPPORTED_PRIMARY_LANGUAGES = {"python", "javascript", "typescript", "html", "css"}

    def __init__(
        self,
        username: str,
        output_dir: Optional[Path] = None,
        token: Optional[str] = None,
    ):
        """
        Инициализация / Initialization

        Args:
            username: GitHub username / Имя пользователя GitHub
            output_dir: Directory to clone repos / Директория для клонирования
            token: GitHub API token (optional) / Токен GitHub API (опционально)
        """
        self.username = username
        self.output_dir = output_dir or Path(
            tempfile.mkdtemp(prefix=f"github_{username}_")
        )
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
                    data = json.loads(response.read().decode("utf-8"))

                    if not data:
                        break

                    repos.extend(data)

                    if len(data) < per_page:
                        break

                    page += 1

            except HTTPError as e:
                if e.code == 404:
                    logger.error(f"User '{self.username}' not found on GitHub")
                    print(
                        f"❌ Пользователь '{self.username}' не найден на GitHub",
                        flush=True,
                    )
                    print(f"   User '{self.username}' not found on GitHub", flush=True)
                elif e.code == 403:
                    logger.error("GitHub API rate limit exceeded. Use --token option.")
                    print(
                        "❌ Превышен лимит запросов GitHub API. Используйте --token",
                        flush=True,
                    )
                    print(
                        "   GitHub API rate limit exceeded. Use --token option.",
                        flush=True,
                    )
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

        print(
            f"✅ Найдено {len(repos)} репозиториев / Found {len(repos)} repositories",
            flush=True,
        )
        return repos

    def filter_python_repos(self, repos: List[Dict]) -> List[Dict]:
        """
        Фильтрует только Python репозитории
        Filters only Python repositories
        """
        python_repos = []
        for repo in repos:
            language = repo.get("language")
            # Проверяем явно на None и пустую строку
            if language is None or language == "":
                # Включим для проверки при клонировании / Include for check on clone
                python_repos.append(repo)
            elif isinstance(language, str) and language.lower() == "python":
                python_repos.append(repo)

        print(
            f"🐍 Python репозиториев: {len(python_repos)} / Python repositories: {len(python_repos)}",
            flush=True,
        )
        return python_repos

    def filter_supported_repos(self, repos: List[Dict]) -> List[Dict]:
        """
        Filters repositories by commonly supported primary languages.
        Empty/unknown language is included and validated after clone.
        """
        supported_repos: List[Dict] = []
        for repo in repos:
            language = repo.get("language")
            if language is None or language == "":
                supported_repos.append(repo)
                continue
            if (
                isinstance(language, str)
                and language.lower() in self.SUPPORTED_PRIMARY_LANGUAGES
            ):
                supported_repos.append(repo)

        print(
            "🧩 Поддерживаемых репозиториев: "
            f"{len(supported_repos)} / Supported repositories: {len(supported_repos)}",
            flush=True,
        )
        return supported_repos

    def _is_supported_repo_path(self, path: Path) -> bool:
        stack = detect_stack_profile(path)
        if stack != "mixed_unknown":
            return True
        for pattern in ("*.html", "*.css", "*.js", "*.ts", "*.py"):
            if any(path.glob(pattern)) or any(path.glob(f"**/{pattern}")):
                return True
        return False

    def clone_repo(self, repo: Dict) -> Optional[Path]:
        """
        Клонирует репозиторий
        Clones repository

        Args:
            repo: Repository info dict / Словарь с информацией о репозитории

        Returns:
            Path to cloned repo or None / Путь к клонированному репозиторию или None
        """
        repo_name = repo["name"]
        clone_url = repo["clone_url"]
        repo_path = self.output_dir / repo_name

        if repo_path.exists():
            print(f"  ⏭️  {repo_name} - уже существует / already exists")
            return repo_path

        try:
            result = subprocess.run(
                ["git", "clone", "--depth", "1", clone_url, str(repo_path)],
                capture_output=True,
                text=True,
                timeout=120,
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
            print(
                "❌ Git не установлен или не в PATH / Git is not installed or not in PATH"
            )
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
            print(
                f"   Клонирование всех {len(repos)} репозиториев / Cloning all {len(repos)} repositories",
                flush=True,
            )
        else:
            repos_to_clone = repos[:max_repos]
            print(
                f"   Клонирование {len(repos_to_clone)} из {len(repos)} репозиториев / Cloning {len(repos_to_clone)} of {len(repos)} repositories",
                flush=True,
            )

        for i, repo in enumerate(repos_to_clone, 1):
            print(f"[{i}/{len(repos_to_clone)}] ", end="")
            path = self.clone_repo(repo)
            if path:
                if self._is_supported_repo_path(path):
                    cloned_paths.append(path)
                else:
                    print(
                        f"      ⚠️  {repo['name']} - неподдерживаемый стек / unsupported stack"
                    )

        print("-" * 60)
        print(f"✅ Успешно клонировано поддерживаемых проектов: {len(cloned_paths)}")
        print(f"   Successfully cloned supported projects: {len(cloned_paths)}")

        return cloned_paths

    def cleanup(self):
        """
        Удаляет временную директорию с клонированными репозиториями
        Removes temporary directory with cloned repositories
        """
        if self.output_dir.exists() and str(self.output_dir).startswith(
            tempfile.gettempdir()
        ):
            shutil.rmtree(self.output_dir, ignore_errors=True)
            print("🧹 Временные файлы удалены / Temporary files removed")
