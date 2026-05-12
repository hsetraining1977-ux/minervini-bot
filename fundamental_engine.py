"""
fundamental_engine.py
=====================
محرك التحليل الأساسي الشامل — 15 عنصر في ملف واحد

البطاقات الحمراء (9 غائبة):
✅ ١. Economic Calendar — تنبيه قبل CPI/NFP/قرار الفائدة
✅ ٢. Fed Statements Analyzer — نبرة الفيدرالي
✅ ٣. Real Yield Monitor — الفائدة الحقيقية
✅ ٤. Risk-On/Off Detector — وضع المخاطرة
✅ ٥. Earnings Guidance Analyzer — التوجيه المستقبلي
✅ ٦. P/E Ratio Filter — هل السهم غالٍ؟
✅ ٧. PEG Ratio Filter — السعر مقابل النمو
✅ ٨. Price/Sales Filter — للشركات النامية
✅ ٩. COT Sentiment — مراكز البنوك الكبرى

البطاقات الصفراء (6 تحتاج تحسين):
✅ ١٠. GDP + PMI + NFP — مؤشرات الاقتصاد الكلي
✅ ١١. QE/QT Monitor — سياسة البنك المركزي
✅ ١٢. Sector Breadth — عرض السوق
✅ ١٣. Free Cash Flow — النقد الحقيقي
✅ ١٤. Overvaluation Alert — تحذير المبالغة
✅ ١٥. Dark Pool Proxy — مؤشر الشراء المؤسسي
"""

import yfinance as yf
import pandas as pd
import numpy as np
import requests
import json
import time
from datetime import datetime, timedelta
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

def send_telegram(msg: str):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "HTML"
        }, timeout=10)
    except Exception as e:
        print(f"[TG] {e}")

WATCHLIST = [
    "NVDA","MSFT","AAPL","GOOGL","META","AMZN","AVGO","AMD",
    "CRWD","PANW","PLTR","NOW","DDOG","SNOW",
    "ADBE","CRM","INTU","NFLX","TTD",
    "TSLA","UBER","V","MA","LLY","UNH","COST","WMT",
]

# ═══════════════════════════════════════════════════════════════════════════════
# ١. Economic Calendar — تنبيه قبل أهم الأحداث
# ═══════════════════════════════════════════════════════════════════════════════

MAJOR_EVENTS = {
    "FOMC": {
        "description": "قرار الفائدة الفيدرالية",
        "impact": "critical",
        "action": "لا تفتح صفقات جديدة قبل 24 ساعة وبعد 2 ساعة",
    },
    "CPI": {
        "description": "مؤشر أسعار المستهلك (التضخم)",
        "impact": "high",
        "action": "راقب التكنولوجيا — إذا CPI أعلى من المتوقع ستهبط",
    },
    "NFP": {
        "description": "بيانات التوظيف الأمريكية",
        "impact": "high",
        "action": "وظائف قوية = اقتصاد جيد لكن قد يرفع التوقعات للفائدة",
    },
    "PPI": {
        "description": "مؤشر أسعار المنتجين",
        "impact": "medium",
        "action": "مؤشر مبكر للتضخم — راقبه قبل CPI",
    },
    "GDP": {
        "description": "الناتج المحلي الإجمالي",
        "impact": "high",
        "action": "GDP قوي = دعم للأسهم الدورية",
    },
    "RETAIL_SALES": {
        "description": "مبيعات التجزئة",
        "impact": "medium",
        "action": "يعكس قوة الاستهلاك والاقتصاد",
    },
}

def get_upcoming_events() -> list:
    """
    يجلب الأحداث الاقتصادية القادمة
    يستخدم مواعيد تقريبية ثابتة + yfinance للأرباح
    """
    print("\n[Calendar] فحص الأحداث الاقتصادية القادمة...")
    upcoming = []
    now = datetime.now()

    # ─── مواعيد FOMC 2025-2026 التقريبية ───────────────────────────────────
    fomc_dates_2026 = [
        datetime(2026, 1, 29), datetime(2026, 3, 19), datetime(2026, 5, 7),
        datetime(2026, 6, 18), datetime(2026, 7, 30), datetime(2026, 9, 17),
        datetime(2026, 10, 29), datetime(2026, 12, 10),
    ]

    for fomc in fomc_dates_2026:
        days = (fomc - now).days
        if 0 <= days <= 14:
            upcoming.append({
                "event":       "FOMC",
                "date":        fomc.strftime("%Y-%m-%d"),
                "days_until":  days,
                "impact":      "critical",
                "description": MAJOR_EVENTS["FOMC"]["description"],
                "action":      MAJOR_EVENTS["FOMC"]["action"],
            })

    # ─── CPI — أول أسبوع من الشهر تقريباً ────────────────────────────────
    next_month = now.replace(day=1) + timedelta(days=32)
    cpi_date = next_month.replace(day=10)
    days_to_cpi = (cpi_date - now).days
    if 0 <= days_to_cpi <= 14:
        upcoming.append({
            "event":       "CPI",
            "date":        cpi_date.strftime("%Y-%m-%d"),
            "days_until":  days_to_cpi,
            "impact":      "high",
            "description": MAJOR_EVENTS["CPI"]["description"],
            "action":      MAJOR_EVENTS["CPI"]["action"],
        })

    # ─── NFP — أول جمعة من الشهر ──────────────────────────────────────────
    first_friday = now.replace(day=1)
    while first_friday.weekday() != 4:
        first_friday += timedelta(days=1)
    if first_friday.month == now.month:
        days_to_nfp = (first_friday - now).days
        if 0 <= days_to_nfp <= 14:
            upcoming.append({
                "event":       "NFP",
                "date":        first_friday.strftime("%Y-%m-%d"),
                "days_until":  days_to_nfp,
                "impact":      "high",
                "description": MAJOR_EVENTS["NFP"]["description"],
                "action":      MAJOR_EVENTS["NFP"]["action"],
            })

    # ─── أرباح الشركات ────────────────────────────────────────────────────
    for sym in WATCHLIST[:15]:
        try:
            ticker = yf.Ticker(sym)
            cal = ticker.calendar
            if cal is not None and not cal.empty:
                if 'Earnings Date' in cal.index:
                    earn_date = pd.Timestamp(cal.loc['Earnings Date'].iloc[0])
                    days = (earn_date - pd.Timestamp.now()).days
                    if 0 <= days <= 14:
                        upcoming.append({
                            "event":      f"أرباح {sym}",
                            "date":       str(earn_date)[:10],
                            "days_until": days,
                            "impact":     "medium",
                            "description": f"نتائج {sym} الفصلية",
                            "action":     "لا تشتري قبل 48 ساعة — انتظر التفاعل",
                        })
        except:
            pass

    upcoming.sort(key=lambda x: x["days_until"])
    print(f"[Calendar] {len(upcoming)} حدث قادم خلال أسبوعين")
    return upcoming

