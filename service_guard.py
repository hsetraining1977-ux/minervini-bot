#!/usr/bin/env python3
"""
service_guard.py — Minervini AI Service Guard
Phase 11: Monitors long-running daemon processes only.

NOTE: market_intelligence.py and smart_execution_engine.py
run as one-shot scripts (not daemons) — they are NOT monitored here.
Only true long-running processes are monitored.

Monitors (long-running daemons only):
    - institutional_regime_classifier
    - adaptive_learning
    - ai_layer  (run via run_ai_layer.sh)
    - regime_sync
    - telegram_gate / smart_telegram_reporter

Features:
    - PID lockfiles
    - Restart cooldown (60s)
    - Protection mode after 5 restarts/hour
    - Health JSON for system_health_score.py
"""

import os, sys, time, logging, subprocess, json, psutil
from datetime import datetime, timedelta
from pathlib import Path

# ── Logging ────────────────────────────────────────────────────────────────
os.makedirs("/root/logs", exist_ok=True)
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

# ── Service Definitions (long-running daemons only) ────────────────────────
# cmd: الأمر الفعلي للتشغيل
# match: النص اللي نبحث عنه في process list
# log: ملف اللوج
# critical: هل النظام يدخل protection mode لو وقع؟
SERVICES = {
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
    "ai_layer": {
        "cmd":      ["bash", "/root/run_ai_layer.sh"],
        "match":    "run_ai_layer.sh",
        "log":      "/root/ai.out",
        "critical": True,
    },
    "regime_sync": {
        "cmd":      ["python3", "/root/regime_sync.py"],
        "match":    "regime_sync.py",
        "log":      "/root/logs/regime_sync.out",
        "critical": False,
    },
    "smart_telegram_reporter": {
        "cmd":      ["python3", "/root/smart_telegram_reporter.py"],
        "match":    "smart_telegram_reporter.py",
        "log":      "/root/logs/telegram_reporter.out",
        "critical": False,
    },
}

# ── Config ─────────────────────────────────────────────────────────────────
RESTART_COOLDOWN  = 60
MAX_RESTARTS_HOUR = 5
CHECK_INTERVAL    = 30

# ── State ──────────────────────────────────────────────────────────────────
_state = {
    name: {
        "restarts":      0,
        "last_restart":  None,
        "last_seen":     None,
        "status":        "UNKNOWN",
        "pid":           None,
        "restart_times": [],
        "skip_restart":  False,   # True if restart loop detected
    }
    for name in SERVICES
}

# ── PID Helpers ────────────────────────────────────────────────────────────

def pid_file(name):
    return PID_DIR / f"{name}.pid"

def write_pid(name, pid):
    pid_file(name).write_text(str(pid))

def read_pid(name):
    p = pid_file(name)
    if p.exists():
        try:
            return int(p.read_text().strip())
        except Exception:
            pass
    return None

def clear_pid(name):
    pid_file(name).unlink(missing_ok=True)

def pid_alive(pid):
    try:
        proc = psutil.Process(pid)
        return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False

# ── Process Detection ──────────────────────────────────────────────────────

def find_process(match):
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmdline = " ".join(proc.info["cmdline"] or [])
            if match in cmdline and "service_guard" not in cmdline:
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return None

def is_running(name):
    stored = read_pid(name)
    if stored and pid_alive(stored):
        _state[name]["pid"] = stored
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

def in_cooldown(name):
    last = _state[name]["last_restart"]
    if last is None:
        return False
    return (datetime.now() - last).total_seconds() < RESTART_COOLDOWN

def restart_loop_detected(name):
    now    = datetime.now()
    cutoff = now - timedelta(hours=1)
    recent = [t for t in _state[name]["restart_times"] if t > cutoff]
    _state[name]["restart_times"] = recent
    return len(recent) >= MAX_RESTARTS_HOUR

def start_service(name):
    if _state[name]["skip_restart"]:
        return False
    if in_cooldown(name):
        log.info(f"[{name}] Cooldown — skip")
        return False
    if restart_loop_detected(name):
        log.warning(f"[{name}] Restart loop — skip & notify")
        _state[name]["skip_restart"] = True
        _notify_protection_mode(name)
        return False

    svc = SERVICES[name]
    script = svc["cmd"][1] if len(svc["cmd"]) > 1 else ""
    if script and not Path(script).exists():
        log.error(f"[{name}] File not found: {script} — marking skip")
        _state[name]["skip_restart"] = True
        return False

    log.info(f"[{name}] Starting...")
    try:
        os.makedirs(os.path.dirname(svc["log"]), exist_ok=True)
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
            _state[name].update({
                "pid":          proc.pid,
                "restarts":     _state[name]["restarts"] + 1,
                "last_restart": datetime.now(),
                "status":       "RUNNING",
            })
            _state[name]["restart_times"].append(datetime.now())
            log.info(f"[{name}] Started PID {proc.pid}")
            _notify_restart(name, proc.pid)
            return True
        else:
            log.error(f"[{name}] Died immediately — marking skip to prevent loop")
            clear_pid(name)
            _state[name]["skip_restart"] = True   # لا تعيد المحاولة تلقائياً
            return False
    except Exception as e:
        log.error(f"[{name}] Error: {e}")
        clear_pid(name)
        return False

