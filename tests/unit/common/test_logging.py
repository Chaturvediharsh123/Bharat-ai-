"""Tests for the structured JSON logging."""
from __future__ import annotations

import json
import logging
import sys

from bharatai.common.logging import JsonFormatter, configure_logging, get_logger


def test_json_formatter_includes_extra_fields() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord("t", logging.INFO, "f.py", 1, "hello %s", ("world",), None)
    record.trace_id = "abc"  # type: ignore[attr-defined]
    payload = json.loads(formatter.format(record))
    assert payload["level"] == "INFO"
    assert payload["message"] == "hello world"
    assert payload["trace_id"] == "abc"


def test_json_formatter_serializes_exception() -> None:
    formatter = JsonFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.LogRecord("t", logging.ERROR, "f.py", 1, "failed", (), sys.exc_info())
    payload = json.loads(formatter.format(record))
    assert "exc" in payload and "ValueError" in payload["exc"]


def test_configure_logging_and_get_logger() -> None:
    configure_logging("DEBUG")
    logger = get_logger("bharatai.test")
    assert isinstance(logger, logging.Logger)
