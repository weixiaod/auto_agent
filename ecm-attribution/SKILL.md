---
name: ecm-attribution
description: >
  Performs ECM (Error Correction Model) attribution analysis given two input scenarios.
  Use this skill whenever the user wants to: compare two economic scenarios using an ECM,
  decompose the gap between two forecasts by variable contribution, run ECM attribution,
  explain what drives the difference between scenario A and scenario B, or produce a
  waterfall chart and attribution table from an error correction model. Trigger even if
  the user just says "run the attribution", "compare my two scenarios", or "what's driving
  the gap" in the context of an ECM or econometric model.
---

# ECM Attribution Skill

You help the user run an attribution analysis using the `ECMAttributor` class at:
`/Users/smile/projects/auto_agent/ecm_attribution.py`

The tool simulates two scenarios forward using an ECM, then decomposes the gap in
predicted Y between them — period by period and cumulatively — by variable contribution.
Output is a waterfall chart (`waterfall.png`) and a per-period CSV (`attribution_table.csv`).

---

## What you need from the user

Gather these inputs before running. Some may already be in the conversation:

### 1. ECM coefficients (the model spec)

```python
config = {
    "feature_cols":    [...],          # list of X variable names
    "short_run_coefs": {col: β, ...},  # short-run ΔX coefficients
    "intercept":       α,              # ECM intercept (float, often small)
    "gamma":           γ,              # speed of adjustment — must be negative
    "long_run_coefs":  {"intercept": a, col: b, ...},  # cointegrating equation
    "Y_0":             float,          # initial level of Y at t=0
    "horizon":         27,             # number of periods (default 27 months)
}
```

**If coefficients are missing:** Ask the user to provide them, or check if they're
defined in a config file or earlier in the conversation. Do not guess or make up values.

### 2. Two scenario DataFrames

- **Format:** wide pandas DataFrame, X variables as levels (not differences)
- **Rows:** `horizon + 1` rows — row 0 is t=0 (initial conditions), rows 1..N are forecast periods
- **Columns:** one column per variable in `feature_cols`, plus optionally a `date` column

The user may provide these as:
- Python code that constructs the DataFrames
- CSV files to load
- Description of how to build them (e.g., "A is baseline, B is a price shock")

### 3. Output location
Default: `./output/` relative to the working directory. Ask only if the user cares.

---

## How to run the analysis

Once you have everything, write and execute a Python script. Keep it concise — the heavy
lifting is done by `ECMAttributor`. A minimal script looks like:

```python
import sys
sys.path.insert(0, "/Users/smile/projects/auto_agent")

import pandas as pd
import numpy as np
from ecm_attribution import ECMAttributor

# --- Config ---
config = { ... }  # fill in from user's spec

# --- Scenarios (wide format, X levels, horizon+1 rows) ---
scenario_a = pd.DataFrame({ ... })
scenario_b = pd.DataFrame({ ... })

# --- Optional: human-readable labels for waterfall ---
labels = { f"attr_{col}": "Display Name" for col in config["feature_cols"] }
labels["attr_ECT"] = "Error Correction"

# --- Run ---
model = ECMAttributor(config)
results = model.run(
    scenario_a,
    scenario_b,
    output_dir="./output",
    waterfall_labels=labels,
    waterfall_title="ECM Attribution: Scenario A vs B (27-month cumulative)",
)

# --- Summary ---
attr_cols = [f"attr_{c}" for c in config["feature_cols"]] + ["attr_ECT", "total"]
print(results["attribution"][attr_cols].sum().round(4).to_string())
print(f"\nUnexplained residual: {results['attribution']['residual'].abs().sum():.2e}")
```

Save the script to a temp file and run it with `python`. Check that the printed residual
is near zero (< 1e-10) — if not, there's likely a coefficient mismatch.

---

## Interpreting and explaining results

After running, always explain the output in plain language. Cover:

1. **Total gap:** "Scenario A's Y ends up X.XX higher/lower than Scenario B over 27 months."
2. **Biggest driver:** Which variable contributed most to the gap and why (relate back to coefficient signs and scenario differences).
3. **ECT contribution:** The error correction term captures how prior disequilibrium feeds forward — if ECT attribution grows over time it means the scenarios diverge in their long-run equilibrium path.
4. **Short-run vs long-run split:** Sum of `attr_{col}` columns = short-run X effects; `attr_ECT` = error correction / long-run feedback.
5. **Residual check:** Confirm attribution is exact (residual ≈ 0).

Tell the user where to find the outputs:
- `./output/waterfall.png` — cumulative waterfall chart
- `./output/attribution_table.csv` — per-period attribution by variable

---

## Common issues and fixes

| Problem | Fix |
|---|---|
| `gamma` is positive | Remind user ECM requires γ < 0 for stability |
| `ModuleNotFoundError: ecm_attribution` | Ensure `sys.path.insert(0, "/Users/smile/projects/auto_agent")` is at the top |
| Scenario has wrong number of rows | Must be `horizon + 1` rows (t=0 through t=horizon) |
| Large residual | Check that `short_run_coefs` keys exactly match `feature_cols` |
| Missing `long_run_coefs` intercept | Default is 0.0 if omitted — clarify with user |

---

## Extending to new use cases

This tool is generic. Any ECM can be plugged in by changing `config`. When the user wants
to apply this to a new domain (e.g., housing demand, retail sales, GDP components), just
update `feature_cols` and the coefficient dicts — the core `ECMAttributor` class does not
need to change.
