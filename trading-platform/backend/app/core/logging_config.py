"""
Professional logging configuration with rotating file handler and colored console output.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


# ANSI color codes for console output
class LogColors:
    RESET = "\033[0m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    LEVEL_COLORS = {
        "DEBUG": CYAN,
        "INFO": GREEN,
        "WARNING": YELLOW,
        "ERROR": RED,
        "CRITICAL": f"{BOLD}{RED}",
    }


class ColoredFormatter(logging.Formatter):
    """Formatter that adds ANSI color codes to log level names."""

    FORMAT = "%(asctime)s │ %(levelname)-8s │ %(name)-30s │ %(message)s"
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    def format(self, record):
        color = LogColors.LEVEL_COLORS.get(record.levelname, LogColors.RESET)
        record.levelname = f"{color}{record.levelname}{LogColors.RESET}"
        record.name = f"{LogColors.DIM}{record.name}{LogColors.RESET}"
        formatter = logging.Formatter(self.FORMAT, datefmt=self.DATE_FORMAT)
        return formatter.format(record)


class FileFormatter(logging.Formatter):
    """Clean formatter for log files (no ANSI codes)."""

    FORMAT = "%(asctime)s │ %(levelname)-8s │ %(name)-30s │ %(message)s"
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    def format(self, record):
        formatter = logging.Formatter(self.FORMAT, datefmt=self.DATE_FORMAT)
        return formatter.format(record)


def setup_logging(log_level: str = "INFO", log_file: str = "logs/trading_platform.log") -> None:
    """
    Configure application-wide logging.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to the log file
    """
    # Ensure log directory exists
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Clear existing handlers
    root_logger.handlers.clear()

    # ---- Console Handler (colored) ----
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(ColoredFormatter())
    root_logger.addHandler(console_handler)

    # ---- Rotating File Handler ----
    file_handler = RotatingFileHandler(
        filename=str(log_path),
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(FileFormatter())
    root_logger.addHandler(file_handler)

    # ---- Per-module log levels ----
    # Reduce noise from chatty third-party libraries
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    # Ensure our app modules log at the configured level
    logging.getLogger("app").setLevel(getattr(logging, log_level.upper(), logging.INFO))
    logging.getLogger("mt5_bridge").setLevel(getattr(logging, log_level.upper(), logging.INFO))

    root_logger.info("Logging initialized — level=%s, file=%s", log_level, log_file)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger for a module."""
    return logging.getLogger(name)
