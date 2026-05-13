#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║   MINERVINI AI — ADAPTIVE MEMORY BUILDER                         ║
║   Bridge: Historical Replay → Adaptive Intelligence Layer        ║
║   ADVISORY ONLY — NO AUTO-MODIFICATION OF RISK ENGINE            ║
╚══════════════════════════════════════════════════════════════════╝
"""

import sys
import os
sys.path.insert(0, "/root")

import json
import numpy as np
from datetime import datetime
from typing import Optional

# ── Storage ───────────────────────────────────────────────────────
MEMORY_DIR   = "/root/adaptive/memory"
ADAPTIVE_DIR = "/root/adaptive"
os.makedirs(MEMORY_DIR,   exist_ok=True)
os.makedirs(ADAPTIVE_DIR, exist_ok=True)

SUGGESTIONS_PATH   = f"{MEMORY_DIR}/adaptive_suggestions.json"
CONFIDENCE_EVO_PATH= f"{MEMORY_DIR}/confidence_evolution.json"
MEMORY_SUMMARY_PATH= f"{MEMORY_DIR}/memory_summary.json"

# ── Ingest from Setup Library → Adaptive Memory ───────────────────
def ingest_from_library() -> dict:
    """
    Read setup_library.json and feed into adaptive_memory.
    ADVISORY ONLY — suggestions generated, not auto-applied to risk.
    """
    try:
        import adaptive_memory as amem

        lib_path = f"{MEMORY_DIR}/setup_library.json"
        if not os.path.exists(lib_path):
            return {"ingested": 0}

        with open(lib_path) as f:
            library = json.load(f)

        ingested = 0
        for setup, data in library.items():
            total = data.get("total_trades", 0)
            if total == 0:
                continue

            wins    = data.get("wins", 0)
            pnl_sum = sum(data.get("pnl_list", []))

            # Feed into adaptive memory setup stats
            # Use bulk update to avoid individual calls
            stats = amem.get_setup_stats()
            if setup not in stats:
                stats[setup] = {
                    "total": 0, "wins": 0, "losses": 0,
                    "total_pnl": 0.0, "by_regime": {},
                    "last_updated": None, "source": "historical",
                }

            # Merge (don't overwrite live paper data)
            s = stats[setup]
            hist_wins   = wins
            hist_losses = total - wins

            # Weighted merge: give historical 30% weight vs live 70%
            existing_total = s.get("total", 0)
            if existing_total > 0:
                # Blend historical into existing
                blend_factor = min(0.3, total / max(total + existing_total, 1))
                s["total"]     = existing_total + int(total * blend_factor)
                s["wins"]      = s.get("wins", 0) + int(hist_wins * blend_factor)
                s["losses"]    = s.get("losses", 0) + int(hist_losses * blend_factor)
                s["total_pnl"] = s.get("total_pnl", 0) + pnl_sum * blend_factor
            else:
                s["total"]     = total
                s["wins"]      = wins
                s["losses"]    = total - wins
                s["total_pnl"] = pnl_sum

            # By regime
            for regime, rdata in data.get("by_regime", {}).items():
                if regime not in s["by_regime"]:
                    s["by_regime"][regime] = {
                        "wins": 0, "losses": 0, "pnl": 0.0
                    }
                s["by_regime"][regime]["wins"]   += rdata.get("wins", 0)
                s["by_regime"][regime]["losses"] += rdata.get("losses", 0)
                s["by_regime"][regime]["pnl"]    += rdata.get("total_pnl", 0)

            s["last_updated"] = datetime.now().isoformat()
            s["source"]       = "historical_blend"
            stats[setup]      = s
            ingested += 1

        # Save merged stats
        amem._write(amem.PATHS["setup_stats"], stats)
        _log_ingestion(ingested, total_setups=len(library))
        return {"ingested": ingested, "total_setups": len(library)}

    except Exception as e:
        print(f"  [MemBuilder] Ingest error: {e}")
        return {"ingested": 0, "error": str(e)}

# ── Generate Adaptive Suggestions ────────────────────────────────
def generate_suggestions() -> list:
    """
    Analyze historical data and generate ADVISORY suggestions.
    These are NOT auto-applied. Human review required for Level 2+.
    """
    suggestions = []

    lib_path = f"{MEMORY_DIR}/setup_library.json"
    if not os.path.exists(lib_path):
        return suggestions

    try:
        with open(lib_path) as f:
            library = json.load(f)

        for setup, data in library.items():
            total = data.get("total_trades", 0)
            if total < 20:
                continue

            wr        = data.get("win_rate", 0)
            exp       = data.get("expectancy", 0)
            pf        = data.get("profit_factor", 0)
            best_reg  = _best_regime_for_setup(data.get("by_regime", {}))
            worst_reg = _worst_regime_for_setup(data.get("by_regime", {}))

            # Strong setup suggestion
            if wr >= 60 and exp >= 0.5 and total >= 30:
                suggestions.append({
                    "type":        "BOOST_SETUP",
                    "setup":       setup,
                    "title":       f"Increase confidence for {setup}",
                    "description": (
                        f"{setup} shows {wr:.1f}% win rate over {total} trades "
                        f"with {exp:+.2f}% expectancy. "
                        f"Best regime: {best_reg}."
                    ),
                    "proposed":    {"modifier_increase": 0.05},
                    "level":       1,
                    "confidence":  round(wr / 100, 2),
                    "trades":      total,
                })

            # Weak setup suggestion
            elif wr <= 38 and total >= 20:
                suggestions.append({
                    "type":        "REDUCE_SETUP",
                    "setup":       setup,
                    "title":       f"Reduce confidence for {setup}",
                    "description": (
                        f"{setup} shows only {wr:.1f}% win rate over {total} trades. "
                        f"Worst regime: {worst_reg}."
                    ),
                    "proposed":    {"modifier_decrease": 0.05},
                    "level":       1,
                    "confidence":  round(1 - wr / 100, 2),
                    "trades":      total,
                })

            # Regime-specific suggestion
            if best_reg and best_reg != "UNKNOWN":
                best_data = data.get("by_regime", {}).get(best_reg, {})
                best_wr   = best_data.get("win_rate", 0)
                if best_wr >= 65 and best_data.get("total", 0) >= 10:
                    suggestions.append({
                        "type":        "REGIME_FOCUS",
                        "setup":       setup,
                        "regime":      best_reg,
                        "title":       f"{setup} excels in {best_reg}",
                        "description": (
                            f"{setup} achieves {best_wr:.1f}% WR during {best_reg} conditions. "
                            f"Consider prioritizing this setup when regime is {best_reg}."
                        ),
                        "proposed":    {"regime_boost": {best_reg: 0.1}},
                        "level":       2,
                        "confidence":  round(best_wr / 100, 2),
                        "trades":      best_data.get("total", 0),
                    })

        # Save suggestions
        suggestions.sort(key=lambda x: x["confidence"], reverse=True)
        with open(SUGGESTIONS_PATH, "w") as f:
            json.dump(suggestions, f, indent=2, default=str)

        # Register Level 2+ with adaptive memory
        try:
            import adaptive_memory as amem
            for s in suggestions:
                if s.get("level", 1) >= 2:
                    amem.add_pending_approval(
                        title           = s["title"],
                        description     = s["description"],
                        proposed_change = s.get("proposed", {}),
                        level           = s.get("level", 2),
                    )
        except Exception:
            pass

    except Exception as e:
        print(f"  [MemBuilder] Suggestion error: {e}")

    return suggestions

# ── Confidence Evolution Tracking ─────────────────────────────────
def track_confidence_evolution() -> dict:
    """Track how setup confidence changes over time"""
    lib_path = f"{MEMORY_DIR}/setup_library.json"
    if not os.path.exists(lib_path):
        return {}

    try:
        with open(lib_path) as f:
            library = json.load(f)

        evolution = {}
        for setup, data in library.items():
            total = data.get("total_trades", 0)
            if total < 5:
                continue
            evolution[setup] = {
                "win_rate":     data.get("win_rate", 0),
                "expectancy":   data.get("expectancy", 0),
                "profit_factor":data.get("profit_factor", 0),
                "total_trades": total,
                "trend":        _compute_trend(data.get("pnl_list", [])),
            }

        # Append to evolution history
        record = {
            "timestamp": datetime.now().isoformat(),
            "setups":    evolution,
        }

        history = []
        if os.path.exists(CONFIDENCE_EVO_PATH):
            try:
                with open(CONFIDENCE_EVO_PATH) as f:
                    history = json.load(f)
                if not isinstance(history, list):
                    history = []
            except Exception:
                history = []

        history.append(record)
        if len(history) > 100:
            history = history[-100:]

        with open(CONFIDENCE_EVO_PATH, "w") as f:
            json.dump(history, f, indent=2, default=str)

        return evolution

    except Exception as e:
        return {}

def _compute_trend(pnl_list: list) -> str:
    if len(pnl_list) < 10:
        return "INSUFFICIENT_DATA"
    recent = pnl_list[-10:]
    older  = pnl_list[-20:-10] if len(pnl_list) >= 20 else pnl_list[:10]
    recent_avg = np.mean(recent)
    older_avg  = np.mean(older)
    if recent_avg > older_avg + 0.2:
        return "IMPROVING"
    elif recent_avg < older_avg - 0.2:
        return "DECLINING"
    return "STABLE"

# ── Memory Summary ────────────────────────────────────────────────
def build_memory_summary() -> dict:
    lib_path = f"{MEMORY_DIR}/setup_library.json"
    reg_path = f"{MEMORY_DIR}/regime_performance.json"

    library     = {}
    regime_perf = {}

    try:
        if os.path.exists(lib_path):
            with open(lib_path) as f:
                library = json.load(f)
    except Exception:
        pass

    try:
        if os.path.exists(reg_path):
            with open(reg_path) as f:
                regime_perf = json.load(f)
    except Exception:
        pass

    total_trades = sum(v.get("total_trades", 0) for v in library.values())
    qualified    = [v for v in library.values() if v.get("total_trades", 0) >= 10]

    best  = max(qualified, key=lambda x: x.get("expectancy", 0), default=None)
    worst = min(qualified, key=lambda x: x.get("expectancy", 0), default=None)

    # Regime summary
    regime_summary = {}
    for regime, data in regime_perf.items():
        t = data.get("total_trades", 0)
        regime_summary[regime] = {
            "trades":   t,
            "win_rate": data.get("win_rate", 0),
            "avg_pnl":  round(data.get("total_pnl", 0) / max(t, 1), 3),
        }

    summary = {
        "timestamp":        datetime.now().isoformat(),
        "total_setups":     len(library),
        "qualified_setups": len(qualified),
        "total_trades":     total_trades,
        "phase":            _get_phase(total_trades),
        "best_setup":       best["setup"] if best else "N/A",
        "best_expectancy":  best.get("expectancy", 0) if best else 0,
        "worst_setup":      worst["setup"] if worst else "N/A",
        "regime_summary":   regime_summary,
        "suggestions_path": SUGGESTIONS_PATH,
        "evolution_path":   CONFIDENCE_EVO_PATH,
    }

    try:
        with open(MEMORY_SUMMARY_PATH, "w") as f:
            json.dump(summary, f, indent=2, default=str)
    except Exception:
        pass

    return summary

def _get_phase(total_trades: int) -> str:
    if total_trades >= 5000:  return "PHASE_3_MULTI_REGIME"
    if total_trades >= 500:   return "PHASE_2_ADVANCED"
    if total_trades >= 50:    return "PHASE_1_BOOTSTRAP"
    return "PHASE_0_INITIALIZING"

def _best_regime_for_setup(by_regime: dict) -> str:
    qualified = {k: v for k, v in by_regime.items() if v.get("total", 0) >= 5}
    if not qualified:
        return "UNKNOWN"
    return max(qualified.items(),
               key=lambda x: x[1].get("win_rate", 0),
               default=("UNKNOWN", {}))[0]

def _worst_regime_for_setup(by_regime: dict) -> str:
    qualified = {k: v for k, v in by_regime.items() if v.get("total", 0) >= 5}
    if not qualified:
        return "UNKNOWN"
    return min(qualified.items(),
               key=lambda x: x[1].get("win_rate", 100),
               default=("UNKNOWN", {}))[0]

def _log_ingestion(ingested: int, total_setups: int):
    try:
        log_path = f"{MEMORY_DIR}/ingestion_log.json"
        logs = []
        if os.path.exists(log_path):
            with open(log_path) as f:
                logs = json.load(f)
        logs.append({
            "timestamp":    datetime.now().isoformat(),
            "ingested":     ingested,
            "total_setups": total_setups,
        })
        if len(logs) > 200:
            logs = logs[-200:]
        with open(log_path, "w") as f:
            json.dump(logs, f, indent=2)
    except Exception:
        pass


if __name__ == "__main__":
    print("── Adaptive Memory Builder ─────────────────────────")
    print("  Ingesting from setup library...")
    result = ingest_from_library()
    print(f"  Ingested: {result.get('ingested', 0)} setups")

    print("  Generating suggestions...")
    suggestions = generate_suggestions()
    print(f"  Suggestions: {len(suggestions)}")

    print("  Building memory summary...")
    summary = build_memory_summary()
    print(f"  Phase: {summary['phase']}")
    print(f"  Total trades: {summary['total_trades']}")
    print(f"  Best setup: {summary['best_setup']}")
    print("  ✔ Memory Builder ready")
