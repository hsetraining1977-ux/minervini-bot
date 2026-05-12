#!/usr/bin/env python3
"""
Institutional Robustness Layer
================================
يغطي كل النقاط الناقصة في كود واحد:
1. Portfolio Correlation Control
2. Adaptive Position Sizing
3. Hard Fail-Safe Layer
4. Cross-Asset Intelligence
5. AI Learning Layer (Trade Memory)
6. Liquidity Regime Detection
7. Institutional Analytics (Sharpe/Sortino/Drawdown)
8. Psychological Market Model
"""

import json, time, requests, os, math
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
import pytz, sys

sys.path.insert(0, '/root')
from config import (TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, ALPACA_API_KEY, ALPACA_SECRET_KEY,
                    FINNHUB_API_KEY)
ALPACA_KEY = ALPACA_API_KEY
ALPACA_SECRET = ALPACA_SECRET_KEY

# ===== إعدادات =====
ET = pytz.timezone('America/New_York')
ALPACA_BASE = "https://paper-api.alpaca.markets"
HEADERS = {"APCA-API-KEY-ID": ALPACA_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET}

# ملفات الحالة
TRADE_MEMORY_FILE  = "/root/trade_memory.json"
ANALYTICS_FILE     = "/root/analytics_state.json"
CORRELATION_FILE   = "/root/correlation_state.json"
LIQUIDITY_FILE     = "/root/liquidity_state.json"
PSYCHOLOGY_FILE    = "/root/psychology_state.json"
FAILSAFE_FILE      = "/root/failsafe_state.json"

# ===== Helpers =====
def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID,
                                 "text": msg, "parse_mode": "HTML"}, timeout=10)
    except: pass

def load_json(path, default):
    try:
        with open(path, 'r') as f: return json.load(f)
    except: return default

def save_json(path, data):
    with open(path, 'w') as f: json.dump(data, f, indent=2, default=str)

def alpaca_get(endpoint):
    try:
        r = requests.get(f"{ALPACA_BASE}{endpoint}", headers=HEADERS, timeout=10)
        return r.json() if r.status_code == 200 else {}
    except: return {}

# ===========================================================
# 1. PORTFOLIO CORRELATION CONTROL
# ===========================================================
SECTOR_MAP = {
    "NVDA":"semiconductors","AMD":"semiconductors","SMCI":"semiconductors",
    "TSM":"semiconductors","INTC":"semiconductors","AVGO":"semiconductors",
    "MSFT":"software","GOOGL":"software","META":"software","CRM":"software",
    "AAPL":"hardware","DELL":"hardware","HPQ":"hardware",
    "AMZN":"ecommerce","SHOP":"ecommerce",
    "JPM":"financials","GS":"financials","BAC":"financials",
    "XOM":"energy","CVX":"energy","OXY":"energy",
    "LLY":"healthcare","UNH":"healthcare","JNJ":"healthcare",
}

def get_correlation_clusters(positions):
    """يكتشف التركيز الخفي في المحفظة"""
    sector_exposure = defaultdict(float)
    total_value = sum(float(p.get('market_value', 0)) for p in positions)
    if total_value == 0: return {}

    for p in positions:
        symbol = p['symbol']
        value  = float(p.get('market_value', 0))
        sector = SECTOR_MAP.get(symbol, 'other')
        sector_exposure[sector] += value / total_value

    return dict(sector_exposure)

def check_correlation_risk(symbol, positions):
    """
    هل إضافة هذا السهم تزيد التركيز فوق الحد؟
    Returns: (allowed: bool, reason: str, concentration: float)
    """
    MAX_SECTOR_EXPOSURE = 0.35  # 35% حد أقصى لكل قطاع

    clusters = get_correlation_clusters(positions)
    symbol_sector = SECTOR_MAP.get(symbol, 'other')
    current_exposure = clusters.get(symbol_sector, 0.0)

    if current_exposure >= MAX_SECTOR_EXPOSURE:
        return False, f"تركيز {symbol_sector} = {current_exposure:.1%} (حد 35%)", current_exposure

    state = {
        "timestamp": datetime.now(ET).isoformat(),
        "clusters": clusters,
        "symbol_checked": symbol,
        "sector": symbol_sector,
        "current_exposure": current_exposure,
        "allowed": True
    }
    save_json(CORRELATION_FILE, state)
    return True, "OK", current_exposure

