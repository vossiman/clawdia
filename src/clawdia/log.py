"""Loguru logging setup for Clawdia.

Configures two sinks: colored stdout and a rotating log file (7-day retention).
Intercepts stdlib logging so third-party libraries also route through loguru.
"""

from __future__ import annotations

import logging
import sys

from loguru import logger


class _InterceptHandler(logging.Handler):
    """Route stdlib logging through loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup(data_dir: str = "data", debug: bool = False) -> None:
    """Configure loguru sinks and intercept stdlib logging."""
    # Remove default loguru sink
    logger.remove()

    level = "DEBUG" if debug else "INFO"

    # Stdout sink (colored)
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> "
        "[<cyan>{name}</cyan>] "
        "<level>{level}</level>: {message}",
    )

    # File sink (daily rotation, 7-day retention, plain text)
    logger.add(
        f"{data_dir}/clawdia.log",
        level=level,
        format="{time:YYYY-MM-DD HH:mm:ss} [{name}] {level}: {message}",
        rotation="1 day",
        retention="7 days",
        compression=None,
    )

    # Intercept stdlib logging
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)

    # Mute noisy third-party loggers
    for name in ("httpx", "httpcore", "telegram", "telegram.ext"):
        logging.getLogger(name).setLevel(logging.WARNING)
