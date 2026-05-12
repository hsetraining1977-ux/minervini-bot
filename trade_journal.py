"""
trade_journal.py
TRADE JOURNAL AI
Minervini Bot — PAPER TRADING ONLY
"""

import json
import os
import datetime
import logging
from exit_intelligence import calc_efficiency_score

log = logging.getLogger("trade_journal")
DATA_DIR     = "/root/logs"
JOURNAL_FILE = f"{DATA_DIR}/trade_journal_v2.json"
ANALYTICS_FILE = f"{DATA_DIR}/trade_analytics.json"

def _load(path, default):
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
    except Exception as e:
        log.error(f"Save error: {e}")

# ── Save trade to journal ─────────────────────────────────────────────────────
def save_trade_journal(trade: dict, lifecycle: dict = {}, health_history: list = []):
    """Save complete trade record to journal database."""
    journal = _load(JOURNAL_FILE, [])

    efficiency = calc_efficiency_score(trade)
    entry      = float(trade.get("entry_price", 0))
    exit_p     = float(trade.get("exit_price", 0))
    shares     = int(trade.get("shares", 0))
    pnl        = round((exit_p - entry) * shares, 2) if exit_p and shares else 0

    record = {
        "trade_id":         trade.get("trade_id", ""),
        "symbol":           trade.get("symbol", ""),
        "setup_type":       trade.get("setup_type", "Minervini SEPA"),
        "market_regime":    trade.get("market_regime", "NEUTRAL"),
        "direction":        trade.get("direction", "LONG"),

        # Prices
        "entry_price":      entry,
        "exit_price":       exit_p,
        "stop_loss":        trade.get("stop_loss", 0),
        "take_profit_1":    trade.get("take_profit_1", 0),

        # Scores
        "execution_score":  trade.get("execution_score", 0),
        "efficiency_grade": efficiency["grade"],
        "efficiency_score": efficiency["total_score"],

        # PnL
        "pnl":              pnl,
        "pnl_pct":          round(pnl / (entry * shares) * 100, 2) if entry and shares else 0,
        "mfe":              trade.get("mfe", 0),
        "mae":              trade.get("mae", 0),
        "realized_pnl":     trade.get("realized_pnl", pnl),

        # Duration
        "duration_mins":    trade.get("duration_mins", 0),
        "entered_at":       trade.get("entered_at", ""),
        "closed_at":        trade.get("closed_at", datetime.datetime.now().isoformat()),

        # Exit
        "exit_reason":      trade.get("exit_reason", "MANUAL"),
        "stage_reached":    lifecycle.get("current_stage", "CLOSED"),
        "lifecycle_events": lifecycle.get("events", []),

        # Quality
        "entry_quality":    trade.get("entry_quality", "N/A"),
        "efficiency_components": efficiency["components"],

        # Meta
        "paper_only":       True,
        "saved_at":         datetime.datetime.now().isoformat(),
    }

    journal.append(record)
    _save(JOURNAL_FILE, journal)
    log.info(f"[{record['symbol']}] Journal saved | Grade={record['efficiency_grade']} | PnL=${pnl:.2f}")

    # Update analytics
    _update_analytics(record)
    return record

# ── Institutional analytics ───────────────────────────────────────────────────
def _update_analytics(record: dict):
    """Update cumulative institutional analytics."""
    analytics = _load(ANALYTICS_FILE, {
        "total_trades":    0,
        "wins":            0,
        "losses":          0,
        "total_pnl":       0.0,
        "avg_pnl":         0.0,
        "avg_duration":    0.0,
        "avg_efficiency":  0.0,
        "best_trade":      None,
        "worst_trade":     None,
        "by_regime":       {},
        "by_setup":        {},
        "by_grade":        {"A+": 0, "A": 0, "B": 0, "C": 0, "D": 0},
        "by_exit_reason":  {},
        "win_quality":     [],
        "loss_quality":    [],
        "updated_at":      "",
    })

    pnl   = record["pnl"]
    grade = record["efficiency_grade"]

    analytics["total_trades"] += 1
    analytics["total_pnl"]    = round(analytics["total_pnl"] + pnl, 2)

    if pnl > 0:
        analytics["wins"]         += 1
        analytics["win_quality"].append(grade)
    else:
        analytics["losses"]       += 1
        analytics["loss_quality"].append(grade)

    # Avg efficiency
    n   = analytics["total_trades"]
    old = analytics["avg_efficiency"]
    analytics["avg_efficiency"] = round(
        (old * (n-1) + record["efficiency_score"]) / n, 1
    )

    # Avg duration
    old_d = analytics["avg_duration"]
    analytics["avg_duration"] = round(
        (old_d * (n-1) + record["duration_mins"]) / n, 1
    )

    # Avg PnL
    analytics["avg_pnl"] = round(analytics["total_pnl"] / n, 2)

    # Best/worst
    if not analytics["best_trade"] or pnl > analytics["best_trade"].get("pnl", 0):
        analytics["best_trade"] = {
            "symbol": record["symbol"], "pnl": pnl, "grade": grade
        }
    if not analytics["worst_trade"] or pnl < analytics["worst_trade"].get("pnl", 0):
        analytics["worst_trade"] = {
            "symbol": record["symbol"], "pnl": pnl, "grade": grade
        }

    # By regime
    regime = record["market_regime"]
    if regime not in analytics["by_regime"]:
        analytics["by_regime"][regime] = {"trades": 0, "pnl": 0, "wins": 0}
    analytics["by_regime"][regime]["trades"] += 1
    analytics["by_regime"][regime]["pnl"]    += pnl
    if pnl > 0:
        analytics["by_regime"][regime]["wins"] += 1

    # By setup
    setup = record["setup_type"]
    if setup not in analytics["by_setup"]:
        analytics["by_setup"][setup] = {"trades": 0, "pnl": 0}
    analytics["by_setup"][setup]["trades"] += 1
    analytics["by_setup"][setup]["pnl"]    += pnl

    # By grade
    analytics["by_grade"][grade] = analytics["by_grade"].get(grade, 0) + 1

    # By exit reason
    exit_r = record["exit_reason"]
    if exit_r not in analytics["by_exit_reason"]:
        analytics["by_exit_reason"][exit_r] = {"count": 0, "pnl": 0}
    analytics["by_exit_reason"][exit_r]["count"] += 1
    analytics["by_exit_reason"][exit_r]["pnl"]   += pnl

    analytics["updated_at"] = datetime.datetime.now().isoformat()
    _save(ANALYTICS_FILE, analytics)

def get_analytics() -> dict:
    return _load(ANALYTICS_FILE, {})

def get_journal(limit: int = 50) -> list:
    journal = _load(JOURNAL_FILE, [])
    return journal[-limit:]

def get_best_setups(n: int = 5) -> list:
    journal = _load(JOURNAL_FILE, [])
    winners = [t for t in journal if t.get("pnl", 0) > 0]
    return sorted(winners, key=lambda x: x.get("pnl", 0), reverse=True)[:n]

def get_worst_setups(n: int = 5) -> list:
    journal = _load(JOURNAL_FILE, [])
    losers  = [t for t in journal if t.get("pnl", 0) < 0]
    return sorted(losers, key=lambda x: x.get("pnl", 0))[:n]
