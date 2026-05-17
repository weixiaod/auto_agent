# ecm_attribution — ECM Attribution skill + tool

**Scope:** rename the existing skill folder, reshape the skill for the 12-model reality, and extend `ECMAttributor` to handle Outlook (different-t0) mode with a distinct backtesting-error waterfall bar.

**Dependencies:**
- `00_foundation.md` — `tools/errors.py` (for `AttributionError`, `DifferentT0Error`), `tools/logging.py`
- `config/model_config.json` — must hold the nested 12-model coefficient structure (pricing × 6, count × 3, avg_loan_amount × 3)

**Blocks:**
- `reporting.md` (consumes attribution results)

**Starting state:** working vertical slice exists at `tools/ecm_attribution.py` + `skills/ecm-attribution/SKILL.md` + stray `skills/ecm_attribution.py`. CCAR (same-t0) path works. Outlook (different-t0) path does not exist yet.

**Invocation model:** attribution is a **cross-run analysis**, not a stage in a single pipeline run. Each CCAR scenario (FRBB, FRBSA, BHCB, BHCS) and each Outlook cycle is its own pipeline run producing its own saved model-output file. Attribution is invoked separately with two such files as input.

---

## T0.4 — Rename `skills/ecm-attribution/` → `skills/ecm_attribution/` + absorb the stray file

**Files:**
- Rename: `skills/ecm-attribution/` → `skills/ecm_attribution/`
- Move: `skills/ecm_attribution.py` → `skills/ecm_attribution/skill.py`

**Steps:**
1. `git mv skills/ecm-attribution skills/ecm_attribution`
2. `git mv skills/ecm_attribution.py skills/ecm_attribution/skill.py`
3. Update any imports referencing `skills.ecm_attribution` as a module path (should work naturally post-rename).
4. Leave `SKILL.md` untouched; it's updated in T1.5.

**Validation:**
```bash
python -c "from skills.ecm_attribution.skill import run_ecm_attribution, MODEL_REGISTRY; print('ok', len(MODEL_REGISTRY))"
```
Expected: `ok 3` (three model types: pricing, count, avg_loan_amount).

---

## T1.5 — Reshape `skills/ecm_attribution/` + Outlook path

**Files:** `skills/ecm_attribution/SKILL.md` (update), `skills/ecm_attribution/skill.py` (update)

**Depends on:** T0.4 (move), T2.9 (Outlook extension in the tool)

**What to build:**

1. **Update `SKILL.md`** — frontmatter and trigger prose to reflect 12-model reality. Agent invokes this as a **cross-run** step with two saved run outputs (or two DataFrames already in memory). Two entry points:
   - CCAR pairing (same t0; e.g. FRBSA26 vs FRBB26): `run_ecm_attribution(stress_df_or_path, baseline_df_or_path, cfg, output_dir)`
   - Outlook pairing (different t0; current cycle vs prior cycle): `run_ecm_attribution_outlook(current_df_or_path, prior_df_or_path, backtesting_error_df, cfg, output_dir)`

   Both entry points accept either a DataFrame (programmatic use) or a path to a saved enterprise-output CSV (manual post-hoc pairing).

2. **Update `skill.py`:**
   - CCAR path already works (current `run_ecm_attribution`).
   - Add Outlook path: accepts `backtesting_error_df`, delegates to `ECMAttributor.run_outlook`.
   - Output dir: `{output_dir}/{model_type}/{segment}/` — one waterfall PNG + one attribution CSV per model (12 total).

**Fixtures:**
- `tests/fixtures/ecm_attribution/scenario_a.csv` — wide DataFrame, all vars, `horizon+1` rows
- `tests/fixtures/ecm_attribution/scenario_b.csv` — same
- `tests/fixtures/ecm_attribution/model_cfg_subset.json` — minimal cfg covering 1–2 models for speed
- `tests/fixtures/ecm_attribution/expected_attribution_<model_type>_<segment>.csv`

**Capture guide:**
- Pick one pricing model (e.g., `new_prime`) and one count model (e.g., `prime`) for the fixture set.
- Run existing CCAR workflow on work laptop with known inputs.
- Save attribution table CSVs + exact cfg dicts used.

**Validation:**
```bash
pytest tests/test_skill_ecm_attribution.py
```
Iterate `skill.py` / `ECMAttributor` until attribution tables match within tolerance.

---

## T2.9 — `tools/ecm_attribution.py` — Outlook extension

**Files:** `tools/ecm_attribution.py` (edit existing)

**What to build:** Extend `ECMAttributor` with Outlook (different-t0) handling.

New method:
```python
def run_outlook(
    self,
    current_scenario_df: pd.DataFrame,
    prior_scenario_df: pd.DataFrame,
    backtesting_error_df: pd.DataFrame,
    output_dir: str,
    ...
) -> dict
```

Behavior:
- Accepts two scenario DataFrames with **different** t0s.
- Accepts `backtesting_error_df` (realized − prior_forecast for overlapping realized periods) — produced by `actuals_replacement` skill.
- Decomposes gap into: variable attributions + ECT + **backtesting error bar** (distinct bar, distinct color).
- Writes one waterfall per model with the backtesting-error bar rendered as a distinct color.

Existing `run()` (CCAR same-t0) remains unchanged.

**Fixtures:**
- Reuse existing ECM fixtures for CCAR assertion.
- New: `tests/fixtures/ecm_attribution_outlook/{current.csv, prior.csv, backtesting_error.csv, expected_attribution.csv}`

**Validation:**
```bash
pytest tests/test_ecm_attribution_outlook.py
```
Assertions:
- Attribution total = (current Y_hat final − prior Y_hat final)
- Residual ≈ 0
- Backtesting_error bar magnitude equals sum of `backtesting_error_df` values

---

## `[GRILL]` — polish targets for this build plan

- [ ] **Outlook `run_outlook` signature.** Exact arg names and types. Does it return a dict keyed by `(model_type, segment)`? What about the waterfall PNG paths — returned in the dict or written to disk only?
- [ ] **`backtesting_error_df` shape contract.** Columns, keying, date semantics. This is the handoff from `actuals_replacement` and must match on both sides.
- [ ] **Output dir structure.** Confirm `{output_dir}/{model_type}/{segment}/` is right; filenames for waterfall PNG and attribution CSV.
- [ ] **Different-t0 decomposition math.** The CCAR decomposition assumes same t0. For Outlook, how exactly do we allocate across variables when the forecast horizons don't align? (Split into overlapping + non-overlapping windows? Rebase to current t0?)
- [ ] **`new_origination_volume` handling.** Derived as count × avg_loan_amount — is it a separate waterfall (13th chart) or not a waterfall at all since it has no ECM?
- [ ] **Skill-level test strategy.** Monkeypatch `ECMAttributor` in the skill test? Or let the skill test be an integration test hitting the real attributor?
- [ ] **`MODEL_REGISTRY` shape.** Current `len == 3` (three model types). Does the registry enumerate all 12 (model_type, segment) pairs, or stay at 3 types with segments looked up separately?
- [ ] **Failure modes.** What errors from `AttributionError` / `DifferentT0Error` do we raise and when?

---

## Locked for this skill

- CCAR path: existing `run()` works, reshape only for folder/import.
- 12 models = pricing × {new_prime, new_near_prime, new_sub_prime, used_prime, used_near_prime, used_sub_prime} + count × {prime, near_prime, sub_prime} + avg_loan_amount × {prime, near_prime, sub_prime}.
- Each model has per-model `feature_short_cols` + `feature_long_cols` coefficient sets in `model_config.json`.
- Backtesting error is a **distinct waterfall bar**, not rolled into variable attributions.
