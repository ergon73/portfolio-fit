import json
from pathlib import Path
from typing import Any, Dict, List, Sequence, cast

from portfolio_fit.scoring import (
    NON_AUTO_STACK_PROFILES,
    EvaluationConstants,
)

CRITERION_KEYS = list(EvaluationConstants.CRITERION_MAX_SCORES.keys())
BLOCK_KEYS = list(EvaluationConstants.BLOCK_MAX_SCORES.keys())
STANDALONE_SIGNAL_KEYS = (
    "frontend_quality",
    "data_layer_quality",
    "api_contract_maturity",
    "fullstack_maturity",
)
DOMAIN_ROADMAP_KEYS = ("backend", "frontend", "data", "devops")

RESULT_REQUIRED_FIELDS = (
    [
        "repo",
        "path",
        "stack_profile",
        "total_score",
        "max_score",
        "raw_max_score",
        "known_score",
        "known_max_score",
        "data_coverage_percent",
        "data_quality_status",
        "data_quality_warnings",
        "category",
        *STANDALONE_SIGNAL_KEYS,
        *(f"{signal_key}_meta" for signal_key in STANDALONE_SIGNAL_KEYS),
        "criteria_meta",
        "blocks_meta",
        "criteria_explainability",
        "recommendations",
        "quick_fixes",
        "domain_roadmaps",
    ]
    + CRITERION_KEYS
    + BLOCK_KEYS
)

CRITERIA_META_REQUIRED_FIELDS = ["max_score", "status", "method", "confidence", "note"]
BLOCK_META_REQUIRED_FIELDS = [
    "score",
    "known_score",
    "known_max",
    "max_score",
    "data_coverage_percent",
]


def _is_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    return isinstance(value, (int, float))


def _repo_label(result: Dict[str, Any], index: int) -> str:
    repo = result.get("repo")
    if isinstance(repo, str) and repo:
        return repo
    return f"index={index}"


