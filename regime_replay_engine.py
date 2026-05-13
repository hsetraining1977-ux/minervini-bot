#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║   MINERVINI AI — REGIME REPLAY ENGINE                            ║
║   Historical Regime Classification & Performance Tracking        ║
║   HISTORICAL LEARNING ONLY — NO LIVE TRADING                     ║
╚══════════════════════════════════════════════════════════════════╝
"""

import json
import os
import numpy as np
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional

# ── Storage ───────────────────────────────────────────────────────
MEMORY_DIR  = "/root/adaptive/memory"
HISTORY_DIR = "/root/adaptive/history"
os.makedirs(MEMORY_DIR,  exist_ok=True)
os.makedirs(HISTORY_DIR, exist_ok=True)

REGIME_PERF_PATH   = f"{MEMORY_DIR}/regime_performance.json"
REGIME_HIST_PATH   = f"{HISTORY_DIR}/regime_history.json"

# ── Regime Definitions ────────────────────────────────────────────
REGIMES = [
    "STRONG_RISK_ON",
    "RISK_ON",
    "NEUTRAL",
    "RISK_OFF",
    "PANIC",
    "CHOPPY",
]

# ── Regime Classifier ─────────────────────────────────────────────
def classify_regime(
    spy_pct_chg:  float,   # SPY 5-day change %
    qqq_pct_chg:  float,   # QQQ 5-day change %
    vix:          float,   # Current VIX
    spy_vs_sma20: float,   # SPY vs 20-day SMA (+ = above)
    volume_ratio: float,   # Current vol / avg vol
    atr_ratio:    float,   # Current ATR / avg ATR (volatility)
    breadth_pct:  float,   # % stocks above 20MA (0-100)
) -> str:
    """
    Classify market regime from multiple indicators.
    Returns one of: STRONG_RISK_ON, RISK_ON, NEUTRAL,
                    RISK_OFF, PANIC, CHOPPY
    """
    score = 0

    # Trend component (0-40 pts)
    if spy_pct_chg > 2:       score += 20
    elif spy_pct_chg > 0.5:   score += 10
    elif spy_pct_chg < -2:    score -= 20
    elif spy_pct_chg < -0.5:  score -= 10

    if qqq_pct_chg > 2:       score += 10
    elif qqq_pct_chg > 0.5:   score += 5
    elif qqq_pct_chg < -2:    score -= 10
    elif qqq_pct_chg < -0.5:  score -= 5

    # Above/below SMA
    if spy_vs_sma20 > 2:      score += 10
    elif spy_vs_sma20 > 0:    score += 5
    elif spy_vs_sma20 < -2:   score -= 10
    elif spy_vs_sma20 < 0:    score -= 5

    # VIX component (0-30 pts)
    if vix < 14:       score += 15
    elif vix < 18:     score += 10
    elif vix < 22:     score += 0
    elif vix < 28:     score -= 10
    elif vix < 35:     score -= 20
    else:              score -= 30   # PANIC territory

    # Breadth component (0-20 pts)
    if breadth_pct > 70:   score += 10
    elif breadth_pct > 50: score += 5
    elif breadth_pct < 30: score -= 10
    elif breadth_pct < 40: score -= 5

    # Volatility (choppiness)
    is_choppy = (atr_ratio > 1.5 and abs(spy_pct_chg) < 1.0)

    # PANIC override
    if vix > 35 or spy_pct_chg < -5:
        return "PANIC"

    # CHOPPY override
    if is_choppy and abs(score) < 15:
        return "CHOPPY"

    # Score → Regime
    if score >= 35:    return "STRONG_RISK_ON"
    elif score >= 15:  return "RISK_ON"
    elif score >= -10: return "NEUTRAL"
    elif score >= -25: return "RISK_OFF"
    else:              return "PANIC"

# ── Load Market Data ──────────────────────────────────────────────
def _load_market_context(date: str) -> Optional[dict]:
    """Load SPY, QQQ, VIX data for regime classification"""
    try:
        end   = datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)
        start = end - timedelta(days=30)

        tickers = ["SPY", "QQQ", "^VIX", "IWM"]
        data = yf.download(
            tickers, start=start, end=end,
            interval="1d", progress=False, auto_adjust=True,
        )

        if data.empty:
            return None

        close = data["Close"] if "Close" in data else data
        if isinstance(close.columns, pd.MultiIndex):
            close = close.droplevel(0, axis=1)

        # Filter to available date
        if date not in [str(d.date()) for d in close.index]:
            return None

        spy = close["SPY"].dropna()
        qqq = close["QQQ"].dropna() if "QQQ" in close else spy
        vix = close["^VIX"].dropna() if "^VIX" in close else pd.Series([20.0])

        if len(spy) < 5:
            return None

        spy_5d   = (spy.iloc[-1] - spy.iloc[-6]) / spy.iloc[-6] * 100 if len(spy) >= 6 else 0
        qqq_5d   = (qqq.iloc[-1] - qqq.iloc[-6]) / qqq.iloc[-6] * 100 if len(qqq) >= 6 else 0
        sma20    = spy.tail(20).mean()
        vs_sma20 = (spy.iloc[-1] - sma20) / sma20 * 100
        vix_val  = float(vix.iloc[-1]) if len(vix) > 0 else 20.0

        # ATR ratio
        if "SPY" in close and len(spy) >= 14:
            hi = data["High"]["SPY"].dropna() if "High" in data else spy
            lo = data["Low"]["SPY"].dropna()  if "Low"  in data else spy
            tr = (hi - lo).tail(14)
            atr_curr = float(tr.iloc[-1]) if len(tr) > 0 else 1.0
            atr_avg  = float(tr.mean())   if len(tr) > 0 else 1.0
            atr_ratio = atr_curr / atr_avg if atr_avg > 0 else 1.0
        else:
            atr_ratio = 1.0

        # Breadth proxy: % of SPY, QQQ, IWM above their 20MA
        breadth_signals = 0
        breadth_count   = 0
        for ticker in ["SPY", "QQQ", "IWM"]:
            if ticker in close:
                s = close[ticker].dropna()
                if len(s) >= 20:
                    breadth_count += 1
                    if s.iloc[-1] > s.tail(20).mean():
                        breadth_signals += 1
        breadth_pct = (breadth_signals / breadth_count * 100) if breadth_count > 0 else 50

        return {
            "date":         date,
            "spy_5d":       round(spy_5d, 3),
            "qqq_5d":       round(qqq_5d, 3),
            "vix":          round(vix_val, 2),
            "spy_vs_sma20": round(vs_sma20, 3),
            "volume_ratio": 1.0,
            "atr_ratio":    round(atr_ratio, 3),
            "breadth_pct":  round(breadth_pct, 1),
        }

    except Exception as e:
        return None

# ── Classify Single Date ──────────────────────────────────────────
def classify_date(date: str) -> dict:
    ctx = _load_market_context(date)
    if not ctx:
        return {"date": date, "regime": "UNKNOWN", "context": {}}

    regime = classify_regime(
        spy_pct_chg  = ctx["spy_5d"],
        qqq_pct_chg  = ctx["qqq_5d"],
        vix          = ctx["vix"],
        spy_vs_sma20 = ctx["spy_vs_sma20"],
        volume_ratio = ctx["volume_ratio"],
        atr_ratio    = ctx["atr_ratio"],
        breadth_pct  = ctx["breadth_pct"],
    )

    return {
        "date":    date,
        "regime":  regime,
        "context": ctx,
    }

# ── Classify Date Range ───────────────────────────────────────────
def classify_date_range(
    start_date: str,
    end_date:   str,
    save:       bool = True,
) -> list:
    """Classify every trading day in a date range"""
    results = []
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end   = datetime.strptime(end_date,   "%Y-%m-%d")

    # Load SPY for the full range at once (efficient)
    try:
        spy_data = yf.download(
            ["SPY", "QQQ", "^VIX", "IWM"],
            start=start - timedelta(days=30),
            end=end + timedelta(days=1),
            interval="1d", progress=False, auto_adjust=True,
        )
    except Exception:
        spy_data = pd.DataFrame()

    current = start
    while current <= end:
        date_str = current.strftime("%Y-%m-%d")

        # Skip weekends
        if current.weekday() < 5:
            result = classify_date(date_str)
            results.append(result)
            if result["regime"] != "UNKNOWN":
                _save_regime_to_history(result)

        current += timedelta(days=1)

    if save and results:
        _update_regime_performance(results)

    return results

# ── Record Setup Performance by Regime ───────────────────────────
def record_regime_setup_performance(
    regime:  str,
    setup:   str,
    won:     bool,
    pnl_pct: float,
    source:  str = "replay",
) -> bool:
    perf = _load_regime_perf()

    if regime not in perf:
        perf[regime] = {
            "regime":       regime,
            "total_trades": 0,
            "wins":         0,
            "losses":       0,
            "total_pnl":    0.0,
            "win_rate":     0.0,
            "by_setup":     {},
            "last_updated": None,
        }

    r = perf[regime]
    r["total_trades"] += 1
    r["total_pnl"]    += pnl_pct
    if won:
        r["wins"] += 1
    else:
        r["losses"] += 1
    r["win_rate"] = round(r["wins"] / r["total_trades"] * 100, 2)

    # By setup breakdown
    if setup not in r["by_setup"]:
        r["by_setup"][setup] = {
            "total": 0, "wins": 0, "losses": 0,
            "total_pnl": 0.0, "win_rate": 0.0,
        }
    s = r["by_setup"][setup]
    s["total"]     += 1
    s["total_pnl"] += pnl_pct
    if won:
        s["wins"] += 1
    else:
        s["losses"] += 1
    s["win_rate"] = round(s["wins"] / s["total"] * 100, 1)

    r["last_updated"] = datetime.now().isoformat()
    perf[regime] = r

    return _save_regime_perf(perf)

# ── Regime Queries ────────────────────────────────────────────────
def get_best_setups_for_regime(regime: str, top: int = 5) -> list:
    perf = _load_regime_perf()
    if regime not in perf:
        return []
    by_setup = perf[regime].get("by_setup", {})
    qualified = {k: v for k, v in by_setup.items() if v.get("total", 0) >= 5}
    return sorted(
        [{"setup": k, "win_rate": v["win_rate"],
          "total": v["total"], "pnl": v["total_pnl"]}
         for k, v in qualified.items()],
        key=lambda x: x["win_rate"], reverse=True,
    )[:top]

def get_regime_summary() -> dict:
    perf = _load_regime_perf()
    summary = {}
    for regime, data in perf.items():
        total = data.get("total_trades", 0)
        summary[regime] = {
            "total_trades": total,
            "win_rate":     data.get("win_rate", 0),
            "avg_pnl":      round(data.get("total_pnl", 0) / max(total, 1), 3),
            "best_setup":   _best_setup_in_regime(data.get("by_setup", {})),
        }
    return summary

def _best_setup_in_regime(by_setup: dict) -> str:
    qualified = {k: v for k, v in by_setup.items() if v.get("total", 0) >= 3}
    if not qualified:
        return "N/A"
    return max(qualified.items(),
               key=lambda x: x[1].get("win_rate", 0),
               default=("N/A", {}))[0]

# ── Private Helpers ───────────────────────────────────────────────
def _load_regime_perf() -> dict:
    try:
        if os.path.exists(REGIME_PERF_PATH):
            with open(REGIME_PERF_PATH) as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _save_regime_perf(perf: dict) -> bool:
    try:
        with open(REGIME_PERF_PATH, "w") as f:
            json.dump(perf, f, indent=2, default=str)
        return True
    except Exception:
        return False

def _save_regime_to_history(result: dict) -> bool:
    history = []
    try:
        if os.path.exists(REGIME_HIST_PATH):
            with open(REGIME_HIST_PATH) as f:
                history = json.load(f)
    except Exception:
        pass
    history.append(result)
    if len(history) > 2000:
        history = history[-2000:]
    try:
        with open(REGIME_HIST_PATH, "w") as f:
            json.dump(history, f, indent=2, default=str)
        return True
    except Exception:
        return False

def _update_regime_performance(results: list):
    perf = _load_regime_perf()
    for r in results:
        regime = r.get("regime", "UNKNOWN")
        if regime == "UNKNOWN":
            continue
        if regime not in perf:
            perf[regime] = {
                "regime": regime, "days_classified": 0,
                "total_trades": 0, "wins": 0, "losses": 0,
                "total_pnl": 0.0, "win_rate": 0.0,
                "by_setup": {}, "last_updated": None,
            }
        perf[regime]["days_classified"] = perf[regime].get("days_classified", 0) + 1
        perf[regime]["last_updated"] = datetime.now().isoformat()
    _save_regime_perf(perf)


if __name__ == "__main__":
    print("── Regime Replay Engine ────────────────────────────")
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"  Classifying today ({today})...")
    result = classify_date(today)
    print(f"  Regime: {result['regime']}")
    ctx = result.get("context", {})
    if ctx:
        print(f"  VIX: {ctx.get('vix', 'N/A')}")
        print(f"  SPY 5d: {ctx.get('spy_5d', 'N/A')}%")
        print(f"  Breadth: {ctx.get('breadth_pct', 'N/A')}%")
    print("  ✔ Regime Engine ready")
