#!/usr/bin/env python3
"""
СКРИПТ ДЛЯ КЛОНИРОВАНИЯ PYTHON-РЕПОЗИТОРИЕВ С GITHUB

Использование:
  python clone_all_repos.py <username> [target_dir]

Пример:
  python clone_all_repos.py ergon73
"""

import os
import sys
from pathlib import Path
from typing import Optional

from portfolio_fit.github_fetcher import GitHubRepoFetcher


def get_dir_size(path: Path) -> Optional[int]:
    """
    Return directory size in bytes, or None on failure.
    """
    if not path.exists():
        return None

    total = 0
    try:
        for root, _, files in os.walk(path):
            for name in files:
                file_path = os.path.join(root, name)
                try:
                    total += os.path.getsize(file_path)
                except OSError:
                    continue
    except OSError:
        return None

    return total


def format_size(num_bytes: Optional[int]) -> str:
    """
    Format size in bytes into a human-readable string.
    """
    if num_bytes is None:
        return "n/a"

    size = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
        if size < 1024 or unit == "PB":
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def clone_repos(username: str, target_dir: Optional[str] = None) -> None:
    """
    Клонирует Python-репозитории пользователя через общий GitHub модуль.
    Clones user Python repositories via shared GitHub module.
    """
    if target_dir is None:
        output_dir = Path(os.path.expanduser("~/github"))
    else:
        output_dir = Path(os.path.expanduser(target_dir))
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"📁 Целевая папка: {output_dir}\n")

    fetcher = GitHubRepoFetcher(username=username, output_dir=output_dir)
    repos = fetcher.get_user_repos()
    if not repos:
        print("❌ Не найдено ни одного репозитория!")
        return

    python_repos = fetcher.filter_python_repos(repos)
    if not python_repos:
        print("❌ Python-репозитории не найдены!")
        return

    print(f"\n✅ Найдено Python-репозиториев: {len(python_repos)}\n")
    cloned_paths = fetcher.clone_all_repos(python_repos, max_repos=0)

    print("\n" + "=" * 80)
    print("СТАТИСТИКА КЛОНИРОВАНИЯ")
    print("=" * 80)
    print(f"✅ Успешно обработано Python-репозиториев: {len(cloned_paths)}")
    print(f"📊 Всего Python-репозиториев в выборке: {len(python_repos)}")

    total_size = format_size(get_dir_size(output_dir))
    print("\n" + "=" * 80)
    print(f"💾 Общий размер папки: {total_size}")
    print(f"📂 Папка: {output_dir}")


def main() -> None:
    """
    CLI entrypoint.
    """
    if len(sys.argv) < 2:
        print("СКРИПТ ДЛЯ КЛОНИРОВАНИЯ PYTHON-РЕПОЗИТОРИЕВ\n")
        print("Использование:")
        print("  python clone_all_repos.py <username> [target_dir]\n")
        print("Примеры:")
        print("  python clone_all_repos.py ergon73")
        print("  python clone_all_repos.py ergon73 ~/my-repos")
        print("\nЕсли не указать target_dir, репо будут склонированы в: ~/github/")
        return

    username = sys.argv[1]
    target_dir = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        clone_repos(username, target_dir)
    except KeyboardInterrupt:
        print("\n\n⚠️  Клонирование прервано пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