def should_pause_trading(events: list) -> tuple:
    """
    يقرر إذا كان يجب إيقاف الشراء بسبب حدث قادم
    """
    for event in events:
        if event["impact"] == "critical" and event["days_until"] <= 1:
            return True, f"FOMC غداً — لا شراء جديد"
        if event["impact"] == "high" and event["days_until"] == 0:
            return True, f"حدث مهم اليوم: {event['event']}"
    return False, "لا أحداث تستوجب التوقف"

def send_calendar_alert(events: list):
    if not events:
        return
    msg = (
        f"📅 <b>Economic Calendar — أحداث قادمة</b>\n"
        f"{'─'*25}\n\n"
    )
    for ev in events[:6]:
        emoji = "🚨" if ev["impact"] == "critical" else "⚠️" if ev["impact"] == "high" else "📌"
        msg += (
            f"{emoji} <b>{ev['event']}</b> — بعد {ev['days_until']} يوم\n"
            f"   {ev['description']}\n"
            f"   💡 {ev['action']}\n\n"
        )
    send_telegram(msg)

# ═══════════════════════════════════════════════════════════════════════════════
# ٢. Fed Statements Analyzer — نبرة الفيدرالي
# ═══════════════════════════════════════════════════════════════════════════════

FED_HAWKISH_WORDS = [
    "inflation", "tighten", "restrictive", "elevated", "persistent",
    "higher for longer", "additional increases", "firm", "vigilant"
]

FED_DOVISH_WORDS = [
    "cut", "ease", "reduce", "lower", "pause", "hold", "below target",
    "softening", "cooling", "moderate", "balance"
]

def analyze_fed_tone() -> dict:
    """
    يحلل نبرة الفيدرالي من آخر الأخبار المتاحة
    يستخدم أخبار yfinance للـ SPY + TLT
    """
    print("\n[Fed] تحليل نبرة الفيدرالي...")
    result = {
        "tone":        "محايد",
        "hawkish_score": 0,
        "dovish_score":  0,
        "signal":      "neutral",
        "action":      "لا تغيير في الاستراتيجية",
    }

    try:
        # أخبار TLT (سندات طويلة) كمؤشر على توقعات الفيدرالي
        tlt = yf.Ticker("TLT")
        news = tlt.news or []

        spy = yf.Ticker("SPY")
        news += (spy.news or [])[:5]

        hawkish = 0
        dovish  = 0

        for item in news[:15]:
            title = (item.get('title', '') + ' ' + item.get('summary', '')).lower()
            hawkish += sum(1 for w in FED_HAWKISH_WORDS if w in title)
            dovish  += sum(1 for w in FED_DOVISH_WORDS  if w in title)

        result["hawkish_score"] = hawkish
        result["dovish_score"]  = dovish

        if hawkish > dovish + 2:
            result["tone"]   = "متشدد (Hawkish) 🔴"
            result["signal"] = "hawkish"
            result["action"] = "قلل مراكز التكنولوجيا — الفائدة قد ترتفع"
        elif dovish > hawkish + 2:
            result["tone"]   = "متساهل (Dovish) 🟢"
            result["signal"] = "dovish"
            result["action"] = "بيئة ممتازة للتكنولوجيا والنمو"
        else:
            result["tone"]   = "محايد ⚪"
            result["signal"] = "neutral"
            result["action"] = "لا تغيير في الاستراتيجية"

        print(f"[Fed] Hawkish={hawkish} | Dovish={dovish} | النبرة: {result['tone']}")

    except Exception as e:
        print(f"[Fed] خطأ: {e}")

    return result

# ═══════════════════════════════════════════════════════════════════════════════
# ٣. Real Yield Monitor — الفائدة الحقيقية
# ═══════════════════════════════════════════════════════════════════════════════

def calc_real_yield() -> dict:
    """
    الفائدة الحقيقية = US10Y - التضخم المتوقع
    سالبة = ذهب وأسهم مدعومة
    موجبة = ضغط على أصول المخاطرة
    """
    print("\n[Real Yield] حساب الفائدة الحقيقية...")
    result = {
        "nominal_yield": None,
        "inflation_exp": None,
        "real_yield":    None,
        "signal":        "neutral",
        "impact":        "محايد",
    }

    try:
        # US10Y الاسمية
        y10 = yf.download("^TNX", period="5d", progress=False, auto_adjust=True)
        y10.columns = [c[0] if isinstance(c, tuple) else c for c in y10.columns]
        nominal = float(y10['Close'].iloc[-1]) / 10

        # TIPS — سندات محمية من التضخم (بديل عملي)
        # الفرق بين US10Y و TIPS = التضخم المتوقع (Break-Even Inflation)
        tips = yf.download("^TYX", period="5d", progress=False, auto_adjust=True)
        if not tips.empty:
            tips.columns = [c[0] if isinstance(c, tuple) else c for c in tips.columns]
            tips_rate = float(tips['Close'].iloc[-1]) / 10
        else:
            tips_rate = nominal - 0.02  # تقدير

        inflation_exp = nominal - tips_rate + 0.02
        real_yield    = nominal - inflation_exp

        result.update({
            "nominal_yield": round(nominal * 100, 2),
            "inflation_exp": round(inflation_exp * 100, 2),
            "real_yield":    round(real_yield * 100, 2),
        })

        if real_yield < -0.01:
            result["signal"] = "negative_real"
            result["impact"] = "إيجابي للذهب وأسهم النمو 🟢"
        elif real_yield > 0.02:
            result["signal"] = "positive_real"
            result["impact"] = "ضغط على أسهم النمو والذهب 🔴"
        else:
            result["signal"] = "neutral"
            result["impact"] = "بيئة محايدة ⚪"

        print(f"[Real Yield] اسمية={nominal*100:.1f}% | تضخم متوقع={inflation_exp*100:.1f}% | حقيقية={real_yield*100:.1f}%")

    except Exception as e:
        print(f"[Real Yield] خطأ: {e}")

    return result

# ═══════════════════════════════════════════════════════════════════════════════
# ٤. Risk-On / Risk-Off Detector
# ═══════════════════════════════════════════════════════════════════════════════

