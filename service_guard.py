#!/usr/bin/env python3
"""
service_guard.py — Minervini AI Service Guard
Phase 11: Unified service supervisor with PID lockfiles.

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
    - Protection Mode trigger after 5 restarts/hour
"""

import os, sys, time, logging, subprocess, json, psutil
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
PID_DIR     = Path("/tmp/minervini_pids")
HEALTH_FILE = Path("/root/logs/service_guard_health.json")
PID_DIR.mkdir(exist_ok=True)

# ── Service Definitions ────────────────────────────────────────────────────
SERVICES = {
    "market_intelligence": {
        "cmd":      ["python3", "/root/market_intelligence.py"],
        "match":    "market_intelligence.py",
        "log":      "/root/logs/market_intelligence.out",
        "critical": True,
    },
    "institutional_regime_classifier": {
        "cmd":      ["python3", "/root/institutional_regime_classifier.py"],
        "match":    "institutional_regime_classifier.py",
        "log":      "/root/logs/institutional.out",
        "critical": True,
    },
    "adaptive_learning": {
        "cmd":      ["python3", "/root/adaptive_learning.py"],
        "match":    "adaptive_learning.py",
        "log":      "/root/logs/adaptive_learning.out",
        "critical": False,
    },
    "smart_execution_engine": {
        "cmd":      ["python3", "/root/smart_execution_engine.py"],
        "match":    "smart_execution_engine.py",
        "log":      "/root/logs/smart_execution.out",
        "critical": True,
    },
    "paper_execution": {
        "cmd":      ["python3", "/root/paper_execution.py"],
        "match":    "paper_execution.py",
        "log":      "/root/logs/paper.out",
        "critical": True,
    },
}

# ── Config ─────────────────────────────────────────────────────────────────
RESTART_COOLDOWN  = 60    # seconds between restarts
MAX_RESTARTS_HOUR = 5     # protection mode trigger
CHECK_INTERVAL    = 30    # seconds between checks

# ── State ──────────────────────────────────────────────────────────────────
_state = {
    name: {
        "restarts":      0,
        "last_restart":  None,
        "last_seen":     None,
        "status":        "UNKNOWN",
        "pid":           None,
        "restart_times": [],
    }
    for name in SERVICES
}

# ── PID Lockfile ───────────────────────────────────────────────────────────

def pid_file(name: str) -> Path:
    return PID_DIR / f"{name}.pid"

def write_pid(name: str, pid: int):
    pid_file(name).write_text(str(pid))

def read_pid(name: str):
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

def find_process(match: str):
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmdline = " ".join(proc.info["cmdline"] or [])
            if match in cmdline and "service_guard" not in cmdline:
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return None

def is_running(name: str) -> bool:
    stored_pid = read_pid(name)
    if stored_pid and pid_alive(stored_pid):
        _state[name]["pid"] = stored_pid
        return True
    proc = find_process(SERVICES[name]["match"])
    if proc:
        write_pid(name, proc.pid)
        _state[name]["pid"] = proc.pid
        return True
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
    now    = datetime.now()
    cutoff = now - timedelta(hours=1)
    recent = [t for t in _state[name]["restart_times"] if t > cutoff]
    _state[name]["restart_times"] = recent
    return len(recent) >= MAX_RESTARTS_HOUR

def validate_before_restart(name: str) -> bool:
    script = SERVICES[name]["cmd"][1]
    if not Path(script).exists():
        log.error(f"[{name}] Script not found: {script}")
        return False
    return True

def start_service(name: str) -> bool:
    if in_cooldown(name):
        log.info(f"[{name}] Cooldown active — skip")
        return False
    if restart_loop_detected(name):
        log.warning(f"[{name}] Restart loop — Protection Mode")
        _notify_protection_mode(name)
        return False
    if not validate_before_restart(name):
        return False

    svc = SERVICES[name]
    log.info(f"[{name}] Starting...")
    try:
        with open(svc["log"], "a") as out:
            proc = subprocess.Popen(
                svc["cmd"],
                stdout=out,
                stderr=out,
                start_new_session=True,
            )
        time.sleep(3)
        if proc.poll() is None:
            write_pid(name, proc.pid)
            _state[name]["pid"]           = proc.pid
            _state[name]["restarts"]     += 1
            _state[name]["last_restart"]  = datetime.now()
            _state[name]["restart_times"].append(datetime.now())
            _state[name]["status"]        = "RUNNING"
            log.info(f"[{name}] Started — PID {proc.pid}")
            _notify_restart(name, proc.pid)
            return True
        else:
            log.error(f"[{name}] Exited immediately — check: {svc['log']}")
            clear_pid(name)
            return False
    except Exception as e:
        log.error(f"[{name}] Start error: {e}")
        clear_pid(name)
        return False

