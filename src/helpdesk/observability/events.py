"""Metadata-only application logs. Never log prompts, tool arguments or results."""

import json
import logging
from logging.handlers import RotatingFileHandler

from helpdesk.observability.redaction import redact


logger = logging.getLogger("helpdesk.events")


def configure_logging(run_dir):
    """Called by the application entrypoint; libraries leave handler ownership alone."""
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if logger.handlers:
        return
    run_dir.mkdir(parents=True, exist_ok=True)
    for handler in (logging.StreamHandler(), RotatingFileHandler(
        run_dir / "app.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )):
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)


def log_event(payload):
    logger.info(redact(json.dumps(payload, ensure_ascii=False)))