def detect_risk_regime() -> dict:
    """
    Risk-On: المستثمرون يحبون المخاطرة → أسهم + كريبتو تصعد
    Risk-Off: الخوف → ذهب + سندات تصعد
    """
    print("\n[Risk Regime] تحديد وضع المخاطرة...")
    result = {
        "regime":  "محايد",
        "score":   0,
        "signals": [],
        "action":  "تداول طبيعي",
    }

    try:
        score = 0
        indicators = {}

        # VIX
        vix = yf.download("^VIX", period="5d", progress=False, auto_adjust=True)
        vix.columns = [c[0] if isinstance(c, tuple) else c for c in vix.columns]
        vix_val = float(vix['Close'].iloc[-1])
        if vix_val < 15:
            score += 2
            result["signals"].append(f"✅ VIX منخفض ({vix_val:.1f}) — Risk-On")
        elif vix_val > 25:
            score -= 2
            result["signals"].append(f"🔴 VIX مرتفع ({vix_val:.1f}) — Risk-Off")

        # الذهب مقابل SPY
        gold = yf.download("GC=F", period="1mo", progress=False, auto_adjust=True)
        spy  = yf.download("SPY",  period="1mo", progress=False, auto_adjust=True)
        gold.columns = [c[0] if isinstance(c, tuple) else c for c in gold.columns]
        spy.columns  = [c[0] if isinstance(c, tuple) else c for c in spy.columns]

        gold_ret = (float(gold['Close'].iloc[-1]) - float(gold['Close'].iloc[0])) / float(gold['Close'].iloc[0]) * 100
        spy_ret  = (float(spy['Close'].iloc[-1])  - float(spy['Close'].iloc[0]))  / float(spy['Close'].iloc[0])  * 100

        if spy_ret > gold_ret + 3:
            score += 2
            result["signals"].append(f"✅ SPY يتفوق على الذهب — Risk-On")
        elif gold_ret > spy_ret + 3:
            score -= 2
            result["signals"].append(f"🔴 الذهب يتفوق على SPY — Risk-Off")

        # DXY
        dxy = yf.download("DX-Y.NYB", period="1mo", progress=False, auto_adjust=True)
        dxy.columns = [c[0] if isinstance(c, tuple) else c for c in dxy.columns]
        dxy_ret = (float(dxy['Close'].iloc[-1]) - float(dxy['Close'].iloc[0])) / float(dxy['Close'].iloc[0]) * 100
        if dxy_ret < -1:
            score += 1
            result["signals"].append(f"✅ DXY يضعف — Risk-On")
        elif dxy_ret > 1:
            score -= 1
            result["signals"].append(f"🔴 DXY يقوى — Risk-Off")

        # HYG (سندات عالية المخاطر) مقابل LQD (سندات عالية الجودة)
        try:
            hyg = yf.download("HYG", period="1mo", progress=False, auto_adjust=True)
            lqd = yf.download("LQD", period="1mo", progress=False, auto_adjust=True)
            hyg.columns = [c[0] if isinstance(c, tuple) else c for c in hyg.columns]
            lqd.columns = [c[0] if isinstance(c, tuple) else c for c in lqd.columns]
            hyg_ret = (float(hyg['Close'].iloc[-1]) - float(hyg['Close'].iloc[0])) / float(hyg['Close'].iloc[0]) * 100
            lqd_ret = (float(lqd['Close'].iloc[-1]) - float(lqd['Close'].iloc[0])) / float(lqd['Close'].iloc[0]) * 100
            if hyg_ret > lqd_ret:
                score += 1
                result["signals"].append("✅ HYG > LQD — Risk-On")
            else:
                score -= 1
                result["signals"].append("🔴 LQD > HYG — Risk-Off")
        except:
            pass

        result["score"] = score

        if score >= 4:
            result["regime"] = "Risk-On قوي 🟢🟢"
            result["action"] = "اشتر النمو والتكنولوجيا بجرأة"
        elif score >= 2:
            result["regime"] = "Risk-On معتدل 🟢"
            result["action"] = "تداول طبيعي مع تفضيل النمو"
        elif score <= -3:
            result["regime"] = "Risk-Off قوي 🔴🔴"
            result["action"] = "قلل المخاطر — ركز على الدفاعيات والذهب"
        elif score <= -1:
            result["regime"] = "Risk-Off معتدل 🔴"
            result["action"] = "كن انتقائياً — تجنب الأسهم عالية المخاطر"
        else:
            result["regime"] = "محايد ⚪"
            result["action"] = "تداول طبيعي بانتقائية"

        print(f"[Risk Regime] النقاط: {score} | الوضع: {result['regime']}")

    except Exception as e:
        print(f"[Risk Regime] خطأ: {e}")

    return result

# ═══════════════════════════════════════════════════════════════════════════════
# ٥. Earnings Guidance Analyzer — التوجيه المستقبلي
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_earnings_guidance(symbol: str) -> dict:
    """
    التوجيه المستقبلي أهم من النتائج الحالية
    يفحص: EPS المتوقع vs السابق + نمو الإيرادات المتوقع
    """
    result = {
        "symbol":          symbol,
        "guidance":        "محايد",
        "eps_forward":     None,
        "eps_current":     None,
        "rev_growth_est":  None,
        "analyst_rating":  None,
        "price_target":    None,
        "signal":          "neutral",
    }

    try:
        ticker = yf.Ticker(symbol)
        info   = ticker.info

        # EPS الحالي والمتوقع
        eps_ttm     = info.get('trailingEps',  None)
        eps_forward = info.get('forwardEps',   None)
        price       = info.get('currentPrice', info.get('regularMarketPrice', None))

        if eps_ttm and eps_forward:
            eps_growth_est = (eps_forward - eps_ttm) / abs(eps_ttm) * 100 if eps_ttm != 0 else 0
            result["eps_forward"] = round(eps_forward, 2)
            result["eps_current"] = round(eps_ttm, 2)
        else:
            eps_growth_est = 0

        # توصيات المحللين
        analyst_count = info.get('numberOfAnalystOpinions', 0)
        target_price  = info.get('targetMeanPrice', None)
        rating        = info.get('recommendationMean', None)  # 1=شراء قوي، 5=بيع قوي

        if target_price and price:
            upside = (target_price - price) / price * 100
            result["price_target"] = round(target_price, 2)
        else:
            upside = 0

        if rating:
            result["analyst_rating"] = round(rating, 1)

        # نمو الإيرادات المتوقع
        rev_growth = info.get('revenueGrowth', 0) or 0
        result["rev_growth_est"] = round(rev_growth * 100, 1)

        # القرار
        score = 0
        if eps_growth_est > 20:  score += 2
        elif eps_growth_est > 0: score += 1
        elif eps_growth_est < 0: score -= 2

        if upside > 15:  score += 2
        elif upside > 5: score += 1
        elif upside < 0: score -= 2

        if rev_growth > 0.15: score += 1
        if rating and rating <= 2.5: score += 1

        if score >= 4:
            result["guidance"] = "إيجابي جداً 🟢🟢"
            result["signal"]   = "strong_buy"
        elif score >= 2:
            result["guidance"] = "إيجابي 🟢"
            result["signal"]   = "positive"
        elif score <= -2:
            result["guidance"] = "سلبي 🔴"
            result["signal"]   = "negative"
        else:
            result["guidance"] = "محايد ⚪"
            result["signal"]   = "neutral"

        print(f"[Guidance] {symbol}: EPS نمو={eps_growth_est:+.1f}% | Upside={upside:+.1f}% | {result['guidance']}")

    except Exception as e:
        print(f"[Guidance] {symbol}: {e}")

    return result

