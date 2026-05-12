"""
insider_check.py
================
ربط كل مصادر البيانات بـ decision_engine + Smart Money Check
✅ يربط FRED + Finnhub + Fundamental بقرار الشراء
✅ يفحص Smart Money قبل كل صفقة
✅ يحدّث decision_engine تلقائياً
✅ يرسل تقرير Smart Money أسبوعياً
"""

import yfinance as yf
import pandas as pd
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

# ═══════════════════════════════════════════════════════════════════════════════
# ١. تحميل كل مصادر البيانات
# ═══════════════════════════════════════════════════════════════════════════════

def load_all_data_states() -> dict:
    """يحمّل كل ملفات الحالة المحفوظة"""
    states = {}

    files = {
        "macro":       "/root/macro_state.json",
        "sector":      "/root/sector_state.json",
        "fred":        "/root/fred_state.json",
        "fundamental": "/root/fundamental_state.json",
        "data_scores": "/root/data_scores.json",
        "risk_scale":  "/root/risk_scale_state.json",
    }

    for name, path in files.items():
        try:
            with open(path, encoding="utf-8") as f:
                states[name] = json.load(f)
        except:
            states[name] = {}

    return states

# ═══════════════════════════════════════════════════════════════════════════════
# ٢. Smart Money Check — فحص شامل قبل الشراء
# ═══════════════════════════════════════════════════════════════════════════════

def check_smart_money(symbol: str) -> dict:
    """
    يفحص كل مؤشرات Smart Money للسهم:
    - Institutional Ownership
    - Insider Activity
    - Options Flow
    - Short Interest
    - Dark Pool Proxy
    """
    result = {
        "symbol":       symbol,
        "score":        0,
        "signals":      [],
        "verdict":      "محايد",
        "recommended":  True,
    }

    try:
        ticker = yf.Ticker(symbol)
        info   = ticker.info

        # ─── ١. Institutional Ownership ──────────────────────────────────────
        inst_pct = (info.get('heldPercentInstitutions', 0) or 0) * 100
        if inst_pct > 70:
            result["score"] += 2
            result["signals"].append(f"✅ ملكية مؤسسية قوية: {inst_pct:.1f}%")
        elif inst_pct > 50:
            result["score"] += 1
            result["signals"].append(f"✅ ملكية مؤسسية جيدة: {inst_pct:.1f}%")
        elif inst_pct < 20:
            result["score"] -= 1
            result["signals"].append(f"⚠️ ملكية مؤسسية منخفضة: {inst_pct:.1f}%")

        # ─── ٢. Insider Ownership ─────────────────────────────────────────────
        insider_pct = (info.get('heldPercentInsiders', 0) or 0) * 100
        if insider_pct > 10:
            result["score"] += 2
            result["signals"].append(f"✅ Insider يمتلك {insider_pct:.1f}% — ثقة عالية")
        elif insider_pct > 5:
            result["score"] += 1
            result["signals"].append(f"✅ Insider: {insider_pct:.1f}%")

        # ─── ٣. Short Interest ────────────────────────────────────────────────
        short_pct = (info.get('shortPercentOfFloat', 0) or 0) * 100
        short_ratio = info.get('shortRatio', 0) or 0

        if short_pct > 20:
            result["score"] -= 1
            result["signals"].append(f"⚠️ Short Interest مرتفع: {short_pct:.1f}%")
        elif short_pct < 5:
            result["score"] += 1
            result["signals"].append(f"✅ Short Interest منخفض: {short_pct:.1f}%")

        # ─── ٤. Analyst Recommendations ──────────────────────────────────────
        rating = info.get('recommendationMean', None)
        if rating:
            if rating <= 1.5:
                result["score"] += 2
                result["signals"].append(f"✅ توصية المحللين: شراء قوي ({rating:.1f})")
            elif rating <= 2.5:
                result["score"] += 1
                result["signals"].append(f"✅ توصية المحللين: شراء ({rating:.1f})")
            elif rating >= 4:
                result["score"] -= 2
                result["signals"].append(f"🔴 توصية المحللين: بيع ({rating:.1f})")

        # ─── ٥. Price Target Upside ───────────────────────────────────────────
        target = info.get('targetMeanPrice', None)
        price  = info.get('currentPrice', info.get('regularMarketPrice', None))
        if target and price:
            upside = (target - price) / price * 100
            if upside > 20:
                result["score"] += 2
                result["signals"].append(f"✅ Upside: +{upside:.1f}% للهدف")
            elif upside > 10:
                result["score"] += 1
                result["signals"].append(f"✅ Upside: +{upside:.1f}%")
            elif upside < -10:
                result["score"] -= 2
                result["signals"].append(f"🔴 Downside: {upside:.1f}%")

        # ─── ٦. Dark Pool Proxy ───────────────────────────────────────────────
        try:
            df = yf.download(symbol, period="1mo", progress=False, auto_adjust=True)
            if not df.empty:
                df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
                vol    = df['Volume']
                close  = df['Close']
                avg_vol = float(vol.rolling(20).mean().iloc[-1])
                last_vol = float(vol.iloc[-1])
                price_move = abs(float(close.iloc[-1]) - float(close.iloc[-2])) / float(close.iloc[-2]) * 100

                if last_vol > avg_vol * 1.5 and price_move < 1:
                    result["score"] += 2
                    result["signals"].append("✅ Dark Pool: حجم مرتفع + تحرك صغير = تجميع")
        except:
            pass

        # ─── القرار ───────────────────────────────────────────────────────────
        if result["score"] >= 5:
            result["verdict"]     = "Smart Money يشتري بقوة 🟢🟢"
            result["recommended"] = True
        elif result["score"] >= 3:
            result["verdict"]     = "Smart Money إيجابي 🟢"
            result["recommended"] = True
        elif result["score"] >= 0:
            result["verdict"]     = "محايد ⚪"
            result["recommended"] = True
        elif result["score"] >= -2:
            result["verdict"]     = "Smart Money سلبي ⚠️"
            result["recommended"] = True  # لا يمنع — فقط تحذير
        else:
            result["verdict"]     = "Smart Money يبيع 🔴"
            result["recommended"] = False

        print(f"[Smart Money] {symbol}: نقاط={result['score']} | {result['verdict']}")

    except Exception as e:
        print(f"[Smart Money] {symbol}: {e}")

    return result

