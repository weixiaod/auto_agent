# 00_foundation — Shared infra

**Scope:** everything the pipeline depends on before any skill can be built. Docs, error hierarchy, logging, packaging, gitignore, schemas skeletons, queries skeletons, config templates.

**Produces no skill.** Every per-skill build plan depends on this.

**Does NOT touch:** any file inside `skills/`. That's the skill build plans' job. Foundation only creates/edits files under `tools/`, `schemas/`, `queries/`, `config/`, `logs/`, `tests/conftest.py`, and the agent-level doc at repo root (`CLAUDE.md`).

**Dependencies:** none.

**Blocks:** all other build plans.

---

## T0.1 — (removed) `CLAUDE_BUILD.md` deleted

The builder's brief was outdated (single-model shape, `feature_cols`, `amount_financed`/`APR`, one common_intermediate). It has been deleted. All build-time context now lives in `BUILD_PLAN.md` + this directory; all runtime guidance lives in `CLAUDE.md`.

---

## T0.2 — Update `CLAUDE.md` to match

**Files:** `CLAUDE.md`

**Depends on:** T0.1

**What to build:** Propagate same corrections. Additionally:
- Intake section: note that a scenario YAML can be passed, and the agent should read it if provided; otherwise ask conversationally.
- Pipeline stages: reflect that Stage 6 (ECM attribution) produces 12 waterfalls, one per model.
- Reporting: flag Excel layout supports 12-model outputs (TBD named-range mapping).

**[GRILL]** Once user shares the job config file from work machine, update intake section with the canonical parameter set. Until then, `config/scenarios/example_scenario.yaml` is the working definition.

**Validation (manual):**
- [ ] Grep for `\bfeature_cols\b` — zero hits.
- [ ] `model_config.json` example block matches real file structure.
- [ ] Intake section references scenario YAML path.

---

## T0.3 — Cleanup

**Files to delete:**
- `output/` (duplicate of `outputs/`)
- `__pycache__/` (root and any nested)
- `.DS_Store` files (all)
- `examples/ecm_example.py`

**Keep:** `outputs/` with its sample CSV + PNG as reference.

**Validation:**
```bash
test ! -d output/ && test ! -d __pycache__/ && \
test -z "$(find . -name '.DS_Store' -not -path './.git/*')" && \
test ! -f examples/ecm_example.py && \
test -d outputs/ && echo OK
```

---

## T0.5 — `pyproject.toml` + dependency pinning

**Files:** `pyproject.toml` (new), `.python-version` (new, optional)

**What to build:**
```toml
[project]
name = "auto_agent"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "pandas>=2.0",
  "numpy>=1.24",
  "snowflake-connector-python>=3.5",
  "openpyxl>=3.1",
  "jsonschema>=4.17",
  "pyyaml>=6.0",
  "requests>=2.31",
  "matplotlib>=3.7",
]

[project.optional-dependencies]
dev = ["pytest>=7.4", "pytest-mock>=3.11"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
```

**Validation:**
```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]" && .venv/bin/pytest --version
```

---

## T0.6 — `.gitignore` updates

**Files:** `.gitignore`

**What to build:** Append:
```
__pycache__/
*.pyc
.venv/
.DS_Store
logs/*.json
outputs/*.xlsx
outputs/*.csv
outputs/*.png
tests/fixtures/**/raw_*.csv
config/snowflake_creds.yaml
```

**Validation (manual):** After scaffold, `git status` does not list any ignored files.

---

## T0.7 — `tools/errors.py` — RiskError hierarchy

**Files:** `tools/errors.py` (new)

**What to build:**
- `class RiskError(Exception)` — base. Carries `stage`, `module`, `context` dict, `suggested_action`. `__str__` formats JSON-compatible.
- `to_log_entry(err) -> dict` producing the CLAUDE.md-spec'd error-log JSON shape.

**Locked subclass hierarchy** — centralized in `tools/errors.py`:
```
RiskError
├── ConfigError
├── DataAcquisitionError
│   ├── QueryExecutionError
│   └── DateAlignmentError
├── ModelExecutionError
│   ├── PayloadValidationError
│   └── EnterpriseAdjustmentError
├── AnalysisError
├── AttributionError
│   └── DifferentT0Error
└── ReportingError
    └── TemplateError
```

Skills may raise these directly or define finer subclasses under the same parents later — but the parent set above is fixed.

**Validation:**
```bash
pytest tests/test_errors.py
```
Expected tests:
- `RiskError("msg", stage="data_acquisition", module="foo.py", context={"k": "v"}, suggested_action="do X")` builds and serializes.
- `to_log_entry(err)` returns dict with keys: `stage, module, error_type, message, context, suggested_action`.
- Subclass inheritance: `isinstance(QueryExecutionError(...), DataAcquisitionError)` is True; `isinstance(EnterpriseAdjustmentError(...), ModelExecutionError)` is True; etc.

