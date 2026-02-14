# Migration Notes: v3.0 -> v3.1

## What changed
- Multi-stack evaluation is now a first-class flow:
  - Python backend
  - Python + React full-stack
  - Django templates
  - Node/TS frontend
- Applicability model is explicit: `known/unknown/not_applicable`.
- Profile recalibration supports stack-aware runs:
  - `--stack-profile`
  - `--strict-stack/--no-strict-stack`
  - split labels by stack (`--split-by-stack`)
- CI includes stack smoke matrix scenarios.

## Compatibility
- Main CLI entrypoint remains `enhanced_evaluate_portfolio.py`.
- Existing JSON output fields remain backward-compatible.
- New/extended signals are additive (`frontend_quality`, `data_layer_quality`,
  `api_contract_maturity`, `fullstack_maturity` and related meta fields).

## Recommended migration checklist
1. Refresh schema and validate existing outputs:
   - `python generate_portfolio_schema.py`
   - `python validate_evaluation_contract.py --input portfolio_evaluation_local.json`
2. Re-run portfolio evaluation in `auto` stack mode:
   - `python enhanced_evaluate_portfolio.py --path <repos> --stack-profile auto`
3. If you use personal calibration, re-run it in stack-aware mode:
   - `python recalibrate_profile.py --profile <name> --results <evaluation.json> --stack-profile python_backend`
4. For mixed datasets, split labels first:
   - `python recalibrate_profile.py --profile <name> --results <evaluation.json> --split-by-stack --only-split`
5. Compare before/after to confirm expected deltas:
   - `python enhanced_evaluate_portfolio.py --path <repos> --compare <baseline.json>`
