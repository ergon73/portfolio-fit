# Definition of Done (Program Level)

## Mandatory for every sprint item
- Code implemented and covered by tests for new logic.
- Documentation updated in the same change.
- No regression in quality gates:
  - `ruff check .`
  - `black --check .`
  - `mypy`
  - `python -m unittest discover -s tests -v`

## Mandatory for scoring changes
- Contract-compatible output (`validate_evaluation_contract.py` passes).
- Schema refreshed when contract changes (`generate_portfolio_schema.py`).
- Calibration impact documented (correlation metrics and MAE before/after).

## Mandatory for release items
- Changelog entry exists.
- Migration note exists when behavior or output changed.
- Quick start examples are executable against current CLI.
