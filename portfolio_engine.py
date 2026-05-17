from telegram_gate import send_telegram, send_alert
"""
portfolio_engine.py
PORTFOLIO HEAT ENGINE
Minervini Bot — PAPER TRADING ONLY
"""

import json
import os
import datetime
import logging
import requests
from typing import Optional
from config import ALPACA_API_KEY, ALPACA_SECRET_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

log = logging.getLogger("portfolio_engine")
DATA_DIR     = "/root/logs"
PAPER_BASE   = "https://paper-api.alpaca.markets"
PORTFOLIO    = 50_000.0
PAPER_ONLY   = True

# ── Risk limits ───────────────────────────────────────────────────────────────
MAX_PORTFOLIO_HEAT    = 0.06   # 6% total open risk
MAX_SECTOR_EXPOSURE   = 0.40   # 40% per sector
MAX_SINGLE_POSITION   = 0.15   # 15% single position
MAX_CORRELATED_HEAT   = 0.08   # 8% correlated group
CASH_RESERVE_MIN      = 0.20   # 20% min cash

SECTOR_LIMITS = {
    "Technology":   0.50,
    "Healthcare":   0.30,
    "Financials":   0.25,
    "Energy":       0.20,
    "Crypto":       0.10,
    "Consumer":     0.25,
    "Industrial":   0.20,
    "Other":        0.20,
}

SECTOR_MAP = {
    "NVDA": "Technology", "AMD":  "Technology", "MSFT": "Technology",
    "AAPL": "Technology", "GOOGL":"Technology", "META": "Technology",
    "SMCI": "Technology", "AVGO": "Technology", "ARM":  "Technology",
    "TSLA": "Technology", "MRVL": "Technology", "INTC": "Technology",
    "LLY":  "Healthcare", "UNH":  "Healthcare", "JNJ":  "Healthcare",
    "PFE":  "Healthcare", "ABBV": "Healthcare", "MRK":  "Healthcare",
    "JPM":  "Financials", "GS":   "Financials", "MS":   "Financials",
    "BAC":  "Financials", "V":    "Financials", "MA":   "Financials",
    "XOM":  "Energy",     "CVX":  "Energy",     "COP":  "Energy",
    "BTCUSD":"Crypto",    "ETHUSD":"Crypto",
}

def _alpaca_get(endpoint):
    try:
        r = requests.get(
            f"{PAPER_BASE}{endpoint}",
            headers={"APCA-API-KEY-ID": ALPACA_API_KEY,
                     "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY},
            timeout=10
        )
        return r.json() if r.status_code == 200 else {}
    except Exception:
        return {}

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

def _send_telegram(msg: str):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"},
            timeout=10
        )
    except Exception:
        pass

# ── Get live positions from Alpaca ────────────────────────────────────────────
def get_live_positions() -> list:
    data = _alpaca_get("/v2/positions")
    if isinstance(data, list):
        return data
    return []

def get_account() -> dict:
    return _alpaca_get("/v2/account")

# ── Portfolio Heat ────────────────────────────────────────────────────────────
def calc_portfolio_heat(positions: list, portfolio_value: float = PORTFOLIO) -> dict:
    """
    Calculate total portfolio heat = sum of open risk for all positions.
    PAPER TRADING ONLY.
    """
    total_market_value = 0.0
    total_unrealized   = 0.0
    total_risk         = 0.0
    sector_exposure    = {}
    position_details   = []

    for pos in positions:
        symbol   = pos.get("symbol", "")
        qty      = float(pos.get("qty", 0))
        avg_entry= float(pos.get("avg_entry_price", 0))
        curr_price= float(pos.get("current_price", avg_entry))
        market_val= float(pos.get("market_value", qty * curr_price))
        unrealized= float(pos.get("unrealized_pl", 0))

        # Estimate risk (distance to implied SL = 5% of entry)
        implied_sl  = avg_entry * 0.95
        risk_per_sh = abs(curr_price - implied_sl)
        open_risk   = risk_per_sh * qty
        open_risk_pct = open_risk / portfolio_value * 100

        sector = SECTOR_MAP.get(symbol, "Other")
        sector_exposure[sector] = sector_exposure.get(sector, 0) + market_val

        total_market_value += market_val
        total_unrealized   += unrealized
        total_risk         += open_risk

        position_details.append({
            "symbol":      symbol,
            "sector":      sector,
            "qty":         qty,
            "entry":       avg_entry,
            "current":     curr_price,
            "market_value":round(market_val, 2),
            "unrealized":  round(unrealized, 2),
            "open_risk":   round(open_risk, 2),
            "risk_pct":    round(open_risk_pct, 2),
            "weight":      round(market_val / portfolio_value * 100, 2),
        })

    heat_pct = total_risk / portfolio_value * 100
    cash_pct = max(0, (portfolio_value - total_market_value) / portfolio_value * 100)

    sector_pct = {
        s: round(v / portfolio_value * 100, 2)
        for s, v in sector_exposure.items()
    }

    result = {
        "portfolio_value":    round(portfolio_value, 2),
        "total_market_value": round(total_market_value, 2),
        "total_unrealized":   round(total_unrealized, 2),
        "total_open_risk":    round(total_risk, 2),
        "portfolio_heat_pct": round(heat_pct, 2),
        "cash_pct":           round(cash_pct, 2),
        "capital_utilized":   round(100 - cash_pct, 2),
        "sector_exposure":    sector_pct,
        "positions":          position_details,
        "position_count":     len(positions),
        "timestamp":          datetime.datetime.now().isoformat(),
        "paper_only":         True,
    }

    _save(f"{DATA_DIR}/portfolio_heat.json", result)
    return result

