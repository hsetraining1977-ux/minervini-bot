#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║   MINERVINI AI — INSTITUTIONAL REGIME CLASSIFIER                 ║
║   MASTER ENGINE: Combines breadth + sectors + vol + liquidity    ║
║   Generates final regime + setup suitability matrix              ║
║   ANALYTICS ONLY — NO LIVE TRADING MODIFICATION                  ║
╚══════════════════════════════════════════════════════════════════╝
"""

import json
import os
import time
import logging
from datetime import datetime
from typing import Optional

import numpy as np

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [RegimeClassifier] %(message)s")
log = logging.getLogger("institutional_regime")

# ── Config ────────────────────────────────────────────────────────
OUTPUT_PATH  = "/root/adaptive/institutional_regime.json"
HISTORY_PATH = "/root/adaptive/regime_history.json"
CACHE_TTL    = 300

os.makedirs("/root/adaptive", exist_ok=True)

SETUPS = [
    "ORB_BREAKOUT", "ORB_BREAKDOWN",
    "TIGHT_CONSOLIDATION_BREAK",
    "MOMENTUM_BURST_UP", "MOMENTUM_BURST_DOWN",
    "VWAP_CROSS_UP", "VWAP_CROSS_DOWN",
    "VOLUME_SPIKE", "RELATIVE_STRENGTH_LEADER",
]

REGIMES = [
    "STRONG_RISK_ON", "RISK_ON", "NEUTRAL",
    "CHOPPY", "RISK_OFF", "PANIC",
]


# ── Load Sub-Engine Data ──────────────────────────────────────────
def _load_json(path: str, max_age_sec: int = 900) -> Optional[dict]:
    try:
        if not os.path.exists(path):
            return None
        with open(path) as f:
            data = json.load(f)
        ts  = datetime.fromisoformat(data.get("timestamp", "2000-01-01"))
        age = (datetime.now() - ts).total_seconds()
        if age > max_age_sec:
            log.warning(f"  Stale data: {path} ({int(age)}s old)")
        return data
    except Exception as e:
        log.warning(f"  Load error {path}: {e}")
        return None


def _run_sub_engines(force: bool = False) -> dict:
    """Run all sub-engines if data is stale."""
    results = {}

    # Breadth
    try:
        from breadth_engine import get_breadth
        results["breadth"] = get_breadth(force=force)
        log.info("  ✓ Breadth loaded")
    except Exception as e:
        log.warning(f"  Breadth error: {e}")
        results["breadth"] = _load_json("/root/adaptive/breadth_metrics.json")

    # Sector Rotation
    try:
        from sector_rotation_engine import get_sector_rotation
        results["sector"] = get_sector_rotation(force=force)
        log.info("  ✓ Sector rotation loaded")
    except Exception as e:
        log.warning(f"  Sector error: {e}")
        results["sector"] = _load_json("/root/adaptive/sector_rotation.json")

    # Volatility
    try:
        from volatility_regime_engine import get_volatility_regime
        results["volatility"] = get_volatility_regime(force=force)
        log.info("  ✓ Volatility loaded")
    except Exception as e:
        log.warning(f"  Volatility error: {e}")
        results["volatility"] = _load_json("/root/adaptive/volatility_regime.json")

    # Liquidity
    try:
        from liquidity_engine import get_liquidity
        results["liquidity"] = get_liquidity(force=force)
        log.info("  ✓ Liquidity loaded")
    except Exception as e:
        log.warning(f"  Liquidity error: {e}")
        results["liquidity"] = _load_json("/root/adaptive/liquidity_state.json")

    return results


# ── SPY / QQQ Behavior ────────────────────────────────────────────
def _spy_qqq_signal() -> dict:
    try:
        import yfinance as yf
        result = {}
        for ticker in ["SPY", "QQQ"]:
            df = yf.Ticker(ticker).history(period="5d", interval="1d")
            if df.empty or len(df) < 2:
                continue
            chg_1d  = float((df["Close"].iloc[-1] / df["Close"].iloc[-2] - 1) * 100)
            chg_5d  = float((df["Close"].iloc[-1] / df["Close"].iloc[0]  - 1) * 100)
            result[ticker] = {"chg_1d": round(chg_1d, 2), "chg_5d": round(chg_5d, 2)}
            time.sleep(0.2)
        return result
    except Exception:
        return {}


# ── Regime Scoring ────────────────────────────────────────────────
def _compute_regime_scores(breadth: dict, sector: dict,
                            vol: dict, liq: dict, spy_qqq: dict) -> dict:
    scores = {r: 0.0 for r in REGIMES}

    # ── Breadth contribution ──────────────────────────────────────
    b_score = breadth.get("breadth_score", 50) if breadth else 50
    p_score = breadth.get("participation_score", 50) if breadth else 50
    t_score = breadth.get("trend_quality_score", 50) if breadth else 50

    if b_score >= 75 and p_score >= 70:
        scores["STRONG_RISK_ON"] += 30
        scores["RISK_ON"]        += 15
    elif b_score >= 55:
        scores["RISK_ON"]  += 25
        scores["NEUTRAL"]  += 10
    elif b_score >= 40:
        scores["NEUTRAL"]  += 20
        scores["CHOPPY"]   += 10
    elif b_score >= 25:
        scores["CHOPPY"]   += 20
        scores["RISK_OFF"] += 15
    else:
        scores["RISK_OFF"] += 25
        scores["PANIC"]    += 10

    # ── Sector contribution ───────────────────────────────────────
    if sector:
        rot_signal  = sector.get("rotation_signal", "NEUTRAL")
        tech_lead   = sector.get("tech_leadership", False)
        semi_lead   = sector.get("semi_leadership", False)
        def_rot     = sector.get("defensive_rotation", False)
        off_rot     = sector.get("offensive_rotation", False)

        if rot_signal == "RISK_ON_GROWTH" and tech_lead and semi_lead:
            scores["STRONG_RISK_ON"] += 25
            scores["RISK_ON"]        += 10
        elif rot_signal in ("RISK_ON_GROWTH", "TECH_LED_MOMENTUM"):
            scores["RISK_ON"]  += 20
        elif rot_signal == "RISK_ON_BROAD":
            scores["RISK_ON"]  += 15
            scores["NEUTRAL"]  += 5
        elif rot_signal == "RISK_OFF_ROTATION":
            scores["RISK_OFF"] += 20
            scores["CHOPPY"]   += 10
        elif def_rot:
            scores["RISK_OFF"] += 15
            scores["NEUTRAL"]  += 5

    # ── Volatility contribution ───────────────────────────────────
    if vol:
        v_regime = vol.get("volatility_regime", "NORMAL_VOL")
        vix      = vol.get("vix_current", 20)

        if v_regime == "LOW_VOL":
            scores["STRONG_RISK_ON"] += 15
            scores["RISK_ON"]        += 10
        elif v_regime == "NORMAL_VOL":
            scores["RISK_ON"]  += 10
            scores["NEUTRAL"]  += 5
        elif v_regime == "HIGH_VOL":
            scores["CHOPPY"]   += 15
            scores["RISK_OFF"] += 10
        elif v_regime == "EXTREME_VOL":
            scores["PANIC"]    += 30
            scores["RISK_OFF"] += 15

        if vix and vix > 30:
            scores["PANIC"]    += 15
            scores["RISK_OFF"] += 5
        elif vix and vix < 15:
            scores["STRONG_RISK_ON"] += 10

    # ── Liquidity contribution ────────────────────────────────────
    if liq:
        l_state = liq.get("liquidity_state", "NORMAL")
        panic   = liq.get("panic_signal", False)
        inst    = liq.get("institutional_signal", False)

        if inst:
            scores["STRONG_RISK_ON"] += 10
            scores["RISK_ON"]        += 5
        elif l_state == "THIN":
            scores["CHOPPY"]   += 10
            scores["NEUTRAL"]  += 5
        if panic:
            scores["PANIC"]    += 20

    # ── SPY/QQQ behavior ─────────────────────────────────────────
    spy_data = spy_qqq.get("SPY", {})
    qqq_data = spy_qqq.get("QQQ", {})
    spy_1d   = spy_data.get("chg_1d", 0)
    qqq_5d   = qqq_data.get("chg_5d", 0)

    if spy_1d > 1.0 and qqq_5d > 3.0:
        scores["STRONG_RISK_ON"] += 10
    elif spy_1d > 0.3:
        scores["RISK_ON"]  += 5
    elif spy_1d < -1.0:
        scores["RISK_OFF"] += 10
    elif spy_1d < -2.0:
        scores["PANIC"]    += 15

    return scores


# ── Final Regime Classification ───────────────────────────────────
def _final_regime(scores: dict) -> tuple:
    best  = max(scores, key=scores.get)
    total = sum(scores.values())
    conf  = round(scores[best] / max(total, 1), 2)
    return best, conf


# ── Setup Suitability Matrix ──────────────────────────────────────
def _build_suitability_matrix(regime: str, breadth: dict,
                               vol: dict, liq: dict) -> dict:
    """
    Score each setup 0-100 for current conditions.
    Based on historical regime performance + current context.
    """
    base_scores = {
        "STRONG_RISK_ON": {
            "ORB_BREAKOUT":              85,
            "TIGHT_CONSOLIDATION_BREAK": 90,
            "MOMENTUM_BURST_UP":         85,
            "RELATIVE_STRENGTH_LEADER":  80,
            "VWAP_CROSS_UP":             75,
            "VOLUME_SPIKE":              70,
            "VWAP_CROSS_DOWN":           30,
            "ORB_BREAKDOWN":             25,
            "MOMENTUM_BURST_DOWN":       20,
        },
        "RISK_ON": {
            "ORB_BREAKOUT":              75,
            "TIGHT_CONSOLIDATION_BREAK": 80,
            "MOMENTUM_BURST_UP":         70,
            "VWAP_CROSS_UP":             70,
            "VOLUME_SPIKE":              65,
            "RELATIVE_STRENGTH_LEADER":  65,
            "VWAP_CROSS_DOWN":           40,
            "ORB_BREAKDOWN":             35,
            "MOMENTUM_BURST_DOWN":       30,
        },
        "NEUTRAL": {
            "ORB_BREAKOUT":              55,
            "TIGHT_CONSOLIDATION_BREAK": 60,
            "VWAP_CROSS_UP":             55,
            "VWAP_CROSS_DOWN":           55,
            "MOMENTUM_BURST_UP":         50,
            "MOMENTUM_BURST_DOWN":       50,
            "VOLUME_SPIKE":              50,
            "ORB_BREAKDOWN":             50,
            "RELATIVE_STRENGTH_LEADER":  50,
        },
        "CHOPPY": {
            "TIGHT_CONSOLIDATION_BREAK": 45,
            "VWAP_CROSS_UP":             40,
            "VWAP_CROSS_DOWN":           40,
            "ORB_BREAKOUT":              35,
            "ORB_BREAKDOWN":             35,
            "MOMENTUM_BURST_UP":         30,
            "MOMENTUM_BURST_DOWN":       30,
            "VOLUME_SPIKE":              40,
            "RELATIVE_STRENGTH_LEADER":  35,
        },
        "RISK_OFF": {
            "ORB_BREAKDOWN":             70,
            "MOMENTUM_BURST_DOWN":       65,
            "VWAP_CROSS_DOWN":           65,
            "VOLUME_SPIKE":              55,
            "TIGHT_CONSOLIDATION_BREAK": 35,
            "ORB_BREAKOUT":              30,
            "VWAP_CROSS_UP":             30,
            "MOMENTUM_BURST_UP":         25,
            "RELATIVE_STRENGTH_LEADER":  20,
        },
        "PANIC": {
            "MOMENTUM_BURST_DOWN":       80,
            "ORB_BREAKDOWN":             75,
            "VWAP_CROSS_DOWN":           70,
            "VOLUME_SPIKE":              60,
            "ORB_BREAKOUT":              20,
            "TIGHT_CONSOLIDATION_BREAK": 15,
            "MOMENTUM_BURST_UP":         15,
            "VWAP_CROSS_UP":             15,
            "RELATIVE_STRENGTH_LEADER":  10,
        },
    }

    scores = base_scores.get(regime, base_scores["NEUTRAL"]).copy()

    # ── Contextual Adjustments ────────────────────────────────────
    breadth_score = (breadth or {}).get("breadth_score", 50)
    vol_regime    = (vol     or {}).get("volatility_regime", "NORMAL_VOL")
    liq_state     = (liq     or {}).get("liquidity_state", "NORMAL")

    for setup in scores:
        adj = 0

        # Breadth adjustment
        if "UP" in setup or "BREAKOUT" in setup or "LEADER" in setup:
            if breadth_score > 70: adj += 5
            elif breadth_score < 30: adj -= 10

        # Vol adjustment
        if vol_regime == "HIGH_VOL":
            if "BURST" in setup: adj += 5
            if "ORB"   in setup: adj += 3
        elif vol_regime == "LOW_VOL":
            if "CONSOLIDATION" in setup: adj += 5
            if "BURST" in setup: adj -= 5

        # Liquidity adjustment
        if liq_state == "INSTITUTIONAL":
            if setup in ("ORB_BREAKOUT", "MOMENTUM_BURST_UP"): adj += 5
        elif liq_state == "THIN":
            adj -= 5

        scores[setup] = max(0, min(100, scores[setup] + adj))

    # ── Build final matrix ────────────────────────────────────────
    matrix = {}
    for setup, score in scores.items():
        if score >= 70:    rating = "HIGHLY_FAVORABLE"
        elif score >= 55:  rating = "FAVORABLE"
        elif score >= 40:  rating = "NEUTRAL"
        elif score >= 25:  rating = "REDUCED"
        else:              rating = "AVOID"

        matrix[setup] = {
            "score":  score,
            "rating": rating,
        }

    return matrix


# ── Institutional Participation Score ─────────────────────────────
def _institutional_participation(breadth: dict, liq: dict,
                                  sector: dict) -> float:
    score = 50.0
    if breadth:
        score += (breadth.get("breadth_score", 50) - 50) * 0.3
        score += (breadth.get("participation_score", 50) - 50) * 0.2
    if liq:
        if liq.get("institutional_signal"): score += 10
        score += (liq.get("etf_participation", 50) - 50) * 0.2
    if sector and sector.get("rotation_velocity") == "FAST":
        score += 5
    return round(max(0, min(100, score)), 1)


# ── AI Narrative Generator ────────────────────────────────────────
def _generate_narrative(regime: str, confidence: float, breadth: dict,
                         sector: dict, vol: dict, liq: dict,
                         suitability: dict) -> str:
    lines = []

    regime_desc = {
        "STRONG_RISK_ON": "broadly bullish with strong institutional participation",
        "RISK_ON":        "constructive with moderate institutional support",
        "NEUTRAL":        "mixed with no clear directional bias",
        "CHOPPY":         "choppy with inconsistent institutional behavior",
        "RISK_OFF":       "defensive with institutional risk reduction",
        "PANIC":          "in panic mode with aggressive institutional selling",
    }
    lines.append(
        f"Market is {regime_desc.get(regime, 'unclear')} "
        f"(confidence: {confidence:.0%})."
    )

    # Breadth commentary
    if breadth:
        bs = breadth.get("breadth_score", 50)
        ps = breadth.get("participation_score", 50)
        if bs >= 70:
            lines.append(
                f"Breadth is strong at {bs:.0f}/100 with broad participation "
                f"({ps:.0f}/100), confirming institutional conviction."
            )
        elif bs <= 35:
            lines.append(
                f"Breadth is deteriorating at {bs:.0f}/100 despite index levels, "
                f"indicating narrow participation ({ps:.0f}/100)."
            )

    # Sector commentary
    if sector:
        leaders = sector.get("leading_sectors", [])
        tech    = sector.get("tech_leadership", False)
        defense = sector.get("defensive_rotation", False)
        if tech:
            lines.append(
                "Technology and semiconductors are leading, "
                "a hallmark of institutional risk appetite."
            )
        elif defense:
            lines.append(
                f"Defensive rotation detected — institutional money "
                f"moving to safety in {leaders}."
            )
        elif leaders:
            lines.append(
                f"Sector leadership concentrated in {leaders[:2]}, "
                f"suggesting selective institutional participation."
            )

    # Volatility commentary
    if vol:
        vr  = vol.get("volatility_regime", "NORMAL_VOL")
        vix = vol.get("vix_current")
        if vr == "EXTREME_VOL":
            lines.append(
                f"VIX at {vix:.1f} signals extreme volatility — "
                f"breakout setups carry significant whipsaw risk."
            )
        elif vr == "LOW_VOL":
            lines.append(
                f"VIX at {vix:.1f} indicates compressed volatility — "
                f"consolidation setups favored over momentum plays."
            )

    # Best setups
    best = [(k, v["score"]) for k, v in suitability.items()
            if v["rating"] in ("HIGHLY_FAVORABLE", "FAVORABLE")]
    best.sort(key=lambda x: x[1], reverse=True)
    avoid = [k for k, v in suitability.items() if v["rating"] == "AVOID"]

    if best:
        top_setups = ", ".join([s for s, _ in best[:3]])
        lines.append(f"Best setups for current conditions: {top_setups}.")
    if avoid:
        lines.append(f"Setups to avoid: {', '.join(avoid[:3])}.")

    return " ".join(lines)


# ── Main Computation ──────────────────────────────────────────────
def compute_institutional_regime(force: bool = False) -> dict:
    log.info("Computing institutional regime...")

    result = {
        "timestamp":                 datetime.now().isoformat(),
        "regime":                    "NEUTRAL",
        "regime_confidence":         0.5,
        "regime_scores":             {},
        "institutional_participation":50.0,
        "setup_suitability":         {},
        "breadth_summary":           {},
        "sector_summary":            {},
        "volatility_summary":        {},
        "liquidity_summary":         {},
        "spy_qqq":                   {},
        "ai_narrative":              "",
        "best_setups":               [],
        "setups_to_avoid":           [],
        "data_sources_available":    0,
        "data_quality":              "partial",
    }

    # ── Load sub-engine data ───────────────────────────────────────
    log.info("Loading sub-engines...")
    sub = _run_sub_engines(force=force)

    breadth = sub.get("breadth")
    sector  = sub.get("sector")
    vol     = sub.get("volatility")
    liq     = sub.get("liquidity")

    available = sum(1 for x in [breadth, sector, vol, liq] if x is not None)
    result["data_sources_available"] = available

    # ── SPY/QQQ ────────────────────────────────────────────────────
    spy_qqq = _spy_qqq_signal()
    result["spy_qqq"] = spy_qqq

    # ── Regime Scoring ─────────────────────────────────────────────
    scores = _compute_regime_scores(
        breadth or {}, sector or {}, vol or {}, liq or {}, spy_qqq
    )
    result["regime_scores"] = {k: round(v, 1) for k, v in scores.items()}

    regime, confidence = _final_regime(scores)
    result["regime"]            = regime
    result["regime_confidence"] = confidence

    log.info(f"Regime: {regime} ({confidence:.0%})")

    # ── Summaries ──────────────────────────────────────────────────
    if breadth:
        result["breadth_summary"] = {
            "breadth_score":       breadth.get("breadth_score"),
            "participation_score": breadth.get("participation_score"),
            "trend_quality":       breadth.get("trend_quality_score"),
            "momentum":            breadth.get("breadth_momentum"),
        }
    if sector:
        result["sector_summary"] = {
            "rotation_signal":  sector.get("rotation_signal"),
            "market_character": sector.get("market_character"),
            "tech_leadership":  sector.get("tech_leadership"),
            "leading_sectors":  sector.get("leading_sectors", []),
        }
    if vol:
        result["volatility_summary"] = {
            "regime":           vol.get("volatility_regime"),
            "vix":              vol.get("vix_current"),
            "score":            vol.get("volatility_score"),
            "trend_day_prob":   vol.get("trend_day_probability"),
        }
    if liq:
        result["liquidity_summary"] = {
            "state":            liq.get("liquidity_state"),
            "rvol_spy":         liq.get("relative_volume_spy"),
            "institutional":    liq.get("institutional_signal"),
            "etf_participation":liq.get("etf_participation"),
        }

    # ── Suitability Matrix ─────────────────────────────────────────
    suitability = _build_suitability_matrix(regime, breadth, vol, liq)
    result["setup_suitability"] = suitability

    # ── Best / Avoid Lists ─────────────────────────────────────────
    result["best_setups"] = sorted(
        [k for k, v in suitability.items()
         if v["rating"] in ("HIGHLY_FAVORABLE", "FAVORABLE")],
        key=lambda k: suitability[k]["score"], reverse=True
    )
    result["setups_to_avoid"] = [
        k for k, v in suitability.items() if v["rating"] == "AVOID"
    ]

    # ── Institutional Participation ────────────────────────────────
    result["institutional_participation"] = _institutional_participation(
        breadth, liq, sector
    )

    # ── AI Narrative ───────────────────────────────────────────────
    result["ai_narrative"] = _generate_narrative(
        regime, confidence, breadth, sector, vol, liq, suitability
    )

    # ── Data Quality ───────────────────────────────────────────────
    result["data_quality"] = "good" if available >= 3 else "partial"

    # ── Update Adaptive Memory ────────────────────────────────────
    _update_adaptive_memory(regime, confidence, suitability)

    # ── Save History ───────────────────────────────────────────────
    _save_history(regime, confidence, result)

    log.info(f"Best setups: {result['best_setups'][:3]}")
    log.info(f"Narrative: {result['ai_narrative'][:100]}...")

    _save(result)
    return result


def _update_adaptive_memory(regime: str, confidence: float, suitability: dict):
    """Feed regime data back into adaptive memory for learning."""
    try:
        import adaptive_memory as amem
        weights = amem.load_weights()
        changed = 0

        # Adjust setup modifiers based on suitability
        for setup, data in suitability.items():
            if setup not in weights.get("setup_modifiers", {}):
                continue
            score = data["score"]
            current_mod = weights["setup_modifiers"][setup]

            # Small nudge based on regime suitability
            if score >= 70 and current_mod < 1.10:
                new_mod = min(current_mod + 0.01, 1.20)
                weights["setup_modifiers"][setup] = round(new_mod, 3)
                changed += 1
            elif score <= 30 and current_mod > 0.90:
                new_mod = max(current_mod - 0.01, 0.80)
                weights["setup_modifiers"][setup] = round(new_mod, 3)
                changed += 1

        if changed > 0:
            weights["version"] = weights.get("version", 1) + 1
            amem.save_weights(weights)
            amem.log_change(
                change_type  = "REGIME_ADAPTATION",
                description  = f"Regime {regime} ({confidence:.0%}) → adjusted {changed} setup modifiers",
                component    = "institutional_regime_classifier",
                auto_applied = True,
                level        = 1,
            )
            log.info(f"  Updated {changed} adaptive weights for regime {regime}")
    except Exception as e:
        log.warning(f"  Adaptive memory update failed: {e}")


def _save_history(regime: str, confidence: float, full_data: dict):
    try:
        history = []
        if os.path.exists(HISTORY_PATH):
            with open(HISTORY_PATH) as f:
                history = json.load(f)
            if not isinstance(history, list):
                history = []

        history.append({
            "timestamp":  datetime.now().isoformat(),
            "regime":     regime,
            "confidence": confidence,
            "best_setups":full_data.get("best_setups", [])[:3],
            "vix":        full_data.get("volatility_summary", {}).get("vix"),
            "breadth":    full_data.get("breadth_summary", {}).get("breadth_score"),
        })

        if len(history) > 500:
            history = history[-500:]

        with open(HISTORY_PATH, "w") as f:
            json.dump(history, f, indent=2, default=str)
    except Exception as e:
        log.warning(f"  History save error: {e}")


# ── Cache-Aware Runner ────────────────────────────────────────────
def get_institutional_regime(force: bool = False) -> dict:
    if not force and os.path.exists(OUTPUT_PATH):
        try:
            with open(OUTPUT_PATH) as f:
                cached = json.load(f)
            ts  = datetime.fromisoformat(cached.get("timestamp", "2000-01-01"))
            age = (datetime.now() - ts).total_seconds()
            if age < CACHE_TTL:
                return cached
        except Exception:
            pass
    return compute_institutional_regime(force=force)


def _save(data: dict):
    try:
        with open(OUTPUT_PATH, "w") as f:
            json.dump(data, f, indent=2, default=str)
        log.info(f"Saved → {OUTPUT_PATH}")
    except Exception as e:
        log.error(f"Save error: {e}")


# ── Background Daemon ─────────────────────────────────────────────
def run_daemon(interval_minutes: int = 10):
    """Run regime classification in background every N minutes."""
    import time as time_module
    log.info(f"Starting regime daemon (interval: {interval_minutes}min)")
    while True:
        try:
            compute_institutional_regime(force=True)
        except Exception as e:
            log.error(f"Daemon cycle error: {e}")
        time_module.sleep(interval_minutes * 60)


# ── Standalone ────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    daemon_mode = "--daemon" in sys.argv

    if daemon_mode:
        run_daemon(interval_minutes=10)
    else:
        print("── Institutional Regime Classifier ─────────────────")
        data = compute_institutional_regime(force=True)
        print(f"\n  REGIME:              {data['regime']}")
        print(f"  Confidence:          {data['regime_confidence']:.0%}")
        print(f"  Institutional Part:  {data['institutional_participation']}")
        print(f"\n  Regime Scores:")
        for r, s in sorted(data['regime_scores'].items(), key=lambda x: x[1], reverse=True):
            print(f"    {r:<20} {s:.1f}")
        print(f"\n  Best Setups:   {data['best_setups'][:4]}")
        print(f"  Avoid Setups:  {data['setups_to_avoid']}")
        print(f"\n  Breadth:   {data['breadth_summary']}")
        print(f"  Sector:    {data['sector_summary']}")
        print(f"  Vol:       {data['volatility_summary']}")
        print(f"  Liquidity: {data['liquidity_summary']}")
        print(f"\n  AI Narrative:")
        print(f"  {data['ai_narrative']}")
        print("\n  ✔ Done")
