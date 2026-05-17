#!/usr/bin/env python3
"""
system_health_score.py — Minervini AI System Health Score
Phase 11: Unified health scoring system.

Score components:
    - CPU usage
    - RAM usage
    - Stale data check
    - Daemon uptime
    - API latency
    - Execution latency
    - Queue freshness
    - Telegram health
    - Market data freshness

Output:
    90-100 → HEALTHY
    70-89  → DEGRADED
    <70    → PROTECTION MODE
"""

import os, sys, time, json, logging, psutil, requests
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger("system_health_score")

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT           = Path("/root")
LOGS           = Path("/root/logs")
HEALTH_OUT     = LOGS / "system_health_score.json"

# Critical JSON files to monitor freshness
CRITICAL_FILES = {
    "market_intelligence":  ROOT / "market_intelligence.json",
    "institutional_regime": ROOT / "institutional_regime.json",
    "trade_plans":          ROOT / "trade_plans.json",
    "service_guard":        LOGS / "service_guard_health.json",
    "portfolio_heat":       ROOT / "portfolio_heat.json",
}

# Max age in minutes before file is considered STALE
FRESHNESS_LIMITS = {
    "market_intelligence":  15,
    "institutional_regime": 15,
    "trade_plans":          60,
    "service_guard":        2,
    "portfolio_heat":       60,
}

# ── Thresholds ─────────────────────────────────────────────────────────────
CPU_WARN      = 80
CPU_CRIT      = 95
RAM_WARN      = 80
RAM_CRIT      = 92
API_WARN_MS   = 2000
API_CRIT_MS   = 5000

# ── Score Weights (total = 100) ────────────────────────────────────────────
WEIGHTS = {
    "cpu":              10,
    "ram":              15,
    "stale_data":       20,
    "daemon_uptime":    20,
    "api_latency":      10,
    "market_freshness": 15,
    "telegram_health":   5,
    "queue_freshness":   5,
}

# ══════════════════════════════════════════════════════════════════════════
# Component Scorers
# ══════════════════════════════════════════════════════════════════════════

def score_cpu() -> tuple[float, str]:
    """Score CPU usage. Full score if < 80%."""
    try:
        cpu = psutil.cpu_percent(interval=1)
        if cpu < CPU_WARN:
            return 1.0, f"CPU {cpu:.1f}% — OK"
        elif cpu < CPU_CRIT:
            return 0.5, f"CPU {cpu:.1f}% — WARNING"
        else:
            return 0.0, f"CPU {cpu:.1f}% — CRITICAL"
    except Exception as e:
        return 0.5, f"CPU check error: {e}"

def score_ram() -> tuple[float, str]:
    """Score RAM usage. Full score if < 80%."""
    try:
        ram = psutil.virtual_memory()
        pct = ram.percent
        used_gb = ram.used / 1024**3
        total_gb = ram.total / 1024**3
        if pct < RAM_WARN:
            return 1.0, f"RAM {pct:.1f}% ({used_gb:.1f}/{total_gb:.1f}GB) — OK"
        elif pct < RAM_CRIT:
            return 0.4, f"RAM {pct:.1f}% — WARNING"
        else:
            return 0.0, f"RAM {pct:.1f}% — CRITICAL"
    except Exception as e:
        return 0.5, f"RAM check error: {e}"

def score_stale_data() -> tuple[float, str]:
    """Check freshness of critical JSON files."""
    now    = datetime.now()
    stale  = []
    ok     = []
    missing = []

    for name, path in CRITICAL_FILES.items():
        max_age = FRESHNESS_LIMITS.get(name, 30)
        if not path.exists():
            missing.append(name)
            continue
        try:
            age_min = (now - datetime.fromtimestamp(path.stat().st_mtime)).total_seconds() / 60
            if age_min > max_age:
                stale.append(f"{name}({age_min:.0f}m)")
            else:
                ok.append(name)
        except Exception:
            missing.append(name)

    total = len(CRITICAL_FILES)
    issues = len(stale) + len(missing)

    if issues == 0:
        return 1.0, f"All {total} files fresh"
    elif issues == 1:
        detail = stale[0] if stale else f"{missing[0]} missing"
        return 0.6, f"STALE: {detail}"
    elif issues <= 2:
        return 0.3, f"STALE: {', '.join(stale)} | MISSING: {', '.join(missing)}"
    else:
        return 0.0, f"STALE: {len(stale)} | MISSING: {len(missing)} files"

