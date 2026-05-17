# BUILD_PLAN.md — Parallel-safe briefing + pointer

This file is the entry point for any agent (human or automated, orchestrator or subagent) tasked with building part of this repo. The full execution plan has been split into per-skill build plans under [`docs/build_plans/`](docs/build_plans/README.md). Read this file first, then the specific skill doc you've been assigned.

---

## Project in one paragraph

This repo is a financial risk modeling pipeline with two modes — CCAR stress testing and Quarterly Outlook. An orchestrator agent gathers parameters (conversationally or from a scenario YAML), runs data_acquisition → model_execution → (actuals_replacement, Outlook only) → analysis + ecm_attribution → reporting. Local `ECMAttributor` uses closed-form coefficients from `config/model_config.json`; the remote model API consumes the same payload. Every stage is fixture-driven: real inputs + expected outputs are captured on the work laptop; the code iterates until it matches. See `CLAUDE.md` for the agent runtime brief; this file and the per-skill docs under `docs/build_plans/` carry all build-time context.

---

## Per-skill build plans

| Order | Plan | Owns |
|---|---|---|
| 1 | [docs/build_plans/00_foundation.md](docs/build_plans/00_foundation.md) | shared infra — errors, logging, pyproject, schemas + queries skeletons, config templates |
| 2 | [docs/build_plans/ecm_attribution.md](docs/build_plans/ecm_attribution.md) | `skills/ecm_attribution/` + `tools/ecm_attribution.py` (CCAR same-t0 + Outlook different-t0 + backtesting-error bar) |
| 3 | [docs/build_plans/data_acquisition.md](docs/build_plans/data_acquisition.md) | `skills/data_acquisition/` + `tools/data_sources/*` + `tools/json_formatter.py` + field-locked schemas + real SQL |
| 4 | [docs/build_plans/model_execution.md](docs/build_plans/model_execution.md) | `skills/model_execution/` + `tools/model_runner.py` + `tools/enterprise_adjuster.py` (industry → enterprise adjustment) |
| 5 | [docs/build_plans/actuals_replacement.md](docs/build_plans/actuals_replacement.md) | `skills/actuals_replacement/` (Outlook only) + `tools/actuals_replacer.py` |
| 6 | [docs/build_plans/analysis.md](docs/build_plans/analysis.md) | `skills/analysis/` + `tools/analysis/{fixed_analysis, exploratory_helpers}.py` |
| 7 | [docs/build_plans/reporting.md](docs/build_plans/reporting.md) | `skills/reporting/` + `tools/reporting/excel_builder.py` |

The `docs/build_plans/README.md` index holds protocols (validation, iteration, fixture capture, float tolerance), the global locked-decisions list, and the grilling queue.

---

## Shared / common files

Files every skill reads, produces, or must coordinate around. Owners listed in parens.

| File / directory | Owner (creates) | Consumed by |
|---|---|---|
| `tools/errors.py` — `RiskError` hierarchy | foundation | every tool raising typed errors |
| `tools/logging.py` — structured JSON logger | foundation | every stage that logs |
| `config/model_config.json` — 12-model ECM coefs + `history_periods` | foundation (scaffold) → ecm_attribution (real coefs on work laptop) | data_acquisition (json_formatter), ecm_attribution, analysis |
| `config/snowflake_creds.yaml` + `.example.yaml` | foundation | data_acquisition |
| `config/scenario_service_config.yaml` (deferred) | foundation | data_acquisition (when SS is live) |
| `config/scenarios/*.yaml` — runnable intake (includes `enterprise_adjustment` block) | foundation (template) | orchestrator, data_acquisition, **model_execution (enterprise_adjustment block)**, actuals_replacement |
| `schemas/auto_loan.json`, `ihs_actuals.json`, `ihs_forecast.json` | foundation (skeleton) → data_acquisition (field-locked) | data_acquisition (fetchers + json_formatter) |
| `queries/*.sql` | foundation (stubs) → data_acquisition (real SQL on work laptop) | data_acquisition (fetchers) |
| `pyproject.toml`, `.python-version` | foundation | entire repo |
| `.gitignore` | foundation | entire repo |
| `tests/conftest.py`, `tests/__init__.py` | foundation | every test |
| `CLAUDE.md` | foundation (corrections) | agent runtime brief |
| `templates/report_template.xlsx` | user-supplied | reporting |
| `outputs/`, `logs/` | foundation (directories) | model_runner, excel_builder, any logger |

