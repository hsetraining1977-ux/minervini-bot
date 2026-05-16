"""
rs_rating.py
============
RS Rating حقيقي مقارنة بـ S&P 500
✅ يحسب أداء السهم مقارنة بالسوق آخر 12 شهر
✅ يعطي نقاط 1-99 كما في IBD
✅ فلتر RS فوق 80 فقط للدخول
✅ يضاف مباشرة لـ auto_monitor.py
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# ─── حساب RS Rating ──────────────────────────────────────────────────────────

def calc_rs_raw(symbol: str, spy_returns: pd.Series) -> float:
    """
    يحسب الأداء النسبي للسهم مقارنة بـ SPY
    المعادلة الأصلية لـ IBD:
    RS = (أداء 3 أشهر × 40%) + (أداء 3 أشهر قبلها × 20%) +
         (أداء 3 أشهر قبلها × 20%) + (أداء 3 أشهر قبلها × 20%)
    """
    try:
        df = yf.download(symbol, period="1y", progress=False, auto_adjust=True)
        if df.empty or len(df) < 60:
            return 0.0

        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        close = df['Close'].dropna()

        if len(close) < 60:
            return 0.0

        # أداء كل ربع
        def pct(days):
            if len(close) < days:
                return 0.0
            return (float(close.iloc[-1]) - float(close.iloc[-days])) / float(close.iloc[-days])

        q1 = pct(63)   # ربع الأول  (3 أشهر)
        q2 = pct(126)  # ربع الثاني (6 أشهر)
        q3 = pct(189)  # ربع الثالث (9 أشهر)
        q4 = pct(252)  # ربع الرابع (12 شهر)

        # المعادلة الموزونة
        rs_raw = (q1 * 0.40) + (q2 * 0.20) + (q3 * 0.20) + (q4 * 0.20)
        return rs_raw

    except Exception as e:
        return 0.0

def calc_rs_ratings(watchlist: list) -> dict:
    """
    يحسب RS Rating لكل الأسهم ويرتبها 1-99
    """
    print(f"[RS] حساب RS Rating لـ {len(watchlist)} سهم...")

    # تحميل SPY كمرجع
    spy_df = yf.download("SPY", period="1y", progress=False, auto_adjust=True)
    spy_df.columns = [c[0] if isinstance(c, tuple) else c for c in spy_df.columns]
    spy_close = spy_df['Close'].dropna()

    def spy_pct(days):
        if len(spy_close) < days:
            return 0.0
        return (float(spy_close.iloc[-1]) - float(spy_close.iloc[-days])) / float(spy_close.iloc[-days])

    spy_raw = (spy_pct(63)*0.40 + spy_pct(126)*0.20 +
               spy_pct(189)*0.20 + spy_pct(252)*0.20)

    # حساب RS الخام لكل سهم
    raw_scores = {}
    for sym in watchlist:
        raw_scores[sym] = calc_rs_raw(sym, spy_close)

    if not raw_scores:
        return {}

    # تحويل لنقاط 1-99
    values = list(raw_scores.values())
    min_v  = min(values)
    max_v  = max(values)
    rng    = max_v - min_v if max_v != min_v else 1

    ratings = {}
    for sym, raw in raw_scores.items():
        score = int(((raw - min_v) / rng) * 98) + 1
        score = max(1, min(99, score))

        # تحقق إن كان السهم يتفوق على SPY
        outperforms = raw > spy_raw

        ratings[sym] = {
            "rs_rating":   score,
            "rs_raw":      round(raw * 100, 1),
            "spy_raw":     round(spy_raw * 100, 1),
            "outperforms": outperforms,
        }

    print(f"[RS] اكتمل — SPY أداء: {spy_raw*100:.1f}%\n")
    return ratings

def filter_by_rs(watchlist: list, min_rs: int = 80) -> list:
    """
    يرجع قائمة الأسهم التي RS Rating بتاعها فوق min_rs
    """
    ratings = calc_rs_ratings(watchlist)
    qualified = []

    for sym, data in ratings.items():
        if data["rs_rating"] >= min_rs:
            qualified.append({
                "symbol":    sym,
                "rs_rating": data["rs_rating"],
                "rs_pct":    data["rs_raw"],
                "spy_pct":   data["spy_raw"],
            })

    # ترتيب من الأعلى للأدنى
    qualified.sort(key=lambda x: x["rs_rating"], reverse=True)

    print(f"[RS] أسهم فوق RS {min_rs}: {len(qualified)} من {len(watchlist)}")
    for s in qualified[:10]:
        print(f"  {s['symbol']:6} | RS: {s['rs_rating']:2} | أداء: {s['rs_pct']:+.1f}% | SPY: {s['spy_pct']:+.1f}%")

    return [s["symbol"] for s in qualified]

# ─── Weekly RS Scanner ────────────────────────────────────────────────────────

def weekly_rs_scan(watchlist: list, telegram_token: str, chat_id: str):
    """
    فحص أسبوعي كل إثنين — يرسل أفضل 10 أسهم على Telegram
    """
    import requests

    ratings = calc_rs_ratings(watchlist)
    sorted_stocks = sorted(ratings.items(),
                          key=lambda x: x[1]["rs_rating"],
                          reverse=True)

    msg = "📊 <b>Weekly RS Scan — أفضل الأسهم</b>\n"
    msg += f"{'─'*25}\n"
    msg += f"تاريخ: {datetime.now().strftime('%Y-%m-%d')}\n\n"

    leaders  = []
    rs_80    = []
    rs_below = []

    for sym, data in sorted_stocks:
        if data["rs_rating"] >= 90:
            leaders.append((sym, data))
        elif data["rs_rating"] >= 80:
            rs_80.append((sym, data))
        else:
            rs_below.append((sym, data))

    if leaders:
        msg += "🏆 <b>قادة السوق (RS 90+)</b>\n"
        for sym, d in leaders[:5]:
            emoji = "🚀" if d["outperforms"] else "📈"
            msg += f"{emoji} {sym}: RS={d['rs_rating']} | {d['rs_raw']:+.1f}%\n"
        msg += "\n"

    if rs_80:
        msg += "✅ <b>أسهم قوية (RS 80-89)</b>\n"
        for sym, d in rs_80[:5]:
            msg += f"• {sym}: RS={d['rs_rating']} | {d['rs_pct']:+.1f}%\n".replace(
                "rs_pct", "rs_raw")
        msg += "\n"

    msg += f"{'─'*25}\n"
    msg += f"إجمالي فوق RS 80: {len(leaders)+len(rs_80)}\n"
    msg += f"SPY أداء سنوي: {list(ratings.values())[0]['spy_raw']:+.1f}%"

    try:
        url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
        requests.post(url, json={
            "chat_id":    chat_id,
            "text":       msg,
            "parse_mode": "HTML"
        }, timeout=10)
        print("[RS] تم إرسال Weekly Scan على Telegram")
    except Exception as e:
        print(f"[RS] خطأ Telegram: {e}")

    return ratings

# ─── اختبار مباشر ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    WATCHLIST = [
        "NVDA","MSFT","AAPL","GOOGL","META","AMZN","AVGO","AMD",
        "CRWD","PANW","PLTR","NOW","DDOG","SNOW",
        "ADBE","CRM","INTU","NFLX","TTD",
        "TSLA","UBER","V","MA","JPM",
        "LLY","UNH","COST","WMT","NKE",
        "CAT","HON","GE","SMH","QQQ",
    ]

    print("=" * 50)
    print("  RS Rating Scanner — Minervini Style")
    print("=" * 50 + "\n")

    # أسهم فوق RS 80
    qualified = filter_by_rs(WATCHLIST, min_rs=80)

    print(f"\n✅ قائمة المراقبة المفلترة ({len(qualified)} سهم):")
    print(qualified)