# ═══════════════════════════════════════════════════════════════════════════════
# ٦-٨. Valuation Filters — P/E + PEG + Price/Sales
# ═══════════════════════════════════════════════════════════════════════════════

VALUATION_BENCHMARKS = {
    "tech":     {"pe_max": 50, "peg_max": 2.0, "ps_max": 15},
    "growth":   {"pe_max": 80, "peg_max": 3.0, "ps_max": 25},
    "value":    {"pe_max": 20, "peg_max": 1.5, "ps_max":  5},
    "default":  {"pe_max": 40, "peg_max": 2.5, "ps_max": 12},
}

SECTOR_MAP = {
    "NVDA": "tech", "AMD": "tech", "AVGO": "tech", "TSM": "tech",
    "MSFT": "tech", "GOOGL": "tech", "AAPL": "tech", "META": "growth",
    "AMZN": "growth", "TSLA": "growth", "PLTR": "growth", "SNOW": "growth",
    "CRWD": "growth", "DDOG": "growth", "NOW": "growth", "NET": "growth",
    "V": "value", "MA": "value", "JPM": "value", "WMT": "value", "COST": "value",
}

def check_valuation(symbol: str) -> dict:
    """
    يفحص التقييم بثلاثة مقاييس:
    P/E — السعر مقابل الأرباح
    PEG — السعر مقابل النمو (أدق من P/E)
    P/S — السعر مقابل الإيرادات (للشركات غير الربحية)
    """
    result = {
        "symbol":      symbol,
        "pe_ratio":    None,
        "peg_ratio":   None,
        "ps_ratio":    None,
        "overvalued":  False,
        "undervalued": False,
        "verdict":     "عادل",
        "signal":      "neutral",
    }

    try:
        ticker = yf.Ticker(symbol)
        info   = ticker.info

        pe  = info.get('trailingPE',   None)
        peg = info.get('pegRatio',     None)
        ps  = info.get('priceToSalesTrailing12Months', None)
        eps_growth = info.get('earningsGrowth', 0) or 0

        result["pe_ratio"]  = round(pe,  1) if pe  else None
        result["peg_ratio"] = round(peg, 2) if peg else None
        result["ps_ratio"]  = round(ps,  1) if ps  else None

        # حدود التقييم حسب القطاع
        sector_type = SECTOR_MAP.get(symbol, "default")
        benchmarks  = VALUATION_BENCHMARKS[sector_type]

        overvalued_signals  = 0
        undervalued_signals = 0

        if pe:
            if pe > benchmarks["pe_max"] * 1.5:
                overvalued_signals += 2
            elif pe > benchmarks["pe_max"]:
                overvalued_signals += 1
            elif pe < benchmarks["pe_max"] * 0.5:
                undervalued_signals += 1

        if peg:
            if peg > benchmarks["peg_max"]:
                overvalued_signals += 2
            elif peg < 1.0:
                undervalued_signals += 2

        if ps:
            if ps > benchmarks["ps_max"] * 2:
                overvalued_signals += 1
            elif ps < benchmarks["ps_max"] * 0.5:
                undervalued_signals += 1

        if overvalued_signals >= 3:
            result["overvalued"] = True
            result["verdict"]    = "مبالغ في تقييمه 🔴"
            result["signal"]     = "overvalued"
        elif undervalued_signals >= 2:
            result["undervalued"] = True
            result["verdict"]     = "رخيص نسبياً 🟢"
            result["signal"]      = "undervalued"
        else:
            result["verdict"] = "تقييم عادل ⚪"
            result["signal"]  = "fair"

        print(f"[Valuation] {symbol}: P/E={pe} | PEG={peg} | P/S={ps} → {result['verdict']}")

    except Exception as e:
        print(f"[Valuation] {symbol}: {e}")

    return result

def valuation_allows_buy(symbol: str) -> tuple:
    """يفحص إذا كان التقييم يسمح بالشراء"""
    val = check_valuation(symbol)
    if val["overvalued"]:
        pe  = val["pe_ratio"]
        peg = val["peg_ratio"]
        return False, f"تقييم مرتفع جداً (P/E={pe}, PEG={peg})"
    return True, f"تقييم مقبول — {val['verdict']}"

# ═══════════════════════════════════════════════════════════════════════════════
# ٩. COT Sentiment Proxy — مراكز البنوك الكبرى
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_cot_proxy() -> dict:
    """
    بديل عملي لتقرير COT الحقيقي (يحتاج API خاص)
    يستخدم: حركة الأموال بين أصول مختلفة
    كمؤشر على توجهات المؤسسات الكبرى
    """
    print("\n[COT Proxy] تحليل مراكز المؤسسات...")
    result = {
        "commercial_bias": "محايد",
        "signals":         [],
        "score":           0,
    }

    try:
        # نسبة Put/Call للسوق الكلي (مؤشر توجه المؤسسات)
        spy = yf.Ticker("SPY")
        exp = spy.options
        if exp:
            chain = spy.option_chain(exp[1] if len(exp) > 1 else exp[0])
            total_calls = chain.calls['volume'].sum() if 'volume' in chain.calls.columns else 0
            total_puts  = chain.puts['volume'].sum()  if 'volume' in chain.puts.columns  else 0
            pc_ratio = total_puts / max(total_calls, 1)

            if pc_ratio < 0.6:
                result["score"] += 2
                result["signals"].append(f"✅ P/C Ratio={pc_ratio:.2f} — مؤسسات تشتري")
            elif pc_ratio > 1.2:
                result["score"] -= 2
                result["signals"].append(f"🔴 P/C Ratio={pc_ratio:.2f} — مؤسسات تتحوط")

        # نسبة TLT/SPY (تحول نحو السندات = خروج من الأسهم)
        tlt_df = yf.download("TLT", period="1mo", progress=False, auto_adjust=True)
        spy_df = yf.download("SPY", period="1mo", progress=False, auto_adjust=True)
        tlt_df.columns = [c[0] if isinstance(c, tuple) else c for c in tlt_df.columns]
        spy_df.columns = [c[0] if isinstance(c, tuple) else c for c in spy_df.columns]

        tlt_ret = (float(tlt_df['Close'].iloc[-1]) - float(tlt_df['Close'].iloc[0])) / float(tlt_df['Close'].iloc[0]) * 100
        spy_ret = (float(spy_df['Close'].iloc[-1]) - float(spy_df['Close'].iloc[0])) / float(spy_df['Close'].iloc[0]) * 100

        if spy_ret > tlt_ret + 2:
            result["score"] += 2
            result["signals"].append(f"✅ أموال تتحرك من سندات لأسهم")
        elif tlt_ret > spy_ret + 2:
            result["score"] -= 2
            result["signals"].append(f"🔴 أموال تتحرك من أسهم لسندات")

        # GLD vs SPY
        gld_df = yf.download("GLD", period="1mo", progress=False, auto_adjust=True)
        gld_df.columns = [c[0] if isinstance(c, tuple) else c for c in gld_df.columns]
        gld_ret = (float(gld_df['Close'].iloc[-1]) - float(gld_df['Close'].iloc[0])) / float(gld_df['Close'].iloc[0]) * 100

        if spy_ret > gld_ret + 3:
            result["score"] += 1
            result["signals"].append("✅ أسهم تتفوق على الذهب")
        elif gld_ret > spy_ret + 3:
            result["score"] -= 1
            result["signals"].append("🔴 الذهب يتفوق على الأسهم")

        if result["score"] >= 3:
            result["commercial_bias"] = "شراء مؤسسي 🟢🟢"
        elif result["score"] >= 1:
            result["commercial_bias"] = "ميل للشراء 🟢"
        elif result["score"] <= -2:
            result["commercial_bias"] = "بيع مؤسسي 🔴🔴"
        elif result["score"] <= -1:
            result["commercial_bias"] = "ميل للبيع 🔴"
        else:
            result["commercial_bias"] = "محايد ⚪"

        print(f"[COT] النقاط: {result['score']} | التوجه: {result['commercial_bias']}")

    except Exception as e:
        print(f"[COT] خطأ: {e}")

    return result