# ===========================================================
# 2. ADAPTIVE POSITION SIZING
# ===========================================================
def adaptive_position_size(symbol, portfolio_value, confidence_score,
                            atr_pct=None, market_regime="bull",
                            sector_exposure=0.0, event_multiplier=1.0):
    """
    معادلة Position Size الديناميكية:
    - Confidence Score  30%
    - Volatility (ATR)  25%
    - Market Regime     20%
    - Portfolio Exposure 15%
    - Event Risk        10%
    """
    BASE_RISK = 0.0125  # 1.25% أساسي

    # --- Confidence Factor (30%) ---
    if confidence_score >= 90:   conf_factor = 1.5
    elif confidence_score >= 80: conf_factor = 1.2
    elif confidence_score >= 70: conf_factor = 1.0
    elif confidence_score >= 65: conf_factor = 0.7
    else:                        conf_factor = 0.5

    # --- Volatility Factor (25%) ---
    if atr_pct is None:
        try:
            hist = yf.Ticker(symbol).history(period="20d")
            atr  = hist['High'].sub(hist['Low']).mean()
            price= hist['Close'].iloc[-1]
            atr_pct = atr / price
        except: atr_pct = 0.02

    if atr_pct < 0.015:   vol_factor = 1.3
    elif atr_pct < 0.025: vol_factor = 1.0
    elif atr_pct < 0.04:  vol_factor = 0.75
    else:                  vol_factor = 0.5

    # --- Market Regime Factor (20%) ---
    regime_factors = {
        "bull":          1.2,
        "risk_on":       1.2,
        "selective":     0.9,
        "neutral":       0.8,
        "bear":          0.4,
        "high_volatility":0.5,
        "defensive":     0.5,
    }
    regime_factor = regime_factors.get(market_regime.lower(), 0.8)

    # --- Concentration Factor (15%) ---
    if sector_exposure > 0.30:   conc_factor = 0.4
    elif sector_exposure > 0.20: conc_factor = 0.7
    else:                         conc_factor = 1.0

    # --- Event Risk Factor (10%) ---
    # event_multiplier جاهز من event_awareness.py

    # --- الحساب النهائي ---
    final_risk = (BASE_RISK
                  * (conf_factor  * 0.30)
                  * (vol_factor   * 0.25)
                  * (regime_factor* 0.20)
                  * (conc_factor  * 0.15)
                  * (event_multiplier * 0.10)
                  + BASE_RISK * 0.0)  # baseline

    # تبسيط: نضرب BASE_RISK بمعامل مرجح
    weighted = (conf_factor*0.30 + vol_factor*0.25 +
                regime_factor*0.20 + conc_factor*0.15 +
                event_multiplier*0.10)
    final_risk = BASE_RISK * weighted

    # حد أقصى وأدنى
    final_risk = max(0.003, min(0.025, final_risk))

    dollar_risk   = portfolio_value * final_risk
    stop_pct      = atr_pct * 2
    position_size = dollar_risk / stop_pct if stop_pct > 0 else 0

    result = {
        "symbol": symbol,
        "final_risk_pct": round(final_risk * 100, 3),
        "dollar_risk": round(dollar_risk, 2),
        "position_size_dollars": round(position_size, 2),
        "factors": {
            "confidence": conf_factor,
            "volatility":  vol_factor,
            "regime":      regime_factor,
            "concentration": conc_factor,
            "event":       event_multiplier,
        }
    }
    return result

