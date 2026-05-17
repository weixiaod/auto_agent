# queries/

Snowflake query templates consumed by `tools/data_sources/*_fetcher.py`.

## Convention

- One `.sql` file per source. Fetchers read the file and bind params; they
  never hold SQL as a Python string.
- Every file starts with a header block that documents:
  - `PURPOSE` — one line, what the query returns.
  - `BIND PARAMS` — names, types, and meanings of each param the fetcher
    must supply.
  - `OUTPUT COLUMNS` — the columns the fetcher's `_normalize` step expects.
- Real SQL is filled on the work laptop. Until then every file contains a
  `PLACEHOLDER` marker and a harmless `SELECT 1` body so lint/smoke checks
  keep passing.

## Files

| File | Owner fetcher |
|---|---|
| `auto_loan_actuals.sql` | `tools/data_sources/auto_loan_fetcher.py` |
| `ihs_econ_actuals.sql` | `tools/data_sources/ihs_actuals_fetcher.py` |
| `ihs_econ_forecasts.sql` | `tools/data_sources/ihs_forecast_fetcher.py` |
