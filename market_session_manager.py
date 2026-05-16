#!/usr/bin/env python3
"""
market_session_manager.py
Detects US market sessions with automatic DST handling.
Primary user timezone: Asia/Riyadh (UTC+3)
"""

from datetime import datetime, time, date, timedelta
from zoneinfo import ZoneInfo
from typing import Tuple
import logging

log = logging.getLogger(__name__)

# ── Timezones ────────────────────────────────────────────────────────────
TZ_ET  = ZoneInfo("America/New_York")   # NYSE/NASDAQ
TZ_SA  = ZoneInfo("Asia/Riyadh")        # Saudi Arabia (UTC+3, no DST)

# ── Session boundaries (ET) ──────────────────────────────────────────────
PREMARKET_START  = time(4,  0)   # 04:00 ET
MARKET_OPEN      = time(9, 30)   # 09:30 ET
MARKET_CLOSE     = time(16, 0)   # 16:00 ET
AFTERHOURS_END   = time(20, 0)   # 20:00 ET

# ── Session states ────────────────────────────────────────────────────────
class SessionState:
    PREMARKET     = "PREMARKET"
    MARKET_OPEN   = "MARKET_OPEN"
    AFTER_HOURS   = "AFTER_HOURS"
    MARKET_CLOSED = "MARKET_CLOSED"
    WEEKEND       = "WEEKEND"
    HOLIDAY       = "HOLIDAY"

# ── US Market Holidays 2025–2026 ─────────────────────────────────────────
US_HOLIDAYS = {
    # 2025
    date(2025,  1,  1): "New Year's Day",
    date(2025,  1, 20): "MLK Day",
    date(2025,  2, 17): "Presidents Day",
    date(2025,  4, 18): "Good Friday",
    date(2025,  5, 26): "Memorial Day",
    date(2025,  6, 19): "Juneteenth",
    date(2025,  7,  4): "Independence Day",
    date(2025,  9,  1): "Labor Day",
    date(2025, 11, 27): "Thanksgiving",
    date(2025, 12, 25): "Christmas",
    # 2026
    date(2026,  1,  1): "New Year's Day",
    date(2026,  1, 19): "MLK Day",
    date(2026,  2, 16): "Presidents Day",
    date(2026,  4,  3): "Good Friday",
    date(2026,  5, 25): "Memorial Day",
    date(2026,  6, 19): "Juneteenth",
    date(2026,  7,  3): "Independence Day (observed)",
    date(2026,  9,  7): "Labor Day",
    date(2026, 11, 26): "Thanksgiving",
    date(2026, 12, 25): "Christmas",
}

# ── Early close days (1:00 PM ET) ────────────────────────────────────────
EARLY_CLOSE_DAYS = {
    date(2025,  7,  3): time(13, 0),
    date(2025, 11, 28): time(13, 0),
    date(2025, 12, 24): time(13, 0),
    date(2026,  7,  2): time(13, 0),
    date(2026, 11, 27): time(13, 0),
    date(2026, 12, 24): time(13, 0),
}


def now_et() -> datetime:
    return datetime.now(TZ_ET)

def now_sa() -> datetime:
    return datetime.now(TZ_SA)

def get_session_state(dt_et: datetime = None) -> Tuple[str, str]:
    """
    Returns (session_state, description) based on current ET time.
    """
    if dt_et is None:
        dt_et = now_et()

    d   = dt_et.date()
    t   = dt_et.time()
    dow = dt_et.weekday()   # 0=Mon … 6=Sun

    # Weekend
    if dow >= 5:
        return SessionState.WEEKEND, f"Weekend — {d.strftime('%A')}"

    # Holiday
    if d in US_HOLIDAYS:
        return SessionState.HOLIDAY, f"US Holiday: {US_HOLIDAYS[d]}"

    # Early close
    market_close = EARLY_CLOSE_DAYS.get(d, MARKET_CLOSE)

    # Session logic
    if t < PREMARKET_START:
        return SessionState.MARKET_CLOSED, "Overnight — market closed"

    if PREMARKET_START <= t < MARKET_OPEN:
        return SessionState.PREMARKET, f"Pre-market ({PREMARKET_START.strftime('%H:%M')}–{MARKET_OPEN.strftime('%H:%M')} ET)"

    if MARKET_OPEN <= t < market_close:
        mins_left = int((
            datetime.combine(d, market_close, tzinfo=TZ_ET) - dt_et
        ).total_seconds() / 60)
        return SessionState.MARKET_OPEN, f"Market open — {mins_left}m remaining"

    if market_close <= t < AFTERHOURS_END:
        return SessionState.AFTER_HOURS, f"After-hours ({MARKET_CLOSE.strftime('%H:%M')}–{AFTERHOURS_END.strftime('%H:%M')} ET)"

    return SessionState.MARKET_CLOSED, "Post-market closed"


