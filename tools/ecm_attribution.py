"""
ecm_attribution.py
------------------
Generic Error Correction Model (ECM) attribution analysis tool.

Given two input scenarios (wide-format pandas DataFrames of X levels),
pre-specified ECM coefficients, and initial conditions, this module:
  1. Iteratively simulates Y_hat for each scenario over a specified horizon
  2. Decomposes the gap (Y_hat_A - Y_hat_B) by variable contribution per period
  3. Exports a per-period attribution CSV table and cumulative waterfall chart

Functional form:
  Long-run:   Y_t = a + Σ bi·Xi_t + u_t
  ECT_t       = Y_hat_t - (a + Σ bi·Xi_t)
  Short-run:  ΔY_hat_t = α + Σ βi·ΔXi_t + γ·ECT_(t-1)

Attribution decomposition (per period t):
  ΔY_A_t - ΔY_B_t = Σ βi·(ΔXi_A_t - ΔXi_B_t) + γ·(ECT_A_(t-1) - ECT_B_(t-1))

Usage:
    from ecm_attribution import ECMAttributor

    config = {
        "feature_cols":    ["price", "income", "rate"],
        "short_run_coefs": {"price": -0.3, "income": 0.5, "rate": -0.1},
        "intercept":       0.05,
        "gamma":           -0.25,
        "long_run_coefs":  {"intercept": 2.0, "price": -0.4, "income": 0.8, "rate": -0.2},
        "Y_0":             150.0,
        "horizon":         27,
    }

    model = ECMAttributor(config)
    results = model.run(scenario_a_df, scenario_b_df, output_dir="./output")
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path
from typing import Optional


class ECMAttributor:
    """
    Generic ECM attribution model. Extend to any use case by specifying
    feature_cols and coefficients in the config dict.

    Parameters
    ----------
    config : dict with keys:
        feature_cols    : list[str]  — X column names in scenario DataFrames
        short_run_coefs : dict       — {col: β} short-run ΔX coefficients
        intercept       : float      — α, ECM intercept (default 0.0)
        gamma           : float      — γ, speed of adjustment (should be negative)
        long_run_coefs  : dict       — {col: b, "intercept": a} long-run equation
        Y_0             : float      — initial level of Y at t=0
        horizon         : int        — number of periods to simulate (default 27)
    """

    def __init__(self, config: dict):
        self.feature_cols = config["feature_cols"]
        self.short_run_coefs = config["short_run_coefs"]
        self.intercept = config.get("intercept", 0.0)
        self.gamma = config["gamma"]
        self.long_run_coefs = config["long_run_coefs"]
        self.Y_0 = config["Y_0"]
        self.horizon = config.get("horizon", 27)

    # ------------------------------------------------------------------
    # Core helpers
    # ------------------------------------------------------------------

    def _compute_ect(self, Y: float, X_row: pd.Series) -> float:
        """ECT_t = Y_t - (a + Σ bi·Xi_t)"""
        lr = self.long_run_coefs
        fitted_lr = lr.get("intercept", 0.0) + sum(
            lr[col] * X_row[col] for col in self.feature_cols
        )
        return Y - fitted_lr

    # ------------------------------------------------------------------
    # Simulation
    # ------------------------------------------------------------------

    def simulate(self, scenario_df: pd.DataFrame) -> pd.DataFrame:
        """
        Iteratively simulate Y_hat over the horizon using the ECM.

        Parameters
        ----------
        scenario_df : pd.DataFrame
            Wide-format DataFrame with X levels. Must have at least horizon+1 rows.
            Row 0  = t=0 (initial conditions for X).
            Rows 1..horizon = t=1..horizon (forecast periods).

        Returns
        -------
        pd.DataFrame with columns:
            period, Y_hat, ECT, ECT_lag, delta_Y_hat, delta_{col} for each feature
        """
        df = scenario_df.reset_index(drop=True).copy()
        assert len(df) >= self.horizon + 1, (
            f"Scenario must have at least {self.horizon + 1} rows "
            f"(t=0 to t={self.horizon})."
        )

        records = []
        Y_hat = self.Y_0
        ECT_prev = self._compute_ect(Y_hat, df.iloc[0])

        for t in range(1, self.horizon + 1):
            row_t = df.iloc[t]
            row_t_minus_1 = df.iloc[t - 1]

            # First differences of X
            delta_X = {
                col: row_t[col] - row_t_minus_1[col]
                for col in self.feature_cols
            }

            # Short-run contributions
            sr_contributions = {
                col: self.short_run_coefs[col] * delta_X[col]
                for col in self.feature_cols
            }

            # ECM prediction
            delta_Y_hat = (
                self.intercept
                + sum(sr_contributions.values())
                + self.gamma * ECT_prev
            )

            # Update state
            Y_hat = Y_hat + delta_Y_hat
            ECT_curr = self._compute_ect(Y_hat, row_t)

            record = {
                "period":      t,
                "Y_hat":       Y_hat,
                "ECT":         ECT_curr,
                "ECT_lag":     ECT_prev,
                "delta_Y_hat": delta_Y_hat,
            }
            for col in self.feature_cols:
                record[f"delta_{col}"] = delta_X[col]

            records.append(record)
            ECT_prev = ECT_curr

        return pd.DataFrame(records)

    # ------------------------------------------------------------------
    # Attribution
    # ------------------------------------------------------------------

    def compute_attribution(
        self, sim_a: pd.DataFrame, sim_b: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Decompose (ΔY_hat_A - ΔY_hat_B) by variable per period.

        Attribution per variable per period t:
          attr_{col}_t = β_col · (Δcol_A_t - Δcol_B_t)
          attr_ECT_t   = γ · (ECT_lag_A_t - ECT_lag_B_t)
          total_t      = ΔY_hat_A_t - ΔY_hat_B_t
          residual_t   = total_t - Σ attr   (should be ~0, verification check)

        Parameters
        ----------
        sim_a, sim_b : outputs of simulate()

        Returns
        -------
        pd.DataFrame with columns:
            period, attr_{col} per feature, attr_ECT, total, residual
        """
        records = []

        for t in range(self.horizon):
            row_a = sim_a.iloc[t]
            row_b = sim_b.iloc[t]

            record = {"period": int(row_a["period"])}
            attr_sum = 0.0

            # Short-run variable attributions
            for col in self.feature_cols:
                delta_gap = row_a[f"delta_{col}"] - row_b[f"delta_{col}"]
                attr = self.short_run_coefs[col] * delta_gap
                record[f"attr_{col}"] = attr
                attr_sum += attr

            # ECT attribution
            ect_lag_gap = row_a["ECT_lag"] - row_b["ECT_lag"]
            attr_ect = self.gamma * ect_lag_gap
            record["attr_ECT"] = attr_ect
            attr_sum += attr_ect

            # Total and verification
            total = row_a["delta_Y_hat"] - row_b["delta_Y_hat"]
            record["total"] = total
            record["residual"] = total - attr_sum  # should be ~0

            records.append(record)

        return pd.DataFrame(records)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_csv(
        self, attribution_df: pd.DataFrame, output_dir: str = "."
    ) -> Path:
        """Export per-period attribution table to CSV."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        path = out / "attribution_table.csv"
        attribution_df.to_csv(path, index=False)
        print(f"[ECMAttributor] Attribution table saved to {path}")
        return path

    # ------------------------------------------------------------------
    # Waterfall plot
    # ------------------------------------------------------------------

    def plot_waterfall(
        self,
        attribution_df: pd.DataFrame,
        output_dir: str = ".",
        labels: Optional[dict] = None,
        title: str = "ECM Attribution — Scenario A vs B (Cumulative)",
        Y_A_final: Optional[float] = None,
        Y_B_final: Optional[float] = None,
    ) -> Path:
        """
        Generate a cumulative waterfall chart over the full horizon.

        Layout: Scenario A (final Y_hat) → attribution bars (A→B direction) → Scenario B (final Y_hat).
        Green bars = variable pushes from A up toward B. Red bars = variable pulls A down toward B.

        Parameters
        ----------
        attribution_df : output of compute_attribution()
        output_dir     : directory to save waterfall.png
        labels         : optional display name override, e.g.
                         {"attr_price": "Price", "attr_ECT": "Error Correction"}
        title          : chart title string
        Y_A_final      : final Y_hat value for Scenario A (from simulate())
        Y_B_final      : final Y_hat value for Scenario B (from simulate())
        """
        attr_cols = [f"attr_{col}" for col in self.feature_cols] + ["attr_ECT"]
        cumulative = attribution_df[attr_cols].sum()

        # Build display labels
        default_labels = {f"attr_{col}": col for col in self.feature_cols}
        default_labels["attr_ECT"] = "ECT"
        if labels:
            default_labels.update(labels)
        display_names = [default_labels.get(k, k) for k in cumulative.index]

        # Negate attributions: we go from A to B, so a positive attr (A > B) is a decrease
        negated = -cumulative.values

        # Full bar sequence: [Y_A] + [negated attrs] + [Y_B]
        all_values = ([Y_A_final] if Y_A_final is not None else []) + \
                     list(negated) + \
                     ([Y_B_final] if Y_B_final is not None else [])
        all_labels = (["Scenario A"] if Y_A_final is not None else []) + \
                     display_names + \
                     (["Scenario B"] if Y_B_final is not None else [])

        # Compute floating bottoms
        bottoms = []
        if Y_A_final is not None:
            bottoms.append(0.0)           # Scenario A anchored at 0
            running = Y_A_final
        else:
            running = 0.0

        for v in negated:
            bottoms.append(running if v >= 0 else running + v)
            running += v

        if Y_B_final is not None:
            bottoms.append(0.0)           # Scenario B anchored at 0

        # Colors
        colors = []
        if Y_A_final is not None:
            colors.append("#4C72B0")      # Scenario A — blue
        for v in negated:
            colors.append("#55A868" if v >= 0 else "#C44E52")  # green up / red down
        if Y_B_final is not None:
            colors.append("#4C72B0")      # Scenario B — blue

        fig, ax = plt.subplots(figsize=(max(8, len(all_labels) * 1.4), 6))
        bars = ax.bar(
            all_labels,
            [abs(v) for v in all_values],
            bottom=bottoms,
            color=colors,
            edgecolor="white",
            linewidth=0.8,
            width=0.6,
        )

        # Value labels on each bar
        y_scale = max(abs(v) for v in all_values) * 0.015 if all_values else 0.01
        for bar, val in zip(bars, all_values):
            label_y = bar.get_y() + bar.get_height() + y_scale
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                label_y,
                f"{val:,.2f}",
                ha="center", va="bottom", fontsize=9, fontweight="bold",
            )

        # Connector lines between attribution bars (not to/from scenario bars)
        start_idx = 1 if Y_A_final is not None else 0
        end_idx = len(all_values) - (2 if Y_B_final is not None else 1)
        running = Y_A_final if Y_A_final is not None else 0.0
        for i in range(start_idx, end_idx):
            running += negated[i - start_idx]
            ax.plot(
                [i + 0.3, i + 0.7],
                [running, running],
                color="gray", linewidth=0.8, linestyle="--",
            )

        # Legend
        legend_handles = [
            mpatches.Patch(color="#4C72B0", label="Scenario level"),
            mpatches.Patch(color="#55A868", label="Increases toward B"),
            mpatches.Patch(color="#C44E52", label="Decreases toward B"),
        ]
        ax.legend(handles=legend_handles, fontsize=9, loc="best")

        ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
        ax.set_ylabel("Y (cumulative forecast)", fontsize=10)
        ax.set_xlabel("Variable", fontsize=10)
        ax.axhline(0, color="black", linewidth=0.8)
        plt.xticks(rotation=20, ha="right")
        plt.tight_layout()

        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        path = out / "waterfall.png"
        plt.savefig(path, dpi=150)
        plt.close()
        print(f"[ECMAttributor] Waterfall chart saved to {path}")
        return path

    # ------------------------------------------------------------------
    # Full pipeline
    # ------------------------------------------------------------------

    def run(
        self,
        scenario_a: pd.DataFrame,
        scenario_b: pd.DataFrame,
        output_dir: str = "./output",
        waterfall_labels: Optional[dict] = None,
        waterfall_title: str = "ECM Attribution — Scenario A vs B (Cumulative)",
    ) -> dict:
        """
        Full pipeline: simulate both scenarios → attribute → export CSV + waterfall.

        Parameters
        ----------
        scenario_a, scenario_b : wide-format DataFrames (X levels, horizon+1 rows)
        output_dir             : directory for outputs
        waterfall_labels       : optional label overrides for waterfall chart
        waterfall_title        : waterfall chart title

        Returns
        -------
        dict with keys: sim_a, sim_b, attribution, csv_path, chart_path
        """
        print("[ECMAttributor] Simulating Scenario A...")
        sim_a = self.simulate(scenario_a)

        print("[ECMAttributor] Simulating Scenario B...")
        sim_b = self.simulate(scenario_b)

        print("[ECMAttributor] Computing attribution...")
        attribution = self.compute_attribution(sim_a, sim_b)

        total_gap = attribution["total"].sum()
        residual = attribution["residual"].abs().sum()
        print(f"[ECMAttributor] Cumulative Y gap (A - B): {total_gap:.4f}")
        print(f"[ECMAttributor] Total unexplained residual (should be ~0): {residual:.2e}")

        csv_path = self.export_csv(attribution, output_dir)
        chart_path = self.plot_waterfall(
            attribution, output_dir, waterfall_labels, waterfall_title,
            Y_A_final=float(sim_a["Y_hat"].iloc[-1]),
            Y_B_final=float(sim_b["Y_hat"].iloc[-1]),
        )

        return {
            "sim_a":       sim_a,
            "sim_b":       sim_b,
            "attribution": attribution,
            "csv_path":    csv_path,
            "chart_path":  chart_path,
        }
