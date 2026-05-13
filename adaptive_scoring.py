#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║   MINERVINI AI — ADAPTIVE SCORING ENGINE                         ║
║   Dynamic Confidence & Setup Weighting                           ║
║   LEVEL 1: Safe Auto-Adaptation Only                             ║
╚══════════════════════════════════════════════════════════════════╝
"""

import sys
import os
sys.path.insert(0, "/root")

from datetime import datetime
from typing import Optional
import adaptive_memory as mem

# ── Constants ─────────────────────────────────────────────────────
MIN_TRADES_FOR_ADAPTATION = 10   # Minimum trades before adapting
ADAPTATION_STEP           = 0.02  # Max change per cycle (2%)
STRONG_PERFORMANCE_WR     = 0.60  # Win rate to boost
WEAK_PERFORMANCE_WR       = 0.40  # Win rate to reduce
STRONG_EXPECTANCY         = 0.5   # Expectancy % to boost
WEAK_EXPECTANCY           = -0.3  # Expectancy % to reduce

# ── Apply Adaptive Score ──────────────────────────────────────────
def apply_adaptive_score(base_score: int, setups: list,
                          regime: str) -> dict:
    """
    Apply adaptive modifiers to base score.
    LEVEL 1 ONLY — safe auto-adaptation.
    Original score always preserved for rollback.
    """
    try:
        weights = mem.load_weights()
        setup_mods  = weights.get("setup_modifiers", {})
        regime_aggr = weights.get("regime_aggressiveness", {})

        # Apply setup modifiers
        modifier = 1.0
        applied  = []
        for setup in setups:
            m = setup_mods.get(setup, 1.0)
            if m != 1.0:
                modifier *= m
                applied.append(f"{setup}:{m:.2f}x")

        # Apply regime aggressiveness
        regime_mod = regime_aggr.get(regime, 1.0)
        if regime_mod != 1.0:
            modifier *= regime_mod
            applied.append(f"regime_{regime}:{regime_mod:.2f}x")

        # Clamp modifier
        modifier = max(0.70, min(1.30, modifier))

        adaptive_score = int(base_score * modifier)

        return {
            "base_score":     base_score,
            "adaptive_score": adaptive_score,
            "modifier":       round(modifier, 4),
            "modifiers_applied": applied,
            "regime":         regime,
            "source":         "adaptive_scoring_v1",
        }

    except Exception:
        # FAIL SAFE — return original
        return {
            "base_score":     base_score,
            "adaptive_score": base_score,
            "modifier":       1.0,
            "modifiers_applied": [],
            "regime":         regime,
            "source":         "fallback_static",
        }

# ── Get Confidence Floor ──────────────────────────────────────────
def get_confidence_floor(regime: str) -> float:
    try:
        weights = mem.load_weights()
        floors  = weights.get("confidence_floor", {})
        return floors.get(regime, 0.65)
    except Exception:
        return 0.65

# ── Get Sizing Modifier ───────────────────────────────────────────
def get_sizing_modifier(regime: str) -> float:
    try:
        weights = mem.load_weights()
        sizing  = weights.get("sizing_modifiers", {})
        return sizing.get(regime, 1.0)
    except Exception:
        return 1.0

# ── Rank Setups ───────────────────────────────────────────────────
def rank_setups(setups: list, regime: str) -> list:
    """Return setups sorted by adaptive performance"""
    try:
        stats = mem.get_setup_stats()
        ranked = []
        for setup in setups:
            s = stats.get(setup, {})
            total = s.get("total", 0)
            if total >= MIN_TRADES_FOR_ADAPTATION:
                wins = s.get("wins", 0)
                wr   = wins / total
                pnl  = s.get("total_pnl", 0) / total
                score = wr * 0.6 + (pnl / 5) * 0.4
            else:
                score = 0.5  # neutral for unknown setups
            ranked.append((setup, round(score, 4)))

        ranked.sort(key=lambda x: x[1], reverse=True)
        return [s[0] for s in ranked]

    except Exception:
        return setups

# ── Core Adaptation Logic ─────────────────────────────────────────
def _clamp(value: float, key: str) -> float:
    limits = mem.SAFETY_LIMITS
    if "setup_modifier" in key:
        return max(limits["setup_modifier_min"],
                   min(limits["setup_modifier_max"], value))
    if "regime_aggr" in key:
        return max(limits["regime_aggr_min"],
                   min(limits["regime_aggr_max"], value))
    if "sizing" in key:
        return max(limits["sizing_modifier_min"],
                   min(limits["sizing_modifier_max"], value))
    if "confidence" in key:
        return max(limits["confidence_floor_min"],
                   min(limits["confidence_floor_max"], value))
    return value

def _compute_setup_win_rate(setup: str, regime: Optional[str] = None) -> Optional[float]:
    stats = mem.get_setup_stats()
    s = stats.get(setup, {})

    if regime:
        by_regime = s.get("by_regime", {}).get(regime, {})
        wins   = by_regime.get("wins", 0)
        losses = by_regime.get("losses", 0)
        total  = wins + losses
    else:
        total = s.get("total", 0)
        wins  = s.get("wins", 0)

    if total < MIN_TRADES_FOR_ADAPTATION:
        return None
    return wins / total

def _compute_expectancy(setup: str) -> Optional[float]:
    stats = mem.get_setup_stats()
    s = stats.get(setup, {})
    total = s.get("total", 0)
    if total < MIN_TRADES_FOR_ADAPTATION:
        return None
    return s.get("total_pnl", 0) / total

# ── Main Adaptation Cycle (LEVEL 1) ──────────────────────────────
def run_adaptation_cycle(source: str = "scheduled") -> dict:
    """
    LEVEL 1 ONLY — Auto-adapt setup modifiers and regime weights.
    All changes within hard safety limits.
    """
    print(f"\n  [Adaptive Scoring] Running Level 1 adaptation cycle...")

    weights  = mem.load_weights()
    setup_mods  = weights.get("setup_modifiers", {})
    regime_aggr = weights.get("regime_aggressiveness", {})
    sizing_mods = weights.get("sizing_modifiers", {})
    conf_floors = weights.get("confidence_floor", {})

    changes_made = 0
    changes_log  = []

    # ── 1. Adapt Setup Modifiers ──────────────────────────────────
    for setup in list(setup_mods.keys()):
        wr  = _compute_setup_win_rate(setup)
        exp = _compute_expectancy(setup)

        if wr is None or exp is None:
            continue

        old_mod = setup_mods[setup]
        new_mod = old_mod

        if wr >= STRONG_PERFORMANCE_WR and exp >= STRONG_EXPECTANCY:
            new_mod = old_mod + ADAPTATION_STEP
            reason  = f"Strong performance WR={wr:.1%} Exp={exp:+.2f}%"
        elif wr <= WEAK_PERFORMANCE_WR or exp <= WEAK_EXPECTANCY:
            new_mod = old_mod - ADAPTATION_STEP
            reason  = f"Weak performance WR={wr:.1%} Exp={exp:+.2f}%"
        else:
            continue

        new_mod = _clamp(new_mod, "setup_modifier")

        if abs(new_mod - old_mod) > 0.001:
            setup_mods[setup] = round(new_mod, 4)
            mem.log_confidence_change(setup, old_mod, new_mod, reason)
            changes_log.append(f"{setup}: {old_mod:.3f} → {new_mod:.3f} ({reason})")
            changes_made += 1

    # ── 2. Adapt Regime Aggressiveness ────────────────────────────
    regime_perf = mem.get_regime_perf()
    for regime, data in regime_perf.items():
        total = data.get("total", 0)
        if total < MIN_TRADES_FOR_ADAPTATION:
            continue

        wr      = data.get("wins", 0) / total
        avg_pnl = data.get("total_pnl", 0) / total

        old_aggr = regime_aggr.get(regime, 1.0)
        new_aggr = old_aggr

        if wr >= STRONG_PERFORMANCE_WR and avg_pnl >= STRONG_EXPECTANCY:
            new_aggr = old_aggr + ADAPTATION_STEP * 0.5
            reason   = f"Regime {regime} strong WR={wr:.1%}"
        elif wr <= WEAK_PERFORMANCE_WR:
            new_aggr = old_aggr - ADAPTATION_STEP * 0.5
            reason   = f"Regime {regime} weak WR={wr:.1%}"
        else:
            continue

        new_aggr = _clamp(new_aggr, "regime_aggr")

        if abs(new_aggr - old_aggr) > 0.001:
            regime_aggr[regime] = round(new_aggr, 4)
            changes_log.append(f"Regime {regime}: {old_aggr:.3f} → {new_aggr:.3f}")
            changes_made += 1

    # ── 3. Save Updated Weights ───────────────────────────────────
    if changes_made > 0:
        weights["setup_modifiers"]        = setup_mods
        weights["regime_aggressiveness"]  = regime_aggr
        weights["version"]                = weights.get("version", 1) + 1
        mem.save_weights(weights)
        mem.log_change(
            "LEVEL1_AUTO",
            f"Auto-adapted {changes_made} weights",
            "adaptive_scoring",
            auto_applied=True,
            level=1,
            details={"changes": changes_log},
        )
        print(f"  ✔ {changes_made} Level 1 adaptations applied")
        for c in changes_log:
            print(f"    • {c}")
    else:
        print("  ✔ No adaptations needed this cycle")

    mem.log_learning_cycle(
        source        = source,
        trades_analyzed = sum(s.get("total", 0) for s in mem.get_setup_stats().values()),
        changes_made  = changes_made,
        summary       = f"Level 1 cycle: {changes_made} changes. " +
                       (", ".join(changes_log[:3]) if changes_log else "stable"),
    )

    return {
        "timestamp":     datetime.now().isoformat(),
        "changes_made":  changes_made,
        "changes":       changes_log,
        "weights_version": weights.get("version", 1),
    }

# ── Level 2 Suggestions (Human Approval Required) ────────────────
def generate_level2_suggestions() -> list:
    """
    Analyze data and generate SUGGESTIONS only.
    These require human approval before any application.
    """
    suggestions = []
    stats = mem.get_setup_stats()
    regime_perf = mem.get_regime_perf()

    # Threshold suggestions
    for regime, data in regime_perf.items():
        total = data.get("total", 0)
        if total < 20:
            continue
        wr = data.get("wins", 0) / total

        if regime == "RISK_ON" and wr > 0.65:
            suggestions.append({
                "type":        "THRESHOLD_SUGGESTION",
                "regime":      regime,
                "title":       f"Lower {regime} entry threshold",
                "description": f"Win rate {wr:.1%} suggests threshold could be reduced from 75 → 72",
                "proposed":    {"threshold": 72, "current": 75},
                "confidence":  round(wr, 2),
                "level":       2,
            })
        elif regime == "RISK_OFF" and wr < 0.35:
            suggestions.append({
                "type":        "THRESHOLD_SUGGESTION",
                "regime":      regime,
                "title":       f"Raise {regime} entry threshold",
                "description": f"Win rate {wr:.1%} suggests raise threshold from 92 → 95",
                "proposed":    {"threshold": 95, "current": 92},
                "confidence":  round(1 - wr, 2),
                "level":       2,
            })

    # Sizing suggestions
    for regime, data in regime_perf.items():
        total = data.get("total", 0)
        if total < 15:
            continue
        avg_pnl = data.get("total_pnl", 0) / total
        if avg_pnl > 1.5:
            suggestions.append({
                "type":        "SIZING_SUGGESTION",
                "regime":      regime,
                "title":       f"Increase position size in {regime}",
                "description": f"Avg PnL {avg_pnl:+.2f}% suggests slightly larger positions",
                "proposed":    {"sizing_modifier": 1.1},
                "level":       2,
            })

    # Register as pending approvals
    for s in suggestions:
        mem.add_pending_approval(
            title           = s["title"],
            description     = s["description"],
            proposed_change = s.get("proposed", {}),
            level           = s.get("level", 2),
        )

    return suggestions

# ── Current Weights Summary ───────────────────────────────────────
def get_scoring_summary() -> dict:
    weights = mem.load_weights()
    stats   = mem.get_setup_stats()

    # Find best/worst setups
    ranked = []
    for setup, data in stats.items():
        total = data.get("total", 0)
        if total >= 5:
            wr = data.get("wins", 0) / total
            ranked.append((setup, wr, total))
    ranked.sort(key=lambda x: x[1], reverse=True)

    return {
        "timestamp":        datetime.now().isoformat(),
        "weights_version":  weights.get("version", 1),
        "setup_modifiers":  weights.get("setup_modifiers", {}),
        "regime_aggr":      weights.get("regime_aggressiveness", {}),
        "sizing_modifiers": weights.get("sizing_modifiers", {}),
        "best_setups":      [(s[0], f"{s[1]:.1%}", s[2]) for s in ranked[:3]],
        "worst_setups":     [(s[0], f"{s[1]:.1%}", s[2]) for s in ranked[-3:]],
        "total_setups_tracked": len(stats),
        "pending_approvals": len(mem.get_pending_approvals()),
    }


if __name__ == "__main__":
    print("── Adaptive Scoring Engine ─────────────────────────")
    summary = get_scoring_summary()
    print(f"  Weights version: {summary['weights_version']}")
    print(f"  Setups tracked:  {summary['total_setups_tracked']}")
    print(f"  Pending approvals: {summary['pending_approvals']}")

    result = run_adaptation_cycle(source="manual_test")
    print(f"\n  Cycle result: {result['changes_made']} changes")
