from telegram_gate import send_telegram, send_alert
try:
    from institutional_layer import get_market_environment, is_sector_allowed, get_adaptive_size
except:
    def get_market_environment(): return {}
    def is_sector_allowed(s, p): return True, "OK"
    def get_adaptive_size(s, pv, c, **kw): return {"position_size_dollars": pv * 0.05}

from insider_check import full_pre_buy_check
"""
decision_engine.py
==================
محرك القرار الموحد — يجمع كل الفلاتر في قرار واحد
✅ Macro Intelligence
✅ Sector Rotation
✅ RS Rating
✅ Annual EPS
✅ Market Regime
✅ يُدمج مع auto_monitor.py تلقائياً
"""

WEIGHTS = {
    "macro": 15,
    "sector": 10,
    "technical": 25,
    "relative_strength": 20,
    "earnings": 15,
    "smart_money": 10,
    "event_risk": 5
}

import json
try:
    from event_awareness import is_trading_allowed, get_position_multiplier
except:
    def is_trading_allowed(): return True
    def get_position_multiplier(): return 1.0
import yfinance as yf
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID


# ═══════════════════════════════════════════════════════════════════════════════
# تحميل حالات الملفات
# ═══════════════════════════════════════════════════════════════════════════════

def load_macro_state() -> dict:
    try:
        with open("/root/macro_state.json", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"action": "SELECTIVE", "warnings": [], "score": 0}

def load_sector_state() -> dict:
    try:
        with open("/root/sector_state.json", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"sectors": {}}

# ═══════════════════════════════════════════════════════════════════════════════
# الفلاتر الفردية
# ═══════════════════════════════════════════════════════════════════════════════

def check_rs_rating(symbol: str, min_rs: int = 80) -> tuple:
    """يفحص RS Rating للسهم"""
    try:
        # تحميل SPY
        spy = yf.download("SPY", period="1y", progress=False, auto_adjust=True)
        spy.columns = [c[0] if isinstance(c, tuple) else c for c in spy.columns]
        spy_close = spy['Close'].dropna()

        def spy_pct(days):
            if len(spy_close) < days: return 0.0
            return (float(spy_close.iloc[-1]) - float(spy_close.iloc[-days])) / float(spy_close.iloc[-days])

        spy_raw = spy_pct(63)*0.40 + spy_pct(126)*0.20 + spy_pct(189)*0.20 + spy_pct(252)*0.20

        # تحميل السهم
        df = yf.download(symbol, period="1y", progress=False, auto_adjust=True)
        if df.empty or len(df) < 60:
            return True, 50, "لا بيانات كافية"

        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        close = df['Close'].dropna()

        def pct(days):
            if len(close) < days: return 0.0
            return (float(close.iloc[-1]) - float(close.iloc[-days])) / float(close.iloc[-days])

        raw = pct(63)*0.40 + pct(126)*0.20 + pct(189)*0.20 + pct(252)*0.20

        # تحويل لنقاط تقريبية
        if raw > spy_raw * 1.5:
            rs = 90
        elif raw > spy_raw * 1.2:
            rs = 85
        elif raw > spy_raw:
            rs = 75
        elif raw > spy_raw * 0.8:
            rs = 60
        else:
            rs = 40

        passed = rs >= min_rs
        return passed, rs, f"RS={rs}"

    except Exception as e:
        return True, 50, f"خطأ RS: {e}"

def check_annual_eps(symbol: str) -> tuple:
    """يفحص نمو الأرباح السنوي"""
    try:
        ticker = yf.Ticker(symbol)
        info   = ticker.info

        eps_growth = info.get('earningsGrowth', None)
        rev_growth = info.get('revenueGrowth', None)

        if eps_growth is None:
            return True, "لا بيانات EPS"

        eps_pct = eps_growth * 100
        rev_pct = (rev_growth * 100) if rev_growth else 0

        if eps_pct >= 25 and rev_pct >= 15:
            return True, f"EPS {eps_pct:+.0f}% Rev {rev_pct:+.0f}%"
        elif eps_pct >= 25:
            return True, f"EPS {eps_pct:+.0f}% (Rev ضعيف)"
        else:
            return False, f"EPS منخفض {eps_pct:+.0f}%"

    except Exception as e:
        return True, f"خطأ EPS"

