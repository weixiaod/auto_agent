# Query Templates

This directory will contain Snowflake query templates linked from the work machine.

## Expected format

Each query template is a .sql file with Jinja-style parameters:

```sql
SELECT date, portfolio_id, asset_class, market_value
FROM risk_db.positions
WHERE scenario_date BETWEEN '{{ start_date }}' AND '{{ end_date }}'
AND portfolio_id IN ({{ portfolio_ids }})
```

## Linking instructions

Once on your work machine:
1. Copy or symlink query files into this directory
2. Reference them in scenario configs: `query_template: queries/your_query.sql`
3. Claude Code will use these templates instead of constructing SQL from scratch
