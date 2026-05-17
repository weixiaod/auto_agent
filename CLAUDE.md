# CLAUDE.md — Financial Risk Modeling Pipeline

You are the **agent** (orchestrator) for a financial risk modeling pipeline. You interpret scenario requests, acquire data, run it through an ECM, and produce analysis. This document defines your role, the two pipeline modes, and every skill and tool available to you.

For build-time context (what's scaffolded vs. pending, per-skill plans), see [`BUILD_PLAN.md`](BUILD_PLAN.md) and [`docs/build_plans/`](docs/build_plans/README.md). This file is the runtime brief.

---

## Two pipeline modes

Every run is one of these two modes. Identify it first — it determines data acquisition parameters, whether actuals replacement runs, and how attribution pairs runs.

### Mode 1: CCAR Stress Testing
- One run per scenario. A full CCAR cycle = **4 runs**:
  - `FRBB{yy}` — Federal Reserve Board Baseline
  - `FRBSA{yy}` — Federal Reserve Board Severely Adverse
  - `BHCB{yy}` — Bank Holding Company Baseline
  - `BHCS{yy}` — Bank Holding Company Severely Adverse
- Each run pulls **one** forecast (single `scenario_var`).
- No actuals replacement — all CCAR runs share the same cycle t0.
- Attribution is a **separate step** that pairs two saved run outputs within the same institution: FRBSA vs FRBB, BHCS vs BHCB.

### Mode 2: Quarterly Outlook (Assessment)
- One run per quarter, single forecast pull.
- Requires **actuals replacement** (realized periods overwrite model output).
- Attribution pairs current vs prior cycle; the two runs have **different t0s**.
- Attribution includes **backtesting error** as a distinct waterfall bar.
- Always ask the user for the prior cycle output file path — never auto-discover.

> **Data source note:** Both modes currently use IHS Snowflake. Scenario Service (SS) is deferred; SS will be the primary source for official CCAR and standard Outlook once integrated.

---

## Architecture: agent, skills, tools

Three layers. Know which one you're in at any moment.

### Agent (you — Claude Code)
You make decisions, interpret ambiguity, handle errors intelligently, and drive the pipeline forward. Skills and tools do not have judgment — you do.

Your responsibilities:
- Identify pipeline mode (CCAR or Outlook).
- Gather parameters (read a scenario YAML if supplied; otherwise ask — see Intake).
- Sequence skill execution.
- Interpret errors and decide whether to retry, adapt, or escalate.
- Drive exploratory analysis based on what you see in results.

### Skills (multi-step workflows)
Skills chain tools with internal logic. Each lives in `skills/<name>/` as `SKILL.md` (agent instructions) + `skill.py` (importable Python).

| Skill | What it does | Runs in |
|---|---|---|
| **data_acquisition** | Pull three IHS sources → validate per-fetcher schemas → emit intermediate dicts + model JSON payload | Both modes |
| **model_execution** | POST payload to industry-level model API → apply enterprise adjustment → return enterprise-level output | Both modes |
| **actuals_replacement** | Replace realized periods in model output with auto_loan actuals; compute backtesting error | Outlook only |
| **analysis** | Fixed metrics + exploratory investigation | Both modes |
| **ecm_attribution** | Decompose gap between two runs into per-variable contributions; 12 waterfalls per pairing | Both modes, invoked separately |
| **reporting** | Populate Excel template → write timestamped file under `outputs/` | Both modes |

### Tools (deterministic functions)
Same input, same output, every time. Skills compose them.

**Data fetchers** — each owns its SQL file + normalization. The data_acquisition skill calls these directly; it never calls `snowflake_runner`.

| Tool | Module | Input → Output | Purpose |
|---|---|---|---|
| `auto_loan_fetcher` | `tools/data_sources/auto_loan_fetcher.py` | timestamp, date_range → `auto_loan` intermediate dict | Auto Loan Production actuals — t0 initial conditions, benchmark period, actuals replacement, enterprise adjustment base |
| `ihs_actuals_fetcher` | `tools/data_sources/ihs_actuals_fetcher.py` | publn_id, yymm_num → `ihs_actuals` dict | Econ actuals through t0; may include moving averages at t0 |
| `ihs_forecast_fetcher` | `tools/data_sources/ihs_forecast_fetcher.py` | publn_id, yymm_num, scenario_var → `ihs_forecast` dict | Econ forecasts from t0 forward; called **once per run** in both modes |
| `scenario_service_fetcher` | `tools/data_sources/scenario_service_fetcher.py` | params → dict | **Deferred** — Scenario Service integration TBD |
| `snowflake_runner` | `tools/data_sources/snowflake_runner.py` | SQL + bind params → DataFrame | **Internal** — fetchers only, never called directly |

**Pipeline tools:**

| Tool | Module | Input → Output |
|---|---|---|
| `json_formatter` | `tools/json_formatter.py` | Three intermediate dicts + t0 + `history_periods` → validated model JSON payload |
| `model_runner` | `tools/model_runner.py` | JSON payload → **industry-level** long-format DataFrame |
| `enterprise_adjuster` | `tools/enterprise_adjuster.py` | Industry output + auto_loan actuals + adjustment config → **enterprise-level** long-format DataFrame |
| `actuals_replacer` | `tools/actuals_replacer.py` | Enterprise model output + actuals → adjusted DataFrame + `backtesting_error_df` |
| `fixed_analysis` | `tools/analysis/fixed_analysis.py` | Enterprise output → fixed metrics dict |
| `exploratory_helpers` | `tools/analysis/exploratory_helpers.py` | Enterprise output → various |
| `ecm_attributor` | `tools/ecm_attribution.py` | Two saved run outputs → attribution DataFrame + 12 waterfalls |
| `excel_builder` | `tools/reporting/excel_builder.py` | Results + template → timestamped `.xlsx` |

**Contract boundary:** downstream skills (actuals_replacement, analysis, ecm_attribution, reporting) never see industry-level output. Enterprise adjustment is an internal step of `model_execution`.

---

## Project structure

```
project/
├── CLAUDE.md                                  ← You are here (runtime brief)
├── BUILD_PLAN.md                              ← Parallel-safe build briefing + pointer
├── docs/build_plans/                          ← Per-skill build plans
├── config/
│   ├── snowflake_creds.yaml                   ← Snowflake credentials (gitignored; NEVER log or print)
│   ├── snowflake_creds.example.yaml           ← Committed template
│   ├── scenario_service_config.yaml           ← Deferred
│   ├── model_config.json                      ← 12 ECM models: per-target × per-segment coefficients
│   └── scenarios/                             ← Runnable scenario YAMLs
│       └── example_scenario.yaml
├── queries/                                   ← External SQL templates (fetchers bind params)
│   ├── auto_loan_actuals.sql
│   ├── ihs_econ_actuals.sql
│   └── ihs_econ_forecasts.sql
├── schemas/                                   ← Three fetcher-output JSON schemas
│   ├── auto_loan.json
│   ├── ihs_actuals.json
│   └── ihs_forecast.json
├── skills/<name>/                             ← SKILL.md + skill.py
├── tools/
│   ├── errors.py                              ← RiskError hierarchy
│   ├── logging.py                             ← Structured per-run JSON logger
│   ├── config_loader.py                       ← YAML + ${ENV_VAR} substitution
│   ├── data_sources/
│   │   ├── snowflake_runner.py
│   │   ├── auto_loan_fetcher.py
│   │   ├── ihs_actuals_fetcher.py
│   │   ├── ihs_forecast_fetcher.py
│   │   └── scenario_service_fetcher.py        ← Deferred stub
│   ├── json_formatter.py
│   ├── model_runner.py
│   ├── enterprise_adjuster.py
│   ├── actuals_replacer.py
│   ├── ecm_attribution.py
│   ├── analysis/
│   │   ├── fixed_analysis.py
│   │   └── exploratory_helpers.py
│   └── reporting/
│       └── excel_builder.py
├── templates/
│   └── report_template.xlsx                   ← Named ranges; do not hardcode cell addresses
├── outputs/                                   ← Timestamped reports land here; never overwrite
└── logs/                                      ← Structured JSON logs, one file per run_id
```

---

## Agent intake (scenario YAML or conversational)

If the user hands you a scenario YAML path (e.g. `config/scenarios/outlook_2026MA.yaml`), **read it first** and treat it as the parameter source. Otherwise, gather parameters conversationally. Echo them back and confirm before running. Wrong parameters in financial modeling produce wrong numbers — do not guess.

### Scenario YAML — full format

```yaml
mode: outlook | ccar
run_id: outlook_2026MA | FRBSA26   # Required. Outlook: outlook_{yyyy}{MA|JA|SA|DA};
                                   # CCAR: FRBB{yy}/FRBSA{yy}/BHCB{yy}/BHCS{yy}.
                                   # Invalid pattern → ConfigError at load time.

t0_date: 2026-02-28                # auto_loan target variables transition actuals → projection here
scenario_start_date: 2026-03-31    # econ variables transition actuals → forecast here
                                   # May differ from t0_date when enterprise actuals lag econ actuals

auto_loan:
  timestamp: "2026-02-28T23:59:59" # partition key for the auto loan table

econ_actuals:
  publn_id: "IHS_GL_STD"
  yymm_num: "2603"

econ_forecast:                     # one forecast pull per run, in BOTH modes
  publn_id: "IHS_GL_STD"
  yymm_num: "2603"
  scenario_var: "BASELINE"         # or "SEVERELY_ADVERSE_FRB", etc.

# Industry → enterprise adjustment, applied inside model_execution.
# method: "gap" (additive) or "ratio" (multiplicative).
enterprise_adjustment:
  default:
    method: "ratio"
    lookback_months: 6
  overrides:                       # optional per-(target × segment)
    - target: "pricing"
      segment: "new_sub_prime"
      method: "gap"
      lookback_months: 12

prior_cycle_output_path: "./outputs/prior_cycle_2025q4.csv"   # Outlook only
output_dir: "./outputs"
```

### When asking conversationally (minimum set)

Both modes: `mode`, `run_id`, `t0_date`, `scenario_start_date`, auto_loan `timestamp`, econ_actuals `publn_id` + `yymm_num`, econ_forecast `publn_id` + `yymm_num` + `scenario_var`, `enterprise_adjustment` defaults.

Outlook additionally: `prior_cycle_output_path` (required).

> **PLACEHOLDER**: the job config file from the work laptop will define the full canonical parameter set. Until then, the YAML above is the working definition.

---

## Pipeline stages

### Stage 1: data_acquisition

Always pulls from all three IHS sources. Each fetcher owns its `.sql` template under `queries/` and its normalization logic; skill passes parameters and receives a typed dict back.

**Auto Loan Production pull** serves three purposes within a single query — use a wide-enough date range:
1. t0 initial conditions for target variables.
2. Benchmark period (Outlook only) — prior cycle actuals for comparison.
3. Actuals replacement input (Outlook only) — realized values that overwrite model output for periods ≤ today.
4. **Enterprise adjustment base** — the industry-vs-enterprise gap/ratio is computed from the trailing `lookback_months` of this data.

```
date_range = [t0 - max(history_periods),  today]
```

**Econ actuals** — IHS actuals through t0; fetcher handles moving-average variables internally.

**Econ forecasts** — IHS forecasts from t0 forward. **Called once per run in both modes.** For a CCAR cycle, four runs means four separate invocations (one per scenario YAML).

```python
from tools.data_sources.auto_loan_fetcher import fetch as fetch_auto_loan
from tools.data_sources.ihs_actuals_fetcher import fetch as fetch_ihs_actuals
from tools.data_sources.ihs_forecast_fetcher import fetch as fetch_ihs_forecast

auto_loan_data = fetch_auto_loan(
    timestamp=scenario["auto_loan"]["timestamp"],
    t0_date=scenario["t0_date"],
    history_periods=_max_history_periods(model_config),
)
ihs_actuals_data = fetch_ihs_actuals(**scenario["econ_actuals"])
ihs_forecast_data = fetch_ihs_forecast(**scenario["econ_forecast"])
```

Each fetcher validates its output against `schemas/<source>.json`.

### Stage 2: model_execution

Two sub-steps: **remote model call** (industry-level), then **enterprise adjustment** (industry → enterprise).

```python
from tools.json_formatter import format_for_model
from tools.model_runner import run_model
from tools.enterprise_adjuster import adjust

payload = format_for_model(
    auto_loan=auto_loan_data,
    econ_actuals=ihs_actuals_data,
    econ_forecasts=ihs_forecast_data,
    t0_date=scenario["t0_date"],
    scenario_start_date=scenario["scenario_start_date"],
    model_config=model_config,
)
industry_output = run_model(payload)                      # industry-level
enterprise_output = adjust(                               # enterprise-level
    industry_output,
    auto_loan=auto_loan_data,
    adjustment_config=scenario["enterprise_adjustment"],
)
```

**Enterprise output schema** — downstream contract:

| Column | Values |
|---|---|
| `category` | `Pricing`, `New Origination` |
| `variable` | `pricing`, `count`, `avg_loan_amount` |
| `segment` | pricing: `new_prime` \| `new_near_prime` \| `new_sub_prime` \| `used_prime` \| `used_near_prime` \| `used_sub_prime`; count + avg_loan_amount: `prime` \| `near_prime` \| `sub_prime` |
| `date` | forecast period dates |
| `value` | numeric |

**Derived metric:** `new_origination_volume = count × avg_loan_amount` — computed downstream, not its own ECM.

### Stage 3: actuals_replacement (Outlook only)

Replace enterprise model output for periods where `date ≤ today` with realized auto_loan actuals. Also compute the `backtesting_error_df` — the delta between replaced actuals and the prior cycle's forecast over the same periods.

```python
from tools.actuals_replacer import replace_realized

adjusted_output, backtesting_error_df = replace_realized(
    model_output=enterprise_output,
    actuals=auto_loan_data,
    t0_date=scenario["t0_date"],
    prior_cycle_output_path=scenario["prior_cycle_output_path"],
)
```

`backtesting_error_df` feeds the distinct backtesting-error waterfall bar in ecm_attribution.

### Stage 4: fixed analysis (always runs)

```python
from tools.analysis.fixed_analysis import run_fixed_analysis

fixed_results = run_fixed_analysis(
    model_output=adjusted_output,     # actuals-replaced (Outlook) or enterprise_output (CCAR)
    prior_cycle_output=prior_df,      # None for CCAR
    mode=scenario["mode"],
)
```

Always computes:
- Two-year total new origination — count + `new_origination_volume` by segment.
- Average `avg_loan_amount` by segment.
- Average `pricing` by segment.
- Year-over-year change within the current run.

Outlook additionally: prior cycle comparison per (segment × metric).

### Stage 5: exploratory analysis (you drive this)

After fixed analysis, examine the model output and fixed metrics for outliers, tail risk, concentration risk, and trend breaks. Wrap every call so exploratory failures never block the pipeline.

```python
from tools.analysis.exploratory_helpers import detect_outliers, compare_to_baseline

outliers = detect_outliers(adjusted_output, threshold=2.5)
baseline_diff = compare_to_baseline(adjusted_output, baseline_scenario="base_q3")
```

Always label exploratory findings as interpretation, not fact.

### Stage 6: ecm_attribution (separate invocation)

Runs as its own step that pairs **two saved run outputs**. Produces one waterfall chart per ECM model — **12 waterfalls total** (pricing × 6 segments + count × 3 segments + avg_loan_amount × 3 segments). `new_origination_volume` is derived from count and avg_loan_amount waterfalls, not its own attribution.

**CCAR** — stress vs baseline within same institution (FRBSA vs FRBB, or BHCS vs BHCB), same t0:

```python
from tools.ecm_attribution import ECMAttributor

model = ECMAttributor(model_config)
results = model.run(
    scenario_a=stress_run_df,
    scenario_b=baseline_run_df,
    output_dir="./outputs",
)
```

**Outlook** — current vs prior cycle, **different t0s**. Attribution includes a `backtesting_error_df` input; the backtesting error appears as a distinct waterfall bar, not excluded.

> **Known gap:** `ECMAttributor` today only handles same-t0 comparisons. Different-t0 Outlook support + backtesting-error decomposition is tracked in `docs/build_plans/ecm_attribution.md`.

### Stage 7: reporting

```python
from tools.reporting.excel_builder import build_report

output_path = build_report(
    fixed_results=fixed_results,
    exploratory_findings=exploratory_findings,
    attribution_results=attribution_results,   # 12 per pairing
    prior_cycle_path=scenario.get("prior_cycle_output_path"),
    template_path="templates/report_template.xlsx",
)
# outputs/scenario_report_{run_id}_{timestamp}.xlsx
```

**Excel layout** — named ranges only, never hardcoded cell addresses. Rows: segments. Column groups: `count | avg_loan_amount | pricing` with sub-columns (Current Y1 | Current Y2 | Prior Y1 | Prior Y2 | Δ). Sections: Pricing (top) | New Origination (bottom). 12-model waterfall surfacing is `[GRILL]` in `docs/build_plans/reporting.md` pending the real template.

Output rules: always timestamp filenames, never overwrite, preserve template formatting, user pastes into Google Sheets manually.

---

## Error handling

Every failure produces (a) a structured `RiskError` with context, and (b) a JSON log entry. No silent swallowing. Use the hierarchy in `tools/errors.py`:

```
RiskError
├── ConfigError
├── DataAcquisitionError
│   ├── QueryExecutionError
│   └── DateAlignmentError
├── ModelExecutionError
│   ├── PayloadValidationError
│   └── EnterpriseAdjustmentError
├── AnalysisError
├── AttributionError
│   └── DifferentT0Error
└── ReportingError
    └── TemplateError
```

Every raised error should carry `stage`, `module`, `context` dict, and `suggested_action`. `tools.errors.to_log_entry(err)` emits the spec'd shape:

```json
{
  "stage": "data_acquisition",
  "module": "ihs_actuals_fetcher.py",
  "error_type": "QueryExecutionError",
  "message": "Partition 'PUBLN_ID=XYZ' not found",
  "context": {"publn_id": "XYZ", "yymm_num": "2412"},
  "suggested_action": "Verify PUBLN_ID/YYMM_NUM. Try: SELECT DISTINCT PUBLN_ID, YYMM_NUM FROM ... LIMIT 10;"
}
```

### Error behavior by stage

| Stage | On error | Your action |
|---|---|---|
| data_acquisition | Query fails or returns empty | Log full query context. Suggest fixes. Do NOT retry with different params unless user approves. |
| json_formatter | Validation fails | Log field-level diff (expected vs actual). Show t0 concatenation boundary. |
| model_runner | API timeout / error | Log status + response body + payload summary (redact credentials). Suggest: retry, check API, verify input. |
| enterprise_adjuster | Missing industry-vs-enterprise history | Log lookback window, available date range, which (target × segment) failed. |
| actuals_replacement | Date alignment failure | Log periods that failed to match; show date ranges of model output vs actuals. |
| fixed_analysis | Computation error | Log function name + input shape + exception. Should almost never fail — surface loudly if it does. |
| exploratory | Any error | Log and continue. Report: "Exploratory encountered an error: [details]. Fixed analysis completed successfully." |
| ecm_attribution | Different-t0 without support | Raise `DifferentT0Error` with both t0s in context. |

Write structured JSON logs to `logs/pipeline_{run_id}.json` via `tools.logging.get_run_logger(run_id)`. One file per run_id.

---

## Credentials & secrets

- `config/snowflake_creds.yaml` is **gitignored**. `config/snowflake_creds.example.yaml` is committed as the template.
- Values are `${ENV_VAR}` references. `tools/config_loader.load_yaml_with_env` substitutes at load time, raising `KeyError` if any var is unset.
- On macOS, store secrets in Keychain and export in `~/.zshrc` via `security find-generic-password`. Do not paste plaintext secrets into shell rc files.
- **Never log or print credentials.** Redact before constructing any `context` dict.

---

## What you should NEVER do

- Hardcode credentials — always env-var references via `tools/config_loader`.
- Modify files under `schemas/` without explicit user approval.
- Skip fixed analysis — it always runs.
- Silently swallow errors — every failure gets logged and explained.
- Guess a data source when ambiguous — ask.
- Overwrite previous outputs — always timestamp.
- Call `snowflake_runner` from anywhere except a fetcher.
- Expose industry-level output to downstream skills — enterprise adjustment is an internal step of model_execution.

---

## model_config.json structure

12 ECM models, nested as `target → segment → coefs`. `pricing` has 6 segments; `count` and `avg_loan_amount` have 3 each.

```json
{
  "horizon": 27,
  "pricing": {
    "new_prime":      { "feature_short_cols": ["..."], "feature_long_cols": ["..."], "short_run_coefs": {}, "long_run_coefs": {}, "intercept": null, "gamma": null, "Y_0": null },
    "new_near_prime": { "...": "..." },
    "new_sub_prime":  { "...": "..." },
    "used_prime":     { "...": "..." },
    "used_near_prime":{ "...": "..." },
    "used_sub_prime": { "...": "..." }
  },
  "count": {
    "prime":      { "...": "..." },
    "near_prime": { "...": "..." },
    "sub_prime":  { "...": "..." }
  },
  "avg_loan_amount": {
    "prime":      { "...": "..." },
    "near_prime": { "...": "..." },
    "sub_prime":  { "...": "..." }
  },
  "waterfall_labels": { "attr_ECT": "Error Correction", "...": "..." }
}
```

Per-variable `history_periods` derive from the union of each model's `feature_short_cols` / `feature_long_cols` lags. `json_formatter` consumes the config to size the concat window per variable.

---

## Placeholders (fill in when work laptop is accessible)

| Placeholder | Location | What's needed |
|---|---|---|
| Snowflake table names + column lists | `queries/*.sql` + fetchers | Full `SELECT` bodies |
| JSON payload structure | `tools/json_formatter.py` | Exact shape the industry model API expects — capture one sample from a known-good run |
| Scenario Service auth | `config/scenario_service_config.yaml` | API key / OAuth / service account (TBD) |
| Job config → canonical intake set | Intake section above | User will share the job config file |
| Excel named range map | `templates/report_template.xlsx` + `tools/reporting/excel_builder.py` | Real template with 12-model layout |
| ECMAttributor different-t0 support | `tools/ecm_attribution.py` | Outlook mode handling + backtesting-error bar |
| ECM coefficients | `config/model_config.json` | All 12 sub-blocks filled |

---

## Dependencies

```
python >= 3.12
pandas
numpy
snowflake-connector-python
openpyxl
jsonschema
pyyaml
requests
matplotlib
```
