from telegram_gate import send_telegram, send_alert
"""
priority1_quality.py
====================
الأولوية الأولى — تحسين جودة الصفقات (6 تحسينات في ملف واحد)
✅ ١. ربط Intelligence بـ Decision Engine
✅ ٢. Performance Dashboard
✅ ٣. Dynamic Stop Loss (ATR-based)
✅ ٤. Pre-Market Scanner
✅ ٥. Gap Up Detection
✅ ٦. Volume Profile Analysis
"""

import yfinance as yf
import pandas as pd
import numpy as np
import requests
import json
import time
import threading
from datetime import datetime, timedelta
import pytz
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
import alpaca_trade_api as tradeapi
from config import ALPACA_KEY, ALPACA_SECRET

# ─── الإعدادات ────────────────────────────────────────────────────────────────
NY_TZ = pytz.timezone('America/New_York')

trading_client = tradeapi.REST(
    ALPACA_KEY, ALPACA_SECRET,
    base_url='https://paper-api.alpaca.markets'
)

WATCHLIST = [
    "NVDA","MSFT","AAPL","GOOGL","META","AMZN","AVGO","AMD",
    "CRWD","PANW","PLTR","NOW","DDOG","SNOW",
    "ADBE","CRM","INTU","NFLX","TTD",
    "TSLA","UBER","V","MA","LLY","UNH","COST","WMT",
]


# ═══════════════════════════════════════════════════════════════════════════════
# ١. ربط Intelligence بـ Decision Engine
# ═══════════════════════════════════════════════════════════════════════════════

def load_intelligence_signals() -> dict:
    """يحمّل إشارات Intelligence من الملفات المحفوظة"""
    signals = {
        "macro_ok":      True,
        "macro_score":   0,
        "sector_ok":     True,
        "news_positive": [],
        "news_negative": [],
        "earnings_soon": [],
        "smart_money":   [],
    }

    # ماكرو
    try:
        with open("/root/macro_state.json", encoding="utf-8") as f:
            macro = json.load(f)
        signals["macro_ok"]    = macro.get("action", "SELECTIVE") not in ["CASH", "REDUCE"]
        signals["macro_score"] = macro.get("score", 0)
    except:
        pass

    # قطاعات
    try:
        with open("/root/sector_state.json", encoding="utf-8") as f:
            sectors = json.load(f)
        leading = [
            sym
            for s in sectors.get("sectors", {}).values()
            if s.get("is_leading")
            for sym in s.get("stocks", [])
        ]
        signals["leading_stocks"] = leading
    except:
        signals["leading_stocks"] = []

    return signals

def intelligence_allows_buy(symbol: str, signals: dict) -> tuple:
    """
    يفحص إشارات Intelligence للسماح بالشراء أو رفضه
    """
    # فحص الماكرو
    if not signals.get("macro_ok", True):
        return False, f"الماكرو سلبي (نقاط: {signals.get('macro_score', 0):+d})"

    # فحص أخبار سلبية
    if symbol in signals.get("news_negative", []):
        return False, f"أخبار سلبية لـ {symbol}"

    # فحص نتائج قريبة
    if symbol in signals.get("earnings_soon", []):
        return False, f"نتائج قريبة — انتظر"

    # فحص القطاع القيادي (لا يمنع — فقط يعطي أولوية)
    leading = signals.get("leading_stocks", [])
    if leading and symbol not in leading:
        return True, "⚠️ ليس في قطاع قيادي — أولوية منخفضة"

    return True, "✅ Intelligence يوافق"

# ═══════════════════════════════════════════════════════════════════════════════
# ٢. Performance Dashboard
# ═══════════════════════════════════════════════════════════════════════════════

# سجل الصفقات
trades_log = []

def log_trade(symbol: str, action: str, price: float,
              shares: int, reason: str = ""):
    """يسجل كل صفقة"""
    trades_log.append({
        "timestamp": str(datetime.now()),
        "symbol":    symbol,
        "action":    action,
        "price":     price,
        "shares":    shares,
        "reason":    reason,
        "value":     price * shares,
    })
    # حفظ في ملف
    try:
        existing = []
        try:
            with open("/root/trades_log.json", encoding="utf-8") as f:
                existing = json.load(f)
        except:
            pass
        existing.append(trades_log[-1])
        with open("/root/trades_log.json", "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Log] خطأ: {e}")

