#!/usr/bin/env python3
"""
logger.py — Central Logging System
Minervini Trading Bot | Production Stabilization
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime

# ── Directories ──────────────────────────────────────────────
LOG_DIR = "/root/logs"
os.makedirs(LOG_DIR, exist_ok=True)

ERROR_LOG   = os.path.join(LOG_DIR, "errors.log")
SYSTEM_LOG  = os.path.join(LOG_DIR, "system.log")
TRADE_LOG   = os.path.join(LOG_DIR, "trades.log")

# ── Sensitive key masking ─────────────────────────────────────
SENSITIVE_KEYS = [
    "ALPACA_API_KEY", "ALPACA_SECRET_KEY", "ALPACA_KEY", "ALPACA_SECRET",
    "TELEGRAM_BOT_TOKEN", "TELEGRAM_TOKEN",
    "ANTHROPIC_API_KEY",
    "FRED_API_KEY", "FINNHUB_API_KEY", "ALPHA_VANTAGE_KEY",
]

class SensitiveFilter(logging.Filter):
    """Mask API keys and secrets from all log output."""
    def filter(self, record):
        msg = str(record.getMessage())
        for key in SENSITIVE_KEYS:
            # mask any value that looks like a key
            import re
            msg = re.sub(
                rf'({key}\s*[:=]\s*)[^\s\'"]+',
                r'\1***MASKED***',
                msg
            )
            # mask sk-ant-api style tokens
            msg = re.sub(r'sk-ant-api[^\s\'"]{0,60}', '***MASKED***', msg)
            msg = re.sub(r'(pk|sk)_[a-zA-Z0-9]{10,}', '***MASKED***', msg)
        record.msg = msg
        record.args = ()
        return True


def _make_formatter(module_name: str) -> logging.Formatter:
    fmt = f"%(asctime)s | %(levelname)-8s | {module_name} | %(message)s"
    return logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")


def _rotating_handler(path: str, max_mb: int = 10, backup_count: int = 5):
    handler = logging.handlers.RotatingFileHandler(
        path,
        maxBytes=max_mb * 1024 * 1024,
        backupCount=backup_count,
        encoding="utf-8",
    )
    return handler


def get_logger(module_name: str, level: int = logging.DEBUG) -> logging.Logger:
    """
    Return a production-grade logger for the given module.

    Usage:
        from logger import get_logger
        log = get_logger(__name__)
        log.info("Started")
        log.error("Something failed", exc_info=True)
    """
    logger = logging.getLogger(module_name)

    # Avoid duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    logger.setLevel(level)
    sensitive_filter = SensitiveFilter()

    # ── Handler 1: system.log (INFO+) with rotation ───────────
    h_system = _rotating_handler(SYSTEM_LOG)
    h_system.setLevel(logging.INFO)
    h_system.setFormatter(_make_formatter(module_name))
    h_system.addFilter(sensitive_filter)
    logger.addHandler(h_system)

    # ── Handler 2: errors.log (ERROR+) with rotation ──────────
    h_error = _rotating_handler(ERROR_LOG)
    h_error.setLevel(logging.ERROR)
    h_error.setFormatter(_make_formatter(module_name))
    h_error.addFilter(sensitive_filter)
    logger.addHandler(h_error)

    # ── Handler 3: Console (WARNING+) ─────────────────────────
    h_console = logging.StreamHandler(sys.stdout)
    h_console.setLevel(logging.WARNING)
    h_console.setFormatter(_make_formatter(module_name))
    h_console.addFilter(sensitive_filter)
    logger.addHandler(h_console)

    # Don't propagate to root logger
    logger.propagate = False

    return logger


def get_trade_logger() -> logging.Logger:
    """Dedicated logger for trade decisions — separate file."""
    logger = logging.getLogger("trades")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    h = _rotating_handler(TRADE_LOG, max_mb=20, backup_count=10)
    h.setLevel(logging.INFO)
    h.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    h.addFilter(SensitiveFilter())
    logger.addHandler(h)
    logger.propagate = False
    return logger


# ── Quick test ────────────────────────────────────────────────
if __name__ == "__main__":
    log = get_logger("logger_test")
    log.info("Logger system initialized ✅")
    log.warning("This is a warning test")
    log.error("This is an error test", exc_info=False)
    try:
        x = 1 / 0
    except Exception:
        log.critical("Critical error caught", exc_info=True)
    print(f"✅ Logs written to: {LOG_DIR}")
    print(f"   system.log : {SYSTEM_LOG}")
    print(f"   errors.log : {ERROR_LOG}")
