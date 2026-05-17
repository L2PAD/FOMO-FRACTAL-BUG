"""
Crypto Intelligence Operating System — Logging
"""
import logging
import sys

LOG_FORMAT = "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s"


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(f"intel_os.{name}")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
