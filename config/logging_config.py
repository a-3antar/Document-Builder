"""Structured logging with secret redaction."""
from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

_SECRET_RE = re.compile(r"(AIza[0-9A-Za-z_\-]{20,}|api[_-]?key['\"=: ]+[^\s'\"]+)", re.IGNORECASE)


class RedactingFilter(logging.Filter):
    """Mask API-key-like strings before they reach any handler."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _SECRET_RE.sub("[REDACTED]", str(record.getMessage()))
        record.args = ()
        return True


def setup_logging(log_dir: Path, verbose: bool = False) -> None:
    """Configure root logger: rotating file plus console."""
    log_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    for handler in (
        RotatingFileHandler(log_dir / "app.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"),
        logging.StreamHandler(),
    ):
        handler.setFormatter(fmt)
        handler.addFilter(RedactingFilter())
        root.addHandler(handler)
