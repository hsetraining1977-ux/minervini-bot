#!/usr/bin/env python3
"""
log_rotator.py — Automatic Log Rotation
Minervini Trading Bot | Production Stabilization
Prevents log files from growing too large.
Runs as a daily cron or standalone daemon.
"""

import os, sys, gzip, shutil, time
from datetime import datetime, timedelta
from pathlib import Path

try:
    from logger import get_logger
    log = get_logger("log_rotator")
except ImportError:
    import logging
    log = logging.getLogger("log_rotator")
    logging.basicConfig(level=logging.INFO)

# ── Config ────────────────────────────────────────────────────
LOG_FILES = [
    "/root/nohup.out",
    "/root/orchestrator.out",
    "/root/telegram.out",
    "/root/ai.out",
    "/root/event.out",
    "/root/institutional.out",
    "/root/streamlit.out",
    "/root/intraday.out",
    "/root/upgrade.out",
    "/root/phase2.out",
    "/root/phase3.out",
]

LOG_DIR = "/root/logs"
ARCHIVE_DIR = "/root/logs/archive"
os.makedirs(ARCHIVE_DIR, exist_ok=True)

MAX_SIZE_MB  = 50   # rotate when file exceeds this size
MAX_AGE_DAYS = 7    # delete archives older than this
RUN_INTERVAL = 3600 # check every hour (in daemon mode)


def get_size_mb(path: str) -> float:
    try:
        return os.path.getsize(path) / (1024 * 1024)
    except FileNotFoundError:
        return 0.0


def rotate_file(path: str):
    """Compress and archive a log file, then truncate the original."""
    if not os.path.exists(path):
        return

    size_mb = get_size_mb(path)
    if size_mb < MAX_SIZE_MB:
        return

    filename = os.path.basename(path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"{filename}.{timestamp}.gz"
    archive_path = os.path.join(ARCHIVE_DIR, archive_name)

    try:
        # Compress to archive
        with open(path, "rb") as f_in:
            with gzip.open(archive_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

        # Truncate original (don't delete — process may still write to it)
        with open(path, "w") as f:
            f.write(f"# Log rotated at {datetime.now().isoformat()}\n")
            f.write(f"# Archive: {archive_path}\n")

        log.info(f"Rotated: {filename} ({size_mb:.1f}MB) → {archive_name}")

    except Exception as e:
        log.error(f"Failed to rotate {path}: {e}", exc_info=True)


def clean_old_archives():
    """Delete archives older than MAX_AGE_DAYS."""
    cutoff = datetime.now() - timedelta(days=MAX_AGE_DAYS)
    deleted = 0
    freed_mb = 0.0

    for archive in Path(ARCHIVE_DIR).glob("*.gz"):
        try:
            mtime = datetime.fromtimestamp(archive.stat().st_mtime)
            if mtime < cutoff:
                size_mb = archive.stat().st_size / (1024 * 1024)
                archive.unlink()
                deleted += 1
                freed_mb += size_mb
                log.info(f"Deleted old archive: {archive.name}")
        except Exception as e:
            log.error(f"Error deleting archive {archive}: {e}")

    if deleted:
        log.info(f"Cleaned {deleted} archives, freed {freed_mb:.1f}MB")


def run_rotation():
    """Run one full rotation cycle."""
    log.info("Starting log rotation cycle...")
    rotated = 0

    for log_file in LOG_FILES:
        size_mb = get_size_mb(log_file)
        if size_mb >= MAX_SIZE_MB:
            rotate_file(log_file)
            rotated += 1

    clean_old_archives()

    # Also rotate files in /root/logs/
    for log_file in Path(LOG_DIR).glob("*.log"):
        size_mb = get_size_mb(str(log_file))
        if size_mb >= MAX_SIZE_MB:
            rotate_file(str(log_file))
            rotated += 1

    log.info(f"Rotation cycle complete. Rotated: {rotated} files")
    return rotated


def print_log_sizes():
    """Print current sizes of all log files."""
    print("\n📊 Log File Sizes:")
    print("-" * 40)
    total = 0.0
    for path in LOG_FILES:
        size = get_size_mb(path)
        total += size
        status = "⚠️" if size > MAX_SIZE_MB * 0.8 else "✅"
        exists = "✅" if os.path.exists(path) else "❌ missing"
        print(f"  {status} {os.path.basename(path):30s} {size:6.1f} MB  {exists}")
    print("-" * 40)
    print(f"  Total: {total:.1f} MB")

    # Archive stats
    archives = list(Path(ARCHIVE_DIR).glob("*.gz"))
    if archives:
        archive_size = sum(f.stat().st_size for f in archives) / (1024*1024)
        print(f"\n📦 Archives: {len(archives)} files, {archive_size:.1f} MB")
    print()


def setup_cron():
    """Add cron job for daily rotation at 2 AM."""
    cron_line = "0 2 * * * python3 /root/log_rotator.py --run-once >> /root/logs/rotator.log 2>&1"
    try:
        result = os.popen("crontab -l 2>/dev/null").read()
        if "log_rotator" not in result:
            new_cron = result.strip() + f"\n{cron_line}\n"
            os.popen(f'echo "{new_cron}" | crontab -')
            log.info("Cron job added for daily log rotation at 2 AM")
            print("✅ Cron job added: daily rotation at 2 AM")
        else:
            print("✅ Cron job already exists")
    except Exception as e:
        log.error(f"Failed to setup cron: {e}")


def main_daemon():
    """Run as daemon — check every hour."""
    log.info("Log Rotator daemon started")
    while True:
        try:
            run_rotation()
        except Exception:
            log.error("Rotation error", exc_info=True)
        time.sleep(RUN_INTERVAL)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Log Rotator")
    parser.add_argument("--run-once",  action="store_true", help="Run once and exit")
    parser.add_argument("--daemon",    action="store_true", help="Run as daemon")
    parser.add_argument("--status",    action="store_true", help="Show log sizes")
    parser.add_argument("--setup-cron",action="store_true", help="Add cron job")
    args = parser.parse_args()

    if args.status:
        print_log_sizes()
    elif args.run_once:
        run_rotation()
    elif args.setup_cron:
        setup_cron()
    elif args.daemon:
        main_daemon()
    else:
        # Default: show status then run once
        print_log_sizes()
        run_rotation()
