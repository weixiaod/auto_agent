# data_acquisition — Data acquisition skill, fetchers, and JSON formatter

**Scope:** the whole "get data into the model" pipeline: skill orchestration, three Snowflake fetchers, Scenario Service stub, and the `json_formatter` that assembles the model payload.

**Dependencies:**
- `00_foundation.md` — `tools/errors.py` (`DataAcquisitionError`, `QueryExecutionError`, `PayloadValidationError`), `tools/logging.py`, schema skeletons, queries skeletons, `config/snowflake_creds.yaml` template, `pyproject.toml` (`snowflake-connector-python`, `jsonschema`, `pyyaml`)
- `config/model_config.json` — `history_periods` per variable (for auto_loan date-range computation and json_formatter slicing)

**Blocks:**
- `model_execution.md` (consumes the JSON payload)
- `actuals_replacement.md` (consumes auto_loan data)

**Starting state:** no code. Three IHS sources (auto_loan, ihs_actuals, ihs_forecast) must always be pulled. Scenario Service is deferred.

---

## Overview

The skill orchestrates three fetchers, then formats a model payload:

```
skill.run(params, cfg)
  ├─ fetch_auto_loan(timestamp, t0_date, history_periods)
  ├─ fetch_ihs_actuals(publn_id, yymm_num)
  ├─ fetch_ihs_forecast(publn_id, yymm_num, scenario_var)   # always one pull
  └─ format_for_model(...) -> JSON payload
```

One forecast pull per run regardless of mode. A CCAR cycle runs four separate pipelines (FRBB, FRBSA, BHCB, BHCS) — each one is a single-scenario run from this skill's perspective. Attribution pairs two runs' outputs downstream.

Fetchers internally split into `_fetch_raw()` (hits Snowflake, untested locally) and `_normalize()` (pure, fixture-tested).

---

## T1.1 — `skills/data_acquisition/`

**Files:** `skills/data_acquisition/SKILL.md`, `skills/data_acquisition/skill.py`

**What to build:**
- `skill.py` exposes `run(params: dict, cfg: dict) -> dict`. Calls three fetchers, then `format_for_model`, returns `{auto_loan, ihs_actuals, ihs_forecast, payload}`. Mode-agnostic; shape is identical for Outlook and CCAR.
- `SKILL.md` — frontmatter `name: data-acquisition`, trigger prose ("run the pipeline", scenario YAML provided, etc.), instructions for agent on invocation.

**Validation:** `[GRILL]` — skill-level test strategy decided during grilling.

---

## T2.1 — `tools/data_sources/snowflake_runner.py`

**Files:** `tools/data_sources/snowflake_runner.py`, `tools/data_sources/__init__.py`

**What to build:**
- `connect(creds_path: str = "config/snowflake_creds.yaml") -> snowflake.connector.Connection` — loads yaml, resolves `${...}` env vars, connects with password.
- `run_query(sql: str, params: dict, conn=None) -> list[dict]` — executes, returns raw rows as list of dicts.
- Both raise `QueryExecutionError` on failure with structured context.

**Note:** internal only. Fetchers call `run_query`; nothing else does.

**Validation:**
```bash
pytest tests/test_snowflake_runner.py
```
Locally testable: env-var resolution, appropriate error when creds file missing. Full execution requires Snowflake access on work laptop.

---

## T2.2 — `tools/data_sources/auto_loan_fetcher.py`

**Files:** `tools/data_sources/auto_loan_fetcher.py`

**Depends on:** `schemas/auto_loan.json` (field-locked version), `queries/auto_loan_actuals.sql`, T2.1

