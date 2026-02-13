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
3. Run recalibration:
   - `python recalibrate_profile.py --profile my_view --results portfolio_evaluation_local.json`
4. Optional activation:
   - `python recalibrate_profile.py --profile my_view --results portfolio_evaluation_local.json --apply-to portfolio_fit/scoring_config.json`

## Artifacts per profile
- `labels/golden_set.csv`
- `artifacts/calibration_report.json`
- `artifacts/calibration_report.txt`
- `artifacts/scoring_config_patch.json`
- `artifacts/recalibration_summary.json`
- `artifacts/recalibration_summary.txt`
- `configs/scoring_config.profile.json`
- `configs/active_config_backups/*` (only when `--apply-to` is used)

## Notes
- If labels file already exists, bootstrap does not overwrite it unless
  `--force-prepare` is set.
- Baseline config remains unchanged unless `--apply-to` is passed explicitly.