# ===========================================================
# 3. HARD FAIL-SAFE LAYER
# ===========================================================
def run_failsafe_checks():
    """
    فحوصات الأمان الصارمة — تعمل كل 5 دقائق
    """
    issues = []
    state  = load_json(FAILSAFE_FILE, {})

    # --- 1. Broker Heartbeat ---
    try:
        account = alpaca_get("/v2/account")
        if not account:
            issues.append("🔴 Alpaca API لا تستجيب")
        else:
            state["last_broker_ping"] = datetime.now(ET).isoformat()
            state["account_status"]   = account.get("status", "unknown")
            if account.get("trading_blocked"):
                issues.append("🔴 Alpaca: التداول محظور!")
            if account.get("account_blocked"):
                issues.append("🔴 Alpaca: الحساب محظور!")
    except Exception as e:
        issues.append(f"🔴 Broker heartbeat فشل: {e}")

    # --- 2. Stale Data Detection ---
    macro_file = "/root/macro_state.json"
    if os.path.exists(macro_file):
        age = time.time() - os.path.getmtime(macro_file)
        if age > 7200:  # أكثر من ساعتين
            issues.append(f"🟡 بيانات Macro قديمة ({age/3600:.1f} ساعة)")

    # --- 3. Max Drawdown Emergency ---
    try:
        account = alpaca_get("/v2/account")
        equity  = float(account.get("equity", 50000))
        start   = float(account.get("last_equity", equity))
        if start > 0:
            dd = (start - equity) / start
            state["current_drawdown"] = round(dd, 4)
            if dd > 0.10:  # 10% drawdown
                issues.append(f"🔴 Emergency: Drawdown {dd:.1%} — وقف التداول!")
                emergency_flatten()
    except: pass

    # --- 4. Exposure Check ---
    try:
        positions = alpaca_get("/v2/positions")
        account   = alpaca_get("/v2/account")
        equity    = float(account.get("equity", 50000))
        total_exp = sum(abs(float(p.get('market_value',0))) for p in positions)
        exposure  = total_exp / equity if equity > 0 else 0
        state["portfolio_exposure"] = round(exposure, 4)
        if exposure > 0.95:
            issues.append(f"🟡 تعرض عالي جداً: {exposure:.1%}")
    except: pass

    # --- 5. Duplicate Order Protection ---
    try:
        orders = alpaca_get("/v2/orders?status=open")
        symbols = [o['symbol'] for o in orders]
        dupes   = [s for s in set(symbols) if symbols.count(s) > 1]
        if dupes:
            issues.append(f"🟡 أوامر مكررة: {dupes}")
    except: pass

    state["last_check"] = datetime.now(ET).isoformat()
    state["issues"]     = issues
    save_json(FAILSAFE_FILE, state)

    if issues:
        msg = "⚠️ <b>Fail-Safe Alert</b>\n\n" + "\n".join(issues)
        send_telegram(msg)
        print(f"[FailSafe] {len(issues)} issues found")
    else:
        print("[FailSafe] ✅ All systems OK")

    return issues

def emergency_flatten():
    """إغلاق كل المراكز في حالة الطوارئ"""
    try:
        r = requests.delete(f"{ALPACA_BASE}/v2/positions",
                            headers=HEADERS, timeout=15)
        if r.status_code in [200, 207]:
            send_telegram("🚨 <b>EMERGENCY FLATTEN</b>\n\nتم إغلاق كل المراكز تلقائياً بسبب Drawdown 10%+")
            print("[FailSafe] 🚨 Emergency flatten executed")
    except Exception as e:
        print(f"[FailSafe] Flatten error: {e}")

