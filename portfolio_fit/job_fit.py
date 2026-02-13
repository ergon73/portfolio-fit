import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

SKILL_KEYWORDS: Dict[str, List[str]] = {
    "python": ["python", "fastapi", "flask", "django"],
    "fastapi": ["fastapi", "uvicorn", "pydantic"],
    "django": ["django", "djangorestframework", "drf"],
    "flask": ["flask"],
    "ai_ml": [
        "llm",
        "langchain",
        "openai",
        "transformer",
        "rag",
        "machine learning",
        "pytorch",
        "tensorflow",
    ],
    "nlp": ["nlp", "tokenizer", "embedding", "sentence-transformer"],
    "data_engineering": ["etl", "pipeline", "airflow", "dbt", "spark"],
    "sql": ["sql", "postgres", "sqlite", "mysql", "sqlalchemy"],
    "nosql": ["mongodb", "redis", "cassandra", "pinecone", "chroma"],
    "docker": ["docker", "dockerfile", "docker-compose"],
    "kubernetes": ["kubernetes", "k8s", "helm"],
    "cloud": ["aws", "gcp", "azure", "s3", "ec2", "cloud run"],
    "ci_cd": ["github actions", "cicd", "ci/cd", "gitlab-ci", "jenkins"],
    "testing": ["pytest", "unit test", "integration test", "coverage"],
    "security": ["bandit", "pip-audit", "safety", "owasp", "jwt"],
    "api_design": ["openapi", "swagger", "rest api", "postman"],
    "async": ["asyncio", "asynchronous", "aiohttp", "aiogram"],
    "telegram": ["telegram", "aiogram", "telebot", "pytelegrambotapi"],
    "web_scraping": ["scrapy", "selenium", "playwright", "beautifulsoup"],
    "observability": ["prometheus", "grafana", "loki", "logging", "monitoring"],
}

DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    "fintech": ["fintech", "payments", "bank", "invoice", "billing"],
    "healthtech": ["health", "medical", "blood pressure", "patient"],
    "ecommerce": ["ecommerce", "catalog", "shop", "marketplace", "order"],
    "edtech": ["education", "course", "school", "learning"],
    "devtools": ["developer tools", "cli", "automation", "tooling"],
}

SENIORITY_KEYWORDS: Dict[str, List[str]] = {
    "junior": ["junior", "entry level", "intern"],
    "middle": ["middle", "mid-level", "mid level"],
    "senior": ["senior", "lead", "staff", "principal"],
}

SKILL_PLAYBOOK: Dict[str, Dict[str, Any]] = {
    "fastapi": {
        "action": "Собрать production-ready FastAPI сервис с OpenAPI, валидацией и тестами.",
        "effort": "medium",
    },
    "django": {
        "action": "Показать Django-проект с auth, ORM, миграциями и тестами.",
        "effort": "medium",
    },
    "ai_ml": {
        "action": "Добавить end-to-end AI use-case (RAG/LLM) с измеримыми метриками.",
        "effort": "high",
    },
    "docker": {
        "action": "Добавить Dockerfile + compose + healthcheck + инструкции запуска.",
        "effort": "low",
    },
    "ci_cd": {
        "action": "Настроить CI (lint/test/coverage) и CD workflow для релизов.",
        "effort": "low",
    },
    "testing": {
        "action": "Повысить покрытие тестами ключевых сценариев и добавить regression tests.",
        "effort": "medium",
    },
    "security": {
        "action": "Подключить pip-audit/bandit/Dependabot и зафиксировать security policy.",
        "effort": "medium",
    },
    "sql": {
        "action": "Показать практику SQL/ORM: индексы, миграции, оптимизация запросов.",
        "effort": "medium",
    },
    "cloud": {
        "action": "Задеплоить сервис в облако (AWS/GCP/Azure) и приложить IaC/инструкции.",
        "effort": "high",
    },
    "kubernetes": {
        "action": "Добавить k8s manifests/Helm для разворачивания основного сервиса.",
        "effort": "high",
    },
}

SKILL_EVIDENCE_STRONG = 2.2
MUST_MATCH_THRESHOLD = 0.55
NICE_MATCH_THRESHOLD = 0.45

MUST_REQUIREMENT_MARKERS = ["must have", "required", "обязательно", "требуется"]
NICE_REQUIREMENT_MARKERS = ["nice to have", "будет плюсом", "plus"]
REQUIREMENT_STOPWORDS = {
    "experience",
    "with",
    "in",
    "and",
    "or",
    "knowledge",
    "strong",
    "good",
    "understanding",
    "the",
    "of",
    "using",
}

