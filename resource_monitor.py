#!/usr/bin/env python3
"""
resource_monitor.py — Memory & CPU Protection
Minervini Trading Bot | Production Stabilization
Monitors RAM, CPU, threads and prevents system freeze.
"""

import os, sys, time, gc, threading, json
import psutil
from datetime import datetime

try:
    from logger import get_logger
    log = get_logger("resource_monitor")
except ImportError:
    import logging
    log = logging.getLogger("resource_monitor")
    logging.basicConfig(level=logging.INFO)

from dotenv import load_dotenv
load_dotenv("/root/.env")

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ── Thresholds ────────────────────────────────────────────────
RAM_WARNING   = 80   # % — send warning
RAM_CRITICAL  = 90   # % — force GC + alert
CPU_WARNING   = 80   # %
CPU_CRITICAL  = 95   # %
DISK_WARNING  = 85   # %
THREAD_LIMIT  = 200  # max threads before alert

CHECK_INTERVAL = 30  # seconds
METRICS_FILE   = "/root/logs/resource_metrics.json"
os.makedirs("/root/logs", exist_ok=True)

_last_alert: dict = {}
ALERT_COOLDOWN = 300  # 5 min


def send_telegram(msg: str, key: str = "generic"):
    now = time.time()
    if now - _last_alert.get(key, 0) < ALERT_COOLDOWN:
        return
    _last_alert[key] = now
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
        log.error(f"Telegram failed: {e}")


def get_metrics() -> dict:
    """Collect all system metrics."""
    cpu    = psutil.cpu_percent(interval=1)
    mem    = psutil.virtual_memory()
    disk   = psutil.disk_usage("/")
    threads = threading.active_count()

    # Per-process breakdown for Python processes
    python_procs = []
    for proc in psutil.process_iter(["pid", "name", "cmdline", "memory_percent", "cpu_percent"]):
        try:
            if "python" in (proc.info["name"] or "").lower():
                cmdline = " ".join(proc.info["cmdline"] or [])
                # Extract script name
                script = "unknown"
                for part in (proc.info["cmdline"] or []):
                    if part.endswith(".py"):
                        script = os.path.basename(part)
                        break
                python_procs.append({
                    "pid":    proc.info["pid"],
                    "script": script,
                    "ram_%":  round(proc.info["memory_percent"], 2),
                    "cpu_%":  round(proc.info["cpu_percent"], 2),
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    return {
        "timestamp":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "cpu_percent":  cpu,
        "ram_percent":  mem.percent,
        "ram_used_gb":  round(mem.used / 1024**3, 2),
        "ram_total_gb": round(mem.total / 1024**3, 2),
        "disk_percent": disk.percent,
        "disk_free_gb": round(disk.free / 1024**3, 2),
        "threads":      threads,
        "python_procs": sorted(python_procs, key=lambda x: x["ram_%"], reverse=True)[:10],
    }


def check_and_protect(metrics: dict):
    """Check thresholds and take protective action."""
    ram  = metrics["ram_percent"]
    cpu  = metrics["cpu_percent"]
    disk = metrics["disk_percent"]
    threads = metrics["threads"]

    # ── RAM ───────────────────────────────────────────────────
    if ram >= RAM_CRITICAL:
        log.error(f"RAM CRITICAL: {ram}% — forcing garbage collection")
        gc.collect()
        send_telegram(
            f"🚨 <b>RAM CRITICAL: {ram}%</b>\n"
            f"Used: {metrics['ram_used_gb']}GB / {metrics['ram_total_gb']}GB\n"
            f"GC forced. Consider restarting heavy processes.",
            key="ram_critical"
        )
    elif ram >= RAM_WARNING:
        log.warning(f"RAM WARNING: {ram}%")
        send_telegram(
            f"⚠️ <b>RAM WARNING: {ram}%</b>\n"
            f"Used: {metrics['ram_used_gb']}GB / {metrics['ram_total_gb']}GB",
            key="ram_warning"
        )

    # ── CPU ───────────────────────────────────────────────────
    if cpu >= CPU_CRITICAL:
        log.error(f"CPU CRITICAL: {cpu}%")
        send_telegram(f"🚨 <b>CPU CRITICAL: {cpu}%</b>", key="cpu_critical")
    elif cpu >= CPU_WARNING:
        log.warning(f"CPU WARNING: {cpu}%")

    # ── Disk ──────────────────────────────────────────────────
    if disk >= DISK_WARNING:
        log.error(f"DISK WARNING: {disk}% — {metrics['disk_free_gb']}GB free")
        send_telegram(
            f"⚠️ <b>DISK WARNING: {disk}%</b>\n"
            f"Free: {metrics['disk_free_gb']}GB\n"
            f"Run: find /root/logs -name '*.out' -size +50M",
            key="disk_warning"
        )

    # ── Threads ───────────────────────────────────────────────
    if threads > THREAD_LIMIT:
        log.error(f"THREAD OVERLOAD: {threads} active threads")
        send_telegram(
            f"⚠️ <b>THREAD OVERLOAD: {threads}</b>\n"
            f"System may be experiencing issues.",
            key="thread_overload"
        )


def save_metrics(metrics: dict):
    try:
        # Keep rolling history of last 100 entries
        history = []
        if os.path.exists(METRICS_FILE):
            with open(METRICS_FILE) as f:
                data = json.load(f)
                history = data.get("history", [])

        history.append({
            "ts":  metrics["timestamp"],
            "cpu": metrics["cpu_percent"],
            "ram": metrics["ram_percent"],
            "disk": metrics["disk_percent"],
        })
        history = history[-100:]  # keep last 100

        with open(METRICS_FILE, "w") as f:
            json.dump({
                "latest":  metrics,
                "history": history,
            }, f, indent=2)
    except Exception as e:
        log.error(f"Failed to save metrics: {e}")


def main():
    log.info("=" * 50)
    log.info("Resource Monitor started")
    log.info(f"Thresholds — RAM: {RAM_CRITICAL}% | CPU: {CPU_CRITICAL}% | Disk: {DISK_WARNING}%")
    log.info("=" * 50)

    while True:
        try:
            metrics = get_metrics()
            check_and_protect(metrics)
            save_metrics(metrics)
            log.info(
                f"Resources OK | CPU:{metrics['cpu_percent']}% "
                f"RAM:{metrics['ram_percent']}% "
                f"Disk:{metrics['disk_percent']}% "
                f"Threads:{metrics['threads']}"
            )
        except Exception:
            log.error("Resource monitor loop error", exc_info=True)
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
