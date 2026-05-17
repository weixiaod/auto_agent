# docs/build_plans — Operational manual

This directory is the master execution plan for the Financial Risk Modeling Pipeline, split by skill. Each per-skill doc is self-contained enough for a subagent to pick up and execute in isolation, given foundation is in place.

If you landed here from a subagent dispatch: read the repo-root [`BUILD_PLAN.md`](../../BUILD_PLAN.md) first — it has the parallel-safe context, the shared-files map, and the dependency graph. Then open the specific skill doc you've been assigned.

---

## Index

| Order | Doc | Produces |
|---|---|---|
| 1 | [`00_foundation.md`](00_foundation.md) | Shared infra: `tools/errors.py`, `tools/logging.py`, `pyproject.toml`, `.gitignore`, schemas skeletons, queries skeletons, config templates, CLAUDE.md corrections |
| 2 | [`ecm_attribution.md`](ecm_attribution.md) | `skills/ecm_attribution/`, `tools/ecm_attribution.py` (with Outlook/different-t0 extension + backtesting-error bar) |
| 3 | [`data_acquisition.md`](data_acquisition.md) | `skills/data_acquisition/`, `tools/data_sources/{snowflake_runner, auto_loan_fetcher, ihs_actuals_fetcher, ihs_forecast_fetcher, scenario_service_fetcher}.py`, `tools/json_formatter.py`, locked schemas, real SQL |
| 4 | [`model_execution.md`](model_execution.md) | `skills/model_execution/`, `tools/model_runner.py` |
| 5 | [`actuals_replacement.md`](actuals_replacement.md) | `skills/actuals_replacement/` (Outlook only), `tools/actuals_replacer.py` |
| 6 | [`analysis.md`](analysis.md) | `skills/analysis/`, `tools/analysis/{fixed_analysis, exploratory_helpers}.py` |
| 7 | [`reporting.md`](reporting.md) | `skills/reporting/`, `tools/reporting/excel_builder.py` |

Skill artifacts (`SKILL.md` + `skill.py`) live under `skills/<name>/`. This directory holds only *how to build* them.

---

## Locked design decisions

These are settled and should not be revisited without explicit discussion.

| # | Decision |
|---|---|
| 1 | Scaffold now on personal laptop; fill `_fetch_raw()` + real queries + fixtures on work laptop. |
| 2 | Hybrid skills: each skill is a folder with `SKILL.md` (agent instructions) + `skill.py` (importable Python). |
| 3 | Validation is fixture-driven. User provides real `input.<ext>` + `expected_output.<ext>` + `CAPTURE_GUIDE.md` per skill/tool. Claude iterates until match. |
| 4 | Fixture formats: JSON for dicts, CSV for DataFrames, xlsx for Excel. |
| 5 | Equality: strict for structure, `rtol=1e-6, atol=1e-9` for floats (`pandas.testing.assert_frame_equal(check_exact=False)`). |
| 6 | Existing ECM code is reshaped into `skills/ecm_attribution/` and extended for Outlook mode. |
| 7 | Fetchers and `model_runner` are internally split: `_fetch_raw()` (untested locally) + `_normalize()` / `_parse_response()` (pure, fixture-tested). |
| 8 | Skill folder names use underscores (Python-legal for imports). |
| 9 | pytest + pyproject.toml, Python 3.11+. |
| 10 | ECM architecture: remote API and local `ECMAttributor` consume the **same** input; local uses closed-form decomposition with coefficients from `model_config.json`. |
| 11 | Three distinct schemas (one per fetcher), **not** one common_intermediate. |
| 12 | Snowflake auth: password via env var (`${SNOWFLAKE_PWD}`); yaml gitignored, `.example.yaml` committed. |
| 13 | Scenario YAML contains full intake params, runnable. |
| 14 | SQL in external `queries/*.sql` files; fetchers read and bind params. |
| 15 | Per-stage `RiskError` base classes + structured `context` dict. |
| 16 | Reality: 12 ECM models (pricing × 6 segments + count × 3 + avg_loan_amount × 3), per-model `feature_short_cols` + `feature_long_cols` split. Volume = count × avg_loan_amount (derived, not its own ECM). |
| 17 | Logging: stdlib-only (~30 lines), custom `JSONFormatter`. Zero extra dependencies. Revisable if a house standard emerges. |
| 18 | `json_formatter` belongs to the data_acquisition build plan (not model_execution) — it's the adapter between fetcher output and model input. |
| 19 | Foundation never touches `skills/`. It only creates/edits files under `tools/`, `schemas/`, `queries/`, `config/`, `logs/`, `tests/conftest.py`, and the root agent doc (`CLAUDE.md`). |
| 20 | yaml env-var substitution is a ~10-line `tools/config_loader.py` helper (stdlib `re` + `pyyaml`). No `envyaml` or similar dependency. |

---

## Open / TBD items (global)

Resolved within the skill build plan that needs them.

| Item | Resolved in | How |
|---|---|---|
| Skill-level test strategy (monkeypatch vs DI vs none) | each skill during its grilling | decide per skill; may differ |
| Exact JSON payload shape the model API expects | `data_acquisition.md` (json_formatter) | user captures a sample payload from a known-good run on work laptop |
| Excel template named range layout | `reporting.md` | user supplies real `templates/report_template.xlsx` |
| Full ECM coefficient values | `ecm_attribution.md` validation | user fills `config/model_config.json` from work machine |
| Job config file → canonical intake param set | `00_foundation.md` (CLAUDE.md update) | user shares the job config file |

---

## Validation protocol

Every TODO has a validation gate. One of:
- `pytest <path>` — runs a test file that must pass.
- `python -c "<import/smoke>"` — a short import/invocation check.
- **Manual** — an inspection step with a checklist (used sparingly, mostly Phase 0 housekeeping).

A TODO is **done** only when its validation command exits green.

---

## Iteration protocol

When a test fails, the job is to iterate on `skill.py` / `tool.py` until the fixture comparison passes.

1. Do **not** modify the expected-output fixture to match the code — the fixture is source of truth.
2. Do **not** relax the assertion tolerance to paper over a mismatch.
3. If after 3 iterations the test still fails, stop and surface the discrepancy with:
   - Actual output head (5 rows)
   - Expected output head (5 rows)
   - Column-by-column diff
   - Hypothesis for the mismatch.
4. Floats compare with `rtol=1e-6, atol=1e-9`. Structure (column names, dtypes, row counts) compares exactly.

---

## Fixture capture protocol

For each fixture, the user will (on work laptop):
1. Run the capture command documented in the TODO's `CAPTURE_GUIDE.md`.
2. Save raw output to `tests/fixtures/<skill-or-tool>/<name>.<ext>`.
3. Commit the fixture if small + non-sensitive; otherwise place it outside the repo and update `.gitignore`.
4. Refine the `CAPTURE_GUIDE.md` with any capture gotchas encountered.

---

## Grilling queue

Polish each build plan in this order. Each session ends with a finalized build plan plus any `[GRILL]` markers resolved.

1. `00_foundation` — mostly mechanical; lock error hierarchy and schema skeletons.
2. `ecm_attribution` — real code exists, easiest to reason about. Lock Outlook extension signature + backtesting-error shape.
3. `actuals_replacement` — pure function. Lock column conventions, t0 semantics, backtesting_error contract with `ecm_attribution`.
4. `data_acquisition` — per-fetcher schema lock-down, JSON payload shape. Biggest session.
5. `model_execution` — structure is lockable now; fixture capture later.
6. `analysis` — fixed vs exploratory boundary; fixed-metric definitions.
7. `reporting` — blocked on template; do last.