def get_full_status() -> dict:
    """Returns full session status dict for use by other modules."""
    dt_et = now_et()
    dt_sa = now_sa()
    state, description = get_session_state(dt_et)

    is_active      = state == SessionState.MARKET_OPEN
    is_premarket   = state == SessionState.PREMARKET
    is_after_hours = state == SessionState.AFTER_HOURS
    is_closed      = state in (
        SessionState.MARKET_CLOSED,
        SessionState.WEEKEND,
        SessionState.HOLIDAY
    )

    # Next market open (ET)
    next_open = _next_market_open(dt_et)
    hours_to_open = (next_open - dt_et).total_seconds() / 3600 if next_open else None

    return {
        "state":           state,
        "description":     description,
        "is_market_open":  is_active,
        "is_premarket":    is_premarket,
        "is_after_hours":  is_after_hours,
        "is_closed":       is_closed,
        "time_et":         dt_et.strftime("%Y-%m-%d %H:%M:%S ET"),
        "time_sa":         dt_sa.strftime("%Y-%m-%d %H:%M:%S AST"),
        "date_et":         dt_et.date().isoformat(),
        "next_open_et":    next_open.strftime("%Y-%m-%d %H:%M ET") if next_open else "Unknown",
        "hours_to_open":   round(hours_to_open, 1) if hours_to_open else None,
        "timestamp":       datetime.utcnow().isoformat(),
    }


def get_scan_interval_seconds(state: str) -> int:
    """Returns recommended scanner interval based on session state."""
    return {
        SessionState.MARKET_OPEN:   60,    # Every 1 min during market
        SessionState.PREMARKET:     300,   # Every 5 min pre-market
        SessionState.AFTER_HOURS:   600,   # Every 10 min after-hours
        SessionState.MARKET_CLOSED: 3600,  # Every 1 hour closed
        SessionState.WEEKEND:       7200,  # Every 2 hours weekend
        SessionState.HOLIDAY:       7200,  # Every 2 hours holiday
    }.get(state, 3600)


def get_adaptive_interval_seconds(state: str) -> int:
    """Returns recommended adaptive learning interval based on session state."""
    return {
        SessionState.MARKET_OPEN:   1800,   # 30 min during market
        SessionState.PREMARKET:     3600,   # 1 hour pre-market
        SessionState.AFTER_HOURS:   3600,   # 1 hour after-hours
        SessionState.MARKET_CLOSED: 14400,  # 4 hours closed
        SessionState.WEEKEND:       28800,  # 8 hours weekend
        SessionState.HOLIDAY:       28800,  # 8 hours holiday
    }.get(state, 3600)


def should_send_telegram_summary(state: str) -> bool:
    """Should we send hourly Telegram summaries?"""
    return state in (SessionState.MARKET_OPEN, SessionState.PREMARKET)


def _next_market_open(dt_et: datetime) -> datetime:
    """Find next market open datetime in ET."""
    check = dt_et
    for _ in range(10):
        check += timedelta(days=1)
        d   = check.date()
        dow = check.weekday()
        if dow >= 5:
            continue
        if d in US_HOLIDAYS:
            continue
        return datetime.combine(d, MARKET_OPEN, tzinfo=TZ_ET)
    return None


def get_saudi_market_times() -> dict:
    """Returns today's market hours in Saudi time for display."""
    dt_et = now_et()
    d     = dt_et.date()

    def et_to_sa(t: time) -> str:
        dt = datetime.combine(d, t, tzinfo=TZ_ET).astimezone(TZ_SA)
        return dt.strftime("%H:%M AST")

    close = EARLY_CLOSE_DAYS.get(d, MARKET_CLOSE)
    early = d in EARLY_CLOSE_DAYS

    return {
        "premarket_start_sa":  et_to_sa(PREMARKET_START),
        "market_open_sa":      et_to_sa(MARKET_OPEN),
        "market_close_sa":     et_to_sa(close),
        "afterhours_end_sa":   et_to_sa(AFTERHOURS_END),
        "early_close":         early,
        "date":                d.isoformat(),
    }


# ── CLI test ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    status = get_full_status()
    sa     = get_saudi_market_times()

    print("\n" + "="*55)
    print("  MARKET SESSION STATUS")
    print("="*55)
    print(f"  State:       {status['state']}")
    print(f"  Description: {status['description']}")
    print(f"  ET Time:     {status['time_et']}")
    print(f"  Saudi Time:  {status['time_sa']}")
    print(f"  Next Open:   {status['next_open_et']}")
    print(f"  Hours Away:  {status['hours_to_open']}h")
    print()
    print("  Saudi Market Hours Today:")
    print(f"  Pre-market:  {sa['premarket_start_sa']}")
    print(f"  Open:        {sa['market_open_sa']}")
    print(f"  Close:       {sa['market_close_sa']}" + (" ⚠ EARLY" if sa['early_close'] else ""))
    print(f"  After-hours: {sa['afterhours_end_sa']}")
    print()
    print(f"  Scan interval:     {get_scan_interval_seconds(status['state'])}s")
    print(f"  Adaptive interval: {get_adaptive_interval_seconds(status['state'])}s")
    print(f"  Send Telegram:     {should_send_telegram_summary(status['state'])}")
    print("="*55)
