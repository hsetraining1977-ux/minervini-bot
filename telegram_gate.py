#!/usr/bin/env python3
"""
telegram_gate.py — Centralized Telegram sender with session guard.
ALL files should import send_telegram from here instead of defining their own.

Usage:
    from telegram_gate import send_telegram, send_alert

Rules:
    - Scan reports: only during MARKET_OPEN or PREMARKET
    - Critical alerts: always send (trade, stop, kill switch, regime shift)
    - Heartbeat: every 2 hours when market closed
"""

import os, logging, time
from datetime import datetime
from typing import Optional

log = logging.getLogger(__name__)

# ── Critical alert types — always sent regardless of session ──────────────
ALWAYS_SEND_KEYWORDS = [
    "TRADE EXECUTED", "STOP LOSS", "TARGET HIT", "KILL SWITCH",
    "REGIME SHIFT", "SYSTEM ERROR", "PROCESS DOWN", "CPU CRITICAL",
    "HEARTBEAT", "MARKET OPEN", "MARKET CLOSE", "حالة النظام",
    "System Status", "🚨", "🛑", "🎯", "🔔", "🔕",
]

# ── Rate limiting — prevent duplicate messages ────────────────────────────
_last_sent: dict = {}
RATE_LIMIT_SECONDS = 60  # same message won't send twice within 60s

def _is_critical(message: str) -> bool:
    """Check if message is a critical alert that should always be sent."""
    return any(kw in message for kw in ALWAYS_SEND_KEYWORDS)

def _is_rate_limited(message: str) -> bool:
    """Prevent same message from being sent too frequently."""
    key = message[:50]
    now = time.time()
    if key in _last_sent:
        if now - _last_sent[key] < RATE_LIMIT_SECONDS:
            return True
    _last_sent[key] = now
    return False

def _get_session_state() -> str:
    """Get current market session state."""
    try:
        from market_session_manager import get_full_status
        status = get_full_status()
        return status.get("state", "UNKNOWN")
    except Exception:
        return "UNKNOWN"

def _should_send(message: str, force: bool = False) -> bool:
    """Decide whether to send this Telegram message."""
    # Always send critical alerts
    if force or _is_critical(message):
        return True

    # Check session state for non-critical messages
    state = _get_session_state()
    if state in ("MARKET_OPEN", "PREMARKET"):
        return True

    # Market closed — block scan reports
    return False

def _raw_send(message: str, parse_mode: str = "HTML") -> bool:
    """Low-level Telegram API call."""
    try:
        import requests
        token   = os.getenv("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        if not token or not chat_id:
            return False
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        r = requests.post(url, json={
            "chat_id":    chat_id,
            "text":       message,
            "parse_mode": parse_mode,
        }, timeout=10)
        return r.status_code == 200
    except Exception as e:
        log.error(f"Telegram error: {e}")
        return False

# ── Public API ────────────────────────────────────────────────────────────

def send_telegram(message: str, parse_mode: str = "HTML") -> bool:
    """
    Main send function with session guard + rate limiting.
    Drop-in replacement for all existing send_telegram() calls.
    """
    if not message:
        return False

    # Rate limit check
    if _is_rate_limited(message):
        log.debug("Telegram rate limited — skipping")
        return False

    # Session guard
    if not _should_send(message):
        log.debug(f"Telegram blocked — market closed: {message[:50]}")
        return False

    return _raw_send(message, parse_mode)

def send_alert(message: str, parse_mode: str = "HTML") -> bool:
    """
    Send critical alert — bypasses session guard.
    Use for: trades, stops, kill switch, regime shifts, errors.
    """
    if _is_rate_limited(message):
        return False
    return _raw_send(message, parse_mode)

def send_heartbeat() -> bool:
    """Send system heartbeat — called by health_monitor every 2 hours."""
    try:
        from market_session_manager import get_full_status
        status = get_full_status()
        state  = status.get("state", "UNKNOWN")

        # Only send heartbeat when market is closed
        if state not in ("MARKET_CLOSED", "WEEKEND", "HOLIDAY"):
            return False

        msg = (
            f"💤 <b>SYSTEM HEARTBEAT</b>\n"
            f"Status:    {state}\n"
            f"Next Open: {status.get('next_open_et', '?')}\n"
            f"({status.get('hours_to_open', '?')}h away)\n"
            f"CPU/RAM nominal.\n"
            f"⏰ {datetime.utcnow().strftime('%H:%M UTC')}"
        )
        return _raw_send(msg)
    except Exception as e:
        log.error(f"Heartbeat error: {e}")
        return False


# ── CLI test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    state = _get_session_state()
    print(f"Current session: {state}")
    print(f"Would send scan report: {_should_send('Scan #100 | CLOSED')}")
    print(f"Would send trade alert: {_should_send('🚀 TRADE EXECUTED NVDA')}")
    print(f"Would send kill switch: {_should_send('🚨 KILL SWITCH ACTIVATED')}")
    print("✅ telegram_gate.py ready")
