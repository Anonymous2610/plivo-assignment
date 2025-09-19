"""
Logging configuration for the Pub/Sub system
"""

import logging
import sys
from datetime import datetime


def setup_logging(level=logging.INFO, log_file=None):
    """
    Set up logging configuration for the application

    Args:
        level: Logging level (default: INFO)
        log_file: Optional log file path (default: None, logs to console)
    """

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Set specific logger levels
    logging.getLogger('pubsub.consumers').setLevel(logging.INFO)
    logging.getLogger('pubsub.state').setLevel(logging.INFO)
    logging.getLogger('pubsub.views').setLevel(logging.INFO)

    # Reduce noise from third-party libraries
    logging.getLogger('channels').setLevel(logging.WARNING)
    logging.getLogger('daphne').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)

    logging.info("Logging configured successfully")


def get_logger(name):
    """Get a logger instance for the given name"""
    return logging.getLogger(name)
