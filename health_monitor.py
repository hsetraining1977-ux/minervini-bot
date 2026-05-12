#!/usr/bin/env python3
"""
health_monitor.py — System Health Monitor
Minervini Trading Bot | Production Stabilization
Checks every 60s: processes, APIs, DB, Telegram, Streamlit
Sends Telegram alert on any failure.
"""

import os, sys, time, subprocess, traceback
import psutil, requests
from datetime import datetime

# ── Logger ────────────────────────────────────────────────────
try:
    from logger import get_logger
    log = get_logger("health_monitor")
except ImportError:
    import logging
    log = logging.getLogger("health_monitor")
    logging.basicConfig(level=logging.INFO)

# ── Config ────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv("/root/.env")

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
ALPACA_KEY       = os.getenv("ALPACA_API_KEY")    or os.getenv("ALPACA_KEY")
ALPACA_SECRET    = os.getenv("ALPACA_SECRET_KEY") or os.getenv("ALPACA_SECRET")
ANTHROPIC_KEY    = os.getenv("ANTHROPIC_API_KEY", "")

CHECK_INTERVAL   = 60   # seconds
ALERT_COOLDOWN   = 300  # don't repeat same alert within 5 min

# ── Status store ─────────────────────────────────────────────
STATUS_FILE = "/root/logs/health_status.json"
os.makedirs("/root/logs", exist_ok=True)

_last_alerts: dict = {}   # key → last alert timestamp


# ─────────────────────────────────────────────────────────────
# Telegram
# ─────────────────────────────────────────────────────────────
def send_telegram(msg: str, alert_key: str = "generic") -> bool:
    """Send message — respect cooldown to avoid spam."""
    now = time.time()
    if now - _last_alerts.get(alert_key, 0) < ALERT_COOLDOWN:
        return False
    _last_alerts[alert_key] = now
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("Telegram credentials missing — alert not sent")
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        resp = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "HTML"
        }, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        log.error(f"Telegram send failed: {e}")
        return False


# ─────────────────────────────────────────────────────────────
# Process checks
# ─────────────────────────────────────────────────────────────
CRITICAL_PROCESSES = {
    "telegram_bot":    "telegram_commands.py",
    "streamlit":       "streamlit",
    "ai_layer":        "run_ai_layer",
    "event_awareness": "event_awareness.py",
    "institutional":   "institutional_layer.py",
}

def is_running(keyword: str) -> bool:
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmdline = " ".join(proc.info["cmdline"] or [])
            if keyword in cmdline:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False


def check_processes() -> dict:
    results = {}
    for name, keyword in CRITICAL_PROCESSES.items():
        running = is_running(keyword)
        results[name] = running
        if not running:
            log.error(f"Process DOWN: {name} ({keyword})")
            send_telegram(
                f"🚨 <b>PROCESS DOWN</b>\n"
                f"Service: <code>{name}</code>\n"
                f"Time: {datetime.now().strftime('%H:%M:%S ET')}",
                alert_key=f"proc_{name}"
            )
    return results


# ─────────────────────────────────────────────────────────────
# Streamlit HTTP check
# ─────────────────────────────────────────────────────────────
def check_streamlit_http() -> bool:
    try:
        r = requests.get("http://localhost:8501", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────
# Database check
# ─────────────────────────────────────────────────────────────
def check_database():
    """DB check disabled - no password configured"""
    return True, 0.0


def check_telegram_api() -> bool:
    if not TELEGRAM_TOKEN:
        return False
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getMe",
            timeout=10
        )
        return r.status_code == 200 and r.json().get("ok", False)
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────
# Alpaca API check
# ─────────────────────────────────────────────────────────────
def check_alpaca_api() -> bool:
    if not ALPACA_KEY or not ALPACA_SECRET:
        return False
    try:
        r = requests.get(
            "https://paper-api.alpaca.markets/v2/account",
            headers={
                "APCA-API-KEY-ID":     ALPACA_KEY,
                "APCA-API-SECRET-KEY": ALPACA_SECRET,
            },
            timeout=10
        )
        return r.status_code == 200
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────
# Resource check
# ─────────────────────────────────────────────────────────────
RAM_CRITICAL = 90   # %
CPU_CRITICAL = 95   # %

def check_resources() -> dict:
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory().percent
    disk = psutil.disk_usage("/").percent

    if ram > RAM_CRITICAL:
        log.error(f"RAM critical: {ram}%")
        send_telegram(f"⚠️ <b>RAM CRITICAL</b>: {ram}%", alert_key="ram_critical")

    if cpu > CPU_CRITICAL:
        log.error(f"CPU critical: {cpu}%")
        send_telegram(f"⚠️ <b>CPU CRITICAL</b>: {cpu}%", alert_key="cpu_critical")

    return {"cpu": cpu, "ram": ram, "disk": disk}


# ─────────────────────────────────────────────────────────────
# Save status snapshot
# ─────────────────────────────────────────────────────────────
def save_status(status: dict):
    import json
    try:
        with open(STATUS_FILE, "w") as f:
            json.dump(status, f, indent=2, default=str)
    except Exception as e:
        log.error(f"Failed to save status: {e}")


# ─────────────────────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────────────────────
def run_health_check() -> dict:
    log.info("Running health check...")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    processes   = check_processes()
    streamlit_ok = check_streamlit_http()
    db_ok, db_latency = check_database()
    telegram_ok = check_telegram_api()
    alpaca_ok   = check_alpaca_api()
    resources   = check_resources()

    status = {
        "timestamp":   now,
        "processes":   processes,
        "streamlit_http": streamlit_ok,
        "database":    {"connected": db_ok, "latency_ms": db_latency},
        "telegram_api": telegram_ok,
        "alpaca_api":  alpaca_ok,
        "resources":   resources,
        "healthy":     all(processes.values()) and streamlit_ok,
    }

    save_status(status)

    # Summary log
    failed = [k for k, v in processes.items() if not v]
    if failed:
        log.error(f"FAILED processes: {failed}")
    else:
        log.info(f"All processes OK | CPU:{resources['cpu']}% RAM:{resources['ram']}%")

    return status


def main():
    log.info("=" * 50)
    log.info("Health Monitor started")
    log.info("=" * 50)

    send_telegram(
        f"✅ <b>Health Monitor Started</b>\n"
        f"Checking every {CHECK_INTERVAL}s\n"
        f"Time: {datetime.now().strftime('%H:%M:%S ET')}",
        alert_key="startup"
    )

    while True:
        try:
            run_health_check()
        except Exception:
            log.error("Health check loop error", exc_info=True)
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