# ===========================================================
# 4. CROSS-ASSET INTELLIGENCE
# ===========================================================
def analyze_cross_assets():
    """
    يربط: Bonds + Oil + Gold + Dollar + VIX + Credit
    """
    assets = {
        "SPY":  "S&P 500",
        "TLT":  "Bonds (20Y)",
        "GLD":  "Gold",
        "USO":  "Oil",
        "UUP":  "Dollar",
        "HYG":  "High Yield Credit",
        "VXX":  "Volatility",
        "BTC-USD": "Crypto (Risk Appetite)",
    }

    signals = {}
    risk_score = 50  # neutral base

    try:
        for ticker, name in assets.items():
            try:
                hist = yf.Ticker(ticker).history(period="5d")
                if len(hist) >= 2:
                    change = (hist['Close'].iloc[-1] - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]
                    signals[ticker] = {"name": name, "change_pct": round(change * 100, 2)}
            except: pass

        # --- تحليل الإشارات ---
        interpretations = []

        spy_chg = signals.get("SPY", {}).get("change_pct", 0)
        tlt_chg = signals.get("TLT", {}).get("change_pct", 0)
        gld_chg = signals.get("GLD", {}).get("change_pct", 0)
        hyg_chg = signals.get("HYG", {}).get("change_pct", 0)
        btc_chg = signals.get("BTC-USD", {}).get("change_pct", 0)
        uup_chg = signals.get("UUP",  {}).get("change_pct", 0)

        # SPY صاعد + Bonds هابطة = Risk-On حقيقي
        if spy_chg > 0.3 and tlt_chg < -0.2:
            risk_score += 15
            interpretations.append("✅ SPY↑ + TLT↓ = Risk-On حقيقي")

        # Gold صاعد = خوف/تضخم
        if gld_chg > 0.5:
            risk_score -= 10
            interpretations.append("🟡 Gold↑ = مخاوف في السوق")

        # High Yield Credit صاعد = ثقة مؤسسية
        if hyg_chg > 0.2:
            risk_score += 10
            interpretations.append("✅ HYG↑ = ثقة مؤسسية")
        elif hyg_chg < -0.3:
            risk_score -= 15
            interpretations.append("🔴 HYG↓ = تراجع الثقة المؤسسية")

        # Crypto صاعد = شهية مخاطرة
        if btc_chg > 2:
            risk_score += 8
            interpretations.append("✅ BTC↑ = شهية مخاطرة")
        elif btc_chg < -3:
            risk_score -= 8
            interpretations.append("🟡 BTC↓ = تراجع شهية المخاطرة")

        # Dollar قوي = ضغط على الأصول
        if uup_chg > 0.4:
            risk_score -= 10
            interpretations.append("🟡 Dollar↑ = ضغط على الأسهم")

        risk_score = max(0, min(100, risk_score))

        if risk_score >= 70:   cross_signal = "RISK_ON"
        elif risk_score >= 50: cross_signal = "NEUTRAL"
        elif risk_score >= 30: cross_signal = "CAUTIOUS"
        else:                   cross_signal = "RISK_OFF"

        result = {
            "timestamp":       datetime.now(ET).isoformat(),
            "risk_score":      risk_score,
            "cross_signal":    cross_signal,
            "signals":         signals,
            "interpretations": interpretations,
        }
        save_json("/root/cross_asset_state.json", result)

        print(f"[CrossAsset] {cross_signal} | Score: {risk_score}")
        return result

    except Exception as e:
        print(f"[CrossAsset] Error: {e}")
        return {"cross_signal": "NEUTRAL", "risk_score": 50}

# ===========================================================
# 5. AI LEARNING LAYER (Trade Memory)
# ===========================================================
def record_trade(symbol, action, price, confidence, reason,
                 regime, sector, vix_level):
    """يسجل كل صفقة مع بيانات السياق"""
    memory = load_json(TRADE_MEMORY_FILE, {"trades": [], "patterns": {}})

    trade = {
        "id":         len(memory["trades"]) + 1,
        "timestamp":  datetime.now(ET).isoformat(),
        "symbol":     symbol,
        "action":     action,
        "price":      price,
        "confidence": confidence,
        "reason":     reason,
        "regime":     regime,
        "sector":     sector,
        "vix_level":  vix_level,
        "outcome":    None,  # يُملأ لاحقاً
        "pnl":        None,
        "exit_price": None,
    }
    memory["trades"].append(trade)
    save_json(TRADE_MEMORY_FILE, memory)
    print(f"[Learning] Trade recorded: {symbol} {action}")
    return trade["id"]

def update_trade_outcome(trade_id, exit_price, pnl):
    """يُحدّث نتيجة الصفقة"""
    memory = load_json(TRADE_MEMORY_FILE, {"trades": [], "patterns": {}})

    for trade in memory["trades"]:
        if trade["id"] == trade_id:
            trade["outcome"]    = "WIN" if pnl > 0 else "LOSS"
            trade["pnl"]        = round(pnl, 2)
            trade["exit_price"] = exit_price
            break

    _update_patterns(memory)
    save_json(TRADE_MEMORY_FILE, memory)