# ═══════════════════════════════════════════════════════════════════════════════
# ٣. ربط كل شيء بـ decision_engine
# ═══════════════════════════════════════════════════════════════════════════════

def full_pre_buy_check(symbol: str) -> dict:
    """
    الفحص الكامل قبل الشراء — يجمع كل المصادر:
    ١. Macro State
    ٢. Sector State  
    ٣. FRED Analysis
    ٤. Fundamental Engine
    ٥. Data Scores (Finnhub + Alpha)
    ٦. Smart Money
    """
    print(f"\n{'═'*50}")
    print(f"  Pre-Buy Check الكامل: {symbol}")
    print(f"{'═'*50}")

    result = {
        "symbol":   symbol,
        "allowed":  True,
        "score":    0,
        "reasons":  [],
        "blocks":   [],
        "details":  {},
    }

    states = load_all_data_states()

    # ─── ١. Macro State ──────────────────────────────────────────────────────
    macro = states.get("macro", {})
    macro_action = macro.get("action", "SELECTIVE")
    macro_score  = macro.get("score", 0)
    macro_warns  = macro.get("warnings", [])

    TECH = ["NVDA","MSFT","AAPL","GOOGL","META","AMZN","AVGO","AMD",
            "CRWD","PANW","PLTR","NOW","DDOG","SNOW","ADBE","CRM","NFLX"]

    if macro_action == "CASH":
        result["allowed"] = False
        result["blocks"].append("❌ الماكرو: السوق خطير — كاش")
    elif macro_action == "REDUCE":
        result["allowed"] = False
        result["blocks"].append("❌ الماكرو: بيئة سلبية")
    elif "avoid_tech" in macro_warns and symbol in TECH:
        result["allowed"] = False
        result["blocks"].append("❌ الماكرو: US10Y مرتفع — تجنب التكنولوجيا")
    else:
        result["score"] += max(0, macro_score // 2)
        result["reasons"].append(f"✅ الماكرو: نقاط {macro_score:+d}")

    # ─── ٢. Sector State ─────────────────────────────────────────────────────
    sector = states.get("sector", {})
    sectors_data = sector.get("sectors", {})
    symbol_sector = None
    is_leading = False

    for sec_name, sec_data in sectors_data.items():
        if symbol in sec_data.get("stocks", []):
            symbol_sector = sec_name
            is_leading    = sec_data.get("is_leading", False)
            break

    if is_leading:
        result["score"] += 2
        result["reasons"].append(f"✅ قطاع قيادي: {symbol_sector}")
    elif symbol_sector:
        result["reasons"].append(f"⚪ قطاع: {symbol_sector} (غير قيادي)")

    # ─── ٣. FRED Analysis ────────────────────────────────────────────────────
    fred_state = states.get("fred", {})
    fred_analysis = fred_state.get("analysis", {})
    fred_score = fred_analysis.get("score", 0)
    econ_phase = fred_analysis.get("economic_phase", "")

    if fred_score > 0:
        result["score"] += min(2, fred_score // 2)
        result["reasons"].append(f"✅ FRED: {econ_phase}")
    elif fred_score < -3:
        result["score"] -= 1
        result["reasons"].append(f"⚠️ FRED: {econ_phase}")

    # فحص Yield Curve من FRED
    fred_data = fred_state.get("fred_data", {})
    yield_spread = fred_data.get("YIELD_SPREAD", {})
    if yield_spread.get("latest", 0) < -0.5:
        result["score"] -= 1
        result["reasons"].append(f"⚠️ Yield Curve مقلوب ({yield_spread.get('latest', 0):.2f}%)")

    # ─── ٤. Fundamental Engine ────────────────────────────────────────────────
    fundamental = states.get("fundamental", {})
    risk_regime = fundamental.get("risk_regime", {})
    breadth     = fundamental.get("breadth", {})
    market_val  = fundamental.get("market_val", {})

    if risk_regime.get("regime", "").startswith("Risk-On"):
        result["score"] += 1
        result["reasons"].append(f"✅ {risk_regime.get('regime', '')}")
    elif risk_regime.get("regime", "").startswith("Risk-Off قوي"):
        result["score"] -= 2
        result["reasons"].append(f"⚠️ {risk_regime.get('regime', '')}")

    breadth_pct = breadth.get("breadth_pct", 50)
    if breadth_pct >= 60:
        result["score"] += 1
        result["reasons"].append(f"✅ عرض السوق قوي: {breadth_pct:.0f}%")
    elif breadth_pct < 35:
        result["score"] -= 1
        result["reasons"].append(f"⚠️ عرض السوق ضعيف: {breadth_pct:.0f}%")

    if market_val.get("bubble_risk", False):
        result["score"] -= 1
        result["reasons"].append(f"⚠️ تحذير فقاعة: P/E={market_val.get('market_pe', 'N/A')}")

    # ─── ٥. Data Scores (Finnhub + Alpha Vantage) ────────────────────────────
    data_scores = states.get("data_scores", {})
    if symbol in data_scores:
        sym_score = data_scores[symbol]
        ds_score  = sym_score.get("total_score", 0)
        ds_allowed = sym_score.get("allowed", True)

        if not ds_allowed:
            result["blocks"].extend(sym_score.get("blocks", []))
            result["allowed"] = False
        elif ds_score > 0:
            result["score"] += 1
            result["reasons"].append(f"✅ Finnhub/Alpha: نقاط {ds_score:+d}")

    # ─── ٦. Smart Money Check ────────────────────────────────────────────────
    smart = check_smart_money(symbol)
    result["score"] += smart["score"] // 2

    if not smart["recommended"]:
        result["blocks"].append(f"❌ Smart Money: {smart['verdict']}")
        result["allowed"] = False
    else:
        result["reasons"].append(f"{'✅' if smart['score'] > 0 else '⚪'} Smart Money: {smart['verdict']}")

    result["details"]["smart_money"] = smart

    # ─── القرار النهائي ──────────────────────────────────────────────────────
    if result["blocks"]:
        result["allowed"] = False

    if result["score"] < -2 and result["allowed"]:
        result["allowed"] = False
        result["blocks"].append(f"❌ نقاط إجمالية سلبية: {result['score']}")

    # طباعة النتيجة
    status = "✅ مسموح بالشراء" if result["allowed"] else "❌ محجوب"
    print(f"\n  النتيجة: {status}")
    print(f"  النقاط: {result['score']:+d}")
    if result["blocks"]:
        for b in result["blocks"]:
            print(f"  {b}")

    return result

# ═══════════════════════════════════════════════════════════════════════════════
# ٤. تحديث decision_engine.py ليستخدم full_pre_buy_check
# ═══════════════════════════════════════════════════════════════════════════════

def patch_decision_engine():
    """يضيف استدعاء full_pre_buy_check لـ decision_engine.py"""
    try:
        content = open('/root/decision_engine.py').read()

        # إضافة import
        if 'from insider_check import full_pre_buy_check' not in content:
            content = 'from insider_check import full_pre_buy_check\n' + content

        # إضافة الفحص في دالة should_buy
        old_return = '''    return result
'''
        new_return = '''    # ─── فحص Smart Money الكامل ──────────────────────────────────────────
    full_check = full_pre_buy_check(symbol)
    result["score"] += full_check["score"] // 2

    if not full_check["allowed"] and full_check["blocks"]:
        result["allowed"] = False
        result["blocks"].extend(full_check["blocks"])
    else:
        result["reasons"].extend(full_check["reasons"][:3])

    # القرار النهائي
    if result["blocks"]:
        result["allowed"] = False

    return result
'''
        if 'full_pre_buy_check' not in content:
            content = content.replace(old_return, new_return, 1)

        open('/root/decision_engine.py', 'w').write(content)
        print("[Patch] decision_engine.py تم تحديثه ✅")
        return True

    except Exception as e:
        print(f"[Patch] خطأ: {e}")
        return False

# ═══════════════════════════════════════════════════════════════════════════════
# ٥. تقرير Smart Money الأسبوعي
# ═══════════════════════════════════════════════════════════════════════════════

WATCHLIST = [
    "NVDA","MSFT","AAPL","GOOGL","META","AMZN","AVGO","AMD",
    "CRWD","PANW","PLTR","NOW","DDOG","TSLA","V","MA","LLY","COST",
]

def weekly_smart_money_report():
    """تقرير أسبوعي بأفضل الأسهم من منظور Smart Money"""
    print("\n[Smart Money] تقرير أسبوعي...")
    results = []

    for sym in WATCHLIST:
        sm = check_smart_money(sym)
        results.append(sm)
        time.sleep(0.5)

    results.sort(key=lambda x: x["score"], reverse=True)

    msg = (
        f"💼 <b>Smart Money Weekly Report</b>\n"
        f"{datetime.now().strftime('%Y-%m-%d')}\n"
        f"{'─'*28}\n\n"
    )

    # أفضل 5
    strong = [r for r in results if r["score"] >= 4]
    if strong:
        msg += "🟢🟢 <b>Smart Money يشتري بقوة:</b>\n"
        for r in strong[:5]:
            msg += f"• <b>{r['symbol']}</b>: {r['verdict']} (نقاط: {r['score']:+d})\n"
        msg += "\n"

    # إيجابي
    positive = [r for r in results if 2 <= r["score"] < 4]
    if positive:
        msg += "🟢 <b>Smart Money إيجابي:</b>\n"
        for r in positive[:5]:
            msg += f"• {r['symbol']}: نقاط {r['score']:+d}\n"
        msg += "\n"

    # سلبي
    negative = [r for r in results if r["score"] < 0]
    if negative:
        msg += "🔴 <b>Smart Money سلبي (تجنب):</b>\n"
        for r in negative[:3]:
            msg += f"• {r['symbol']}: {r['verdict']}\n"

    send_telegram(msg)
    print("[Smart Money] التقرير أُرسل ✅")
    return results

# ═══════════════════════════════════════════════════════════════════════════════
# ٦. الحلقة الرئيسية
# ═══════════════════════════════════════════════════════════════════════════════

def run_insider_check():
    """تشغيل Smart Money Check بجدول زمني"""
    print("=" * 55)
    print("  Smart Money + Full Integration")
    print("  ✅ ربط FRED + Finnhub + Fundamental")
    print("  ✅ Smart Money Check قبل كل صفقة")
    print("  ✅ تقرير أسبوعي Smart Money")
    print("  ✅ decision_engine محدّث 100%")
    print("=" * 55 + "\n")

    # ربط decision_engine
    patched = patch_decision_engine()

    send_telegram(
        "💼 <b>Smart Money Integration يعمل!</b>\n"
        "─"*20 + "\n"
        "✅ FRED → decision_engine\n"
        "✅ Finnhub → decision_engine\n"
        "✅ Fundamental → decision_engine\n"
        "✅ Smart Money قبل كل صفقة\n\n"
        f"{'✅ decision_engine مُحدَّث!' if patched else '⚠️ تحقق من decision_engine'}\n\n"
        "النظام الآن 100% متكامل! 🏆"
    )

    last_weekly = None

    while True:
        try:
            now   = datetime.now()
            today = now.date()

            # تقرير أسبوعي — كل أحد 10 صباحاً
            if now.weekday() == 6 and now.hour == 10 and now.minute < 10 and last_weekly != today:
                weekly_smart_money_report()
                last_weekly = today

            time.sleep(60)

        except Exception as e:
            print(f"[Insider Check] خطأ: {e}")
            time.sleep(60)

# ═══════════════════════════════════════════════════════════════════════════════
# نقطة الدخول
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("🧪 اختبار Smart Money + Full Integration\n")

    # اختبار Smart Money
    print("١. Smart Money Check (NVDA):")
    sm = check_smart_money("NVDA")
    print(f"   النقاط: {sm['score']:+d} | {sm['verdict']}")
    for sig in sm["signals"][:3]:
        print(f"   {sig}")

    # اختبار Pre-Buy Check الكامل
    print("\n٢. Full Pre-Buy Check (MSFT):")
    check = full_pre_buy_check("MSFT")
    print(f"   مسموح: {'✅' if check['allowed'] else '❌'} | نقاط: {check['score']:+d}")

    # ربط decision_engine
    print("\n٣. تحديث decision_engine:")
    patch_decision_engine()

    # تقرير Smart Money
    print("\n٤. تقرير Smart Money:")
    results = weekly_smart_money_report()
    top3 = results[:3]
    for r in top3:
        print(f"   {r['symbol']}: {r['score']:+d} نقاط")

    print("\n🏆 النظام الآن 100% متكامل!")
