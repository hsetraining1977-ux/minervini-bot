#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║   MINERVINI AI — VOLATILITY REGIME ENGINE                        ║
║   Classifies volatility environments for setup context           ║
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [VolRegime] %(message)s")
log = logging.getLogger("volatility_regime")

# ── Config ────────────────────────────────────────────────────────
OUTPUT_PATH = "/root/adaptive/volatility_regime.json"
CACHE_TTL   = 300   # 5 minutes — vol changes fast

os.makedirs("/root/adaptive", exist_ok=True)

VIX_THRESHOLDS = {
    "LOW_VOL":     (0,  15),
    "NORMAL_VOL":  (15, 25),
    "HIGH_VOL":    (25, 35),
    "EXTREME_VOL": (35, 999),
}


# ── Fetch ─────────────────────────────────────────────────────────
def _fetch_vix() -> Optional[float]:
    try:
        import yfinance as yf
        df = yf.Ticker("^VIX").history(period="2d", interval="1h")
        if df.empty:
            return None
        return float(df["Close"].iloc[-1])
    except Exception:
        return None


def _fetch_ohlcv(ticker: str, period: str = "1mo",
                 interval: str = "1d") -> Optional[object]:
    try:
        import yfinance as yf
        df = yf.Ticker(ticker).history(period=period, interval=interval)
        return df if not df.empty else None
    except Exception:
        return None


# ── ATR Calculation ───────────────────────────────────────────────
def _compute_atr(df, period: int = 14) -> Optional[float]:
    try:
        if df is None or len(df) < period + 1:
            return None
        high   = df["High"].values
        low    = df["Low"].values
        close  = df["Close"].values
        tr_list = []
        for i in range(1, len(close)):
            tr = max(
                high[i] - low[i],
                abs(high[i] - close[i-1]),
                abs(low[i]  - close[i-1])
            )
            tr_list.append(tr)
        if len(tr_list) < period:
            return None
        atr = np.mean(tr_list[-period:])
        # Normalize by price
        return round(float(atr / close[-1] * 100), 3)
    except Exception:
        return None


def _intraday_range_expansion(ticker: str = "SPY") -> Optional[float]:
    """Today's range vs 20-day avg range."""
    try:
        import yfinance as yf
        df_1d = yf.Ticker(ticker).history(period="1mo", interval="1d")
        if df_1d.empty or len(df_1d) < 5:
            return None
        avg_range = ((df_1d["High"] - df_1d["Low"]) / df_1d["Close"]).mean() * 100
        today_range = float(
            (df_1d["High"].iloc[-1] - df_1d["Low"].iloc[-1]) /
            df_1d["Close"].iloc[-1] * 100
        )
        return round(today_range / max(avg_range, 0.001), 2)
    except Exception:
        return None


def _realized_volatility(ticker: str = "SPY", window: int = 20) -> Optional[float]:
    """Annualized realized vol over window days."""
    try:
        import yfinance as yf
        df = yf.Ticker(ticker).history(period="3mo", interval="1d")
        if df.empty or len(df) < window + 1:
            return None
        log_returns = np.log(df["Close"] / df["Close"].shift(1)).dropna()
        rv = float(log_returns.iloc[-window:].std() * np.sqrt(252) * 100)
        return round(rv, 2)
    except Exception:
        return None


def _vix_term_structure() -> Optional[str]:
    """Compare VIX to VIX3M or UVXY to detect term structure."""
    try:
        import yfinance as yf
        vix  = yf.Ticker("^VIX").history(period="5d",  interval="1d")
        uvxy = yf.Ticker("UVXY").history(period="5d",  interval="1d")
        if vix.empty or uvxy.empty:
            return "NORMAL"
        vix_chg  = float(vix["Close"].pct_change().iloc[-1])
        uvxy_chg = float(uvxy["Close"].pct_change().iloc[-1])
        if uvxy_chg > vix_chg + 0.02:
            return "CONTANGO_STRESS"
        elif vix_chg > 0.05:
            return "BACKWARDATION"
        return "NORMAL"
    except Exception:
        return "UNKNOWN"


