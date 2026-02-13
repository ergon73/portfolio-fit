# ADR-0001: Evidence Classification for Scoring

## Status
Accepted

## Date
2026-02-13

## Context
Portfolio scoring mixes strong measurements and heuristic signals. Without explicit
evidence classes, users cannot estimate reliability of a final score.

## Decision
Each criterion result must include:
- `status`: `known` or `unknown`
- `method`: `measured` or `heuristic`
- `confidence`: numeric range `[0.0, 1.0]`
- `note`: short rationale or collection error context

Classification rules:
- `measured`: value produced from concrete artifacts or deterministic analysis
  (`coverage.xml`, AST counters, git metadata, parsed tool outputs).
- `heuristic`: value inferred by pattern matching or proxy checks
  (presence signals, text matches, workflow hints).
- `unknown`: no reliable data available; criterion contributes no direct score and
  is reflected in data coverage.

## Consequences
- Scores remain comparable while uncertainty becomes explicit.
- Data quality warnings can be generated from missing core evidence.
- Calibration and tuning use transparent evidence provenance.
