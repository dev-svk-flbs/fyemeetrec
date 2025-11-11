#!/usr/bin/env python3
"""
Logging Configuration for Audio Recording System
Provides centralized logging setup with rotation and proper formatting
"""

import logging
import logging.handlers
import os
from pathlib import Path
from datetime import datetime
import sys

class SafeFormatter(logging.Formatter):
    """Formatter that handles encoding errors gracefully"""
    def format(self, record):
        try:
            return super().format(record)
        except UnicodeEncodeError:
            # If encoding fails, remove non-ASCII characters
            result = super().format(record)
            return result.encode('ascii', 'ignore').decode('ascii')

def setup_logging(name="audiomictest", log_level=logging.DEBUG):
    """
    Setup logging with rotation and proper formatting
    
    Args:
        name: Logger name (usually module name)
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
    
    Returns:
        Configured logger instance
    """
    
    # Create logs directory if it doesn't exist
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    # Prevent duplicate handlers if logger already configured
    if logger.hasHandlers():
        return logger
    
    # Create formatters with safe encoding handling
    detailed_formatter = SafeFormatter(
        fmt='%(asctime)s | %(name)s | %(levelname)-8s | %(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = SafeFormatter(
        fmt='%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # File handler with rotation (5MB max, keep 1 backup)
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_dir / f"{name}.log",
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=1,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    
    # Console handler for immediate feedback with UTF-8 encoding
    import sys
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    
    # Ensure console can handle UTF-8 (for emojis)
    try:
        # Reconfigure stdout to use UTF-8 encoding
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass  # If reconfiguration fails, continue anyway
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # Log startup message
    logger.info(f" Logging initialized for {name} - Log file: {file_handler.baseFilename}")
    
    return logger

def get_logger(name=None):
    """
    Get a logger instance for a specific module
    
    Args:
        name: Module name (will use calling module if None)
    
    Returns:
        Logger instance
    """
    if name is None:
        import inspect
        frame = inspect.currentframe().f_back
        name = frame.f_globals.get('__name__', 'unknown')
    
    return setup_logging(name)

# Create module-specific loggers
app_logger = setup_logging("app")
dual_stream_logger = setup_logging("dual_stream") 
settings_logger = setup_logging("settings")
ffmpeg_logger = setup_logging("ffmpeg")