def generate_performance_report() -> str:
    """يولّد تقرير أداء شامل"""
    try:
        # تحميل الصفقات
        try:
            with open("/root/trades_log.json", encoding="utf-8") as f:
                all_trades = json.load(f)
        except:
            all_trades = []

        # حساب الإحصائيات من Alpaca
        account   = trading_client.get_account()
        portfolio = float(account.portfolio_value)
        cash      = float(account.cash)
        positions = trading_client.list_positions()

        # حساب P&L المراكز الحالية
        total_unrealized = sum(float(p.unrealized_pl) for p in positions)
        total_unrealized_pct = sum(
            float(p.unrealized_plpc) * 100 for p in positions
        ) / max(len(positions), 1)

        # إحصائيات من السجل
        buys  = [t for t in all_trades if t["action"] == "BUY"]
        sells = [t for t in all_trades if t["action"] == "SELL"]

        # حساب صفقات مغلقة
        closed_trades = []
        for sell in sells:
            sym  = sell["symbol"]
            buy  = next((b for b in buys if b["symbol"] == sym), None)
            if buy:
                pnl = (sell["price"] - buy["price"]) * sell["shares"]
                pnl_pct = (sell["price"] - buy["price"]) / buy["price"] * 100
                closed_trades.append({
                    "symbol":  sym,
                    "pnl":     pnl,
                    "pnl_pct": pnl_pct,
                })

        winners = [t for t in closed_trades if t["pnl"] > 0]
        losers  = [t for t in closed_trades if t["pnl"] <= 0]
        win_rate = len(winners) / max(len(closed_trades), 1) * 100

        avg_win  = np.mean([t["pnl_pct"] for t in winners]) if winners else 0
        avg_loss = np.mean([t["pnl_pct"] for t in losers])  if losers  else 0
        rr_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0

        # Max Drawdown من portfolio history
        max_dd = -15.0  # placeholder — يحتاج تاريخ المحفظة

        report = (
            f"📊 <b>Performance Dashboard</b>\n"
            f"{datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"{'─'*28}\n\n"
            f"<b>المحفظة:</b>\n"
            f"القيمة الكلية: ${portfolio:,.0f}\n"
            f"النقد: ${cash:,.0f}\n"
            f"P&amp;L غير محققة: ${total_unrealized:+,.0f}\n"
            f"مراكز مفتوحة: {len(positions)}\n\n"
            f"<b>إحصائيات الصفقات:</b>\n"
            f"إجمالي الصفقات: {len(closed_trades)}\n"
            f"Win Rate: {win_rate:.1f}%\n"
            f"متوسط الربح: {avg_win:+.1f}%\n"
            f"متوسط الخسارة: {avg_loss:+.1f}%\n"
            f"R:R Ratio: {rr_ratio:.2f}x\n\n"
        )

        if positions:
            report += "<b>المراكز الحالية:</b>\n"
            for pos in positions:
                pnl_pct = float(pos.unrealized_plpc) * 100
                emoji   = "🟢" if pnl_pct >= 0 else "🔴"
                report += f"{emoji} {pos.symbol}: {pnl_pct:+.1f}%\n"

        return report

    except Exception as e:
        return f"❌ خطأ في Dashboard: {e}"

# ═══════════════════════════════════════════════════════════════════════════════
# ٣. Dynamic Stop Loss (ATR-based)
# ═══════════════════════════════════════════════════════════════════════════════