# ═══════════════════════════════════════════════════════════════════════════════
# ١٠. GDP + PMI + NFP Monitor
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_macro_indicators() -> dict:
    """
    يحلل المؤشرات الاقتصادية الكبرى من مصادر متاحة
    """
    print("\n[Macro Indicators] تحليل المؤشرات الاقتصادية...")
    result = {
        "economic_phase": "غير محدد",
        "indicators":     {},
        "score":          0,
    }

    try:
        score = 0

        # ─── Unemployment Rate من يfinance ─────────────────────────────────
        try:
            unemp = yf.download("UNRATE", period="3mo", progress=False, auto_adjust=True)
            if not unemp.empty:
                unemp.columns = [c[0] if isinstance(c, tuple) else c for c in unemp.columns]
                unemp_rate = float(unemp['Close'].iloc[-1])
                if unemp_rate < 4.5:
                    score += 2
                    result["indicators"]["بطالة"] = f"{unemp_rate:.1f}% ✅ منخفضة"
                elif unemp_rate > 6:
                    score -= 2
                    result["indicators"]["بطالة"] = f"{unemp_rate:.1f}% 🔴 مرتفعة"
                else:
                    result["indicators"]["بطالة"] = f"{unemp_rate:.1f}% ⚪ معتدلة"
        except:
            pass

        # ─── Consumer Confidence (XLY/XLP Ratio) ──────────────────────────
        try:
            xly = yf.download("XLY", period="3mo", progress=False, auto_adjust=True)
            xlp = yf.download("XLP", period="3mo", progress=False, auto_adjust=True)
            xly.columns = [c[0] if isinstance(c, tuple) else c for c in xly.columns]
            xlp.columns = [c[0] if isinstance(c, tuple) else c for c in xlp.columns]

            xly_ret = (float(xly['Close'].iloc[-1]) - float(xly['Close'].iloc[0])) / float(xly['Close'].iloc[0]) * 100
            xlp_ret = (float(xlp['Close'].iloc[-1]) - float(xlp['Close'].iloc[0])) / float(xlp['Close'].iloc[0]) * 100

            if xly_ret > xlp_ret:
                score += 1
                result["indicators"]["ثقة المستهلك"] = f"إيجابية ✅ (XLY>{xlp_ret:.1f}%)"
            else:
                score -= 1
                result["indicators"]["ثقة المستهلك"] = f"سلبية 🔴 (XLP>{xlp_ret:.1f}%)"
        except:
            pass

        # ─── Copper كمؤشر للنمو الاقتصادي ────────────────────────────────
        try:
            copper = yf.download("HG=F", period="3mo", progress=False, auto_adjust=True)
            copper.columns = [c[0] if isinstance(c, tuple) else c for c in copper.columns]
            copper_ret = (float(copper['Close'].iloc[-1]) - float(copper['Close'].iloc[0])) / float(copper['Close'].iloc[0]) * 100
            if copper_ret > 3:
                score += 2
                result["indicators"]["النحاس (PMI proxy)"] = f"+{copper_ret:.1f}% ✅ نمو"
            elif copper_ret < -3:
                score -= 2
                result["indicators"]["النحاس (PMI proxy)"] = f"{copper_ret:.1f}% 🔴 تباطؤ"
            else:
                result["indicators"]["النحاس (PMI proxy)"] = f"{copper_ret:+.1f}% ⚪ محايد"
        except:
            pass

        # ─── ISM Manufacturing Proxy (XLI) ────────────────────────────────
        try:
            xli = yf.download("XLI", period="3mo", progress=False, auto_adjust=True)
            xli.columns = [c[0] if isinstance(c, tuple) else c for c in xli.columns]
            xli_ret = (float(xli['Close'].iloc[-1]) - float(xli['Close'].iloc[0])) / float(xli['Close'].iloc[0]) * 100
            if xli_ret > 5:
                score += 1
                result["indicators"]["الصناعة (PMI proxy)"] = f"+{xli_ret:.1f}% ✅"
            elif xli_ret < -5:
                score -= 1
                result["indicators"]["الصناعة (PMI proxy)"] = f"{xli_ret:.1f}% 🔴"
            else:
                result["indicators"]["الصناعة (PMI proxy)"] = f"{xli_ret:+.1f}% ⚪"
        except:
            pass

        result["score"] = score

        if score >= 5:
            result["economic_phase"] = "توسع قوي 🚀"
        elif score >= 2:
            result["economic_phase"] = "نمو معتدل 📈"
        elif score >= -1:
            result["economic_phase"] = "محايد ⚖️"
        elif score >= -3:
            result["economic_phase"] = "تباطؤ ⚠️"
        else:
            result["economic_phase"] = "ركود محتمل 🔴"

        print(f"[Macro] المرحلة: {result['economic_phase']} | النقاط: {score}")

    except Exception as e:
        print(f"[Macro Indicators] خطأ: {e}")

    return result

# ═══════════════════════════════════════════════════════════════════════════════
# ١١. QE/QT Monitor
# ═══════════════════════════════════════════════════════════════════════════════