REQUIREMENT_ALIAS: Dict[str, str] = {
    "ci/cd": "ci_cd",
    "ci cd": "ci_cd",
    "ci": "ci_cd",
    "cd": "ci_cd",
    "api design": "api_design",
    "security scanning": "security",
    "data engineering": "data_engineering",
    "ai": "ai_ml",
    "ml": "ai_ml",
    "llm": "ai_ml",
    "machine learning": "ai_ml",
}


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _keyword_in_text(keyword: str, normalized_text: str) -> bool:
    escaped = re.escape(keyword.lower())
    if re.search(r"[a-z0-9_]", keyword) and " " not in keyword and "/" not in keyword:
        pattern = rf"(?<![a-z0-9_]){escaped}(?![a-z0-9_])"
        return re.search(pattern, normalized_text) is not None
    return escaped in normalized_text


def detect_skills_in_text(text: str) -> Set[str]:
    normalized = _normalize_text(text)
    detected: Set[str] = set()
    for skill, keywords in SKILL_KEYWORDS.items():
        if any(_keyword_in_text(keyword, normalized) for keyword in keywords):
            detected.add(skill)
    return detected


def detect_domains_in_text(text: str) -> Set[str]:
    normalized = _normalize_text(text)
    domains: Set[str] = set()
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if any(_keyword_in_text(keyword, normalized) for keyword in keywords):
            domains.add(domain)
    return domains


def detect_seniority(text: str) -> Optional[str]:
    normalized = _normalize_text(text)
    for level, keywords in SENIORITY_KEYWORDS.items():
        if any(_keyword_in_text(keyword, normalized) for keyword in keywords):
            return level
    return None


def parse_job_description(jd_text: str) -> Dict[str, Any]:
    normalized = _normalize_text(jd_text)
    all_skills = detect_skills_in_text(normalized)

    must_have: Set[str] = set()
    nice_to_have: Set[str] = set()
    for skill, keywords in SKILL_KEYWORDS.items():
        for keyword in keywords:
            escaped = re.escape(keyword)
            must_patterns = [
                rf"(must|required|обязательно|требуется).{{0,40}}{escaped}",
                rf"{escaped}.{{0,40}}(must|required|обязательно|требуется)",
            ]
            nice_patterns = [
                rf"(nice to have|plus|будет плюсом).{{0,40}}{escaped}",
                rf"{escaped}.{{0,40}}(nice to have|plus|будет плюсом)",
            ]
            if any(re.search(pattern, normalized) for pattern in must_patterns):
                must_have.add(skill)
            if any(re.search(pattern, normalized) for pattern in nice_patterns):
                nice_to_have.add(skill)

    raw_must_terms = _extract_requirement_terms(normalized, MUST_REQUIREMENT_MARKERS)
    raw_nice_terms = _extract_requirement_terms(normalized, NICE_REQUIREMENT_MARKERS)

    out_of_taxonomy_must: Set[str] = set()
    out_of_taxonomy_nice: Set[str] = set()

    for term in raw_must_terms:
        mapped = _map_requirement_term_to_skills(term)
        if mapped:
            must_have.update(mapped)
        elif term:
            out_of_taxonomy_must.add(term)

    for term in raw_nice_terms:
        mapped = _map_requirement_term_to_skills(term)
        if mapped:
            nice_to_have.update(mapped)
        elif term:
            out_of_taxonomy_nice.add(term)

    if not must_have and not out_of_taxonomy_must:
        must_have = set(all_skills)
    nice_to_have.update(all_skills.difference(must_have))

    return {
        "must_have": sorted(must_have),
        "nice_to_have": sorted(nice_to_have),
        "out_of_taxonomy_must_have": sorted(out_of_taxonomy_must),
        "out_of_taxonomy_nice_to_have": sorted(out_of_taxonomy_nice),
        "all_detected_skills": sorted(all_skills),
        "domain_signals": sorted(detect_domains_in_text(normalized)),
        "seniority": detect_seniority(normalized),
    }


def _read_repo_text(repo_path: Path) -> str:
    chunks: List[str] = []

    # Repo and file names are also useful signals.
    chunks.append(repo_path.name)
    for file_path in (
        repo_path / "README.md",
        repo_path / "pyproject.toml",
        repo_path / "requirements.txt",
        repo_path / "Dockerfile",
        repo_path / ".github" / "workflows" / "ci.yml",
        repo_path / ".github" / "workflows" / "main.yml",
    ):
        if file_path.exists() and file_path.is_file():
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            chunks.append(content[:20000])

    return "\n".join(chunks)