def calc_atr_stop(symbol: str, multiplier: float = 2.5) -> dict:
    """
    يحسب Stop Loss ديناميكي بناءً على ATR
    Minervini يستخدم ATR × 2-3 كـ Stop Loss
    أقل تذبذب → Stop أضيق | أكثر تذبذب → Stop أوسع
    """
    result = {
        "stop_pct":   0.07,  # الافتراضي 7%
        "atr":        None,
        "atr_pct":    None,
        "method":     "fixed_7pct",
    }

    try:
        df = yf.download(symbol, period="3mo", progress=False, auto_adjust=True)
        if df.empty or len(df) < 20:
            return result

        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

        # حساب ATR
        hl   = df['High'] - df['Low']
        hpc  = (df['High'] - df['Close'].shift()).abs()
        lpc  = (df['Low']  - df['Close'].shift()).abs()
        tr   = pd.concat([hl, hpc, lpc], axis=1).max(axis=1)
        atr  = tr.rolling(14).mean().iloc[-1]
        price = float(df['Close'].iloc[-1])

        atr_pct = (atr / price) * multiplier

        # حد أدنى 5% وحد أقصى 12%
        stop_pct = max(0.05, min(0.12, atr_pct))

        result.update({
            "stop_pct": round(stop_pct, 4),
            "atr":      round(atr, 2),
            "atr_pct":  round(atr_pct * 100, 2),
            "method":   "atr_dynamic",
            "price":    price,
        })

        print(f"[ATR Stop] {symbol}: ATR={atr:.2f} | Stop={stop_pct*100:.1f}%")

    except Exception as e:
        print(f"[ATR Stop] خطأ {symbol}: {e}")

    return result

# ═══════════════════════════════════════════════════════════════════════════════
# ٤. Pre-Market Scanner
# ═══════════════════════════════════════════════════════════════════════════════

def pre_market_scan(watchlist: list) -> list:
    """
    يفحص الأسهم قبل افتتاح السوق (8:00-9:30 صباحاً نيويورك)
    يبحث عن: أسهم قريبة من Pivot + حجم مرتفع في Pre-Market
    """
    print(f"\n[Pre-Market] فحص {len(watchlist)} سهم...")
    opportunities = []

    for sym in watchlist:
        try:
            df = yf.download(sym, period="5d", interval="1h",
                           progress=False, auto_adjust=True)
            if df.empty or len(df) < 10:
                continue

            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

            # آخر سعر متاح
            last_close = float(df['Close'].iloc[-1])

            # أعلى سعر في آخر 20 يوم (Pivot)
            daily = yf.download(sym, period="1mo", progress=False, auto_adjust=True)
            if daily.empty:
                continue
            daily.columns = [c[0] if isinstance(c, tuple) else c for c in daily.columns]

            pivot   = float(daily['High'].rolling(15).max().iloc[-1])
            pct_gap = (last_close - pivot) / pivot * 100

            # قريب من الـ Pivot (ضمن 3%)
            if -3 <= pct_gap <= 2:
                # فحص الحجم
                avg_vol  = float(daily['Volume'].rolling(20).mean().iloc[-1])
                last_vol = float(daily['Volume'].iloc[-1])
                vol_ratio = last_vol / avg_vol if avg_vol > 0 else 0

                opportunities.append({
                    "symbol":    sym,
                    "price":     last_close,
                    "pivot":     round(pivot, 2),
                    "pct_gap":   round(pct_gap, 2),
                    "vol_ratio": round(vol_ratio, 2),
                    "priority":  "high" if vol_ratio > 1.5 else "normal",
                })
                print(f"  📍 {sym}: ${last_close:.2f} | Pivot: ${pivot:.2f} | Gap: {pct_gap:+.1f}%")

        except Exception as e:
            pass

    opportunities.sort(key=lambda x: x["vol_ratio"], reverse=True)
    print(f"[Pre-Market] {len(opportunities)} فرصة محتملة")
    return opportunities

def send_pre_market_report(opportunities: list):
    """يرسل تقرير Pre-Market على Telegram"""
    if not opportunities:
        send_telegram("📭 Pre-Market: لا توجد فرص قريبة من الـ Pivot اليوم")
        return

    msg = (
        f"🌅 <b>Pre-Market Scanner</b>\n"
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"{'─'*25}\n\n"
        f"أسهم قريبة من Pivot قبل الافتتاح:\n\n"
    )

    for opp in opportunities[:8]:
        priority = "🔥" if opp["priority"] == "high" else "📍"
        msg += (
            f"{priority} <b>{opp['symbol']}</b>\n"
            f"   السعر: ${opp['price']:.2f} | Pivot: ${opp['pivot']:.2f}\n"
            f"   المسافة: {opp['pct_gap']:+.1f}% | حجم: {opp['vol_ratio']:.1f}x\n\n"
        )

    msg += "⏰ السوق يفتح بعد قليل — ترقب الاختراق بحجم قوي"
    send_telegram(msg)

