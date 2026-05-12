"""
trade_lifecycle.py
TRADE LIFECYCLE TRACKER
Minervini Bot — PAPER TRADING ONLY
"""

import json
import os
import datetime
import logging
from typing import Optional

log = logging.getLogger("trade_lifecycle")
DATA_DIR = "/root/logs"
LIFECYCLE_FILE = f"{DATA_DIR}/trade_lifecycle.json"

# ── Lifecycle stages ──────────────────────────────────────────────────────────
STAGES = [
    "PLANNED",
    "PENDING",
    "ENTERED",
    "SCALED_IN",
    "PARTIAL_EXIT",
    "TRAILING",
    "CLOSED",
    "CANCELLED",
]

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

def _now():
    return datetime.datetime.now().isoformat()

# ── Create lifecycle ──────────────────────────────────────────────────────────
def create_lifecycle(plan: dict) -> dict:
    """Initialize a full lifecycle record for a trade plan."""
    trade_id = f"{plan.get('symbol','?')}_{int(datetime.datetime.now().timestamp())}"
    lifecycle = {
        "trade_id":       trade_id,
        "symbol":         plan.get("symbol", ""),
        "setup_type":     plan.get("setup", "Minervini SEPA"),
        "direction":      plan.get("direction", "LONG"),
        "entry_price":    plan.get("entry", plan.get("entry_price", 0)),
        "stop_loss":      plan.get("stop_loss", plan.get("sl", 0)),
        "take_profit_1":  plan.get("take_profit_1", plan.get("tp1", 0)),
        "take_profit_2":  plan.get("take_profit_2", plan.get("tp2", 0)),
        "take_profit_3":  plan.get("take_profit_3", plan.get("tp3", 0)),
        "execution_score": plan.get("execution_score", plan.get("score", 0)),
        "market_regime":  plan.get("regime", plan.get("market_regime", "NEUTRAL")),
        "current_stage":  "PLANNED",
        "stage_history":  [{"stage": "PLANNED", "timestamp": _now(), "notes": "Trade plan created"}],
        "health_history": [],
        "pnl_history":    [],
        "events":         [],
        "mfe":            0.0,   # max favorable excursion
        "mae":            0.0,   # max adverse excursion
        "shares":         0,
        "realized_pnl":   0.0,
        "unrealized_pnl": 0.0,
        "exit_reason":    None,
        "exit_price":     None,
        "duration_mins":  0,
        "paper_only":     True,
        "created_at":     _now(),
        "closed_at":      None,
    }
    lifecycles = _load(LIFECYCLE_FILE, {})
    lifecycles[trade_id] = lifecycle
    _save(LIFECYCLE_FILE, lifecycles)
    log.info(f"[{lifecycle['symbol']}] Lifecycle created: {trade_id}")
    return lifecycle

# ── Advance stage ─────────────────────────────────────────────────────────────
def advance_stage(trade_id: str, new_stage: str, notes: str = "", data: dict = {}) -> bool:
    """Move trade to next lifecycle stage."""
    if new_stage not in STAGES:
        log.error(f"Invalid stage: {new_stage}")
        return False

    lifecycles = _load(LIFECYCLE_FILE, {})
    if trade_id not in lifecycles:
        log.error(f"Trade not found: {trade_id}")
        return False

    lc = lifecycles[trade_id]
    old_stage = lc["current_stage"]
    lc["current_stage"] = new_stage
    lc["stage_history"].append({
        "stage":     new_stage,
        "timestamp": _now(),
        "notes":     notes,
        "data":      data,
    })

    # Update specific fields on stage transition
    if new_stage == "ENTERED":
        lc["entered_at"] = _now()
        lc["shares"] = data.get("shares", lc.get("shares", 0))

    elif new_stage in ("CLOSED", "CANCELLED"):
        lc["closed_at"]   = _now()
        lc["exit_price"]  = data.get("exit_price", 0)
        lc["exit_reason"] = data.get("exit_reason", "MANUAL")
        lc["realized_pnl"] = data.get("realized_pnl", 0)
        if lc.get("entered_at"):
            entered = datetime.datetime.fromisoformat(lc["entered_at"])
            lc["duration_mins"] = int(
                (datetime.datetime.now() - entered).total_seconds() / 60
            )

    lc.update({k: v for k, v in data.items()
                if k not in ("stage", "timestamp", "notes")})

    lifecycles[trade_id] = lc
    _save(LIFECYCLE_FILE, lifecycles)
    log.info(f"[{lc['symbol']}] Stage: {old_stage} → {new_stage} | {notes}")
    return True

# ── Log event ─────────────────────────────────────────────────────────────────
def log_event(trade_id: str, event_type: str, details: dict = {}):
    """Log any lifecycle event."""
    lifecycles = _load(LIFECYCLE_FILE, {})
    if trade_id not in lifecycles:
        return
    lifecycles[trade_id]["events"].append({
        "type":      event_type,
        "timestamp": _now(),
        "details":   details,
    })
    _save(LIFECYCLE_FILE, lifecycles)

# ── Update PnL ────────────────────────────────────────────────────────────────
def update_pnl(trade_id: str, current_price: float):
    """Update unrealized PnL and MFE/MAE."""
    lifecycles = _load(LIFECYCLE_FILE, {})
    if trade_id not in lifecycles:
        return
    lc = lifecycles[trade_id]
    entry  = float(lc.get("entry_price", current_price))
    shares = int(lc.get("shares", 0))
    unreal = round((current_price - entry) * shares, 2)
    lc["unrealized_pnl"] = unreal
    lc["mfe"] = max(lc.get("mfe", 0), unreal)
    lc["mae"] = min(lc.get("mae", 0), unreal)
    lc["pnl_history"].append({
        "ts":    _now(),
        "price": current_price,
        "pnl":   unreal,
    })
    # Keep last 200 entries
    if len(lc["pnl_history"]) > 200:
        lc["pnl_history"] = lc["pnl_history"][-200:]
    lifecycles[trade_id] = lc
    _save(LIFECYCLE_FILE, lifecycles)

# ── Get active trades ─────────────────────────────────────────────────────────
def get_active_lifecycles() -> list:
    lifecycles = _load(LIFECYCLE_FILE, {})
    return [
        lc for lc in lifecycles.values()
        if lc.get("current_stage") not in ("CLOSED", "CANCELLED")
    ]

def get_all_lifecycles() -> dict:
    return _load(LIFECYCLE_FILE, {})

def get_lifecycle(trade_id: str) -> Optional[dict]:
    return _load(LIFECYCLE_FILE, {}).get(trade_id)
