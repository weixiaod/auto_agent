# auto_agent

A Python financial risk modeling pipeline with an LLM orchestrator
(Claude Code) that drives two operational modes: **CCAR stress testing**
and **Quarterly Outlook**. The pipeline pulls economic + auto loan data
from Snowflake, runs it through an ECM (Error Correction Model),
attributes the gap between scenarios variable-by-variable, and writes a
timestamped Excel report.

## Two layers

- **Agent** — Claude Code itself, guided by [`CLAUDE.md`](CLAUDE.md) at runtime.
- **Skills + tools** — Python under `skills/<name>/` and `tools/`. Skills
  sequence; tools are deterministic.

## Pipeline modes

| Mode | Runs | Attribution |
|---|---|---|
| **CCAR** | One run per scenario; a full cycle = 4 (`FRBB`, `FRBSA`, `BHCB`, `BHCS`) | Separate step; pairs stress vs baseline within an institution, same t0 |
| **Outlook** | One run per quarter; requires actuals replacement | Separate step; pairs current vs prior cycle, different t0s, includes backtesting-error bar |

Detailed runtime brief: [`CLAUDE.md`](CLAUDE.md).
Build-time briefing + per-skill plans: [`BUILD_PLAN.md`](BUILD_PLAN.md), [`docs/build_plans/`](docs/build_plans/).

## Repo layout

```
config/         scenario YAMLs + model_config.json + Snowflake creds template
queries/        external .sql templates (fetchers bind params)
schemas/        per-fetcher JSON schemas
skills/         <name>/SKILL.md + skill.py
tools/          deterministic functions (errors, logging, fetchers, model, attribution, reporting)
tests/          pytest suite
docs/build_plans/   per-skill build plans
outputs/        timestamped run artifacts (gitignored)
logs/           structured per-run JSON logs (gitignored)
```

## Quickstart

```bash
# Python 3.12+
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Configure Snowflake creds by copying the template and exporting env vars:

```bash
cp config/snowflake_creds.example.yaml config/snowflake_creds.yaml
# Store secrets in Keychain (macOS):
security add-generic-password -s snowflake_pwd -a "$USER" -w
# ~/.zshrc:
export SNOWFLAKE_PWD=$(security find-generic-password -s snowflake_pwd -w)
```

## Status

| Component | State |
|---|---|
| Foundation (errors, logging, schemas skeletons, queries skeletons, configs, tests) | done — scaffolded |
| ECM attribution (CCAR same-t0) | done — vertical slice; Outlook different-t0 + backtesting-error bar pending |
| data_acquisition / model_execution / actuals_replacement / analysis / reporting | pending — see `docs/build_plans/` |
| Real Snowflake SQL, model API, fixtures, ECM coefficients | pending — captured on work laptop |
