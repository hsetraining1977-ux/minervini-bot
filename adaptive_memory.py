#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║   MINERVINI AI — ADAPTIVE MEMORY                                 ║
║   Persistent Storage for Adaptive Learning Layer                 ║
║   PAPER TRADING ONLY — NO LIVE EXECUTION                         ║
╚══════════════════════════════════════════════════════════════════╝
"""

import json
import os
import threading
from datetime import datetime
from typing import Any, Optional

# ── Storage Paths ─────────────────────────────────────────────────
MEMORY_DIR = "/root/adaptive"
os.makedirs(MEMORY_DIR, exist_ok=True)

PATHS = {
    "setup_stats":       f"{MEMORY_DIR}/setup_statistics.json",
    "regime_perf":       f"{MEMORY_DIR}/regime_performance.json",
    "confidence_hist":   f"{MEMORY_DIR}/confidence_history.json",
    "adaptive_changes":  f"{MEMORY_DIR}/adaptive_changes.json",
    "missed_analysis":   f"{MEMORY_DIR}/missed_analysis.json",
    "learning_history":  f"{MEMORY_DIR}/learning_history.json",
    "current_weights":   f"{MEMORY_DIR}/current_weights.json",
    "pending_approvals": f"{MEMORY_DIR}/pending_approvals.json",
    "narratives":        f"{MEMORY_DIR}/narratives.json",
}

# ── Thread Safety ─────────────────────────────────────────────────
_lock = threading.Lock()

# ── Default Weights (LEVEL 1 — Safe Auto) ────────────────────────
DEFAULT_WEIGHTS = {
    "version":    1,
    "updated_at": datetime.now().isoformat(),

    # Setup confidence modifiers (multiplicative, max ±20%)
    "setup_modifiers": {
        "ORB_BREAKOUT":             1.0,
        "VOLUME_SPIKE":             1.0,
        "VWAP_CROSS_UP":            1.0,
        "MOMENTUM_BURST_UP":        1.0,
        "TIGHT_CONSOLIDATION_BREAK":1.0,
        "ORB_BREAKDOWN":            1.0,
        "VWAP_CROSS_DOWN":          1.0,
        "MOMENTUM_BURST_DOWN":      1.0,
    },

    # Regime aggressiveness (1.0 = normal)
    "regime_aggressiveness": {
        "RISK_ON":    1.0,
        "NEUTRAL":    1.0,
        "RISK_OFF":   1.0,
        "TRANSITION": 1.0,
    },

    # Position sizing modifiers (max ±15%)
    "sizing_modifiers": {
        "RISK_ON":  1.0,
        "NEUTRAL":  1.0,
        "RISK_OFF": 1.0,
    },

    # Confidence floor by regime
    "confidence_floor": {
        "RISK_ON":    0.55,
        "NEUTRAL":    0.65,
        "RISK_OFF":   0.75,
        "TRANSITION": 0.70,
    },
}

# ── Safety Limits (LEVEL 1 hard caps) ────────────────────────────
SAFETY_LIMITS = {
    "setup_modifier_min":       0.80,   # -20% max reduction
    "setup_modifier_max":       1.20,   # +20% max boost
    "regime_aggr_min":          0.85,
    "regime_aggr_max":          1.15,
    "sizing_modifier_min":      0.85,
    "sizing_modifier_max":      1.15,
    "confidence_floor_min":     0.50,
    "confidence_floor_max":     0.85,
}

# ── Core Read/Write ───────────────────────────────────────────────
def _read(path: str, default: Any = None) -> Any:
    if default is None:
        default = {}
    try:
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return default

def _write(path: str, data: Any) -> bool:
    try:
        with _lock:
            with open(path, "w") as f:
                json.dump(data, f, indent=2, default=str)
        return True
    except Exception:
        return False

def _append(path: str, record: dict) -> bool:
    try:
        with _lock:
            existing = _read(path, [])
            if not isinstance(existing, list):
                existing = [existing]
            existing.append(record)
            # Keep last 1000 records
            if len(existing) > 1000:
                existing = existing[-1000:]
            with open(path, "w") as f:
                json.dump(existing, f, indent=2, default=str)
        return True
    except Exception:
        return False

# ── Weights API ───────────────────────────────────────────────────
def load_weights() -> dict:
    stored = _read(PATHS["current_weights"])
    if not stored:
        _write(PATHS["current_weights"], DEFAULT_WEIGHTS)
        return DEFAULT_WEIGHTS.copy()
    # Merge with defaults to handle new keys
    merged = DEFAULT_WEIGHTS.copy()
    for k, v in stored.items():
        if isinstance(v, dict) and k in merged:
            merged[k].update(v)
        else:
            merged[k] = v
    return merged

def save_weights(weights: dict) -> bool:
    weights["updated_at"] = datetime.now().isoformat()
    return _write(PATHS["current_weights"], weights)

def reset_weights() -> bool:
    """Rollback to static defaults"""
    defaults = DEFAULT_WEIGHTS.copy()
    defaults["updated_at"] = datetime.now().isoformat()
    defaults["version"] = load_weights().get("version", 1) + 1
    log_change("ROLLBACK", "All weights reset to defaults", "SYSTEM", auto_applied=True)
    return _write(PATHS["current_weights"], defaults)

# ── Setup Statistics API ──────────────────────────────────────────
def update_setup_stat(setup: str, won: bool, pnl_pct: float,
                      regime: str, source: str = "replay") -> bool:
    stats = _read(PATHS["setup_stats"], {})
    if setup not in stats:
        stats[setup] = {
            "total": 0, "wins": 0, "losses": 0,
            "total_pnl": 0.0, "by_regime": {},
            "last_updated": None, "source": source,
        }
    stats[setup]["total"]     += 1
    stats[setup]["total_pnl"] += pnl_pct
    if won:
        stats[setup]["wins"] += 1
    else:
        stats[setup]["losses"] += 1

    # By regime
    if regime not in stats[setup]["by_regime"]:
        stats[setup]["by_regime"][regime] = {"wins": 0, "losses": 0, "pnl": 0.0}
    if won:
        stats[setup]["by_regime"][regime]["wins"] += 1
    else:
        stats[setup]["by_regime"][regime]["losses"] += 1
    stats[setup]["by_regime"][regime]["pnl"] += pnl_pct
    stats[setup]["last_updated"] = datetime.now().isoformat()

    return _write(PATHS["setup_stats"], stats)

def get_setup_stats() -> dict:
    return _read(PATHS["setup_stats"], {})

# ── Regime Performance API ────────────────────────────────────────
def update_regime_perf(regime: str, won: bool, pnl_pct: float,
                       source: str = "replay") -> bool:
    perf = _read(PATHS["regime_perf"], {})
    if regime not in perf:
        perf[regime] = {
            "total": 0, "wins": 0, "losses": 0,
            "total_pnl": 0.0, "last_updated": None,
        }
    perf[regime]["total"]     += 1
    perf[regime]["total_pnl"] += pnl_pct
    if won:
        perf[regime]["wins"] += 1
    else:
        perf[regime]["losses"] += 1
    perf[regime]["last_updated"] = datetime.now().isoformat()
    return _write(PATHS["regime_perf"], perf)

def get_regime_perf() -> dict:
    return _read(PATHS["regime_perf"], {})

# ── Confidence History API ────────────────────────────────────────
def log_confidence_change(setup: str, old_val: float,
                           new_val: float, reason: str) -> bool:
    return _append(PATHS["confidence_hist"], {
        "timestamp": datetime.now().isoformat(),
        "setup":     setup,
        "old_value": round(old_val, 4),
        "new_value": round(new_val, 4),
        "delta":     round(new_val - old_val, 4),
        "reason":    reason,
    })

def get_confidence_history(limit: int = 100) -> list:
    hist = _read(PATHS["confidence_hist"], [])
    return hist[-limit:] if len(hist) > limit else hist

# ── Adaptive Changes Log ──────────────────────────────────────────
def log_change(change_type: str, description: str,
               component: str, auto_applied: bool = False,
               level: int = 1, details: dict = None) -> bool:
    return _append(PATHS["adaptive_changes"], {
        "timestamp":    datetime.now().isoformat(),
        "type":         change_type,
        "description":  description,
        "component":    component,
        "auto_applied": auto_applied,
        "level":        level,
        "details":      details or {},
        "status":       "applied" if auto_applied else "pending",
    })

def get_changes(limit: int = 50) -> list:
    changes = _read(PATHS["adaptive_changes"], [])
    return changes[-limit:] if len(changes) > limit else changes

# ── Pending Approvals API (LEVEL 2) ──────────────────────────────
def add_pending_approval(title: str, description: str,
                          proposed_change: dict, level: int = 2) -> str:
    approvals = _read(PATHS["pending_approvals"], [])
    approval_id = f"APR_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    approvals.append({
        "id":             approval_id,
        "timestamp":      datetime.now().isoformat(),
        "title":          title,
        "description":    description,
        "proposed_change":proposed_change,
        "level":          level,
        "status":         "PENDING",
        "approved_at":    None,
        "rejected_at":    None,
    })
    _write(PATHS["pending_approvals"], approvals)
    return approval_id

def get_pending_approvals() -> list:
    approvals = _read(PATHS["pending_approvals"], [])
    return [a for a in approvals if a.get("status") == "PENDING"]

def approve_change(approval_id: str) -> bool:
    approvals = _read(PATHS["pending_approvals"], [])
    for a in approvals:
        if a["id"] == approval_id and a["status"] == "PENDING":
            a["status"]      = "APPROVED"
            a["approved_at"] = datetime.now().isoformat()
            _write(PATHS["pending_approvals"], approvals)
            log_change("APPROVAL", f"Approved: {a['title']}", "HUMAN", True, a["level"])
            return True
    return False

def reject_change(approval_id: str) -> bool:
    approvals = _read(PATHS["pending_approvals"], [])
    for a in approvals:
        if a["id"] == approval_id and a["status"] == "PENDING":
            a["status"]      = "REJECTED"
            a["rejected_at"] = datetime.now().isoformat()
            _write(PATHS["pending_approvals"], approvals)
            return True
    return False

# ── Missed Analysis API ───────────────────────────────────────────
def log_missed(symbol: str, move_pct: float, regime: str,
               setups: list, score: int, reason: str) -> bool:
    return _append(PATHS["missed_analysis"], {
        "timestamp":  datetime.now().isoformat(),
        "symbol":     symbol,
        "move_pct":   round(move_pct, 2),
        "regime":     regime,
        "setups":     setups,
        "score":      score,
        "reason":     reason,
    })

def get_missed_analysis(limit: int = 200) -> list:
    data = _read(PATHS["missed_analysis"], [])
    return data[-limit:] if len(data) > limit else data

# ── Learning History API ──────────────────────────────────────────
def log_learning_cycle(source: str, trades_analyzed: int,
                        changes_made: int, summary: str) -> bool:
    return _append(PATHS["learning_history"], {
        "timestamp":       datetime.now().isoformat(),
        "source":          source,
        "trades_analyzed": trades_analyzed,
        "changes_made":    changes_made,
        "summary":         summary,
    })

def get_learning_history(limit: int = 50) -> list:
    hist = _read(PATHS["learning_history"], [])
    return hist[-limit:] if len(hist) > limit else hist

# ── Narratives API ────────────────────────────────────────────────
def save_narrative(narrative: dict, source: str = "adaptive") -> bool:
    return _append(PATHS["narratives"], {
        "timestamp": datetime.now().isoformat(),
        "source":    source,
        "narrative": narrative,
    })

def get_latest_narrative() -> dict:
    narratives = _read(PATHS["narratives"], [])
    return narratives[-1] if narratives else {}

# ── Status Report ─────────────────────────────────────────────────
def get_memory_status() -> dict:
    weights  = load_weights()
    setup_stats = get_setup_stats()
    pending  = get_pending_approvals()
    changes  = get_changes(10)
    history  = get_learning_history(5)

    return {
        "timestamp":        datetime.now().isoformat(),
        "weights_version":  weights.get("version", 1),
        "weights_updated":  weights.get("updated_at"),
        "setups_tracked":   len(setup_stats),
        "pending_approvals":len(pending),
        "recent_changes":   len(changes),
        "learning_cycles":  len(history),
        "memory_dir":       MEMORY_DIR,
        "files": {k: os.path.exists(v) for k, v in PATHS.items()},
    }


if __name__ == "__main__":
    print("── Adaptive Memory Status ──────────────────────────")
    status = get_memory_status()
    for k, v in status.items():
        print(f"  {k}: {v}")
    print(f"\n  Default weights initialized: {MEMORY_DIR}")
    print("  ✔ Adaptive Memory ready")