def check_macro_filter(symbol: str, macro_state: dict) -> tuple:
    """يفحص فلتر الماكرو"""
    action   = macro_state.get("action", "SELECTIVE")
    warnings = macro_state.get("warnings", [])
    score    = macro_state.get("score", 0)

    TECH = ["NVDA","MSFT","AAPL","GOOGL","META","AMZN","AVGO","AMD",
            "CRWD","PANW","PLTR","NOW","DDOG","SNOW","ADBE","CRM","NFLX","TTD"]
    ENERGY = ["XOM","CVX","OXY"]

    is_tech   = symbol in TECH
    is_energy = symbol in ENERGY

    if action == "CASH":
        return False, "الماكرو: السوق خطير — كاش"

    if action == "REDUCE":
        return False, "الماكرو: بيئة سلبية — قلل المخاطر"

    if "avoid_tech" in warnings and is_tech:
        return False, "الماكرو: US10Y عالٍ — تجنب التكنولوجيا"

    if "avoid_growth" in warnings and is_tech:
        return False, "الماكرو: DXY قوي — تجنب النمو"

    if "recession_risk" in warnings and not is_energy:
        return False, "الماكرو: خطر ركود"

    return True, f"الماكرو إيجابي (نقاط: {score:+d})"

def check_sector_filter(symbol: str, sector_state: dict) -> tuple:
    """يفحص إذا كان السهم في قطاع قيادي"""
    sectors = sector_state.get("sectors", {})

    # إيجاد قطاع السهم
    for sector_name, sector_data in sectors.items():
        stocks = sector_data.get("stocks", [])
        if symbol in stocks:
            is_leading = sector_data.get("is_leading", False)
            score      = sector_data.get("score", 0)
            if is_leading:
                return True, f"قطاع قيادي: {sector_name}"
            else:
                return False, f"قطاع ضعيف: {sector_name} (نقاط: {score:+.1f})"

    # السهم غير مصنف — نسمح به
    return True, "قطاع غير مصنف — مسموح"

def check_earnings_risk(symbol: str) -> tuple:
    """يفحص إذا كان هناك نتائج خلال 48 ساعة"""
    try:
        ticker = yf.Ticker(symbol)
        cal    = ticker.calendar

        if cal is None or cal.empty:
            return True, "لا موعد نتائج"

        if 'Earnings Date' in cal.index:
            earnings_date = cal.loc['Earnings Date'].iloc[0]
            earnings_dt   = pd.Timestamp(earnings_date)
            days_until    = (earnings_dt - pd.Timestamp.now()).days

            if 0 <= days_until <= 2:
                return False, f"نتائج بعد {days_until} يوم — انتظر!"
            elif days_until <= 5:
                return True, f"نتائج بعد {days_until} يوم — احذر"

        return True, "لا خطر نتائج"
    except:
        return True, "لا بيانات نتائج"

# ═══════════════════════════════════════════════════════════════════════════════
# محرك القرار الرئيسي
# ═══════════════════════════════════════════════════════════════════════════════