def score_daemon_uptime() -> tuple[float, str]:
    """Check service_guard health for daemon status."""
    try:
        health_file = LOGS / "service_guard_health.json"
        if not health_file.exists():
            return 0.3, "service_guard_health.json not found"

        data = json.loads(health_file.read_text())
        services = data.get("services", {})

        if not services:
            return 0.3, "No service data"

        critical_down = []
        optional_down = []

        for name, info in services.items():
            status = info.get("status", "UNKNOWN")
            critical = info.get("critical", False)
            if status != "RUNNING":
                if critical:
                    critical_down.append(name)
                else:
                    optional_down.append(name)

        total    = len(services)
        n_down   = len(critical_down) + len(optional_down)
        running  = total - n_down

        if len(critical_down) == 0 and len(optional_down) == 0:
            return 1.0, f"All {total} services running"
        elif len(critical_down) == 0:
            return 0.7, f"{running}/{total} running | Optional down: {', '.join(optional_down)}"
        elif len(critical_down) == 1:
            return 0.3, f"CRITICAL DOWN: {critical_down[0]}"
        else:
            return 0.0, f"CRITICAL DOWN: {', '.join(critical_down)}"

    except Exception as e:
        return 0.3, f"Daemon check error: {e}"

def score_api_latency() -> tuple[float, str]:
    """Check Alpaca API latency."""
    try:
        api_key    = os.getenv("APCA_API_KEY_ID", "")
        api_secret = os.getenv("APCA_API_SECRET_KEY", "")
        base       = os.getenv("APCA_API_BASE_URL", "https://paper-api.alpaca.markets")

        if not api_key:
            return 0.5, "API key not set — skip latency check"

        start = time.time()
        r = requests.get(
            f"{base}/v2/clock",
            headers={
                "APCA-API-KEY-ID":     api_key,
                "APCA-API-SECRET-KEY": api_secret,
            },
            timeout=8,
        )
        latency_ms = (time.time() - start) * 1000

        if r.status_code != 200:
            return 0.0, f"API error: HTTP {r.status_code}"

        if latency_ms < API_WARN_MS:
            return 1.0, f"API latency {latency_ms:.0f}ms — OK"
        elif latency_ms < API_CRIT_MS:
            return 0.5, f"API latency {latency_ms:.0f}ms — SLOW"
        else:
            return 0.0, f"API latency {latency_ms:.0f}ms — CRITICAL"

    except requests.exceptions.Timeout:
        return 0.0, "API TIMEOUT — disconnected"
    except Exception as e:
        return 0.3, f"API check error: {e}"

def score_market_freshness() -> tuple[float, str]:
    """Check market_intelligence.json freshness and content."""
    try:
        path = ROOT / "market_intelligence.json"
        if not path.exists():
            return 0.0, "market_intelligence.json missing"

        data    = json.loads(path.read_text())
        updated = data.get("updated_at") or data.get("timestamp")

        if not updated:
            # Fall back to file mtime
            age_min = (datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)).total_seconds() / 60
        else:
            try:
                age_min = (datetime.now() - datetime.fromisoformat(updated)).total_seconds() / 60
            except Exception:
                age_min = 999

        if age_min <= 5:
            return 1.0, f"Market data fresh ({age_min:.1f}m ago)"
        elif age_min <= 15:
            return 0.7, f"Market data {age_min:.1f}m old — OK"
        elif age_min <= 30:
            return 0.3, f"Market data {age_min:.1f}m old — STALE"
        else:
            return 0.0, f"Market data {age_min:.1f}m old — CRITICAL STALE"

    except Exception as e:
        return 0.3, f"Market freshness error: {e}"

def score_telegram_health() -> tuple[float, str]:
    """Quick Telegram connectivity check."""
    try:
        token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN", "")
        if not token:
            return 0.5, "Telegram token not set"

        r = requests.get(
            f"https://api.telegram.org/bot{token}/getMe",
            timeout=5,
        )
        if r.status_code == 200:
            return 1.0, "Telegram connected"
        else:
            return 0.0, f"Telegram error: HTTP {r.status_code}"
    except requests.exceptions.Timeout:
        return 0.0, "Telegram TIMEOUT"
    except Exception as e:
        return 0.3, f"Telegram check error: {e}"

def score_queue_freshness() -> tuple[float, str]:
    """Check trade_plans.json freshness."""
    try:
        path = ROOT / "trade_plans.json"
        if not path.exists():
            return 0.5, "trade_plans.json not found (may be normal)"

        age_min = (datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)).total_seconds() / 60
        if age_min <= 30:
            return 1.0, f"Trade queue fresh ({age_min:.0f}m)"
        elif age_min <= 120:
            return 0.7, f"Trade queue {age_min:.0f}m old"
        else:
            return 0.3, f"Trade queue {age_min:.0f}m old — STALE"
    except Exception as e:
        return 0.5, f"Queue check error: {e}"

# ══════════════════════════════════════════════════════════════════════════
# Master Scorer
# ══════════════════════════════════════════════════════════════════════════

