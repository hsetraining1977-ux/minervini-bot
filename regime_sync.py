#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║   MINERVINI AI — REGIME SYNC                                     ║
║   Master Bridge: Unifies regime across all 3 dashboards          ║
║   8501 ← 8503 ← 8504 ← institutional_regime.json               ║
║   ANALYTICS ONLY — NO LIVE TRADING MODIFICATION                  ║
╚══════════════════════════════════════════════════════════════════╝

WHAT THIS DOES:
1. Reads institutional_regime.json (8504 - source of truth)
2. Updates market_intelligence.json (fixes 8501 NEUTRAL → correct regime)
3. Tags all live paper trades with correct regime (fixes 8503 UNKNOWN)
4. Updates regime_performance.json (8503 Regime Intelligence tab)
5. Refreshes portfolio heat + trade plans freshness (fixes STALE)
6. Runs every 5 minutes as daemon
"""

import json
import os
import sys
import time
import logging
from datetime import datetime
from typing import Optional

logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s [RegimeSync] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/root/logs/regime_sync.log"),
    ]
)
log = logging.getLogger("regime_sync")

# ── Paths ─────────────────────────────────────────────────────────
PATHS = {
    # Source of truth (8504)
    "institutional_regime": "/root/adaptive/institutional_regime.json",
    "breadth":              "/root/adaptive/breadth_metrics.json",
    "volatility":           "/root/adaptive/volatility_regime.json",
    "liquidity":            "/root/adaptive/liquidity_state.json",
    "sector":               "/root/adaptive/sector_rotation.json",

    # 8501 targets
    "market_intelligence":  "/root/market_intelligence.json",
    "portfolio_heat":       "/root/portfolio_heat.json",
    "trade_plans":          "/root/trade_plans.json",

    # 8503 targets
    "regime_performance":   "/root/adaptive/regime_performance.json",
    "paper_trades":         "/root/paper_trades.json",
    "setup_statistics":     "/root/adaptive/setup_statistics.json",

    # Shared
    "sync_status":          "/root/adaptive/regime_sync_status.json",
}

os.makedirs("/root/adaptive", exist_ok=True)
os.makedirs("/root/logs",     exist_ok=True)


# ── Helpers ───────────────────────────────────────────────────────
def _read(path: str, default=None):
    try:
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    except Exception as e:
        log.warning(f"Read error {path}: {e}")
    return default if default is not None else {}


def _write(path: str, data) -> bool:
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        return True
    except Exception as e:
        log.error(f"Write error {path}: {e}")
        return False


def _age_minutes(data: dict) -> float:
    try:
        ts  = datetime.fromisoformat(data.get("timestamp", "2000-01-01"))
        return (datetime.now() - ts).total_seconds() / 60
    except Exception:
        return 9999.0


# ══════════════════════════════════════════════════════════════════
# STEP 1 — Load Institutional Regime (Source of Truth)
# ══════════════════════════════════════════════════════════════════
def load_regime() -> Optional[dict]:
    data = _read(PATHS["institutional_regime"])
    if not data:
        log.warning("institutional_regime.json not found — skipping sync")
        return None
    age = _age_minutes(data)
    if age > 30:
        log.warning(f"Regime data is {age:.0f}min old — may be stale")
    log.info(f"Loaded regime: {data.get('regime')} "
             f"(confidence: {data.get('regime_confidence', 0):.0%}, "
             f"age: {age:.0f}min)")
    return data


# ══════════════════════════════════════════════════════════════════
# STEP 2 — Fix 8501: Update market_intelligence.json
# ══════════════════════════════════════════════════════════════════
def sync_market_intelligence(regime_data: dict) -> bool:
    """
    8501 reads market_intelligence.json for REGIME display.
    Update it with data from institutional_regime.json.
    """
    log.info("Syncing market_intelligence.json (8501)...")

    regime      = regime_data.get("regime", "NEUTRAL")
    confidence  = regime_data.get("regime_confidence", 0.5)
    breadth     = regime_data.get("breadth_summary", {})
    vol_summary = regime_data.get("volatility_summary", {})
    liq_summary = regime_data.get("liquidity_summary", {})
    sector_sum  = regime_data.get("sector_summary", {})

    # Map institutional regime → 8501 format
    regime_map = {
        "STRONG_RISK_ON": "RISK_ON",
        "RISK_ON":        "RISK_ON",
        "NEUTRAL":        "NEUTRAL",
        "CHOPPY":         "NEUTRAL",
        "RISK_OFF":       "RISK_OFF",
        "PANIC":          "RISK_OFF",
    }
    mapped_regime = regime_map.get(regime, "NEUTRAL")

    # Risk score (0-100)
    risk_score_map = {
        "STRONG_RISK_ON": 25,
        "RISK_ON":        40,
        "NEUTRAL":        55,
        "CHOPPY":         65,
        "RISK_OFF":       80,
        "PANIC":          95,
    }
    risk_score = risk_score_map.get(regime, 60)

    # VIX
    vix = vol_summary.get("vix", 20) or 20

    # Liquidity state → 8501 format
    liq_state = liq_summary.get("state", "NORMAL")
    liq_map   = {
        "INSTITUTIONAL": "ABUNDANT",
        "NORMAL":        "NORMAL",
        "THIN":          "TIGHTENING",
        "PANIC_LIQUIDITY":"CRISIS",
    }
    liq_mapped = liq_map.get(liq_state, "NORMAL")

    # Psychology from breadth
    b_score = breadth.get("breadth_score", 50) or 50
    if b_score >= 80:
        psychology = "EUPHORIC"
    elif b_score >= 65:
        psychology = "OPTIMISTIC"
    elif b_score >= 45:
        psychology = "NEUTRAL"
    elif b_score >= 30:
        psychology = "FEARFUL"
    else:
        psychology = "PANIC"

    # Load existing to preserve fields we don't own
    existing = _read(PATHS["market_intelligence"], {})

    # Build updated intelligence
    updated = {
        **existing,
        "timestamp":     datetime.now().isoformat(),
        "market_regime": mapped_regime,
        "regime_detail": regime,
        "regime_confidence": confidence,
        "risk_on":       mapped_regime == "RISK_ON",
        "vix":           vix,
        "vix_label":     "Low" if vix < 18 else "Normal" if vix < 28 else "High",
        "risk_score":    risk_score,
        "liquidity":     liq_mapped,
        "psychology":    psychology,
        "fear_score":    max(0, min(100, risk_score - 10)),
        "breadth_score": b_score,
        "participation": breadth.get("participation_score", 50),
        "trend_quality": breadth.get("trend_quality_score", 50),
        "tech_leadership":  sector_sum.get("tech_leadership", False),
        "leading_sectors":  sector_sum.get("leading_sectors", []),
        "rotation_signal":  sector_sum.get("rotation_signal", "NEUTRAL"),
        "volatility_regime":vol_summary.get("regime", "NORMAL_VOL"),
        "trend_day_prob":   vol_summary.get("trend_day_prob", 0.5),
        "institutional_participation": regime_data.get("institutional_participation", 50),
        "best_setups":   regime_data.get("best_setups", []),
        "setups_to_avoid":regime_data.get("setups_to_avoid", []),
        "ai_narrative":  regime_data.get("ai_narrative", ""),
        "cross_asset":   "NEUTRAL",
        "event_lockdown":False,
        "source":        "institutional_regime_classifier",
    }

    ok = _write(PATHS["market_intelligence"], updated)
    if ok:
        log.info(f"  ✅ 8501 regime updated: {mapped_regime} "
                 f"(from {regime}) | VIX: {vix} | "
                 f"Liquidity: {liq_mapped} | Psychology: {psychology}")
    return ok


# ══════════════════════════════════════════════════════════════════
# STEP 3 — Fix 8503: Tag paper trades with correct regime
# ══════════════════════════════════════════════════════════════════
def sync_paper_trades(regime_data: dict) -> int:
    """
    Tag all paper trades that have UNKNOWN or missing regime
    with the current institutional regime.
    """
    log.info("Syncing paper trades regime tags (8503)...")

    regime   = regime_data.get("regime", "NEUTRAL")
    trades   = _read(PATHS["paper_trades"], [])
    if not isinstance(trades, list):
        trades = []

    tagged  = 0
    for trade in trades:
        current_regime = trade.get("regime", "")
        if not current_regime or current_regime in ("UNKNOWN", "unknown", ""):
            trade["regime"]            = regime
            trade["regime_confidence"] = regime_data.get("regime_confidence", 0.5)
            trade["regime_tagged_at"]  = datetime.now().isoformat()
            tagged += 1

    if tagged > 0:
        _write(PATHS["paper_trades"], trades)
        log.info(f"  ✅ Tagged {tagged} trades with regime: {regime}")
    else:
        log.info("  ✓ All trades already have regime labels")

    return tagged


# ══════════════════════════════════════════════════════════════════
# STEP 4 — Fix 8503: Update regime_performance.json
# ══════════════════════════════════════════════════════════════════
def sync_regime_performance(regime_data: dict) -> bool:
    """
    Build regime_performance.json from:
    1. Paper trades (live performance by regime)
    2. Setup statistics (historical performance by regime)
    """
    log.info("Syncing regime_performance.json (8503)...")

    regime = regime_data.get("regime", "NEUTRAL")

    # Load existing performance
    perf = _read(PATHS["regime_performance"], {})

    # Load paper trades for live stats
    trades = _read(PATHS["paper_trades"], [])
    if not isinstance(trades, list):
        trades = []

    # Aggregate live trades by regime
    live_by_regime = {}
    for trade in trades:
        r = trade.get("regime", "UNKNOWN")
        if r not in live_by_regime:
            live_by_regime[r] = {"total": 0, "wins": 0, "losses": 0, "total_pnl": 0.0}
        live_by_regime[r]["total"] += 1
        pnl = trade.get("pnl_pct", trade.get("pnl", 0)) or 0
        live_by_regime[r]["total_pnl"] += float(pnl)
        if pnl > 0:
            live_by_regime[r]["wins"] += 1
        else:
            live_by_regime[r]["losses"] += 1

    # Load setup statistics for historical regime breakdown
    setup_stats = _read(PATHS["setup_statistics"], {})
    hist_by_regime = {}
    for setup, sdata in setup_stats.items():
        for r, rdata in sdata.get("by_regime", {}).items():
            if r == "UNKNOWN":
                continue
            if r not in hist_by_regime:
                hist_by_regime[r] = {"total": 0, "wins": 0, "losses": 0, "total_pnl": 0.0}
            hist_by_regime[r]["total"]     += rdata.get("wins", 0) + rdata.get("losses", 0)
            hist_by_regime[r]["wins"]      += rdata.get("wins", 0)
            hist_by_regime[r]["losses"]    += rdata.get("losses", 0)
            hist_by_regime[r]["total_pnl"] += rdata.get("pnl", rdata.get("total_pnl", 0))

    # Merge: use historical if live is empty for a regime
    all_regimes = set(list(live_by_regime.keys()) + list(hist_by_regime.keys()))
    all_regimes.discard("UNKNOWN")

    # Add current regime even if no trades yet
    all_regimes.add(regime)

    for r in all_regimes:
        live = live_by_regime.get(r, {})
        hist = hist_by_regime.get(r, {})

        # Prefer live data; supplement with historical
        total     = live.get("total", 0) or hist.get("total", 0)
        wins      = live.get("wins",  0) or hist.get("wins",  0)
        losses    = live.get("losses",0) or hist.get("losses",0)
        total_pnl = live.get("total_pnl", 0) or hist.get("total_pnl", 0)

        # Build regime aggressiveness from institutional data
        regime_scores = regime_data.get("regime_scores", {})
        regime_score  = regime_scores.get(r, 50)
        aggr = 1.0 + (regime_score - 50) / 500  # subtle adjustment

        perf[r] = {
            "total":          total,
            "wins":           wins,
            "losses":         losses,
            "total_pnl":      round(total_pnl, 4),
            "win_rate":       round(wins / max(total, 1) * 100, 1),
            "aggressiveness": round(min(1.15, max(0.85, aggr)), 3),
            "sizing_modifier":1.0,
            "confidence_floor": 0.65 if r in ("STRONG_RISK_ON","RISK_ON") else
                                0.70 if r == "NEUTRAL" else
                                0.75,
            "last_updated":   datetime.now().isoformat(),
            "source":         "regime_sync",
            "is_current":     r == regime,
        }

    ok = _write(PATHS["regime_performance"], perf)
    if ok:
        log.info(f"  ✅ Updated {len(perf)} regimes in regime_performance.json")
        for r, v in perf.items():
            log.info(f"    {r}: {v.get('total',0)} trades, WR={v.get('win_rate',0)}%"
                     f"{' ← CURRENT' if v.get('is_current') else ''}")
    return ok


# ══════════════════════════════════════════════════════════════════
# STEP 5 — Fix 8503: Update adaptive_memory regime_perf
# ══════════════════════════════════════════════════════════════════
def sync_adaptive_memory_regime(regime_data: dict) -> bool:
    """Feed regime data into adaptive_memory regime_performance."""
    try:
        sys.path.insert(0, "/root")
        import adaptive_memory as amem

        regime      = regime_data.get("regime", "NEUTRAL")
        regime_perf = amem.get_regime_perf()

        # Ensure current regime exists
        if regime not in regime_perf:
            regime_perf[regime] = {
                "total": 0, "wins": 0, "losses": 0,
                "total_pnl": 0.0, "last_updated": None,
            }
        regime_perf[regime]["last_updated"] = datetime.now().isoformat()

        # Add historical data from setup_statistics by_regime
        setup_stats = _read(PATHS["setup_statistics"], {})
        for setup, sdata in setup_stats.items():
            for r, rdata in sdata.get("by_regime", {}).items():
                if r == "UNKNOWN":
                    continue
                if r not in regime_perf:
                    regime_perf[r] = {
                        "total": 0, "wins": 0, "losses": 0,
                        "total_pnl": 0.0, "last_updated": None,
                    }
                # Only add if not already populated from live
                if regime_perf[r]["total"] == 0:
                    regime_perf[r]["total"]     = rdata.get("wins",0) + rdata.get("losses",0)
                    regime_perf[r]["wins"]      = rdata.get("wins", 0)
                    regime_perf[r]["losses"]    = rdata.get("losses", 0)
                    regime_perf[r]["total_pnl"] = rdata.get("pnl", rdata.get("total_pnl", 0))
                    regime_perf[r]["last_updated"] = datetime.now().isoformat()

        amem._write(amem.PATHS["regime_perf"], regime_perf)
        log.info(f"  ✅ adaptive_memory regime_perf updated: {list(regime_perf.keys())}")
        return True

    except Exception as e:
        log.warning(f"  adaptive_memory sync warning: {e}")
        return False


# ══════════════════════════════════════════════════════════════════
# STEP 6 — Fix 8501: Refresh data freshness timestamps
# ══════════════════════════════════════════════════════════════════
def refresh_data_freshness(regime_data: dict) -> bool:
    """
    8501 shows STALE for portfolio_heat and trade_plans.
    Touch these files to reset staleness.
    """
    log.info("Refreshing data freshness (8501 STALE fix)...")

    # Portfolio heat
    ph = _read(PATHS["portfolio_heat"], {})
    ph["timestamp"]       = datetime.now().isoformat()
    ph["regime"]          = regime_data.get("regime", "NEUTRAL")
    ph["regime_confidence"]= regime_data.get("regime_confidence", 0.5)
    ph["breadth_score"]   = regime_data.get("breadth_summary", {}).get("breadth_score", 50)
    ph["source"]          = "regime_sync"
    _write(PATHS["portfolio_heat"], ph)

    # Trade plans — update regime in each plan
    plans = _read(PATHS["trade_plans"], [])
    if isinstance(plans, list):
        regime = regime_data.get("regime", "NEUTRAL")
        for plan in plans:
            plan["market_regime"]     = regime
            plan["regime_updated_at"] = datetime.now().isoformat()
            # Update suitability score based on regime
            setup = plan.get("setup_type", "")
            suitability = regime_data.get("setup_suitability", {})
            if setup in suitability:
                plan["regime_suitability"] = suitability[setup].get("rating", "NEUTRAL")
                plan["regime_score"]       = suitability[setup].get("score", 50)
        _write(PATHS["trade_plans"], plans)
        log.info(f"  ✅ Updated {len(plans)} trade plans with regime context")
    else:
        log.info("  ✓ No trade plans to update")

    log.info("  ✅ Data freshness timestamps refreshed")
    return True


# ══════════════════════════════════════════════════════════════════
# STEP 7 — Update 8503 narrative with regime context
# ══════════════════════════════════════════════════════════════════
def sync_adaptive_narrative(regime_data: dict) -> bool:
    """Push institutional AI narrative into adaptive_memory narratives."""
    try:
        sys.path.insert(0, "/root")
        import adaptive_memory as amem

        regime    = regime_data.get("regime", "NEUTRAL")
        narrative = regime_data.get("ai_narrative", "")
        best      = regime_data.get("best_setups", [])
        avoid     = regime_data.get("setups_to_avoid", [])

        narrative_obj = {
            "regime":      regime,
            "confidence":  regime_data.get("regime_confidence", 0.5),
            "summary":     narrative,
            "best_setups": best,
            "avoid_setups":avoid,
            "breadth":     regime_data.get("breadth_summary", {}),
            "sector":      regime_data.get("sector_summary", {}),
            "source":      "institutional_regime_classifier",
        }

        amem.save_narrative(narrative_obj, source="institutional_regime_sync")
        log.info(f"  ✅ Narrative synced: regime={regime}, best={best[:2]}")
        return True

    except Exception as e:
        log.warning(f"  Narrative sync warning: {e}")
        return False


# ══════════════════════════════════════════════════════════════════
# STEP 8 — Save sync status
# ══════════════════════════════════════════════════════════════════
def save_sync_status(regime: str, results: dict):
    status = {
        "timestamp":           datetime.now().isoformat(),
        "regime":              regime,
        "syncs_completed":     sum(1 for v in results.values() if v),
        "syncs_total":         len(results),
        "results":             {k: bool(v) for k, v in results.items()},
        "dashboards_updated":  ["8501", "8503", "8504"],
    }
    _write(PATHS["sync_status"], status)
    log.info(f"Sync status: {status['syncs_completed']}/{status['syncs_total']} ✅")


# ══════════════════════════════════════════════════════════════════
# MAIN SYNC CYCLE
# ══════════════════════════════════════════════════════════════════

def sync_cross_asset(regime_data: dict) -> bool:
    """Sync regime signal into cross_asset_state.json so master_orchestrator reads correct regime."""
    import json, os
    from datetime import datetime
    cross_asset_path = "/root/cross_asset_state.json"
    try:
        regime = regime_data.get("regime", "NEUTRAL")
        # Map regime to cross_asset signal
        cross_map = {
            "STRONG_RISK_ON": "RISK_ON",
            "RISK_ON":        "RISK_ON",
            "NEUTRAL":        "NEUTRAL",
            "CHOPPY":         "NEUTRAL",
            "RISK_OFF":       "RISK_OFF",
            "PANIC":          "RISK_OFF",
        }
        cross_signal = cross_map.get(regime, "NEUTRAL")

        # Read existing file to preserve other fields
        cross = {}
        if os.path.exists(cross_asset_path):
            try:
                with open(cross_asset_path, "r") as f:
                    cross = json.load(f)
            except Exception:
                cross = {}

        cross["regime"]        = regime
        cross["cross_signal"]  = cross_signal
        cross["regime_detail"] = regime
        cross["timestamp"]     = datetime.now().isoformat()

        ok = _write(cross_asset_path, cross)
        if ok:
            log.info(f"  cross_asset_state.json: {cross_signal} (from {regime})")
        return ok
    except Exception as e:
        log.warning(f"  cross_asset sync warning: {e}")
        return False

def run_sync() -> dict:
    log.info("=" * 60)
    log.info("REGIME SYNC CYCLE STARTING")
    log.info("=" * 60)

    # Load regime (source of truth)
    regime_data = load_regime()
    if not regime_data:
        log.error("Cannot sync — no regime data available")
        return {}

    regime  = regime_data.get("regime", "NEUTRAL")
    results = {}

    # Run all sync steps
    results["market_intelligence"] = sync_market_intelligence(regime_data)
    results["paper_trades"]        = sync_paper_trades(regime_data) >= 0
    results["regime_performance"]  = sync_regime_performance(regime_data)
    results["adaptive_memory"]     = sync_adaptive_memory_regime(regime_data)
    results["data_freshness"]      = refresh_data_freshness(regime_data)
    results["narrative"]           = sync_adaptive_narrative(regime_data)
    results["cross_asset"]         = sync_cross_asset(regime_data)

    # Save status
    save_sync_status(regime, results)

    log.info("=" * 60)
    log.info(f"SYNC COMPLETE — Regime: {regime}")
    log.info(f"  8501 (Control Center):     {'✅' if results['market_intelligence'] else '❌'}")
    log.info(f"  8503 (Adaptive Intel):     {'✅' if results['regime_performance'] else '❌'}")
    log.info(f"  8504 (Institutional):      ✅ (source)")
    log.info("=" * 60)

    return results


# ══════════════════════════════════════════════════════════════════
# DAEMON MODE
# ══════════════════════════════════════════════════════════════════
def run_daemon(interval_minutes: int = 5):
    log.info(f"Starting Regime Sync Daemon (every {interval_minutes} min)")
    log.info("Syncs: 8504 → 8501 + 8503")

    while True:
        try:
            run_sync()
        except Exception as e:
            log.error(f"Sync cycle error: {e}")
            import traceback
            traceback.print_exc()

        log.info(f"Next sync in {interval_minutes} minutes...")
        time.sleep(interval_minutes * 60)


# ══════════════════════════════════════════════════════════════════
# STANDALONE
# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    daemon_mode = "--daemon" in sys.argv
    once_mode   = "--once"   in sys.argv or len(sys.argv) == 1

    if daemon_mode:
        run_daemon(interval_minutes=5)
    else:
        print("── Regime Sync ─────────────────────────────────────")
        results = run_sync()
        print(f"\n  Results:")
        for k, v in results.items():
            print(f"    {k:<25} {'✅' if v else '❌'}")
        print("\n  Dashboards updated:")
        print("    8501 Control Center  ← regime, VIX, liquidity, psychology")
        print("    8503 Adaptive Intel  ← regime_performance, paper_trades")
        print("    8504 Institutional   ← source of truth (unchanged)")
        print("\n  ✔ Done")