**What to build:**
- `_fetch_raw(timestamp, start_date, end_date) -> list[dict]` — reads `queries/auto_loan_actuals.sql`, calls `snowflake_runner.run_query`.
- `_normalize(raw_rows: list[dict], source_metadata: dict) -> dict` — converts raw rows to auto_loan intermediate dict conforming to `schemas/auto_loan.json`.
- `fetch(timestamp, t0_date, history_periods) -> dict` — wrapper: computes date range (`start = t0 − max(history_periods)`, `end = today`), calls `_fetch_raw`, `_normalize`, validates against schema.

**Quadruple duty note:** the returned data is used for:
1. t0 initial conditions for the model (both modes)
2. Prior-cycle benchmark period (Outlook only)
3. Actuals replacement for realized periods (Outlook only)
4. Enterprise-vs-industry adjustment lookback (both modes; consumed by `enterprise_adjuster` in `model_execution.md`)

Date range must cover all four:
```
start_date = t0_date − max(
  max(history_periods across variables),
  max(lookback_months across adjustment overrides + default)
)
end_date = today  (or scenario_start_date + realized window for actuals replacement)
```

**Fixtures:**
- `tests/fixtures/auto_loan_fetcher/raw_rows.json`
- `tests/fixtures/auto_loan_fetcher/expected_normalized.json`
- `tests/fixtures/auto_loan_fetcher/CAPTURE_GUIDE.md`

**Capture guide:**
1. On work laptop, run `queries/auto_loan_actuals.sql` with representative params (real t0 + timestamp).
2. Dump to `raw_rows.json`.
3. Hand-verify normalized shape matches what json_formatter expects.

**Validation:**
```bash
pytest tests/test_auto_loan_fetcher.py
```

---

## T2.3 — `tools/data_sources/ihs_actuals_fetcher.py`

Same pattern as T2.2. Fixtures at `tests/fixtures/ihs_actuals_fetcher/`.

Extra consideration: fetcher may include moving averages at t0 for variables where the model expects an MA input rather than raw levels. Internal handling.

---

## T2.4 — `tools/data_sources/ihs_forecast_fetcher.py`

Same pattern as T2.2. Always called once per run. But capture fixtures with **two different** `scenario_var` values to prove the parameter actually affects output:
- `tests/fixtures/ihs_forecast_fetcher/raw_rows_scenarioA.json`
- `tests/fixtures/ihs_forecast_fetcher/raw_rows_scenarioB.json`
- `tests/fixtures/ihs_forecast_fetcher/expected_normalized_scenarioA.json`
- `tests/fixtures/ihs_forecast_fetcher/expected_normalized_scenarioB.json`

---

## T2.5 — `tools/data_sources/scenario_service_fetcher.py` (DEFERRED stub)

**Files:** `tools/data_sources/scenario_service_fetcher.py`

**What to build:** Module with `fetch(**kwargs)` that raises `NotImplementedError("Scenario Service integration deferred; see BUILD_PLAN.md Open/TBD.")`.

**Validation:**
```bash
python -c "from tools.data_sources.scenario_service_fetcher import fetch
try: fetch()
except NotImplementedError as e: print('ok:', e)"
```

---

## T0.8-bis — Lock schema fields

**Files:** `schemas/auto_loan.json`, `schemas/ihs_actuals.json`, `schemas/ihs_forecast.json`

**What to build:** Replace `additionalProperties: true` skeletons from foundation with field-locked schemas. Each schema declares exact `source_metadata` fields, the `data` structure, and required fields.

**[GRILL]** Exact field list per fetcher is polished during grilling.

**Validation:**
```bash
python -c "import jsonschema, json; [jsonschema.Draft202012Validator.check_schema(json.load(open(f))) for f in ['schemas/auto_loan.json','schemas/ihs_actuals.json','schemas/ihs_forecast.json']]"
```

---

## T0.9-bis — Lock SQL queries

**Files:** `queries/auto_loan_actuals.sql`, `queries/ihs_econ_actuals.sql`, `queries/ihs_econ_forecasts.sql`

**What to build:** Replace `SELECT 1 AS placeholder;` stubs with real SQL, captured from work machine. Each query binds the params declared in its header.

