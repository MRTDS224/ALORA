import datetime
import json
import logging
import sys
from typing import Any, Dict

from app.core.config import settings


class JsonLogFormatter(logging.Formatter):
    """Structured JSON formatter natively parsed by Google Cloud Logging (severity, message, extras)."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "severity": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("request_id", "method", "path", "status_code", "duration_ms", "ip", "action", "actor", "target"):
            val = getattr(record, key, None)
            if val is not None:
                payload[key] = val
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging() -> None:
    level_name = (settings.LOG_LEVEL or "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger("alora")
    root.setLevel(level)
    root.propagate = False

    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonLogFormatter())
        root.addHandler(handler)


def get_logger(name: str = "alora") -> logging.Logger:
    if not name.startswith("alora"):
        name = f"alora.{name}"
    return logging.getLogger(name)
