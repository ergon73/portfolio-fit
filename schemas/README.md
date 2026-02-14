# JSON Schemas

## Portfolio evaluation contract
- Schema file: `schemas/portfolio_evaluation.schema.json`
- Generator: `python generate_portfolio_schema.py`
- Validator: `python validate_evaluation_contract.py --input portfolio_evaluation_local.json`

This schema defines mandatory fields for each repository object in
`portfolio_evaluation_*.json`.

Key multi-stack fields:
- `stack_profile`: detected repository profile.
- `criteria_meta[*].status`: `known` / `unknown` / `not_applicable`.
- Standalone full-stack signals:
  - `frontend_quality`
  - `data_layer_quality`
  - `api_contract_maturity`
  - `fullstack_maturity`
