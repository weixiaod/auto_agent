# model_execution — Model execution skill + model runner + enterprise adjuster

**Scope:** call the model API (industry-level forecast), then apply the enterprise adjustment (gap or ratio, per target × segment) to produce the enterprise-level forecast DataFrame.

The skill has two internal steps, both owned by this build plan:
1. `model_runner` — HTTP POST → industry-level long-format DataFrame.
2. `enterprise_adjuster` — shifts industry output to enterprise level using recent enterprise-vs-industry history.

**Dependencies:**
- `00_foundation.md` — `tools/errors.py` (`ModelExecutionError`, plus `EnterpriseAdjustmentError`), `tools/logging.py`, `pyproject.toml` (`requests`, `pandas`)
- `data_acquisition.md` — consumes the JSON payload (for `model_runner`) **and** the auto_loan intermediate dict (for `enterprise_adjuster` history)
- Scenario YAML — `enterprise_adjustment` block (default + overrides)

**Blocks:**
- `actuals_replacement.md` (Outlook mode post-processing; consumes enterprise model output)
- `analysis.md` (consumes enterprise model output)
- `ecm_attribution.md` (consumes enterprise model output as scenario DataFrames)

---

## T1.2 — `skills/model_execution/`

**Files:** `skills/model_execution/SKILL.md`, `skills/model_execution/skill.py`

**What to build:**
- `skill.py` exposes `run(payload: dict, auto_loan_data: dict, adjustment_config: dict, endpoint: str = None) -> pd.DataFrame`. Pipeline:
  1. `industry_df = model_runner.run_model(payload, endpoint)`
  2. `enterprise_df = enterprise_adjuster.adjust(industry_df, auto_loan_data, adjustment_config)`
  3. Returns `enterprise_df` (long-format DataFrame).
- `SKILL.md` — frontmatter `name: model-execution`, trigger prose (invoked after data_acquisition has produced both a payload and auto_loan data), invocation instructions. Notes that output is enterprise-level, not industry-level.

**Note:** In CCAR mode, the orchestrator calls `run` twice (once per scenario payload). In Outlook mode, once. The `auto_loan_data` + `adjustment_config` inputs are identical across both calls.

**Validation:** `[GRILL]` — skill-level test strategy decided during grilling.

---

## T2.7 — `tools/model_runner.py`

**Files:** `tools/model_runner.py`

**What to build:**
- `_post_raw(payload: dict, endpoint: str) -> dict` — HTTP POST, returns raw response JSON. Redacts credentials from logs.
- `_parse_response(response: dict) -> pd.DataFrame` — converts response to long-format DataFrame with columns `(category, variable, segment, date, value)`.
- `run_model(payload: dict, endpoint: str = None) -> pd.DataFrame` — wrapper. Raises `ModelExecutionError` on API failures.

**Model output contract (long-format DataFrame):**

| Column | Values |
|---|---|
| `category` | `Pricing`, `New Origination` |
| `variable` | e.g. `avg_loan_amount`, `count`, `pricing` |
| `segment` | `new_prime`, `new_near_prime`, `new_sub_prime`, `used_prime`, `used_near_prime`, `used_sub_prime` (pricing) or `prime`, `near_prime`, `sub_prime` (count, avg_loan_amount) |
| `date` | forecast period dates |
| `value` | numeric |

**Fixtures:**
- `tests/fixtures/model_runner/raw_response.json` — captured from real API call
- `tests/fixtures/model_runner/expected_long_df.csv`

**Validation:**
```bash
pytest tests/test_model_runner.py
```
Exercises `_parse_response` only. `_post_raw` tested on work laptop with real endpoint.

---

## T2.7b — `tools/enterprise_adjuster.py`

**Files:** `tools/enterprise_adjuster.py`

**What to build:** `adjust(industry_df: pd.DataFrame, auto_loan_data: dict, adjustment_config: dict) -> pd.DataFrame` — pure function. For each `(target, segment)` row in `industry_df`:

1. Resolve method + lookback from `adjustment_config` (override if present, else default).
2. From `auto_loan_data`, slice the last `lookback_months` of enterprise actuals for that target × segment.
3. Fetch the matching industry actuals for the same window (from IHS actuals — `[GRILL]`: where does this come from? see below).
4. Compute the adjustment factor:
   - `gap`: `mean(enterprise_actual − industry_actual)` → added to all future industry values for that (target, segment).
   - `ratio`: `mean(enterprise_actual / industry_actual)` → multiplied into all future industry values.
