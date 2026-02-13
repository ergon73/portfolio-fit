# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Added
- Golden-set calibration flow:
  - `prepare_golden_set.py`
  - `calibrate_scoring_model.py`
  - `tune_scoring_config.py`
- Job-fit analysis pipeline:
  - `job_fit_analysis.py`
  - `run_job_fit_benchmark.py`
  - `portfolio_fit/job_fit.py`
  - `portfolio_fit/job_fit_benchmark.py`
- Data quality warnings and portfolio quick-fix matrix in reports.
- JSON contract tooling:
  - `portfolio_fit/schema_contract.py`
  - `generate_portfolio_schema.py`
  - `validate_evaluation_contract.py`
  - `schemas/portfolio_evaluation.schema.json`
- Profile-based recalibration workflow:
  - `portfolio_fit/recalibration.py`
  - `recalibrate_profile.py`
  - `docs/recalibration-profiles.md`
- Release package drafts:
  - `docs/releases/v3.0.0-release-notes.md`
  - `docs/releases/v3.0.0-publish-checklist.md`

### Changed
- Scoring engine extracts measured evidence when available and marks unknown data explicitly.
- Reporting now validates JSON output against a formal contract before writing artifacts.
- CI quality gates cover new modules and scripts.
- Job Fit engine now applies stricter skill matching and handles out-of-taxonomy JD requirements.

### Documentation
- Added baseline freeze and quality documents:
  - `docs/baselines/v2.3-baseline-freeze.md`
  - `docs/adr/0001-evidence-classification.md`
  - `docs/quality/definition-of-done.md`
  - `docs/migration-v2_3-to-v3_0.md`
  - `docs/calibration-applicability-limits.md`
