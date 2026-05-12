"""
system_supervisor.py
SYSTEM SUPERVISOR & RELIABILITY LAYER
Minervini Bot — PAPER TRADING ONLY
Monitors all processes, restarts on crash, sends Telegram alerts.
"""

import os, sys, time, json, datetime, logging, subprocess, psutil, requests
sys.path.insert(0, "/root")
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SUPERVISOR] %(message)s",
    handlers=[
        logging.FileHandler("/root/logs/supervisor.log"),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger("supervisor")

DATA_DIR   = "/root/logs"
PAPER_ONLY = True

# ── Process definitions ───────────────────────────────────────────────────────
PROCESSES = {
    "paper_execution": {
        "cmd":     ["python3", "/root/paper_execution.py"],
        "log":     "/root/logs/paper.out",
        "match":   "paper_execution.py",
        "critical": True,
        "restart_delay": 5,
    },
    "smart_execution": {
        "cmd":     ["python3", "/root/smart_execution_engine.py"],
        "log":     "/root/logs/smart_engine.out",
        "match":   "smart_execution_engine.py",
        "critical": True,
        "restart_delay": 5,
    },
    "master_orchestrator": {
        "cmd":     ["python3", "/root/master_orchestrator.py"],
        "log":     "/root/logs/orchestrator.out",
        "match":   "master_orchestrator.py",
        "critical": False,
        "restart_delay": 10,
    },
    "market_intelligence": {
        "cmd":     ["python3", "/root/market_intelligence.py"],
        "log":     "/root/logs/market.out",
        "match":   "market_intelligence.py",
        "critical": True,
        "restart_delay": 5,
    },
    "streamlit": {
        "cmd":     ["streamlit", "run", "/root/dashboard_new.py",
                    "--server.port", "8501", "--server.address", "0.0.0.0"],
        "log":     "/root/logs/dashboard.log",
        "match":   "streamlit",
        "critical": False,
        "restart_delay": 15,
    },
}

restart_counts = {k: 0 for k in PROCESSES}
last_restart   = {k: 0.0 for k in PROCESSES}

# ── Telegram ──────────────────────────────────────────────────────────────────
def _tg(msg: str):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"},
            timeout=8
        )
    except Exception:
        pass

def _load(path, default={}):
    try:
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    except Exception:
        pass
    return default

def _save(path, data):
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception:
        pass

# ── Process management ────────────────────────────────────────────────────────
def is_running(match_str: str) -> bool:
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmd = " ".join(proc.info["cmdline"] or [])
            if match_str in cmd and "supervisor" not in cmd:
                return True
        except Exception:
            pass
    return False

def start_process(name: str, cfg: dict):
    now = time.time()
    if now - last_restart[name] < cfg["restart_delay"]:
        return
    last_restart[name] = now
    restart_counts[name] += 1

    log_path = cfg["log"]
    try:
        with open(log_path, "a") as logf:
            proc = subprocess.Popen(
                cfg["cmd"],
                stdout=logf, stderr=logf,
                start_new_session=True
            )
        log.info(f"Started {name} PID={proc.pid}")
        _tg(
            f"🔄 *PROCESS RESTARTED*\n"
            f"• `{name}`\n"
            f"• Restart #{restart_counts[name]}\n"
            f"• Time: {datetime.datetime.now().strftime('%H:%M:%S')}\n"
            f"⚠️ PAPER TRADING ONLY"
        )
    except Exception as e:
        log.error(f"Failed to start {name}: {e}")
        _tg(f"❌ *FAILED TO START* `{name}`\nError: `{e}`")

# ── System health snapshot ────────────────────────────────────────────────────
def build_health_snapshot() -> dict:
    cpu   = psutil.cpu_percent(interval=1)
    ram   = psutil.virtual_memory()
    disk  = psutil.disk_usage("/")
    procs = {k: is_running(v["match"]) for k, v in PROCESSES.items()}

    # API latency
    api_latency = 9999
    try:
        from config import ALPACA_API_KEY, ALPACA_SECRET_KEY
        t0 = time.time()
        requests.get(
            "https://paper-api.alpaca.markets/v2/account",
            headers={"APCA-API-KEY-ID": ALPACA_API_KEY,
                     "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY},
            timeout=5
        )
        api_latency = round((time.time() - t0) * 1000, 1)
    except Exception:
        pass

    # Last market update
    mi_path = f"{DATA_DIR}/market_intelligence.json"
    last_mi = "unknown"
    data_age_mins = 999
    if os.path.exists(mi_path):
        mtime = os.path.getmtime(mi_path)
        data_age_mins = round((time.time() - mtime) / 60, 1)
        last_mi = datetime.datetime.fromtimestamp(mtime).strftime("%H:%M:%S")

    snap = {
        "cpu_pct":         cpu,
        "ram_pct":         round(ram.percent, 1),
        "ram_used_mb":     round(ram.used / 1024**2, 0),
        "disk_pct":        round(disk.percent, 1),
        "processes":       procs,
        "all_running":     all(procs[k] for k,v in PROCESSES.items() if v["critical"]),
        "api_latency_ms":  api_latency,
        "last_market_update": last_mi,
        "data_age_mins":   data_age_mins,
        "restart_counts":  dict(restart_counts),
        "timestamp":       datetime.datetime.now().isoformat(),
        "paper_only":      True,
    }
    _save(f"{DATA_DIR}/health_status.json", snap)
    return snap

# ── Main supervisor loop ──────────────────────────────────────────────────────
def run_supervisor():
    log.info("=" * 60)
    log.info("  SYSTEM SUPERVISOR — PAPER TRADING ONLY")
    log.info("=" * 60)
    _tg("🟢 *SUPERVISOR STARTED*\nMonitoring all processes.\n⚠️ PAPER TRADING ONLY")

    cycle = 0
    while True:
        try:
            # Check and restart processes
            for name, cfg in PROCESSES.items():
                if not is_running(cfg["match"]):
                    log.warning(f"Process DOWN: {name}")
                    if cfg["critical"] or restart_counts[name] < 3:
                        start_process(name, cfg)

            # Build health snapshot every 5 cycles
            if cycle % 5 == 0:
                snap = build_health_snapshot()
                log.info(
                    f"Health: CPU={snap['cpu_pct']}% RAM={snap['ram_pct']}% "
                    f"API={snap['api_latency_ms']}ms "
                    f"DataAge={snap['data_age_mins']}m"
                )

            cycle += 1
            time.sleep(30)

        except KeyboardInterrupt:
            log.info("Supervisor stopped")
            break
        except Exception as e:
            log.error(f"Supervisor error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    run_supervisor()
