"""
correlation_engine.py
CORRELATION INTELLIGENCE ENGINE
Minervini Bot — PAPER TRADING ONLY
"""

import json
import os
import datetime
import logging
import requests
from config import ALPACA_API_KEY, ALPACA_SECRET_KEY

log = logging.getLogger("correlation_engine")
DATA_DIR = "/root/logs"

# ── Known correlation groups ──────────────────────────────────────────────────
CORRELATION_GROUPS = {
    "Semiconductors": ["NVDA", "AMD", "SMCI", "AVGO", "MRVL", "ARM", "INTC", "MU", "QCOM"],
    "MegaCap_Tech":   ["AAPL", "MSFT", "GOOGL", "META", "AMZN"],
    "EV_Tech":        ["TSLA", "RIVN", "LCID", "NIO"],
    "Crypto":         ["BTCUSD", "ETHUSD", "COIN", "MSTR"],
    "Healthcare":     ["LLY", "UNH", "JNJ", "PFE", "ABBV", "MRK"],
    "Banks":          ["JPM", "GS", "MS", "BAC", "C", "WFC"],
    "Energy":         ["XOM", "CVX", "COP", "SLB"],
    "Biotech":        ["MRNA", "BNTX", "REGN", "BIIB"],
}

MAX_GROUP_EXPOSURE = 2   # max positions from same group
MAX_GROUP_HEAT_PCT = 4.0 # max % heat from same correlation group

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

def get_correlation_group(symbol: str) -> str:
    """Return correlation group name for a symbol."""
    for group, members in CORRELATION_GROUPS.items():
        if symbol in members:
            return group
    return "Other"

def get_group_members_in_portfolio(symbol: str, positions: list) -> list:
    """Return existing portfolio positions in same correlation group."""
    group   = get_correlation_group(symbol)
    if group == "Other":
        return []
    members = CORRELATION_GROUPS.get(group, [])
    return [p for p in positions if p.get("symbol", "") in members]

def calc_correlation_risk(positions: list, portfolio_value: float) -> dict:
    """Calculate correlation risk for current portfolio."""
    group_exposure = {}

    for pos in positions:
        symbol    = pos.get("symbol", "")
        mkt_val   = float(pos.get("market_value", 0))
        open_risk = float(pos.get("open_risk", 0))
        group     = get_correlation_group(symbol)

        if group not in group_exposure:
            group_exposure[group] = {
                "symbols":    [],
                "market_val": 0,
                "open_risk":  0,
                "heat_pct":   0,
                "count":      0,
            }
        group_exposure[group]["symbols"].append(symbol)
        group_exposure[group]["market_val"] += mkt_val
        group_exposure[group]["open_risk"]  += open_risk
        group_exposure[group]["heat_pct"]   += open_risk / portfolio_value * 100
        group_exposure[group]["count"]      += 1

    corr_warnings = []
    for group, data in group_exposure.items():
        if group == "Other":
            continue
        if data["count"] >= MAX_GROUP_EXPOSURE:
            corr_warnings.append({
                "group":   group,
                "symbols": data["symbols"],
                "count":   data["count"],
                "heat":    round(data["heat_pct"], 2),
                "warning": f"{group}: {data['count']} positions → high correlation risk",
            })
        if data["heat_pct"] > MAX_GROUP_HEAT_PCT:
            corr_warnings.append({
                "group":   group,
                "symbols": data["symbols"],
                "heat":    round(data["heat_pct"], 2),
                "warning": f"{group}: heat {data['heat_pct']:.1f}% > {MAX_GROUP_HEAT_PCT:.0f}% limit",
            })

    result = {
        "group_exposure":   group_exposure,
        "corr_warnings":    corr_warnings,
        "timestamp":        datetime.datetime.now().isoformat(),
        "paper_only":       True,
    }

    try:
        with open(f"{DATA_DIR}/correlation_risk.json", "w") as f:
            json.dump(result, f, indent=2, default=str)
    except Exception:
        pass

    return result

def check_correlation_for_new_trade(
    symbol: str, positions: list, portfolio_value: float
) -> tuple:
    """
    Check if adding symbol would create excessive correlation.
    Returns (approved, size_multiplier, reason).
    """
    group         = get_correlation_group(symbol)
    group_members = get_group_members_in_portfolio(symbol, positions)
    count         = len(group_members)

    if count == 0:
        return True, 1.0, f"No correlation risk ({group})"

    if count >= MAX_GROUP_EXPOSURE:
        return False, 0.0, (
            f"Correlation limit: {count} {group} positions already "
            f"({', '.join([p['symbol'] for p in group_members])})"
        )

    # Reduce size based on correlation
    size_mult = max(0.5, 1.0 - (count * 0.25))
    return True, size_mult, (
        f"Correlation warning: {count} {group} positions → "
        f"size reduced to {size_mult*100:.0f}%"
    )