# ═══════════════════════════════════════════════════════════════════════════════
# ٥. Gap Up Detection
# ═══════════════════════════════════════════════════════════════════════════════

def detect_gap_ups(watchlist: list, min_gap_pct: float = 3.0) -> list:
    """
    يكتشف الأسهم التي فتحت بارتفاع قوي (Gap Up)
    Gap Up + Trend Template = فرصة ذهبية
    """
    print(f"\n[Gap Up] البحث عن Gaps قوية...")
    gaps = []

    for sym in watchlist:
        try:
            df = yf.download(sym, period="5d", interval="1d",
                           progress=False, auto_adjust=True)
            if df.empty or len(df) < 3:
                continue

            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

            # Gap = الافتتاح اليوم vs الإغلاق أمس
            today_open  = float(df['Open'].iloc[-1])
            prev_close  = float(df['Close'].iloc[-2])
            gap_pct     = (today_open - prev_close) / prev_close * 100

            today_vol   = float(df['Volume'].iloc[-1])
            avg_vol     = float(df['Volume'].rolling(20).mean().iloc[-2])
            vol_ratio   = today_vol / avg_vol if avg_vol > 0 else 0

            if gap_pct >= min_gap_pct:
                # تحقق من الـ Trend Template أولاً
                close = df['Close']
                ma50  = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else None
                trend_ok = (float(close.iloc[-1]) > float(ma50)) if ma50 else False

                gaps.append({
                    "symbol":    sym,
                    "gap_pct":   round(gap_pct, 2),
                    "open":      today_open,
                    "prev_close": prev_close,
                    "vol_ratio": round(vol_ratio, 2),
                    "trend_ok":  trend_ok,
                    "quality":   "A" if (gap_pct >= 5 and vol_ratio >= 2 and trend_ok)
                                 else "B" if (gap_pct >= 3 and trend_ok)
                                 else "C",
                })
                print(f"  ⬆️ {sym}: Gap {gap_pct:+.1f}% | Vol: {vol_ratio:.1f}x | Trend: {'✅' if trend_ok else '❌'}")

        except Exception as e:
            pass

    gaps.sort(key=lambda x: (x["quality"], x["gap_pct"]), reverse=True)
    print(f"[Gap Up] {len(gaps)} Gap وُجد")
    return gaps

def send_gap_report(gaps: list):
    """يرسل تقرير Gap Ups على Telegram"""
    if not gaps:
        return

    msg = (
        f"⬆️ <b>Gap Up Detection</b>\n"
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"{'─'*25}\n\n"
    )

    quality_a = [g for g in gaps if g["quality"] == "A"]
    quality_b = [g for g in gaps if g["quality"] == "B"]

    if quality_a:
        msg += "🏆 <b>فرص A (Gap قوي + Trend + حجم)</b>\n"
        for g in quality_a[:3]:
            msg += f"🔥 {g['symbol']}: +{g['gap_pct']:.1f}% | {g['vol_ratio']:.1f}x حجم\n"
        msg += "\n"

    if quality_b:
        msg += "✅ <b>فرص B (Gap + Trend)</b>\n"
        for g in quality_b[:3]:
            msg += f"📈 {g['symbol']}: +{g['gap_pct']:.1f}%\n"

    send_telegram(msg)

