#!/usr/bin/env python3
"""
replay_scheduler.py — Minervini AI Replay Scheduler
Phase 8: Run historical_replay_engine ONLY after market close.
- Runs once per day after market closes (16:00-20:00 ET)
- Low priority (nice 19)
- Skips weekends and holidays
- Prevents duplicate runs
"""

import os, time, logging, subprocess
from datetime import datetime, date
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ReplayScheduler] %(message)s",
    handlers=[
        logging.FileHandler("/root/logs/replay_scheduler.log"),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger(__name__)

LOCK_FILE = Path("/tmp/replay_running.lock")
LAST_RUN_FILE = Path("/tmp/replay_last_run.txt")
REPLAY_SCRIPT = "/root/historical_replay_engine.py"

def get_session():
    try:
        from market_session_manager import get_full_status
        return get_full_status()
    except Exception as e:
        log.error(f"Session check failed: {e}")
        return {}

def already_ran_today() -> bool:
    if not LAST_RUN_FILE.exists():
        return False
    last = LAST_RUN_FILE.read_text().strip()
    return last == date.today().isoformat()

def mark_ran_today():
    LAST_RUN_FILE.write_text(date.today().isoformat())

def run_replay():
    if LOCK_FILE.exists():
        log.info("Replay already running — skipping")
        return

    log.info("Starting historical replay (after-hours, low priority)...")
    LOCK_FILE.write_text(str(os.getpid()))

    try:
        result = subprocess.run(
            ["nice", "-n", "19", "python3", REPLAY_SCRIPT, "2y"],
            timeout=3600,  # Max 1 hour
            capture_output=True,
            text=True
        )
        log.info(f"Replay complete: {result.stdout[-500:] if result.stdout else 'no output'}")
        if result.returncode != 0:
            log.error(f"Replay error: {result.stderr[-200:]}")
        mark_ran_today()
    except subprocess.TimeoutExpired:
        log.warning("Replay timed out after 1 hour — stopping")
    except Exception as e:
        log.error(f"Replay failed: {e}")
    finally:
        LOCK_FILE.unlink(missing_ok=True)

def should_run_replay(status: dict) -> bool:
    state = status.get("state", "")
    # Run during after-hours or market closed (but not weekend/holiday)
    return state in ("AFTER_HOURS", "MARKET_CLOSED")

def main():
    log.info("Replay Scheduler started")

    while True:
        try:
            status = get_session()
            state = status.get("state", "UNKNOWN")

            if state in ("WEEKEND", "HOLIDAY"):
                log.info(f"Weekend/Holiday — sleeping 8h")
                time.sleep(8 * 3600)
                continue

            if already_ran_today():
                log.info(f"Already ran today — sleeping 1h")
                time.sleep(3600)
                continue

            if should_run_replay(status):
                log.info(f"Session: {state} — starting replay")
                run_replay()
                time.sleep(3600)
            else:
                log.info(f"Session: {state} — waiting for market close")
                time.sleep(1800)  # Check every 30 min

        except Exception as e:
            log.error(f"Scheduler error: {e}")
            time.sleep(1800)

if __name__ == "__main__":
    main()
