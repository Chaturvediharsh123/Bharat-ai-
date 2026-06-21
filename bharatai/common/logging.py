"""bharatai.common.logging — centralized structured (JSON) logging.

Use ``configure_logging`` once at startup (composition root) and ``get_logger``
everywhere else. Output is line-delimited JSON so it is greppable and ships to
any log aggregator unchanged.
"""
from __future__ import annotations

import json
import logging
import sys
from typing import Any

_CONFIGURED = False
_RESERVED = set(logging.makeLogRecord({}).__dict__.keys()) | {
    "message",
    "asctime",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    """Render a log record as a single JSON line, including extra fields."""

    def format(self, record: logging.LogRecord) -> str:
        """Serialize the record to JSON."""
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Install the JSON formatter on the root logger exactly once."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger (call ``configure_logging`` first)."""
    return logging.getLogger(name)
