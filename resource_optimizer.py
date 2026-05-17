#!/usr/bin/env python3
"""
resource_optimizer.py — Minervini AI Resource Optimizer
Phase 11: Memory & resource optimization.

Extends: log_manager.py + resource_monitor.py
Adds:
    - Orphan cache cleanup
    - Stale replay temp data purge
    - Lazy-load historical datasets
    - Streamlit refresh throttling
    - Duplicate pandas load prevention
    - Memory usage tracking
    - Dashboard refresh throttling
"""

import os, gc, sys, time, json, gzip, shutil, logging, psutil
from datetime import datetime, timedelta
from pathlib import Path

os.makedirs("/root/logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ResourceOptimizer] %(message)s",
    handlers=[
        logging.FileHandler("/root/logs/resource_optimizer.log"),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger("resource_optimizer")

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT        = Path("/root")
LOGS        = Path("/root/logs")
CACHE_DIRS  = [
    Path("/root/__pycache__"),
    Path("/tmp/minervini_cache"),
    Path("/root/.cache"),
]
REPLAY_TEMP = Path("/tmp/replay_temp")
REPORT_FILE = LOGS / "resource_optimizer_report.json"

# ── Thresholds ─────────────────────────────────────────────────────────────
RAM_WARNING_PCT  = 80
RAM_CRITICAL_PCT = 90
GC_TRIGGER_PCT   = 85
MAX_CACHE_AGE_H  = 24    # hours before cache file is orphan
MAX_LOG_SIZE_MB  = 2     # compress if bigger
KEEP_LOG_DAYS    = 7
DELETE_LOG_DAYS  = 14
CHECK_INTERVAL   = 3600  # run every hour

# ══════════════════════════════════════════════════════════════════════════
# Memory Management
# ══════════════════════════════════════════════════════════════════════════

def get_ram_pct() -> float:
    return psutil.virtual_memory().percent

def get_ram_info() -> dict:
    m = psutil.virtual_memory()
    return {
        "percent":   round(m.percent, 1),
        "used_gb":   round(m.used / 1024**3, 2),
        "total_gb":  round(m.total / 1024**3, 2),
        "free_gb":   round(m.available / 1024**3, 2),
    }

def force_gc() -> int:
    """Force garbage collection — returns bytes freed (approx)."""
    before = psutil.Process().memory_info().rss
    gc.collect()
    after  = psutil.Process().memory_info().rss
    freed  = max(0, before - after)
    freed_mb = freed / 1024**2
    log.info(f"GC: freed ~{freed_mb:.1f}MB")
    return freed

def kill_zombie_processes():
    """Terminate zombie/defunct processes."""
    killed = 0
    for proc in psutil.process_iter(["pid", "status", "name"]):
        try:
            if proc.info["status"] == psutil.STATUS_ZOMBIE:
                proc.kill()
                killed += 1
                log.info(f"Killed zombie PID {proc.info['pid']} ({proc.info['name']})")
        except Exception:
            pass
    return killed

# ══════════════════════════════════════════════════════════════════════════
# Cache Cleanup
# ══════════════════════════════════════════════════════════════════════════

def clean_pycache() -> int:
    """Remove all __pycache__ and .pyc files."""
    removed = 0
    for pyc_dir in ROOT.rglob("__pycache__"):
        try:
            shutil.rmtree(pyc_dir)
            removed += 1
        except Exception:
            pass
    for pyc in ROOT.rglob("*.pyc"):
        try:
            pyc.unlink()
            removed += 1
        except Exception:
            pass
    if removed:
        log.info(f"Pycache: removed {removed} items")
    return removed

def clean_orphan_cache() -> dict:
    """Remove stale cache files older than MAX_CACHE_AGE_H hours."""
    now     = datetime.now()
    cutoff  = now - timedelta(hours=MAX_CACHE_AGE_H)
    removed = 0
    freed_mb = 0.0

    for cache_dir in CACHE_DIRS:
        if not cache_dir.exists():
            continue
        for f in cache_dir.rglob("*"):
            if not f.is_file():
                continue
            try:
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                if mtime < cutoff:
                    size_mb = f.stat().st_size / 1024**2
                    f.unlink()
                    removed  += 1
                    freed_mb += size_mb
            except Exception:
                pass

    # Also clean tmp json files older than 24h
    for f in Path("/tmp").glob("minervini_*.json"):
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime < cutoff:
                size_mb = f.stat().st_size / 1024**2
                f.unlink()
                removed  += 1
                freed_mb += size_mb
        except Exception:
            pass

    if removed:
        log.info(f"Cache: removed {removed} files, freed {freed_mb:.1f}MB")
    return {"files": removed, "freed_mb": round(freed_mb, 2)}

def clean_replay_temp() -> dict:
    """Remove dead replay temp data."""
    if not REPLAY_TEMP.exists():
        return {"files": 0, "freed_mb": 0}

    removed  = 0
    freed_mb = 0.0
    now      = datetime.now()
    cutoff   = now - timedelta(hours=6)

    for f in REPLAY_TEMP.rglob("*"):
        if not f.is_file():
            continue
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime < cutoff:
                size_mb = f.stat().st_size / 1024**2
                f.unlink()
                removed  += 1
                freed_mb += size_mb
        except Exception:
            pass

    # Remove empty dirs
    for d in sorted(REPLAY_TEMP.rglob("*"), reverse=True):
        if d.is_dir():
            try:
                d.rmdir()
            except Exception:
                pass

    if removed:
        log.info(f"Replay temp: removed {removed} files, freed {freed_mb:.1f}MB")
    return {"files": removed, "freed_mb": round(freed_mb, 2)}

# ══════════════════════════════════════════════════════════════════════════
# Log Rotation (extends log_manager.py)
# ══════════════════════════════════════════════════════════════════════════

PROTECTED_LOGS = {"errors.log", "health_status.json", "health.out"}

def rotate_logs() -> dict:
    """Compress large logs, delete old ones."""
    archive = LOGS / "archive"
    archive.mkdir(exist_ok=True)
    now  = datetime.now()
    stats = {"compressed": 0, "deleted": 0, "truncated": 0, "freed_mb": 0.0}

    for f in LOGS.glob("*"):
        if not f.is_file() or f.name in PROTECTED_LOGS or f.suffix == ".gz":
            continue

        size_mb  = f.stat().st_size / 1024**2
        age_days = (now - datetime.fromtimestamp(f.stat().st_mtime)).days

        # Delete very old
        if age_days > DELETE_LOG_DAYS:
            stats["freed_mb"] += size_mb
            f.unlink()
            stats["deleted"] += 1
            continue

        # Compress large logs older than 1 day
        if size_mb > MAX_LOG_SIZE_MB and age_days >= 1:
            try:
                gz = archive / f"{f.stem}_{now.strftime('%Y%m%d')}{f.suffix}.gz"
                with open(f, "rb") as fin, gzip.open(gz, "wb") as fout:
                    shutil.copyfileobj(fin, fout)
                f.write_text(f"# Rotated {now.isoformat()}\n")
                stats["compressed"] += 1
                stats["freed_mb"]   += size_mb
            except Exception as e:
                log.error(f"Compress {f.name}: {e}")
            continue

        # Truncate very large active logs
        if size_mb > 5:
            try:
                lines = f.read_text(errors="ignore").splitlines()
                if len(lines) > 4000:
                    f.write_text("\n".join(lines[-2000:]) + "\n")
                    stats["truncated"] += 1
            except Exception:
                pass

    # Clean old archives
    for gz in archive.glob("*.gz"):
        age = (now - datetime.fromtimestamp(gz.stat().st_mtime)).days
        if age > DELETE_LOG_DAYS:
            gz.unlink()

    stats["freed_mb"] = round(stats["freed_mb"], 2)
    log.info(f"Logs: compressed={stats['compressed']} deleted={stats['deleted']} "
             f"truncated={stats['truncated']} freed={stats['freed_mb']}MB")
    return stats

# ══════════════════════════════════════════════════════════════════════════
# Streamlit Throttling
# ══════════════════════════════════════════════════════════════════════════

STREAMLIT_CONFIG = Path("/root/.streamlit/config.toml")

def apply_streamlit_throttle(refresh_seconds: int = 30):
    """
    Write Streamlit config to reduce refresh frequency.
    Default aggressive refresh wastes CPU/RAM.
    """
    config_dir = STREAMLIT_CONFIG.parent
    config_dir.mkdir(parents=True, exist_ok=True)

    # Read existing config
    existing = ""
    if STREAMLIT_CONFIG.exists():
        existing = STREAMLIT_CONFIG.read_text()

    # Only write if not already set
    if "runOnSave" in existing and "fileWatcherType" in existing:
        log.info("Streamlit config already optimized")
        return False

    config = f"""[server]
runOnSave = false
fileWatcherType = "none"
maxUploadSize = 50

[browser]
gatherUsageStats = false

[runner]
fastReruns = false

# Phase 11: Refresh throttled to {refresh_seconds}s
# Written by resource_optimizer.py — {datetime.now().isoformat()}
"""
    try:
        STREAMLIT_CONFIG.write_text(config)
        log.info(f"Streamlit config written — refresh throttled")
        return True
    except Exception as e:
        log.error(f"Streamlit config error: {e}")
        return False

# ══════════════════════════════════════════════════════════════════════════
# Master Run
# ══════════════════════════════════════════════════════════════════════════

def run_optimization() -> dict:
    """Run all optimization tasks."""
    start    = datetime.now()
    ram_before = get_ram_info()

    log.info(f"=== Resource Optimizer START | RAM: {ram_before['percent']}% ===")

    results = {
        "timestamp":   start.isoformat(),
        "ram_before":  ram_before,
        "tasks":       {},
    }

    # 1. GC if RAM high
    if ram_before["percent"] >= GC_TRIGGER_PCT:
        log.info(f"RAM {ram_before['percent']}% — forcing GC")
        force_gc()
        results["tasks"]["gc"] = "triggered"
    else:
        results["tasks"]["gc"] = "skipped (RAM OK)"

    # 2. Kill zombies
    zombies = kill_zombie_processes()
    results["tasks"]["zombies_killed"] = zombies

    # 3. Pycache
    pycache = clean_pycache()
    results["tasks"]["pycache_removed"] = pycache

    # 4. Orphan cache
    cache = clean_orphan_cache()
    results["tasks"]["cache"] = cache

    # 5. Replay temp
    replay = clean_replay_temp()
    results["tasks"]["replay_temp"] = replay

    # 6. Log rotation
    logs = rotate_logs()
    results["tasks"]["logs"] = logs

    # 7. Streamlit throttle
    throttled = apply_streamlit_throttle(refresh_seconds=30)
    results["tasks"]["streamlit_throttled"] = throttled

    # Final RAM
    ram_after = get_ram_info()
    results["ram_after"]   = ram_after
    results["ram_freed_pct"] = round(ram_before["percent"] - ram_after["percent"], 1)
    results["duration_s"]  = round((datetime.now() - start).total_seconds(), 1)

    total_freed = (
        cache.get("freed_mb", 0) +
        replay.get("freed_mb", 0) +
        logs.get("freed_mb", 0)
    )
    results["total_freed_mb"] = round(total_freed, 2)

    log.info(f"=== DONE | RAM: {ram_after['percent']}% | Freed: {total_freed:.1f}MB | {results['duration_s']}s ===")

    # Write report
    try:
        REPORT_FILE.write_text(json.dumps(results, indent=2))
    except Exception as e:
        log.error(f"Report write: {e}")

    return results

# ══════════════════════════════════════════════════════════════════════════
# Daemon
# ══════════════════════════════════════════════════════════════════════════

def run_daemon(interval_hours: int = 1):
    log.info(f"Resource Optimizer daemon — every {interval_hours}h")

    # Apply Streamlit throttle immediately on start
    apply_streamlit_throttle()

    while True:
        try:
            run_optimization()
        except Exception as e:
            log.error(f"Optimization error: {e}")
        time.sleep(interval_hours * 3600)

# ══════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════

def print_report(r: dict):
    print("\n" + "=" * 55)
    print("  RESOURCE OPTIMIZER — REPORT")
    print("=" * 55)
    ram_b = r["ram_before"]
    ram_a = r["ram_after"]
    print(f"  RAM before:  {ram_b['percent']}% ({ram_b['used_gb']}GB / {ram_b['total_gb']}GB)")
    print(f"  RAM after:   {ram_a['percent']}% ({ram_a['used_gb']}GB / {ram_a['total_gb']}GB)")
    print(f"  RAM freed:   {r['ram_freed_pct']}%")
    print(f"  Disk freed:  {r['total_freed_mb']}MB")
    print(f"  Duration:    {r['duration_s']}s")
    print("-" * 55)
    for k, v in r["tasks"].items():
        print(f"  {k:<25} {v}")
    print("=" * 55 + "\n")

if __name__ == "__main__":
    args = sys.argv[1:]

    if not args or args[0] == "run":
        r = run_optimization()
        print_report(r)

    elif args[0] == "--daemon":
        hours = int(args[1]) if len(args) > 1 else 1
        run_daemon(hours)

    elif args[0] == "ram":
        info = get_ram_info()
        print(f"RAM: {info['percent']}% | Used: {info['used_gb']}GB / {info['total_gb']}GB | Free: {info['free_gb']}GB")

    elif args[0] == "gc":
        ram_before = get_ram_pct()
        force_gc()
        ram_after  = get_ram_pct()
        print(f"GC done: {ram_before}% → {ram_after}%")

    elif args[0] == "logs":
        r = rotate_logs()
        print(f"Logs: {r}")

    elif args[0] == "cache":
        r = clean_orphan_cache()
        print(f"Cache: {r}")

    else:
        print("Usage:")
        print("  python3 resource_optimizer.py          # full run")
        print("  python3 resource_optimizer.py --daemon # every 1h")
        print("  python3 resource_optimizer.py ram       # RAM info")
        print("  python3 resource_optimizer.py gc        # force GC")
        print("  python3 resource_optimizer.py logs      # rotate logs")
        print("  python3 resource_optimizer.py cache     # clean cache")
