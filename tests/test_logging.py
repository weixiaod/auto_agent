import json
import logging
from pathlib import Path

from tools.logging import JSONFormatter, get_run_logger


def test_get_run_logger_returns_logger(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    logger = get_run_logger("test123")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "pipeline.test123"


def test_logger_writes_parseable_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    logger = get_run_logger("writetest")
    logger.info("hello", extra={"stage": "test", "run_id": "writetest"})
    for h in logger.handlers:
        h.flush()

    log_file = Path("logs/pipeline_writetest.json")
    assert log_file.exists()
    line = log_file.read_text().strip()
    record = json.loads(line)
    assert record["message"] == "hello"
    assert record["level"] == "INFO"
    assert record["stage"] == "test"
    assert record["run_id"] == "writetest"
    assert "timestamp" in record
    assert "module" in record


def test_idempotent_handler_attachment(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    a = get_run_logger("idem")
    b = get_run_logger("idem")
    assert a is b
    assert len(a.handlers) == 1


def test_formatter_standalone():
    fmt = JSONFormatter()
    record = logging.LogRecord(
        name="pipeline.x",
        level=logging.INFO,
        pathname="x.py",
        lineno=1,
        msg="hi",
        args=(),
        exc_info=None,
    )
    record.custom = "value"
    out = fmt.format(record)
    parsed = json.loads(out)
    assert parsed["message"] == "hi"
    assert parsed["level"] == "INFO"
    assert parsed["custom"] == "value"