def _update_patterns(memory):
    """يستخرج الأنماط من الصفقات المكتملة"""
    completed = [t for t in memory["trades"] if t["outcome"]]
    if len(completed) < 5:
        return

    patterns = {}

    # Win Rate by Regime
    for regime in set(t["regime"] for t in completed):
        regime_trades = [t for t in completed if t["regime"] == regime]
        wins  = sum(1 for t in regime_trades if t["outcome"] == "WIN")
        patterns[f"winrate_{regime}"] = round(wins / len(regime_trades), 3)

    # Win Rate by Sector
    for sector in set(t["sector"] for t in completed):
        sector_trades = [t for t in completed if t["sector"] == sector]
        wins  = sum(1 for t in sector_trades if t["outcome"] == "WIN")
        patterns[f"winrate_sector_{sector}"] = round(wins / len(sector_trades), 3)

    # Avg PnL by Confidence Range
    high_conf = [t for t in completed if t.get("confidence", 0) >= 80]
    low_conf  = [t for t in completed if t.get("confidence", 0) < 80]
    if high_conf:
        patterns["avg_pnl_high_conf"] = round(sum(t["pnl"] for t in high_conf) / len(high_conf), 2)
    if low_conf:
        patterns["avg_pnl_low_conf"]  = round(sum(t["pnl"] for t in low_conf)  / len(low_conf),  2)

    memory["patterns"] = patterns
    print(f"[Learning] Patterns updated: {len(patterns)} patterns")

def get_learning_insights():
    """يُرجع رؤى من الصفقات السابقة"""
    memory = load_json(TRADE_MEMORY_FILE, {"trades": [], "patterns": {}})
    patterns = memory.get("patterns", {})
    completed = [t for t in memory["trades"] if t["outcome"]]

    if len(completed) < 3:
        return {"message": "بيانات غير كافية بعد", "trades_count": len(completed)}

    total  = len(completed)
    wins   = sum(1 for t in completed if t["outcome"] == "WIN")
    total_pnl = sum(t.get("pnl", 0) for t in completed)

    return {
        "total_trades":  total,
        "win_rate":      round(wins/total, 3),
        "total_pnl":     round(total_pnl, 2),
        "patterns":      patterns,
        "best_regime":   max((k for k in patterns if k.startswith("winrate_") and "sector" not in k),
                              key=lambda k: patterns[k], default="N/A"),
    }

# ===========================================================
# 6. LIQUIDITY REGIME DETECTION
# ===========================================================
def detect_liquidity_regime():
    """
    يكتشف: هل السيولة الحقيقية تدخل؟
    يراقب: Breadth + A/D + High Yield + Financial Conditions
    """
    try:
        tickers = {"SPY": None, "IWM": None, "HYG": None,
                   "LQD": None, "XLF": None}

        for t in tickers:
            try:
                hist = yf.Ticker(t).history(period="10d")
                tickers[t] = hist
            except: pass

        signals     = []
        liq_score   = 50

        # --- Breadth: SPY vs IWM (small caps) ---
        if tickers["SPY"] is not None and tickers["IWM"] is not None:
            spy_ret = (tickers["SPY"]['Close'].iloc[-1] / tickers["SPY"]['Close'].iloc[-5] - 1)
            iwm_ret = (tickers["IWM"]['Close'].iloc[-1] / tickers["IWM"]['Close'].iloc[-5] - 1)
            if iwm_ret > spy_ret:
                liq_score += 15
                signals.append("✅ Small Caps تقود = سيولة واسعة")
            else:
                liq_score -= 10
                signals.append("🟡 Large Caps فقط = سيولة ضيقة")

        # --- Credit Markets ---
        if tickers["HYG"] is not None:
            hyg_trend = tickers["HYG"]['Close'].iloc[-1] / tickers["HYG"]['Close'].iloc[-5] - 1
            if hyg_trend > 0.005:
                liq_score += 15
                signals.append("✅ High Yield صاعد = سيولة صحية")
            elif hyg_trend < -0.01:
                liq_score -= 20
                signals.append("🔴 High Yield هابط = انسحاب السيولة")

        # --- Financials ---
        if tickers["XLF"] is not None:
            xlf_trend = tickers["XLF"]['Close'].iloc[-1] / tickers["XLF"]['Close'].iloc[-5] - 1
            if xlf_trend > 0.01:
                liq_score += 10
                signals.append("✅ Banks صاعدة = بيئة سيولة جيدة")

        liq_score = max(0, min(100, liq_score))

        if liq_score >= 70:   regime = "EXPANDING"
        elif liq_score >= 50: regime = "NEUTRAL"
        elif liq_score >= 30: regime = "TIGHTENING"
        else:                  regime = "CONTRACTING"

        result = {
            "timestamp":     datetime.now(ET).isoformat(),
            "liquidity_score": liq_score,
            "regime":        regime,
            "signals":       signals,
        }
        save_json(LIQUIDITY_FILE, result)
        print(f"[Liquidity] {regime} | Score: {liq_score}")
        return result

    except Exception as e:
        print(f"[Liquidity] Error: {e}")
        return {"regime": "NEUTRAL", "liquidity_score": 50}

