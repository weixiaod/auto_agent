# actuals_replacement — Actuals replacement skill + tool (Outlook only)

**Scope:** in Outlook mode, replace model output for periods that have already occurred with realized auto-loan actuals, and compute the backtesting-error DataFrame fed into ECM attribution.

**Dependencies:**
- `00_foundation.md` — `tools/errors.py` (`DataAcquisitionError` or a new `ReplacementError` — see `[GRILL]`), `DateAlignmentError`
- `data_acquisition.md` — auto_loan intermediate dict supplies realized values
- `model_execution.md` — model output DataFrame is the thing being adjusted

**Blocks:**
- `ecm_attribution.md` Outlook path (consumes `backtesting_error_df`)
- `analysis.md` Outlook path (consumes adjusted model output)

**Runs in:** Outlook mode only. CCAR mode skips this skill entirely.

---

## T1.3 — `skills/actuals_replacement/`

**Files:** `skills/actuals_replacement/SKILL.md`, `skills/actuals_replacement/skill.py`

**What to build:**
- `skill.py` exposes `run(model_output, auto_loan_data, prior_cycle_output, t0_date) -> dict`. Returns `{"adjusted_output": DataFrame, "backtesting_error": DataFrame}`.
  - `adjusted_output` = `actuals_replacer.replace_realized(model_output, actuals, t0_date)`.
  - `backtesting_error` = realized actuals − prior_cycle_output values, over the overlapping realized periods.
- `SKILL.md` — frontmatter `name: actuals-replacement`, trigger prose (Outlook mode only, after model_execution), invocation instructions.

**Critical:** `backtesting_error` shape must match what `ecm_attribution.run_outlook` expects. This is the integration contract.

**Validation:** `[GRILL]` — decide test strategy, likely fixture-driven integration given pure inputs/outputs.

---

## T2.8 — `tools/actuals_replacer.py`

**Files:** `tools/actuals_replacer.py`

**What to build:** `replace_realized(model_output, actuals, t0_date) -> pd.DataFrame` — pure function.

- Replaces rows where `date <= today` with matched actuals.
- Matches on `(variable, segment, date)`.
- Raises `DateAlignmentError` if any realized period in model_output has no actuals match.

**Fixtures:**
- `tests/fixtures/actuals_replacer/input_model_output.csv`
- `tests/fixtures/actuals_replacer/input_actuals.csv`
- `tests/fixtures/actuals_replacer/expected_adjusted.csv`
- `tests/fixtures/actuals_replacer/input_t0_date.json` (single-key)

**Validation:**
```bash
pytest tests/test_actuals_replacer.py
```
Pure function — should be quickest tool to validate.

---

## `[GRILL]` — polish targets for this build plan

- [ ] **"Realized period" definition.** Is it strictly `date <= today` or `date <= t0_date`? They may differ: t0 is the assessment as-of date; "today" is when the pipeline runs. Realized means actuals exist.
- [ ] **Match granularity.** `(variable, segment, date)` — does date need exact equality or can it be period-start alignment (first of month, etc.)? What if auto_loan actuals come monthly but model output is weekly (or vice versa)?
- [ ] **Partial coverage.** What if actuals cover some but not all realized periods? Raise `DateAlignmentError` or replace what we can and flag the rest?
- [ ] **`backtesting_error_df` column contract.** Columns, keying. Must match `ecm_attribution.run_outlook`'s expected input exactly.
- [ ] **Prior cycle output format.** Long-format CSV — same schema as model output? Different t0? How do we align realized periods across the two?
- [ ] **What about variables with no actuals?** Pricing (APR) — are there realized actuals for pricing, or only count / avg_loan_amount? If pricing has no actuals, does backtesting_error apply only to volume-related variables?
- [ ] **Should `skill.run()` also accept the auto_loan intermediate dict, or pre-sliced actuals?** The skill-to-tool boundary.
- [ ] **Error class.** Does it make sense to keep all errors under `DataAcquisitionError`, or does this stage deserve its own `ReplacementError`?

---

## Locked for this skill

- Outlook-only skill; CCAR skips it.
- Pure function at the tool level (no I/O, no side effects).
- `backtesting_error_df` is fed to `ecm_attribution.run_outlook` as a **distinct waterfall bar** — it's not rolled into variable attributions.
- Raises `DateAlignmentError` on mismatched realized periods.
