#!/usr/bin/env python3
"""
СКРИПТ ДЛЯ КЛОНИРОВАНИЯ ВСЕХ РЕПОЗИТОРИЕВ С GITHUB

Использование:
  python clone_all_repos.py <username>
  
Пример:
  python clone_all_repos.py ergon73
  
Результат:
  Все репозитории будут склонированы в папку: ~/github/<repo_name>/
"""

import os
import sys
import subprocess
import json
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError
from typing import Optional

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

def get_github_repos(username: str, per_page: int = 100) -> list:
    """
    Получает список всех репозиториев пользователя через GitHub API
    
    Args:
        username: GitHub username
        per_page: Количество репо на страницу (макс 100)
        
    Returns:
        Список словарей с информацией о репозиториях
    """
    print(f"📥 Получаю список репозиториев пользователя: {username}")
    
    repos = []
    page = 1
    
    while True:
        url = f"https://api.github.com/users/{username}/repos?per_page={per_page}&page={page}&sort=updated"
        
        try:
            response = urlopen(url, timeout=10)
            data = json.loads(response.read().decode('utf-8'))
            
            if not data:
                break
                
            repos.extend(data)
            page += 1
            
            print(f"  ✓ Загружена страница {page-1} ({len(data)} репозиториев)")
            
        except URLError as e:
            print(f"❌ Ошибка при получении данных: {e}")
            break
    
    return repos

def clone_repos(username: str, target_dir: str = None) -> None:
    """
    Клонирует все репозитории пользователя
    
    Args:
        username: GitHub username
        target_dir: Папка для клонирования (default: ~/github)
    """
    
    # Определяем целевую папку
    if target_dir is None:
        target_dir = os.path.expanduser("~/github")
    else:
        target_dir = os.path.expanduser(target_dir)
    
    # Создаём папку если её нет
    Path(target_dir).mkdir(parents=True, exist_ok=True)
    print(f"📁 Целевая папка: {target_dir}\n")
    
    # Получаем список репозиториев
    repos = get_github_repos(username)
    
    if not repos:
        print("❌ Не найдено ни одного репозитория!")
        return
    
    print(f"\n✅ Найдено {len(repos)} репозиториев\n")
    print("=" * 80)
    print("НАЧИНАЮ КЛОНИРОВАНИЕ")
    print("=" * 80 + "\n")
    
    # Клонируем каждый репо
    successful = 0
    failed = 0
    skipped = 0
    
    for i, repo in enumerate(repos, 1):
        repo_name = repo['name']
        clone_url = repo['clone_url']
        repo_path = os.path.join(target_dir, repo_name)
        
        # Пропускаем если уже существует
        if os.path.exists(repo_path):
            print(f"{i:2}. ⏭️  {repo_name:40} (уже существует, пропускаю)")
            skipped += 1
            continue
        
        print(f"{i:2}. 🔄 {repo_name:40} ", end="", flush=True)
        
        try:
            # Клонируем репо
            result = subprocess.run(
                ['git', 'clone', '--quiet', clone_url, repo_path],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                # Получаем размер репо
                repo_size = format_size(get_dir_size(Path(repo_path)))
                
                print(f"✅ ({repo_size})")
                successful += 1
            else:
                print(f"❌ Ошибка: {result.stderr.split(chr(10))[0]}")
                failed += 1
                
        except subprocess.TimeoutExpired:
            print(f"❌ Timeout (репо слишком большой)")
            failed += 1
        except Exception as e:
            print(f"❌ {str(e)}")
            failed += 1
    
    # Итоговая статистика
    print("\n" + "=" * 80)
    print("СТАТИСТИКА КЛОНИРОВАНИЯ")
    print("=" * 80)
    print(f"✅ Успешно склонировано: {successful}")
    print(f"❌ Ошибок при клонировании: {failed}")
    print(f"⏭️  Пропущено (уже существуют): {skipped}")
    print(f"📊 Всего репозиториев: {len(repos)}")
    print("\n" + "=" * 80)
    
    # Выводим команду для проверки размера
    total_size = format_size(get_dir_size(Path(target_dir)))
    
    print(f"💾 Общий размер всех репо: {total_size}")
    print(f"📂 Папка: {target_dir}")
    
    # Выводим список всех клонированных репо
    if successful > 0:
        print("\n✅ СКЛОНИРОВАННЫЕ РЕПОЗИТОРИИ:\n")
        
        cloned_repos = sorted([d for d in os.listdir(target_dir) 
                              if os.path.isdir(os.path.join(target_dir, d))])
        
        for repo_name in cloned_repos:
            repo_path = os.path.join(target_dir, repo_name)
            # Проверяем что это git репо
            if os.path.exists(os.path.join(repo_path, '.git')):
                repo_size = format_size(get_dir_size(Path(repo_path)))
                print(f"  ✓ {repo_name:40} ({repo_size})")

def main():
    """Главная функция"""
    
    if len(sys.argv) < 2:
        print("СКРИПТ ДЛЯ КЛОНИРОВАНИЯ ВСЕХ РЕПОЗИТОРИЕВ\n")
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

