"""
skills/ecm_attribution.py
--------------------------
ECM attribution skill — runs all 12 ECM models and returns structured results.

Models covered:
  pricing        × 6 segments  (new/used × prime/near_prime/sub_prime)
  count          × 3 segments  (prime/near_prime/sub_prime)
  avg_loan_amount× 3 segments  (prime/near_prime/sub_prime)

Volume (count × avg_loan_amount) is a separate step — not included here.

Each model runs independently via ECMAttributor. Outputs land in:
  {output_dir}/{model_type}/{segment}/attribution_table.csv
  {output_dir}/{model_type}/{segment}/waterfall.png

Usage:
    from skills.ecm_attribution import run_ecm_attribution

    results = run_ecm_attribution(
        scenario_a=df_stress,      # wide DataFrame, all macro variables, horizon+1 rows
        scenario_b=df_baseline,    # same structure
        cfg=model_cfg,             # loaded from config/model_config.json
        output_dir="./outputs/run_20260414",
    )
    # results["pricing"]["new_prime"]["attribution"]  -> DataFrame
    # results["count"]["prime"]["sim_a"]              -> DataFrame
"""

import json
import logging
from pathlib import Path

import pandas as pd

from tools.ecm_attribution import ECMAttributor

logger = logging.getLogger(__name__)

# Canonical model registry — order within each type is fixed
MODEL_REGISTRY: dict[str, list[str]] = {
    "pricing":         ["new_prime", "new_near_prime", "new_sub_prime",
                        "used_prime", "used_near_prime", "used_sub_prime"],
    "count":           ["prime", "near_prime", "sub_prime"],
    "avg_loan_amount": ["prime", "near_prime", "sub_prime"],
}


def _validate_model_cfg(model_type: str, segment: str, model_cfg: dict) -> None:
    """
    Raise a clear error if any required coefficient fields are still placeholder/null.
    Called before instantiating ECMAttributor — fail loud, not silently.
    """
    required = [
        "feature_short_cols", "feature_long_cols",
        "short_run_coefs", "long_run_coefs",
        "intercept", "gamma", "Y_0",
    ]
    missing = [k for k in required if model_cfg.get(k) is None]
    if missing:
        raise ValueError(
            f"[ecm_attribution skill] config/model_config.json is incomplete for "
            f"{model_type}/{segment}. Fill in from work machine before running. "
            f"Missing / null fields: {missing}"
        )

    placeholder_cols = [
        c for c in (model_cfg.get("feature_short_cols", []) +
                    model_cfg.get("feature_long_cols", []))
        if c == "PLACEHOLDER"
    ]
    if placeholder_cols:
        raise ValueError(
            f"[ecm_attribution skill] feature columns are still PLACEHOLDER for "
            f"{model_type}/{segment}. Fill in from work machine before running."
        )


def run_ecm_attribution(
    scenario_a: pd.DataFrame,
    scenario_b: pd.DataFrame,
    cfg: dict,
    output_dir: str = "./outputs",
    waterfall_title_prefix: str = "ECM Attribution",
) -> dict:
    """
    Run ECM attribution for all 12 models (pricing × 6, count × 3, avg_loan_amount × 3).

    Parameters
    ----------
    scenario_a : pd.DataFrame
        Wide-format macro scenario DataFrame. Columns must include all variables
        referenced across feature_short_cols and feature_long_cols for every model.
        Must have horizon + 1 rows (row 0 = t0, rows 1..horizon = forecast periods).
    scenario_b : pd.DataFrame
        Same structure as scenario_a (the comparison scenario).
    cfg : dict
        Loaded contents of config/model_config.json.
    output_dir : str
        Root output directory. Each model writes to {output_dir}/{model_type}/{segment}/.
    waterfall_title_prefix : str
        Prefix for waterfall chart titles, e.g. "CCAR 2026 Q1 Attribution".

    Returns
    -------
    dict
        Nested structure: results[model_type][segment] = {
            "sim_a":       pd.DataFrame,   # simulated Y_hat path for scenario A
            "sim_b":       pd.DataFrame,   # simulated Y_hat path for scenario B
            "attribution": pd.DataFrame,   # per-period attribution by variable
            "csv_path":    Path,
            "chart_path":  Path,
        }
        Failed models are stored as {"error": str} — they do not abort the run.
    """
    horizon = cfg.get("horizon", 27)
    results: dict = {}
    failed: list[str] = []

    for model_type, segments in MODEL_REGISTRY.items():
        results[model_type] = {}

        for segment in segments:
            label = f"{model_type}/{segment}"

            try:
                model_cfg = cfg[model_type][segment]
                _validate_model_cfg(model_type, segment, model_cfg)

                # Inject shared horizon — models don't store it individually
                model_cfg = {**model_cfg, "horizon": horizon}

                attributor = ECMAttributor(model_cfg)

                segment_output_dir = str(Path(output_dir) / model_type / segment)
                title = f"{waterfall_title_prefix} — {label}"

                logger.info(f"[ecm_attribution] Running {label}...")
                run_result = attributor.run(
                    scenario_a=scenario_a,
                    scenario_b=scenario_b,
                    output_dir=segment_output_dir,
                    waterfall_title=title,
                )
                results[model_type][segment] = run_result
                logger.info(f"[ecm_attribution] {label} complete. "
                            f"Cumulative gap: {run_result['attribution']['total'].sum():.4f}")

            except Exception as exc:
                logger.error(f"[ecm_attribution] {label} failed: {exc}")
                results[model_type][segment] = {"error": str(exc)}
                failed.append(label)

    if failed:
        logger.warning(
            f"[ecm_attribution] {len(failed)} model(s) failed and were skipped: {failed}. "
            f"Check logs. Successful models are still returned."
        )

    return results


def load_results_summary(results: dict) -> pd.DataFrame:
    """
    Flatten results into a summary DataFrame for quick inspection.
    Rows: one per model. Columns: model_type, segment, cumulative_gap, status.
    """
    rows = []
    for model_type, segments in results.items():
        for segment, result in segments.items():
            if "error" in result:
                rows.append({
                    "model_type": model_type,
                    "segment":    segment,
                    "status":     "failed",
                    "cumulative_gap": None,
                    "error":      result["error"],
                })
            else:
                gap = result["attribution"]["total"].sum()
                rows.append({
                    "model_type": model_type,
                    "segment":    segment,
                    "status":     "ok",
                    "cumulative_gap": round(gap, 4),
                    "error":      None,
                })
    return pd.DataFrame(rows)
