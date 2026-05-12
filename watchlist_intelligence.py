#!/usr/bin/env python3
"""
watchlist_intelligence.py — Dynamic Watchlist Engine
SEMI-AUTONOMOUS EXECUTION LAYER | Intelligence Only
Builds regime-aware, momentum-filtered watchlist dynamically.
"""

import os, json, time
from datetime import datetime
from typing import Optional

try:
    from logger import get_logger
    log = get_logger("watchlist_intelligence")
except ImportError:
    import logging
    log = logging.getLogger("watchlist_intelligence")
    logging.basicConfig(level=logging.INFO)

from dotenv import load_dotenv
load_dotenv("/root/.env")

WATCHLIST_FILE = "/root/logs/watchlist.json"
os.makedirs("/root/logs", exist_ok=True)

# ── Sector Watchlists by Regime ───────────────────────────────
REGIME_SECTORS = {
    "RISK_ON": {
        "primary":   ["Technology", "Consumer Discretionary", "Industrials"],
        "secondary": ["Financials", "Materials"],
        "avoid":     ["Utilities", "Consumer Staples"],
    },
    "NEUTRAL": {
        "primary":   ["Technology", "Healthcare", "Financials"],
        "secondary": ["Industrials", "Consumer Discretionary"],
        "avoid":     [],
    },
    "RISK_OFF": {
        "primary":   ["Healthcare", "Consumer Staples", "Utilities"],
        "secondary": ["Financials"],
        "avoid":     ["Technology", "Consumer Discretionary"],
    },
    "CRISIS": {
        "primary":   ["Consumer Staples", "Utilities"],
        "secondary": ["Healthcare"],
        "avoid":     ["Technology", "Consumer Discretionary", "Financials"],
    },
}

# ── Base Universe by Category ─────────────────────────────────
UNIVERSE = {
    "mega_cap_tech": ["NVDA", "MSFT", "AAPL", "META", "GOOGL", "AMZN", "AVGO"],
    "growth_tech":   ["ARM", "ANET", "MRVL", "CRWD", "SNOW", "DDOG", "NET"],
    "financials":    ["GS", "JPM", "MS", "V", "MA", "AXP"],
    "healthcare":    ["LLY", "NVO", "UNH", "ABBV", "TMO"],
    "industrials":   ["CAT", "DE", "ETN", "GE", "HON"],
    "consumer":      ["LULU", "NKE", "SBUX", "MCD", "COST"],
    "energy":        ["XOM", "CVX", "SLB", "EOG"],
    "materials":     ["FCX", "NEM", "ALB", "MP"],
    "crypto_proxy":  ["COIN", "MSTR", "MARA", "RIOT"],
    "defense":       ["LMT", "RTX", "NOC", "GD"],
}

# ── Macro overlays ────────────────────────────────────────────
MACRO_OVERLAYS = {
    "high_vix":      ["GLD", "TLT", "VYM"],        # VIX > 25
    "low_vix":       ["SMH", "QQQ", "ARKK"],        # VIX < 15
    "strong_dollar": ["EEM"],                        # avoid EM
    "weak_dollar":   ["GLD", "SLV", "COPX"],
    "rising_rates":  ["BX", "KKR", "BAC"],
    "falling_rates": ["REGL", "REM"],
}