# ── Health Snapshot ────────────────────────────────────────────────────────

def update_health():
    snapshot = {
        "updated_at":       datetime.now().isoformat(),
        "source_engine":    "service_guard",
        "freshness_seconds": 0,
        "services": {}
    }
    for name in SERVICES:
        s = _state[name]
        snapshot["services"][name] = {
            "status":       s["status"],
            "pid":          s["pid"],
            "restarts":     s["restarts"],
            "last_restart": s["last_restart"].isoformat() if s["last_restart"] else None,
            "last_seen":    s["last_seen"].isoformat() if s["last_seen"] else None,
            "critical":     SERVICES[name]["critical"],
        }
    try:
        HEALTH_FILE.write_text(json.dumps(snapshot, indent=2))
    except Exception as e:
        log.error(f"Health write error: {e}")
    return snapshot

# ── Telegram ───────────────────────────────────────────────────────────────

def _notify_restart(name: str, pid: int):
    try:
        from telegram_gate import send_alert
        send_alert(
            f"🔄 <b>SERVICE RESTARTED</b>\n"
            f"Service: <code>{name}</code>\n"
            f"PID: {pid}\n"
            f"Total restarts: {_state[name]['restarts']}\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        )
    except Exception:
        pass

def _notify_protection_mode(name: str):
    try:
        from telegram_gate import send_alert
        send_alert(
            f"🚨 <b>RESTART LOOP — PROTECTION MODE</b>\n"
            f"Service: <code>{name}</code>\n"
            f"Restarts (1h): {len(_state[name]['restart_times'])}\n"
            f"⚠️ Manual intervention required\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        )
    except Exception:
        pass

# ── Main Loop ──────────────────────────────────────────────────────────────

def check_all():
    for name in SERVICES:
        try:
            running = is_running(name)
            if running:
                _state[name]["status"]    = "RUNNING"
                _state[name]["last_seen"] = datetime.now()
            else:
                _state[name]["status"] = "DOWN"
                log.warning(f"[{name}] DOWN — restarting")
                start_service(name)
        except Exception as e:
            log.error(f"[{name}] Check error: {e}")
    update_health()

def run_guard():
    log.info("=" * 55)
    log.info("  SERVICE GUARD — Phase 11")
    log.info(f"  Monitoring {len(SERVICES)} services")
    log.info(f"  Check: {CHECK_INTERVAL}s | Cooldown: {RESTART_COOLDOWN}s | Max restarts/h: {MAX_RESTARTS_HOUR}")
    log.info("=" * 55)
    tick = 0
    while True:
        try:
            check_all()
            tick += 1
            if tick % 20 == 0:
                running = sum(1 for n in SERVICES if _state[n]["status"] == "RUNNING")
                log.info(f"Heartbeat: {running}/{len(SERVICES)} running")
            time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            log.info("Stopped")
            break
        except Exception as e:
            log.error(f"Loop error: {e}")
            time.sleep(CHECK_INTERVAL)

# ── CLI ────────────────────────────────────────────────────────────────────

def cmd_status():
    print("\n" + "=" * 62)
    print("  SERVICE GUARD — STATUS")
    print("=" * 62)
    for name in SERVICES:
        running  = is_running(name)
        icon     = "🟢" if running else "🔴"
        pid      = str(_state[name]["pid"]) if _state[name]["pid"] else "—"
        critical = "CRITICAL" if SERVICES[name]["critical"] else "optional"
        print(f"  {icon} {name:<42} PID:{pid:<8} [{critical}]")
    print("=" * 62 + "\n")

def cmd_restart(name: str):
    if name not in SERVICES:
        print(f"Unknown: {name}")
        print(f"Available: {', '.join(SERVICES)}")
        return
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
    _state[name]["last_restart"] = None  # reset cooldown for manual restart
    success = start_service(name)
    print(f"[{name}] {'✅ Started' if success else '❌ Failed — check log'}")

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] == "--daemon":
        run_guard()
    elif args[0] == "status":
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
        print("  python3 service_guard.py             # daemon")
        print("  python3 service_guard.py status       # show status")
        print("  python3 service_guard.py restart <name>")
        print("  python3 service_guard.py restart-all")
        print(f"\nServices: {', '.join(SERVICES)}")