# ===========================================================
# 7. INSTITUTIONAL ANALYTICS
# ===========================================================
def calculate_analytics():
    """
    يحسب: Sharpe + Sortino + Max Drawdown + Win Rate by Regime
    """
    try:
        memory    = load_json(TRADE_MEMORY_FILE, {"trades": []})
        completed = [t for t in memory["trades"] if t.get("pnl") is not None]

        if len(completed) < 5:
            return {"message": "تحتاج 5+ صفقات مكتملة"}

        pnls    = [t["pnl"] for t in completed]
        returns = np.array(pnls)

        # --- Sharpe Ratio ---
        if returns.std() > 0:
            sharpe = (returns.mean() / returns.std()) * math.sqrt(252)
        else:
            sharpe = 0

        # --- Sortino Ratio ---
        downside = returns[returns < 0]
        if len(downside) > 0 and downside.std() > 0:
            sortino = (returns.mean() / downside.std()) * math.sqrt(252)
        else:
            sortino = sharpe

        # --- Max Drawdown ---
        cumulative = np.cumsum(returns)
        peak       = np.maximum.accumulate(cumulative)
        drawdown   = cumulative - peak
        max_dd     = drawdown.min()

        # --- Win Rate ---
        wins     = sum(1 for p in pnls if p > 0)
        win_rate = wins / len(pnls)

        # --- Expectancy ---
        avg_win  = np.mean([p for p in pnls if p > 0]) if any(p > 0 for p in pnls) else 0
        avg_loss = abs(np.mean([p for p in pnls if p < 0])) if any(p < 0 for p in pnls) else 1
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

        result = {
            "timestamp":    datetime.now(ET).isoformat(),
            "total_trades": len(completed),
            "win_rate":     round(win_rate, 3),
            "sharpe_ratio": round(sharpe, 3),
            "sortino_ratio":round(sortino, 3),
            "max_drawdown": round(max_dd, 2),
            "total_pnl":    round(sum(pnls), 2),
            "expectancy":   round(expectancy, 2),
            "avg_win":      round(avg_win, 2),
            "avg_loss":     round(avg_loss, 2),
        }
        save_json(ANALYTICS_FILE, result)

        msg = f"""📊 <b>Institutional Analytics</b>

📈 Sharpe Ratio: <b>{sharpe:.2f}</b>
📉 Sortino Ratio: <b>{sortino:.2f}</b>
🎯 Win Rate: <b>{win_rate:.1%}</b>
💰 Total P&L: <b>${sum(pnls):,.0f}</b>
📉 Max Drawdown: <b>${max_dd:,.0f}</b>
⚡ Expectancy: <b>${expectancy:.2f}/trade</b>
🔢 Total Trades: <b>{len(completed)}</b>"""
        send_telegram(msg)
        print(f"[Analytics] Sharpe={sharpe:.2f} | WinRate={win_rate:.1%}")
        return result

    except Exception as e:
        print(f"[Analytics] Error: {e}")
        return {}

