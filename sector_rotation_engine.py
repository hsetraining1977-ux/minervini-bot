#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║   MINERVINI AI — SECTOR ROTATION ENGINE                          ║
║   Detects institutional sector rotation & leadership             ║
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [SectorRotation] %(message)s")
log = logging.getLogger("sector_rotation")

# ── Config ────────────────────────────────────────────────────────
OUTPUT_PATH = "/root/adaptive/sector_rotation.json"
CACHE_TTL   = 600

os.makedirs("/root/adaptive", exist_ok=True)

SECTORS = {
    "XLK":  "Technology",
    "XLF":  "Financials",
    "XLE":  "Energy",
    "XLV":  "Healthcare",
    "XLI":  "Industrials",
    "XLY":  "ConsumerDisc",
    "XLP":  "ConsumerStaples",
    "XLU":  "Utilities",
    "XLB":  "Materials",
    "XLRE": "RealEstate",
    "XLC":  "Communications",
}

SEMIS    = ["SMH", "SOXX"]
DEFENSE  = ["XLP", "XLU", "XLV"]
OFFENSE  = ["XLK", "XLY", "XLF", "XLI"]
BENCHMARK = "SPY"


# ── Fetch Helpers ─────────────────────────────────────────────────
def _get_returns(ticker: str, period: str = "1mo") -> Optional[float]:
    try:
        import yfinance as yf
        df = yf.Ticker(ticker).history(period=period, interval="1d")
        if df.empty or len(df) < 2:
            return None
        return float((df["Close"].iloc[-1] / df["Close"].iloc[0] - 1) * 100)
    except Exception:
        return None


def _get_relative_strength(ticker: str, benchmark: str = "SPY",
                            period: str = "1mo") -> Optional[float]:
    try:
        import yfinance as yf
        df_t = yf.Ticker(ticker).history(period=period, interval="1d")
        df_b = yf.Ticker(benchmark).history(period=period, interval="1d")
        if df_t.empty or df_b.empty:
            return None
        ret_t = (df_t["Close"].iloc[-1] / df_t["Close"].iloc[0] - 1) * 100
        ret_b = (df_b["Close"].iloc[-1] / df_b["Close"].iloc[0] - 1) * 100
        return round(float(ret_t - ret_b), 2)
    except Exception:
        return None


def _get_volume_ratio(ticker: str) -> Optional[float]:
    """Volume today vs 20-day average."""
    try:
        import yfinance as yf
        df = yf.Ticker(ticker).history(period="1mo", interval="1d")
        if df.empty or len(df) < 5:
            return None
        avg_vol = df["Volume"].iloc[:-1].mean()
        cur_vol = df["Volume"].iloc[-1]
        return round(float(cur_vol / max(avg_vol, 1)), 2)
    except Exception:
        return None


def _momentum_score(ticker: str) -> Optional[float]:
    """3-period momentum (5d, 20d, 60d) weighted."""
    try:
        import yfinance as yf
        df = yf.Ticker(ticker).history(period="4mo", interval="1d")
        if df.empty or len(df) < 60:
            return None
        c = df["Close"].tolist()
        r5  = (c[-1] / c[-5]  - 1) * 100 if len(c) >= 5  else 0
        r20 = (c[-1] / c[-20] - 1) * 100 if len(c) >= 20 else 0
        r60 = (c[-1] / c[-60] - 1) * 100 if len(c) >= 60 else 0
        return round(r5 * 0.4 + r20 * 0.35 + r60 * 0.25, 2)
    except Exception:
        return None


