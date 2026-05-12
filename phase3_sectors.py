"""
phase3_sectors.py
=================
المرحلة الثالثة — Sector Rotation Intelligence
✅ يحدد القطاعات القيادية تلقائياً
✅ يعطي أولوية للأسهم في القطاعات الأقوى
✅ يتجنب القطاعات الضعيفة
✅ تقرير أسبوعي بأقوى القطاعات
✅ يعمل مع auto_monitor.py بدون تعديله
"""

import yfinance as yf
import pandas as pd
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
# تعريف القطاعات وأسهمها
# ═══════════════════════════════════════════════════════════════════════════════

SECTORS = {
    "التكنولوجيا": {
        "etf":    "XLK",
        "stocks": ["NVDA","MSFT","AAPL","AVGO","AMD","ORCL","TSM","QCOM"],
        "weight": 0
    },
    "السيبراني": {
        "etf":    "HACK",
        "stocks": ["CRWD","PANW","ZS","FTNT","NOW","DDOG","NET","PLTR"],
        "weight": 0
    },
    "أشباه الموصلات": {
        "etf":    "SMH",
        "stocks": ["NVDA","AVGO","AMD","TSM","ARM","ANET","MRVL","LRCX"],
        "weight": 0
    },
    "الصحة والأدوية": {
        "etf":    "XLV",
        "stocks": ["LLY","UNH","ISRG","DXCM","ABBV","REGN","VRTX"],
        "weight": 0
    },
    "المالية": {
        "etf":    "XLF",
        "stocks": ["JPM","GS","V","MA","PYPL"],
        "weight": 0
    },
    "الاستهلاكي": {
        "etf":    "XLY",
        "stocks": ["TSLA","AMZN","COST","WMT","NKE","LULU"],
        "weight": 0
    },
    "الطاقة": {
        "etf":    "XLE",
        "stocks": ["XOM","CVX","OXY"],
        "weight": 0
    },
    "الصناعي": {
        "etf":    "XLI",
        "stocks": ["CAT","HON","GE","LMT","NOC"],
        "weight": 0
    },
    "البرمجيات والسحابة": {
        "etf":    "IGV",
        "stocks": ["ADBE","CRM","INTU","WDAY","NFLX","TTD","HUBS"],
        "weight": 0
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
# حساب أداء القطاعات
# ═══════════════════════════════════════════════════════════════════════════════

def calc_sector_performance() -> dict:
    """
    يحسب أداء كل قطاع مقارنة بـ SPY
    باستخدام ETF الخاص بكل قطاع
    """
    print("\n[Sectors] حساب أداء القطاعات...")

    # تحميل SPY كمرجع
    spy = yf.download("SPY", period="3mo", progress=False, auto_adjust=True)
    spy.columns = [c[0] if isinstance(c, tuple) else c for c in spy.columns]
    spy_ret_1m  = (float(spy['Close'].iloc[-1]) - float(spy['Close'].iloc[-21])) / float(spy['Close'].iloc[-21])
    spy_ret_3m  = (float(spy['Close'].iloc[-1]) - float(spy['Close'].iloc[0]))   / float(spy['Close'].iloc[0])

    results = {}

    for sector_name, sector_data in SECTORS.items():
        etf = sector_data["etf"]
        try:
            df = yf.download(etf, period="3mo", progress=False, auto_adjust=True)
            if df.empty or len(df) < 21:
                continue
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

            close = df['Close']
            ret_1m = (float(close.iloc[-1]) - float(close.iloc[-21])) / float(close.iloc[-21])
            ret_3m = (float(close.iloc[-1]) - float(close.iloc[0]))   / float(close.iloc[0])

            # RS مقارنة بـ SPY
            rs_1m = ret_1m - spy_ret_1m
            rs_3m = ret_3m - spy_ret_3m

            # نقاط مركبة (60% شهر + 40% ثلاثة أشهر)
            score = (rs_1m * 0.60) + (rs_3m * 0.40)

            results[sector_name] = {
                "etf":     etf,
                "ret_1m":  round(ret_1m * 100, 1),
                "ret_3m":  round(ret_3m * 100, 1),
                "rs_1m":   round(rs_1m * 100, 1),
                "rs_3m":   round(rs_3m * 100, 1),
                "score":   round(score * 100, 2),
                "stocks":  sector_data["stocks"],
                "leading": score > 0,
            }
            print(f"  {sector_name:20} | 1M: {ret_1m*100:+.1f}% | RS: {rs_1m*100:+.1f}%")

        except Exception as e:
            print(f"  ❌ {sector_name}: {e}")

    return results

# ═══════════════════════════════════════════════════════════════════════════════
# تحديد القطاعات القيادية
# ═══════════════════════════════════════════════════════════════════════════════

def get_leading_sectors(results: dict, top_n: int = 4) -> dict:
    """
    يرجع أقوى N قطاعات
    """
    sorted_sectors = sorted(
        results.items(),
        key=lambda x: x[1]["score"],
        reverse=True
    )

    leading = {}
    for i, (name, data) in enumerate(sorted_sectors):
        data["rank"] = i + 1
        data["is_leading"] = i < top_n and data["leading"]
        leading[name] = data

    return leading

def get_priority_watchlist(sector_results: dict) -> list:
    """
    يبني قائمة مراقبة مرتبة حسب قوة القطاع
    الأسهم في القطاعات القيادية تأتي أولاً
    """
    priority_stocks = []
    secondary_stocks = []

    for name, data in sector_results.items():
        if data.get("is_leading"):
            priority_stocks.extend(data["stocks"])
        else:
            secondary_stocks.extend(data["stocks"])

    # إزالة التكرار مع الحفاظ على الترتيب
    seen = set()
    final_list = []
    for sym in priority_stocks + secondary_stocks:
        if sym not in seen:
            seen.add(sym)
            final_list.append(sym)

    return final_list

# ═══════════════════════════════════════════════════════════════════════════════
# تقرير Telegram
# ═══════════════════════════════════════════════════════════════════════════════

def send_sector_report(sector_results: dict):
    """يرسل تقرير القطاعات على Telegram"""

    sorted_sectors = sorted(
        sector_results.items(),
        key=lambda x: x[1]["score"],
        reverse=True
    )

    msg = (
        f"🏭 <b>Sector Rotation Report</b>\n"
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"{'─'*28}\n\n"
    )

    # القيادية
    leading = [(n, d) for n, d in sorted_sectors if d.get("is_leading")]
    if leading:
        msg += "🚀 <b>قطاعات قيادية (أولوية الشراء)</b>\n"
        for name, data in leading:
            msg += (
                f"📈 <b>{name}</b> ({data['etf']})\n"
                f"   شهر: {data['ret_1m']:+.1f}% | RS: {data['rs_1m']:+.1f}%\n"
            )
        msg += "\n"

    # المتوسطة
    neutral = [(n, d) for n, d in sorted_sectors
               if not d.get("is_leading") and d["score"] > -2]
    if neutral:
        msg += "⚖️ <b>قطاعات محايدة</b>\n"
        for name, data in neutral[:3]:
            msg += f"• {name}: {data['ret_1m']:+.1f}%\n"
        msg += "\n"

    # الضعيفة
    weak = [(n, d) for n, d in sorted_sectors if d["score"] <= -2]
    if weak:
        msg += "⚠️ <b>قطاعات ضعيفة (تجنب)</b>\n"
        for name, data in weak:
            msg += f"❌ {name}: {data['ret_1m']:+.1f}%\n"

    send_telegram(msg)
    print("[Sectors] تم إرسال التقرير على Telegram ✅")

# ═══════════════════════════════════════════════════════════════════════════════
# حفظ القطاعات القيادية
# ═══════════════════════════════════════════════════════════════════════════════

def save_sector_state(sector_results: dict):
    """يحفظ حالة القطاعات في ملف JSON"""
    state = {
        "updated": str(datetime.now()),
        "sectors": {
            name: {
                "score":      data["score"],
                "is_leading": data.get("is_leading", False),
                "ret_1m":     data["ret_1m"],
                "rs_1m":      data["rs_1m"],
                "stocks":     data["stocks"],
            }
            for name, data in sector_results.items()
        }
    }
    with open("/root/sector_state.json", "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    print("[Sectors] حالة القطاعات محفوظة ✅")

def load_leading_stocks() -> list:
    """يقرأ الأسهم القيادية من آخر فحص"""
    try:
        with open("/root/sector_state.json", encoding="utf-8") as f:
            state = json.load(f)
        leading = []
        for name, data in state["sectors"].items():
            if data["is_leading"]:
                leading.extend(data["stocks"])
        # إزالة التكرار
        return list(dict.fromkeys(leading))
    except:
        return []

# ═══════════════════════════════════════════════════════════════════════════════
# التشغيل الرئيسي
# ═══════════════════════════════════════════════════════════════════════════════

def run_sector_rotation():
    """يشغّل Sector Rotation كل أسبوع"""
    print("=" * 55)
    print("  Phase 3 — Sector Rotation Intelligence")
    print("=" * 55 + "\n")

    send_telegram(
        "🏭 <b>المرحلة الثالثة تعمل!</b>\n"
        "─"*20 + "\n"
        "✅ Sector Rotation Intelligence\n"
        "✅ تحديد القطاعات القيادية\n"
        "✅ تقرير أسبوعي بأقوى القطاعات\n\n"
        "النظام يعمل بذكاء أعلى! 🧠"
    )

    last_check = None

    while True:
        try:
            now = datetime.now()

            # فحص كل إثنين الساعة 7 صباحاً (قبل Weekly RS Scan)
            if (now.weekday() == 0 and now.hour == 7 and now.minute < 5
                    and last_check != now.date()):

                print(f"\n[Sectors] {now.strftime('%Y-%m-%d %H:%M')} — بدء التحليل الأسبوعي")
                results      = calc_sector_performance()
                leading      = get_leading_sectors(results, top_n=4)
                priority     = get_priority_watchlist(leading)

                save_sector_state(leading)
                send_sector_report(leading)

                leading_sectors = [n for n, d in leading.items() if d.get("is_leading")]
                print(f"\n[Sectors] القطاعات القيادية: {leading_sectors}")
                print(f"[Sectors] أسهم الأولوية: {priority[:10]}...")

                last_check = now.date()

            time.sleep(60)

        except Exception as e:
            print(f"[Sectors] خطأ: {e}")
            time.sleep(60)

# ═══════════════════════════════════════════════════════════════════════════════
# نقطة الدخول
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("🧪 اختبار Sector Rotation...\n")

    results  = calc_sector_performance()
    leading  = get_leading_sectors(results, top_n=4)
    priority = get_priority_watchlist(leading)

    print("\n" + "="*55)
    print("  📊 نتائج Sector Rotation")
    print("="*55)

    sorted_r = sorted(leading.items(), key=lambda x: x[1]["score"], reverse=True)
    for name, data in sorted_r:
        rank   = data["rank"]
        status = "🚀 قيادي" if data.get("is_leading") else "⚖️ محايد" if data["score"] > -2 else "❌ ضعيف"
        print(f"  #{rank} {name:20} | {data['ret_1m']:+.1f}% | RS: {data['rs_1m']:+.1f}% | {status}")

    print(f"\n  أسهم الأولوية ({len(priority)}):")
    print(f"  {priority[:12]}")

    save_sector_state(leading)
    send_sector_report(leading)

    print("\n✅ اكتمل! التقرير وصل على Telegram")
