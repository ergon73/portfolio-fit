# Migration Notes: v2.3 -> v3.0

## Current status
Draft migration guide. Finalized when `v3.0` tag is cut.

## Expected compatibility
- CLI entrypoint remains `enhanced_evaluate_portfolio.py`.
- Output file names remain unchanged.
- Contract validation becomes a default quality step.

## Planned changes to watch
- Better calibration loop with reviewed expert labels.
- Job-fit recommendation quality checks across real JDs.
- Possible tightening of JSON contract constraints.

## Recommended migration checklist
1. Regenerate schema:
   - `python generate_portfolio_schema.py`
2. Validate historical outputs:
   - `python validate_evaluation_contract.py --input portfolio_evaluation_local.json`
3. Re-run calibration with reviewed labels:
   - `python calibrate_scoring_model.py --labels <reviewed.csv> --results <evaluation.json>`
4. Compare score deltas before applying new tuning:
   - `python enhanced_evaluate_portfolio.py --path <repos> --compare <baseline.json>`
