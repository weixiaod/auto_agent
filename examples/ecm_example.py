"""
ecm_example.py
--------------
Example script for running ECM attribution analysis.
Loads model config from config/model_config.json and scenario data from data/.
Replace scenario DataFrames with your actual input data.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from ecm_attribution import ECMAttributor

# ── 1. Load config ────────────────────────────────────────────────────────────
with open(ROOT / "config" / "model_config.json") as f:
    cfg = json.load(f)

# ── 2. Prepare scenario DataFrames ────────────────────────────────────────────
# Wide format: X variable levels, horizon+1 rows (row 0 = t=0 initial conditions).
# Replace these with your actual scenario data, e.g.:
#   scenario_a = pd.read_csv(ROOT / "data" / "scenario_a.csv")
#   scenario_b = pd.read_csv(ROOT / "data" / "scenario_b.csv")

horizon = cfg["horizon"]
dates = pd.date_range("2024-01", periods=horizon + 1, freq="MS")

scenario_a = pd.DataFrame({
    "date":   dates,
    "price":  np.linspace(100, 120, horizon + 1),
    "income": np.linspace(200, 230, horizon + 1),
    "rate":   np.linspace(5.0, 4.0, horizon + 1),
})

scenario_b = pd.DataFrame({
    "date":   dates,
    "price":  np.linspace(100, 130, horizon + 1),
    "income": np.linspace(200, 225, horizon + 1),
    "rate":   np.linspace(5.0, 4.5, horizon + 1),
})

# ── 3. Run ────────────────────────────────────────────────────────────────────
model = ECMAttributor(cfg)
results = model.run(
    scenario_a,
    scenario_b,
    output_dir=str(ROOT / "outputs"),
    waterfall_labels=cfg.get("waterfall_labels"),
    waterfall_title=f"ECM Attribution: Scenario A vs B ({horizon}-month cumulative)",
)

# ── 4. Inspect results ────────────────────────────────────────────────────────
print("\nPer-period attribution (first 5 rows):")
print(results["attribution"].head())

print("\nCumulative attribution by variable:")
attr_cols = [f"attr_{c}" for c in cfg["feature_cols"]] + ["attr_ECT", "total"]
print(results["attribution"][attr_cols].sum().to_string())
