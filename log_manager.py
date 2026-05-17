#!/usr/bin/env python3
"""
log_manager.py — Minervini AI Log Manager
Phase 6: Rotation, compression, auto-cleanup
- Keep last 7 days only
- Compress logs > 1MB
- Delete logs > 14 days
- Run as daemon every 6 hours
"""

import os, gzip, shutil, logging, time
from pathlib import Path
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

LOGS_DIR     = Path("/root/logs")
ARCHIVE_DIR  = Path("/root/logs/archive")
MAX_SIZE_MB  = 1       # Compress if > 1MB
KEEP_DAYS    = 7       # Keep logs for 7 days
DELETE_DAYS  = 14      # Delete after 14 days
CHECK_HOURS  = 6       # Run every 6 hours

# Logs to never delete (critical)
PROTECTED = {"errors.log", "health_status.json", "health.out"}

def compress_file(path: Path) -> bool:
    """Compress a log file with gzip."""
    try:
        gz_path = path.with_suffix(path.suffix + ".gz")
        with open(path, 'rb') as f_in:
            with gzip.open(gz_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        path.unlink()
        log.info(f"Compressed: {path.name} → {gz_path.name}")
        return True
    except Exception as e:
        log.error(f"Compress failed {path.name}: {e}")
        return False

def truncate_large_log(path: Path, keep_lines: int = 1000):
    """Keep only last N lines of a large active log."""
    try:
        lines = path.read_text(errors="ignore").splitlines()
        if len(lines) > keep_lines * 2:
            kept = lines[-keep_lines:]
            path.write_text("\n".join(kept) + "\n")
            log.info(f"Truncated: {path.name} ({len(lines)} → {keep_lines} lines)")
            return True
    except Exception as e:
        log.error(f"Truncate failed {path.name}: {e}")
    return False

def rotate_logs():
    """Main rotation logic."""
    ARCHIVE_DIR.mkdir(exist_ok=True)
    now = datetime.now()
    stats = {
        "compressed": 0,
        "deleted": 0,
        "truncated": 0,
        "total_freed_mb": 0.0,
    }

    for f in LOGS_DIR.glob("*"):
        if not f.is_file():
            continue
        if f.name in PROTECTED:
            continue
        if f.suffix == ".gz":
            continue

        size_mb = f.stat().st_size / 1024 / 1024
        age_days = (now - datetime.fromtimestamp(f.stat().st_mtime)).days

        # Delete very old logs
        if age_days > DELETE_DAYS and f.name not in PROTECTED:
            freed = size_mb
            f.unlink()
            stats["deleted"] += 1
            stats["total_freed_mb"] += freed
            log.info(f"Deleted old log: {f.name} ({age_days}d old)")
            continue

        # Compress large logs older than 1 day
        if size_mb > MAX_SIZE_MB and age_days >= 1:
            # Move to archive first
            archive_path = ARCHIVE_DIR / f"{f.stem}_{now.strftime('%Y%m%d')}{f.suffix}"
            shutil.copy2(f, archive_path)
            if compress_file(archive_path):
                # Clear original log (keep it active but empty)
                f.write_text(f"# Log rotated {now.isoformat()}\n")
                stats["compressed"] += 1
                stats["total_freed_mb"] += size_mb
            continue

        # Truncate very large active logs
        if size_mb > 5:
            if truncate_large_log(f, keep_lines=2000):
                stats["truncated"] += 1

    # Clean old archive files
    for f in ARCHIVE_DIR.glob("*.gz"):
        age_days = (now - datetime.fromtimestamp(f.stat().st_mtime)).days
        if age_days > DELETE_DAYS:
            f.unlink()
            log.info(f"Deleted archive: {f.name}")

    return stats

def get_log_summary() -> dict:
    """Get current log sizes summary."""
    files = []
    total_mb = 0.0
    for f in LOGS_DIR.glob("*"):
        if f.is_file():
            size_mb = round(f.stat().st_size / 1024 / 1024, 2)
            total_mb += size_mb
            files.append({"file": f.name, "size_mb": size_mb})
    files.sort(key=lambda x: x["size_mb"], reverse=True)
    return {
        "total_mb": round(total_mb, 2),
        "file_count": len(files),
        "top_5": files[:5],
    }

def run_daemon():
    """Run as background daemon."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [LogManager] %(message)s",
        handlers=[
            logging.FileHandler("/root/logs/log_manager.log"),
            logging.StreamHandler(),
        ]
    )
    log.info("Log Manager daemon started")

    while True:
        try:
            summary_before = get_log_summary()
            log.info(f"Before: {summary_before['total_mb']}MB across {summary_before['file_count']} files")

            stats = rotate_logs()

            summary_after = get_log_summary()
            log.info(f"After:  {summary_after['total_mb']}MB across {summary_after['file_count']} files")
            log.info(f"Freed:  {stats['total_freed_mb']:.1f}MB | "
                     f"Compressed: {stats['compressed']} | "
                     f"Deleted: {stats['deleted']} | "
                     f"Truncated: {stats['truncated']}")

        except Exception as e:
            log.error(f"Rotation error: {e}")

        time.sleep(CHECK_HOURS * 3600)

if __name__ == "__main__":
    import sys
    if "--daemon" in sys.argv:
        run_daemon()
    else:
        # One-time run
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        print("\n" + "="*50)
        print("  LOG MANAGER — ONE-TIME CLEANUP")
        print("="*50)

        before = get_log_summary()
        print(f"\nBefore: {before['total_mb']}MB ({before['file_count']} files)")
        for f in before["top_5"]:
            print(f"  {f['file']:40s} {f['size_mb']}MB")

        stats = rotate_logs()

        after = get_log_summary()
        print(f"\nAfter:  {after['total_mb']}MB ({after['file_count']} files)")
        print(f"\nFreed:  {stats['total_freed_mb']:.1f}MB")
        print(f"Compressed: {stats['compressed']} | Deleted: {stats['deleted']} | Truncated: {stats['truncated']}")
        print("="*50)
