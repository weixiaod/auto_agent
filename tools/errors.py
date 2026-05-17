"""RiskError hierarchy for the financial risk modeling pipeline.

Every error raised by a tool or skill should be a subclass of RiskError,
carrying structured context so the orchestrator can produce the CLAUDE.md-
spec'd error-log JSON.
"""

from __future__ import annotations

from typing import Any


class RiskError(Exception):
    """Base class for all pipeline errors.

    Carries structured fields so `to_log_entry` can serialize the error
    into the JSON shape described in CLAUDE.md.
    """

    def __init__(
        self,
        message: str,
        *,
        stage: str | None = None,
        module: str | None = None,
        context: dict[str, Any] | None = None,
        suggested_action: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.stage = stage
        self.module = module
        self.context = dict(context) if context else {}
        self.suggested_action = suggested_action

    def __str__(self) -> str:
        return self.message


# --- Config -----------------------------------------------------------------


class ConfigError(RiskError):
    pass


# --- Data acquisition ------------------------------------------------------


class DataAcquisitionError(RiskError):
    pass


class QueryExecutionError(DataAcquisitionError):
    pass


class DateAlignmentError(DataAcquisitionError):
    pass


# --- Model execution -------------------------------------------------------


class ModelExecutionError(RiskError):
    pass


class PayloadValidationError(ModelExecutionError):
    pass


class EnterpriseAdjustmentError(ModelExecutionError):
    pass


# --- Analysis --------------------------------------------------------------


class AnalysisError(RiskError):
    pass


# --- Attribution -----------------------------------------------------------


class AttributionError(RiskError):
    pass


class DifferentT0Error(AttributionError):
    pass


# --- Reporting -------------------------------------------------------------


class ReportingError(RiskError):
    pass


class TemplateError(ReportingError):
    pass


def to_log_entry(err: RiskError) -> dict[str, Any]:
    """Serialize a RiskError into the log-entry shape defined in CLAUDE.md."""
    return {
        "stage": err.stage,
        "module": err.module,
        "error_type": type(err).__name__,
        "message": err.message,
        "context": err.context,
        "suggested_action": err.suggested_action,
    }
