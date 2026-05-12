"""
capital_allocator.py
DYNAMIC CAPITAL ALLOCATOR
Minervini Bot — PAPER TRADING ONLY
"""

import json
import os
import datetime
import logging
import requests
from config import ALPACA_API_KEY, ALPACA_SECRET_KEY

log = logging.getLogger("capital_allocator")
DATA_DIR = "/root/logs"

BASE_ALLOCATION = {
    "swing":    0.70,
    "intraday": 0.20,
    "cash":     0.10,
}

def _load(path, default):
    try:
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    except Exception:
        pass
    return default

def _alpaca_get(endpoint):
    try:
        r = requests.get(
            f"https://paper-api.alpaca.markets{endpoint}",
            headers={"APCA-API-KEY-ID": ALPACA_API_KEY,
                     "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY},
            timeout=10
        )
        return r.json() if r.status_code == 200 else {}
    except Exception:
        return {}

def get_vix() -> float:
    try:
        data = _alpaca_get("/v2/stocks/VIXY/bars?timeframe=1Day&limit=1")
        bars = data.get("bars", [])
        return float(bars[-1]["c"]) if bars else 20.0
    except Exception:
        return 20.0

def calc_dynamic_allocation(portfolio_value: float = 50000.0) -> dict:
    """
    Dynamic capital allocation based on regime, VIX, breadth, drawdown.
    PAPER TRADING ONLY.
    """
    mi      = _load(f"{DATA_DIR}/market_intelligence.json", {})
    perf    = _load(f"{DATA_DIR}/paper_performance.json", {})
    heat    = _load(f"{DATA_DIR}/portfolio_heat.json", {})

    regime  = mi.get("regime", mi.get("market_regime", "NEUTRAL")).upper()
    vix     = get_vix()
    breadth = float(mi.get("breadth_score", mi.get("breadth", 50)))
    drawdown= float(perf.get("max_drawdown", 0))
    dd_pct  = abs(drawdown) / portfolio_value * 100 if portfolio_value else 0

    alloc   = dict(BASE_ALLOCATION)
    reasons = []

    # ── Regime adjustments ────────────────────────────────────────────────────
    if "RISK_ON" in regime or "STRONG" in regime:
        alloc["swing"]    += 0.10
        alloc["cash"]     -= 0.05
        alloc["intraday"] -= 0.05
        reasons.append(f"RISK_ON → more swing")
    elif "RISK_OFF" in regime:
        alloc["swing"]    -= 0.20
        alloc["cash"]     += 0.15
        alloc["intraday"] -= 0.05
        reasons.append(f"RISK_OFF → more cash")
    elif "NEUTRAL" in regime:
        reasons.append("NEUTRAL → base allocation")

    # ── VIX adjustments ───────────────────────────────────────────────────────
    if vix > 30:
        alloc["swing"]    -= 0.15
        alloc["cash"]     += 0.15
        reasons.append(f"VIX={vix:.0f} > 30 → defensive")
    elif vix > 22:
        alloc["swing"]    -= 0.08
        alloc["cash"]     += 0.08
        reasons.append(f"VIX={vix:.0f} > 22 → cautious")
    elif vix < 15:
        alloc["swing"]    += 0.05
        alloc["intraday"] += 0.03
        alloc["cash"]     -= 0.08
        reasons.append(f"VIX={vix:.0f} < 15 → aggressive")

    # ── Breadth adjustments ───────────────────────────────────────────────────
    if breadth < 35:
        alloc["swing"]    -= 0.10
        alloc["cash"]     += 0.10
        reasons.append(f"Breadth={breadth:.0f} weak → reduce swing")
    elif breadth > 65:
        alloc["swing"]    += 0.05
        reasons.append(f"Breadth={breadth:.0f} strong → add swing")

    # ── Drawdown adjustments ──────────────────────────────────────────────────
    if dd_pct > 5:
        alloc["swing"]    -= 0.20
        alloc["intraday"] -= 0.10
        alloc["cash"]     += 0.30
        reasons.append(f"Drawdown={dd_pct:.1f}% > 5% → defensive mode")
    elif dd_pct > 3:
        alloc["swing"]    -= 0.10
        alloc["cash"]     += 0.10
        reasons.append(f"Drawdown={dd_pct:.1f}% → reduce risk")

    # ── Normalize to 100% ─────────────────────────────────────────────────────
    alloc["swing"]    = max(0.10, min(0.90, alloc["swing"]))
    alloc["intraday"] = max(0.05, min(0.40, alloc["intraday"]))
    alloc["cash"]     = max(0.05, min(0.70, alloc["cash"]))

    total = alloc["swing"] + alloc["intraday"] + alloc["cash"]
    alloc = {k: round(v / total, 3) for k, v in alloc.items()}

    result = {
        "allocation":       alloc,
        "dollar_amounts": {
            k: round(v * portfolio_value, 2) for k, v in alloc.items()
        },
        "regime":           regime,
        "vix":              vix,
        "breadth":          breadth,
        "drawdown_pct":     round(dd_pct, 2),
        "reasons":          reasons,
        "timestamp":        datetime.datetime.now().isoformat(),
        "paper_only":       True,
    }

    try:
        with open(f"{DATA_DIR}/capital_allocation.json", "w") as f:
            json.dump(result, f, indent=2, default=str)
    except Exception as e:
        log.error(f"Save error: {e}")

    log.info(
        f"Allocation: Swing={alloc['swing']*100:.0f}% | "
        f"Intraday={alloc['intraday']*100:.0f}% | "
        f"Cash={alloc['cash']*100:.0f}%"
    )
    return result

def get_position_size_multiplier(portfolio_value: float = 50000.0) -> float:
    """Return size multiplier based on current risk environment."""
    alloc  = calc_dynamic_allocation(portfolio_value)
    heat   = _load(f"{DATA_DIR}/portfolio_heat.json", {})
    heat_pct = heat.get("portfolio_heat_pct", 0)

    # Base multiplier from cash level
    cash_pct = alloc["allocation"]["cash"]
    if cash_pct > 0.40:
        mult = 0.5
    elif cash_pct > 0.25:
        mult = 0.75
    else:
        mult = 1.0

    # Reduce if heat is building
    if heat_pct > 4:
        mult *= 0.6
    elif heat_pct > 2:
        mult *= 0.8

    return round(max(0.25, min(1.0, mult)), 2)
