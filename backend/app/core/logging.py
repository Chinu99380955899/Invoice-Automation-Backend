"""Structured logging configuration.

Produces JSON logs in production for easy ingestion into log aggregators
(ELK, Datadog, etc.) and human-readable console logs in development.
"""
import logging
import sys
from typing import Any, Dict

import structlog

from app.core.config import settings


def configure_logging() -> None:
    """Configure stdlib logging + structlog processors."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )
    # Silence noisy third-party libs
    for noisy in ("urllib3", "botocore", "azure", "paddle"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.log_format == "json":
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance bound with the module name."""
    return structlog.get_logger(name or "app")


def bind_request_context(**kwargs: Any) -> None:
    """Bind per-request context (request_id, user_id) to the logger."""
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_request_context() -> None:
    structlog.contextvars.clear_contextvars()
