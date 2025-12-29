"""Centralized logging configuration for the ARK Modding Discord Bot.

This module provides a structured logging setup with timestamps, log levels,
and module names to make it easy to distinguish logs between different cogs.

Usage:
    from am_bot.logging_config import setup_logging
    setup_logging()  # Call once at application startup

Environment Variables:
    LOG_LEVEL: Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
               Default: INFO
"""

import logging
import os
import sys


# Log format with timestamp, level, module, and message
LOG_FORMAT = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: str | None = None) -> None:
    """Configure logging for the entire application.

    Args:
        level: Optional log level override. If not provided, uses LOG_LEVEL
               environment variable or defaults to INFO.
    """
    # Determine log level from argument, env var, or default
    log_level_str = level or os.getenv("LOG_LEVEL", "INFO")
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)

    # Create formatter
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove any existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create and configure console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Configure discord.py library logging (less verbose)
    discord_logger = logging.getLogger("discord")
    discord_logger.setLevel(logging.WARNING)

    # Configure discord.http specifically (very noisy at DEBUG)
    discord_http_logger = logging.getLogger("discord.http")
    discord_http_logger.setLevel(logging.WARNING)

    # Log initial setup message
    app_logger = logging.getLogger(__name__)
    app_logger.info(f"Logging configured at {log_level_str.upper()} level")