# ── Compression Detection ─────────────────────────────────────────
def _detect_compression(ticker: str = "SPY") -> Optional[str]:
    """Bollinger Band width to detect compression."""
    try:
        import yfinance as yf
        df = yf.Ticker(ticker).history(period="3mo", interval="1d")
        if df.empty or len(df) < 20:
            return None
        close = df["Close"]
        ma20  = close.rolling(20).mean()
        std20 = close.rolling(20).std()
        bb_width_now  = float((std20.iloc[-1]  / ma20.iloc[-1])  * 100)
        bb_width_hist = float((std20.iloc[-10] / ma20.iloc[-10]) * 100)
        ratio = bb_width_now / max(bb_width_hist, 0.001)
        if ratio < 0.7:
            return "COMPRESSING"
        elif ratio > 1.3:
            return "EXPANDING"
        return "STABLE"
    except Exception:
        return None


# ── Main Computation ──────────────────────────────────────────────
def compute_volatility_regime() -> dict:
    log.info("Computing volatility regime...")

    result = {
        "timestamp":             datetime.now().isoformat(),
        "volatility_regime":     "NORMAL_VOL",
        "volatility_score":      50.0,
        "expansion_probability": 0.5,
        "trend_day_probability": 0.5,
        "vix_current":           None,
        "vix_percentile":        50.0,
        "atr_normalized":        None,
        "realized_vol":          None,
        "range_expansion":       None,
        "compression_state":     None,
        "term_structure":        "NORMAL",
        "regime_confidence":     0.5,
        "setup_implications":    {},
        "data_quality":          "partial",
    }

    # ── VIX ────────────────────────────────────────────────────────
    vix = _fetch_vix()
    result["vix_current"] = round(vix, 2) if vix else None
    log.info(f"  VIX: {vix}")

    # ── ATR ────────────────────────────────────────────────────────
    spy_df = _fetch_ohlcv("SPY", "2mo", "1d")
    atr    = _compute_atr(spy_df)
    result["atr_normalized"] = atr
    log.info(f"  ATR (normalized): {atr}%")

    # ── Realized Vol ───────────────────────────────────────────────
    rv = _realized_volatility("SPY")
    result["realized_vol"] = rv
    log.info(f"  Realized Vol: {rv}%")

    # ── Intraday Range ─────────────────────────────────────────────
    rng = _intraday_range_expansion("SPY")
    result["range_expansion"] = rng
    log.info(f"  Range Expansion: {rng}x")

    # ── Compression ────────────────────────────────────────────────
    comp = _detect_compression("SPY")
    result["compression_state"] = comp
    log.info(f"  Compression: {comp}")

    # ── Term Structure ─────────────────────────────────────────────
    term = _vix_term_structure()
    result["term_structure"] = term
    time.sleep(0.3)

    # ── VIX Percentile ─────────────────────────────────────────────
    try:
        import yfinance as yf
        vix_hist = yf.Ticker("^VIX").history(period="1y", interval="1d")
        if not vix_hist.empty and vix:
            pct = float(np.percentile(vix_hist["Close"].values, 
                        np.searchsorted(np.sort(vix_hist["Close"].values), vix) 
                        / len(vix_hist["Close"]) * 100))
            result["vix_percentile"] = round(min(pct, 100), 1)
    except Exception:
        pass

    # ── Regime Classification ──────────────────────────────────────
    regime, vol_score = _classify_regime(vix, atr, rv, rng, comp)
    result["volatility_regime"] = regime
    result["volatility_score"]  = round(vol_score, 1)

    # ── Probabilities ──────────────────────────────────────────────
    result["expansion_probability"] = _expansion_prob(vol_score, comp, rng)
    result["trend_day_probability"] = _trend_day_prob(vol_score, rng, regime)

    # ── Regime Confidence ──────────────────────────────────────────
    data_points = sum(1 for x in [vix, atr, rv, rng, comp] if x is not None)
    result["regime_confidence"] = round(data_points / 5, 2)
    result["data_quality"]      = "good" if data_points >= 4 else "partial"

    # ── Setup Implications ─────────────────────────────────────────
    result["setup_implications"] = _setup_implications(regime, vol_score)

    log.info(f"Regime: {regime} | Score: {vol_score:.1f} | "
             f"Trend prob: {result['trend_day_probability']:.2f}")

    _save(result)
    return result