def build_portfolio_evaluation_schema() -> Dict[str, Any]:
    criterion_meta_properties = {
        criterion: {
            "type": "object",
            "required": CRITERIA_META_REQUIRED_FIELDS,
            "properties": {
                "max_score": {"type": "number", "minimum": 0},
                "status": {
                    "type": "string",
                    "enum": ["known", "unknown", "not_applicable"],
                },
                "method": {"type": "string", "enum": ["measured", "heuristic"]},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "note": {"type": "string"},
            },
            "additionalProperties": True,
        }
        for criterion in CRITERION_KEYS
    }

    blocks_meta_properties = {
        block: {
            "type": "object",
            "required": BLOCK_META_REQUIRED_FIELDS,
            "properties": {
                "score": {"type": ["number", "null"]},
                "known_score": {"type": "number"},
                "known_max": {"type": "number"},
                "max_score": {"type": "number"},
                "data_coverage_percent": {"type": "number"},
            },
            "additionalProperties": True,
        }
        for block in BLOCK_KEYS
    }

    criterion_score_properties = {
        criterion: {"type": ["number", "null"]} for criterion in CRITERION_KEYS
    }
    block_score_properties = {
        block: {"type": ["number", "null"]} for block in BLOCK_KEYS
    }
    standalone_score_properties = {
        signal_key: {
            "type": ["number", "null"],
            "description": f"Standalone full-stack signal: {signal_key}",
        }
        for signal_key in STANDALONE_SIGNAL_KEYS
    }
    standalone_meta_properties = {
        f"{signal_key}_meta": {
            "type": "object",
            "required": CRITERIA_META_REQUIRED_FIELDS + ["score"],
            "properties": {
                "score": {"type": ["number", "null"]},
                "max_score": {"type": "number", "minimum": 0},
                "status": {
                    "type": "string",
                    "enum": ["known", "unknown", "not_applicable"],
                },
                "method": {"type": "string", "enum": ["measured", "heuristic"]},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "note": {"type": "string"},
            },
            "additionalProperties": True,
        }
        for signal_key in STANDALONE_SIGNAL_KEYS
    }

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://ergon73.github.io/portfolio-fit/schemas/portfolio_evaluation.schema.json",
        "title": "Portfolio evaluation result list (multi-stack)",
        "description": (
            "Evaluation contract for Python/JS/TS/HTML/CSS oriented repositories "
            "with stack-aware applicability and standalone full-stack signals."
        ),
        "type": "array",
        "items": {
            "type": "object",
            "required": RESULT_REQUIRED_FIELDS,
            "properties": {
                "repo": {"type": "string", "minLength": 1},
                "path": {"type": "string", "minLength": 1},
                "stack_profile": {
                    "type": "string",
                    "enum": list(NON_AUTO_STACK_PROFILES),
                    "description": "Auto-detected or forced stack profile",
                },
                "total_score": {"type": "number", "minimum": 0, "maximum": 50},
                "max_score": {"type": "number", "minimum": 0},
                "raw_max_score": {"type": "number", "minimum": 0},
                "known_score": {"type": "number", "minimum": 0},
                "known_max_score": {"type": "number", "minimum": 0},
                "data_coverage_percent": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 100,
                },
                "data_quality_status": {
                    "type": "string",
                    "enum": ["green", "yellow", "red"],
                },
                "data_quality_warnings": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "category": {"type": "string", "minLength": 1},
                "criteria_meta": {
                    "type": "object",
                    "required": CRITERION_KEYS,
                    "properties": criterion_meta_properties,
                    "additionalProperties": True,
                },
                "blocks_meta": {
                    "type": "object",
                    "required": BLOCK_KEYS,
                    "properties": blocks_meta_properties,
                    "additionalProperties": True,
                },
                "criteria_explainability": {
                    "type": "object",
                    "required": CRITERION_KEYS + list(STANDALONE_SIGNAL_KEYS),
                    "additionalProperties": True,
                },
                "recommendations": {"type": "array"},
                "quick_fixes": {"type": "array"},
                "domain_roadmaps": {
                    "type": "object",
                    "required": list(DOMAIN_ROADMAP_KEYS),
                    "properties": {
                        domain: {"type": "array", "items": {"type": "object"}}
                        for domain in DOMAIN_ROADMAP_KEYS
                    },
                    "additionalProperties": True,
                },
                **criterion_score_properties,
                **block_score_properties,
                **standalone_score_properties,
                **standalone_meta_properties,
            },
            "additionalProperties": True,
        },
    }