5. Apply factor to every forecast row in `industry_df` for that (target, segment).

Returns a new DataFrame with the same shape as `industry_df`, values adjusted.

Raises `EnterpriseAdjustmentError` when:
- `(target, segment)` in `industry_df` has no enterprise actuals in the lookback window.
- `adjustment_config` default block is missing.
- Override references an unknown target or segment.

**Fixtures:**
- `tests/fixtures/enterprise_adjuster/input_industry_df.csv`
- `tests/fixtures/enterprise_adjuster/input_auto_loan_data.json`
- `tests/fixtures/enterprise_adjuster/input_adjustment_config.json`
- `tests/fixtures/enterprise_adjuster/expected_enterprise_df.csv`

**Capture guide:** constructible from known-good enterprise + industry actuals by hand — not dependent on a live API call. Prioritize capturing one fixture per method (one `gap`, one `ratio`) and at least one with overrides exercised.

**Validation:**
```bash
pytest tests/test_enterprise_adjuster.py
```

---

## `[GRILL]` — polish targets for this build plan

**model_runner:**
- [ ] **Endpoint config.** Hardcoded per-env? Pulled from `config/`? Passed via scenario YAML? Env var?
- [ ] **Auth.** How is the model API authenticated (bearer token env var, mTLS, none)?
- [ ] **Response shape.** The raw response JSON structure — is it already long-format, nested by category, or grouped by variable? Affects `_parse_response` complexity.
- [ ] **Segment mismatch.** Pricing has 6 segments (new_*, used_*); count + avg_loan_amount have 3. Does the raw response mix them in one flat array or separate them by category?
- [ ] **Timeout + retries.** What timeout, what retry strategy, when do we raise `ModelExecutionError` vs retry?
- [ ] **Error detail.** Must `ModelExecutionError` capture the full response body or a redacted summary? Which fields get redacted?

**enterprise_adjuster:**
- [ ] **Industry actuals source for the lookback delta.** To compute `mean(enterprise − industry)` over the last N months, we need matching industry actuals for those same months + target + segment. Options: (a) read from `ihs_actuals_data` already fetched upstream, (b) separately fetch from Snowflake, (c) use the initial part of `industry_df` if the model response includes pre-t0 values. Pick one.
- [ ] **Target naming alignment.** Scenario YAML says `target: "pricing"` etc. Industry_df uses `variable: "pricing"`. Confirm the matching key and whether any rename is needed.
- [ ] **Segment coverage.** Pricing has 6 segments; count + avg_loan_amount have 3. Can an override reference a segment that doesn't exist for the target (e.g., `target: count, segment: new_prime`)? If so, raise or silently ignore?
- [ ] **Per-period adjustment vs. single factor.** Spec says single factor (mean over lookback) applied flat to all future periods. Confirm vs. e.g. decaying/weighted factor or per-month fan-out.
- [ ] **Sign handling for gap with negative values.** If `enterprise_actual − industry_actual` flips sign within the lookback, the mean may still be meaningful — flag whether any sanity check is needed.
- [ ] **Volume derivation.** `new_origination_volume = count × avg_loan_amount` — is volume computed pre- or post-adjustment? (Post is standard: adjust count and avg_loan_amount separately, multiply after.)

**skill orchestration:**
- [ ] **Skill-level test strategy.** Monkeypatch `run_model` + `enterprise_adjuster.adjust` in the skill test? Fixture-driven integration? Decide.

---

## Locked for this skill

- Model API is a Python-written HTTP API accepting JSON, returning JSON.
- `model_runner` output: long-format DataFrame `(category, variable, segment, date, value)` at **industry** level.
- `enterprise_adjuster` output: same shape, same columns, **enterprise**-level values.
- Skill output = enterprise-level. Downstream skills never see industry-level output.
- `_post_raw` / `_parse_response` split — `_post_raw` untested locally.
- `run_model` raises `ModelExecutionError`; `enterprise_adjuster.adjust` raises `EnterpriseAdjustmentError`, both with structured context.
- Enterprise adjustment is a **flat factor** per (target, segment) computed as mean over lookback window, applied uniformly to all future periods.
