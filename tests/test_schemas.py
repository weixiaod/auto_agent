import json
from pathlib import Path

import jsonschema
import pytest

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"

SCHEMAS = ["auto_loan.json", "ihs_actuals.json", "ihs_forecast.json"]


@pytest.mark.parametrize("name", SCHEMAS)
def test_schema_is_valid_draft_2020_12(name):
    schema = json.loads((SCHEMA_DIR / name).read_text())
    jsonschema.Draft202012Validator.check_schema(schema)


@pytest.mark.parametrize("name,source_type", [
    ("auto_loan.json", "auto_loan"),
    ("ihs_actuals.json", "ihs_actuals"),
    ("ihs_forecast.json", "ihs_forecast"),
])
def test_schema_source_type_is_locked(name, source_type):
    schema = json.loads((SCHEMA_DIR / name).read_text())
    assert schema["properties"]["source_type"]["const"] == source_type
    assert schema["properties"]["schema_version"]["const"] == "1.0"
