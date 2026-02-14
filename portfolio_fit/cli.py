import argparse
import sys
from pathlib import Path

from portfolio_fit.discovery import evaluate_repos, validate_path
from portfolio_fit.github_fetcher import GitHubRepoFetcher
from portfolio_fit.reporting import print_results
from portfolio_fit.scoring import STACK_PROFILES


def parse_arguments() -> argparse.Namespace:
    """
    Парсинг аргументов командной строки
    Parse command line arguments
    """
    parser = argparse.ArgumentParser(
        description="Enhanced Portfolio Evaluation Script v3.1\n"
        "Расширенный скрипт оценки портфолио v3.1",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования / Usage examples:
  %(prog)s                           # Интерактивный режим / Interactive mode
  %(prog)s --github username         # Оценка GitHub аккаунта / Evaluate GitHub account
  %(prog)s -g username -o ./repos    # С указанием папки / With output directory
  %(prog)s --path ./my_repos         # Локальная папка / Local folder
  %(prog)s --path ./workspace --recursive  # Рекурсивный поиск / Recursive discovery
  %(prog)s --path ./workspace --stack-profile node_frontend  # Принудительный профиль / Forced stack profile
  %(prog)s --path ./repos --compare portfolio_evaluation_local.json  # Сравнение запусков / Compare runs
        """,
    )

    parser.add_argument(
        "-g",
        "--github",
        type=str,
        metavar="USERNAME",
        help="GitHub username для оценки / GitHub username to evaluate",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=str,
        metavar="DIR",
        help="Директория для клонирования репозиториев / Directory to clone repos",
    )

    parser.add_argument(
        "-p",
        "--path",
        type=str,
        metavar="DIR",
        help="Путь к локальной папке с репозиториями / Path to local repos folder",
    )

    parser.add_argument(
        "-t",
        "--token",
        type=str,
        metavar="TOKEN",
        help="GitHub API token (для увеличения лимита запросов) / GitHub API token",
    )

    parser.add_argument(
        "-m",
        "--max-repos",
        type=int,
        default=100,
        metavar="N",
        help="Максимум репозиториев для клонирования (по умолчанию 100, 0 = все) / Max repos to clone (default 100, 0 = all)",
    )

    parser.add_argument(
        "--keep-repos",
        action="store_true",
        help="Не удалять клонированные репозитории / Keep cloned repositories",
    )

    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Рекурсивно искать репозитории во вложенных папках / Recursively discover nested repositories",
    )

    parser.add_argument(
        "--compare",
        type=str,
        metavar="JSON_FILE",
        help="Сравнить текущие результаты с предыдущим JSON-отчетом / Compare with previous JSON report",
    )

    parser.add_argument(
        "--stack-profile",
        type=str,
        choices=list(STACK_PROFILES),
        default="auto",
        help=(
            "Профиль стека (auto/python_backend/python_fullstack_react/"
            "python_django_templates/node_frontend/mixed_unknown) / "
            "Stack profile override"
        ),
    )

    return parser.parse_args()


def main():
    """
    Основной скрипт
    Main script
    """
    # Принудительная очистка буфера для PowerShell
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        # Для старых версий Python
        pass

    # Явный вывод в самом начале для диагностики
    sys.stdout.write("=" * 120 + "\n")
    sys.stdout.flush()
    sys.stdout.write(
        "РАСШИРЕННЫЙ СКРИПТ ОЦЕНКИ ПОРТФОЛИО v3.1 / ENHANCED PORTFOLIO EVALUATION SCRIPT v3.1\n"
    )
    sys.stdout.flush()
    sys.stdout.write("17 Core-критериев + full-stack signals / 50 Баллов\n")
    sys.stdout.flush()
    sys.stdout.write("17 core criteria + full-stack signals / 50 points\n")
    sys.stdout.flush()
    sys.stdout.write("=" * 120 + "\n\n")
    sys.stdout.flush()

    try:
        args = parse_arguments()

        # Режим GitHub / GitHub mode
        if args.github:
            output_dir = Path(args.output) if args.output else None

            fetcher = GitHubRepoFetcher(
                username=args.github, output_dir=output_dir, token=args.token
            )

            try:
                # Получаем список репозиториев / Get repository list
                repos = fetcher.get_user_repos()
                if not repos:
                    print(
                        f"\n⚠️  Не найдено репозиториев для пользователя '{args.github}'",
                        flush=True,
                    )
                    print(
                        f"   No repositories found for user '{args.github}'", flush=True
                    )
                    print("   Возможные причины / Possible reasons:", flush=True)
                    print(
                        "   - Пользователь не существует / User doesn't exist",
                        flush=True,
                    )
                    print(
                        "   - Нет публичных репозиториев / No public repositories",
                        flush=True,
                    )
                    print(
                        "   - Ошибка при обращении к GitHub API / Error accessing GitHub API",
                        flush=True,
                    )
                    return

                # Фильтруем поддерживаемые репозитории / Filter supported repos
                supported_repos = fetcher.filter_supported_repos(repos)

                # Клонируем / Clone
                cloned_paths = fetcher.clone_all_repos(
                    supported_repos, max_repos=args.max_repos
                )

                if not cloned_paths:
                    print(
                        "❌ Нет репозиториев для оценки / No repositories to evaluate",
                        flush=True,
                    )
                    return

                # Оцениваем / Evaluate
                results = evaluate_repos(
                    fetcher.output_dir,
                    github_username=args.github,
                    recursive=False,
                    stack_profile=args.stack_profile,
                )

                # Выводим результаты / Print results
                print_results(
                    results, github_username=args.github, compare_path=args.compare
                )

            finally:
                # Очистка если не указано --keep-repos / Cleanup if not --keep-repos
                if not args.keep_repos and not args.output:
                    fetcher.cleanup()
                else:
                    print(
                        f"\n📁 Репозитории сохранены в: {fetcher.output_dir}",
                        flush=True,
                    )
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
                github_username = input(
                    "Введите GitHub username / Enter GitHub username: "
                ).strip()
                if github_username:
                    # Рекурсивный вызов с аргументами / Recursive call with args
                    sys.argv = [sys.argv[0], "--github", github_username]
                    main()
                    return

            path_input = input(
                "\nВведите путь к папке с репозиториями (или Enter для текущей): \n"
                "Enter path to repositories folder (or Enter for current): "
            ).strip()
            repos_dir = validate_path(path_input)

        if repos_dir is None:
            print("❌ Ошибка: некорректный путь! / Error: invalid path!", flush=True)
            return

        if not repos_dir.exists():
            print(
                f"❌ Ошибка: папка {repos_dir} не найдена! / Error: folder {repos_dir} not found!",
                flush=True,
            )
            return

        # Оцениваем / Evaluate
        results = evaluate_repos(
            repos_dir, recursive=args.recursive, stack_profile=args.stack_profile
        )

        # Выводим результаты / Print results
        print_results(results, compare_path=args.compare)

    except KeyboardInterrupt:
        print("\n\n⚠️  Прервано пользователем / Interrupted by user", flush=True)
        sys.exit(1)
    except Exception as e:
        print(
            f"\n❌ КРИТИЧЕСКАЯ ОШИБКА / CRITICAL ERROR: {e}",
            flush=True,
            file=sys.stderr,
        )
        print(f"   {type(e).__name__}: {str(e)}", flush=True, file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