**Validation:** Implicitly validated by fetcher fixture tests (T2.2–T2.4).

---

## T2.6 — `tools/json_formatter.py`

**Files:** `tools/json_formatter.py`

**Depends on:** all three schemas (field-locked), `config/model_config.json` `history_periods`

**What to build:** `format_for_model(auto_loan_data, ihs_actuals_data, ihs_forecasts, t0_date, scenario_start_date, history_periods) -> dict`:
- Concatenates econ actuals + forecasts at `scenario_start_date` per variable (not at `t0_date`). This is the econ glue point.
- Applies `history_periods` lookback to each econ variable from `scenario_start_date`.
- Uses `t0_date` for the target-variable initial conditions from `auto_loan_data`.
- Handles the gap between `t0_date` and `scenario_start_date` when they diverge (enterprise data lags econ data).

Raises `PayloadValidationError` if fields are missing, the concatenation boundary is inconsistent, or the two-date gap is ambiguous.

**[OPEN]:** Exact JSON payload shape is a placeholder. Fixture-driven — user captures a sample payload from a known-good call on work laptop.

**Fixtures:**
- `tests/fixtures/json_formatter/input_auto_loan.json`
- `tests/fixtures/json_formatter/input_ihs_actuals.json`
- `tests/fixtures/json_formatter/input_ihs_forecast.json`
- `tests/fixtures/json_formatter/input_cfg.json`
- `tests/fixtures/json_formatter/expected_payload.json`

**Validation:**
```bash
pytest tests/test_json_formatter.py
```
Iterate until output payload matches expected.

---

## `[GRILL]` — polish targets for this build plan

- [ ] **Exact fields per schema.** `source_metadata`, `data` array vs keyed object, value types, required fields. One pass per fetcher.
- [ ] **auto_loan date-range semantics.** Calendar unit (months, quarters). What's `end` — today, `scenario_start_date`, or `max(today, scenario_start_date)`?
- [ ] **Two-date gap behavior in `json_formatter`.** When `t0_date < scenario_start_date`, we have econ actuals for a window where the target series has already started its "forecast" (from `t0_date`). How does the model want this represented: (a) target-variable initial conditions at t0 plus the model bridges internally; (b) target actuals through the last known date + forecast init at scenario_start; (c) something else? Blocked on a sample payload from work laptop.
- [ ] **MA handling in ihs_actuals.** Which variables expect an MA at t0 vs raw? Does the fetcher compute it or pull pre-computed?
- [ ] **scenario_var semantics.** Is it a single string, or an object with multiple dimensions? Does it map 1:1 to a column filter or to a partition?
- [ ] **REMINDER: standard `scenario_var` value list.** User has a canonical list of allowed values. Pull it in when implementing `ihs_forecast_fetcher` — validate the incoming `scenario_var` against this list at `fetch()` entry and raise `ConfigError` on unknown values. List to be provided by user at implementation time.
- [ ] **json_formatter payload shape.** Wait for work-laptop sample or agree a placeholder shape to iterate on later.
- [ ] **Skill-level test strategy.** Monkeypatch fetchers in skill test? Or fixture-driven integration?
- [ ] **Error boundary.** Which `DataAcquisitionError` subclasses belong here vs foundation?
- [ ] **`fetch()` retries or not.** Fail fast vs exponential backoff on transient Snowflake errors.

---

## Locked for this skill

- Three distinct schemas (one per fetcher). No common_intermediate.
- Fetchers split internally into `_fetch_raw()` + `_normalize()`. Only `_normalize()` is locally testable.
- SQL lives in `queries/*.sql`; fetchers read + bind params.
- Snowflake auth via env-var substitution in yaml.
- Always pull all three IHS sources. One forecast pull per run regardless of mode. (A CCAR cycle = 4 separate runs.)
- `scenario_service_fetcher` raises `NotImplementedError`.
