#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║   MINERVINI AI — HISTORICAL LEARNING DAEMON                      ║
║   Primary: Alpaca Historical API (years of minute data)          ║
║   Fallback: Yahoo Finance (daily bars)                           ║
║   LOW CPU PRIORITY — ASYNC — NON-BLOCKING                        ║
╚══════════════════════════════════════════════════════════════════╝

Data Sources:
  Alpaca Historical API → 1m/5m bars for years of history
  Yahoo Finance         → Daily bars fallback (any date)

Phases:
  Phase 0: Last 6 months  @ 5m  (Alpaca) → 50-500 trades
  Phase 1: Last 12 months @ 5m  (Alpaca) → 500-2000 trades
  Phase 2: Last 2 years   @ 1d  (Yahoo)  → 2000-5000 trades
  Phase 3: Last 5 years   @ 1d  (Yahoo)  → 5000+ trades
"""

import sys
import os
sys.path.insert(0, "/root")

# ── Low CPU Priority ──────────────────────────────────────────────
try:
    os.nice(10)
except Exception:
    pass

import json
import time
import argparse
from datetime import datetime, timedelta

import historical_replay_engine as hrengine
import adaptive_memory_builder  as ambuilder
import setup_replay_library     as slib
import regime_replay_engine     as rengine

# ── Config ────────────────────────────────────────────────────────
DAEMON_LOG  = "/root/adaptive/daemon.log"
STATE_PATH  = "/root/adaptive/memory/daemon_state.json"
MEMORY_DIR  = "/root/adaptive/memory"
os.makedirs("/root/adaptive", exist_ok=True)
os.makedirs(MEMORY_DIR, exist_ok=True)

# ── Phase Configuration ───────────────────────────────────────────
# Alpaca supports years of 1m/5m data — no 60-day limit!
# Yahoo Finance daily works for any historical date.

PHASE_CONFIG = {
    "PHASE_0_INITIALIZING": {
        "days_back":   180,      # 6 months
        "interval":    "5m",     # Alpaca minute data
        "symbols":     hrengine.WATCHLISTS["tech_leaders"],
        "chunk_days":  14,       # Process 2 weeks at a time
        "description": "Bootstrap — 6 months @ 5min via Alpaca",
        "target_trades": 500,
    },
    "PHASE_1_BOOTSTRAP": {
        "days_back":   365,      # 12 months
        "interval":    "5m",     # Alpaca minute data
        "symbols":     (hrengine.WATCHLISTS["tech_leaders"] +
                        hrengine.WATCHLISTS["growth_leaders"]),
        "chunk_days":  14,
        "description": "Advanced — 12 months @ 5min via Alpaca",
        "target_trades": 2000,
    },
    "PHASE_2_ADVANCED": {
        "days_back":   730,      # 2 years
        "interval":    "1d",     # Yahoo daily (any date)
        "symbols":     (hrengine.WATCHLISTS["tech_leaders"] +
                        hrengine.WATCHLISTS["growth_leaders"] +
                        hrengine.WATCHLISTS["sector_etfs"]),
        "chunk_days":  30,
        "description": "Multi-regime — 2 years @ daily",
        "target_trades": 5000,
    },
    "PHASE_3_MULTI_REGIME": {
        "days_back":   1825,     # 5 years
        "interval":    "1d",     # Yahoo daily
        "symbols":     hrengine.WATCHLISTS["mega_cap"],
        "chunk_days":  60,
        "description": "Institutional — 5 years @ daily",
        "target_trades": 99999,
    },
}

# ── Logging ───────────────────────────────────────────────────────
def _log(msg: str):
    ts   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(DAEMON_LOG, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass

# ── State ─────────────────────────────────────────────────────────
def _load_state() -> dict:
    try:
        if os.path.exists(STATE_PATH):
            with open(STATE_PATH) as f:
                return json.load(f)
    except Exception:
        pass
    return {
        "phase":           "PHASE_0_INITIALIZING",
        "last_replay_end": None,
        "total_cycles":    0,
        "total_trades":    0,
        "started_at":      datetime.now().isoformat(),
    }

def _save_state(state: dict):
    try:
        with open(STATE_PATH, "w") as f:
            json.dump(state, f, indent=2, default=str)
    except Exception:
        pass

def _current_phase() -> str:
    summary = ambuilder.build_memory_summary()
    return summary.get("phase", "PHASE_0_INITIALIZING")

# ── Single Replay Cycle ───────────────────────────────────────────
def run_cycle(state: dict) -> dict:
    phase  = _current_phase()
    config = PHASE_CONFIG.get(phase, PHASE_CONFIG["PHASE_0_INITIALIZING"])

    _log(f"  Phase: {phase}")
    _log(f"  {config['description']}")
    _log(f"  Interval: {config['interval']} | "
         f"Source: {'Alpaca' if config['interval'] != '1d' else 'Yahoo Daily'}")

    end_date    = datetime.now() - timedelta(days=1)
    days_back   = config["days_back"]
    chunk_days  = config["chunk_days"]
    last_replay = state.get("last_replay_end")

    if last_replay:
        try:
            chunk_start = datetime.strptime(last_replay, "%Y-%m-%d") + timedelta(days=1)
        except Exception:
            chunk_start = end_date - timedelta(days=days_back)
    else:
        chunk_start = end_date - timedelta(days=days_back)

    chunk_end = min(chunk_start + timedelta(days=chunk_days), end_date)

    if chunk_start > end_date:
        _log("  Cycle complete — restarting from beginning")
        chunk_start = end_date - timedelta(days=days_back)
        chunk_end   = chunk_start + timedelta(days=chunk_days)

    start_str = chunk_start.strftime("%Y-%m-%d")
    end_str   = chunk_end.strftime("%Y-%m-%d")

    # Deduplicate symbols
    symbols = list(set(config["symbols"]))
    _log(f"  Replaying {start_str} → {end_str} | {len(symbols)} symbols")

    try:
        result = hrengine.replay_batch(
            symbols    = symbols,
            start_date = start_str,
            end_date   = end_str,
            interval   = config["interval"],
            verbose    = False,
        )

        state["last_replay_end"] = end_str
        state["total_cycles"]    = state.get("total_cycles", 0) + 1
        state["total_trades"]    = state.get("total_trades", 0) + result.get("total_trades", 0)
        state["phase"]           = phase
        state["last_cycle_at"]   = datetime.now().isoformat()

        _log(f"  ✔ Cycle {state['total_cycles']} | "
             f"Trades: {result.get('total_trades', 0)} | "
             f"Total: {state['total_trades']}")

        suggestions = ambuilder.generate_suggestions()
        ambuilder.track_confidence_evolution()
        _log(f"  Suggestions: {len(suggestions)}")

    except Exception as e:
        _log(f"  ✗ Cycle error (non-fatal): {e}")

    return state

# ── Status Report ─────────────────────────────────────────────────
def report_status():
    state   = _load_state()
    summary = ambuilder.build_memory_summary()
    lib     = slib.get_library_summary()
    regimes = rengine.get_regime_summary()

    _log("  ── STATUS REPORT ────────────────────────────────")
    _log(f"  Phase:         {summary.get('phase', 'N/A')}")
    _log(f"  Total trades:  {lib.get('total_trades', 0)}")
    _log(f"  Best setup:    {lib.get('best_setup', 'N/A')} "
         f"({lib.get('best_expectancy', 0):+.2f}%)")
    _log(f"  Regimes mapped:{len(regimes)}")
    _log(f"  Cycles run:    {state.get('total_cycles', 0)}")

    config = PHASE_CONFIG.get(summary.get("phase", "PHASE_0_INITIALIZING"), {})
    target = config.get("target_trades", 500)
    current_trades = lib.get("total_trades", 0)
    pct = min(100, current_trades / max(target, 1) * 100)
    _log(f"  Phase progress:{current_trades}/{target} ({pct:.1f}%)")

# ── Daemon ────────────────────────────────────────────────────────
def run_daemon(interval_min: int = 30, max_cycles: int = 0):
    _log("="*55)
    _log("  HISTORICAL LEARNING DAEMON")
    _log("  Alpaca (5m/years) + Yahoo (1d/any date)")
    _log("  Low Priority — Non-Blocking — Advisory Only")
    _log("="*55)

    state = _load_state()
    count = 0

    while True:
        try:
            _log(f"\n  ── Cycle {count+1} ──────────────────────────────")
            state = run_cycle(state)
            _save_state(state)
            count += 1

            if max_cycles > 0 and count >= max_cycles:
                _log(f"  Max cycles ({max_cycles}) reached")
                break

            if count % 5 == 0:
                report_status()

            _log(f"  Sleeping {interval_min} min...")
            time.sleep(interval_min * 60)

        except KeyboardInterrupt:
            _log("  Stopped by user")
            break
        except Exception as e:
            _log(f"  Daemon error: {e}")
            time.sleep(60)

    _log("  Daemon finished")

# ── CLI ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Minervini AI — Historical Learning Daemon"
    )
    parser.add_argument("--mode",
                        choices=["daemon","once","status","phase1","phase2","phase3"],
                        default="daemon")
    parser.add_argument("--interval", type=int, default=30,
                        help="Minutes between cycles")
    parser.add_argument("--cycles",   type=int, default=0,
                        help="Max cycles (0=infinite)")
    args = parser.parse_args()

    print("""