def extract_skills_from_repo_result(result: Dict[str, Any]) -> List[str]:
    repo_path_raw = result.get("path")
    text = str(result.get("repo", ""))
    if repo_path_raw:
        repo_path = Path(str(repo_path_raw))
        if repo_path.exists() and repo_path.is_dir():
            text = text + "\n" + _read_repo_text(repo_path)

    skills = detect_skills_in_text(text)

    if _to_float(result.get("cicd"), 0.0) > 0:
        skills.add("ci_cd")
    if _to_float(result.get("docker"), 0.0) > 0:
        skills.add("docker")
    if _to_float(result.get("test_coverage"), 0.0) > 0:
        skills.add("testing")
    if _to_float(result.get("vulnerabilities"), 0.0) > 0:
        skills.add("security")

    return sorted(skills)


def build_portfolio_skill_index(
    evaluation_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    repo_skills: Dict[str, List[str]] = {}
    counter: Counter = Counter()
    skill_weighted_evidence: Dict[str, float] = {}
    skill_repo_weights: Dict[str, List[Tuple[str, float]]] = {}

    for result in evaluation_results:
        repo = str(result.get("repo", ""))
        if not repo:
            continue
        skills = extract_skills_from_repo_result(result)
        repo_skills[repo] = skills
        counter.update(skills)
        repo_weight = _repo_evidence_weight(result)
        for skill in skills:
            skill_weighted_evidence[skill] = (
                skill_weighted_evidence.get(skill, 0.0) + repo_weight
            )
            entries = skill_repo_weights.setdefault(skill, [])
            entries.append((repo, repo_weight))

    skill_confidence = {
        skill: round(min(1.0, evidence / SKILL_EVIDENCE_STRONG), 3)
        for skill, evidence in skill_weighted_evidence.items()
    }
    top_repo_signals: Dict[str, List[Dict[str, Any]]] = {}
    for skill, entries in skill_repo_weights.items():
        ranked = sorted(entries, key=lambda item: item[1], reverse=True)[:5]
        top_repo_signals[skill] = [
            {"repo": repo, "weight": round(weight, 3)} for repo, weight in ranked
        ]

    return {
        "repo_skills": repo_skills,
        "skill_frequency": dict(counter),
        "skill_weighted_evidence": {
            key: round(value, 3) for key, value in skill_weighted_evidence.items()
        },
        "skill_confidence": skill_confidence,
        "skill_top_repo_signals": top_repo_signals,
        "portfolio_skills": sorted(
            skill
            for skill, confidence in skill_confidence.items()
            if confidence >= NICE_MATCH_THRESHOLD
        ),
    }


def _fit_category(score_percent: float) -> str:
    if score_percent >= 80:
        return "strong_fit"
    if score_percent >= 60:
        return "moderate_fit"
    if score_percent >= 40:
        return "weak_fit"
    return "low_fit"


def _quality_factor(status: str) -> float:
    normalized = status.lower()
    if normalized == "green":
        return 1.0
    if normalized == "yellow":
        return 0.8
    if normalized == "red":
        return 0.55
    return 0.7


def _average_criteria_confidence(result: Dict[str, Any]) -> float:
    criteria_meta = result.get("criteria_meta", {})
    if not isinstance(criteria_meta, dict):
        return 0.7

    values: List[float] = []
    for meta in criteria_meta.values():
        if not isinstance(meta, dict):
            continue
        status = str(meta.get("status", "known"))
        if status == "unknown":
            continue
        confidence = _to_float(meta.get("confidence"), -1.0)
        if confidence >= 0:
            values.append(max(0.0, min(1.0, confidence)))
    if not values:
        return 0.7
    return sum(values) / len(values)


def _repo_evidence_weight(result: Dict[str, Any]) -> float:
    score_ratio = max(0.0, min(1.0, _to_float(result.get("total_score"), 0.0) / 50.0))
    coverage_ratio = max(
        0.0, min(1.0, _to_float(result.get("data_coverage_percent"), 0.0) / 100.0)
    )
    confidence_ratio = _average_criteria_confidence(result)
    quality = _quality_factor(str(result.get("data_quality_status", "yellow")))

    base = score_ratio * 0.45 + coverage_ratio * 0.35 + confidence_ratio * 0.20
    clamped = max(0.1, min(1.0, base))
    return clamped * quality


def _extract_requirement_terms(normalized_text: str, markers: List[str]) -> List[str]:
    terms: List[str] = []
    for marker in markers:
        pattern = re.compile(rf"{re.escape(marker)}\s*:?\s*([^\n\.;]+)")
        for match in pattern.finditer(normalized_text):
            clause = match.group(1).strip()
            if not clause:
                continue
            normalized_clause = (
                clause.replace(" and ", ",").replace(" или ", ",").replace("&", ",")
            )
            for token in normalized_clause.split(","):
                cleaned = re.sub(r"[^a-z0-9+#\-\s]", " ", token).strip()
                cleaned = re.sub(r"\s+", " ", cleaned)
                if not cleaned or cleaned in REQUIREMENT_STOPWORDS:
                    continue
                if len(cleaned) < 2:
                    continue
                if all(part in REQUIREMENT_STOPWORDS for part in cleaned.split()):
                    continue
                terms.append(cleaned)
    # deduplicate preserving order
    unique_terms: List[str] = []
    seen: Set[str] = set()
    for item in terms:
        if item not in seen:
            unique_terms.append(item)
            seen.add(item)
    return unique_terms


def _display_skill_name(skill_id: str) -> str:
    if skill_id.startswith("other::"):
        return skill_id.split("other::", 1)[1]
    return skill_id


def _map_requirement_term_to_skills(term: str) -> Set[str]:
    normalized_term = _normalize_text(term)
    if not normalized_term:
        return set()

    direct = REQUIREMENT_ALIAS.get(normalized_term)
    if direct:
        return {direct}

    detected = detect_skills_in_text(normalized_term)
    if detected:
        return detected

    # Attempt to map multi-word term by parts if direct detection failed.
    resolved: Set[str] = set()
    for chunk in normalized_term.split():
        alias = REQUIREMENT_ALIAS.get(chunk)
        if alias:
            resolved.add(alias)
            continue
        resolved.update(detect_skills_in_text(chunk))
    return resolved


def _build_roadmap(
    must_missing: List[str], nice_missing: List[str]
) -> Dict[str, List[Dict[str, str]]]:
    def to_actions(skills: List[str]) -> List[Dict[str, str]]:
        actions: List[Dict[str, str]] = []
        for skill in skills:
            playbook = SKILL_PLAYBOOK.get(skill)
            if playbook:
                actions.append(
                    {
                        "skill": skill,
                        "action": str(playbook["action"]),
                        "effort": str(playbook["effort"]),
                    }
                )
            else:
                actions.append(
                    {
                        "skill": skill,
                        "action": f"Добавить репозиторий/фичу, демонстрирующую {skill}.",
                        "effort": "medium",
                    }
                )
        return actions

    must_actions = to_actions(must_missing)
    nice_actions = to_actions(nice_missing)

    roadmap_2 = must_actions[:3]
    roadmap_4 = must_actions[3:6] + nice_actions[:2]
    roadmap_8 = must_actions[6:] + nice_actions[2:6]
    return {
        "2_weeks": roadmap_2,
        "4_weeks": roadmap_4,
        "8_weeks": roadmap_8,
    }


def analyze_job_fit(
    evaluation_results: List[Dict[str, Any]], jd_text: str
) -> Dict[str, Any]:
    jd = parse_job_description(jd_text)
    portfolio_index = build_portfolio_skill_index(evaluation_results)
    confidence_map_raw = portfolio_index.get("skill_confidence", {})
    confidence_map = confidence_map_raw if isinstance(confidence_map_raw, dict) else {}

    must_have = set(jd["must_have"])
    nice_to_have = set(jd["nice_to_have"])
    out_tax_must = {
        f"other::{term}" for term in jd.get("out_of_taxonomy_must_have", [])
    }
    out_tax_nice = {
        f"other::{term}" for term in jd.get("out_of_taxonomy_nice_to_have", [])
    }
    must_requirements = must_have.union(out_tax_must)
    nice_requirements = nice_to_have.union(out_tax_nice)

    must_confidence: Dict[str, float] = {
        skill: _to_float(confidence_map.get(skill), 0.0) for skill in must_requirements
    }
    nice_confidence: Dict[str, float] = {
        skill: _to_float(confidence_map.get(skill), 0.0) for skill in nice_requirements
    }

    must_matched = sorted(
        _display_skill_name(skill)
        for skill, confidence in must_confidence.items()
        if confidence >= MUST_MATCH_THRESHOLD
    )
    must_missing = sorted(
        _display_skill_name(skill)
        for skill, confidence in must_confidence.items()
        if confidence < MUST_MATCH_THRESHOLD
    )
    must_partial = sorted(
        _display_skill_name(skill)
        for skill, confidence in must_confidence.items()
        if 0.0 < confidence < MUST_MATCH_THRESHOLD
    )

    nice_matched = sorted(
        _display_skill_name(skill)
        for skill, confidence in nice_confidence.items()
        if confidence >= NICE_MATCH_THRESHOLD
    )
    nice_missing = sorted(
        _display_skill_name(skill)
        for skill, confidence in nice_confidence.items()
        if confidence < NICE_MATCH_THRESHOLD
    )
    nice_partial = sorted(
        _display_skill_name(skill)
        for skill, confidence in nice_confidence.items()
        if 0.0 < confidence < NICE_MATCH_THRESHOLD
    )

    must_coverage = (
        sum(must_confidence.values()) / len(must_requirements)
        if must_requirements
        else 1.0
    )
    nice_coverage = (
        sum(nice_confidence.values()) / len(nice_requirements)
        if nice_requirements
        else 1.0
    )
    fit_score_percent = round((must_coverage * 0.8 + nice_coverage * 0.2) * 100, 2)

    gaps = [
        {
            "skill": skill,
            "priority": "must_have",
            "missing": True,
            "evidence_confidence": round(
                must_confidence.get(f"other::{skill}", must_confidence.get(skill, 0.0)),
                3,
            ),
        }
        for skill in must_missing
    ] + [
        {
            "skill": skill,
            "priority": "nice_to_have",
            "missing": True,
            "evidence_confidence": round(
                nice_confidence.get(f"other::{skill}", nice_confidence.get(skill, 0.0)),
                3,
            ),
        }
        for skill in nice_missing
    ]

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "fit_score_percent": fit_score_percent,
        "fit_category": _fit_category(fit_score_percent),
        "must_have_coverage_percent": round(must_coverage * 100, 2),
        "nice_to_have_coverage_percent": round(nice_coverage * 100, 2),
        "jd": jd,
        "portfolio": portfolio_index,
        "matching": {
            "must_have_matched": must_matched,
            "must_have_missing": must_missing,
            "must_have_partial": must_partial,
            "nice_to_have_matched": nice_matched,
            "nice_to_have_missing": nice_missing,
            "nice_to_have_partial": nice_partial,
            "must_have_confidence": {
                _display_skill_name(key): round(value, 3)
                for key, value in sorted(must_confidence.items())
            },
            "nice_to_have_confidence": {
                _display_skill_name(key): round(value, 3)
                for key, value in sorted(nice_confidence.items())
            },
        },
        "gaps": gaps,
        "roadmap": _build_roadmap(must_missing, nice_missing),
    }