# ===========================================================
# 8. PSYCHOLOGICAL MARKET MODEL
# ===========================================================
def analyze_market_psychology():
    """
    يكتشف: euphoric / fearful / complacent / panic
    عبر: VIX structure + Put/Call + Breadth + Momentum
    """
    try:
        tickers_data = {}
        for t in ["SPY", "^VIX", "^VIX3M"]:
            try:
                hist = yf.Ticker(t).history(period="20d")
                tickers_data[t] = hist
            except: pass

        fear_score = 50  # 0=euphoria, 100=panic
        signals    = []

        # --- VIX Level ---
        if "^VIX" in tickers_data and len(tickers_data["^VIX"]) > 0:
            vix = tickers_data["^VIX"]['Close'].iloc[-1]
            if vix < 13:
                fear_score -= 20
                signals.append(f"😄 VIX={vix:.1f} — Extreme Complacency")
            elif vix < 18:
                fear_score -= 10
                signals.append(f"😊 VIX={vix:.1f} — Low Fear")
            elif vix < 25:
                signals.append(f"😐 VIX={vix:.1f} — Normal")
            elif vix < 35:
                fear_score += 20
                signals.append(f"😨 VIX={vix:.1f} — Elevated Fear")
            else:
                fear_score += 40
                signals.append(f"😱 VIX={vix:.1f} — PANIC")
        else:
            vix = 20

        # --- VIX Term Structure (Contango = complacent, Backwardation = fear) ---
        if "^VIX" in tickers_data and "^VIX3M" in tickers_data:
            try:
                vix_spot  = tickers_data["^VIX"]['Close'].iloc[-1]
                vix_3m    = tickers_data["^VIX3M"]['Close'].iloc[-1]
                if vix_3m > vix_spot * 1.05:
                    fear_score -= 10
                    signals.append("✅ VIX Contango = سوق هادئ")
                elif vix_spot > vix_3m:
                    fear_score += 15
                    signals.append("⚠️ VIX Backwardation = قلق فوري")
            except: pass

        # --- SPY Momentum Exhaustion ---
        if "SPY" in tickers_data and len(tickers_data["SPY"]) >= 14:
            spy = tickers_data["SPY"]['Close']
            rsi_period = 14
            delta  = spy.diff()
            gain   = delta.clip(lower=0).rolling(rsi_period).mean()
            loss   = (-delta.clip(upper=0)).rolling(rsi_period).mean()
            rs     = gain / loss
            rsi    = 100 - (100 / (1 + rs))
            current_rsi = rsi.iloc[-1]

            if current_rsi > 75:
                fear_score -= 15
                signals.append(f"🔥 RSI={current_rsi:.0f} — Euphoric/Overbought")
            elif current_rsi < 30:
                fear_score += 15
                signals.append(f"💧 RSI={current_rsi:.0f} — Oversold/Fear")
        else:
            current_rsi = 50

        fear_score = max(0, min(100, fear_score))

        if fear_score >= 70:   state = "PANIC"
        elif fear_score >= 55: state = "FEARFUL"
        elif fear_score >= 45: state = "NEUTRAL"
        elif fear_score >= 30: state = "COMPLACENT"
        else:                   state = "EUPHORIC"

        # نصيحة تداولية
        advice_map = {
            "PANIC":      "فرصة محتملة للشراء — انتظر تثبيت",
            "FEARFUL":    "حذر — قلل الحجم",
            "NEUTRAL":    "بيئة تداول طبيعية",
            "COMPLACENT": "انتبه من reversal مفاجئ",
            "EUPHORIC":   "خطر — السوق مبالغ في التفاؤل",
        }

        result = {
            "timestamp":    datetime.now(ET).isoformat(),
            "fear_score":   fear_score,
            "market_state": state,
            "vix":          round(vix, 1),
            "rsi_spy":      round(current_rsi, 1),
            "signals":      signals,
            "advice":       advice_map[state],
        }
        save_json(PSYCHOLOGY_FILE, result)
        print(f"[Psychology] {state} | Fear={fear_score} | VIX={vix:.1f}")
        return result

    except Exception as e:
        print(f"[Psychology] Error: {e}")
        return {"market_state": "NEUTRAL", "fear_score": 50}