def get_regime_watchlist(regime: str, vix: float = 17.0,
                          macro: dict = None) -> dict:
    """Build dynamic watchlist based on current conditions."""
    macro = macro or {}

    regime_config = REGIME_SECTORS.get(regime, REGIME_SECTORS["NEUTRAL"])
    primary_sectors = regime_config["primary"]
    avoid_sectors   = regime_config["avoid"]

    # Build symbol list by regime
    watchlist = {
        "TIER_1": [],   # Highest conviction
        "TIER_2": [],   # Secondary
        "AVOID":  [],
    }

    # Tier 1 — mega cap + primary sectors
    watchlist["TIER_1"].extend(UNIVERSE["mega_cap_tech"][:5])

    if regime in ("RISK_ON", "NEUTRAL"):
        watchlist["TIER_1"].extend(UNIVERSE["growth_tech"][:4])
        watchlist["TIER_2"].extend(UNIVERSE["financials"][:3])
        watchlist["TIER_2"].extend(UNIVERSE["industrials"][:3])

    if regime == "RISK_OFF":
        watchlist["TIER_1"].extend(UNIVERSE["healthcare"][:4])
        watchlist["TIER_1"].extend(UNIVERSE["consumer"][:2])
        watchlist["TIER_2"].extend(UNIVERSE["defense"][:3])
        watchlist["AVOID"].extend(UNIVERSE["crypto_proxy"])

    if regime == "CRISIS":
        watchlist["TIER_1"] = UNIVERSE["healthcare"][:3] + UNIVERSE["consumer"][:3]
        watchlist["TIER_2"] = UNIVERSE["defense"][:2]
        watchlist["AVOID"]  = UNIVERSE["mega_cap_tech"] + UNIVERSE["growth_tech"]

    # VIX overlays
    if vix > 25:
        watchlist["TIER_1"].extend(MACRO_OVERLAYS["high_vix"])
        watchlist["AVOID"].extend(UNIVERSE["crypto_proxy"])
    elif vix < 15:
        watchlist["TIER_2"].extend(MACRO_OVERLAYS["low_vix"])

    # Macro overlays
    if macro.get("dollar_strong"):
        watchlist["AVOID"].extend(MACRO_OVERLAYS["strong_dollar"])
    if macro.get("rates_rising"):
        watchlist["TIER_2"].extend(MACRO_OVERLAYS["rising_rates"])

    # Deduplicate
    watchlist["TIER_1"] = list(dict.fromkeys(watchlist["TIER_1"]))
    watchlist["TIER_2"] = list(dict.fromkeys(
        s for s in watchlist["TIER_2"] if s not in watchlist["TIER_1"]
    ))
    watchlist["AVOID"] = list(dict.fromkeys(
        s for s in watchlist["AVOID"]
        if s not in watchlist["TIER_1"] and s not in watchlist["TIER_2"]
    ))

    return watchlist


def build_intelligence_watchlist(regime: str, vix: float,
                                   top_scores: list,
                                   macro: dict = None) -> dict:
    """
    Full intelligence watchlist combining:
    - Regime-based universe
    - Current top scoring symbols
    - Macro conditions
    """
    base = get_regime_watchlist(regime, vix, macro)

    # Add top scoring symbols to Tier 1 if not already present
    for item in top_scores[:5]:
        sym = item.get("symbol", "")
        if sym and sym not in base["TIER_1"] and sym not in base["AVOID"]:
            base["TIER_1"].insert(0, sym)

    result = {
        "timestamp":  datetime.now().isoformat(),
        "regime":     regime,
        "vix":        vix,
        "watchlist":  base,
        "total":      len(base["TIER_1"]) + len(base["TIER_2"]),
        "scan_focus": base["TIER_1"][:10],  # top 10 to scan first
        "macro":      macro or {},
        "rationale":  _build_rationale(regime, vix, macro),
    }

    _save_watchlist(result)
    return result


def _build_rationale(regime: str, vix: float, macro: dict) -> str:
    parts = [f"Regime: {regime}"]
    parts.append(f"VIX: {vix:.1f} ({'elevated' if vix > 25 else 'low' if vix < 15 else 'normal'})")
    if macro:
        if macro.get("dollar_strong"): parts.append("USD strong — avoiding EM")
        if macro.get("rates_rising"):  parts.append("Rising rates — favoring financials")
    return " | ".join(parts)


def _save_watchlist(data: dict):
    try:
        with open(WATCHLIST_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        log.error(f"Failed to save watchlist: {e}")


def load_watchlist() -> dict:
    try:
        if os.path.exists(WATCHLIST_FILE):
            with open(WATCHLIST_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


# ── Test ──────────────────────────────────────────────────────
if __name__ == "__main__":
    wl = build_intelligence_watchlist(
        regime="RISK_ON",
        vix=17.2,
        top_scores=[
            {"symbol": "NVDA", "score": 87.5},
            {"symbol": "AMD",  "score": 85.0},
            {"symbol": "TSLA", "score": 82.0},
        ],
        macro={"rates_rising": False, "dollar_strong": False}
    )
    print(f"✅ Watchlist built: {wl['total']} symbols")
    print(f"Tier 1: {wl['watchlist']['TIER_1']}")
    print(f"Tier 2: {wl['watchlist']['TIER_2']}")
    print(f"Scan focus: {wl['scan_focus']}")
