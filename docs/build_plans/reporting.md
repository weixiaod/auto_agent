# reporting — Reporting skill + Excel builder

**Scope:** populate a structured Excel template with fixed analysis results, exploratory findings, and attribution results; write a timestamped file to `outputs/`.

**Dependencies:**
- `00_foundation.md` — `tools/errors.py` (`ReportingError`, `TemplateError`), `tools/logging.py`, `pyproject.toml` (`openpyxl`)
- `analysis.md` — consumes `fixed_results` dict
- `ecm_attribution.md` — consumes attribution results (12 waterfalls + tables)
- `templates/report_template.xlsx` — **user-supplied, not yet in repo**. Blocks most of this work.

**Blocked by:** user supplying `templates/report_template.xlsx`.

---

## T1.6 — `skills/reporting/`

**Files:** `skills/reporting/SKILL.md`, `skills/reporting/skill.py`

**What to build:**
- `skill.py` exposes `run(fixed_results, exploratory_findings, attribution_results, prior_cycle_path=None, template_path="templates/report_template.xlsx") -> str`. Delegates to `excel_builder.build_report(...)`. Returns the output file path.
- `SKILL.md` — frontmatter `name: reporting`, trigger prose (run at end of pipeline), invocation instructions.

**Validation:** `[GRILL]`. Depends on real template.

---

## T2.12 — `tools/reporting/excel_builder.py`

**Files:** `tools/reporting/excel_builder.py`, `tools/reporting/__init__.py`

**Depends on:** `templates/report_template.xlsx` (user supplies)

**What to build:** `build_report(fixed_results, exploratory_findings, attribution_results, prior_cycle_path=None, template_path) -> str` — loads template with openpyxl, writes via **named ranges** (never hardcoded cell addresses), saves to `outputs/scenario_report_{timestamp}.xlsx`.

**Excel template layout (expected):** one sheet, compact, named ranges:
- Rows: 6 segments (new_prime, new_near_prime, new_sub_prime, used_prime, used_near_prime, used_sub_prime)
- Column groups: Count | Amount Financed | APR — each with sub-columns: Current Y1 | Current Y2 | Prior Y1 | Prior Y2 | Δ
- Sections: Pricing (top) | New Origination (bottom)

**Output rules (non-negotiable):**
- Always timestamp the filename.
- Never overwrite previous outputs.
- Preserve all template formatting (fonts, borders, conditional formatting).
- User manually pastes into Google Sheets downstream.

**[OPEN]:** Named-range mapping is TBD until template is provided.

**Fixtures:**
- `tests/fixtures/excel_builder/input_fixed_results.json`
- `tests/fixtures/excel_builder/input_attribution.json`
- `tests/fixtures/excel_builder/expected_output.xlsx`

Comparison: load both with openpyxl, compare **named-range values only** (not byte-equal — openpyxl doesn't produce bit-identical output for the same input).

**Validation:**
```bash
pytest tests/test_excel_builder.py
```

---

## `[GRILL]` — polish targets for this build plan

- [ ] **Named-range mapping.** Needs the real template. Blocked.
- [ ] **12-model attribution in the report.** Does the Excel embed the 12 waterfall PNGs, only their tables, or just summary stats? What if the template was designed for the old 1-model reality?
- [ ] **Outlook extras.** Backtesting-error bar is a new thing — does the template have a cell/range for it, or do we need a template update?
- [ ] **Exploratory findings rendering.** Free-form bullets, a fixed table, or a comment cell?
- [ ] **Prior cycle columns.** Is the "Prior Y1 / Prior Y2 / Δ" group always populated (blank for CCAR) or conditionally created?
- [ ] **Filename template.** `scenario_report_{timestamp}.xlsx` — include mode (ccar/outlook) and scenario name?
- [ ] **Skill-level test strategy.** Fixture-driven with a real template, or monkeypatch openpyxl?

---

## Locked for this skill

- Writes only via named ranges, never hardcoded cell addresses.
- Always timestamped filename; never overwrite existing output.
- Template formatting preserved.
- Fixtures compare named-range values, not byte-equal files.