def compute_health_score() -> dict:
    """Run all component checks and compute final score."""
    now = datetime.now()

    scorers = {
        "cpu":              score_cpu,
        "ram":              score_ram,
        "stale_data":       score_stale_data,
        "daemon_uptime":    score_daemon_uptime,
        "api_latency":      score_api_latency,
        "market_freshness": score_market_freshness,
        "telegram_health":  score_telegram_health,
        "queue_freshness":  score_queue_freshness,
    }

    components = {}
    total_score = 0.0

    for name, fn in scorers.items():
        try:
            ratio, detail = fn()
        except Exception as e:
            ratio, detail = 0.5, f"Error: {e}"

        weight     = WEIGHTS.get(name, 10)
        points     = ratio * weight
        total_score += points

        components[name] = {
            "score":   round(points, 1),
            "max":     weight,
            "ratio":   round(ratio, 2),
            "detail":  detail,
            "status":  "OK" if ratio >= 0.7 else ("WARN" if ratio >= 0.3 else "CRITICAL"),
        }

    final_score = round(total_score, 1)

    if final_score >= 90:
        level  = "HEALTHY"
        emoji  = "✅"
    elif final_score >= 70:
        level  = "DEGRADED"
        emoji  = "⚠️"
    else:
        level  = "PROTECTION_MODE"
        emoji  = "🚨"

    result = {
        "updated_at":       now.isoformat(),
        "source_engine":    "system_health_score",
        "freshness_seconds": 0,
        "score":            final_score,
        "level":            level,
        "emoji":            emoji,
        "components":       components,
        "protection_mode":  final_score < 70,
    }

    # Write to file
    try:
        HEALTH_OUT.write_text(json.dumps(result, indent=2))
    except Exception as e:
        log.error(f"Write error: {e}")

    return result

# ── Protection Mode Action ─────────────────────────────────────────────────

def trigger_protection_mode(result: dict):
    """Notify and disable new entries if in protection mode."""
    try:
        from telegram_gate import send_alert
        components = result["components"]
        critical = [
            f"• {k}: {v['detail']}"
            for k, v in components.items()
            if v["status"] == "CRITICAL"
        ]
        send_alert(
            f"🚨 <b>PROTECTION MODE ACTIVATED</b>\n"
            f"Health Score: {result['score']}/100\n\n"
            f"Critical Issues:\n" + "\n".join(critical) +
            f"\n\n⚠️ New entries DISABLED\n"
            f"Exits only — preserve portfolio\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        )
    except Exception:
        pass

    # Write protection mode flag
    try:
        flag = {
            "protection_mode": True,
            "activated_at":    datetime.now().isoformat(),
            "score":           result["score"],
            "reason":          "Health score below 70",
        }
        (ROOT / "protection_mode.json").write_text(json.dumps(flag, indent=2))
    except Exception:
        pass

# ── Display ────────────────────────────────────────────────────────────────

def print_report(result: dict):
    score  = result["score"]
    level  = result["level"]
    emoji  = result["emoji"]

    print("\n" + "=" * 55)
    print(f"  SYSTEM HEALTH SCORE — {emoji} {level}")
    print(f"  Score: {score}/100")
    print("=" * 55)

    for name, c in result["components"].items():
        icon = "✅" if c["status"] == "OK" else ("⚠️" if c["status"] == "WARN" else "🔴")
        print(f"  {icon} {name:<20} {c['score']:>5.1f}/{c['max']}  {c['detail']}")

    print("=" * 55)
    if result["protection_mode"]:
        print("  🚨 PROTECTION MODE — new entries disabled")
    print()

# ── Daemon Mode ────────────────────────────────────────────────────────────

def run_daemon(interval_minutes: int = 5):
    """Run health check every N minutes."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [HealthScore] %(message)s",
        handlers=[
            logging.FileHandler("/root/logs/system_health_score.log"),
            logging.StreamHandler(),
        ]
    )
    log.info(f"Health Score daemon started — check every {interval_minutes}m")

    while True:
        try:
            result = compute_health_score()
            log.info(f"Score: {result['score']}/100 — {result['level']}")

            if result["protection_mode"]:
                trigger_protection_mode(result)

        except Exception as e:
            log.error(f"Health check error: {e}")

        time.sleep(interval_minutes * 60)

# ── CLI ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    args = sys.argv[1:]

    logging.basicConfig(level=logging.WARNING, format="%(message)s")

    if not args or args[0] == "check":
        result = compute_health_score()
        print_report(result)
        if result["protection_mode"]:
            trigger_protection_mode(result)

    elif args[0] == "--daemon":
        interval = int(args[1]) if len(args) > 1 else 5
        run_daemon(interval)

    elif args[0] == "json":
        result = compute_health_score()
        print(json.dumps(result, indent=2))

    else:
        print("Usage:")
        print("  python3 system_health_score.py          # one-time check")
        print("  python3 system_health_score.py --daemon # run every 5 min")
        print("  python3 system_health_score.py --daemon 10 # every 10 min")
        print("  python3 system_health_score.py json     # raw JSON output")