╔══════════════════════════════════════════════════════════════════╗
║   MINERVINI AI — HISTORICAL LEARNING DAEMON                      ║
║   Alpaca: years of 5m data | Yahoo: daily fallback               ║
║   ⚠  ADVISORY ONLY — NO LIVE TRADING — LOW CPU                  ║
╚══════════════════════════════════════════════════════════════════╝
    """)

    if args.mode == "status":
        report_status()

    elif args.mode == "once":
        state = _load_state()
        state = run_cycle(state)
        _save_state(state)
        report_status()

    elif args.mode == "phase1":
        _log("Phase 1 — Last 12 months @ 5min (Alpaca)")
        end   = datetime.now() - timedelta(days=1)
        start = end - timedelta(days=365)
        hrengine.replay_batch(
            symbols    = list(set(hrengine.WATCHLISTS["tech_leaders"] +
                                  hrengine.WATCHLISTS["growth_leaders"])),
            start_date = start.strftime("%Y-%m-%d"),
            end_date   = end.strftime("%Y-%m-%d"),
            interval   = "5m",
            verbose    = True,
        )
        ambuilder.generate_suggestions()
        ambuilder.build_memory_summary()
        report_status()

    elif args.mode == "phase2":
        _log("Phase 2 — Last 2 years @ daily (Yahoo)")
        end   = datetime.now() - timedelta(days=1)
        start = end - timedelta(days=730)
        hrengine.replay_batch(
            symbols    = list(set(hrengine.WATCHLISTS["tech_leaders"] +
                                  hrengine.WATCHLISTS["growth_leaders"] +
                                  hrengine.WATCHLISTS["sector_etfs"])),
            start_date = start.strftime("%Y-%m-%d"),
            end_date   = end.strftime("%Y-%m-%d"),
            interval   = "1d",
            verbose    = False,
        )
        ambuilder.generate_suggestions()
        ambuilder.build_memory_summary()
        report_status()

    elif args.mode == "phase3":
        _log("Phase 3 — Last 5 years @ daily (Yahoo)")
        end   = datetime.now() - timedelta(days=1)
        start = end - timedelta(days=1825)
        hrengine.replay_batch(
            symbols    = hrengine.WATCHLISTS["mega_cap"],
            start_date = start.strftime("%Y-%m-%d"),
            end_date   = end.strftime("%Y-%m-%d"),
            interval   = "1d",
            verbose    = False,
        )
        ambuilder.generate_suggestions()
        ambuilder.build_memory_summary()
        report_status()

    elif args.mode == "daemon":
        run_daemon(
            interval_min = args.interval,
            max_cycles   = args.cycles,
        )
