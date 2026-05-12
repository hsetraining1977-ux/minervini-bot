#!/usr/bin/env python3
"""
Institutional Intraday Tactical Framework
==========================================
Layer 1: Liquidity & Float Intelligence
Layer 2: Opening Range Breakout (ORB)
Layer 3: Live Market Regime Filter
Layer 4: Final Institutional Rating
Layer 5: Volume Spike Validation
Layer 6: Multi-Timeframe Alignment
Layer 7: ATR Risk Engine
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings("ignore")

WEIGHTS = {
    "gap":               20,
    "rv":                25,
    "vwap":              20,
    "momentum":          20,
    "relative_strength": 15,
}

def calculate_vwap(df):
    try:
        df = df.copy()
        df["tp"]  = (df["High"] + df["Low"] + df["Close"]) / 3
        df["tpv"] = df["tp"] * df["Volume"]
        return round(float((df["tpv"].cumsum() / df["Volume"].cumsum()).iloc[-1]), 4)
    except:
        return 0.0

def get_market_regime() -> dict:
    try:
        spy_intraday = yf.Ticker("SPY").history(period="1d", interval="5m")
        vix_data     = yf.Ticker("^VIX").history(period="1d", interval="1d")
        if spy_intraday.empty:
            return {"regime": "NEUTRAL", "spy_above_vwap": False, "spy_momentum": 0, "vix_level": 20, "regime_multiplier": 0.85}
        spy_vwap       = calculate_vwap(spy_intraday)
        spy_price      = float(spy_intraday["Close"].iloc[-1])
        spy_open       = float(spy_intraday["Open"].iloc[0])
        spy_above_vwap = spy_price > spy_vwap
        spy_momentum   = (spy_price - spy_open) / spy_open * 100
        vix_level      = float(vix_data["Close"].iloc[-1]) if not vix_data.empty else 20
        risk_off = (not spy_above_vwap and spy_momentum < -0.3 and vix_level > 22)
        risk_on  = (spy_above_vwap and spy_momentum > 0.3 and vix_level < 20)
        if risk_off:   regime, multiplier = "RISK_OFF", 0.50
        elif risk_on:  regime, multiplier = "RISK_ON",  1.10
        else:          regime, multiplier = "NEUTRAL",  0.85
        print(f"[Regime] {regime} | SPY VWAP: {'✅' if spy_above_vwap else '❌'} | Mom: {spy_momentum:+.2f}% | VIX: {vix_level:.1f}")
        return {"regime": regime, "spy_above_vwap": spy_above_vwap, "spy_momentum": round(spy_momentum, 2), "vix_level": round(vix_level, 1), "regime_multiplier": multiplier}
    except Exception as e:
        print(f"[Regime ERROR] {e}")
        return {"regime": "NEUTRAL", "spy_above_vwap": False, "spy_momentum": 0, "vix_level": 20, "regime_multiplier": 0.85}

def check_liquidity(symbol: str) -> dict:
    try:
        info         = yf.Ticker(symbol).info
        price        = info.get("currentPrice") or info.get("regularMarketPrice", 0)
        avg_vol      = info.get("averageVolume", 0)
        market_cap   = info.get("marketCap", 0)
        float_shares = info.get("floatShares", 0)
        is_penny  = price < 5
        is_liquid = avg_vol >= 1_000_000 and price >= 5
        if is_penny:                bonus = -100
        elif not is_liquid:         bonus = -40
        elif avg_vol >= 10_000_000: bonus = 5
        else:                       bonus = 0
        return {"is_liquid": is_liquid, "is_penny_stock": is_penny, "price": round(price, 2), "avg_volume": avg_vol, "market_cap": market_cap, "float_shares": float_shares, "liquidity_score_bonus": bonus}
    except Exception as e:
        print(f"[Liquidity ERROR] {symbol}: {e}")
        return {"is_liquid": True, "is_penny_stock": False, "liquidity_score_bonus": 0, "price": 0, "avg_volume": 0, "market_cap": 0, "float_shares": 0}

def check_orb(intraday, orb_candles=3) -> dict:
    try:
        if len(intraday) < orb_candles + 1:
            return {"orb_breakout": False, "orb_breakdown": False, "orb_high": 0, "orb_low": 0, "orb_bonus": 0}
        orb_high   = float(intraday.iloc[:orb_candles]["High"].max())
        orb_low    = float(intraday.iloc[:orb_candles]["Low"].min())
        curr_price = float(intraday["Close"].iloc[-1])
        orb_breakout  = curr_price > orb_high
        orb_breakdown = curr_price < orb_low
        bonus = 15 if orb_breakout else (-15 if orb_breakdown else 0)
        return {"orb_breakout": orb_breakout, "orb_breakdown": orb_breakdown, "orb_high": round(orb_high, 2), "orb_low": round(orb_low, 2), "orb_bonus": bonus}
    except Exception as e:
        print(f"[ORB ERROR] {e}")
        return {"orb_breakout": False, "orb_breakdown": False, "orb_high": 0, "orb_low": 0, "orb_bonus": 0}

def validate_volume_spike(intraday) -> dict:
    try:
        if len(intraday) < 11:
            return {"volume_spike": False, "volume_ratio": 0.0, "volume_bonus": 0}
        avg_vol  = float(intraday["Volume"].iloc[-11:-1].mean()) or 1
        last_vol = float(intraday["Volume"].iloc[-1])
        ratio    = round(last_vol / avg_vol, 2)
        spike    = ratio >= 1.8
        bonus    = 10 if spike else 0
        return {"volume_spike": spike, "volume_ratio": ratio, "volume_bonus": bonus}
    except Exception as e:
        print(f"[VolSpike ERROR] {e}")
        return {"volume_spike": False, "volume_ratio": 0.0, "volume_bonus": 0}

def multi_timeframe_alignment(symbol: str, intraday, vwap: float) -> dict:
    try:
        current_price = float(intraday["Close"].iloc[-1])
        five_min_ok   = current_price > vwap if vwap > 0 else False
        one_hour_ok = False
        try:
            h1 = yf.Ticker(symbol).history(period="30d", interval="1h")
            if len(h1) >= 50:
                ema20 = float(h1["Close"].ewm(span=20, adjust=False).mean().iloc[-1])
                ema50 = float(h1["Close"].ewm(span=50, adjust=False).mean().iloc[-1])
                one_hour_ok = ema20 > ema50
        except: pass
        daily_ok = False
        try:
            d = yf.Ticker(symbol).history(period="60d", interval="1d")
            if len(d) >= 50:
                sma50    = float(d["Close"].rolling(50).mean().iloc[-1])
                daily_ok = float(d["Close"].iloc[-1]) > sma50
        except: pass
        count = sum([five_min_ok, one_hour_ok, daily_ok])
        if count == 3:   alignment_score = 15
        elif count == 2: alignment_score = 5
        else:            alignment_score = -15
        return {"alignment_score": alignment_score, "aligned": count >= 2, "five_min_ok": five_min_ok, "one_hour_ok": one_hour_ok, "daily_ok": daily_ok}
    except Exception as e:
        print(f"[MTF ERROR] {symbol}: {e}")
        return {"alignment_score": 0, "aligned": False, "five_min_ok": False, "one_hour_ok": False, "daily_ok": False}

def calculate_atr_risk(daily_df, current_price: float, portfolio_size: float = 50000) -> dict:
    try:
        if len(daily_df) < 15:
            return {"atr": 0, "stop_loss": 0, "target_1": 0, "target_2": 0, "position_size": 0}
        high  = daily_df["High"]
        low   = daily_df["Low"]
        close = daily_df["Close"]
        tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
        atr  = round(float(tr.rolling(14).mean().iloc[-1]), 2)
        sl   = round(current_price - atr * 1.5, 2)
        t1   = round(current_price + atr * 2,   2)
        t2   = round(current_price + atr * 4,   2)
        risk_dollars   = portfolio_size * 0.01
        risk_per_share = current_price - sl
        pos_size = int(risk_dollars / risk_per_share) if risk_per_share > 0 else 0
        return {"atr": atr, "stop_loss": sl, "target_1": t1, "target_2": t2, "position_size": pos_size}
    except Exception as e:
        print(f"[ATR ERROR] {e}")
        return {"atr": 0, "stop_loss": 0, "target_1": 0, "target_2": 0, "position_size": 0}

def scan_symbol(symbol: str, spy_return: float, market_regime: dict) -> dict:
    try:
        intraday = yf.Ticker(symbol).history(period="1d", interval="5m")
        daily    = yf.Ticker(symbol).history(period="30d", interval="1d")
        if intraday.empty or len(intraday) < 5 or len(daily) < 2:
            return None
        liq = check_liquidity(symbol)
        if liq["is_penny_stock"]:
            print(f"  ⛔ {symbol} — Penny Stock → IGNORE")
            return {"symbol": symbol, "score": 0, "rating": "IGNORE", "gap_pct": 0, "rv": 0, "momentum_pct": 0, "above_vwap": False, "orb_breakout": False, "market_regime": market_regime["regime"], "is_liquid": False, "is_penny_stock": True, "rs_vs_spy": 0, "current_price": liq["price"], "vwap": 0}
        yesterday_close  = float(daily["Close"].iloc[-2])
        today_open       = float(intraday["Open"].iloc[0])
        current_price    = float(intraday["Close"].iloc[-1])
        gap_pct          = (today_open - yesterday_close) / yesterday_close * 100
        current_volume   = float(intraday["Volume"].sum())
        avg_daily_vol    = float(daily["Volume"].iloc[:-1].mean()) or 1
        elapsed_minutes  = len(intraday) * 5
        expected_vol     = avg_daily_vol * (elapsed_minutes / 390)
        rv               = current_volume / expected_vol if expected_vol > 0 else 0
        vwap             = calculate_vwap(intraday)
        price_above_vwap = current_price > vwap if vwap > 0 else False
        momentum_pct     = (current_price - today_open) / today_open * 100
        symbol_return    = (current_price - yesterday_close) / yesterday_close * 100
        rs_vs_spy        = symbol_return - spy_return
        orb = check_orb(intraday)
        vol = validate_volume_spike(intraday)
        mtf = multi_timeframe_alignment(symbol, intraday, vwap)
        atr = calculate_atr_risk(daily, current_price)
        score = 0
        if gap_pct >= 2.0:        score += WEIGHTS["gap"]
        elif gap_pct >= 1.0:      score += WEIGHTS["gap"] * 0.6
        elif gap_pct >= 0.5:      score += WEIGHTS["gap"] * 0.3
        if rv >= 2.0:             score += WEIGHTS["rv"]
        elif rv >= 1.5:           score += WEIGHTS["rv"] * 0.7
        elif rv >= 1.2:           score += WEIGHTS["rv"] * 0.4
        if price_above_vwap:      score += WEIGHTS["vwap"]
        if momentum_pct >= 1.5:   score += WEIGHTS["momentum"]
        elif momentum_pct >= 0.8: score += WEIGHTS["momentum"] * 0.6
        elif momentum_pct >= 0.3: score += WEIGHTS["momentum"] * 0.3
        if rs_vs_spy >= 1.5:      score += WEIGHTS["relative_strength"]
        elif rs_vs_spy >= 0.5:    score += WEIGHTS["relative_strength"] * 0.6
        elif rs_vs_spy >= 0:      score += WEIGHTS["relative_strength"] * 0.3
        score += orb["orb_bonus"]
        score += liq["liquidity_score_bonus"]
        score += vol["volume_bonus"]
        score += mtf["alignment_score"]
        score  = score * market_regime["regime_multiplier"]
        score  = round(max(0, min(score, 100)), 1)
        if score >= 85:   rating = "HOT"
        elif score >= 70: rating = "STRONG"
        elif score >= 55: rating = "WATCH"
        else:             rating = "IGNORE"
        emoji      = "🔥" if rating == "HOT" else "💪" if rating == "STRONG" else "👀" if rating == "WATCH" else "❌"
        orb_status = "🚀ORB" if orb["orb_breakout"] else ("🔻Brk" if orb["orb_breakdown"] else "➡️In")
        print(f"  {emoji} {symbol:6s} | {score:5.1f} | {rating:6s} | Gap:{gap_pct:+.1f}% RV:{rv:.1f}x Mom:{momentum_pct:+.1f}% VWAP:{'✅' if price_above_vwap else '❌'} {orb_status} VOL:{'🔥' if vol['volume_spike'] else '❌'} MTF:{'✅' if mtf['aligned'] else '❌'} ATR:{atr['atr']} SL:{atr['stop_loss']} T1:{atr['target_1']}")
        return {"symbol": symbol, "score": score, "rating": rating, "gap_pct": round(gap_pct, 2), "rv": round(rv, 2), "momentum_pct": round(momentum_pct, 2), "above_vwap": price_above_vwap, "orb_breakout": orb["orb_breakout"], "orb_breakdown": orb["orb_breakdown"], "orb_high": orb["orb_high"], "orb_low": orb["orb_low"], "market_regime": market_regime["regime"], "is_liquid": liq["is_liquid"], "is_penny_stock": liq["is_penny_stock"], "current_price": round(current_price, 2), "rs_vs_spy": round(rs_vs_spy, 2), "vwap": vwap, "volume_spike": vol["volume_spike"], "volume_ratio": vol["volume_ratio"], "mtf_alignment": mtf["aligned"], "stop_loss": atr["stop_loss"], "target_1": atr["target_1"], "target_2": atr["target_2"], "position_size": atr["position_size"], "atr": atr["atr"]}
    except Exception as e:
        print(f"[SCAN ERROR] {symbol}: {e}")
        return None

def scan_intraday_opportunities(symbols: list) -> list:
    print(f"\n{'='*75}")
    print(f"  🏦 Institutional Intraday Scanner | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*75}")
    market_regime = get_market_regime()
    spy_return    = market_regime.get("spy_momentum", 0)
    print(f"\n  Scanning {len(symbols)} symbols...\n")
    results = [r for s in symbols if (r := scan_symbol(s, spy_return, market_regime))]
    results.sort(key=lambda x: x["score"], reverse=True)
    hot    = [r for r in results if r["rating"] == "HOT"]
    strong = [r for r in results if r["rating"] == "STRONG"]
    watch  = [r for r in results if r["rating"] == "WATCH"]
    print(f"\n  ✅ HOT: {len(hot)} | STRONG: {len(strong)} | WATCH: {len(watch)}")
    print(f"\n{'='*100}")
    print(f"{'SYM':<6} {'SCR':>5} {'RATING':<7} {'GAP%':>5} {'RV':>4} {'MOM%':>5} {'VWAP':>4} {'ORB':>4} {'VOL':>4} {'MTF':>4} {'ATR':>6} {'SL':>7} {'T1':>7} {'SZ':>5}")
    print(f"{'='*100}")
    for r in results:
        print(f"{r['symbol']:<6} {r['score']:>5.1f} {r['rating']:<7} {r['gap_pct']:>+5.1f} {r['rv']:>4.1f}x {r['momentum_pct']:>+5.1f} {'✅' if r.get('above_vwap') else '❌':>4} {'🚀' if r.get('orb_breakout') else '❌':>4} {'🔥' if r.get('volume_spike') else '❌':>4} {'✅' if r.get('mtf_alignment') else '❌':>4} {r.get('atr',0):>6.2f} {r.get('stop_loss',0):>7.2f} {r.get('target_1',0):>7.2f} {r.get('position_size',0):>5}")
    print(f"{'='*100}")
    return results

if __name__ == "__main__":
    symbols = ["NVDA", "AMD", "TSLA", "AVGO"]
    scan_intraday_opportunities(symbols)

if __name__ == "__main__":
    import time
    while True:
        try:
            main()
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(60)
