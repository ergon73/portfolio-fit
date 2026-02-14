# Recalibration Profiles

This workflow lets each user apply their own expert judgment without modifying
the project baseline by default.

## Why this exists
- Different people value repositories differently.
- One shared scoring model cannot fully represent all hiring contexts.
- Profiles keep recalibration artifacts isolated and reproducible.

## Workflow
1. Generate profile labels:
   - `python recalibrate_profile.py --profile my_view --results portfolio_evaluation_local.json --prepare-golden-set --autofill --only-prepare`
2. Edit expert labels:
   - `calibration/profiles/my_view/labels/golden_set.csv`
3. Optional: split labels into stack-specific subsets:
   - `python recalibrate_profile.py --profile my_view --results portfolio_evaluation_local.json --split-by-stack --include-additional-stacks --only-split`
4. Run stack-aware recalibration:
   - `python recalibrate_profile.py --profile my_view --results portfolio_evaluation_local.json --stack-profile python_backend`
5. Optional activation:
   - `python recalibrate_profile.py --profile my_view --results portfolio_evaluation_local.json --stack-profile python_backend --apply-to portfolio_fit/scoring_config.json`

## Stack profiles
- Supported values: `auto`, `all`, `python_backend`, `python_fullstack_react`,
  `django_templates` (alias of `python_django_templates`),
  `python_django_templates`, `node_frontend`, `mixed_unknown`.
- Default mode is `--stack-profile auto --strict-stack`.
- In strict mode, `auto` fails if overlap contains mixed stacks.
- Use `--no-strict-stack` to allow mixed overlap in auto mode and fallback to
  dominant stack.
- Use `--stack-profile all` for an intentionally mixed calibration run.

## Artifacts per profile
- `labels/golden_set.csv`
- `labels/by_stack/golden_set_python_backend.csv` (if split was requested)
- `labels/by_stack/golden_set_python_fullstack_react.csv` (if split was requested)
- `labels/by_stack/golden_set_django_templates.csv` (if split was requested)
- `labels/by_stack/split_summary.json` (if split was requested)
- `artifacts/calibration_report.json`
- `artifacts/calibration_report.txt`
- `artifacts/scoring_config_patch.json`
- `artifacts/recalibration_summary.json`
- `artifacts/recalibration_summary.txt`
- `configs/scoring_config.profile.json`
- `scoring_config.<stack>.json` (for example `scoring_config.python_backend.json`)
- `configs/active_config_backups/*` (only when `--apply-to` is used)

## Notes
- If labels file already exists, bootstrap does not overwrite it unless
  `--force-prepare` is set.
- Baseline config remains unchanged unless `--apply-to` is passed explicitly.
- Recalibration reports include stack breakdown metrics:
  correlation (`pearson`), rank (`spearman`), and error bands (`mae`, `p90`).
