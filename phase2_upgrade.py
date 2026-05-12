"""
phase2_upgrade.py
=================
المرحلة الثانية — ثلاث تحسينات معاً:
✅ Annual EPS Filter    — نمو الأرباح السنوي 25%+
✅ Add Method           — زيادة المراكز الرابحة تلقائياً
✅ Weekly RS Scan       — تقرير أسبوعي كل إثنين
"""

import yfinance as yf
import pandas as pd
import requests
import time
import threading
from datetime import datetime
from config import ALPACA_KEY, ALPACA_SECRET, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
import alpaca_trade_api as tradeapi

trading_client = tradeapi.REST(
    ALPACA_KEY, ALPACA_SECRET,
    base_url='https://paper-api.alpaca.markets'
)

# ─── الإعدادات ────────────────────────────────────────────────────────────────
ADD_METHOD_TRIGGER   = 0.10   # زد المركز عند ربح 10%
ADD_METHOD_SIZE      = 0.50   # زد 50% من الحجم الأصلي
MIN_ANNUAL_EPS       = 0.25   # نمو سنوي 25%+
MIN_ANNUAL_REV       = 0.15   # نمو إيرادات سنوي 15%+
RS_MIN_RATING        = 80     # RS فوق 80

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
# ١. Annual EPS Filter
# ═══════════════════════════════════════════════════════════════════════════════

def check_annual_eps(symbol: str) -> dict:
    """
    يفحص نمو الأرباح السنوي — O'Neil + Minervini
    الشرط: نمو EPS سنوي 25%+ ونمو إيرادات 15%+
    """
    result = {
        "passed": False,
        "annual_eps_growth": None,
        "annual_rev_growth": None,
        "reason": ""
    }

    try:
        ticker = yf.Ticker(symbol)
        financials = ticker.financials        # P&L سنوي
        info = ticker.info

        if financials is None or financials.empty:
            result["reason"] = "no_financials"
            return result

        # EPS السنوي
        eps_col = None
        for col in ["Basic EPS", "Diluted EPS", "EPS"]:
            if col in financials.index:
                eps_col = col
                break

        if eps_col and financials.shape[1] >= 2:
            eps_current = float(financials.loc[eps_col].iloc[0])
            eps_prev    = float(financials.loc[eps_col].iloc[1])
            if eps_prev != 0 and eps_prev > 0:
                eps_growth = (eps_current - eps_prev) / abs(eps_prev)
                result["annual_eps_growth"] = round(eps_growth * 100, 1)
            else:
                eps_growth = 0
                result["annual_eps_growth"] = 0
        else:
            # نستخدم info كبديل
            eps_growth = info.get("earningsGrowth", 0) or 0
            result["annual_eps_growth"] = round(eps_growth * 100, 1)

        # نمو الإيرادات السنوي
        rev_col = None
        for col in ["Total Revenue", "Revenue"]:
            if col in financials.index:
                rev_col = col
                break

        if rev_col and financials.shape[1] >= 2:
            rev_current = float(financials.loc[rev_col].iloc[0])
            rev_prev    = float(financials.loc[rev_col].iloc[1])
            if rev_prev != 0:
                rev_growth = (rev_current - rev_prev) / abs(rev_prev)
                result["annual_rev_growth"] = round(rev_growth * 100, 1)
            else:
                rev_growth = 0
        else:
            rev_growth = info.get("revenueGrowth", 0) or 0
            result["annual_rev_growth"] = round(rev_growth * 100, 1)

        # الفلتر
        eps_ok = eps_growth >= MIN_ANNUAL_EPS
        rev_ok = rev_growth >= MIN_ANNUAL_REV

        if eps_ok and rev_ok:
            result["passed"] = True
            result["reason"] = "passed"
        elif not eps_ok:
            result["reason"] = f"eps_low_{result['annual_eps_growth']}%"
        else:
            result["reason"] = f"rev_low_{result['annual_rev_growth']}%"

    except Exception as e:
        result["reason"] = f"error_{str(e)[:30]}"

    return result

def scan_annual_eps(watchlist: list) -> list:
    """
    يفلتر القائمة بناءً على Annual EPS
    يرجع الأسهم التي تجتاز الفلتر
    """
    print(f"\n[EPS] فحص Annual EPS لـ {len(watchlist)} سهم...")
    qualified = []

    for sym in watchlist:
        result = check_annual_eps(sym)
        if result["passed"]:
            qualified.append(sym)
            print(f"  ✅ {sym:6} | EPS: {result['annual_eps_growth']:+.0f}% | Rev: {result['annual_rev_growth']:+.0f}%")
        else:
            print(f"  ❌ {sym:6} | {result['reason']}")

    print(f"\n[EPS] اجتاز الفلتر: {len(qualified)} من {len(watchlist)}\n")
    return qualified

# ═══════════════════════════════════════════════════════════════════════════════
# ٢. Add Method — زيادة المراكز الرابحة
# ═══════════════════════════════════════════════════════════════════════════════

