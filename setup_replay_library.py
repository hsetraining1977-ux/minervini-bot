#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║   MINERVINI AI — SETUP REPLAY LIBRARY                            ║
║   Setup Classification & Statistics Database                     ║
║   HISTORICAL LEARNING ONLY — NO LIVE TRADING                     ║
╚══════════════════════════════════════════════════════════════════╝
"""

import json
import os
import numpy as np
from datetime import datetime
from typing import Optional

# ── Storage ───────────────────────────────────────────────────────
LIBRARY_DIR = "/root/adaptive/history"
MEMORY_DIR  = "/root/adaptive/memory"
os.makedirs(LIBRARY_DIR, exist_ok=True)
os.makedirs(MEMORY_DIR,  exist_ok=True)

SETUP_DB_PATH      = f"{MEMORY_DIR}/setup_library.json"
EXPECTANCY_PATH    = f"{MEMORY_DIR}/setup_expectancy.json"
RANKINGS_PATH      = f"{MEMORY_DIR}/historical_rankings.json"

# ── Setup Definitions ─────────────────────────────────────────────
SETUP_CATALOG = {
    # ── LONG Setups ───────────────────────────────────────────────
    "ORB_BREAKOUT": {
        "direction": "LONG",
        "description": "Opening Range Breakout — price breaks above first 30-min high",
        "key_factors": ["volume_expansion", "trend_alignment", "gap_up"],
        "ideal_regime": ["STRONG_RISK_ON", "RISK_ON"],
        "avoid_regime": ["PANIC", "CHOPPY"],
    },
    "VOLUME_SPIKE": {
        "direction": "LONG",
        "description": "Volume 2x+ average with price expansion",
        "key_factors": ["volume_ratio", "price_momentum", "breadth"],
        "ideal_regime": ["STRONG_RISK_ON", "RISK_ON", "NEUTRAL"],
        "avoid_regime": ["PANIC"],
    },
    "VWAP_CROSS_UP": {
        "direction": "LONG",
        "description": "Price crosses above VWAP with momentum",
        "key_factors": ["vwap_distance", "volume", "trend"],
        "ideal_regime": ["RISK_ON", "NEUTRAL"],
        "avoid_regime": ["RISK_OFF", "PANIC"],
    },
    "TIGHT_CONSOLIDATION_BREAK": {
        "direction": "LONG",
        "description": "Tight range (<1%) breaks out with volume",
        "key_factors": ["range_tightness", "volume_surge", "prior_trend"],
        "ideal_regime": ["STRONG_RISK_ON", "RISK_ON"],
        "avoid_regime": ["CHOPPY", "PANIC"],
    },
    "MOMENTUM_BURST_UP": {
        "direction": "LONG",
        "description": "Strong 1.5%+ single candle momentum with follow-through",
        "key_factors": ["candle_size", "volume", "prior_base"],
        "ideal_regime": ["STRONG_RISK_ON", "RISK_ON"],
        "avoid_regime": ["RISK_OFF", "PANIC", "CHOPPY"],
    },
    "RELATIVE_STRENGTH_LEADER": {
        "direction": "LONG",
        "description": "Stock outperforming SPY/sector significantly",
        "key_factors": ["rs_rating", "sector_momentum", "institutional_buying"],
        "ideal_regime": ["STRONG_RISK_ON", "RISK_ON", "NEUTRAL"],
        "avoid_regime": ["PANIC"],
    },
    "SECTOR_ROTATION_ENTRY": {
        "direction": "LONG",
        "description": "Early entry into rotating sector leadership",
        "key_factors": ["sector_rs", "volume_expansion", "breadth"],
        "ideal_regime": ["RISK_ON", "NEUTRAL"],
        "avoid_regime": ["RISK_OFF", "PANIC"],
    },

    # ── SHORT Setups ──────────────────────────────────────────────
    "ORB_BREAKDOWN": {
        "direction": "SHORT",
        "description": "Opening Range Breakdown — price breaks below first 30-min low",
        "key_factors": ["volume_expansion", "weakness", "gap_down"],
        "ideal_regime": ["RISK_OFF", "PANIC"],
        "avoid_regime": ["STRONG_RISK_ON"],
    },
    "VWAP_CROSS_DOWN": {
        "direction": "SHORT",
        "description": "Price crosses below VWAP with selling pressure",
        "key_factors": ["vwap_distance", "volume", "weakness"],
        "ideal_regime": ["RISK_OFF", "NEUTRAL"],
        "avoid_regime": ["STRONG_RISK_ON"],
    },
    "MOMENTUM_BURST_DOWN": {
        "direction": "SHORT",
        "description": "Strong -1.5%+ downside momentum candle",
        "key_factors": ["candle_size", "volume", "prior_weakness"],
        "ideal_regime": ["RISK_OFF", "PANIC"],
        "avoid_regime": ["STRONG_RISK_ON", "RISK_ON"],
    },
}

# ── Empty Stats Template ──────────────────────────────────────────
def _empty_stats(setup_name: str) -> dict:
    info = SETUP_CATALOG.get(setup_name, {})
    return {
        "setup":        setup_name,
        "direction":    info.get("direction", "LONG"),
        "description":  info.get("description", ""),
        "total_trades": 0,
        "wins":         0,
        "losses":       0,
        "win_rate":     0.0,
        "avg_winner":   0.0,
        "avg_loser":    0.0,
        "expectancy":   0.0,
        "profit_factor":0.0,
        "avg_hold_bars":0.0,
        "avg_rr":       0.0,
        "sharpe":       0.0,
        "by_regime":    {},
        "by_volume_ctx":{},
        "by_volatility":{},
        "pnl_list":     [],
        "last_updated": None,
        "source_count": {"replay": 0, "paper": 0, "historical": 0},
    }

# ── Load / Save DB ────────────────────────────────────────────────
def load_library() -> dict:
    try:
        if os.path.exists(SETUP_DB_PATH):
            with open(SETUP_DB_PATH) as f:
                return json.load(f)
    except Exception:
        pass
    # Initialize with all setups
    return {s: _empty_stats(s) for s in SETUP_CATALOG}

def save_library(db: dict) -> bool:
    try:
        with open(SETUP_DB_PATH, "w") as f:
            json.dump(db, f, indent=2, default=str)
        return True
    except Exception:
        return False

# ── Record Trade Outcome ──────────────────────────────────────────
def record_outcome(
    setup:       str,
    won:         bool,
    pnl_pct:     float,
    regime:      str,
    hold_bars:   int   = 0,
    rr_achieved: float = 0.0,
    volume_ctx:  str   = "NORMAL",   # LOW / NORMAL / HIGH / EXTREME
    volatility:  str   = "NORMAL",   # LOW / NORMAL / HIGH
    source:      str   = "replay",
) -> bool:
    db = load_library()

    if setup not in db:
        db[setup] = _empty_stats(setup)

    s = db[setup]
    s["total_trades"] += 1
    s["source_count"][source] = s["source_count"].get(source, 0) + 1

    if won:
        s["wins"] += 1
    else:
        s["losses"] += 1

    # Keep last 500 PnL values
    pnl_list = s.get("pnl_list", [])
    pnl_list.append(round(pnl_pct, 4))
    if len(pnl_list) > 500:
        pnl_list = pnl_list[-500:]
    s["pnl_list"] = pnl_list

    # Recompute stats
    winners = [p for p in pnl_list if p > 0]
    losers  = [p for p in pnl_list if p <= 0]
    total   = len(pnl_list)

    s["win_rate"]    = round(len(winners) / total * 100, 2) if total > 0 else 0
    s["avg_winner"]  = round(np.mean(winners), 4) if winners else 0
    s["avg_loser"]   = round(abs(np.mean(losers)), 4) if losers else 0

    gross_profit = sum(winners)
    gross_loss   = abs(sum(losers))
    s["profit_factor"] = round(gross_profit / gross_loss, 3) if gross_loss > 0 else gross_profit

    wr = s["win_rate"] / 100
    s["expectancy"] = round(
        wr * s["avg_winner"] - (1 - wr) * s["avg_loser"], 4
    )

    if np.std(pnl_list) > 0:
        s["sharpe"] = round(
            np.mean(pnl_list) / np.std(pnl_list) * np.sqrt(252), 3
        )

    # Hold time
    if hold_bars > 0:
        old_avg  = s.get("avg_hold_bars", 0) or 0
        old_cnt  = s["total_trades"] - 1
        s["avg_hold_bars"] = round(
            (old_avg * old_cnt + hold_bars) / s["total_trades"], 1
        )

    # RR
    if rr_achieved != 0:
        old_rr  = s.get("avg_rr", 0) or 0
        old_cnt = s["total_trades"] - 1
        s["avg_rr"] = round(
            (old_rr * old_cnt + rr_achieved) / s["total_trades"], 3
        )

    # By regime
    if regime:
        if regime not in s["by_regime"]:
            s["by_regime"][regime] = {
                "total": 0, "wins": 0, "losses": 0,
                "total_pnl": 0.0, "win_rate": 0.0,
            }
        r = s["by_regime"][regime]
        r["total"]     += 1
        r["total_pnl"] += pnl_pct
        if won:
            r["wins"] += 1
        else:
            r["losses"] += 1
        r["win_rate"] = round(r["wins"] / r["total"] * 100, 1)

    # By volume context
    if volume_ctx not in s["by_volume_ctx"]:
        s["by_volume_ctx"][volume_ctx] = {"total": 0, "wins": 0, "pnl": 0.0}
    s["by_volume_ctx"][volume_ctx]["total"] += 1
    s["by_volume_ctx"][volume_ctx]["pnl"]   += pnl_pct
    if won:
        s["by_volume_ctx"][volume_ctx]["wins"] += 1

    # By volatility
    if volatility not in s["by_volatility"]:
        s["by_volatility"][volatility] = {"total": 0, "wins": 0, "pnl": 0.0}
    s["by_volatility"][volatility]["total"] += 1
    s["by_volatility"][volatility]["pnl"]   += pnl_pct
    if won:
        s["by_volatility"][volatility]["wins"] += 1

    s["last_updated"] = datetime.now().isoformat()
    db[setup] = s
    return save_library(db)

# ── Generate Expectancy Report ────────────────────────────────────
def generate_expectancy_report() -> dict:
    db = load_library()
    report = {}

    for setup, data in db.items():
        if data["total_trades"] < 5:
            continue
        report[setup] = {
            "setup":        setup,
            "direction":    data["direction"],
            "total_trades": data["total_trades"],
            "win_rate":     data["win_rate"],
            "expectancy":   data["expectancy"],
            "profit_factor":data["profit_factor"],
            "avg_winner":   data["avg_winner"],
            "avg_loser":    data["avg_loser"],
            "avg_rr":       data["avg_rr"],
            "sharpe":       data["sharpe"],
            "best_regime":  _best_regime(data["by_regime"]),
            "worst_regime": _worst_regime(data["by_regime"]),
        }

    # Sort by expectancy
    sorted_report = dict(sorted(
        report.items(),
        key=lambda x: x[1]["expectancy"],
        reverse=True,
    ))

    try:
        with open(EXPECTANCY_PATH, "w") as f:
            json.dump(sorted_report, f, indent=2, default=str)
    except Exception:
        pass

    return sorted_report

# ── Generate Rankings ─────────────────────────────────────────────
def generate_rankings() -> dict:
    db = load_library()
    qualified = {k: v for k, v in db.items() if v["total_trades"] >= 5}

    rankings = {
        "by_win_rate":    _rank_by(qualified, "win_rate"),
        "by_expectancy":  _rank_by(qualified, "expectancy"),
        "by_profit_factor":_rank_by(qualified, "profit_factor"),
        "by_sharpe":      _rank_by(qualified, "sharpe"),
        "best_long":      _rank_direction(qualified, "LONG",  "expectancy"),
        "best_short":     _rank_direction(qualified, "SHORT", "expectancy"),
        "generated_at":   datetime.now().isoformat(),
        "total_setups":   len(db),
        "qualified_setups":len(qualified),
        "total_trades":   sum(v["total_trades"] for v in db.values()),
    }

    try:
        with open(RANKINGS_PATH, "w") as f:
            json.dump(rankings, f, indent=2, default=str)
    except Exception:
        pass

    return rankings

def _rank_by(db: dict, key: str, top: int = 5) -> list:
    return sorted(
        [{"setup": k, key: v.get(key, 0), "trades": v["total_trades"]}
         for k, v in db.items()],
        key=lambda x: x[key], reverse=True,
    )[:top]

def _rank_direction(db: dict, direction: str, key: str) -> list:
    filtered = {k: v for k, v in db.items() if v.get("direction") == direction}
    return _rank_by(filtered, key)

def _best_regime(by_regime: dict) -> str:
    if not by_regime:
        return "UNKNOWN"
    return max(by_regime.items(),
               key=lambda x: x[1].get("win_rate", 0),
               default=("UNKNOWN", {}))[0]

def _worst_regime(by_regime: dict) -> str:
    if not by_regime:
        return "UNKNOWN"
    qualified = {k: v for k, v in by_regime.items() if v.get("total", 0) >= 3}
    if not qualified:
        return "UNKNOWN"
    return min(qualified.items(),
               key=lambda x: x[1].get("win_rate", 100),
               default=("UNKNOWN", {}))[0]

# ── Summary ───────────────────────────────────────────────────────
def get_library_summary() -> dict:
    db = load_library()
    total_trades = sum(v["total_trades"] for v in db.values())
    qualified    = [v for v in db.values() if v["total_trades"] >= 5]

    best = max(qualified, key=lambda x: x["expectancy"], default=None)
    worst= min(qualified, key=lambda x: x["expectancy"], default=None)

    return {
        "timestamp":        datetime.now().isoformat(),
        "total_setups":     len(db),
        "qualified_setups": len(qualified),
        "total_trades":     total_trades,
        "best_setup":       best["setup"] if best else "N/A",
        "best_expectancy":  best["expectancy"] if best else 0,
        "worst_setup":      worst["setup"] if worst else "N/A",
        "worst_expectancy": worst["expectancy"] if worst else 0,
        "avg_win_rate":     round(np.mean([v["win_rate"] for v in qualified]), 1) if qualified else 0,
    }


if __name__ == "__main__":
    print("── Setup Replay Library ────────────────────────────")
    summary = get_library_summary()
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print(f"\n  Catalog: {list(SETUP_CATALOG.keys())}")
    print("  ✔ Setup Library ready")
