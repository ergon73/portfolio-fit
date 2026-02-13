import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from portfolio_fit.schema_contract import validate_results_contract

BLOCK_SPECS = [
    (
        "block1_code_quality",
        "БЛОК 1 - Качество кода / CODE QUALITY",
        15,
        [
            ("test_coverage", "Покрытие тестами / Test Coverage", 5),
            ("code_complexity", "Сложность кода / Code Complexity", 5),
            ("type_hints", "Type Hints / Type Hints", 5),
        ],
    ),
    (
        "block2_security",
        "БЛОК 2 - Безопасность / SECURITY",
        10,
        [
            ("vulnerabilities", "Уязвимости / Vulnerabilities", 5),
            ("dep_health", "Здоровье зависимостей / Dependency Health", 3),
            ("security_scanning", "Сканирование безопасности / Security Scanning", 2),
        ],
    ),
    (
        "block3_maintenance",
        "БЛОК 3 - Поддержка / MAINTENANCE",
        10,
        [
            ("project_activity", "Активность проекта / Project Activity", 5),
            ("version_stability", "Стабильность версии / Version Stability", 3),
            ("changelog", "CHANGELOG / CHANGELOG", 2),
        ],
    ),
    (
        "block4_architecture",
        "БЛОК 4 - Архитектура / ARCHITECTURE",
        10,
        [
            ("docstrings", "Docstrings / Docstrings", 5),
            ("logging", "Логирование / Logging", 3),
            ("structure", "Структура проекта / Project Structure", 2),
        ],
    ),
    (
        "block5_documentation",
        "БЛОК 5 - Документация / DOCUMENTATION",
        10,
        [
            ("readme", "README / README", 5),
            ("api_docs", "API документация / API Documentation", 3),
            ("getting_started", "Простота запуска / Getting Started", 2),
        ],
    ),
    (
        "block6_devops",
        "БЛОК 6 - DevOps / DEVOPS",
        5,
        [
            ("docker", "Docker / Docker", 3),
            ("cicd", "CI/CD / CI/CD", 2),
        ],
    ),
]

CORE_METRICS = {"test_coverage", "code_complexity", "vulnerabilities"}

CRITERION_PLAYBOOK: Dict[str, Dict[str, Any]] = {
    "test_coverage": {
        "title": "Raise automated test coverage",
        "action": "Add tests for critical flows and publish coverage.xml in CI.",
        "impact": 5,
        "effort": 3,
    },
    "code_complexity": {
        "title": "Reduce complex functions",
        "action": "Split large functions and add guard clauses for simpler flow.",
        "impact": 4,
        "effort": 3,
    },
    "type_hints": {
        "title": "Increase type hint coverage",
        "action": "Annotate public functions first and enforce mypy in CI.",
        "impact": 3,
        "effort": 2,
    },
    "vulnerabilities": {
        "title": "Resolve dependency vulnerabilities",
        "action": "Run pip-audit in CI and upgrade vulnerable packages.",
        "impact": 5,
        "effort": 3,
    },
    "dep_health": {
        "title": "Trim dependency surface",
        "action": "Remove unused packages and pin direct dependencies.",
        "impact": 3,
        "effort": 2,
    },
    "security_scanning": {
        "title": "Enable security scanning",
        "action": "Add Dependabot and bandit/pip-audit workflow checks.",
        "impact": 4,
        "effort": 2,
    },
    "project_activity": {
        "title": "Improve maintenance signals",
        "action": "Publish regular updates and tag stable checkpoints.",
        "impact": 2,
        "effort": 3,
    },
    "version_stability": {
        "title": "Adopt semantic versioning",
        "action": "Define stable versions in pyproject and cut tagged releases.",
        "impact": 2,
        "effort": 1,
    },
    "changelog": {
        "title": "Maintain CHANGELOG",
        "action": "Document user-visible changes in CHANGELOG.md.",
        "impact": 2,
        "effort": 1,
    },
    "docstrings": {
        "title": "Improve docstring coverage",
        "action": "Add concise docstrings for public functions and classes.",
        "impact": 3,
        "effort": 2,
    },
    "logging": {
        "title": "Harden logging",
        "action": "Replace debug prints with structured logging.",
        "impact": 3,
        "effort": 2,
    },
    "structure": {
        "title": "Normalize project layout",
        "action": "Keep code in src/, tests in tests/, docs in docs/.",
        "impact": 3,
        "effort": 2,
    },
    "readme": {
        "title": "Strengthen README onboarding",
        "action": "Add install, usage, examples, and troubleshooting sections.",
        "impact": 4,
        "effort": 2,
    },
    "api_docs": {
        "title": "Publish API contract",
        "action": "Provide OpenAPI/Postman artifacts and usage examples.",
        "impact": 3,
        "effort": 2,
    },
    "getting_started": {
        "title": "Simplify first run",
        "action": "Add make target or one-command startup script.",
        "impact": 3,
        "effort": 1,
    },
    "docker": {
        "title": "Containerize reproducibly",
        "action": "Add Dockerfile, compose, dockerignore and healthcheck.",
        "impact": 3,
        "effort": 3,
    },
    "cicd": {
        "title": "Expand CI checks",
        "action": "Run lint, tests, coverage and release checks in workflows.",
        "impact": 4,
        "effort": 2,
    },
}


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _score_text(value: Optional[float], max_score: float) -> str:
    if value is None:
        return f"n/a/{max_score}"
    return f"{value:.2f}/{max_score}"


