from tools.errors import (
    AnalysisError,
    AttributionError,
    ConfigError,
    DataAcquisitionError,
    DateAlignmentError,
    DifferentT0Error,
    EnterpriseAdjustmentError,
    ModelExecutionError,
    PayloadValidationError,
    QueryExecutionError,
    ReportingError,
    RiskError,
    TemplateError,
    to_log_entry,
)


def test_risk_error_builds_with_structured_fields():
    err = RiskError(
        "boom",
        stage="data_acquisition",
        module="foo.py",
        context={"k": "v"},
        suggested_action="do X",
    )
    assert err.message == "boom"
    assert err.stage == "data_acquisition"
    assert err.module == "foo.py"
    assert err.context == {"k": "v"}
    assert err.suggested_action == "do X"
    assert str(err) == "boom"


def test_risk_error_defaults():
    err = RiskError("just a message")
    assert err.stage is None
    assert err.module is None
    assert err.context == {}
    assert err.suggested_action is None


def test_to_log_entry_shape():
    err = QueryExecutionError(
        "missing partition",
        stage="data_acquisition",
        module="snowflake_runner.py",
        context={"publn_id": "XYZ"},
        suggested_action="check publn_id",
    )
    entry = to_log_entry(err)
    assert entry == {
        "stage": "data_acquisition",
        "module": "snowflake_runner.py",
        "error_type": "QueryExecutionError",
        "message": "missing partition",
        "context": {"publn_id": "XYZ"},
        "suggested_action": "check publn_id",
    }


def test_subclass_inheritance():
    assert issubclass(QueryExecutionError, DataAcquisitionError)
    assert issubclass(DateAlignmentError, DataAcquisitionError)
    assert issubclass(DataAcquisitionError, RiskError)

    assert issubclass(PayloadValidationError, ModelExecutionError)
    assert issubclass(EnterpriseAdjustmentError, ModelExecutionError)
    assert issubclass(ModelExecutionError, RiskError)

    assert issubclass(DifferentT0Error, AttributionError)
    assert issubclass(AttributionError, RiskError)

    assert issubclass(TemplateError, ReportingError)
    assert issubclass(ReportingError, RiskError)

    for cls in (ConfigError, AnalysisError):
        assert issubclass(cls, RiskError)


def test_context_is_copied_not_referenced():
    ctx = {"a": 1}
    err = RiskError("x", context=ctx)
    ctx["a"] = 2
    assert err.context == {"a": 1}
