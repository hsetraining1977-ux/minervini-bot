#!/usr/bin/env python3
"""
service_guard.py — Minervini AI Service Guard
Phase 11: Unified service supervisor with PID lockfiles.

Replaces / wraps: auto_restart.py + system_supervisor.py
Monitors:
    - market_intelligence
    - institutional_regime_classifier
    - adaptive_learning
    - smart_execution_engine
    - paper_execution

Features:
    - One-instance-per-service enforcement (PID lockfiles)
    - Graceful restart with validation
    - Restart cooldown (prevents restart loops)
    - Health timestamps
    - Process heartbeat
    - Protection Mode integration
"""

import os, sys, time, signal, logging, subprocess, json, psutil
from datetime import datetime, timedelta
from pathlib import Path

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ServiceGuard] %(message)s",
    handlers=[
        logging.FileHandler("/root/logs/service_guard.log"),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger("service_guard")

# ── Paths ──────────────────────────────────────────────────────────────────
PID_DIR        = Path("/tmp/minervini_pids")
HEALTH_FILE    = Path("/root/logs/service_guard_health.json")
PID_DIR.mkdir(exist_ok=True)

# ── Service Definitions ────────────────────────────────────────────────────
SERVICES = {
    "market_intelligence": {
        "cmd":   ["python3", "/root/market_intelligence.py", "--daemon"],
        "match": "market_intelligence.py",
        "log":   "/root/logs/market_intelligence.out",
        "critical": True,
    },
    "institutional_regime_classifier": {
        "cmd":   ["python3", "/root/institutional_regime_classifier.py", "--daemon"],
        "match": "institutional_regime_classifier.py",
        "log":   "/root/logs/institutional.out",
        "critical": True,
    },
    "adaptive_learning": {
        "cmd":   ["python3", "/root/adaptive_learning.py", "--daemon"],
        "match": "adaptive_learning.py",
        "log":   "/root/logs/adaptive_learning.out",
        "critical": False,
    },
    "smart_execution_engine": {
        "cmd":   ["python3", "/root/smart_execution_engine.py", "--daemon"],
        "match": "smart_execution_engine.py",
        "log":   "/root/logs/smart_execution.out",
        "critical": True,
    },
    "paper_execution": {
        "cmd":   ["python3", "/root/paper_execution.py"],
        "match": "paper_execution.py",
        "log":   "/root/logs/paper.out",
        "critical": True,
    },
}

# ── Cooldown & State ───────────────────────────────────────────────────────
RESTART_COOLDOWN   = 60    # seconds between restarts per service
MAX_RESTARTS_HOUR  = 5     # protection mode trigger
CHECK_INTERVAL     = 30    # seconds between health checks

_state: dict = {
    name: {
        "restarts":      0,
        "last_restart":  None,
        "last_seen":     None,
        "status":        "UNKNOWN",
        "pid":           None,
        "restart_times": [],   # timestamps of last restarts
    }
    for name in SERVICES
}

# ── PID Lockfile Helpers ───────────────────────────────────────────────────

def pid_file(name: str) -> Path:
    return PID_DIR / f"{name}.pid"

def write_pid(name: str, pid: int):
    pid_file(name).write_text(str(pid))

def read_pid(name: str) -> int | None:
    p = pid_file(name)
    if p.exists():
        try:
            return int(p.read_text().strip())
        except Exception:
            pass
    return None

def clear_pid(name: str):
    pid_file(name).unlink(missing_ok=True)

def pid_alive(pid: int) -> bool:
    try:
        proc = psutil.Process(pid)
        return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False

# ── Process Detection ──────────────────────────────────────────────────────

def find_process(match: str) -> psutil.Process | None:
    """Find running process by script name."""
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmdline = " ".join(proc.info["cmdline"] or [])
            if match in cmdline:
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return None

def is_running(name: str) -> bool:
    """Check if service is running — uses PID file + process scan."""
    svc = SERVICES[name]

    # Check PID file first
    stored_pid = read_pid(name)
    if stored_pid and pid_alive(stored_pid):
        _state[name]["pid"] = stored_pid
        return True

    # Fallback: scan processes
    proc = find_process(svc["match"])
    if proc:
        write_pid(name, proc.pid)
        _state[name]["pid"] = proc.pid
        return True

    # Stale PID file — clean up
    clear_pid(name)
    _state[name]["pid"] = None
    return False

# ── Restart Logic ──────────────────────────────────────────────────────────

def in_cooldown(name: str) -> bool:
    last = _state[name]["last_restart"]
    if last is None:
        return False
    return (datetime.now() - last).total_seconds() < RESTART_COOLDOWN

def restart_loop_detected(name: str) -> bool:
    """Detect if service is restarting too frequently."""
    now = datetime.now()
    cutoff = now - timedelta(hours=1)
    recent = [t for t in _state[name]["restart_times"] if t > cutoff]
    _state[name]["restart_times"] = recent
    return len(recent) >= MAX_RESTARTS_HOUR

def validate_before_restart(name: str) -> bool:
    """Basic validation before restarting a service."""
    script = SERVICES[name]["cmd"][1] if len(SERVICES[name]["cmd"]) > 1 else ""
    if script and not Path(script).exists():
        log.error(f"[{name}] Script not found: {script} — cannot restart")
        return False
    return True

def start_service(name: str) -> bool:
    """Start a service with PID lockfile."""
    if in_cooldown(name):
        log.info(f"[{name}] In cooldown — skipping restart")
        return False

    if restart_loop_detected(name):
        log.warning(f"[{name}] Restart loop detected — entering protection mode")
        _notify_protection_mode(name)
        return False

    if not validate_before_restart(name):
        return False

    svc = SERVICES[name]
    log.info(f"[{name}] Starting...")

    try:
        log_path = svc.get("log", f"/root/logs/{name}.out")
        with open(log_path, "a") as log_out:
            proc = subprocess.Popen(
                svc["cmd"],
                stdout=log_out,
                stderr=log_out,
                start_new_session=True,
            )

        time.sleep(2)  # Brief wait to confirm startup

        if proc.poll() is None:  # Still running
            write_pid(name, proc.pid)
            _state[name]["pid"]          = proc.pid
            _state[name]["restarts"]    += 1
            _state[name]["last_restart"] = datetime.now()
            _state[name]["restart_times"].append(datetime.now())
            _state[name]["status"]       = "RUNNING"
            log.info(f"[{name}] Started — PID {proc.pid}")
            _notify_restart(name, proc.pid)
            return True
        else:
            log.error(f"[{name}] Failed to start (exited immediately)")
            clear_pid(name)
            return False

    except Exception as e:
        log.error(f"[{name}] Start error: {e}")
        clear_pid(name)
        return False

# ── Health Snapshot ────────────────────────────────────────────────────────

def update_health():
    """Write health snapshot to JSON."""
    snapshot = {
        "timestamp":  datetime.now().isoformat(),
        "services":   {}
    }
    for name in SERVICES:
        s = _state[name]
        snapshot["services"][name] = {
            "status":       s["status"],
            "pid":          s["pid"],
            "restarts":     s["restarts"],
            "last_restart": s["last_restart"].isoformat() if s["last_restart"] else None,
            "last_seen":    s["last_seen"].isoformat() if s["last_seen"] else None,
        }

    try:
        HEALTH_FILE.write_text(json.dumps(snapshot, indent=2))
    except Exception as e:
        log.error(f"Health write failed: {e}")

    return snapshot

def get_health() -> dict:
    """Read health snapshot."""
    try:
        return json.loads(HEALTH_FILE.read_text())
    except Exception:
        return {}

# ── Telegram Notifications ─────────────────────────────────────────────────

def _notify_restart(name: str, pid: int):
    try:
        from telegram_gate import send_alert
        send_alert(
            f"🔄 <b>SERVICE RESTARTED</b>\n"
            f"Service: {name}\n"
            f"PID: {pid}\n"
            f"Restarts today: {_state[name]['restarts']}\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        )
    except Exception:
        pass

def _notify_protection_mode(name: str):
    try:
        from telegram_gate import send_alert
        send_alert(
            f"🚨 <b>RESTART LOOP — PROTECTION MODE</b>\n"
            f"Service: {name}\n"
            f"Restarts (1h): {len(_state[name]['restart_times'])}\n"
            f"Action: Manual intervention required\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        )
    except Exception:
        pass

# ── Main Guard Loop ────────────────────────────────────────────────────────

def check_all():
    """Check all services and restart if needed."""
    for name in SERVICES:
        try:
            running = is_running(name)
            now = datetime.now()

            if running:
                _state[name]["status"]    = "RUNNING"
                _state[name]["last_seen"] = now
            else:
                _state[name]["status"] = "DOWN"
                log.warning(f"[{name}] DOWN — attempting restart")
                start_service(name)

        except Exception as e:
            log.error(f"[{name}] Check error: {e}")

    update_health()

def heartbeat():
    """Log heartbeat every 10 minutes."""
    running = sum(1 for n in SERVICES if _state[n]["status"] == "RUNNING")
    log.info(f"Heartbeat: {running}/{len(SERVICES)} services running")

def run_guard():
    """Main guard loop."""
    log.info("=" * 50)
    log.info("  SERVICE GUARD — Phase 11")
    log.info(f"  Monitoring {len(SERVICES)} services")
    log.info(f"  Cooldown: {RESTART_COOLDOWN}s | Max restarts/h: {MAX_RESTARTS_HOUR}")
    log.info("=" * 50)

    heartbeat_counter = 0

    while True:
        try:
            check_all()

            heartbeat_counter += 1
            if heartbeat_counter >= 20:  # Every ~10 minutes
                heartbeat()
                heartbeat_counter = 0

            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            log.info("Service Guard stopped by user")
            break
        except Exception as e:
            log.error(f"Guard loop error: {e}")
            time.sleep(CHECK_INTERVAL)

# ── CLI ────────────────────────────────────────────────────────────────────

def cmd_status():
    """Print current status of all services."""
    print("\n" + "=" * 55)
    print("  SERVICE GUARD — STATUS")
    print("=" * 55)
    for name in SERVICES:
        running = is_running(name)
        status  = "🟢 RUNNING" if running else "🔴 DOWN"
        pid     = _state[name]["pid"] or "—"
        restarts = _state[name]["restarts"]
        print(f"  {name:<38} {status}  PID:{pid}  Restarts:{restarts}")
    print("=" * 55 + "\n")

def cmd_restart(name: str):
    """Force restart a specific service."""
    if name not in SERVICES:
        print(f"Unknown service: {name}")
        print(f"Available: {', '.join(SERVICES.keys())}")
        return
    # Kill existing
    proc = find_process(SERVICES[name]["match"])
    if proc:
        try:
            proc.terminate()
            time.sleep(2)
            if proc.is_running():
                proc.kill()
        except Exception:
            pass
    clear_pid(name)
    _state[name]["last_restart"] = None  # Reset cooldown for manual restart
    start_service(name)

if __name__ == "__main__":
    import sys
    args = sys.argv[1:]

    if not args or args[0] == "--daemon":
        run_guard()
    elif args[0] == "status":
        # Quick status check without daemon
        for name in SERVICES:
            is_running(name)
        cmd_status()
    elif args[0] == "restart" and len(args) > 1:
        cmd_restart(args[1])
    elif args[0] == "restart-all":
        for name in SERVICES:
            cmd_restart(name)
    else:
        print("Usage:")
        print("  python3 service_guard.py            # run as daemon")
        print("  python3 service_guard.py status      # show status")
        print("  python3 service_guard.py restart <service>")
        print("  python3 service_guard.py restart-all")