def should_buy(symbol: str, price: float = None) -> dict:
    # Event Awareness Check
    if not is_trading_allowed():
        return {"allowed": False, "reason": "EVENT_LOCKDOWN", "warnings": ["      "], "score": 0}
    event_multiplier = get_position_multiplier()
    # Institutional: Sector Correlation Check
    try:
        import requests
        pos = requests.get("https://paper-api.alpaca.markets/v2/positions", headers={"APCA-API-KEY-ID": ALPACA_API_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY}, timeout=5).json()
        sec_ok, sec_reason = is_sector_allowed(symbol, pos)
        if not sec_ok:
            return {"allowed": False, "reason": f"SECTOR_OVERWEIGHT: {sec_reason}", "warnings": [sec_reason], "score": 0}
    except:
        pass

    """
    القرار النهائي للشراء — يجمع كل الفلاتر
    يرجع: {allowed, score, reasons, blocks}
    """
    result = {
        "symbol":  symbol,
        "allowed": True,
        "score":   0,
        "reasons": [],
        "blocks":  [],
        'warnings': [],
        "time":    str(datetime.now()),
    }

    # تحميل الحالات
    macro_state  = load_macro_state()
    sector_state = load_sector_state()

    # ─── ١. فلتر الماكرو ────────────────────────────────────────────────────
    macro_ok, macro_reason = check_macro_filter(symbol, macro_state)
    if macro_ok:
        result["score"] += 2
        result["reasons"].append(f"✅ {macro_reason}")
    else:
        result["allowed"] = False
        result["blocks"].append(f"❌ {macro_reason}")

    # ─── ٢. فلتر القطاع ─────────────────────────────────────────────────────
    sector_ok, sector_reason = check_sector_filter(symbol, sector_state)
    if sector_ok:
        result["score"] += 2
        result["reasons"].append(f"✅ {sector_reason}")
    else:
        result["score"] -= 1
        result["reasons"].append(f"⚠️ {sector_reason}")
        # القطاع الضعيف لا يمنع الشراء تماماً — فقط يقلل النقاط

    # ─── ٣. فلتر RS Rating ───────────────────────────────────────────────────
    rs_ok, rs_score, rs_reason = check_rs_rating(symbol)
    if rs_ok:
        result["score"] += 2
        result["reasons"].append(f"✅ {rs_reason}")
    else:
        result["score"] -= 1
        result["reasons"].append(f"⚠️ {rs_reason}")
        # RS منخفض لا يمنع تماماً — فقط يقلل النقاط

    # ─── ٤. فلتر EPS السنوي ──────────────────────────────────────────────────
    eps_ok, eps_reason = check_annual_eps(symbol)
    if eps_ok:
        result["score"] += 1
        result["reasons"].append(f"✅ {eps_reason}")
    else:
        result["score"] -= 1
        result["reasons"].append(f"⚠️ {eps_reason}")

    # ─── ٥. فلتر خطر النتائج ─────────────────────────────────────────────────
    earn_ok, earn_reason = check_earnings_risk(symbol)
    if earn_ok:
        result["reasons"].append(f"✅ {earn_reason}")
    else:
        result["allowed"] = False
        result["blocks"].append(f"❌ {earn_reason}")

    # ─── القرار النهائي ──────────────────────────────────────────────────────
    # إذا فيه حجب إلزامي → لا تشتري
    if result["blocks"]:
        result["allowed"] = False

    # إذا النقاط سلبية → لا تشتري
    if result["score"] < 0:
        result["allowed"] = False
        result["blocks"].append(f"❌ نقاط سلبية: {result['score']}")

    # Weighted Score Classification
    try:
        result["max_score"] = sum(WEIGHTS.values())
        result["score_pct"] = round((result["score"] / result["max_score"]) * 100, 1)
        if result["score_pct"] >= 90:   result["rating"] = "ELITE"
        elif result["score_pct"] >= 75: result["rating"] = "STRONG"
        elif result["score_pct"] >= 60: result["rating"] = "GOOD"
        elif result["score_pct"] >= 40: result["rating"] = "WEAK"
        else:                           result["rating"] = "AVOID"
    except Exception as e:
        result["max_score"] = 100
        result["score_pct"] = 0
        result["rating"] = "UNKNOWN"
    # Structured Rejection Analytics
    try:
        import os, json
        os.makedirs("/root/logs", exist_ok=True)
        log_entry = {
            "symbol": result.get("symbol", symbol),
            "allowed": result.get("allowed"),
            "score": result.get("score"),
            "reasons": result.get("reasons", []),
            "blocks": result.get("blocks", []),
            "warnings": result.get("warnings", []),
            "timestamp": str(datetime.now())
        }
        with open("/root/logs/trade_decisions.log", "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        print(f"[ANALYTICS ERROR] {e}")
    calculate_position_size(result)
    return result

# ═══════════════════════════════════════════════════════════════════════════════
# واجهة لـ auto_monitor.py
# ═══════════════════════════════════════════════════════════════════════════════

# كاش للقرارات — لا نعيد الحساب لكل سهم كل 5 دقائق
_decision_cache = {}
_cache_time = {}
CACHE_DURATION = 3600  # ساعة واحدة

def get_buy_decision(symbol: str) -> bool:
    """
    الدالة الرئيسية التي يستدعيها auto_monitor.py
    ترجع True/False فقط
    """
    now = datetime.now().timestamp()

    # استخدم الكاش إذا لم تمر ساعة
    if symbol in _decision_cache:
        if now - _cache_time.get(symbol, 0) < CACHE_DURATION:
            return _decision_cache[symbol]

    # احسب القرار
    decision = should_buy(symbol)
    allowed  = decision["allowed"]

    # حفظ في الكاش
    _decision_cache[symbol] = allowed
    _cache_time[symbol]     = now

    if not allowed:
        print(f"[Decision] ❌ {symbol}: {' | '.join(decision['blocks'])}")
    else:
        print(f"[Decision] ✅ {symbol}: نقاط={decision['score']:+d}")

    return allowed

def log_decision(symbol: str, decision: dict, telegram: bool = False):
    """يسجل القرار ويرسله على Telegram إذا طُلب"""
    status = "✅ مسموح بالشراء" if decision["allowed"] else "❌ محجوب"

    log = (
        f"🧠 <b>Decision Engine — {symbol}</b>\n"
        f"{'─'*25}\n"
        f"القرار: {status}\n"
        f"النقاط: {decision['score']:+d}\n\n"
    )

    if decision["reasons"]:
        log += "<b>الأسباب:</b>\n"
        for r in decision["reasons"]:
            log += f"{r}\n"

    if decision["blocks"]:
        log += "\n<b>الحجب:</b>\n"
        for b in decision["blocks"]:
            log += f"{b}\n"

    print(log)
    if telegram:
        send_telegram(log)

# ═══════════════════════════════════════════════════════════════════════════════
# نقطة الدخول
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 55)
    print("  Decision Engine — اختبار شامل")
    print("=" * 55 + "\n")

    test_stocks = ["NVDA", "MSFT", "AAPL", "META", "XOM", "LLY"]

    for sym in test_stocks:
        print(f"\n{'─'*40}")
        print(f"فحص {sym}...")
        decision = should_buy(sym)
        log_decision(sym, decision, telegram=False)

    # إرسال تقرير موجز على Telegram
    allowed = [s for s in test_stocks if should_buy(s)["allowed"]]
    blocked = [s for s in test_stocks if not should_buy(s)["allowed"]]

    msg = (
        f"🧠 <b>Decision Engine — تقرير الاختبار</b>\n"
        f"{'─'*25}\n"
        f"✅ مسموح بالشراء: {', '.join(allowed) if allowed else 'لا أحد'}\n"
        f"❌ محجوب: {', '.join(blocked) if blocked else 'لا أحد'}\n\n"
        f"النظام يعمل بـ 5 فلاتر متكاملة 🎯"
    )
    send_telegram(msg)
    print("\n✅ اكتمل! التقرير وصل على Telegram")

# ============================================================
# ADAPTIVE POSITION SIZING
# ============================================================
    calculate_position_size(result)
def calculate_position_size(result: dict, portfolio_value: float = 50000) -> dict:
    try:
        rating    = result.get("rating", "AVOID")
        score_pct = result.get("score_pct", 0)
        warnings  = result.get("warnings", [])

        # Base size by rating
        if rating == "ELITE":    size_pct = 0.15
        elif rating == "STRONG": size_pct = 0.08
        elif rating == "GOOD":   size_pct = 0.04
        elif rating == "WEAK":   size_pct = 0.01
        else:                    size_pct = 0.0

        # Score boost/cut
        if score_pct > 95:  size_pct *= 1.2
        elif score_pct < 50: size_pct *= 0.5

        # Warnings penalty
        if len(warnings) > 2: size_pct *= 0.7

        # Cap
        size_pct = round(min(size_pct, 0.20), 4)
        dollars  = round(portfolio_value * size_pct, 2)

        result["position_size_pct"]     = size_pct
        result["position_size_dollars"] = dollars
        return result

    except Exception as e:
        print(f"[POSITION SIZE ERROR] {e}")
        result["position_size_pct"]     = 0
        result["position_size_dollars"] = 0
        return result