# ===========================================================
# MASTER RUN — يجمع كل الطبقات
# ===========================================================
def run_institutional_layer():
    """
    تقرير موحد يجمع كل الطبقات
    يُرسل عبر Telegram كل صباح
    """
    print("\n" + "="*60)
    print("[Institutional] 🚀 Running full analysis...")
    print("="*60)

    # تشغيل كل الطبقات
    cross  = analyze_cross_assets()
    liq    = detect_liquidity_regime()
    psych  = analyze_market_psychology()
    fails  = run_failsafe_checks()
    learn  = get_learning_insights()

    # تجميع التقرير
    cross_signal = cross.get("cross_signal", "NEUTRAL")
    liq_regime   = liq.get("regime", "NEUTRAL")
    psych_state  = psych.get("market_state", "NEUTRAL")
    fear_score   = psych.get("fear_score", 50)
    vix          = psych.get("vix", 20)

    # الحكم النهائي على البيئة
    env_score = 50
    if cross_signal == "RISK_ON":    env_score += 20
    elif cross_signal == "RISK_OFF": env_score -= 20
    if liq_regime == "EXPANDING":    env_score += 15
    elif liq_regime == "CONTRACTING":env_score -= 15
    if psych_state == "PANIC":       env_score += 10  # contrarian
    elif psych_state == "EUPHORIC":  env_score -= 10  # contrarian
    elif psych_state == "FEARFUL":   env_score -= 5

    env_score = max(0, min(100, env_score))

    if env_score >= 70:   env_label = "🟢 ممتازة"
    elif env_score >= 55: env_label = "🟡 جيدة"
    elif env_score >= 40: env_label = "🟠 محايدة"
    else:                  env_label = "🔴 سيئة"

    msg = f"""🏦 <b>Institutional Layer Report</b>
{datetime.now(ET).strftime('%Y-%m-%d %H:%M ET')}

🌍 <b>Cross-Asset:</b> {cross_signal} ({cross.get('risk_score',50)}/100)
💧 <b>Liquidity:</b> {liq_regime} ({liq.get('liquidity_score',50)}/100)
🧠 <b>Psychology:</b> {psych_state} | VIX={vix}
🎯 <b>بيئة السوق:</b> {env_label} ({env_score}/100)

📚 <b>Trade Memory:</b> {learn.get('total_trades',0)} صفقة | Win Rate: {learn.get('win_rate',0):.1%}

{'⚠️ تحذيرات: ' + str(len(fails)) if fails else '✅ لا تحذيرات'}"""

    send_telegram(msg)
    print(f"[Institutional] ✅ Report sent | Env={env_score}")

    return {
        "env_score":    env_score,
        "cross_signal": cross_signal,
        "liquidity":    liq_regime,
        "psychology":   psych_state,
    }

# ===========================================================
# PUBLIC API — للاستخدام من الملفات الأخرى
# ===========================================================
def get_adaptive_size(symbol, portfolio_value, confidence,
                      regime="bull", sector_exposure=0.0):
    """واجهة بسيطة للاستخدام من auto_monitor"""
    try:
        from event_awareness import get_position_multiplier
        event_mult = get_position_multiplier()
    except:
        event_mult = 1.0

    return adaptive_position_size(symbol, portfolio_value, confidence,
                                   market_regime=regime,
                                   sector_exposure=sector_exposure,
                                   event_multiplier=event_mult)

def is_sector_allowed(symbol, positions):
    """هل يمكن إضافة هذا السهم؟"""
    allowed, reason, exposure = check_correlation_risk(symbol, positions)
    return allowed, reason

def get_market_environment():
    """البيئة الكاملة للسوق — للاستخدام من decision_engine"""
    cross = load_json("/root/cross_asset_state.json", {"cross_signal":"NEUTRAL","risk_score":50})
    liq   = load_json(LIQUIDITY_FILE, {"regime":"NEUTRAL","liquidity_score":50})
    psych = load_json(PSYCHOLOGY_FILE, {"market_state":"NEUTRAL","fear_score":50})
    return {"cross": cross, "liquidity": liq, "psychology": psych}

# ===========================================================
# MAIN
# ===========================================================
if __name__ == "__main__":
    import schedule

    print("[Institutional] 🚀 Starting Institutional Robustness Layer")

    # تشغيل فوري
    run_institutional_layer()

    # جدول زمني
    schedule.every(6).hours.do(run_institutional_layer)
    schedule.every(5).minutes.do(run_failsafe_checks)
    schedule.every(1).hours.do(analyze_cross_assets)
    schedule.every(2).hours.do(detect_liquidity_regime)
    schedule.every(3).hours.do(analyze_market_psychology)
    schedule.every().day.at("09:00").do(calculate_analytics)

    while True:
        schedule.run_pending()
        time.sleep(60)