# ── Concentration warnings ────────────────────────────────────────────────────
def check_concentration(heat: dict) -> list:
    """Detect concentration risks and over-exposure."""
    warnings = []

    # Portfolio heat
    if heat["portfolio_heat_pct"] > MAX_PORTFOLIO_HEAT * 100:
        warnings.append({
            "type":    "PORTFOLIO_HEAT",
            "level":   "HIGH",
            "message": f"Portfolio heat {heat['portfolio_heat_pct']:.1f}% > {MAX_PORTFOLIO_HEAT*100:.0f}%",
        })

    # Cash reserve
    if heat["cash_pct"] < CASH_RESERVE_MIN * 100:
        warnings.append({
            "type":    "LOW_CASH",
            "level":   "MEDIUM",
            "message": f"Cash {heat['cash_pct']:.1f}% < {CASH_RESERVE_MIN*100:.0f}% minimum",
        })

    # Sector limits
    for sector, pct in heat["sector_exposure"].items():
        limit = SECTOR_LIMITS.get(sector, 0.20) * 100
        if pct > limit:
            warnings.append({
                "type":    "SECTOR_OVERLOAD",
                "level":   "HIGH",
                "message": f"{sector} exposure {pct:.1f}% > {limit:.0f}% limit",
            })

    # Single position concentration
    for pos in heat["positions"]:
        if pos["weight"] > MAX_SINGLE_POSITION * 100:
            warnings.append({
                "type":    "POSITION_CONCENTRATION",
                "level":   "MEDIUM",
                "message": f"{pos['symbol']} weight {pos['weight']:.1f}% > {MAX_SINGLE_POSITION*100:.0f}%",
            })

    if warnings:
        _save(f"{DATA_DIR}/concentration_warnings.json", {
            "warnings":  warnings,
            "timestamp": datetime.datetime.now().isoformat(),
        })
        for w in warnings:
            if w["level"] == "HIGH":
                _send_telegram(
                    f"⚠️ *PORTFOLIO WARNING — PAPER*\n"
                    f"Type: `{w['type']}`\n"
                    f"{w['message']}\n"
                    f"⚠️ PAPER TRADING ONLY"
                )

    return warnings

# ── Portfolio-level trade approval ────────────────────────────────────────────
def approve_new_trade(symbol: str, planned_risk: float, heat: dict) -> tuple:
    """
    Portfolio-level AI decision: should we add this trade?
    Returns (approved, reason).
    PAPER TRADING ONLY.
    """
    # Check heat budget
    new_heat = heat["portfolio_heat_pct"] + (planned_risk / heat["portfolio_value"] * 100)
    if new_heat > MAX_PORTFOLIO_HEAT * 100:
        return False, f"Portfolio heat would reach {new_heat:.1f}% > {MAX_PORTFOLIO_HEAT*100:.0f}%"

    # Check cash
    if heat["cash_pct"] < CASH_RESERVE_MIN * 100:
        return False, f"Insufficient cash: {heat['cash_pct']:.1f}%"

    # Check sector
    sector = SECTOR_MAP.get(symbol, "Other")
    sector_pct = heat["sector_exposure"].get(sector, 0)
    limit = SECTOR_LIMITS.get(sector, 0.20) * 100
    if sector_pct >= limit:
        return False, f"{sector} already at {sector_pct:.1f}% limit ({limit:.0f}%)"

    # Check duplicate symbol
    existing = [p["symbol"] for p in heat["positions"]]
    if symbol in existing:
        return False, f"{symbol} already in portfolio"

    return True, f"Approved | Heat: {heat['portfolio_heat_pct']:.1f}% → {new_heat:.1f}% | Sector: {sector} {sector_pct:.1f}%"

# ── Main portfolio snapshot ───────────────────────────────────────────────────
def run_portfolio_snapshot() -> dict:
    """Full portfolio intelligence snapshot."""
    positions = get_live_positions()
    account   = get_account()
    port_val  = float(account.get("portfolio_value", PORTFOLIO))

    heat      = calc_portfolio_heat(positions, port_val)
    warnings  = check_concentration(heat)

    snapshot = {
        **heat,
        "warnings":      warnings,
        "warning_count": len(warnings),
    }

    log.info(
        f"Portfolio: Heat={heat['portfolio_heat_pct']:.1f}% | "
        f"Cash={heat['cash_pct']:.1f}% | "
        f"Positions={heat['position_count']} | "
        f"Warnings={len(warnings)}"
    )
    return snapshot
