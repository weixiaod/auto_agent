"""
example_usage.py
----------------
Demonstrates how to configure and run ECMAttributor for a specific use case.
Replace feature_cols, coefficients, Y_0, and scenario DataFrames with your own.
"""

import pandas as pd
import numpy as np
from ecm_attribution import ECMAttributor

# ── 1. Define config (customize per use case) ─────────────────────────────────

config = {
    # Column names in your scenario DataFrames
    "feature_cols": ["price", "income", "rate"],

    # Short-run ECM coefficients: β per variable
    "short_run_coefs": {
        "price":  -0.30,
        "income":  0.50,
        "rate":   -0.10,
    },

    # ECM intercept (α)
    "intercept": 0.05,

    # Speed of adjustment (γ) — must be negative for a valid ECM
    "gamma": -0.25,

    # Long-run cointegrating equation coefficients
    "long_run_coefs": {
        "intercept": 2.0,
        "price":    -0.40,
        "income":    0.80,
        "rate":     -0.20,
    },

    # Initial Y level at t=0
    "Y_0": 150.0,

    # Forecast horizon (number of periods)
    "horizon": 27,
}

# ── 2. Prepare scenario DataFrames ────────────────────────────────────────────
# Wide format: one row per period, columns = X variable levels.
# Must have horizon+1 rows: row 0 = t=0 (initial), rows 1..27 = forecast periods.
# X values are LEVELS (not differences) — the model computes ΔX internally.

dates = pd.date_range("2024-01", periods=28, freq="MS")

scenario_a = pd.DataFrame({
    "date":   dates,
    "price":  np.linspace(100, 120, 28),   # gradual price increase
    "income": np.linspace(200, 230, 28),   # income grows
    "rate":   np.linspace(5.0, 4.0, 28),  # rate eases
})

scenario_b = pd.DataFrame({
    "date":   dates,
    "price":  np.linspace(100, 130, 28),   # steeper price increase vs A
    "income": np.linspace(200, 225, 28),   # slightly lower income vs A
    "rate":   np.linspace(5.0, 4.5, 28),  # rate stays higher vs A
})

# ── 3. Optional: human-readable labels for the waterfall chart ────────────────

waterfall_labels = {
    "attr_price":  "Price",
    "attr_income": "Income",
    "attr_rate":   "Interest Rate",
    "attr_ECT":    "Error Correction",
}

# ── 4. Run ────────────────────────────────────────────────────────────────────

model = ECMAttributor(config)
results = model.run(
    scenario_a,
    scenario_b,
    output_dir="./output",
    waterfall_labels=waterfall_labels,
    waterfall_title="ECM Attribution: Scenario A vs Scenario B (27-month cumulative)",
)

# ── 5. Inspect results ────────────────────────────────────────────────────────

print("\nPer-period attribution (first 5 rows):")
print(results["attribution"].head())

print("\nCumulative attribution by variable:")
attr_cols = [f"attr_{c}" for c in config["feature_cols"]] + ["attr_ECT", "total"]
print(results["attribution"][attr_cols].sum().to_string())