def _criterion_labels() -> Dict[str, str]:
    labels: Dict[str, str] = {}
    for _, _, _, criteria in BLOCK_SPECS:
        for key, label, _ in criteria:
            labels[key] = label
    return labels


CRITERION_LABELS = _criterion_labels()


def build_criterion_explainability(result: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Build explainability payload for every criterion."""
    explainability: Dict[str, Dict[str, Any]] = {}
    criteria_meta = result.get("criteria_meta", {})
    if not isinstance(criteria_meta, dict):
        return explainability

    for criterion, meta_raw in criteria_meta.items():
        if not isinstance(meta_raw, dict):
            continue

        score_raw = result.get(criterion)
        score = None if score_raw is None else _to_float(score_raw)
        max_score = _to_float(meta_raw.get("max_score"), 0.0)
        status = str(meta_raw.get("status", "unknown"))
        method = str(meta_raw.get("method", "heuristic"))
        confidence = _to_float(meta_raw.get("confidence"), 0.0)
        note = str(meta_raw.get("note", "")).strip()

        if score is None or status == "unknown":
            why = note or "No reliable data available to score this criterion yet."
            gap = max_score
        else:
            gap = max(0.0, max_score - score)
            if gap == 0:
                why = note or "Criterion is fully satisfied."
            else:
                why = (
                    note
                    or f"Partial result: {score:.2f}/{max_score:.2f}, gap {gap:.2f}."
                )

        explainability[criterion] = {
            "label": CRITERION_LABELS.get(criterion, criterion),
            "score": round(score, 2) if score is not None else None,
            "max_score": round(max_score, 2),
            "gap_to_max": round(gap, 2),
            "status": status,
            "method": method,
            "confidence": round(confidence, 2),
            "why": why,
        }

    return explainability


def generate_recommendations(
    result: Dict[str, Any],
    explainability: Optional[Dict[str, Dict[str, Any]]] = None,
    limit: int = 7,
) -> List[Dict[str, Any]]:
    """Generate actionable recommendations for low-score or unknown criteria."""
    if explainability is None:
        explainability = build_criterion_explainability(result)

    recommendations: List[Dict[str, Any]] = []
    for criterion, explanation in explainability.items():
        playbook = CRITERION_PLAYBOOK.get(criterion)
        if not playbook:
            continue

        score_raw = explanation.get("score")
        score = None if score_raw is None else _to_float(score_raw)
        max_score = _to_float(explanation.get("max_score"), 0.0)
        status = str(explanation.get("status", "unknown"))
        if max_score <= 0:
            continue

        if status == "unknown" or score is None:
            gap_ratio = 0.9 if criterion in CORE_METRICS else 0.7
        else:
            ratio = score / max_score
            if ratio >= 0.85:
                continue
            gap_ratio = max(0.0, 1.0 - ratio)

        impact = int(playbook.get("impact", 1))
        effort = max(1, int(playbook.get("effort", 1)))
        confidence = _to_float(explanation.get("confidence"), 0.0)
        confidence_factor = 1.0 + (
            0.15 if status == "unknown" else (1.0 - confidence) * 0.1
        )
        priority_score = (gap_ratio * impact / effort) * confidence_factor

        recommendations.append(
            {
                "criterion": criterion,
                "label": explanation.get("label", criterion),
                "title": playbook.get("title", "Improve criterion"),
                "action": playbook.get(
                    "action", "Add improvements for this criterion."
                ),
                "reason": explanation.get("why", "Low score detected."),
                "impact": impact,
                "effort": effort,
                "quick_win": impact >= 3 and effort <= 2,
                "priority_score": round(priority_score, 3),
            }
        )

    recommendations.sort(
        key=lambda item: (
            _to_float(item.get("priority_score"), 0.0),
            _to_float(item.get("impact"), 0.0),
            -_to_float(item.get("effort"), 0.0),
        ),
        reverse=True,
    )
    return recommendations[:limit]


def enrich_result_with_insights(result: Dict[str, Any]) -> Dict[str, Any]:
    """Attach explainability and recommendation sections to a repo result."""
    enriched = deepcopy(result)
    explainability = build_criterion_explainability(enriched)
    recommendations = generate_recommendations(enriched, explainability=explainability)
    quick_fixes = [rec for rec in recommendations if bool(rec.get("quick_win"))][:5]
    enriched["criteria_explainability"] = explainability
    enriched["recommendations"] = recommendations
    enriched["quick_fixes"] = quick_fixes
    return enriched


def enrich_results_with_insights(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [enrich_result_with_insights(result) for result in results]


def build_portfolio_quick_fixes(
    results: List[Dict[str, Any]], limit: int = 8
) -> List[Dict[str, Any]]:
    """Aggregate quick fixes across repositories into impact/effort matrix."""
    aggregate: Dict[str, Dict[str, Any]] = {}

    for result in results:
        repo = str(result.get("repo", "unknown-repo"))
        recommendations = result.get("recommendations", [])
        if not isinstance(recommendations, list):
            continue

        for rec in recommendations:
            if not isinstance(rec, dict) or not bool(rec.get("quick_win")):
                continue

            criterion = str(rec.get("criterion", "unknown"))
            item = aggregate.setdefault(
                criterion,
                {
                    "criterion": criterion,
                    "title": rec.get("title", "Quick fix"),
                    "action": rec.get("action", ""),
                    "impact": int(rec.get("impact", 1)),
                    "effort": int(rec.get("effort", 1)),
                    "repos": set(),
                    "priority_total": 0.0,
                    "samples": 0,
                },
            )
            item["repos"].add(repo)
            item["priority_total"] += _to_float(rec.get("priority_score"), 0.0)
            item["samples"] += 1

    matrix: List[Dict[str, Any]] = []
    for item in aggregate.values():
        samples = max(1, int(item["samples"]))
        avg_priority = item["priority_total"] / samples
        matrix.append(
            {
                "criterion": item["criterion"],
                "title": item["title"],
                "action": item["action"],
                "impact": int(item["impact"]),
                "effort": int(item["effort"]),
                "repos_affected": len(item["repos"]),
                "avg_priority": round(avg_priority, 3),
            }
        )

    matrix.sort(
        key=lambda row: (
            _to_float(row.get("avg_priority"), 0.0),
            _to_float(row.get("repos_affected"), 0.0),
        ),
        reverse=True,
    )
    return matrix[:limit]


def save_text_report(
    results: List[Dict[str, Any]], github_username: Optional[str] = None
) -> str:
    """
    Сохраняет полный текстовый отчет с отсортированным списком всех репозиториев
    Saves full text report with sorted list of all repositories
    """
    if not results:
        return ""

    enriched_results = enrich_results_with_insights(results)
    sorted_results = sorted(
        enriched_results, key=lambda x: x["total_score"], reverse=True
    )
    report_file = f"portfolio_report_{github_username or 'local'}.txt"

    with open(report_file, "w", encoding="utf-8") as f:
        f.write("=" * 120 + "\n")
        if github_username:
            f.write(f"ПОЛНЫЙ ОТЧЕТ ОЦЕНКИ ПОРТФОЛИО @{github_username}\n")
            f.write(f"FULL PORTFOLIO EVALUATION REPORT @{github_username}\n")
        else:
            f.write(
                "ПОЛНЫЙ ОТЧЕТ ОЦЕНКИ ПОРТФОЛИО / FULL PORTFOLIO EVALUATION REPORT\n"
            )
        f.write("(по Product Readiness Score v2.3 / by Product Readiness Score v2.3)\n")
        f.write("=" * 120 + "\n\n")

        f.write("ОБЩАЯ СТАТИСТИКА / GENERAL STATISTICS\n")
        f.write("-" * 120 + "\n")
        f.write(f"Всего репозиториев / Total repositories: {len(sorted_results)}\n")

        categories: Dict[str, int] = {}
        for result in sorted_results:
            category = str(result.get("category", "unknown"))
            categories[category] = categories.get(category, 0) + 1

        f.write("\nРаспределение по категориям / Distribution by categories:\n")
        for cat, count in categories.items():
            percentage = count * 100 // len(sorted_results) if sorted_results else 0
            f.write(f"  {cat:45} : {count:3} ({percentage:3}%)\n")

        avg_score = sum(
            _to_float(r.get("total_score"), 0.0) for r in sorted_results
        ) / len(sorted_results)
        avg_coverage = sum(
            _to_float(r.get("data_coverage_percent"), 0.0) for r in sorted_results
        ) / len(sorted_results)
        f.write(f"\nСредний балл / Average score: {avg_score:.2f}/50\n")
        f.write(
            f"Среднее покрытие данных / Average data coverage: {avg_coverage:.2f}%\n"
        )
        f.write(
            "Максимальный балл / Maximum score: "
            f"{max(_to_float(r.get('total_score'), 0.0) for r in sorted_results):.2f}/50\n"
        )
        f.write(
            "Минимальный балл / Minimum score: "
            f"{min(_to_float(r.get('total_score'), 0.0) for r in sorted_results):.2f}/50\n"
        )

        f.write("\n" + "=" * 120 + "\n")
        f.write("ПОЛНЫЙ СПИСОК РЕПОЗИТОРИЕВ (отсортирован по баллам)\n")
        f.write("FULL REPOSITORY LIST (sorted by score)\n")
        f.write("=" * 120 + "\n\n")

        for i, result in enumerate(sorted_results, 1):
            repo_name = result["repo"]
            if github_username:
                repo_url = f"https://github.com/{github_username}/{repo_name}"
            else:
                repo_url = result.get("github_url", repo_name)

            f.write(f"{'=' * 120}\n")
            f.write(f"#{i}. {repo_name}\n")
            f.write(f"{'-' * 120}\n")
            f.write(f"URL: {repo_url}\n")
            f.write(
                f"Общий балл / Total Score: {_to_float(result.get('total_score'), 0.0):.2f}/50\n"
            )
            f.write(f"Категория / Category: {result.get('category', 'unknown')}\n")
            f.write(
                "Покрытие данных / Data coverage: "
                f"{_to_float(result.get('data_coverage_percent'), 0.0):.2f}%\n"
            )
            f.write(
                "Известные данные / Known score: "
                f"{_to_float(result.get('known_score'), 0.0):.2f}/"
                f"{_to_float(result.get('known_max_score'), 0.0):.2f}\n"
            )
            f.write(
                "Качество данных / Data quality: "
                f"{result.get('data_quality_status', 'n/a')}\n"
            )
            f.write("\nДетальная оценка / Detailed Evaluation:\n")

            criteria_meta = result.get("criteria_meta", {})
            blocks_meta = result.get("blocks_meta", {})

            for block_key, block_title, block_max, criteria_list in BLOCK_SPECS:
                block_info = {}
                if isinstance(blocks_meta, dict):
                    raw_block_info = blocks_meta.get(block_key, {})
                    if isinstance(raw_block_info, dict):
                        block_info = raw_block_info
                block_score_raw = block_info.get("score")
                block_score = (
                    None if block_score_raw is None else _to_float(block_score_raw)
                )
                block_coverage = _to_float(block_info.get("data_coverage_percent"), 0.0)
                f.write(
                    f"  {block_title}: {_score_text(block_score, float(block_max))} "
                    f"| data {block_coverage:.1f}%\n"
                )

                for criterion_key, criterion_label, criterion_max in criteria_list:
                    criterion_score_raw = result.get(criterion_key)
                    criterion_score = (
                        None
                        if criterion_score_raw is None
                        else _to_float(criterion_score_raw)
                    )
                    meta = {}
                    if isinstance(criteria_meta, dict):
                        raw_meta = criteria_meta.get(criterion_key, {})
                        if isinstance(raw_meta, dict):
                            meta = raw_meta
                    status = str(meta.get("status", "known"))
                    method = str(meta.get("method", "heuristic"))
                    confidence = _to_float(meta.get("confidence"), 0.0)
                    note = str(meta.get("note", ""))
                    f.write(
                        f"    • {criterion_label}: "
                        f"{_score_text(criterion_score, float(criterion_max))} "
                        f"[{status}, {method}, conf={confidence:.2f}]\n"
                    )
                    if note:
                        f.write(f"      note: {note}\n")

            recommendations = result.get("recommendations", [])
            if isinstance(recommendations, list) and recommendations:
                f.write("\n  Actionable recommendations:\n")
                for recommendation in recommendations[:4]:
                    if not isinstance(recommendation, dict):
                        continue
                    f.write(
                        "    - "
                        f"{recommendation.get('title', 'Improve criterion')} "
                        f"(impact={recommendation.get('impact', '?')}, "
                        f"effort={recommendation.get('effort', '?')}, "
                        f"priority={_to_float(recommendation.get('priority_score'), 0.0):.2f})\n"
                    )
                    f.write(f"      action: {recommendation.get('action', '')}\n")
                    f.write(f"      why: {recommendation.get('reason', '')}\n")

            quality_warnings = result.get("data_quality_warnings", [])
            if isinstance(quality_warnings, list) and quality_warnings:
                f.write("\n  Data quality warnings:\n")
                for warning in quality_warnings:
                    f.write(f"    - {warning}\n")

            f.write("\n")

        f.write("\n" + "=" * 120 + "\n")
        f.write("РЕКОМЕНДАЦИИ / RECOMMENDATIONS\n")
        f.write("=" * 120 + "\n\n")

        excellent_repos = [
            r
            for r in sorted_results
            if _to_float(r.get("total_score"), 0.0) >= 30
            and _to_float(r.get("data_coverage_percent"), 0.0) >= 70.0
        ]
        good_repos = [
            r
            for r in sorted_results
            if 20 <= _to_float(r.get("total_score"), 0.0) < 30
            and _to_float(r.get("data_coverage_percent"), 0.0) >= 70.0
        ]

        if excellent_repos:
            f.write(
                f"🌟 Отличные проекты для портфолио ({len(excellent_repos)} проектов):\n"
            )
            f.write(
                f"   Excellent projects for portfolio ({len(excellent_repos)} projects):\n"
            )
            for result in excellent_repos:
                url = str(
                    result.get(
                        "github_url",
                        (
                            f"{github_username}/{result['repo']}"
                            if github_username
                            else result["repo"]
                        ),
                    )
                )
                f.write(
                    f"   • {url} - {_to_float(result.get('total_score'), 0.0):.1f}/50 "
                    f"(data {_to_float(result.get('data_coverage_percent'), 0.0):.0f}%)\n"
                )
            f.write("\n")

        if good_repos:
            f.write(f"⭐ Хорошие проекты ({len(good_repos)} проектов):\n")
            f.write(f"   Good projects ({len(good_repos)} projects):\n")
            for result in good_repos[:10]:
                url = str(
                    result.get(
                        "github_url",
                        (
                            f"{github_username}/{result['repo']}"
                            if github_username
                            else result["repo"]
                        ),
                    )
                )
                f.write(
                    f"   • {url} - {_to_float(result.get('total_score'), 0.0):.1f}/50 "
                    f"(data {_to_float(result.get('data_coverage_percent'), 0.0):.0f}%)\n"
                )

        quick_fix_matrix = build_portfolio_quick_fixes(sorted_results, limit=10)
        if quick_fix_matrix:
            f.write("\n" + "=" * 120 + "\n")
            f.write("MATRIX QUICK FIXES (impact/effort)\n")
            f.write("=" * 120 + "\n")
            for idx, row in enumerate(quick_fix_matrix, 1):
                f.write(
                    f"{idx:2}. {row['title']} | impact={row['impact']} "
                    f"effort={row['effort']} repos={row['repos_affected']} "
                    f"priority={row['avg_priority']:.2f}\n"
                )
                f.write(f"    action: {row['action']}\n")

        f.write("\n" + "=" * 120 + "\n")
        f.write(
            f"Отчет создан / Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        )
        f.write("=" * 120 + "\n")

    return report_file


def load_evaluation_results(json_path: str) -> List[Dict[str, Any]]:
    """Load evaluation JSON from disk."""
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"comparison file not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict) and isinstance(data.get("results"), list):
        return [item for item in data["results"] if isinstance(item, dict)]
    raise ValueError("comparison file has unsupported format; expected list[dict]")


def _extract_criterion_deltas(
    previous: Dict[str, Any], current: Dict[str, Any], limit: int = 5
) -> List[Dict[str, Any]]:
    previous_meta = previous.get("criteria_meta", {})
    current_meta = current.get("criteria_meta", {})
    if not isinstance(previous_meta, dict) or not isinstance(current_meta, dict):
        return []

    deltas: List[Dict[str, Any]] = []
    for criterion in current_meta:
        before_raw = previous.get(criterion)
        after_raw = current.get(criterion)
        if before_raw is None or after_raw is None:
            continue

        before = _to_float(before_raw)
        after = _to_float(after_raw)
        delta = round(after - before, 2)
        if abs(delta) < 0.01:
            continue

        deltas.append(
            {
                "criterion": criterion,
                "label": CRITERION_LABELS.get(criterion, criterion),
                "before": round(before, 2),
                "after": round(after, 2),
                "delta": delta,
            }
        )

    deltas.sort(key=lambda item: abs(_to_float(item.get("delta"), 0.0)), reverse=True)
    return deltas[:limit]


def build_comparison(
    previous_results: List[Dict[str, Any]],
    current_results: List[Dict[str, Any]],
    baseline_source: Optional[str] = None,
) -> Dict[str, Any]:
    """Build before/after comparison for evaluation runs."""
    previous_map = {
        str(item.get("repo")): item
        for item in previous_results
        if isinstance(item, dict) and item.get("repo")
    }
    current_map = {
        str(item.get("repo")): item
        for item in current_results
        if isinstance(item, dict) and item.get("repo")
    }

    entries: List[Dict[str, Any]] = []
    comparable_deltas: List[float] = []

    for repo in sorted(current_map):
        current = current_map[repo]
        previous = previous_map.get(repo)

        if previous is None:
            entries.append(
                {
                    "repo": repo,
                    "status": "new",
                    "before_score": None,
                    "after_score": round(_to_float(current.get("total_score"), 0.0), 2),
                    "delta_score": None,
                    "before_coverage": None,
                    "after_coverage": round(
                        _to_float(current.get("data_coverage_percent"), 0.0), 2
                    ),
                    "delta_coverage": None,
                    "category_before": None,
                    "category_after": current.get("category"),
                    "criterion_deltas": [],
                }
            )
            continue

        before_score = _to_float(previous.get("total_score"), 0.0)
        after_score = _to_float(current.get("total_score"), 0.0)
        delta_score = round(after_score - before_score, 2)
        comparable_deltas.append(delta_score)

        before_coverage = _to_float(previous.get("data_coverage_percent"), 0.0)
        after_coverage = _to_float(current.get("data_coverage_percent"), 0.0)
        delta_coverage = round(after_coverage - before_coverage, 2)

        status = "unchanged"
        if delta_score > 0.05:
            status = "improved"
        elif delta_score < -0.05:
            status = "declined"

        entries.append(
            {
                "repo": repo,
                "status": status,
                "before_score": round(before_score, 2),
                "after_score": round(after_score, 2),
                "delta_score": delta_score,
                "before_coverage": round(before_coverage, 2),
                "after_coverage": round(after_coverage, 2),
                "delta_coverage": delta_coverage,
                "category_before": previous.get("category"),
                "category_after": current.get("category"),
                "criterion_deltas": _extract_criterion_deltas(previous, current),
            }
        )

    removed_repos = sorted(set(previous_map).difference(current_map))
    for repo in removed_repos:
        previous = previous_map[repo]
        entries.append(
            {
                "repo": repo,
                "status": "removed",
                "before_score": round(_to_float(previous.get("total_score"), 0.0), 2),
                "after_score": None,
                "delta_score": None,
                "before_coverage": round(
                    _to_float(previous.get("data_coverage_percent"), 0.0), 2
                ),
                "after_coverage": None,
                "delta_coverage": None,
                "category_before": previous.get("category"),
                "category_after": None,
                "criterion_deltas": [],
            }
        )

    summary = {
        "total_current": len(current_map),
        "total_previous": len(previous_map),
        "comparable": len(comparable_deltas),
        "improved": sum(1 for item in entries if item.get("status") == "improved"),
        "declined": sum(1 for item in entries if item.get("status") == "declined"),
        "unchanged": sum(1 for item in entries if item.get("status") == "unchanged"),
        "new": sum(1 for item in entries if item.get("status") == "new"),
        "removed": sum(1 for item in entries if item.get("status") == "removed"),
        "avg_delta_score": (
            round(sum(comparable_deltas) / len(comparable_deltas), 3)
            if comparable_deltas
            else 0.0
        ),
    }

    entries.sort(
        key=lambda item: (
            (
                _to_float(item.get("delta_score"), -999.0)
                if item.get("delta_score") is not None
                else -999.0
            ),
            str(item.get("repo", "")),
        ),
        reverse=True,
    )

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "baseline_source": baseline_source,
        "summary": summary,
        "repos": entries,
    }


def save_comparison_artifacts(
    comparison: Dict[str, Any], github_username: Optional[str] = None
) -> Tuple[str, str]:
    """Persist comparison to JSON and TXT files."""
    suffix = github_username or "local"
    json_file = f"portfolio_compare_{suffix}.json"
    txt_file = f"portfolio_compare_{suffix}.txt"

    with open(json_file, "w", encoding="utf-8") as file:
        json.dump(comparison, file, indent=2, ensure_ascii=False)

    summary = comparison.get("summary", {})
    repos = comparison.get("repos", [])
    with open(txt_file, "w", encoding="utf-8") as file:
        file.write("=" * 120 + "\n")
        file.write("COMPARISON REPORT (before/after)\n")
        file.write("=" * 120 + "\n\n")
        file.write(f"Generated at: {comparison.get('generated_at')}\n")
        file.write(f"Baseline source: {comparison.get('baseline_source')}\n\n")

        file.write("SUMMARY\n")
        file.write("-" * 120 + "\n")
        file.write(f"Comparable repos: {summary.get('comparable', 0)}\n")
        file.write(f"Improved: {summary.get('improved', 0)}\n")
        file.write(f"Declined: {summary.get('declined', 0)}\n")
        file.write(f"Unchanged: {summary.get('unchanged', 0)}\n")
        file.write(f"New: {summary.get('new', 0)}\n")
        file.write(f"Removed: {summary.get('removed', 0)}\n")
        file.write(
            "Average score delta: "
            f"{_to_float(summary.get('avg_delta_score'), 0.0):.2f}\n\n"
        )

        file.write("REPOSITORY DELTAS\n")
        file.write("-" * 120 + "\n")
        if isinstance(repos, list):
            for item in repos:
                if not isinstance(item, dict):
                    continue
                repo = item.get("repo", "unknown")
                status = item.get("status", "unknown")
                file.write(
                    f"- {repo}: status={status}, before={item.get('before_score')}, "
                    f"after={item.get('after_score')}, delta={item.get('delta_score')}\n"
                )
                criterion_deltas = item.get("criterion_deltas", [])
                if isinstance(criterion_deltas, list) and criterion_deltas:
                    for delta in criterion_deltas:
                        if not isinstance(delta, dict):
                            continue
                        file.write(
                            f"    * {delta.get('label', delta.get('criterion'))}: "
                            f"{delta.get('before')} -> {delta.get('after')} "
                            f"(delta={delta.get('delta')})\n"
                        )

        file.write("\n" + "=" * 120 + "\n")

    return json_file, txt_file


def print_comparison_summary(comparison: Dict[str, Any]) -> None:
    """Print a short comparison summary to console."""
    summary = comparison.get("summary", {})
    if not isinstance(summary, dict):
        return

    print("\n" + "=" * 120)
    print("СРАВНЕНИЕ ЗАПУСКОВ / BEFORE vs AFTER")
    print("=" * 120)
    print(
        f"  comparable={summary.get('comparable', 0)} "
        f"| improved={summary.get('improved', 0)} "
        f"| declined={summary.get('declined', 0)} "
        f"| unchanged={summary.get('unchanged', 0)}"
    )
    print(
        f"  new={summary.get('new', 0)} "
        f"| removed={summary.get('removed', 0)} "
        f"| avg delta={_to_float(summary.get('avg_delta_score'), 0.0):.2f}"
    )


def print_results(
    results: List[Dict[str, Any]],
    github_username: Optional[str] = None,
    compare_path: Optional[str] = None,
) -> None:
    """
    Выводит результаты оценки
    Prints evaluation results
    """
    if not results:
        return

    enriched_results = enrich_results_with_insights(results)
    enriched_results.sort(key=lambda x: x["total_score"], reverse=True)

    print("\n" + "=" * 120)
    if github_username:
        print(f"ТОП-20 ПРОЕКТОВ ДЛЯ ПОРТФОЛИО @{github_username}")
        print(f"TOP-20 PROJECTS FOR PORTFOLIO @{github_username}")
    else:
        print("ТОП-20 ПРОЕКТОВ ДЛЯ ПОРТФОЛИО / TOP-20 PROJECTS FOR PORTFOLIO")
    print("(по Product Readiness Score v2.3 / by Product Readiness Score v2.3)")
    print("=" * 120 + "\n")

    for i, result in enumerate(enriched_results[:20], 1):
        repo_info = result["repo"]
        if github_username:
            repo_info = f"github.com/{github_username}/{result['repo']}"
        coverage = _to_float(result.get("data_coverage_percent"), 0.0)
        print(
            f"{i:2}. {repo_info:50} "
            f"{_to_float(result.get('total_score'), 0.0):6.2f}/50 | "
            f"{result.get('category', 'unknown')} | data {coverage:5.1f}%"
        )

    contract_errors = validate_results_contract(enriched_results)
    if contract_errors:
        errors_file = (
            f"portfolio_evaluation_{github_username or 'local'}_contract_errors.txt"
        )
        with open(errors_file, "w", encoding="utf-8") as file:
            file.write("\n".join(contract_errors))
            file.write("\n")
        print(f"\n⚠️  JSON contract validation found {len(contract_errors)} issue(s).")
        print(f"   Details saved to {errors_file}")
    else:
        print("\n✅ JSON contract validation passed.")

    json_file = f"portfolio_evaluation_{github_username or 'local'}.json"
    with open(json_file, "w", encoding="utf-8") as file:
        json.dump(enriched_results, file, indent=2, ensure_ascii=False)

    print(f"\n✅ Полные результаты (JSON) сохранены в {json_file}")
    print(f"   Full results (JSON) saved to {json_file}")

    report_file = save_text_report(enriched_results, github_username)
    if report_file:
        print(f"✅ Полный текстовый отчет сохранен в {report_file}")
        print(f"   Full text report saved to {report_file}")

    print("\n" + "=" * 120)
    print("СТАТИСТИКА / STATISTICS")
    print("=" * 120)

    categories: Dict[str, int] = {}
    for result in enriched_results:
        category = str(result.get("category", "unknown"))
        categories[category] = categories.get(category, 0) + 1

    for cat, count in categories.items():
        percentage = count * 100 // len(enriched_results) if enriched_results else 0
        print(f"  {cat:40} : {count:3} проектов/projects ({percentage}%)")

    quality_counts: Dict[str, int] = {}
    for result in enriched_results:
        status = str(result.get("data_quality_status", "unknown"))
        quality_counts[status] = quality_counts.get(status, 0) + 1
    print("\n  Data quality flags:")
    for status, count in quality_counts.items():
        print(f"  {status:40} : {count:3} repos")

    avg_score = sum(
        _to_float(r.get("total_score"), 0.0) for r in enriched_results
    ) / len(enriched_results)
    avg_coverage = sum(
        _to_float(r.get("data_coverage_percent"), 0.0) for r in enriched_results
    ) / len(enriched_results)
    print(f"\n  Средний балл / Average score: {avg_score:.2f}/50")
    print(f"  Среднее покрытие данных / Average data coverage: {avg_coverage:.2f}%")

    print("\n" + "=" * 120)
    print("РЕКОМЕНДАЦИИ / RECOMMENDATIONS")
    print("=" * 120)

    excellent_repos = [
        r
        for r in enriched_results
        if _to_float(r.get("total_score"), 0.0) >= 30
        and _to_float(r.get("data_coverage_percent"), 0.0) >= 70.0
    ]
    if excellent_repos:
        print(f"\n🌟 Рекомендуемые для портфолио ({len(excellent_repos)} проектов):")
        print(f"   Recommended for portfolio ({len(excellent_repos)} projects):")
        for result in excellent_repos[:5]:
            url = result.get("github_url", result["repo"])
            print(
                f"   • {url} ({_to_float(result.get('total_score'), 0.0):.1f}/50, "
                f"data {_to_float(result.get('data_coverage_percent'), 0.0):.0f}%)"
            )

    quick_fix_matrix = build_portfolio_quick_fixes(enriched_results, limit=8)
    if quick_fix_matrix:
        print("\n  QUICK FIX MATRIX (impact/effort):")
        for idx, row in enumerate(quick_fix_matrix, 1):
            print(
                f"   {idx}. {row['title']} | impact={row['impact']} "
                f"effort={row['effort']} repos={row['repos_affected']}"
            )

    if compare_path:
        try:
            previous_results = load_evaluation_results(compare_path)
            comparison = build_comparison(
                previous_results,
                enriched_results,
                baseline_source=compare_path,
            )
            compare_json, compare_txt = save_comparison_artifacts(
                comparison, github_username=github_username
            )
            print_comparison_summary(comparison)
            print(f"\n✅ Comparison JSON saved to {compare_json}")
            print(f"✅ Comparison text report saved to {compare_txt}")
        except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError) as error:
            print(
                f"\n⚠️  Сравнение пропущено: {error}\n"
                "   Comparison skipped due to invalid baseline file."
            )
