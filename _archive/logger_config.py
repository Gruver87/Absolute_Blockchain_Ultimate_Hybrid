"""
Logging configuration for Absolute Blockchain Ultimate
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from datetime import datetime


def setup_logging(log_level=logging.INFO, log_dir="logs"):
    """Setup logging system"""
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()
    
    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(log_level)
    console_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    console.setFormatter(logging.Formatter(console_format))
    root_logger.addHandler(console)
    
    # File handler
    file_handler = logging.handlers.RotatingFileHandler(
        log_path / "blockchain.log",
        maxBytes=10_485_760,
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(console_format))
    root_logger.addHandler(file_handler)
    
    # Error handler
    error_handler = logging.handlers.RotatingFileHandler(
        log_path / "errors.log",
        maxBytes=10_485_760,
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    root_logger.addHandler(error_handler)
    
    return root_logger


def get_logger(name: str):
    """Get configured logger"""
    return logging.getLogger(name)


if __name__ == "__main__":
    setup_logging()
    logger = get_logger(__name__)
    logger.info("Logging system ready")