# ── Main Computation ──────────────────────────────────────────────
def compute_sector_rotation() -> dict:
    log.info("Computing sector rotation...")

    result = {
        "timestamp":            datetime.now().isoformat(),
        "sector_data":          {},
        "sector_rankings":      [],
        "leading_sectors":      [],
        "lagging_sectors":      [],
        "rotation_signal":      "NEUTRAL",
        "rotation_velocity":    "SLOW",
        "tech_leadership":      False,
        "semi_leadership":      False,
        "defensive_rotation":   False,
        "offensive_rotation":   False,
        "market_character":     "MIXED",
        "data_quality":         "partial",
    }

    sector_data = {}

    # ── Fetch per sector ─────────────────────────────────────────
    for ticker, name in SECTORS.items():
        try:
            ret_1m = _get_returns(ticker, "1mo")
            rs     = _get_relative_strength(ticker, BENCHMARK, "1mo")
            vol_r  = _get_volume_ratio(ticker)
            mom    = _momentum_score(ticker)
            time.sleep(0.2)

            sector_data[ticker] = {
                "name":              name,
                "return_1m":         ret_1m,
                "relative_strength": rs,
                "volume_ratio":      vol_r,
                "momentum_score":    mom,
                "composite_score":   _composite(ret_1m, rs, vol_r, mom),
            }
            log.info(f"  {ticker} ({name}): RS={rs}, Mom={mom}")
        except Exception as e:
            log.warning(f"  {ticker} error: {e}")
            sector_data[ticker] = {"name": name, "composite_score": 0}

    result["sector_data"] = sector_data

    # ── Rankings ─────────────────────────────────────────────────
    ranked = sorted(
        [(k, v) for k, v in sector_data.items() if v.get("composite_score") is not None],
        key=lambda x: x[1]["composite_score"],
        reverse=True,
    )

    result["sector_rankings"] = [
        {"rank": i+1, "ticker": k, "name": v["name"],
         "score": round(v["composite_score"], 2),
         "rs": v.get("relative_strength", 0)}
        for i, (k, v) in enumerate(ranked)
    ]

    leaders  = [r["ticker"] for r in result["sector_rankings"][:3]]
    laggers  = [r["ticker"] for r in result["sector_rankings"][-3:]]
    result["leading_sectors"] = leaders
    result["lagging_sectors"] = laggers

    # ── Rotation Detection ────────────────────────────────────────
    defense_scores = [sector_data.get(t, {}).get("composite_score", 0) for t in DEFENSE]
    offense_scores = [sector_data.get(t, {}).get("composite_score", 0) for t in OFFENSE]

    avg_defense = np.mean([s for s in defense_scores if s is not None] or [0])
    avg_offense = np.mean([s for s in offense_scores if s is not None] or [0])

    result["defensive_rotation"] = bool(avg_defense > avg_offense + 2)
    result["offensive_rotation"] = bool(avg_offense > avg_defense + 2)

    # ── Tech & Semi Leadership ────────────────────────────────────
    xlk_score = sector_data.get("XLK", {}).get("composite_score", 0) or 0
    result["tech_leadership"] = bool(xlk_score > 0 and "XLK" in leaders)

    semi_scores = []
    for semi in SEMIS:
        try:
            import yfinance as yf
            df = yf.Ticker(semi).history(period="1mo", interval="1d")
            if not df.empty and len(df) >= 2:
                ret = (df["Close"].iloc[-1] / df["Close"].iloc[0] - 1) * 100
                semi_scores.append(float(ret))
            time.sleep(0.2)
        except Exception:
            pass

    spy_ret = _get_returns("SPY", "1mo") or 0
    result["semi_leadership"] = bool(semi_scores and np.mean(semi_scores) > spy_ret)

    # ── Rotation Velocity ─────────────────────────────────────────
    scores = [v.get("composite_score", 0) or 0 for v in sector_data.values()]
    spread = max(scores) - min(scores) if scores else 0
    if spread > 10:
        result["rotation_velocity"] = "FAST"
    elif spread > 5:
        result["rotation_velocity"] = "MODERATE"
    else:
        result["rotation_velocity"] = "SLOW"

    # ── Rotation Signal ───────────────────────────────────────────
    if result["defensive_rotation"]:
        result["rotation_signal"] = "RISK_OFF_ROTATION"
    elif result["offensive_rotation"] and result["tech_leadership"]:
        result["rotation_signal"] = "RISK_ON_GROWTH"
    elif result["offensive_rotation"]:
        result["rotation_signal"] = "RISK_ON_BROAD"
    elif result["semi_leadership"]:
        result["rotation_signal"] = "TECH_LED_MOMENTUM"
    else:
        result["rotation_signal"] = "NEUTRAL"

    # ── Market Character ──────────────────────────────────────────
    if result["tech_leadership"] and result["semi_leadership"] and result["offensive_rotation"]:
        result["market_character"] = "MOMENTUM_GROWTH"
    elif result["defensive_rotation"]:
        result["market_character"] = "DEFENSIVE"
    elif result["offensive_rotation"]:
        result["market_character"] = "CYCLICAL_GROWTH"
    else:
        result["market_character"] = "MIXED"

    result["data_quality"] = "good" if len(sector_data) >= 8 else "partial"

    log.info(f"Rotation: {result['rotation_signal']} | "
             f"Leaders: {leaders} | Velocity: {result['rotation_velocity']}")

    _save(result)
    return result


def _composite(ret, rs, vol_ratio, momentum) -> float:
    parts = []
    if ret       is not None: parts.append(("ret", ret, 0.25))
    if rs        is not None: parts.append(("rs",  rs,  0.35))
    if vol_ratio is not None: parts.append(("vol", (vol_ratio - 1) * 10, 0.15))
    if momentum  is not None: parts.append(("mom", momentum, 0.25))
    if not parts:
        return 0.0
    total_w = sum(w for _, _, w in parts)
    return sum(v * w for _, v, w in parts) / total_w


# ── Cache-Aware Runner ────────────────────────────────────────────
def get_sector_rotation(force: bool = False) -> dict:
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
    return compute_sector_rotation()


def _save(data: dict):
    try:
        with open(OUTPUT_PATH, "w") as f:
            json.dump(data, f, indent=2, default=str)
        log.info(f"Saved → {OUTPUT_PATH}")
    except Exception as e:
        log.error(f"Save error: {e}")


# ── Standalone ────────────────────────────────────────────────────
if __name__ == "__main__":
    print("── Sector Rotation Engine ──────────────────────────")
    data = compute_sector_rotation()
    print(f"  Rotation Signal:  {data['rotation_signal']}")
    print(f"  Market Character: {data['market_character']}")
    print(f"  Tech Leadership:  {data['tech_leadership']}")
    print(f"  Semi Leadership:  {data['semi_leadership']}")
    print(f"  Defensive:        {data['defensive_rotation']}")
    print(f"  Leading:          {data['leading_sectors']}")
    print(f"  Lagging:          {data['lagging_sectors']}")
    print(f"  Velocity:         {data['rotation_velocity']}")
    print("  ✔ Done")