def _classify_regime(vix, atr, rv, rng, comp) -> tuple:
    score = 50.0
    votes = []

    if vix:
        if   vix < 12:  votes.append(10)
        elif vix < 18:  votes.append(30)
        elif vix < 25:  votes.append(55)
        elif vix < 35:  votes.append(75)
        else:           votes.append(95)

    if rv:
        if   rv < 10: votes.append(15)
        elif rv < 18: votes.append(35)
        elif rv < 25: votes.append(60)
        elif rv < 35: votes.append(80)
        else:         votes.append(95)

    if rng:
        if   rng < 0.7: votes.append(20)
        elif rng < 1.0: votes.append(40)
        elif rng < 1.5: votes.append(60)
        elif rng < 2.0: votes.append(75)
        else:           votes.append(90)

    score = float(np.mean(votes)) if votes else 50.0

    if   score < 25: regime = "LOW_VOL"
    elif score < 50: regime = "NORMAL_VOL"
    elif score < 75: regime = "HIGH_VOL"
    else:            regime = "EXTREME_VOL"

    return regime, score


def _expansion_prob(vol_score: float, comp, rng) -> float:
    prob = vol_score / 100
    if comp == "COMPRESSING": prob = min(prob + 0.15, 1.0)
    if rng and rng > 1.5:     prob = min(prob + 0.10, 1.0)
    return round(prob, 2)


def _trend_day_prob(vol_score: float, rng, regime: str) -> float:
    base = 0.4
    if regime == "NORMAL_VOL": base = 0.55
    if regime == "HIGH_VOL":   base = 0.65
    if rng and rng > 1.3:      base = min(base + 0.10, 0.90)
    return round(base, 2)


def _setup_implications(regime: str, score: float) -> dict:
    implications = {}
    if regime == "LOW_VOL":
        implications = {
            "ORB_BREAKOUT":             "REDUCED",
            "MOMENTUM_BURST_UP":        "REDUCED",
            "TIGHT_CONSOLIDATION_BREAK":"FAVORABLE",
            "VWAP_CROSS_UP":            "NEUTRAL",
            "VOLUME_SPIKE":             "REDUCED",
        }
    elif regime == "NORMAL_VOL":
        implications = {
            "ORB_BREAKOUT":             "FAVORABLE",
            "MOMENTUM_BURST_UP":        "FAVORABLE",
            "TIGHT_CONSOLIDATION_BREAK":"FAVORABLE",
            "VWAP_CROSS_UP":            "FAVORABLE",
            "VOLUME_SPIKE":             "NEUTRAL",
        }
    elif regime == "HIGH_VOL":
        implications = {
            "ORB_BREAKOUT":             "FAVORABLE",
            "MOMENTUM_BURST_UP":        "FAVORABLE",
            "TIGHT_CONSOLIDATION_BREAK":"NEUTRAL",
            "VWAP_CROSS_UP":            "NEUTRAL",
            "VOLUME_SPIKE":             "FAVORABLE",
            "ORB_BREAKDOWN":            "FAVORABLE",
        }
    else:  # EXTREME_VOL
        implications = {
            "ORB_BREAKOUT":             "DANGEROUS",
            "MOMENTUM_BURST_UP":        "DANGEROUS",
            "TIGHT_CONSOLIDATION_BREAK":"AVOID",
            "ORB_BREAKDOWN":            "FAVORABLE",
            "MOMENTUM_BURST_DOWN":      "FAVORABLE",
        }
    return implications


# ── Cache-Aware Runner ────────────────────────────────────────────
def get_volatility_regime(force: bool = False) -> dict:
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
    return compute_volatility_regime()


def _save(data: dict):
    try:
        with open(OUTPUT_PATH, "w") as f:
            json.dump(data, f, indent=2, default=str)
        log.info(f"Saved → {OUTPUT_PATH}")
    except Exception as e:
        log.error(f"Save error: {e}")


# ── Standalone ────────────────────────────────────────────────────
if __name__ == "__main__":
    print("── Volatility Regime Engine ────────────────────────")
    data = compute_volatility_regime()
    print(f"  Regime:               {data['volatility_regime']}")
    print(f"  Vol Score:            {data['volatility_score']}")
    print(f"  VIX:                  {data['vix_current']}")
    print(f"  VIX Percentile:       {data['vix_percentile']}%")
    print(f"  ATR (normalized):     {data['atr_normalized']}%")
    print(f"  Realized Vol:         {data['realized_vol']}%")
    print(f"  Range Expansion:      {data['range_expansion']}x")
    print(f"  Compression:          {data['compression_state']}")
    print(f"  Expansion Prob:       {data['expansion_probability']}")
    print(f"  Trend Day Prob:       {data['trend_day_probability']}")
    print(f"  Setup Implications:   {data['setup_implications']}")
    print("  ✔ Done")
