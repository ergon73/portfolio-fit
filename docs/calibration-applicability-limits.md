# Calibration Applicability Limits

## Scope
This project supports calibration, but calibration quality depends on the label source.

## Hard limits
- A calibration run is only as good as the expert labels used in `golden_set.csv`.
- Proxy labels (Codex-generated or heuristic-adjusted) are useful for direction, not as final truth.
- A tuning patch can improve rank correlation on a labeled subset while harming global portfolio ranking.

## Operational policy
- Never auto-apply tuning patch to `portfolio_fit/scoring_config.json` by default.
- Keep tuned configurations in profile artifacts:
  - `calibration/profiles/<profile>/configs/scoring_config.profile.json`
- Validate impact before adoption using before/after comparison on real portfolio runs.

## Required checks before adoption
1. Calibration report quality:
   - Spearman
   - Pearson
   - MAE
2. Global ranking sanity:
   - `enhanced_evaluate_portfolio.py --compare <baseline.json>`
   - confirm no unacceptable mass decline.
3. Evidence coverage:
   - ensure labels include low/mid/high quality repos and red-quality cases.

## Recommendation
- Treat the shipped baseline as stable default.
- Use profile-based recalibration for personal or recruiter-specific views.
