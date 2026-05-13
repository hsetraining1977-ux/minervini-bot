"""
macro_intelligence.py
======================
ذكاء اقتصادي كلي — يراقب المؤشرات الكبرى
ويترجمها لقرارات تداول تلقائية
✅ DXY — قوة الدولار
✅ US10Y — عوائد السندات
✅ VIX — مؤشر الخوف
✅ النحاس — صحة الاقتصاد
✅ الذهب والنفط — الملاذ الآمن
✅ Yield Curve — خطر الركود
✅ قرار تلقائي: اشتر / انتظر / تحوط
"""

import yfinance as yf
import pandas as pd
import numpy as np
import requests
import time
import json
from datetime import datetime
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

# ─── Telegram ─────────────────────────────────────────────────────────────────
def send_telegram(msg: str):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "HTML"
        }, timeout=10)
    except Exception as e:
        print(f"[TG] خطأ: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# المؤشرات الكبرى
# ═══════════════════════════════════════════════════════════════════════════════

MACRO_SYMBOLS = {
    "DXY":    "DX-Y.NYB",   # مؤشر الدولار
    "US10Y":  "^TNX",       # عائد سندات 10 سنوات
    "US02Y":  "^IRX",       # عائد سندات 2 سنوات
    "VIX":    "^VIX",       # مؤشر الخوف
    "GOLD":   "GC=F",       # الذهب
    "OIL":    "CL=F",       # النفط
    "COPPER": "HG=F",       # النحاس
    "SPY":    "SPY",        # S&P 500
    "QQQ":    "QQQ",        # ناسداك
    "TLT":    "TLT",        # سندات طويلة الأمد
}

# حدود المؤشرات
THRESHOLDS = {
    "DXY_HIGH":      105,    # دولار قوي جداً
    "DXY_LOW":       100,    # دولار ضعيف
    "US10Y_DANGER":  4.5,    # خطر على التكنولوجيا
    "US10Y_HIGH":    5.0,    # خطر شديد
    "VIX_PANIC":     40,     # ذعر = فرصة شراء
    "VIX_FEAR":      25,     # قلق
    "VIX_CALM":      15,     # هدوء مفرط
    "COPPER_RISE":   3,      # نمو اقتصادي (%)
}

# ═══════════════════════════════════════════════════════════════════════════════
# جلب بيانات المؤشرات
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_macro_data() -> dict:
    """يجلب بيانات كل المؤشرات الكبرى"""
    print("\n[Macro] جلب بيانات المؤشرات...")
    data = {}

    for name, symbol in MACRO_SYMBOLS.items():
        try:
            df = yf.download(symbol, period="3mo", progress=False, auto_adjust=True)
            if df.empty:
                continue
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
            close = df['Close'].dropna()

            current  = float(close.iloc[-1])
            prev_day = float(close.iloc[-2]) if len(close) > 1 else current
            prev_wk  = float(close.iloc[-5]) if len(close) > 5 else current
            prev_mo  = float(close.iloc[-21]) if len(close) > 21 else current

            data[name] = {
                "current":    round(current, 2),
                "day_chg":    round((current - prev_day) / prev_day * 100, 2),
                "week_chg":   round((current - prev_wk)  / prev_wk  * 100, 2),
                "month_chg":  round((current - prev_mo)  / prev_mo  * 100, 2),
                "ma20":       round(float(close.rolling(20).mean().iloc[-1]), 2),
                "ma50":       round(float(close.rolling(50).mean().iloc[-1]), 2),
            }
            print(f"  {name:8}: {current:.2f} ({data[name]['day_chg']:+.2f}%)")

        except Exception as e:
            print(f"  ❌ {name}: {e}")

    return data

# ═══════════════════════════════════════════════════════════════════════════════
# تحليل الوضع الاقتصادي الكلي
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_macro_regime(data: dict) -> dict:
    """
    يحلل الوضع الاقتصادي الكلي ويحدد:
    - مرحلة السوق
    - توصية التداول
    - القطاعات المفضلة
    """
    signals = []
    warnings = []
    score = 0  # موجب = شراء، سالب = تجنب

    # ─── ١. DXY — قوة الدولار ───────────────────────────────────────────────
    if "DXY" in data:
        dxy = data["DXY"]["current"]
        dxy_chg = data["DXY"]["month_chg"]

        if dxy > THRESHOLDS["DXY_HIGH"] and dxy_chg > 2:
            signals.append("⚠️ DXY قوي جداً — ضغط على أسهم النمو والسلع")
            warnings.append("avoid_growth")
            score -= 2
        elif dxy < THRESHOLDS["DXY_LOW"] and dxy_chg < -2:
            signals.append("✅ DXY ضعيف — بيئة إيجابية للأسهم والسلع")
            score += 2
        else:
            signals.append(f"⚖️ DXY محايد ({dxy:.1f})")

    # ─── ٢. US10Y — عوائد السندات ───────────────────────────────────────────
    if "US10Y" in data:
        y10 = data["US10Y"]["current"] / 10  # تحويل من نقاط أساس
        y10_display = data["US10Y"]["current"]

        if y10_display > THRESHOLDS["US10Y_HIGH"] * 10:
            signals.append(f"🔴 US10Y خطير ({y10_display:.1f}) — تجنب التكنولوجيا فوراً")
            warnings.append("avoid_tech")
            warnings.append("avoid_growth")
            score -= 3
        elif y10_display > THRESHOLDS["US10Y_DANGER"] * 10:
            signals.append(f"⚠️ US10Y مرتفع ({y10_display:.1f}) — ضغط على التكنولوجيا")
            warnings.append("reduce_tech")
            score -= 1
        else:
            signals.append(f"✅ US10Y مقبول ({y10_display:.1f})")
            score += 1

    # ─── ٣. Yield Curve — منحنى العائد ─────────────────────────────────────
    if "US10Y" in data and "US02Y" in data:
        spread = data["US10Y"]["current"] - data["US02Y"]["current"]
        if spread < 0:
            signals.append(f"🚨 Yield Curve مقلوب! ({spread:.1f}) — خطر ركود")
            warnings.append("recession_risk")
            score -= 2
        else:
            signals.append(f"✅ Yield Curve طبيعي (+{spread:.1f})")
            score += 1

    # ─── ٤. VIX — مؤشر الخوف ────────────────────────────────────────────────
    if "VIX" in data:
        vix = data["VIX"]["current"]

        if vix > THRESHOLDS["VIX_PANIC"]:
            signals.append(f"💎 VIX ذعر ({vix:.1f}) — فرصة شراء تاريخية!")
            score += 3  # الجميع يبيع = فرصة ذهبية
        elif vix > THRESHOLDS["VIX_FEAR"]:
            signals.append(f"⚠️ VIX قلق ({vix:.1f}) — تداول بحذر")
            score -= 1
        elif vix < THRESHOLDS["VIX_CALM"]:
            signals.append(f"⚠️ VIX هادئ جداً ({vix:.1f}) — السوق مخدر")
            score -= 1
        else:
            signals.append(f"✅ VIX طبيعي ({vix:.1f})")
            score += 1

    # ─── ٥. النحاس — صحة الاقتصاد ──────────────────────────────────────────
    if "COPPER" in data:
        copper_chg = data["COPPER"]["month_chg"]

        if copper_chg > THRESHOLDS["COPPER_RISE"]:
            signals.append(f"✅ النحاس يرتفع ({copper_chg:+.1f}%) — نمو اقتصادي")
            score += 2
        elif copper_chg < -THRESHOLDS["COPPER_RISE"]:
            signals.append(f"⚠️ النحاس يهبط ({copper_chg:+.1f}%) — تباطؤ اقتصادي")
            score -= 2
        else:
            signals.append(f"⚖️ النحاس محايد ({copper_chg:+.1f}%)")

    # ─── ٦. الذهب — الملاذ الآمن ────────────────────────────────────────────
    if "GOLD" in data:
        gold_chg = data["GOLD"]["month_chg"]
        gold_cur = data["GOLD"]["current"]

        if gold_chg > 5:
            signals.append(f"⚠️ الذهب يصعد بقوة ({gold_chg:+.1f}%) — خوف في السوق")
            score -= 1
        elif gold_chg > 2:
            signals.append(f"⚖️ الذهب يرتفع ({gold_chg:+.1f}%) — تحوط معتدل")
        else:
            signals.append(f"✅ الذهب مستقر ({gold_chg:+.1f}%)")
            score += 1

    # ─── ٧. النفط — تكلفة الاقتصاد ──────────────────────────────────────────
    if "OIL" in data:
        oil_chg = data["OIL"]["month_chg"]

        if oil_chg > 10:
            signals.append(f"⚠️ النفط يرتفع بقوة ({oil_chg:+.1f}%) — ضغط تضخمي")
            warnings.append("oil_inflation")
            score -= 1
        elif oil_chg < -10:
            signals.append(f"⚠️ النفط ينهار ({oil_chg:+.1f}%) — خوف من ركود")
            score -= 1
        else:
            signals.append(f"✅ النفط مستقر ({oil_chg:+.1f}%)")

    # ─── تحديد المرحلة ───────────────────────────────────────────────────────
    if score >= 5:
        phase = "🚀 صعود قوي — اشتر بجرأة"
        action = "BUY_AGGRESSIVE"
        preferred_sectors = ["التكنولوجيا", "أشباه الموصلات", "السيبراني", "النمو"]
    elif score >= 2:
        phase = "📈 بيئة إيجابية — اشتر بانتقائية"
        action = "BUY_SELECTIVE"
        preferred_sectors = ["التكنولوجيا", "الصحة", "الاستهلاك"]
    elif score >= -1:
        phase = "⚖️ بيئة محايدة — انتقائي جداً"
        action = "SELECTIVE"
        preferred_sectors = ["الدفاعي", "الصحة", "المالية"]
    elif score >= -3:
        phase = "⚠️ بيئة سلبية — قلل المخاطر"
        action = "REDUCE"
        preferred_sectors = ["الطاقة", "الذهب", "الدفاعي"]
    else:
        phase = "🔴 بيئة خطرة — انتظر أو تحوط"
        action = "CASH"
        preferred_sectors = ["النقد", "سندات قصيرة", "الذهب"]

    return {
        "score":             score,
        "phase":             phase,
        "action":            action,
        "preferred_sectors": preferred_sectors,
        "signals":           signals,
        "warnings":          warnings,
        "timestamp":         str(datetime.now()),
    }

# ═══════════════════════════════════════════════════════════════════════════════
# فلتر الشراء — يمنع الشراء إذا الماكرو سلبي
# ═══════════════════════════════════════════════════════════════════════════════

def macro_allows_buy(symbol: str, macro_state: dict) -> tuple:
    """
    يقرر إذا كان الماكرو يسمح بشراء هذا السهم
    يرجع (True/False, السبب)
    """
    action   = macro_state.get("action", "SELECTIVE")
    warnings = macro_state.get("warnings", [])

    # تصنيف السهم
    tech_stocks   = ["NVDA","MSFT","AAPL","GOOGL","META","AMZN","AVGO","AMD",
                     "CRWD","PANW","PLTR","NOW","DDOG","SNOW","ADBE","CRM","NFLX"]
    energy_stocks = ["XOM","CVX","OXY"]
    gold_stocks   = ["GLD","GOLD","NEM"]

    is_tech   = symbol in tech_stocks
    is_energy = symbol in energy_stocks

    # قرارات الفلتر
    if action == "CASH":
        return False, "السوق خطير — لا شراء"

    if action == "REDUCE":
        if is_tech and "avoid_tech" in warnings:
            return False, "عوائد السندات عالية — تجنب التكنولوجيا"
        return False, "بيئة سلبية — قلل المخاطر"

    if "avoid_tech" in warnings and is_tech:
        return False, f"US10Y مرتفع — تجنب {symbol}"

    if "avoid_growth" in warnings and is_tech:
        return False, "DXY قوي — تجنب أسهم النمو"

    if "recession_risk" in warnings:
        if not is_energy:
            return False, "خطر ركود — تجنب الأسهم الدورية"

    return True, "الماكرو يسمح بالشراء"

# ═══════════════════════════════════════════════════════════════════════════════
# تقرير Telegram
# ═══════════════════════════════════════════════════════════════════════════════

def send_macro_report(macro_data: dict, analysis: dict):
    """يرسل تقرير الماكرو على Telegram"""

    msg = (
        f"🌍 <b>Macro Intelligence Report</b>\n"
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"{'─'*28}\n\n"
        f"<b>المرحلة: {analysis['phase']}</b>\n"
        f"النقاط: {analysis['score']:+d}\n\n"
    )

    # أهم المؤشرات
    msg += "📊 <b>المؤشرات الرئيسية:</b>\n"
    if "DXY" in macro_data:
        msg += f"💵 DXY: {macro_data['DXY']['current']} ({macro_data['DXY']['day_chg']:+.1f}%)\n"
    if "US10Y" in macro_data:
        msg += f"📈 US10Y: {macro_data['US10Y']['current']:.1f} نقطة أساس\n"
    if "VIX" in macro_data:
        msg += f"😱 VIX: {macro_data['VIX']['current']:.1f}\n"
    if "GOLD" in macro_data:
        msg += f"🥇 الذهب: ${macro_data['GOLD']['current']:,.0f} ({macro_data['GOLD']['month_chg']:+.1f}% شهري)\n"
    if "OIL" in macro_data:
        msg += f"🛢️ النفط: ${macro_data['OIL']['current']:.1f} ({macro_data['OIL']['month_chg']:+.1f}% شهري)\n"
    if "COPPER" in macro_data:
        msg += f"🔧 النحاس: ${macro_data['COPPER']['current']:.2f} ({macro_data['COPPER']['month_chg']:+.1f}% شهري)\n"

    # الإشارات
    msg += f"\n📡 <b>الإشارات:</b>\n"
    for signal in analysis["signals"][:5]:
        msg += f"{signal}\n"

    # القطاعات المفضلة
    msg += f"\n✅ <b>القطاعات المفضلة:</b>\n"
    msg += ", ".join(analysis["preferred_sectors"])

    # التحذيرات
    if analysis["warnings"]:
        msg += f"\n\n⚠️ <b>تحذيرات:</b>\n"
        for w in analysis["warnings"]:
            msg += f"• {w}\n"

    send_telegram(msg)
    print("[Macro] تقرير أُرسل على Telegram ✅")

# ═══════════════════════════════════════════════════════════════════════════════
# حفظ وتحميل الحالة
# ═══════════════════════════════════════════════════════════════════════════════

def save_macro_state(analysis: dict):
    """يحفظ حالة الماكرو للاستخدام في auto_monitor"""
    with open("/root/macro_state.json", "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)

def load_macro_state() -> dict:
    """يحمّل آخر حالة ماكرو"""
    try:
        with open("/root/macro_state.json", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"action": "SELECTIVE", "warnings": [], "score": 0}

# ═══════════════════════════════════════════════════════════════════════════════
# الحلقة الرئيسية
# ═══════════════════════════════════════════════════════════════════════════════

def run_macro_intelligence():
    """تشغيل Macro Intelligence بجدول زمني"""
    print("=" * 55)
    print("  Macro Intelligence — بدء التشغيل")
    print("  ✅ DXY + US10Y + VIX")
    print("  ✅ الذهب + النفط + النحاس")
    print("  ✅ Yield Curve")
    print("  ✅ قرار تلقائي كل يوم")
    print("=" * 55 + "\n")

    send_telegram(
        "🌍 <b>Macro Intelligence يعمل!</b>\n"
        "─"*20 + "\n"
        "✅ يراقب 7 مؤشرات كبرى\n"
        "✅ يقرر تلقائياً: اشتر/انتظر/تحوط\n"
        "✅ تقرير يومي الساعة 7 صباحاً\n\n"
        "النظام يفكر كصندوق استثمار كبير! 🧠"
    )

    last_daily = None

    while True:
        try:
            now = datetime.now()

            # تحليل يومي الساعة 7 صباحاً
            if now.hour == 7 and now.minute < 5 and last_daily != now.date():
                print(f"\n[Macro] {now.strftime('%Y-%m-%d')} — تحليل يومي")
                macro_data = fetch_macro_data()
                analysis   = analyze_macro_regime(macro_data)
                save_macro_state(analysis)
                send_macro_report(macro_data, analysis)
                last_daily = now.date()

            time.sleep(60)

        except Exception as e:
            print(f"[Macro] خطأ: {e}")
            time.sleep(60)

# ═══════════════════════════════════════════════════════════════════════════════
# نقطة الدخول
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# Correlation Monitor — الخيوط الخفية
# ═══════════════════════════════════════════════════════════════════════════════

def detect_hidden_signals(macro_data: dict) -> list:
    """
    يكتشف الخيوط الخفية من العلاقات بين المؤشرات
    قبل أن تتحدث عنها القنوات الإخبارية
    """
    signals = []

    # ─── خيط ١: DXY يرتفع + الذهب يرتفع = خوف حقيقي ─────────────────────
    if "DXY" in macro_data and "GOLD" in macro_data:
        dxy_up  = macro_data["DXY"]["week_chg"] > 1
        gold_up = macro_data["GOLD"]["week_chg"] > 1
        if dxy_up and gold_up:
            signals.append(
                "🚨 <b>خيط خفي:</b> DXY والذهب يرتفعان معاً\n"
                "   → خوف حقيقي في السوق، ليس مجرد تقلب عادي\n"
                "   → المؤسسات تشتري الملاذات الآمنة"
            )

    # ─── خيط ٢: VIX يرتفع + SPY يهبط = بيع مؤسسي ─────────────────────────
    if "VIX" in macro_data and "SPY" in macro_data:
        vix_spike = macro_data["VIX"]["week_chg"] > 20
        spy_drop  = macro_data["SPY"]["week_chg"] < -2
        if vix_spike and spy_drop:
            signals.append(
                "⚠️ <b>خيط خفي:</b> VIX يقفز + SPY يهبط\n"
                "   → بيع مؤسسي منظم، ليس ذعراً عشوائياً\n"
                "   → انتظر استقرار VIX قبل الشراء"
            )

    # ─── خيط ٣: النحاس يهبط + SPY يرتفع = صعود وهمي ──────────────────────
    if "COPPER" in macro_data and "SPY" in macro_data:
        copper_drop = macro_data["COPPER"]["month_chg"] < -3
        spy_up      = macro_data["SPY"]["month_chg"] > 3
        if copper_drop and spy_up:
            signals.append(
                "🔍 <b>خيط خفي:</b> النحاس يهبط والأسهم ترتفع\n"
                "   → الصعود غير مدعوم اقتصادياً (صعود وهمي)\n"
                "   → احذر من انعكاس مفاجئ"
            )

    # ─── خيط ٤: US10Y يرتفع + QQQ يهبط = ضغط على التكنولوجيا ─────────────
    if "US10Y" in macro_data and "QQQ" in macro_data:
        y10_up  = macro_data["US10Y"]["week_chg"] > 5
        qqq_drop = macro_data["QQQ"]["week_chg"] < -2
        if y10_up and qqq_drop:
            signals.append(
                "📉 <b>خيط خفي:</b> السندات ترتفع + ناسداك يهبط\n"
                "   → أموال تخرج من التكنولوجيا للسندات\n"
                "   → قلل مراكز التكنولوجيا مؤقتاً"
            )

    # ─── خيط ٥: الذهب يهبط + النحاس يرتفع = انتعاش اقتصادي ───────────────
    if "GOLD" in macro_data and "COPPER" in macro_data:
        gold_drop   = macro_data["GOLD"]["month_chg"] < -2
        copper_up   = macro_data["COPPER"]["month_chg"] > 3
        if gold_drop and copper_up:
            signals.append(
                "🚀 <b>خيط خفي:</b> الذهب يهبط + النحاس يرتفع\n"
                "   → المال يتحول من الملاذ الآمن للنمو\n"
                "   → بيئة ممتازة لأسهم التكنولوجيا والصناعة"
            )

    # ─── خيط ٦: VIX هادئ جداً + السوق في قمة = خطر انعكاس ────────────────
    if "VIX" in macro_data and "SPY" in macro_data:
        vix_low  = macro_data["VIX"]["current"] < 13
        spy_high = macro_data["SPY"]["month_chg"] > 8
        if vix_low and spy_high:
            signals.append(
                "⚠️ <b>خيط خفي:</b> VIX منخفض جداً + السوق في قمة\n"
                "   → السوق 'مخدر' والجميع متفائل\n"
                "   → Minervini: 'الخطر الحقيقي يأتي عندما لا يشعر أحد بالخطر'"
            )

    if not signals:
        signals.append("✅ لا توجد خيوط مقلقة — الأسواق تتحرك بشكل منطقي")

    return signals

def send_correlation_report(macro_data: dict):
    """يرسل تقرير الخيوط الخفية"""
    signals = detect_hidden_signals(macro_data)

    msg = (
        f"🔍 <b>الخيوط الخفية — Correlation Monitor</b>\n"
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"{'─'*28}\n\n"
        f"<b>العلاقات بين: DXY | US10Y | VIX | SPX</b>\n\n"
    )

    for signal in signals:
        msg += f"{signal}\n\n"

    msg += (
        f"{'─'*28}\n"
        f"💡 هذه الإشارات تسبق الأخبار بـ 1-3 أيام\n"
        f"المحترفون يقرأونها قبل فتح مراكزهم"
    )

    send_telegram(msg)
    print("[Correlation] تقرير الخيوط الخفية أُرسل ✅")

if __name__ == "__main__":
    print("🧪 اختبار Macro Intelligence...\n")

    macro_data = fetch_macro_data()
    analysis   = analyze_macro_regime(macro_data)

    print(f"\n{'='*55}")
    print(f"  المرحلة: {analysis['phase']}")
    print(f"  النقاط: {analysis['score']:+d}")
    print(f"  القطاعات: {', '.join(analysis['preferred_sectors'])}")
    print(f"{'='*55}\n")

    print("الإشارات:")
    for s in analysis["signals"]:
        print(f"  {s}")

    # اختبار فلتر الشراء
    print("\nاختبار فلتر الشراء:")
    test_stocks = ["NVDA", "XOM", "MSFT", "GLD"]
    for sym in test_stocks:
        allowed, reason = macro_allows_buy(sym, analysis)
        emoji = "✅" if allowed else "❌"
        print(f"  {emoji} {sym}: {reason}")

    save_macro_state(analysis)
    send_macro_report(macro_data, analysis)
    print("\n✅ اكتمل! التقرير وصل على Telegram")

    # تقرير الخيوط الخفية
    print("\n🔍 الخيوط الخفية:")
    hidden = detect_hidden_signals(macro_data)
    for s in hidden:
        print(f"  {s[:80]}")
    send_correlation_report(macro_data)

    print("\n✅ اكتمل! كلا التقريرين وصلا على Telegram")


# Keep running every 1 hour
import time as _time
if __name__ == "__main__":
    while True:
        try:
            macro_data = fetch_macro_data()
            analysis = analyze_macro_regime(macro_data)
            save_macro_state(analysis)
        except Exception as e:
            print(f"Macro error: {e}")
        _time.sleep(3600)
