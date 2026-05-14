#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║   MINERVINI AI — LIQUIDITY ENGINE                                ║
║   Understands institutional liquidity conditions                 ║
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [Liquidity] %(message)s")
log = logging.getLogger("liquidity_engine")

# ── Config ────────────────────────────────────────────────────────
OUTPUT_PATH = "/root/adaptive/liquidity_state.json"
CACHE_TTL   = 300

os.makedirs("/root/adaptive", exist_ok=True)

MARKET_ETFS = ["SPY", "QQQ", "IWM", "DIA"]
SECTOR_ETFS = ["XLK", "XLF", "XLE", "XLV", "XLI"]
ALL_ETFS    = MARKET_ETFS + SECTOR_ETFS


# ── Fetch ─────────────────────────────────────────────────────────
def _fetch(ticker: str, period: str = "1mo",
           interval: str = "1d") -> Optional[object]:
    try:
        import yfinance as yf
        df = yf.Ticker(ticker).history(period=period, interval=interval)
        return df if not df.empty else None
    except Exception:
        return None


def _intraday(ticker: str, interval: str = "5m") -> Optional[object]:
    try:
        import yfinance as yf
        df = yf.Ticker(ticker).history(period="1d", interval=interval)
        return df if not df.empty else None
    except Exception:
        return None


# ── Volume Analysis ───────────────────────────────────────────────
def _relative_volume(ticker: str) -> Optional[float]:
    """Current volume vs 20-day average."""
    df = _fetch(ticker, "2mo", "1d")
    if df is None or len(df) < 5:
        return None
    avg = df["Volume"].iloc[:-1].mean()
    cur = df["Volume"].iloc[-1]
    return round(float(cur / max(avg, 1)), 2)


def _opening_participation(ticker: str = "SPY") -> Optional[float]:
    """First 30 min volume as % of daily average."""
    try:
        import yfinance as yf
        df_5m = yf.Ticker(ticker).history(period="1d", interval="5m")
        df_1d = yf.Ticker(ticker).history(period="1mo", interval="1d")
        if df_5m.empty or df_1d.empty:
            return None
        open_vol = float(df_5m["Volume"].iloc[:6].sum())   # 6 × 5min = 30min
        avg_daily = float(df_1d["Volume"].mean())
        return round(open_vol / max(avg_daily, 1) * 100, 2)
    except Exception:
        return None


def _closing_participation(ticker: str = "SPY") -> Optional[float]:
    """Last 30 min volume as % of daily average."""
    try:
        import yfinance as yf
        df_5m = yf.Ticker(ticker).history(period="1d", interval="5m")
        df_1d = yf.Ticker(ticker).history(period="1mo", interval="1d")
        if df_5m.empty or df_1d.empty or len(df_5m) < 6:
            return None
        close_vol = float(df_5m["Volume"].iloc[-6:].sum())
        avg_daily = float(df_1d["Volume"].mean())
        return round(close_vol / max(avg_daily, 1) * 100, 2)
    except Exception:
        return None


def _volume_trend(ticker: str = "SPY") -> Optional[str]:
    """Is volume trending up or down vs 10-day avg?"""
    df = _fetch(ticker, "1mo", "1d")
    if df is None or len(df) < 10:
        return None
    recent = df["Volume"].iloc[-5:].mean()
    older  = df["Volume"].iloc[-10:-5].mean()
    if recent > older * 1.1:
        return "RISING"
    elif recent < older * 0.9:
        return "FALLING"
    return "STABLE"


def _etf_participation_score() -> float:
    """% of ETFs with above-average volume."""
    above_avg = 0
    total     = 0
    for etf in ALL_ETFS:
        rv = _relative_volume(etf)
        if rv is not None:
            total += 1
            if rv > 1.0:
                above_avg += 1
        time.sleep(0.1)
    return round(above_avg / max(total, 1) * 100, 1)


# ── Dollar Volume ─────────────────────────────────────────────────
def _dollar_volume(ticker: str = "SPY") -> Optional[float]:
    """Today's dollar volume in billions."""
    try:
        import yfinance as yf
        df = yf.Ticker(ticker).history(period="2d", interval="1d")
        if df.empty:
            return None
        dv = float(df["Volume"].iloc[-1] * df["Close"].iloc[-1])
        return round(dv / 1e9, 2)
    except Exception:
        return None


# ── Classify Liquidity ────────────────────────────────────────────
def _classify_liquidity(rvol_spy: float, etf_participation: float,
                         open_part: float, trend: str) -> str:
    score = 0

    if rvol_spy:
        if   rvol_spy > 2.0:  score += 3
        elif rvol_spy > 1.3:  score += 2
        elif rvol_spy > 0.9:  score += 1
        elif rvol_spy < 0.6:  score -= 2

    if etf_participation > 70: score += 2
    elif etf_participation > 50: score += 1
    elif etf_participation < 30: score -= 1

    if open_part and open_part > 15: score += 1

    if trend == "RISING":  score += 1
    if trend == "FALLING": score -= 1

    if score >= 5: return "INSTITUTIONAL"
    if score >= 3: return "NORMAL"
    if score >= 1: return "THIN"
    return "PANIC_LIQUIDITY" if (rvol_spy and rvol_spy > 3) else "THIN"


