# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Planned
- v3.1.x stabilization and post-release fixes.

## [3.1.0] - 2026-02-14

### Added
- Stack smoke fixtures for CI matrix:
  - `tests/ci_smoke_stack_profiles.py`
  - `.github/workflows/ci.yml` matrix scenarios:
    - `backend-only`
    - `node-ts`
    - `django-templates`
    - `mixed-fullstack`
- Migration and release docs for v3.1:
  - `docs/migration-v3_0-to-v3_1.md`
  - `docs/releases/v3.1.0-release-notes.md`
  - `docs/releases/v3.1.0-publish-checklist.md`

### Changed
- Profile recalibration workflow is now stack-aware by default:
  - `--stack-profile`
  - `--strict-stack` / `--no-strict-stack`
  - labels split by stack (`--split-by-stack`).
- Documentation refreshed for multi-stack usage in:
  - `README.md`
  - `ENHANCED_USAGE_GUIDE.md`
  - `docs/recalibration-profiles.md`

### Contract/Schema
- Portfolio evaluation schema and contract docs updated for multi-language
  and standalone full-stack signals:
  - `schemas/portfolio_evaluation.schema.json`
  - `schemas/README.md`

## [3.0.0] - 2026-02-13

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

### Changed
- Scoring engine extracts measured evidence when available and marks unknown
  data explicitly.
- Reporting validates JSON output against a formal contract before writing
  artifacts.
- CI quality gates cover new modules and scripts.
- Job Fit engine applies stricter skill matching and handles out-of-taxonomy
  JD requirements.

### Documentation
- Added baseline and migration docs:
  - `docs/baselines/v2.3-baseline-freeze.md`
  - `docs/adr/0001-evidence-classification.md`
  - `docs/quality/definition-of-done.md`
  - `docs/migration-v2_3-to-v3_0.md`
  - `docs/calibration-applicability-limits.md`