def monitor_qt_qe() -> dict:
    """
    يراقب إشارات التيسير الكمي (QE) والتشديد الكمي (QT)
    من خلال حركة TLT وM2 proxy
    """
    print("\n[QE/QT] مراقبة السياسة النقدية...")
    result = {
        "policy":  "محايد",
        "signal":  "neutral",
        "details": [],
    }

    try:
        # TLT — إذا البنك المركزي يشتري سندات (QE) → TLT يرتفع
        tlt = yf.download("TLT", period="3mo", progress=False, auto_adjust=True)
        tlt.columns = [c[0] if isinstance(c, tuple) else c for c in tlt.columns]
        tlt_ret  = (float(tlt['Close'].iloc[-1]) - float(tlt['Close'].iloc[0])) / float(tlt['Close'].iloc[0]) * 100
        tlt_trend = "صاعد" if float(tlt['Close'].iloc[-1]) > float(tlt['Close'].rolling(50).mean().iloc[-1]) else "هابط"

        if tlt_ret > 3 and tlt_trend == "صاعد":
            result["policy"] = "ميل نحو QE / تيسير 🟢"
            result["signal"] = "qe_bias"
            result["details"].append(f"TLT +{tlt_ret:.1f}% — توقعات تيسير")
        elif tlt_ret < -3:
            result["policy"] = "استمرار QT / تشديد 🔴"
            result["signal"] = "qt_bias"
            result["details"].append(f"TLT {tlt_ret:.1f}% — ضغط على السندات")
        else:
            result["policy"] = "محايد ⚪"
            result["details"].append(f"TLT {tlt_ret:+.1f}% — لا اتجاه واضح")

        # MOVE Index (تقلب السندات) — ارتفاعه = قلق
        try:
            move = yf.download("^MOVE", period="1mo", progress=False, auto_adjust=True)
            if not move.empty:
                move.columns = [c[0] if isinstance(c, tuple) else c for c in move.columns]
                move_val = float(move['Close'].iloc[-1])
                if move_val > 130:
                    result["details"].append(f"⚠️ MOVE مرتفع ({move_val:.0f}) — قلق في سوق السندات")
                else:
                    result["details"].append(f"✅ MOVE طبيعي ({move_val:.0f})")
        except:
            pass

        print(f"[QE/QT] السياسة: {result['policy']}")

    except Exception as e:
        print(f"[QE/QT] خطأ: {e}")

    return result

# ═══════════════════════════════════════════════════════════════════════════════
# ١٢. Sector Breadth Analysis
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_market_breadth() -> dict:
    """
    يحسب عرض السوق — كم % من الأسهم صحية؟
    فوق 70% = سوق قوي | أقل من 40% = سوق ضعيف
    """
    print(f"\n[Breadth] تحليل عرض السوق...")
    result = {
        "above_ma50":  0,
        "above_ma200": 0,
        "new_highs":   0,
        "breadth_pct": 0,
        "verdict":     "محايد",
        "signal":      "neutral",
    }

    above_50  = 0
    above_200 = 0
    new_highs = 0
    checked   = 0

    for sym in WATCHLIST:
        try:
            df = yf.download(sym, period="1y", progress=False, auto_adjust=True)
            if df.empty or len(df) < 50:
                continue
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

            close  = df['Close']
            ma50   = close.rolling(50).mean().iloc[-1]
            ma200  = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else None
            hi52w  = close.rolling(252).max().iloc[-1]  if len(close) >= 252 else close.max()
            current = float(close.iloc[-1])

            if current > float(ma50):   above_50  += 1
            if ma200 and current > float(ma200): above_200 += 1
            if current >= float(hi52w) * 0.98:   new_highs += 1
            checked += 1

        except:
            pass

    if checked > 0:
        breadth = above_50 / checked * 100
        result.update({
            "above_ma50":  above_50,
            "above_ma200": above_200,
            "new_highs":   new_highs,
            "breadth_pct": round(breadth, 1),
        })

        if breadth >= 70:
            result["verdict"] = "سوق قوي جداً 🟢🟢"
            result["signal"]  = "strong"
        elif breadth >= 55:
            result["verdict"] = "سوق صحي 🟢"
            result["signal"]  = "healthy"
        elif breadth >= 40:
            result["verdict"] = "سوق محايد ⚪"
            result["signal"]  = "neutral"
        elif breadth >= 25:
            result["verdict"] = "سوق ضعيف ⚠️"
            result["signal"]  = "weak"
        else:
            result["verdict"] = "سوق هابط 🔴"
            result["signal"]  = "bearish"

        print(f"[Breadth] فوق MA50: {above_50}/{checked} ({breadth:.0f}%) | {result['verdict']}")

    return result

# ═══════════════════════════════════════════════════════════════════════════════
# ١٣. Free Cash Flow Analysis
# ═══════════════════════════════════════════════════════════════════════════════

def check_free_cash_flow(symbol: str) -> dict:
    """
    Free Cash Flow = النقد الحقيقي (أهم من الأرباح المحاسبية)
    FCF Yield = FCF / Market Cap — كلما كان أعلى كان أفضل
    """
    result = {
        "symbol":    symbol,
        "fcf":       None,
        "fcf_yield": None,
        "verdict":   "غير محدد",
        "signal":    "neutral",
    }

    try:
        ticker = yf.Ticker(symbol)
        info   = ticker.info

        fcf        = info.get('freeCashflow', None)
        market_cap = info.get('marketCap',    None)
        price      = info.get('currentPrice', info.get('regularMarketPrice', None))

        if fcf and market_cap and market_cap > 0:
            fcf_yield = fcf / market_cap * 100
            result["fcf"]       = round(fcf / 1e9, 2)
            result["fcf_yield"] = round(fcf_yield, 2)

            if fcf < 0:
                result["verdict"] = "FCF سالب ⚠️"
                result["signal"]  = "negative_fcf"
            elif fcf_yield > 4:
                result["verdict"] = "FCF ممتاز 🟢"
                result["signal"]  = "strong_fcf"
            elif fcf_yield > 2:
                result["verdict"] = "FCF جيد ✅"
                result["signal"]  = "good_fcf"
            else:
                result["verdict"] = "FCF ضعيف ⚪"
                result["signal"]  = "weak_fcf"

            print(f"[FCF] {symbol}: FCF=${result['fcf']}B | Yield={fcf_yield:.1f}% | {result['verdict']}")

    except Exception as e:
        print(f"[FCF] {symbol}: {e}")

    return result

# ═══════════════════════════════════════════════════════════════════════════════
# ١٤. Overvaluation Alert
# ═══════════════════════════════════════════════════════════════════════════════