# ── Health File ────────────────────────────────────────────────────────────

def update_health():
    snap = {
        "updated_at":       datetime.now().isoformat(),
        "source_engine":    "service_guard",
        "freshness_seconds": 0,
        "services": {
            name: {
                "status":       _state[name]["status"],
                "pid":          _state[name]["pid"],
                "restarts":     _state[name]["restarts"],
                "critical":     SERVICES[name]["critical"],
                "skip_restart": _state[name]["skip_restart"],
                "last_restart": _state[name]["last_restart"].isoformat()
                                if _state[name]["last_restart"] else None,
            }
            for name in SERVICES
        }
    }
    try:
        HEALTH_FILE.write_text(json.dumps(snap, indent=2))
    except Exception as e:
        log.error(f"Health write: {e}")
    return snap

# ── Notifications ──────────────────────────────────────────────────────────

def _notify_restart(name, pid):
    try:
        from telegram_gate import send_alert
        send_alert(
            f"🔄 <b>SERVICE RESTARTED</b>\n"
            f"<code>{name}</code> — PID {pid}\n"
            f"Total restarts: {_state[name]['restarts']}\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        )
    except Exception:
        pass

def _notify_protection_mode(name):
    try:
        from telegram_gate import send_alert
        send_alert(
            f"🚨 <b>RESTART LOOP DETECTED</b>\n"
            f"<code>{name}</code> failed {MAX_RESTARTS_HOUR}x in 1h\n"
            f"Auto-restart DISABLED for this service\n"
            f"⚠️ Manual check required\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        )
    except Exception:
        pass

# ── Main Loop ──────────────────────────────────────────────────────────────

def check_all():
    for name in SERVICES:
        try:
            if is_running(name):
                _state[name]["status"]    = "RUNNING"
                _state[name]["last_seen"] = datetime.now()
                _state[name]["skip_restart"] = False  # reset if it recovered
            else:
                _state[name]["status"] = "DOWN"
                if not _state[name]["skip_restart"]:
                    log.warning(f"[{name}] DOWN — restarting")
                    start_service(name)
                else:
                    log.debug(f"[{name}] DOWN but skip_restart=True")
        except Exception as e:
            log.error(f"[{name}] check error: {e}")
    update_health()

def run_guard():
    log.info("=" * 55)
    log.info("  SERVICE GUARD — Phase 11")
    log.info(f"  Monitoring {len(SERVICES)} long-running daemons")
    log.info(f"  Check: {CHECK_INTERVAL}s | Cooldown: {RESTART_COOLDOWN}s")
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
    print("\n" + "=" * 65)
    print("  SERVICE GUARD — STATUS")
    print("=" * 65)
    for name in SERVICES:
        running  = is_running(name)
        icon     = "🟢" if running else "🔴"
        pid      = str(_state[name]["pid"]) if _state[name]["pid"] else "—"
        tag      = "CRITICAL" if SERVICES[name]["critical"] else "optional"
        print(f"  {icon} {name:<42} PID:{pid:<8} [{tag}]")
    print("=" * 65 + "\n")

def cmd_restart(name):
    if name not in SERVICES:
        print(f"Unknown: {name} | Available: {', '.join(SERVICES)}")
        return
    proc = find_process(SERVICES[name]["match"])
    if proc:
        try:
            proc.terminate(); time.sleep(2)
            if proc.is_running(): proc.kill()
        except Exception:
            pass
    clear_pid(name)
    _state[name]["last_restart"]  = None
    _state[name]["skip_restart"]  = False
    success = start_service(name)
    print(f"[{name}] {'✅ Started' if success else '❌ Failed'}")

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] == "--daemon":
        run_guard()
    elif args[0] == "status":
        for name in SERVICES: is_running(name)
        cmd_status()
    elif args[0] == "restart" and len(args) > 1:
        cmd_restart(args[1])
    elif args[0] == "restart-all":
        for name in SERVICES: cmd_restart(name)
    else:
        print("Usage:")
        print("  python3 service_guard.py            # daemon")
        print("  python3 service_guard.py status      # status")
        print("  python3 service_guard.py restart <name>")
        print(f"\nMonitored: {', '.join(SERVICES)}")