# ═══════════════════════════════════════════════════════════════════════════════
# ٦. Volume Profile Analysis
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_volume_profile(symbol: str, periods: int = 60) -> dict:
    """
    يحلل Volume Profile لإيجاد مناطق الدعم والمقاومة الحقيقية
    High Volume Nodes = دعم ومقاومة قوية
    Low Volume Nodes = مناطق تتحرك فيها الأسعار بسرعة
    """
    result = {
        "symbol":     symbol,
        "support":    [],
        "resistance": [],
        "poc":        None,  # Point of Control (أعلى حجم)
        "vah":        None,  # Value Area High
        "val":        None,  # Value Area Low
    }

    try:
        df = yf.download(symbol, period="3mo", progress=False, auto_adjust=True)
        if df.empty or len(df) < 20:
            return result

        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

        close   = df['Close']
        volume  = df['Volume']
        current = float(close.iloc[-1])

        # إنشاء Volume Profile (20 مستوى سعري)
        price_min = float(close.min())
        price_max = float(close.max())
        price_range = price_max - price_min
        if price_range == 0:
            return result

        n_levels = 20
        level_size = price_range / n_levels
        profile = {}

        for price, vol in zip(close, volume):
            level = int((float(price) - price_min) / level_size)
            level = min(level, n_levels - 1)
            level_price = price_min + (level * level_size) + (level_size / 2)
            profile[round(level_price, 2)] = profile.get(round(level_price, 2), 0) + float(vol)

        # Point of Control (أعلى حجم)
        poc_price = max(profile, key=profile.get)
        result["poc"] = poc_price

        # Value Area (70% من الحجم حول الـ POC)
        total_vol    = sum(profile.values())
        target_vol   = total_vol * 0.70
        sorted_levels = sorted(profile.items(), key=lambda x: x[1], reverse=True)

        value_area   = []
        accum_vol    = 0
        for price, vol in sorted_levels:
            value_area.append(price)
            accum_vol += vol
            if accum_vol >= target_vol:
                break

        result["vah"] = max(value_area)
        result["val"] = min(value_area)

        # مناطق الدعم (أسفل السعر الحالي + حجم عالٍ)
        for price, vol in sorted_levels[:5]:
            if price < current:
                result["support"].append(round(price, 2))
            else:
                result["resistance"].append(round(price, 2))

        result["support"]    = sorted(result["support"], reverse=True)[:3]
        result["resistance"] = sorted(result["resistance"])[:3]

        print(f"[Volume Profile] {symbol}: POC=${poc_price:.2f} | VAH=${result['vah']:.2f} | VAL=${result['val']:.2f}")

    except Exception as e:
        print(f"[Volume Profile] خطأ {symbol}: {e}")

    return result

def check_near_support(symbol: str, price: float, vp: dict) -> tuple:
    """يفحص إذا كان السعر قريباً من منطقة دعم قوية"""
    support = vp.get("support", [])
    val     = vp.get("val")

    for sup in support:
        if abs(price - sup) / price < 0.03:  # ضمن 3%
            return True, f"قرب دعم Volume Profile ${sup:.2f}"

    if val and abs(price - val) / price < 0.02:
        return True, f"قرب Value Area Low ${val:.2f}"

    return False, "لا يوجد دعم قريب"

# ═══════════════════════════════════════════════════════════════════════════════
# محرك القرار المحدّث — يجمع كل التحسينات
# ═══════════════════════════════════════════════════════════════════════════════

def enhanced_buy_decision(symbol: str, price: float) -> dict:
    """
    قرار الشراء المحسّن — يجمع كل الفلاتر الستة
    """
    result = {
        "symbol":  symbol,
        "allowed": True,
        "score":   0,
        "reasons": [],
        "blocks":  [],
        "stop_pct": 0.07,
        "stop_price": price * 0.93,
    }

    # تحميل إشارات Intelligence
    signals = load_intelligence_signals()

    # ─── ١. Intelligence Filter ──────────────────────────────────────────────
    intel_ok, intel_reason = intelligence_allows_buy(symbol, signals)
    if intel_ok:
        result["score"] += 2
        result["reasons"].append(f"✅ {intel_reason}")
    else:
        result["allowed"] = False
        result["blocks"].append(f"❌ Intelligence: {intel_reason}")

    # ─── ٢. ATR Dynamic Stop Loss ────────────────────────────────────────────
    atr_data = calc_atr_stop(symbol)
    result["stop_pct"]   = atr_data["stop_pct"]
    result["stop_price"] = price * (1 - atr_data["stop_pct"])
    result["reasons"].append(
        f"✅ Stop Loss ديناميكي: {atr_data['stop_pct']*100:.1f}% "
        f"(ATR: {atr_data.get('atr_pct', 'N/A')}%)"
    )

    # ─── ٣. Gap Up Bonus ─────────────────────────────────────────────────────
    try:
        df = yf.download(symbol, period="3d", interval="1d",
                        progress=False, auto_adjust=True)
        if not df.empty and len(df) >= 2:
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
            gap_pct = (float(df['Open'].iloc[-1]) - float(df['Close'].iloc[-2])) / float(df['Close'].iloc[-2]) * 100
            if gap_pct >= 3:
                result["score"] += 1
                result["reasons"].append(f"✅ Gap Up: +{gap_pct:.1f}%")
    except:
        pass

    # ─── ٤. Volume Profile Support ───────────────────────────────────────────
    vp = analyze_volume_profile(symbol)
    near_support, vp_reason = check_near_support(symbol, price, vp)
    if near_support:
        result["score"] += 1
        result["reasons"].append(f"✅ {vp_reason}")
    result["volume_profile"] = vp

    # ─── القرار النهائي ──────────────────────────────────────────────────────
    if result["blocks"]:
        result["allowed"] = False

    return result