---

## T0.8 — Three distinct schemas (skeleton)

**Files (new):**
- `schemas/auto_loan.json`
- `schemas/ihs_actuals.json`
- `schemas/ihs_forecast.json`

**What to build:** One JSON Schema per fetcher. Each has:
- `source_type` (const: `auto_loan` | `ihs_actuals` | `ihs_forecast`)
- `source_metadata` (object — fetcher-specific fields like `timestamp`, `publn_id`, `yymm_num`, `scenario_var`)
- `schema_version` (const: `"1.0"`)
- `data` (array or keyed object — fetcher-specific)

**[GRILL]** Specific field lists per fetcher are locked in `data_acquisition.md`. For now, scaffold with `additionalProperties: true` and TODO comments.

**Validation:**
```bash
python -c "import jsonschema, json; jsonschema.Draft202012Validator.check_schema(json.load(open('schemas/auto_loan.json')))"
```
Repeat for all three.

---

## T0.9 — `queries/` directory (skeleton)

**Files (new):**
- `queries/README.md` — convention (external SQL, fetchers read + bind).
- `queries/auto_loan_actuals.sql` — placeholder
- `queries/ihs_econ_actuals.sql` — placeholder
- `queries/ihs_econ_forecasts.sql` — placeholder

**What to build:** Each `.sql` file has a header block listing expected bind params and output columns. Example:
```sql
-- PURPOSE: Fetch auto loan production actuals for t0 initial conditions + benchmark + replacement
-- BIND PARAMS:
--   :timestamp   (str) — partition timestamp
--   :start_date  (date) — earliest date in range (= t0 - max(history_periods))
--   :end_date    (date) — latest date (typically today)
-- OUTPUT COLUMNS: date, segment, variable, value
-- PLACEHOLDER: real query to be filled on work laptop
SELECT 1 AS placeholder;
```

Real SQL gets filled in `data_acquisition.md`.

**Validation:**
```bash
ls queries/*.sql | xargs -I{} head -n 3 {} | grep -q PLACEHOLDER && echo OK
```

---

## T0.10 — Config templates

**Files (new):**
- `config/snowflake_creds.example.yaml`
- `config/scenario_service_config.yaml` (deferred stub)
- `config/scenarios/example_scenario.yaml`

**What to build:**

`snowflake_creds.example.yaml` — supports either password or private-key auth. Pick one stanza; comment the other.
```yaml
account:   ${SNOWFLAKE_ACCOUNT}
user:      ${SNOWFLAKE_USER}
role:      ${SNOWFLAKE_ROLE}
warehouse: ${SNOWFLAKE_WAREHOUSE}
database:  ${SNOWFLAKE_DATABASE}
schema:    ${SNOWFLAKE_SCHEMA}

# --- Auth: password ---
password:  ${SNOWFLAKE_PWD}

# --- Auth: key-pair (preferred if corp Snowflake supports it) ---
# Comment out `password` above and uncomment these:
# private_key_file:     ${SNOWFLAKE_PRIVATE_KEY_PATH}
# private_key_file_pwd: ${SNOWFLAKE_PRIVATE_KEY_PWD}
```

**Secret storage recommendation — macOS Keychain.** Do not put secrets directly in `.zshrc`. Store in Keychain once, export from Keychain in `.zshrc`:
```bash
# one-time setup
security add-generic-password -s snowflake_pwd -a "$USER" -w
# (paste password when prompted)

# in ~/.zshrc
export SNOWFLAKE_PWD=$(security find-generic-password -s snowflake_pwd -w)
```
For key-pair auth, only the key *path* needs exporting (`SNOWFLAKE_PRIVATE_KEY_PATH`); the key itself lives encrypted at rest on disk.

`scenario_service_config.yaml`:
```yaml
# DEFERRED — Scenario Service integration is on hold.
enabled: false
```

`config/scenarios/example_scenario.yaml` — Outlook variant:
```yaml
mode: outlook
run_id: outlook_2026MA               # Outlook convention: outlook_{yyyy}{MA|JA|SA|DA}
                                     #   MA/JA/SA/DA = March / June / Sept / Dec Assessment

# Two dates — may diverge when enterprise (auto_loan) actuals lag econ actuals.
t0_date: 2026-02-28                  # assessment as-of; auto_loan initial conditions
scenario_start_date: 2026-03-31      # econ glue point: actuals stop, forecasts start

auto_loan:
  timestamp: "2026-02-28T23:59:59"   # partition key for the auto loan table

econ_actuals:
  publn_id: "IHS_GL_STD"
  yymm_num: "2603"

econ_forecast:
  publn_id: "IHS_GL_STD"
  yymm_num: "2603"
  scenario_var: "BASELINE"           # Outlook: single scenario

# Industry → enterprise forecast adjustment, applied inside model_execution skill.
# Method: "gap" (additive) or "ratio" (multiplicative). Uses the last N months of
# (enterprise_actual − industry_actual) for gap, or the ratio for ratio.
enterprise_adjustment:
  default:
    method: "ratio"
    lookback_months: 6
  overrides:                         # optional per-(target × segment)
    - target: "pricing"
      segment: "new_sub_prime"
      method: "gap"
      lookback_months: 12
    - target: "count"
      segment: "prime"
      method: "gap"
      lookback_months: 3

prior_cycle_output_path: "./outputs/prior_cycle_2025q4.csv"
output_dir: "./outputs"
```