def save_job_fit_report(report: Dict[str, Any], output_prefix: str) -> Tuple[str, str]:
    json_path = f"{output_prefix}.json"
    txt_path = f"{output_prefix}.txt"

    with open(json_path, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=2, ensure_ascii=False)

    matching = report.get("matching", {})
    roadmap = report.get("roadmap", {})
    with open(txt_path, "w", encoding="utf-8") as file:
        file.write("=" * 100 + "\n")
        file.write("JOB FIT REPORT\n")
        file.write("=" * 100 + "\n\n")
        file.write(f"Generated at: {report.get('generated_at')}\n")
        file.write(f"Fit score: {report.get('fit_score_percent')}%\n")
        file.write(f"Fit category: {report.get('fit_category')}\n")
        file.write(f"Must-have coverage: {report.get('must_have_coverage_percent')}%\n")
        file.write(
            f"Nice-to-have coverage: {report.get('nice_to_have_coverage_percent')}%\n\n"
        )

        file.write("Missing must-have skills:\n")
        for skill in matching.get("must_have_missing", []):
            file.write(f"  - {skill}\n")
        partial = matching.get("must_have_partial", [])
        if isinstance(partial, list) and partial:
            file.write("\nPartially covered must-have skills (low evidence):\n")
            for skill in partial:
                file.write(f"  - {skill}\n")

        file.write("\nRoadmap (2/4/8 weeks):\n")
        for horizon in ("2_weeks", "4_weeks", "8_weeks"):
            file.write(f"\n{horizon}:\n")
            for item in roadmap.get(horizon, []):
                if isinstance(item, dict):
                    file.write(
                        f"  - [{item.get('skill')}] {item.get('action')} "
                        f"(effort={item.get('effort')})\n"
                    )

    return json_path, txt_path
