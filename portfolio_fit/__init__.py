"""portfolio_fit package."""

from portfolio_fit.calibration import (
    build_calibration_report,
    load_expert_labels,
    load_model_scores,
)
from portfolio_fit.discovery import (
    discover_python_repos,
    discover_supported_repos,
    evaluate_repos,
    is_python_repo_dir,
    is_supported_repo_dir,
    validate_path,
)
from portfolio_fit.github_fetcher import GitHubRepoFetcher
from portfolio_fit.job_fit import analyze_job_fit, parse_job_description
from portfolio_fit.job_fit_benchmark import run_job_fit_benchmark
from portfolio_fit.recalibration import (
    STACK_PROFILE_CHOICES as RECALIBRATION_STACK_PROFILE_CHOICES,
)
from portfolio_fit.recalibration import (
    build_profile_paths,
    prepare_profile_labels,
    run_profile_recalibration,
    split_profile_labels_by_stack,
)
from portfolio_fit.reporting import print_results, save_text_report
from portfolio_fit.schema_contract import (
    build_portfolio_evaluation_schema,
    validate_results_contract,
)
from portfolio_fit.scoring import (
    STACK_PROFILES,
    CriterionResult,
    EnhancedRepositoryEvaluator,
    EvaluationConstants,
    detect_stack_profile,
)
from portfolio_fit.tuning import suggest_criterion_max_scores

__all__ = [
    "CriterionResult",
    "EvaluationConstants",
    "EnhancedRepositoryEvaluator",
    "STACK_PROFILES",
    "detect_stack_profile",
    "validate_path",
    "is_supported_repo_dir",
    "is_python_repo_dir",
    "discover_supported_repos",
    "discover_python_repos",
    "evaluate_repos",
    "load_expert_labels",
    "load_model_scores",
    "build_calibration_report",
    "suggest_criterion_max_scores",
    "parse_job_description",
    "analyze_job_fit",
    "run_job_fit_benchmark",
    "build_profile_paths",
    "prepare_profile_labels",
    "run_profile_recalibration",
    "split_profile_labels_by_stack",
    "RECALIBRATION_STACK_PROFILE_CHOICES",
    "build_portfolio_evaluation_schema",
    "validate_results_contract",
    "GitHubRepoFetcher",
    "save_text_report",
    "print_results",
]