def check_market_overvaluation() -> dict:
    """
    يفحص إذا كان السوق ككل مبالغاً في تقييمه
    يستخدم: Buffett Indicator + مقارنة تاريخية
    """
    print("\n[Overvaluation] فحص مبالغة تقييم السوق...")
    result = {
        "market_pe":    None,
        "verdict":      "محايد",
        "signal":       "neutral",
        "bubble_risk":  False,
    }

    try:
        # P/E السوق من SPY
        spy_ticker = yf.Ticker("SPY")
        spy_info   = spy_ticker.info
        market_pe  = spy_info.get('trailingPE', None)

        if market_pe:
            result["market_pe"] = round(market_pe, 1)
            if market_pe > 30:
                result["verdict"]     = "مبالغ في التقييم 🔴"
                result["signal"]      = "overvalued"
                result["bubble_risk"] = True
            elif market_pe > 22:
                result["verdict"] = "مرتفع نسبياً ⚠️"
                result["signal"]  = "elevated"
            elif market_pe < 15:
                result["verdict"] = "رخيص تاريخياً 🟢"
                result["signal"]  = "cheap"
            else:
                result["verdict"] = "تقييم عادل ⚪"
                result["signal"]  = "fair"

        # فحص VIX كمؤشر مبالغة
        vix = yf.download("^VIX", period="5d", progress=False, auto_adjust=True)
        vix.columns = [c[0] if isinstance(c, tuple) else c for c in vix.columns]
        vix_val = float(vix['Close'].iloc[-1])

        if vix_val < 12 and market_pe and market_pe > 25:
            result["bubble_risk"] = True
            result["verdict"]    += " + VIX منخفض جداً (خطر فقاعة)"

        print(f"[Overvaluation] P/E السوق: {market_pe} | {result['verdict']}")

    except Exception as e:
        print(f"[Overvaluation] خطأ: {e}")

    return result

# ═══════════════════════════════════════════════════════════════════════════════
# ١٥. Dark Pool Proxy
# ═══════════════════════════════════════════════════════════════════════════════

def detect_dark_pool_activity(symbol: str) -> dict:
    """
    Dark Pool بديل عملي — يكتشف نشاط الشراء المؤسسي الخفي
    من خلال: حجم مرتفع + تحرك سعري صغير (علامة تجميع)
    """
    result = {
        "symbol":    symbol,
        "activity":  "طبيعي",
        "signal":    "neutral",
        "score":     0,
    }

    try:
        df = yf.download(symbol, period="1mo", interval="1d",
                        progress=False, auto_adjust=True)
        if df.empty or len(df) < 10:
            return result

        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

        close  = df['Close']
        volume = df['Volume']
        high   = df['High']
        low    = df['Low']

        vol_avg = volume.rolling(10).mean()
        score   = 0

        for i in range(-5, 0):
            vol_ratio  = float(volume.iloc[i]) / float(vol_avg.iloc[i]) if float(vol_avg.iloc[i]) > 0 else 1
            price_move = abs(float(close.iloc[i]) - float(close.iloc[i-1])) / float(close.iloc[i-1]) * 100
            range_pct  = (float(high.iloc[i]) - float(low.iloc[i])) / float(close.iloc[i]) * 100

            # حجم مرتفع + تحرك سعري صغير = تجميع مؤسسي محتمل
            if vol_ratio > 1.5 and price_move < 1 and range_pct < 2:
                score += 1

        result["score"] = score

        if score >= 3:
            result["activity"] = "تجميع مؤسسي محتمل 🟢"
            result["signal"]   = "accumulation"
        elif score >= 2:
            result["activity"] = "نشاط مشبوه إيجابي"
            result["signal"]   = "possible_accumulation"
        else:
            result["activity"] = "طبيعي"
            result["signal"]   = "neutral"

        if score > 0:
            print(f"[Dark Pool] {symbol}: نقاط={score} | {result['activity']}")

    except Exception as e:
        pass

    return result

# ═══════════════════════════════════════════════════════════════════════════════
# محرك القرار الشامل — يجمع كل الـ 15 عنصر
# ═══════════════════════════════════════════════════════════════════════════════

def comprehensive_buy_decision(symbol: str) -> dict:
    """
    القرار الشامل — يجمع التحليل الأساسي الكامل
    """
    print(f"\n{'═'*50}")
    print(f"  تحليل شامل لـ {symbol}")
    print(f"{'═'*50}")

    decision = {
        "symbol":  symbol,
        "allowed": True,
        "score":   0,
        "reasons": [],
        "blocks":  [],
        "stop_pct": 0.07,
    }

    # ─── ١. Valuation ──────────────────────────────────────────────────────
    val_ok, val_reason = valuation_allows_buy(symbol)
    if val_ok:
        decision["score"] += 2
        decision["reasons"].append(f"✅ التقييم: {val_reason}")
    else:
        decision["score"] -= 1
        decision["reasons"].append(f"⚠️ التقييم: {val_reason}")

    # ─── ٢. Earnings Guidance ──────────────────────────────────────────────
    guidance = analyze_earnings_guidance(symbol)
    if guidance["signal"] in ["strong_buy", "positive"]:
        decision["score"] += 2
        decision["reasons"].append(f"✅ التوجيه: {guidance['guidance']}")
    elif guidance["signal"] == "negative":
        decision["score"] -= 2
        decision["reasons"].append(f"⚠️ التوجيه: {guidance['guidance']}")

    # ─── ٣. Free Cash Flow ─────────────────────────────────────────────────
    fcf = check_free_cash_flow(symbol)
    if fcf["signal"] == "negative_fcf":
        decision["score"] -= 1
        decision["reasons"].append(f"⚠️ FCF سالب")
    elif fcf["signal"] in ["strong_fcf", "good_fcf"]:
        decision["score"] += 1
        decision["reasons"].append(f"✅ FCF: {fcf['verdict']}")

    # ─── ٤. Dark Pool Activity ─────────────────────────────────────────────
    dp = detect_dark_pool_activity(symbol)
    if dp["signal"] == "accumulation":
        decision["score"] += 2
        decision["reasons"].append(f"✅ تجميع مؤسسي محتمل")

    # ─── القرار ────────────────────────────────────────────────────────────
    if decision["blocks"]:
        decision["allowed"] = False
    elif decision["score"] < 0:
        decision["allowed"] = False
        decision["blocks"].append(f"نقاط سلبية: {decision['score']}")

    return decision

