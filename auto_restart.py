#!/usr/bin/env python3
"""
auto_restart.py — Auto Restart Recovery
Minervini Trading Bot | Production Stabilization
Monitors critical services and restarts them if down.
"""

import os, sys, time, subprocess, json
import psutil
from datetime import datetime

try:
    from logger import get_logger
    log = get_logger("auto_restart")
except ImportError:
    import logging
    log = logging.getLogger("auto_restart")
    logging.basicConfig(level=logging.INFO)

from dotenv import load_dotenv
load_dotenv("/root/.env")

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

CHECK_INTERVAL   = 30    # check every 30 seconds
MAX_RESTARTS     = 5     # max restarts per service before giving up
RESTART_COOLDOWN = 120   # seconds between restarts for same service

# ── Service definitions ───────────────────────────────────────
# Each entry: keyword to detect process, command to restart it
SERVICES = {
    "telegram_commands": {
        "keyword": "telegram_commands.py",
        "cmd":     "python3 /root/telegram_commands.py >> /root/telegram.out 2>&1",
        "log":     "/root/telegram.out",
    },
    "streamlit": {
        "keyword": "streamlit",
        "cmd":     "~/.local/bin/streamlit run /root/dashboard.py --server.port 8501 --server.address 0.0.0.0 >> /root/streamlit.out 2>&1",
        "log":     "/root/streamlit.out",
    },
}

# ── Restart tracking ─────────────────────────────────────────
_restart_counts: dict = {name: 0 for name in SERVICES}
_last_restart:   dict = {name: 0.0 for name in SERVICES}


def send_telegram(msg: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        import requests
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e:
        log.error(f"Telegram send failed: {e}")


def is_running(keyword: str) -> bool:
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmdline = " ".join(proc.info["cmdline"] or [])
            if keyword in cmdline:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False


def restart_service(name: str, config: dict) -> bool:
    """Attempt to restart a service. Returns True if successful."""
    now = time.time()

    # Cooldown check
    if now - _last_restart[name] < RESTART_COOLDOWN:
        return False

    # Max restarts check
    if _restart_counts[name] >= MAX_RESTARTS:
        log.error(f"Service {name} exceeded MAX_RESTARTS ({MAX_RESTARTS}) — giving up")
        send_telegram(
            f"🔴 <b>SERVICE FAILED PERMANENTLY</b>\n"
            f"Service: <code>{name}</code>\n"
            f"Max restarts ({MAX_RESTARTS}) exceeded.\n"
            f"Manual intervention required!"
        )
        return False

    log.warning(f"Restarting service: {name} (attempt #{_restart_counts[name]+1})")

    try:
        cmd = config["cmd"]
        # Use nohup to keep it running after restart
        full_cmd = f"nohup {cmd} &"
        subprocess.Popen(
            full_cmd,
            shell=True,
            cwd="/root",
            env={**os.environ,
                 "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY", "")},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(5)  # Wait for process to start

        _restart_counts[name] += 1
        _last_restart[name] = now

        # Verify it actually started
        if is_running(config["keyword"]):
            log.info(f"✅ Service {name} restarted successfully")
            send_telegram(
                f"🔄 <b>SERVICE RESTARTED</b>\n"
                f"Service: <code>{name}</code>\n"
                f"Attempt: #{_restart_counts[name]}\n"
                f"Time: {datetime.now().strftime('%H:%M:%S ET')}"
            )
            return True
        else:
            log.error(f"❌ Service {name} failed to start after restart")
            send_telegram(
                f"❌ <b>RESTART FAILED</b>\n"
                f"Service: <code>{name}</code> did not start\n"
                f"Check logs: {config['log']}"
            )
            return False

    except Exception as e:
        log.error(f"Error restarting {name}: {e}", exc_info=True)
        return False


def check_and_recover():
    """Main check loop — verify each service and restart if needed."""
    for name, config in SERVICES.items():
        try:
            if not is_running(config["keyword"]):
                log.warning(f"Service DOWN: {name}")
                restart_service(name, config)
            else:
                # Reset restart count if running fine
                if _restart_counts[name] > 0:
                    log.info(f"Service {name} is back online — resetting restart count")
                    _restart_counts[name] = 0
        except Exception as e:
            log.error(f"Error checking {name}: {e}", exc_info=True)


def save_restart_stats():
    stats = {
        "timestamp": datetime.now().isoformat(),
        "restarts": _restart_counts,
        "last_restart": {k: datetime.fromtimestamp(v).isoformat()
                         if v > 0 else None
                         for k, v in _last_restart.items()}
    }
    os.makedirs("/root/logs", exist_ok=True)
    with open("/root/logs/restart_stats.json", "w") as f:
        json.dump(stats, f, indent=2)


def main():
    log.info("=" * 50)
    log.info("Auto Restart Recovery started")
    log.info(f"Monitoring: {list(SERVICES.keys())}")
    log.info(f"Check interval: {CHECK_INTERVAL}s")
    log.info("=" * 50)

    send_telegram(
        f"🛡️ <b>Auto Restart Monitor Started</b>\n"
        f"Monitoring {len(SERVICES)} services\n"
        f"Time: {datetime.now().strftime('%H:%M:%S ET')}"
    )

    check_count = 0
    while True:
        try:
            check_and_recover()
            check_count += 1
            # Save stats every 10 checks
            if check_count % 10 == 0:
                save_restart_stats()
        except Exception:
            log.error("Auto-restart loop error", exc_info=True)
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