---

## Cross-skill data contracts

Artifacts passed between skills. If you change the shape of any of these, you change the interface between two build plans — coordinate.

| Artifact | Produced by | Consumed by |
|---|---|---|
| `auto_loan` intermediate dict | data_acquisition (`auto_loan_fetcher.fetch`) | data_acquisition (json_formatter), **model_execution (enterprise_adjuster)**, actuals_replacement |
| `ihs_actuals` intermediate dict | data_acquisition (`ihs_actuals_fetcher.fetch`) | data_acquisition (json_formatter), possibly model_execution (enterprise_adjuster — see `[GRILL]`) |
| `ihs_forecast` intermediate dict (1x or 2x) | data_acquisition (`ihs_forecast_fetcher.fetch`) | data_acquisition (json_formatter) |
| Model JSON payload | data_acquisition (`json_formatter.format_for_model`) | model_execution |
| **Industry-level** long-format DataFrame — `(category, variable, segment, date, value)` | model_execution (`model_runner.run_model`) | model_execution (`enterprise_adjuster` — internal only) |
| **Enterprise-level** long-format DataFrame — same shape | model_execution (`enterprise_adjuster.adjust`) | actuals_replacement, analysis, ecm_attribution |
| Adjusted (actuals-replaced) enterprise output | actuals_replacement | analysis, ecm_attribution (Outlook) |
| `backtesting_error_df` | actuals_replacement | ecm_attribution (Outlook only; feeds the distinct backtesting-error waterfall bar) |
| `fixed_results` dict | analysis | reporting |
| `attribution_results` (12 per run — one per model) | ecm_attribution | reporting |

**Contract boundary:** downstream skills (actuals_replacement, analysis, ecm_attribution, reporting) never see industry-level output. Enterprise adjustment is an internal step of `model_execution`.

---

## Dependency graph (build order + parallel-safe groupings)

```
foundation  (blocks all skills)
  │
  ├── ecm_attribution                 ← cross-run analysis; pairs two saved run outputs
  │
  └── data_acquisition                ← must precede model_execution
        │
        └── model_execution           ← must precede actuals_replacement + analysis
              ├── actuals_replacement ← Outlook only; can parallel with analysis
              └── analysis
                    │
                    └── reporting     ← last; needs analysis + ecm_attribution outputs
```

**A pipeline *run* executes:** data_acquisition → model_execution → (actuals_replacement if Outlook) → analysis. One run = one scenario. A CCAR cycle is 4 runs (FRBB, FRBSA, BHCB, BHCS); Outlook is 1 run per quarter.

**`ecm_attribution` is a separate invocation** that pairs two saved run outputs: CCAR pairs stress vs baseline within the same institution (FRB or BHC); Outlook pairs current cycle vs prior cycle.

**Parallel-safe groupings** (after foundation is green):
- `ecm_attribution` runs independently of the data/model chain.
- After `model_execution`: `actuals_replacement` and `analysis` can proceed in parallel.
- `reporting` waits on `analysis` (always) and `ecm_attribution` (if its results are being included).

A subagent assigned a single skill should read the parent doc for that skill and **not modify files outside its `Owns` column** without escalating. Shared files listed above have a single owner per cell.

---

## Current repo status (snapshot)

- **Working:** ECM attribution vertical slice — `tools/ecm_attribution.py`, `skills/ecm-attribution/SKILL.md`, sample outputs under `outputs/`.
- **Missing:** everything else in the table above.
- **Environment:** personal laptop; no Snowflake, no model API, no real fixtures. Those come when work laptop is accessible.
- **Strategy:** scaffold structure + pure-logic + test harness *now*; capture fixtures and fill `_fetch_raw()` / real SQL / real coefficients *on work laptop*.

Further detail lives in the per-skill build plans. Start at [`docs/build_plans/README.md`](docs/build_plans/README.md).
