# analysis — Analysis skill + fixed/exploratory tools

**Scope:** compute fixed metrics on the model output (always runs), optionally run exploratory helpers (detects outliers, concentration, trend breaks). Fixed section is deterministic and fixture-testable; exploratory section is agent-driven.

**Dependencies:**
- `00_foundation.md` — `tools/errors.py` (`AnalysisError`), `tools/logging.py`
- `model_execution.md` — consumes model output long-format DataFrame (or Outlook-adjusted version)

**Blocks:**
- `reporting.md` (consumes `fixed_results` dict)

---

## T1.4 — `skills/analysis/`

**Files:** `skills/analysis/SKILL.md`, `skills/analysis/skill.py`

**What to build:**
- `skill.py` exposes `run(model_output, prior_cycle_output=None, mode) -> dict`. Returns `{"fixed": fixed_results, "exploratory": exploratory_findings}`.
  - Always runs `fixed_analysis.run_fixed_analysis(...)`.
  - Optionally runs exploratory helpers in a `try/except` that **never** raises — any exception is caught, logged, and `exploratory` returns `{"error": str}`.
- `SKILL.md` — frontmatter `name: analysis`, trigger prose, invocation instructions. Includes judgment prose for the agent on how to interpret exploratory findings (always label as interpretation, not fact).

**Validation:** `[GRILL]`. Fixed-analysis tool is fixture-tested (T2.10). Skill orchestration may be prose-only or lightly tested.

---

## T2.10 — `tools/analysis/fixed_analysis.py`

**Files:** `tools/analysis/fixed_analysis.py`, `tools/analysis/__init__.py`

**What to build:** `run_fixed_analysis(model_output, prior_cycle_output=None, mode) -> dict` — pure. Computes:

**Always:**
- Two-year total new origination (count + amount_financed) by segment
- Average amount_financed by segment
- Average APR (from pricing model output) by segment
- Year-over-year change within the current run

**Outlook mode additionally:**
- Prior cycle comparison — current vs prior for count, amount, APR per segment

Returns nested dict keyed by metric → segment → value.

**Fixtures:**
- `tests/fixtures/fixed_analysis/input_model_output.csv`
- `tests/fixtures/fixed_analysis/input_prior_cycle.csv`
- `tests/fixtures/fixed_analysis/expected_results.json`

**Validation:**
```bash
pytest tests/test_fixed_analysis.py
```

---

## T2.11 — `tools/analysis/exploratory_helpers.py`

**Files:** `tools/analysis/exploratory_helpers.py`

**What to build:**
- `detect_outliers(df, threshold=2.5) -> pd.DataFrame` — pure. Returns rows flagged as outliers.
- `compare_to_baseline(df, baseline_scenario) -> pd.DataFrame` — pure. Returns per-variable, per-segment deltas.

**Fixtures:** Constructed inline in tests (synthetic) — these are pure stats, no real-data capture needed.

**Validation:**
```bash
pytest tests/test_exploratory_helpers.py
```

---

## `[GRILL]` — polish targets for this build plan

- [ ] **"Two-year" definition.** Is the horizon exactly 24 months from t0? Or Y1 + Y2 calendar years? Does it use forecast periods only or include replaced actuals?
- [ ] **amount_financed vs volume.** The old language said `amount_financed`. The new reality has `avg_loan_amount` + `count` with `new_origination_volume = count × avg_loan_amount`. Fixed analysis reports "total amount" — is that `sum(avg_loan_amount × count)` per period, or is there a top-line volume variable?
- [ ] **Segment handling.** Pricing has 6 segments; count + avg_loan_amount have 3. How does fixed analysis reconcile — report per-segment with unavailable segments as None, or split into two tables?
- [ ] **YoY definition.** Year-over-year within the current run — Y2 vs Y1? First 12 months vs next 12? Calendar year aligned?
- [ ] **Prior cycle comparison metric set.** Which of {count, amount, APR, volume} get a current-vs-prior entry, and what's the aggregation (sum over horizon, annual averages)?
- [ ] **Output dict schema.** Lock the exact key hierarchy. reporting.md will consume this — it needs a fixed contract.
- [ ] **Exploratory scope.** Agent-driven means the agent calls these functions when it sees something worth investigating. Does the skill also run a default pass (e.g., always call `detect_outliers`), or purely on-demand?
- [ ] **Exploratory error policy.** Skill catches and logs — where does the error land for the agent to see? In the returned dict, in the log only, or surfaced to the user?

---

## Locked for this skill

- Fixed analysis always runs. Exploratory is best-effort.
- Exploratory errors never block the pipeline.
- Tools are pure (no I/O, no side effects).
- Exploratory findings are always labeled as interpretation, not fact, in the agent output.
