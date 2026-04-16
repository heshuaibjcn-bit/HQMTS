"""Structured logging setup using structlog."""

from __future__ import annotations

import logging
import sys

import structlog


def setup_logging(level: str = "INFO", fmt: str = "json") -> None:
    """Configure structured logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR).
        fmt: Output format - "json" for production, "text" for development.
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.UnicodeDecoder(),
            (
                structlog.processors.JSONRenderer()
                if fmt == "json"
                else structlog.dev.ConsoleRenderer()
            ),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer()
            if fmt == "text"
            else structlog.processors.JSONRenderer(),
        )
    )
    root_logger.handlers.clear()
    root_logger.addHandler(handler)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)
