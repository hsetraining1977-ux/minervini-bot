#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║   MINERVINI AI — BREADTH ENGINE                                  ║
║   Measures internal market strength & participation              ║
║   ANALYTICS ONLY — NO LIVE TRADING MODIFICATION                  ║
╚══════════════════════════════════════════════════════════════════╝
"""

import json
import os
import time
import logging
from datetime import datetime, timedelta
from typing import Optional

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [Breadth] %(message)s")
log = logging.getLogger("breadth_engine")

# ── Config ────────────────────────────────────────────────────────
OUTPUT_PATH = "/root/adaptive/breadth_metrics.json"
CACHE_TTL   = 600   # 10 minutes

ETFS = ["SPY", "QQQ", "IWM", "DIA",
        "XLK", "XLF", "XLE", "XLV",
        "XLI", "XLY", "XLP", "XLU"]

os.makedirs("/root/adaptive", exist_ok=True)


# ── Data Fetch ────────────────────────────────────────────────────
def _fetch(tickers: list, period: str = "5d", interval: str = "1d") -> dict:
    """Fetch OHLCV data via yfinance with error handling."""
    try:
        import yfinance as yf
        data = yf.download(tickers, period=period, interval=interval,
                           progress=False, threads=True)
        return data
    except Exception as e:
        log.warning(f"yfinance fetch error: {e}")
        return {}


def _fetch_intraday(ticker: str, period: str = "1d", interval: str = "5m") -> Optional[object]:
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        return t.history(period=period, interval=interval)
    except Exception:
        return None


# ── VWAP Calculation ──────────────────────────────────────────────
def _compute_vwap(df) -> Optional[float]:
    try:
        if df is None or df.empty:
            return None
        typical = (df["High"] + df["Low"] + df["Close"]) / 3
        vwap = (typical * df["Volume"]).cumsum() / df["Volume"].cumsum()
        return float(vwap.iloc[-1])
    except Exception:
        return None


def _price_vs_vwap(ticker: str) -> Optional[str]:
    """Return 'above' or 'below' VWAP for given ticker."""
    try:
        df = _fetch_intraday(ticker)
        if df is None or df.empty:
            return None
        vwap  = _compute_vwap(df)
        price = float(df["Close"].iloc[-1])
        return "above" if price > vwap else "below"
    except Exception:
        return None


# ── Moving Average Analysis ───────────────────────────────────────
def _ma_position(prices: list, ma_period: int) -> Optional[str]:
    """Return 'above' or 'below' given MA."""
    try:
        if len(prices) < ma_period:
            return None
        ma = np.mean(prices[-ma_period:])
        return "above" if prices[-1] > ma else "below"
    except Exception:
        return None


# ── Breadth Metrics ───────────────────────────────────────────────
def compute_breadth() -> dict:
    log.info("Computing market breadth...")

    result = {
        "timestamp":          datetime.now().isoformat(),
        "breadth_score":      50.0,
        "participation_score":50.0,
        "trend_quality_score":50.0,
        "advance_decline":    {},
        "vwap_analysis":      {},
        "ma_analysis":        {},
        "breadth_momentum":   "NEUTRAL",
        "market_participation":"MODERATE",
        "data_quality":       "partial",
    }

    # ── VWAP Analysis ─────────────────────────────────────────────
    vwap_results = {}
    above_vwap   = 0
    total_vwap   = 0

    for etf in ETFS:
        pos = _price_vs_vwap(etf)
        if pos:
            vwap_results[etf] = pos
            total_vwap += 1
            if pos == "above":
                above_vwap += 1
        time.sleep(0.1)   # rate limit

    result["vwap_analysis"] = vwap_results
    pct_above_vwap = (above_vwap / max(total_vwap, 1)) * 100

    # ── MA Analysis ───────────────────────────────────────────────
    ma_results = {}
    above_20ma  = 0
    above_50ma  = 0
    above_200ma = 0
    total_ma    = 0

    try:
        import yfinance as yf
        for etf in ETFS:
            try:
                df = yf.Ticker(etf).history(period="1y", interval="1d")
                if df.empty:
                    continue
                closes = df["Close"].tolist()
                pos20  = _ma_position(closes, 20)
                pos50  = _ma_position(closes, 50)
                pos200 = _ma_position(closes, 200)
                ma_results[etf] = {
                    "above_20ma":  pos20 == "above",
                    "above_50ma":  pos50 == "above",
                    "above_200ma": pos200 == "above",
                }
                total_ma += 1
                if pos20  == "above": above_20ma  += 1
                if pos50  == "above": above_50ma  += 1
                if pos200 == "above": above_200ma += 1
                time.sleep(0.15)
            except Exception:
                continue
    except ImportError:
        pass

    result["ma_analysis"] = ma_results
    pct_above_20  = (above_20ma  / max(total_ma, 1)) * 100
    pct_above_50  = (above_50ma  / max(total_ma, 1)) * 100
    pct_above_200 = (above_200ma / max(total_ma, 1)) * 100

    # ── Advance/Decline Proxy ─────────────────────────────────────
    try:
        import yfinance as yf
        advances = 0
        declines = 0
        for etf in ETFS:
            try:
                df = yf.Ticker(etf).history(period="2d", interval="1d")
                if len(df) >= 2:
                    chg = df["Close"].iloc[-1] - df["Close"].iloc[-2]
                    if chg > 0: advances += 1
                    else:       declines += 1
                time.sleep(0.1)
            except Exception:
                continue
        result["advance_decline"] = {
            "advances": advances,
            "declines": declines,
            "ratio":    round(advances / max(declines, 1), 2),
        }
    except ImportError:
        result["advance_decline"] = {"advances": 0, "declines": 0, "ratio": 1.0}

    # ── Score Calculation ─────────────────────────────────────────
    ad_ratio   = result["advance_decline"].get("ratio", 1.0)
    ad_score   = min(100, ad_ratio * 50)

    breadth_score = (
        pct_above_vwap * 0.30 +
        pct_above_20   * 0.25 +
        pct_above_50   * 0.25 +
        ad_score       * 0.20
    )

    participation_score = (
        pct_above_vwap * 0.50 +
        pct_above_20   * 0.30 +
        ad_score       * 0.20
    )

    trend_quality_score = (
        pct_above_200  * 0.40 +
        pct_above_50   * 0.35 +
        pct_above_20   * 0.25
    )

    result["breadth_score"]       = round(breadth_score, 1)
    result["participation_score"] = round(participation_score, 1)
    result["trend_quality_score"] = round(trend_quality_score, 1)

    result["pct_above_vwap"]  = round(pct_above_vwap, 1)
    result["pct_above_20ma"]  = round(pct_above_20, 1)
    result["pct_above_50ma"]  = round(pct_above_50, 1)
    result["pct_above_200ma"] = round(pct_above_200, 1)

    # ── Breadth Momentum Classification ──────────────────────────
    if breadth_score >= 75:
        result["breadth_momentum"] = "STRONG_EXPANSION"
    elif breadth_score >= 60:
        result["breadth_momentum"] = "EXPANDING"
    elif breadth_score >= 40:
        result["breadth_momentum"] = "NEUTRAL"
    elif breadth_score >= 25:
        result["breadth_momentum"] = "CONTRACTING"
    else:
        result["breadth_momentum"] = "WEAK"

    # ── Participation Classification ──────────────────────────────
    if participation_score >= 70:
        result["market_participation"] = "BROAD"
    elif participation_score >= 50:
        result["market_participation"] = "MODERATE"
    elif participation_score >= 30:
        result["market_participation"] = "NARROW"
    else:
        result["market_participation"] = "VERY_NARROW"

    result["data_quality"] = "good" if total_vwap >= 8 else "partial"

    log.info(f"Breadth: {result['breadth_score']:.1f} | "
             f"Participation: {result['participation_score']:.1f} | "
             f"Trend: {result['trend_quality_score']:.1f} | "
             f"Momentum: {result['breadth_momentum']}")

    _save(result)
    return result


# ── Cache-Aware Runner ────────────────────────────────────────────
def get_breadth(force: bool = False) -> dict:
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
    return compute_breadth()


def _save(data: dict):
    try:
        with open(OUTPUT_PATH, "w") as f:
            json.dump(data, f, indent=2, default=str)
        log.info(f"Saved → {OUTPUT_PATH}")
    except Exception as e:
        log.error(f"Save error: {e}")


# ── Standalone ────────────────────────────────────────────────────
if __name__ == "__main__":
    print("── Breadth Engine ──────────────────────────────────")
    metrics = compute_breadth()
    print(f"  Breadth Score:       {metrics['breadth_score']}")
    print(f"  Participation Score: {metrics['participation_score']}")
    print(f"  Trend Quality:       {metrics['trend_quality_score']}")
    print(f"  Momentum:            {metrics['breadth_momentum']}")
    print(f"  Participation:       {metrics['market_participation']}")
    print(f"  Above VWAP:          {metrics.get('pct_above_vwap', 0)}%")
    print(f"  Above 20MA:          {metrics.get('pct_above_20ma', 0)}%")
    print(f"  Above 200MA:         {metrics.get('pct_above_200ma', 0)}%")
    print("  ✔ Done")