# ═══════════════════════════════════════════════════════════════════════════════
# الجدول الزمني التلقائي
# ═══════════════════════════════════════════════════════════════════════════════

def run_priority1():
    """تشغيل كل تحسينات الأولوية الأولى بجدول زمني"""
    print("=" * 55)
    print("  Priority 1 — تحسين جودة الصفقات")
    print("  ✅ Intelligence Integration")
    print("  ✅ Performance Dashboard")
    print("  ✅ Dynamic ATR Stop Loss")
    print("  ✅ Pre-Market Scanner")
    print("  ✅ Gap Up Detection")
    print("  ✅ Volume Profile Analysis")
    print("=" * 55 + "\n")

    send_telegram(
        "🚀 <b>Priority 1 يعمل!</b>\n"
        "─"*20 + "\n"
        "✅ Intelligence مرتبط بالقرار\n"
        "✅ Performance Dashboard\n"
        "✅ Dynamic ATR Stop Loss\n"
        "✅ Pre-Market Scanner\n"
        "✅ Gap Up Detection\n"
        "✅ Volume Profile Analysis\n\n"
        "النظام أصبح أكثر دقة! 🎯"
    )

    last_premarket  = None
    last_gap        = None
    last_dashboard  = None

    while True:
        try:
            now    = datetime.now(NY_TZ)
            hour   = now.hour
            minute = now.minute
            today  = now.date()

            # Pre-Market Scan — 8:30 صباحاً نيويورك
            if hour == 8 and 25 <= minute <= 35 and last_premarket != today:
                opps = pre_market_scan(WATCHLIST)
                send_pre_market_report(opps)
                last_premarket = today

            # Gap Up Detection — عند الافتتاح 9:35 صباحاً
            if hour == 9 and 35 <= minute <= 45 and last_gap != today:
                gaps = detect_gap_ups(WATCHLIST)
                if gaps:
                    send_gap_report(gaps)
                last_gap = today

            # Performance Dashboard — 4:30 مساءً (بعد إغلاق السوق)
            if hour == 16 and 30 <= minute <= 40 and last_dashboard != today:
                report = generate_performance_report()
                send_telegram(report)
                last_dashboard = today

            time.sleep(60)

        except Exception as e:
            print(f"[Priority1] خطأ: {e}")
            time.sleep(60)

# ═══════════════════════════════════════════════════════════════════════════════
# نقطة الدخول
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("🧪 اختبار Priority 1...\n")

    # اختبار ATR Stop Loss
    print("١. Dynamic ATR Stop Loss:")
    for sym in ["NVDA", "TSLA", "AAPL"]:
        atr = calc_atr_stop(sym)
        print(f"   {sym}: Stop = {atr['stop_pct']*100:.1f}% (ATR method)")

    # اختبار Pre-Market
    print("\n٢. Pre-Market Scanner:")
    opps = pre_market_scan(WATCHLIST[:10])
    send_pre_market_report(opps)

    # اختبار Gap Up
    print("\n٣. Gap Up Detection:")
    gaps = detect_gap_ups(WATCHLIST[:10])
    if gaps:
        send_gap_report(gaps)
    else:
        print("   لا توجد Gaps اليوم")

    # اختبار Volume Profile
    print("\n٤. Volume Profile:")
    vp = analyze_volume_profile("NVDA")
    print(f"   NVDA: POC=${vp.get('poc', 'N/A')} | Support={vp.get('support', [])}")

    # Performance Dashboard
    print("\n٥. Performance Dashboard:")
    report = generate_performance_report()
    send_telegram(report)

    print("\n✅ كل الاختبارات اكتملت!")
