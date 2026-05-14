#!/usr/bin/env python3
"""
auto_restart.py — watches critical processes and restarts them if they die.
Runs as daemon every 60 seconds.
Processes watched: ai_layer, regime_sync, institutional_regime_classifier
"""

import subprocess, time, os, logging
from datetime import datetime

LOG_FILE = "/root/logs/auto_restart.log"
os.makedirs("/root/logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [AutoRestart] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# ─── Process definitions ───────────────────────────────────────────────
PROCESSES = [
    {
        "name": "ai_layer",
        "match": "ai_layer.py",
        "cmd": "nohup bash /root/run_ai_layer.sh >> /root/ai.out 2>&1 &",
        "wait": 3,
    },
    {
        "name": "regime_sync",
        "match": "regime_sync.py",
        "cmd": "nohup nice -n 19 python3 /root/regime_sync.py --daemon > /root/logs/regime_sync.log 2>&1 &",
        "wait": 2,
    },
    {
        "name": "institutional_regime",
        "match": "institutional_regime_classifier.py",
        "cmd": "nohup nice -n 19 python3 /root/institutional_regime_classifier.py --daemon > /root/logs/institutional_regime.log 2>&1 &",
        "wait": 2,
    },
]

# ─── Helpers ────────────────────────────────────────────────────────────
def is_running(match: str) -> bool:
    try:
        result = subprocess.run(
            ["pgrep", "-f", match],
            capture_output=True, text=True
        )
        return result.returncode == 0
    except Exception:
        return False

def restart_process(proc: dict) -> bool:
    try:
        log.warning(f"⚠ {proc['name']} is DOWN — restarting...")
        subprocess.run(proc["cmd"], shell=True)
        time.sleep(proc["wait"])
        if is_running(proc["match"]):
            log.info(f"✅ {proc['name']} restarted successfully")
            return True
        else:
            log.error(f"❌ {proc['name']} failed to restart")
            return False
    except Exception as e:
        log.error(f"❌ Error restarting {proc['name']}: {e}")
        return False

# ─── Main loop ──────────────────────────────────────────────────────────
def run_daemon(interval_seconds: int = 60):
    log.info("=" * 60)
    log.info("Auto Restart Daemon starting...")
    log.info(f"Watching {len(PROCESSES)} processes every {interval_seconds}s")
    log.info("=" * 60)

    while True:
        try:
            all_ok = True
            for proc in PROCESSES:
                if not is_running(proc["match"]):
                    all_ok = False
                    restart_process(proc)

            if all_ok:
                log.info(f"✅ All {len(PROCESSES)} processes running OK")

        except Exception as e:
            log.error(f"Watch cycle error: {e}")

        time.sleep(interval_seconds)

if __name__ == "__main__":
    import sys
    if "--daemon" in sys.argv:
        run_daemon()
    else:
        # Single check
        log.info("Running single check...")
        for proc in PROCESSES:
            status = "✅ running" if is_running(proc["match"]) else "❌ DOWN"
            log.info(f"  {proc['name']}: {status}")