def save_portfolio_evaluation_schema(output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    schema = build_portfolio_evaluation_schema()
    output_path.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    return output_path


def validate_result_contract(result: Dict[str, Any], index: int = 0) -> List[str]:
    errors: List[str] = []
    repo_label = _repo_label(result, index)

    for field in RESULT_REQUIRED_FIELDS:
        if field not in result:
            errors.append(f"{repo_label}: missing required field '{field}'")

    for field in ("repo", "path", "category"):
        value = result.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{repo_label}: field '{field}' must be a non-empty string")

    stack_profile = result.get("stack_profile")
    if stack_profile not in set(NON_AUTO_STACK_PROFILES):
        errors.append(
            f"{repo_label}: field 'stack_profile' must be one of {', '.join(NON_AUTO_STACK_PROFILES)}"
        )

    for field in (
        "total_score",
        "max_score",
        "raw_max_score",
        "known_score",
        "known_max_score",
        "data_coverage_percent",
    ):
        if not _is_number(result.get(field)):
            errors.append(f"{repo_label}: field '{field}' must be a number")

    if _is_number(result.get("data_coverage_percent")):
        coverage_value = float(cast(float, result["data_coverage_percent"]))
        if not 0.0 <= coverage_value <= 100.0:
            errors.append(
                f"{repo_label}: field 'data_coverage_percent' must be in [0, 100]"
            )

    if _is_number(result.get("total_score")) and _is_number(result.get("max_score")):
        total_score_value = float(cast(float, result["total_score"]))
        max_score_value = float(cast(float, result["max_score"]))
        if total_score_value > max_score_value + 1e-6:
            errors.append(
                f"{repo_label}: field 'total_score' cannot exceed 'max_score'"
            )

    if _is_number(result.get("known_score")) and _is_number(
        result.get("known_max_score")
    ):
        known_score_value = float(cast(float, result["known_score"]))
        known_max_score_value = float(cast(float, result["known_max_score"]))
        if known_score_value > known_max_score_value + 1e-6:
            errors.append(
                f"{repo_label}: field 'known_score' cannot exceed 'known_max_score'"
            )

    for signal_key in STANDALONE_SIGNAL_KEYS:
        signal_score = result.get(signal_key)
        if signal_score is not None and not _is_number(signal_score):
            errors.append(
                f"{repo_label}: field '{signal_key}' must be a number or null"
            )

    quality_status = result.get("data_quality_status")
    if quality_status not in {"green", "yellow", "red"}:
        errors.append(
            f"{repo_label}: field 'data_quality_status' must be one of green/yellow/red"
        )

    warnings = result.get("data_quality_warnings")
    if not isinstance(warnings, list):
        errors.append(f"{repo_label}: field 'data_quality_warnings' must be a list")
    elif not all(isinstance(item, str) for item in warnings):
        errors.append(
            f"{repo_label}: field 'data_quality_warnings' must contain only strings"
        )

    for field in ("recommendations", "quick_fixes"):
        if not isinstance(result.get(field), list):
            errors.append(f"{repo_label}: field '{field}' must be a list")

    domain_roadmaps = result.get("domain_roadmaps")
    if not isinstance(domain_roadmaps, dict):
        errors.append(f"{repo_label}: field 'domain_roadmaps' must be an object")
    else:
        for domain in DOMAIN_ROADMAP_KEYS:
            items = domain_roadmaps.get(domain)
            if not isinstance(items, list):
                errors.append(
                    f"{repo_label}: domain_roadmaps['{domain}'] must be a list"
                )

    for signal_key in STANDALONE_SIGNAL_KEYS:
        meta_key = f"{signal_key}_meta"
        signal_meta = result.get(meta_key)
        if not isinstance(signal_meta, dict):
            errors.append(f"{repo_label}: field '{meta_key}' must be an object")
            continue

        for required_field in CRITERIA_META_REQUIRED_FIELDS + ["score"]:
            if required_field not in signal_meta:
                errors.append(f"{repo_label}: {meta_key} missing '{required_field}'")

        signal_meta_score = signal_meta.get("score")
        if signal_meta_score is not None and not _is_number(signal_meta_score):
            errors.append(f"{repo_label}: {meta_key}.score must be number or null")
        if not _is_number(signal_meta.get("max_score")):
            errors.append(f"{repo_label}: {meta_key}.max_score must be number")

        signal_status = signal_meta.get("status")
        if signal_status not in {"known", "unknown", "not_applicable"}:
            errors.append(
                f"{repo_label}: {meta_key}.status must be known/unknown/not_applicable"
            )

        signal_method = signal_meta.get("method")
        if signal_method not in {"measured", "heuristic"}:
            errors.append(f"{repo_label}: {meta_key}.method must be measured/heuristic")

        signal_confidence = signal_meta.get("confidence")
        if not _is_number(signal_confidence):
            errors.append(f"{repo_label}: {meta_key}.confidence must be number")
        else:
            signal_confidence_value = float(cast(float, signal_confidence))
            if not 0.0 <= signal_confidence_value <= 1.0:
                errors.append(f"{repo_label}: {meta_key}.confidence must be in [0, 1]")

        if not isinstance(signal_meta.get("note"), str):
            errors.append(f"{repo_label}: {meta_key}.note must be string")

    for criterion in CRITERION_KEYS:
        criterion_score = result.get(criterion)
        if criterion_score is not None and not _is_number(criterion_score):
            errors.append(
                f"{repo_label}: criterion '{criterion}' must be a number or null"
            )

    criteria_meta = result.get("criteria_meta")
    if not isinstance(criteria_meta, dict):
        errors.append(f"{repo_label}: field 'criteria_meta' must be an object")
    else:
        for criterion in CRITERION_KEYS:
            meta = criteria_meta.get(criterion)
            if not isinstance(meta, dict):
                errors.append(
                    f"{repo_label}: criteria_meta['{criterion}'] must be an object"
                )
                continue

            for required_field in CRITERIA_META_REQUIRED_FIELDS:
                if required_field not in meta:
                    errors.append(
                        f"{repo_label}: criteria_meta['{criterion}'] missing '{required_field}'"
                    )

            if not _is_number(meta.get("max_score")):
                errors.append(
                    f"{repo_label}: criteria_meta['{criterion}'].max_score must be number"
                )

            status = meta.get("status")
            if status not in {"known", "unknown", "not_applicable"}:
                errors.append(
                    f"{repo_label}: criteria_meta['{criterion}'].status must be known/unknown/not_applicable"
                )

            method = meta.get("method")
            if method not in {"measured", "heuristic"}:
                errors.append(
                    f"{repo_label}: criteria_meta['{criterion}'].method must be measured/heuristic"
                )

            confidence = meta.get("confidence")
            if not _is_number(confidence):
                errors.append(
                    f"{repo_label}: criteria_meta['{criterion}'].confidence must be number"
                )
            else:
                confidence_value = float(cast(float, confidence))
                if not 0.0 <= confidence_value <= 1.0:
                    errors.append(
                        f"{repo_label}: criteria_meta['{criterion}'].confidence must be in [0, 1]"
                    )

            if not isinstance(meta.get("note"), str):
                errors.append(
                    f"{repo_label}: criteria_meta['{criterion}'].note must be string"
                )

    blocks_meta = result.get("blocks_meta")
    if not isinstance(blocks_meta, dict):
        errors.append(f"{repo_label}: field 'blocks_meta' must be an object")
    else:
        for block in BLOCK_KEYS:
            block_meta = blocks_meta.get(block)
            if not isinstance(block_meta, dict):
                errors.append(f"{repo_label}: blocks_meta['{block}'] must be an object")
                continue
            for required_field in BLOCK_META_REQUIRED_FIELDS:
                if required_field not in block_meta:
                    errors.append(
                        f"{repo_label}: blocks_meta['{block}'] missing '{required_field}'"
                    )

            for numeric_field in (
                "known_score",
                "known_max",
                "max_score",
                "data_coverage_percent",
            ):
                if not _is_number(block_meta.get(numeric_field)):
                    errors.append(
                        f"{repo_label}: blocks_meta['{block}'].{numeric_field} must be number"
                    )
            score = block_meta.get("score")
            if score is not None and not _is_number(score):
                errors.append(
                    f"{repo_label}: blocks_meta['{block}'].score must be number or null"
                )

            block_coverage = block_meta.get("data_coverage_percent")
            if _is_number(block_coverage):
                block_coverage_value = float(cast(float, block_coverage))
                if not 0.0 <= block_coverage_value <= 100.0:
                    errors.append(
                        f"{repo_label}: blocks_meta['{block}'].data_coverage_percent must be in [0, 100]"
                    )

            block_score = result.get(block)
            if block_score is not None and not _is_number(block_score):
                errors.append(f"{repo_label}: field '{block}' must be a number or null")

    explainability = result.get("criteria_explainability")
    if not isinstance(explainability, dict):
        errors.append(
            f"{repo_label}: field 'criteria_explainability' must be an object"
        )
    else:
        for criterion in CRITERION_KEYS:
            if criterion not in explainability:
                errors.append(
                    f"{repo_label}: criteria_explainability missing '{criterion}'"
                )
        for signal_key in STANDALONE_SIGNAL_KEYS:
            if signal_key not in explainability:
                errors.append(
                    f"{repo_label}: criteria_explainability missing '{signal_key}'"
                )

    return errors


def validate_results_contract(results: Sequence[Dict[str, Any]]) -> List[str]:
    if not isinstance(results, Sequence) or isinstance(results, (str, bytes)):
        return ["results payload must be a list of objects"]

    errors: List[str] = []
    for index, item in enumerate(results):
        if not isinstance(item, dict):
            errors.append(f"index={index}: result item must be an object")
            continue
        errors.extend(validate_result_contract(item, index=index))
    return errors
