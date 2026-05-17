"""Per-run structured JSON logging. Stdlib-only, intentionally minimal."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

_RESERVED = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "taskName",
}


class JSONFormatter(logging.Formatter):
    """Emit one JSON object per log record. `extra=` kwargs pass through."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.module,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        return json.dumps(payload, default=str)


def get_run_logger(run_id: str) -> logging.Logger:
    """Return a per-run logger writing to logs/pipeline_{run_id}.json.

    Idempotent: repeated calls with the same run_id return the same logger
    without duplicating handlers.
    """
    logger = logging.getLogger(f"pipeline.{run_id}")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    logger.propagate = False
    Path("logs").mkdir(exist_ok=True)
    handler = logging.FileHandler(f"logs/pipeline_{run_id}.json")
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    return logger