# ── Main Computation ──────────────────────────────────────────────
def compute_liquidity() -> dict:
    log.info("Computing liquidity conditions...")

    result = {
        "timestamp":             datetime.now().isoformat(),
        "liquidity_state":       "NORMAL",
        "liquidity_score":       50.0,
        "relative_volume_spy":   None,
        "etf_participation":     50.0,
        "opening_participation": None,
        "closing_participation": None,
        "volume_trend":          "STABLE",
        "dollar_volume_spy":     None,
        "per_etf_rvol":          {},
        "institutional_signal":  False,
        "panic_signal":          False,
        "setup_implications":    {},
        "data_quality":          "partial",
    }

    # ── SPY Relative Volume ────────────────────────────────────────
    rvol_spy = _relative_volume("SPY")
    result["relative_volume_spy"] = rvol_spy
    log.info(f"  SPY RVOL: {rvol_spy}x")
    time.sleep(0.2)

    # ── Per-ETF RVOL ───────────────────────────────────────────────
    per_etf = {}
    for etf in MARKET_ETFS:
        rv = _relative_volume(etf)
        per_etf[etf] = rv
        time.sleep(0.15)
    result["per_etf_rvol"] = per_etf

    # ── ETF Participation ──────────────────────────────────────────
    etf_part = _etf_participation_score()
    result["etf_participation"] = etf_part
    log.info(f"  ETF Participation: {etf_part}%")

    # ── Opening / Closing ──────────────────────────────────────────
    open_part  = _opening_participation("SPY")
    close_part = _closing_participation("SPY")
    result["opening_participation"] = open_part
    result["closing_participation"] = close_part
    log.info(f"  Open: {open_part}% | Close: {close_part}%")
    time.sleep(0.2)

    # ── Volume Trend ───────────────────────────────────────────────
    trend = _volume_trend("SPY")
    result["volume_trend"] = trend

    # ── Dollar Volume ──────────────────────────────────────────────
    dv = _dollar_volume("SPY")
    result["dollar_volume_spy"] = dv
    log.info(f"  Dollar Volume: ${dv}B")

    # ── Classification ─────────────────────────────────────────────
    state = _classify_liquidity(
        rvol_spy, etf_part,
        open_part or 10.0, trend or "STABLE"
    )
    result["liquidity_state"] = state

    # ── Liquidity Score ────────────────────────────────────────────
    score_map = {"THIN": 25, "NORMAL": 50, "INSTITUTIONAL": 80, "PANIC_LIQUIDITY": 90}
    result["liquidity_score"] = float(score_map.get(state, 50))

    # ── Signals ────────────────────────────────────────────────────
    result["institutional_signal"] = state == "INSTITUTIONAL"
    result["panic_signal"]         = state == "PANIC_LIQUIDITY"

    # ── Setup Implications ─────────────────────────────────────────
    result["setup_implications"] = _setup_implications(state, rvol_spy or 1.0)

    # ── Data Quality ───────────────────────────────────────────────
    data_pts = sum(1 for x in [rvol_spy, etf_part, open_part, trend, dv]
                   if x is not None)
    result["data_quality"] = "good" if data_pts >= 4 else "partial"

    log.info(f"Liquidity: {state} | Score: {result['liquidity_score']} | "
             f"Institutional: {result['institutional_signal']}")

    _save(result)
    return result


def _setup_implications(state: str, rvol: float) -> dict:
    if state == "INSTITUTIONAL":
        return {
            "ORB_BREAKOUT":             "FAVORABLE",
            "TIGHT_CONSOLIDATION_BREAK":"FAVORABLE",
            "MOMENTUM_BURST_UP":        "FAVORABLE",
            "VOLUME_SPIKE":             "FAVORABLE",
            "VWAP_CROSS_UP":            "FAVORABLE",
        }
    elif state == "NORMAL":
        return {
            "ORB_BREAKOUT":             "NEUTRAL",
            "TIGHT_CONSOLIDATION_BREAK":"FAVORABLE",
            "MOMENTUM_BURST_UP":        "NEUTRAL",
            "VOLUME_SPIKE":             "NEUTRAL",
        }
    elif state == "THIN":
        return {
            "ORB_BREAKOUT":             "REDUCED",
            "TIGHT_CONSOLIDATION_BREAK":"REDUCED",
            "MOMENTUM_BURST_UP":        "REDUCED",
            "VOLUME_SPIKE":             "AVOID",
        }
    else:  # PANIC_LIQUIDITY
        return {
            "ORB_BREAKDOWN":       "FAVORABLE",
            "MOMENTUM_BURST_DOWN": "FAVORABLE",
            "ORB_BREAKOUT":        "DANGEROUS",
            "VOLUME_SPIKE":        "NEUTRAL",
        }


# ── Cache-Aware Runner ────────────────────────────────────────────
def get_liquidity(force: bool = False) -> dict:
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
    return compute_liquidity()


def _save(data: dict):
    try:
        with open(OUTPUT_PATH, "w") as f:
            json.dump(data, f, indent=2, default=str)
        log.info(f"Saved → {OUTPUT_PATH}")
    except Exception as e:
        log.error(f"Save error: {e}")


# ── Standalone ────────────────────────────────────────────────────
if __name__ == "__main__":
    print("── Liquidity Engine ────────────────────────────────")
    data = compute_liquidity()
    print(f"  State:              {data['liquidity_state']}")
    print(f"  Score:              {data['liquidity_score']}")
    print(f"  SPY RVOL:           {data['relative_volume_spy']}x")
    print(f"  ETF Participation:  {data['etf_participation']}%")
    print(f"  Opening:            {data['opening_participation']}%")
    print(f"  Dollar Volume SPY:  ${data['dollar_volume_spy']}B")
    print(f"  Institutional:      {data['institutional_signal']}")
    print(f"  Panic:              {data['panic_signal']}")
    print(f"  Volume Trend:       {data['volume_trend']}")
    print("  ✔ Done")