# تتبع المراكز التي تمت زيادتها
added_positions = set()

def check_add_method():
    """
    Minervini Add Method:
    - عند ربح 10%+ → أضف 50% من الحجم الأصلي
    - مرة واحدة فقط لكل صفقة
    - فقط إذا السهم فوق MA50
    """
    try:
        positions = trading_client.list_positions()
        account   = trading_client.get_account()
        cash      = float(account.cash)

        for pos in positions:
            sym      = pos.symbol
            pnl_pct  = float(pos.unrealized_plpc)
            qty      = int(float(pos.qty))
            price    = float(pos.current_price)
            entry    = float(pos.avg_entry_price)

            # تجاهل Crypto والمراكز التي تمت زيادتها
            if "USD" in sym or sym in added_positions:
                continue

            # شرط الربح 10%+
            if pnl_pct < ADD_METHOD_TRIGGER:
                continue

            # تحقق من MA50
            try:
                df = yf.download(sym, period="3mo", progress=False, auto_adjust=True)
                df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
                ma50 = float(df['Close'].rolling(50).mean().iloc[-1])
                if price < ma50:
                    continue
            except:
                continue

            # احسب الكمية الإضافية
            add_qty   = max(1, int(qty * ADD_METHOD_SIZE))
            add_cost  = add_qty * price

            if add_cost > cash * 0.10:  # لا تتجاوز 10% من النقد
                add_qty = max(1, int(cash * 0.10 / price))

            if add_qty < 1 or add_cost > cash:
                continue

            # نفذ الإضافة
            try:
                trading_client.submit_order(
                    symbol=sym,
                    qty=add_qty,
                    side="buy",
                    type="market",
                    time_in_force="day"
                )
                added_positions.add(sym)

                msg = (
                    f"➕ <b>Add Method — {sym}</b>\n"
                    f"{'─'*20}\n"
                    f"الربح الحالي: {pnl_pct*100:+.1f}%\n"
                    f"أضفنا: {add_qty} سهم\n"
                    f"السعر: ${price:.2f}\n"
                    f"التكلفة: ${add_cost:,.0f}\n"
                    f"السهم فوق MA50 ✅"
                )
                send_telegram(msg)
                print(f"[Add] {sym}: أضفنا {add_qty} سهم عند ربح {pnl_pct*100:.1f}%")

            except Exception as e:
                print(f"[Add] خطأ في {sym}: {e}")

    except Exception as e:
        print(f"[Add Method] خطأ: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# ٣. Weekly RS Scan — تقرير أسبوعي
# ═══════════════════════════════════════════════════════════════════════════════

EXTENDED_WATCHLIST = [
    "NVDA","MSFT","AAPL","GOOGL","META","AMZN","AVGO","AMD","ORCL","TSM",
    "CRWD","PANW","ZS","FTNT","NOW","DDOG","SNOW","PLTR","NET","MDB",
    "ADBE","CRM","INTU","WDAY","NFLX","TTD","HUBS","BILL",
    "ARM","ANET","MRVL","LRCX","KLAC","AMAT",
    "TSLA","UBER","SHOP","ABNB","DASH","CELH","ENPH",
    "LLY","UNH","ISRG","DXCM","ABBV","REGN","VRTX",
    "V","MA","JPM","GS","PYPL",
    "COST","WMT","LULU","NKE","DECK","ONON",
    "CAT","HON","GE","LMT","XOM","CVX",
    "SMH","QQQ","SOXX","IBB",
]

def calc_rs_score(symbol: str, spy_close: pd.Series) -> float:
    """يحسب RS Score مقارنة بـ SPY"""
    try:
        df = yf.download(symbol, period="1y", progress=False, auto_adjust=True)
        if df.empty or len(df) < 60:
            return 0.0
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        close = df['Close'].dropna()

        def pct(days):
            if len(close) < days:
                return 0.0
            return (float(close.iloc[-1]) - float(close.iloc[-days])) / float(close.iloc[-days])

        return (pct(63)*0.40 + pct(126)*0.20 + pct(189)*0.20 + pct(252)*0.20)
    except:
        return 0.0

def weekly_rs_scan():
    """
    فحص أسبوعي شامل كل إثنين:
    - RS Rating لكل الأسهم
    - Annual EPS Filter
    - يرسل أفضل 10 على Telegram
    """
    print("\n[Weekly] بدء الفحص الأسبوعي...")

    # تحميل SPY
    spy_df = yf.download("SPY", period="1y", progress=False, auto_adjust=True)
    spy_df.columns = [c[0] if isinstance(c, tuple) else c for c in spy_df.columns]
    spy_close = spy_df['Close'].dropna()

    def spy_pct(days):
        if len(spy_close) < days: return 0.0
        return (float(spy_close.iloc[-1]) - float(spy_close.iloc[-days])) / float(spy_close.iloc[-days])

    spy_raw = spy_pct(63)*0.40 + spy_pct(126)*0.20 + spy_pct(189)*0.20 + spy_pct(252)*0.20

    # حساب RS لكل سهم
    scores = {}
    for sym in EXTENDED_WATCHLIST:
        scores[sym] = calc_rs_score(sym, spy_close)

    # تحويل لنقاط 1-99
    values = list(scores.values())
    min_v, max_v = min(values), max(values)
    rng = max_v - min_v if max_v != min_v else 1

    ratings = {}
    for sym, raw in scores.items():
        rating = int(((raw - min_v) / rng) * 98) + 1
        ratings[sym] = {
            "rs":  max(1, min(99, rating)),
            "pct": round(raw * 100, 1),
            "beats_spy": raw > spy_raw
        }

    # ترتيب الأفضل
    sorted_stocks = sorted(ratings.items(), key=lambda x: x[1]["rs"], reverse=True)

    # فحص EPS للأفضل 20
    top20 = [s[0] for s in sorted_stocks[:20]]
    eps_qualified = set(scan_annual_eps(top20))

    # بناء التقرير
    msg = (
        f"📊 <b>Weekly Scan — {datetime.now().strftime('%Y-%m-%d')}</b>\n"
        f"{'─'*28}\n"
        f"SPY أداء سنوي: {spy_raw*100:+.1f}%\n\n"
    )

    # القادة — RS 90+ وEPS ممتاز
    leaders = [(s, d) for s, d in sorted_stocks if d["rs"] >= 90 and s in eps_qualified]
    if leaders:
        msg += "🏆 <b>قادة السوق (RS 90+ + EPS ✅)</b>\n"
        for sym, d in leaders[:5]:
            msg += f"🚀 {sym}: RS={d['rs']} | {d['pct']:+.1f}%\n"
        msg += "\n"

    # أقوياء — RS 80+
    strong = [(s, d) for s, d in sorted_stocks if 80 <= d["rs"] < 90]
    if strong:
        msg += "💪 <b>أسهم قوية (RS 80-89)</b>\n"
        for sym, d in strong[:5]:
            eps_mark = "✅" if sym in eps_qualified else ""
            msg += f"• {sym}: RS={d['rs']} | {d['pct']:+.1f}% {eps_mark}\n"
        msg += "\n"

    msg += f"{'─'*28}\n"
    msg += f"فوق RS 80: {len([s for s,d in ratings.items() if d['rs']>=80])}\n"
    msg += f"اجتاز EPS: {len(eps_qualified)} من {len(top20)}\n"
    msg += f"إجمالي الأسهم: {len(EXTENDED_WATCHLIST)}"

    send_telegram(msg)
    print(f"[Weekly] اكتمل — تم إرسال التقرير على Telegram ✅")

    return ratings

# ═══════════════════════════════════════════════════════════════════════════════
# حلقة التشغيل الرئيسية
# ═══════════════════════════════════════════════════════════════════════════════

def run_phase2():
    """تشغيل المرحلة الثانية في خيط منفصل"""
    print("=" * 55)
    print("  Phase 2 Upgrade — بدء التشغيل")
    print("  ✅ Annual EPS Filter")
    print("  ✅ Add Method (10% trigger)")
    print("  ✅ Weekly RS Scan (كل إثنين)")
    print("=" * 55 + "\n")

    send_telegram(
        "🚀 <b>المرحلة الثانية تعمل!</b>\n"
        "─"*20 + "\n"
        "✅ Annual EPS Filter (25%+)\n"
        "✅ Add Method (زيادة الرابحة)\n"
        "✅ Weekly RS Scan (كل إثنين)\n\n"
        "النظام الآن أذكى وأقوى! 💪"
    )

    last_weekly = None
    last_add_check = None

    while True:
        try:
            now = datetime.now()

            # Weekly Scan — كل إثنين الساعة 8 صباحاً
            if (now.weekday() == 0 and now.hour == 8 and now.minute < 5
                    and last_weekly != now.date()):
                weekly_rs_scan()
                last_weekly = now.date()

            # Add Method — كل 15 دقيقة
            if (last_add_check is None or
                    (now - last_add_check).seconds >= 900):
                check_add_method()
                last_add_check = now

            time.sleep(60)

        except Exception as e:
            print(f"[Phase2] خطأ: {e}")
            time.sleep(60)

if __name__ == "__main__":
    # تشغيل Weekly Scan فوراً للاختبار
    print("🧪 اختبار Weekly RS Scan...\n")
    weekly_rs_scan()

    print("\n🧪 اختبار Annual EPS...\n")
    test = ["NVDA", "MSFT", "AAPL", "META", "AMZN"]
    scan_annual_eps(test)

    print("\n✅ كل الاختبارات اكتملت!")
    print("لتشغيل النظام كاملاً: from phase2_upgrade import run_phase2; run_phase2()")