CCAR variant differs in `mode`, `run_id` convention, and drops `prior_cycle_output_path`. Each CCAR scenario is its **own** YAML + run (single `scenario_var`, not a stress-vs-baseline pair); a full CCAR cycle = 4 runs (FRBB, FRBSA, BHCB, BHCS). Attribution happens as a separate step that pairs two run outputs.

```yaml
mode: ccar
run_id: FRBSA26                      # CCAR convention: one id per scenario
                                     #   FRBB{yy}  — Federal Reserve Board Baseline
                                     #   FRBSA{yy} — Federal Reserve Board Severely Adverse
                                     #   BHCB{yy}  — Bank Holding Company Baseline
                                     #   BHCS{yy}  — Bank Holding Company Severely Adverse
...
econ_forecast:
  publn_id: "IHS_GL_STD"
  yymm_num: "2603"
  scenario_var: "SEVERELY_ADVERSE_FRB"   # single scenario — no stress/baseline pair in YAML
```

`run_id` is **required** (not auto-generated). An invalid pattern fails at scenario-load time with a `ConfigError`.

**Consequence:** `data_acquisition` makes one forecast pull per run regardless of mode. Mode only affects (a) whether `actuals_replacement` runs (Outlook yes, CCAR no) and (b) how attribution pairs runs (see `ecm_attribution.md`).

**Semantics of the two dates:**
- `t0_date` — where auto_loan target variables transition from actuals (initial conditions) to model projections. Driven by enterprise data availability.
- `scenario_start_date` — where econ variables transition from actuals to forecast. Driven by IHS data availability.
- When enterprise actuals lag econ actuals, `t0_date < scenario_start_date`. The `json_formatter` must reconcile the gap (exact handling `[GRILL]` in `data_acquisition.md`).

**Validation:**
```bash
python -c "import yaml; yaml.safe_load(open('config/scenarios/example_scenario.yaml'))"
python -c "import yaml; yaml.safe_load(open('config/snowflake_creds.example.yaml'))"
```

---

## T0.11 — `logs/` + `tools/logging.py`

**Files (new):**
- `logs/.gitkeep`
- `tools/logging.py`

**What to build:** `tools/logging.py` — stdlib-only, ~30 lines, no extra deps.
- `JSONFormatter(logging.Formatter)` — subclass that emits one JSON object per record. Fields: `timestamp, level, module, message`, plus any `extra=` kwargs passed to the logger call.
- `get_run_logger(run_id: str) -> logging.Logger` — returns a logger named `pipeline.{run_id}`. Idempotent: if the logger already has handlers, return as-is. Otherwise attach a `FileHandler("logs/pipeline_{run_id}.json")` with `JSONFormatter`.

Good-practice defaults: append-only file, `INFO` level, no propagation to root (avoid duplicate console output). That's it — intentionally minimal.

**Validation:**
```bash
pytest tests/test_logging.py
```
Expected tests:
- `get_run_logger("test123")` returns Logger.
- `logger.info("hello", extra={"stage": "test"})` writes a parseable JSON line with all required fields.
- Calling `get_run_logger("test123")` twice does not duplicate handlers.

---

## T0.12 — yaml env-var helper (part of `tools/logging.py` companion or its own file)

**Files:** `tools/config_loader.py` (new, small)

**What to build:** one function, ~10 lines, stdlib + pyyaml only:

```python
import os, re, yaml

_ENV_VAR = re.compile(r'\$\{([^}]+)\}')

def load_yaml_with_env(path: str) -> dict:
    """Load a YAML file, substituting ${VAR} with os.environ['VAR']. Raises KeyError if a var is unset."""
    with open(path) as f:
        raw = f.read()
    def sub(m):
        name = m.group(1)
        if name not in os.environ:
            raise KeyError(f"Environment variable {name!r} not set (referenced in {path})")
        return os.environ[name]
    return yaml.safe_load(_ENV_VAR.sub(sub, raw))
```

Used by `snowflake_runner.connect` (in `data_acquisition.md`). Small enough that we don't need a separate dependency like `envyaml`.

**Validation:**
```bash
pytest tests/test_config_loader.py
```
Expected tests:
- Substitutes `${VAR}` when env var is set.
- Raises `KeyError` with variable name when unset.
- Non-interpolated yaml passes through unchanged.

---

## Grilling targets for this build plan

All resolved. Foundation ready to scaffold.
