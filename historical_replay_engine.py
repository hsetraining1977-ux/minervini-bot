#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║   MINERVINI AI — HISTORICAL REPLAY ENGINE                        ║
║   Primary: Alpaca Historical API (years of minute data)          ║
║   Fallback: Yahoo Finance (daily bars only)                      ║
║   HISTORICAL LEARNING ONLY — NO LIVE TRADING                     ║
╚══════════════════════════════════════════════════════════════════╝
"""

import sys
import os
sys.path.insert(0, "/root")

import json
import argparse
import numpy as np
import pandas as pd
import requests
import yfinance as yf
from datetime import datetime, timedelta
from typing import Optional

import setup_replay_library    as slib
import regime_replay_engine    as rengine
import adaptive_memory_builder as ambuilder

# ── Storage ───────────────────────────────────────────────────────
LOG_DIR    = "/root/adaptive/history"
MEMORY_DIR = "/root/adaptive/memory"
os.makedirs(LOG_DIR,    exist_ok=True)
os.makedirs(MEMORY_DIR, exist_ok=True)

PROGRESS_PATH = f"{MEMORY_DIR}/replay_progress.json"

# ── Watchlists ────────────────────────────────────────────────────
WATCHLISTS = {
    "tech_leaders":   ["NVDA","MSFT","AAPL","GOOGL","META","AMD","TSLA","AVGO","ORCL","CRM"],
    "growth_leaders": ["NVDA","TSLA","SMCI","PLTR","MSTR","CELH","AXON","CRWD","SNOW","ARM"],
    "momentum":       ["NVDA","TSLA","SMCI","PLTR","AXON","CRWD","DKNG","COIN","MSTR","ARM"],
    "mega_cap":       ["AAPL","MSFT","AMZN","GOOGL","META","NVDA","JPM","V","MA","UNH"],
    "sector_etfs":    ["XLK","XLF","XLE","XLV","XLI","XLB","XLU","XLRE","XLP","XLY"],
    "breadth":        ["SPY","QQQ","IWM","MDY"],
}

# ══════════════════════════════════════════════════════════════════
# DATA LOADERS
# ══════════════════════════════════════════════════════════════════

def _alpaca_keys():
    try:
        from config import ALPACA_API_KEY, ALPACA_SECRET_KEY
        return ALPACA_API_KEY, ALPACA_SECRET_KEY
    except Exception:
        return None, None


def _load_alpaca(
    symbol:    str,
    start:     str,
    end:       str,
    timeframe: str = "5Min",
) -> Optional[pd.DataFrame]:
    """
    Alpaca Historical Bars API.
    Supports years of 1Min/5Min data — no 60-day limit.
    """
    api_key, secret = _alpaca_keys()
    if not api_key:
        return None

    headers = {
        "APCA-API-KEY-ID":     api_key,
        "APCA-API-SECRET-KEY": secret,
    }
    url    = f"https://data.alpaca.markets/v2/stocks/{symbol}/bars"
    params = {
        "start":      start + "T09:30:00Z",
        "end":        end   + "T16:00:00Z",
        "timeframe":  timeframe,
        "limit":      10000,
        "feed":       "iex",
        "adjustment": "split",
    }

    all_bars = []
    try:
        while True:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            if resp.status_code != 200:
                return None
            data = resp.json()
            bars = data.get("bars", [])
            if not bars:
                break
            all_bars.extend(bars)
            token = data.get("next_page_token")
            if not token:
                break
            params["page_token"] = token

        if not all_bars:
            return None

        df = pd.DataFrame(all_bars)
        df["t"] = pd.to_datetime(df["t"], utc=True).dt.tz_convert("America/New_York")
        df = df.set_index("t")
        df = df.rename(columns={"o":"Open","h":"High","l":"Low","c":"Close","v":"Volume"})
        df = df[["Open","High","Low","Close","Volume"]].sort_index()
        return df

    except Exception:
        return None


def _load_yahoo_daily(symbol: str, start: str, end: str) -> Optional[pd.DataFrame]:
    """Yahoo Finance daily — works for any historical date"""
    try:
        df = yf.download(
            symbol, start=start, end=end,
            interval="1d", progress=False, auto_adjust=True,
        )
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df if not df.empty else None
    except Exception:
        return None


def load_bars(symbol: str, date: str, interval: str = "5m") -> Optional[pd.DataFrame]:
    """
    Smart loader:
    1. Try Alpaca (supports years of minute data)
    2. Fallback Yahoo daily (for any date range)
    """
    tf_map = {"1m":"1Min","5m":"5Min","15m":"15Min","1h":"1Hour","1d":"1Day"}
    alpaca_tf = tf_map.get(interval, "5Min")

    end_str = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

    # Try Alpaca first
    df = _load_alpaca(symbol, date, end_str, alpaca_tf)
    if df is not None and not df.empty:
        if interval != "1d":
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
            df = df[df.index.date == target_date]
        return df if not df.empty else None

    # Fallback: Yahoo daily (works for all dates)
    df = _load_yahoo_daily(symbol, date, end_str)
    if df is not None and not df.empty:
        return df

    return None

# ══════════════════════════════════════════════════════════════════
# INDICATORS
# ══════════════════════════════════════════════════════════════════

def _vwap(df: pd.DataFrame) -> pd.Series:
    if "Volume" not in df.columns:
        return pd.Series([0.0] * len(df), index=df.index)
    tp  = (df["High"] + df["Low"] + df["Close"]) / 3
    cvol= df["Volume"].cumsum()
    return (tp * df["Volume"]).cumsum() / cvol.replace(0, np.nan)

def _atr(df: pd.DataFrame, period: int = 14) -> float:
    if len(df) < 2:
        return float(df["High"].iloc[-1] - df["Low"].iloc[-1]) if len(df) > 0 else 1.0
    return float((df["High"] - df["Low"]).tail(period).mean())

# ══════════════════════════════════════════════════════════════════
# SETUP DETECTION
# ══════════════════════════════════════════════════════════════════

def detect_setups(
    candle: pd.Series, prev: pd.DataFrame,
    vwap: float, avg_vol: float, atr: float,
) -> list:
    setups = []
    if len(prev) < 3:
        return setups

    close      = float(candle["Close"])
    volume     = float(candle.get("Volume", 0))
    prev_close = float(prev["Close"].iloc[-1])
    pct        = (close - prev_close) / prev_close * 100 if prev_close > 0 else 0

    # ORB
    if len(prev) >= 6:
        orb_h = float(prev.iloc[:6]["High"].max())
        orb_l = float(prev.iloc[:6]["Low"].min())
        if close > orb_h * 1.002:
            setups.append("ORB_BREAKOUT")
        elif close < orb_l * 0.998:
            setups.append("ORB_BREAKDOWN")

    # Volume Spike
    if avg_vol > 0 and volume > avg_vol * 2:
        setups.append("VOLUME_SPIKE")

    # VWAP Cross
    if vwap > 0:
        if prev_close < vwap and close > vwap:
            setups.append("VWAP_CROSS_UP")
        elif prev_close > vwap and close < vwap:
            setups.append("VWAP_CROSS_DOWN")

    # Momentum Burst
    if pct > 1.5:
        setups.append("MOMENTUM_BURST_UP")
    elif pct < -1.5:
        setups.append("MOMENTUM_BURST_DOWN")

    # Tight Consolidation
    if len(prev) >= 8:
        rh = float(prev.tail(8)["High"].max())
        rl = float(prev.tail(8)["Low"].min())
        rm = float(prev.tail(8)["Close"].mean())
        if rm > 0 and (rh - rl) / rm < 0.015 and close > rh:
            setups.append("TIGHT_CONSOLIDATION_BREAK")

    # Relative Strength
    if pct > 1.0 and volume > avg_vol * 1.3:
        setups.append("RELATIVE_STRENGTH_LEADER")

    return setups

# ══════════════════════════════════════════════════════════════════
# TRADE SIMULATOR
# ══════════════════════════════════════════════════════════════════

def simulate_trade(
    entry: float, setups: list,
    future: pd.DataFrame, regime: str, atr: float,
) -> Optional[dict]:
    if not setups or len(future) < 3:
        return None

    direction = "SHORT" if any("DOWN" in s or "BREAKDOWN" in s for s in setups) else "LONG"

    # ATR-based R/R
    if atr > 0 and entry > 0:
        stop_pct   = min(0.03, (atr * 1.5) / entry)
        target_pct = stop_pct * 2.0
    else:
        stop_pct, target_pct = 0.02, 0.04

    stop   = entry * (1 - stop_pct) if direction == "LONG" else entry * (1 + stop_pct)
    target = entry * (1 + target_pct) if direction == "LONG" else entry * (1 - target_pct)

    result     = "TIMEOUT"
    exit_price = float(future["Close"].iloc[-1])
    hold_bars  = len(future)

    for i, (_, fc) in enumerate(future.iterrows()):
        lo, hi = float(fc["Low"]), float(fc["High"])
        if direction == "LONG":
            if lo <= stop:
                result, exit_price, hold_bars = "STOP_LOSS", stop, i+1; break
            if hi >= target:
                result, exit_price, hold_bars = "TARGET_HIT", target, i+1; break
        else:
            if hi >= stop:
                result, exit_price, hold_bars = "STOP_LOSS", stop, i+1; break
            if lo <= target:
                result, exit_price, hold_bars = "TARGET_HIT", target, i+1; break

    pnl_pct = ((exit_price - entry) / entry if direction == "LONG"
               else (entry - exit_price) / entry) * 100
    won = pnl_pct > 0
    rr  = abs(pnl_pct) / (stop_pct * 100) if won and stop_pct > 0 else 0

    return {
        "direction":   direction,
        "entry_price": round(entry, 4),
        "exit_price":  round(exit_price, 4),
        "result":      result,
        "pnl_pct":     round(pnl_pct, 4),
        "hold_bars":   hold_bars,
        "rr_achieved": round(rr, 3),
        "won":         won,
        "setups":      setups,
        "regime":      regime,
    }

# ══════════════════════════════════════════════════════════════════
# SINGLE SYMBOL REPLAY
# ══════════════════════════════════════════════════════════════════

def replay_symbol(
    symbol: str, date: str, interval: str = "5m",
    regime: str = None, verbose: bool = False,
) -> dict:
    result = {
        "symbol": symbol, "date": date, "interval": interval,
        "regime": regime or "UNKNOWN", "candles": 0,
        "setups_found": 0, "trades": 0, "wins": 0,
        "losses": 0, "total_pnl": 0.0, "source": "none",
    }
    try:
        df = load_bars(symbol, date, interval)
        if df is None or len(df) < 10:
            return result

        result["source"] = "alpaca" if "alpaca" in str(type(df)) else "yahoo"

        if not regime or regime == "UNKNOWN":
            regime = rengine.classify_date(date).get("regime", "NEUTRAL")
            result["regime"] = regime

        vwap_s  = _vwap(df)
        avg_vol = float(df["Volume"].mean()) if "Volume" in df.columns else 0
        atr_val = _atr(df)
        atr_pct = (atr_val / float(df["Close"].mean()) * 100) if float(df["Close"].mean()) > 0 else 2
        vol_ctx = "HIGH" if atr_pct > 4 else "NORMAL" if atr_pct > 2 else "LOW"
        result["candles"] = len(df)

        for i in range(6, len(df) - 3):
            candle = df.iloc[i]
            prev   = df.iloc[max(0, i-20):i]
            future = df.iloc[i+1:min(i+13, len(df))]
            vwap   = float(vwap_s.iloc[i]) if not pd.isna(vwap_s.iloc[i]) else 0

            vol    = float(candle.get("Volume", 0))
            v_ctx  = "EXTREME" if avg_vol > 0 and vol > avg_vol*3 else \
                     "HIGH"    if avg_vol > 0 and vol > avg_vol*2 else "NORMAL"

            setups = detect_setups(candle, prev, vwap, avg_vol, atr_val)
            if not setups:
                continue
            result["setups_found"] += 1

            primary = [s for s in setups if s in slib.SETUP_CATALOG]
            if not primary:
                continue

            trade = simulate_trade(float(candle["Close"]), primary, future, regime, atr_val)
            if not trade:
                continue

            for setup in primary:
                slib.record_outcome(
                    setup=setup, won=trade["won"], pnl_pct=trade["pnl_pct"],
                    regime=regime, hold_bars=trade["hold_bars"],
                    rr_achieved=trade["rr_achieved"],
                    volume_ctx=v_ctx, volatility=vol_ctx, source="historical",
                )
                rengine.record_regime_setup_performance(
                    regime=regime, setup=setup,
                    won=trade["won"], pnl_pct=trade["pnl_pct"], source="historical",
                )

            result["trades"]    += 1
            result["total_pnl"] += trade["pnl_pct"]
            result["wins"]      += int(trade["won"])
            result["losses"]    += int(not trade["won"])

            if verbose and result["trades"] <= 2:
                e = "🟢" if trade["won"] else "🔴"
                print(f"    {e} {symbol} {primary[0]} @ ${trade['entry_price']:.2f} "
                      f"→ {trade['result']} {trade['pnl_pct']:+.2f}%")

    except Exception as e:
        if verbose:
            print(f"    ✗ {symbol} {date}: {e}")
    return result

# ══════════════════════════════════════════════════════════════════
# BATCH REPLAY
# ══════════════════════════════════════════════════════════════════

def replay_batch(
    symbols: list, start_date: str, end_date: str,
    interval: str = "5m", verbose: bool = False,
) -> dict:
    print(f"\n{'='*60}")
    print(f"  HISTORICAL REPLAY | {start_date} → {end_date}")
    print(f"  Symbols: {len(symbols)} | Interval: {interval}")
    print(f"  Source: Alpaca (primary) + Yahoo (fallback)")
    print(f"  ⚠  LEARNING ONLY — NO LIVE TRADING")
    print(f"{'='*60}\n")

    total_trades = total_setups = total_candles = sessions = 0
    current = datetime.strptime(start_date, "%Y-%m-%d")
    end     = datetime.strptime(end_date,   "%Y-%m-%d")

    while current <= end:
        if current.weekday() >= 5:
            current += timedelta(days=1)
            continue
        date_str = current.strftime("%Y-%m-%d")
        regime   = rengine.classify_date(date_str).get("regime", "NEUTRAL")
        day_t = day_s = 0

        for symbol in symbols:
            r = replay_symbol(symbol, date_str, interval, regime, verbose)
            day_t         += r["trades"]
            day_s         += r["setups_found"]
            total_candles += r["candles"]

        total_trades += day_t
        total_setups += day_s
        sessions     += 1
        if day_t > 0:
            print(f"  {date_str} [{regime:16s}] Trades:{day_t:3d} Setups:{day_s:3d}")
        current += timedelta(days=1)

    lib = slib.get_library_summary()
    slib.generate_expectancy_report()
    slib.generate_rankings()
    ambuilder.ingest_from_library()
    ambuilder.generate_suggestions()
    ambuilder.track_confidence_evolution()

    summary = {
        "timestamp": datetime.now().isoformat(),
        "start_date": start_date, "end_date": end_date,
        "symbols": len(symbols), "sessions": sessions,
        "total_candles": total_candles, "total_setups": total_setups,
        "total_trades": total_trades, "setups_tracked": lib["total_trades"],
        "best_setup": lib["best_setup"],
    }
    _save_progress(summary)

    print(f"\n  ── COMPLETE | Trades:{total_trades} | "
          f"Tracked:{lib['total_trades']} | Best:{lib['best_setup']}")
    return summary

def _save_progress(summary):
    try:
        data = []
        if os.path.exists(PROGRESS_PATH):
            with open(PROGRESS_PATH) as f:
                data = json.load(f)
            if not isinstance(data, list):
                data = [data]
        data.append(summary)
        with open(PROGRESS_PATH, "w") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception:
        pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol",    type=str)
    parser.add_argument("--watchlist", type=str, choices=list(WATCHLISTS.keys()))
    parser.add_argument("--start",     type=str, required=True)
    parser.add_argument("--end",       type=str, default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--interval",  type=str, default="5m",
                        choices=["1m","5m","15m","1h","1d"])
    parser.add_argument("--verbose",   action="store_true")
    args = parser.parse_args()

    symbols = (
        [args.symbol.upper()] if args.symbol else
        WATCHLISTS.get(args.watchlist, WATCHLISTS["tech_leaders"])
    )
    replay_batch(symbols, args.start, args.end, args.interval, args.verbose)
