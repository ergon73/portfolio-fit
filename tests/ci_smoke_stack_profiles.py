#!/usr/bin/env python3
import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from portfolio_fit.discovery import evaluate_repos
from portfolio_fit.reporting import enrich_result_with_insights
from portfolio_fit.schema_contract import validate_results_contract

ScenarioFactory = Callable[[Path], None]


def _touch(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _init_repo(repo_path: Path) -> None:
    repo_path.mkdir(parents=True, exist_ok=True)
    (repo_path / ".git").mkdir(parents=True, exist_ok=True)


def _build_python_backend(repo_path: Path) -> None:
    _init_repo(repo_path)
    _touch(
        repo_path / "main.py",
        "def add(a: int, b: int) -> int:\n" "    return a + b\n",
    )
    _touch(repo_path / "requirements.txt", "fastapi==0.112.0\n")
    _touch(repo_path / "README.md", "# Backend\n")


def _build_node_ts_frontend(repo_path: Path) -> None:
    _init_repo(repo_path)
    package_json = {
        "name": "node-ts-frontend",
        "version": "1.0.0",
        "scripts": {
            "build": "vite build",
            "test": "vitest",
            "lint": "eslint .",
            "typecheck": "tsc --noEmit",
        },
        "dependencies": {
            "react": "^18.2.0",
            "react-dom": "^18.2.0",
        },
        "devDependencies": {
            "typescript": "^5.6.0",
            "vite": "^5.0.0",
            "eslint": "^9.0.0",
            "vitest": "^2.0.0",
        },
    }
    _touch(repo_path / "package.json", json.dumps(package_json, indent=2))
    _touch(
        repo_path / "tsconfig.json",
        json.dumps(
            {
                "compilerOptions": {
                    "strict": True,
                    "noImplicitAny": True,
                    "strictNullChecks": True,
                }
            },
            indent=2,
        ),
    )
    _touch(repo_path / "src" / "main.tsx", "console.log('frontend');\n")
    _touch(repo_path / "index.html", "<!doctype html><html lang='en'></html>\n")


def _build_django_templates(repo_path: Path) -> None:
    _init_repo(repo_path)
    _touch(
        repo_path / "manage.py",
        "#!/usr/bin/env python\n" "def main() -> None:\n" "    pass\n",
    )
    _touch(repo_path / "requirements.txt", "Django==5.1.0\n")
    _touch(repo_path / "templates" / "base.html", "<html><body></body></html>\n")
    _touch(repo_path / "app" / "views.py", "def view(request):\n    return None\n")


def _build_mixed_fullstack(repo_path: Path) -> None:
    _init_repo(repo_path)
    _touch(
        repo_path / "api.py",
        "def health() -> dict:\n" "    return {'ok': True}\n",
    )
    package_json = {
        "name": "python-react-fullstack",
        "version": "1.0.0",
        "dependencies": {
            "react": "^18.2.0",
        },
    }
    _touch(repo_path / "package.json", json.dumps(package_json, indent=2))
    _touch(repo_path / "src" / "App.tsx", "export const App = () => null;\n")


SCENARIOS: Dict[str, Dict[str, object]] = {
    "backend-only": {
        "expected_stack": "python_backend",
        "factory": _build_python_backend,
    },
    "node-ts": {
        "expected_stack": "node_frontend",
        "factory": _build_node_ts_frontend,
    },
    "django-templates": {
        "expected_stack": "python_django_templates",
        "factory": _build_django_templates,
    },
    "mixed-fullstack": {
        "expected_stack": "python_fullstack_react",
        "factory": _build_mixed_fullstack,
    },
}


def run_scenario(scenario_name: str) -> None:
    scenario = SCENARIOS[scenario_name]
    expected_stack = str(scenario["expected_stack"])
    factory = scenario["factory"]
    assert callable(factory)

    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp) / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        repo_path = workspace / scenario_name
        scenario_factory = factory
        scenario_factory(repo_path)

        results = evaluate_repos(workspace, recursive=False, stack_profile="auto")
        if len(results) != 1:
            raise RuntimeError(
                f"scenario '{scenario_name}' expected 1 result, got {len(results)}"
            )

        result = results[0]
        detected_stack = str(result.get("stack_profile"))
        if detected_stack != expected_stack:
            raise RuntimeError(
                f"scenario '{scenario_name}' stack mismatch: "
                f"expected '{expected_stack}', got '{detected_stack}'"
            )

        enriched_results = [enrich_result_with_insights(item) for item in results]
        errors = validate_results_contract(enriched_results)
        if errors:
            raise RuntimeError(
                f"scenario '{scenario_name}' contract errors: {errors[:3]}"
            )

        print(
            f"smoke scenario ok: {scenario_name} | stack={detected_stack} | "
            f"score={result.get('total_score')}"
        )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run stack-profile smoke scenario(s) for CI matrix."
    )
    parser.add_argument(
        "--scenario",
        choices=["all", *sorted(SCENARIOS.keys())],
        default="all",
        help="Scenario to run (default: all).",
    )
    return parser.parse_args()


def main() -> None:
    stdout_obj: Any = sys.stdout
    stderr_obj: Any = sys.stderr
    try:
        stdout_obj.reconfigure(encoding="utf-8", errors="replace")
        stderr_obj.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    args = parse_arguments()
    if args.scenario == "all":
        for scenario_name in sorted(SCENARIOS.keys()):
            run_scenario(scenario_name)
        return
    run_scenario(args.scenario)


if __name__ == "__main__":
    main()
