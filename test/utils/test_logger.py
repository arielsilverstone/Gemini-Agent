# ============================================================================
# File: test_logger.py
# Purpose: Logging utilities for test results
# Created: 28JUL25 | Refactored: 02AUG25
# ============================================================================
# Section 1: Imports and configurations
# ============================================================================
# SECTION 1: Imports
# ============================================================================
import sys
import json
from loguru import logger
from tests.test_logging import test_stats

# ============================================================================
# SECTION 2: Functions
# ============================================================================
def setup_logging():
    """Set up Loguru to capture test results."""
    logger.remove()  # Remove default handler
    # Add a sink for critical errors to stderr
    logger.add(sys.stderr, level="CRITICAL")

    def serialize_record(record):
        """Custom serializer to format log records as JSON."""
        subset = {
            "timestamp": record["time"].isoformat(),
            "level": record["level"].name,
            "message": record["message"],
        }
        if "details" in record["extra"]:
            subset["details"] = record["extra"]["details"]
        return json.dumps(subset)

    def is_test_log(record):
        """Filter for test-related log messages."""
        return "test_log" in record["extra"]

    # Sink for structured test logs
    logger.add(
        "tests/logs/test_run.json",
        level="INFO",
        format="{message}",
        filter=is_test_log,
        serialize=True,
        rotation="10 MB",
        catch=True,
    )

    # Sink for general debug logs
    logger.add(
        "tests/logs/debug.log",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="10 MB",
        catch=True,
    )

# ============================================================================
# SECTION 3: Main Logic
# ============================================================================
# This script is intended to be imported as a module, so no main logic here.