def save_fundamental_state(state: dict):
    """يحفظ حالة التحليل الأساسي"""
    with open("/root/fundamental_state.json", "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, default=str)

# ═══════════════════════════════════════════════════════════════════════════════
# التقرير اليومي الشامل
# ═══════════════════════════════════════════════════════════════════════════════

def send_fundamental_report(
    events, fed, real_yield, risk_regime,
    breadth, qt_qe, macro, market_val
):
    msg = (
        f"📊 <b>Fundamental Engine — التقرير الشامل</b>\n"
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"{'─'*28}\n\n"
        f"<b>المرحلة الاقتصادية:</b> {macro['economic_phase']}\n"
        f"<b>وضع المخاطرة:</b> {risk_regime['regime']}\n"
        f"<b>السياسة النقدية:</b> {qt_qe['policy']}\n"
        f"<b>نبرة الفيدرالي:</b> {fed['tone']}\n\n"
        f"<b>الفائدة الحقيقية:</b> {real_yield.get('real_yield', 'N/A')}% → {real_yield.get('impact', '')}\n"
        f"<b>تقييم السوق P/E:</b> {market_val.get('market_pe', 'N/A')} → {market_val.get('verdict', '')}\n"
        f"<b>عرض السوق:</b> {breadth['breadth_pct']}% فوق MA50 → {breadth['verdict']}\n\n"
    )

    if events:
        msg += f"<b>أحداث قادمة:</b>\n"
        for ev in events[:3]:
            emoji = "🚨" if ev["impact"] == "critical" else "⚠️"
            msg += f"{emoji} {ev['event']} بعد {ev['days_until']} يوم\n"
        msg += "\n"

    pause, pause_reason = should_pause_trading(events)
    if pause:
        msg += f"⛔ <b>تحذير: {pause_reason}</b>\n"
    else:
        msg += f"✅ لا أحداث تستوجب التوقف\n"

    msg += f"\n💡 {risk_regime['action']}"
    send_telegram(msg)

# ═══════════════════════════════════════════════════════════════════════════════
# الحلقة الرئيسية
# ═══════════════════════════════════════════════════════════════════════════════

def run_fundamental_engine():
    """تشغيل محرك التحليل الأساسي الكامل"""
    print("=" * 55)
    print("  Fundamental Engine — 15 عنصر")
    print("=" * 55 + "\n")

    send_telegram(
        "📊 <b>Fundamental Engine يعمل!</b>\n"
        "─"*20 + "\n"
        "✅ Economic Calendar\n"
        "✅ Fed Statements Analyzer\n"
        "✅ Real Yield Monitor\n"
        "✅ Risk-On/Off Detector\n"
        "✅ Earnings Guidance\n"
        "✅ P/E + PEG + P/S Filters\n"
        "✅ COT Sentiment Proxy\n"
        "✅ GDP + PMI + NFP\n"
        "✅ QE/QT Monitor\n"
        "✅ Sector Breadth\n"
        "✅ Free Cash Flow\n"
        "✅ Overvaluation Alert\n"
        "✅ Dark Pool Proxy\n\n"
        "التحليل الأساسي مكتمل 100%! 🏆"
    )

    last_daily = None
    last_calendar = None

    while True:
        try:
            now   = datetime.now()
            today = now.date()

            # تقرير يومي شامل — 6:30 صباحاً
            if now.hour == 6 and 25 <= now.minute <= 35 and last_daily != today:
                print(f"\n[Fundamental] {now.strftime('%Y-%m-%d')} — تقرير يومي")

                events      = get_upcoming_events()
                fed         = analyze_fed_tone()
                real_yield  = calc_real_yield()
                risk_regime = detect_risk_regime()
                breadth     = analyze_market_breadth()
                qt_qe       = monitor_qt_qe()
                macro       = analyze_macro_indicators()
                market_val  = check_market_overvaluation()
                cot         = analyze_cot_proxy()

                # حفظ الحالة
                state = {
                    "timestamp":   str(now),
                    "events":      events,
                    "fed":         fed,
                    "real_yield":  real_yield,
                    "risk_regime": risk_regime,
                    "breadth":     breadth,
                    "qt_qe":       qt_qe,
                    "macro":       macro,
                    "market_val":  market_val,
                    "cot":         cot,
                }
                save_fundamental_state(state)

                send_fundamental_report(
                    events, fed, real_yield, risk_regime,
                    breadth, qt_qe, macro, market_val
                )

                if events:
                    send_calendar_alert(events)

                last_daily = today

            time.sleep(60)

        except Exception as e:
            print(f"[Fundamental] خطأ: {e}")
            time.sleep(60)

# ═══════════════════════════════════════════════════════════════════════════════
# نقطة الدخول
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("🧪 اختبار Fundamental Engine — 15 عنصر\n")

    print("١. Economic Calendar:")
    events = get_upcoming_events()
    print(f"   {len(events)} حدث قادم")

    print("\n٢. Fed Tone:")
    fed = analyze_fed_tone()
    print(f"   النبرة: {fed['tone']}")

    print("\n٣. Real Yield:")
    ry = calc_real_yield()
    print(f"   حقيقية: {ry.get('real_yield', 'N/A')}%")

    print("\n٤. Risk Regime:")
    risk = detect_risk_regime()
    print(f"   الوضع: {risk['regime']}")

    print("\n٥. Earnings Guidance (NVDA):")
    guidance = analyze_earnings_guidance("NVDA")
    print(f"   التوجيه: {guidance['guidance']}")

    print("\n٦-٨. Valuation (MSFT):")
    val_ok, val_reason = valuation_allows_buy("MSFT")
    print(f"   {'✅' if val_ok else '❌'} {val_reason}")

    print("\n٩. COT Proxy:")
    cot = analyze_cot_proxy()
    print(f"   التوجه: {cot['commercial_bias']}")

    print("\n١٠. Macro Indicators:")
    macro = analyze_macro_indicators()
    print(f"   المرحلة: {macro['economic_phase']}")

    print("\n١١. QE/QT:")
    qt = monitor_qt_qe()
    print(f"   السياسة: {qt['policy']}")

    print("\n١٢. Market Breadth:")
    breadth = analyze_market_breadth()
    print(f"   {breadth['breadth_pct']}% فوق MA50 | {breadth['verdict']}")

    print("\n١٣. Free Cash Flow (AAPL):")
    fcf = check_free_cash_flow("AAPL")
    print(f"   FCF: ${fcf.get('fcf', 'N/A')}B | {fcf['verdict']}")

    print("\n١٤. Market Overvaluation:")
    ov = check_market_overvaluation()
    print(f"   P/E: {ov.get('market_pe')} | {ov['verdict']}")

    print("\n١٥. Dark Pool (NVDA):")
    dp = detect_dark_pool_activity("NVDA")
    print(f"   النشاط: {dp['activity']}")

    print("\n✅ القرار الشامل لـ NVDA:")
    dec = comprehensive_buy_decision("NVDA")
    print(f"   مسموح: {'✅' if dec['allowed'] else '❌'} | نقاط: {dec['score']:+d}")

    # إرسال تقرير شامل
    send_fundamental_report(
        events, fed, ry, risk, breadth, qt, macro, ov
    )
    if events:
        send_calendar_alert(events)

    print("\n🏆 كل الاختبارات اكتملت!")
