#!/usr/bin/env python3
"""
Compatibility entrypoint for portfolio-fit CLI.
Legacy imports from this file are preserved via re-exports.
"""

from portfolio_fit import (
    CriterionResult,
    EnhancedRepositoryEvaluator,
    EvaluationConstants,
    GitHubRepoFetcher,
    discover_python_repos,
    evaluate_repos,
    is_python_repo_dir,
    print_results,
    save_text_report,
    validate_path,
)
from portfolio_fit.cli import main, parse_arguments

__all__ = [
    "CriterionResult",
    "EvaluationConstants",
    "EnhancedRepositoryEvaluator",
    "GitHubRepoFetcher",
    "validate_path",
    "is_python_repo_dir",
    "discover_python_repos",
    "evaluate_repos",
    "save_text_report",
    "print_results",
    "parse_arguments",
    "main",
]


if __name__ == "__main__":
    main()
