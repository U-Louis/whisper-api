"""JSON logs. Fields are chosen by the caller. The formatter does not dump the record."""

from __future__ import annotations

import json
import logging


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {"event": getattr(record, "event", record.getMessage())}
        for name in ("outcome", "key_id", "correlation_id", "status", "path", "error_type"):
            value = getattr(record, name, None)
            if value is not None:
                payload[name] = value
        if record.exc_info and record.exc_info[0] is not None:
            payload["error_type"] = record.exc_info[0].__name__
        return json.dumps(payload, separators=(",", ":"))


def configure_logging() -> None:
    logger = logging.getLogger("whisper_api")
    logger.setLevel(logging.INFO)
    if any(isinstance(handler.formatter, JsonFormatter) for handler in logger.handlers):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.propagate = False
