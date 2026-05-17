from telegram_gate import send_telegram, send_alert
"""
monitor_upgrade.py
==================
إضافات على auto_monitor.py بدون تعديله:
✅ Market Regime Filter  — لا شراء في السوق الهابط
✅ Telegram Commands     — /status /pnl /stop /resume /positions
✅ Circuit Breaker       — إيقاف تلقائي عند خسارة 5%
✅ Daily Summary         — تقرير يومي تلقائي الساعة 6 مساءً
"""

import yfinance as yf
import pandas as pd
import requests
import time
import json
import threading
from datetime import datetime, timedelta
from config import (ALPACA_KEY, ALPACA_SECRET,
                    TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
import alpaca_trade_api as tradeapi

# ─── الإعدادات ────────────────────────────────────────────────────────────────
CIRCUIT_BREAKER_PCT   = 0.05   # إيقاف عند خسارة 5% من المحفظة
DAILY_LOSS_LIMIT_PCT  = 0.03   # حد خسارة يومية 3%
TELEGRAM_POLL_INTERVAL = 5     # فحص الأوامر كل 5 ثوانٍ

# ─── الاتصال بـ Alpaca ────────────────────────────────────────────────────────
trading_client = tradeapi.REST(
    ALPACA_KEY, ALPACA_SECRET,
    base_url='https://paper-api.alpaca.markets'
)

# ─── حالة النظام ──────────────────────────────────────────────────────────────
system_state = {
    "running":          True,
    "trading_enabled":  True,   # False = Circuit Breaker فعّال
    "start_portfolio":  None,   # قيمة المحفظة عند البداية
    "daily_start":      None,   # قيمة المحفظة بداية اليوم
    "last_update_id":   0,      # آخر Telegram message_id
    "paused_by_user":   False,
    "paused_by_regime": False,
    "paused_by_circuit": False,
}

# ─── Telegram ─────────────────────────────────────────────────────────────────

def get_telegram_updates():
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
        resp = requests.get(url, params={
            "offset": system_state["last_update_id"] + 1,
            "timeout": 3
        }, timeout=10)
        return resp.json().get("result", [])
    except:
        return []

# ─── Market Regime Filter ─────────────────────────────────────────────────────
def is_market_healthy() -> bool:
    """
    السوق صحي إذا:
    - SPY فوق MA200
    - MA200 صاعد (ليس هابطاً)
    """
    try:
        spy = yf.download("SPY", period="1y", progress=False, auto_adjust=True)
        if spy.empty:
            return True
        spy.columns = [c[0] if isinstance(c, tuple) else c for c in spy.columns]
        close  = spy['Close']
        ma200  = close.rolling(200).mean()
        slope  = ma200.diff(20)

        current_price  = float(close.iloc[-1])
        current_ma200  = float(ma200.iloc[-1])
        current_slope  = float(slope.iloc[-1])

        healthy = current_price > current_ma200 and current_slope > 0

        status = "صحي ✅" if healthy else "هابط ⚠️"
        print(f"[Regime] SPY: ${current_price:.0f} | MA200: ${current_ma200:.0f} | {status}")
        return healthy
    except Exception as e:
        print(f"[Regime] خطأ: {e}")
        return True  # افتراضي: السوق صحي

# ─── Circuit Breaker ──────────────────────────────────────────────────────────
def check_circuit_breaker():
    """
    يوقف التداول تلقائياً إذا:
    - خسارة 5%+ من قيمة المحفظة عند البداية
    - خسارة 3%+ في اليوم الحالي
    """
    try:
        account = trading_client.get_account()
        current = float(account.portfolio_value)

        # تهيئة القيم الأولية
        if system_state["start_portfolio"] is None:
            system_state["start_portfolio"] = current
            system_state["daily_start"]     = current
            return False

        # إعادة تعيين الخسارة اليومية كل صباح
        now = datetime.now()
        if now.hour == 9 and now.minute < 35:
            system_state["daily_start"] = current

        # حساب الخسائر
        total_loss_pct = (current - system_state["start_portfolio"]) / system_state["start_portfolio"]
        daily_loss_pct = (current - system_state["daily_start"])     / system_state["daily_start"]

        # فعّل Circuit Breaker
        if total_loss_pct <= -CIRCUIT_BREAKER_PCT:
            if not system_state["paused_by_circuit"]:
                system_state["trading_enabled"]   = False
                system_state["paused_by_circuit"]  = True
                msg = (
                    f"🚨 <b>Circuit Breaker فعّال!</b>\n"
                    f"خسارة إجمالية: {total_loss_pct*100:.1f}%\n"
                    f"قيمة المحفظة: ${current:,.0f}\n"
                    f"التداول متوقف — أرسل /resume للاستئناف"
                )
                send_telegram(msg)
                print(f"[Circuit Breaker] فعّال! خسارة {total_loss_pct*100:.1f}%")
            return True

        if daily_loss_pct <= -DAILY_LOSS_LIMIT_PCT:
            if not system_state["paused_by_circuit"]:
                system_state["trading_enabled"]  = False
                system_state["paused_by_circuit"] = True
                msg = (
                    f"⚠️ <b>حد الخسارة اليومية!</b>\n"
                    f"خسارة اليوم: {daily_loss_pct*100:.1f}%\n"
                    f"التداول متوقف لبقية اليوم"
                )
                send_telegram(msg)
            return True

        return False
    except Exception as e:
        print(f"[Circuit Breaker] خطأ: {e}")
        return False

# ─── Telegram Commands ────────────────────────────────────────────────────────
def handle_command(text: str):
    """معالجة أوامر Telegram"""
    text = text.strip().lower()
    print(f"[Command] استقبل: {text}")

    # /status — حالة النظام
    if text == "/status":
        try:
            account  = trading_client.get_account()
            cash     = float(account.cash)
            portfolio = float(account.portfolio_value)
            positions = trading_client.list_positions()

            regime  = "صحي ✅" if is_market_healthy() else "هابط ⚠️"
            trading = "مفعّل ✅" if system_state["trading_enabled"] else "متوقف ⛔"

            pnl = ""
            if system_state["start_portfolio"]:
                pnl_pct = (portfolio - system_state["start_portfolio"]) / system_state["start_portfolio"] * 100
                pnl = f"\nP&amp;L الإجمالي: {pnl_pct:+.1f}%"

            msg = (
                f"📊 <b>حالة النظام</b>\n"
                f"{'─'*25}\n"
                f"المحفظة: ${portfolio:,.0f}\n"
                f"النقد: ${cash:,.0f}\n"
                f"المراكز المفتوحة: {len(positions)}{pnl}\n"
                f"السوق: {regime}\n"
                f"التداول: {trading}\n"
                f"الوقت: {datetime.now().strftime('%H:%M:%S')}"
            )
            send_telegram(msg)
        except Exception as e:
            send_telegram(f"❌ خطأ في /status: {e}")

    # /pnl — الأرباح والخسائر
    elif text == "/pnl":
        try:
            positions = trading_client.list_positions()
            if not positions:
                send_telegram("📭 لا توجد مراكز مفتوحة حالياً")
                return

            msg = "💰 <b>المراكز الحالية</b>\n" + "─"*25 + "\n"
            total_pnl = 0
            for pos in positions:
                pnl     = float(pos.unrealized_pl)
                pnl_pct = float(pos.unrealized_plpc) * 100
                emoji   = "🟢" if pnl >= 0 else "🔴"
                msg    += f"{emoji} <b>{pos.symbol}</b>: {pnl_pct:+.1f}% (${pnl:+,.0f})\n"
                total_pnl += pnl

            total_emoji = "🟢" if total_pnl >= 0 else "🔴"
            msg += f"{'─'*25}\n{total_emoji} الإجمالي: ${total_pnl:+,.0f}"
            send_telegram(msg)
        except Exception as e:
            send_telegram(f"❌ خطأ في /pnl: {e}")

    # /positions — تفاصيل المراكز
    elif text == "/positions":
        try:
            positions = trading_client.list_positions()
            if not positions:
                send_telegram("📭 لا توجد مراكز مفتوحة")
                return

            msg = "📋 <b>تفاصيل المراكز</b>\n" + "─"*25 + "\n"
            for pos in positions:
                msg += (
                    f"<b>{pos.symbol}</b>\n"
                    f"  الأسهم: {pos.qty}\n"
                    f"  سعر الدخول: ${float(pos.avg_entry_price):.2f}\n"
                    f"  السعر الحالي: ${float(pos.current_price):.2f}\n"
                    f"  P&amp;L: {float(pos.unrealized_plpc)*100:+.1f}%\n\n"
                )
            send_telegram(msg)
        except Exception as e:
            send_telegram(f"❌ خطأ في /positions: {e}")

    # /stop — إيقاف التداول
    elif text == "/stop":
        system_state["trading_enabled"] = False
        system_state["paused_by_user"]  = True
        send_telegram(
            "⛔ <b>التداول متوقف</b>\n"
            "النظام يراقب فقط — لن يفتح صفقات جديدة\n"
            "أرسل /resume للاستئناف"
        )

    # /resume — استئناف التداول
    elif text == "/resume":
        system_state["trading_enabled"]   = True
        system_state["paused_by_user"]    = False
        system_state["paused_by_circuit"] = False
        send_telegram(
            "✅ <b>التداول مستأنف</b>\n"
            "النظام يبحث عن فرص الآن"
        )

    # /pause — إيقاف مؤقت
    elif text == "/pause":
        system_state["trading_enabled"] = False
        system_state["paused_by_user"]  = True
        send_telegram("⏸ التداول موقوف مؤقتاً — /resume للاستئناف")

    # /regime — حالة السوق
    elif text == "/regime":
        healthy = is_market_healthy()
        if healthy:
            send_telegram("📈 <b>السوق صحي</b>\nSPY فوق MA200 — التداول مسموح")
        else:
            send_telegram("📉 <b>السوق هابط</b>\nSPY تحت MA200 — لا شراء جديد")

    # /help — قائمة الأوامر
    elif text == "/help":
        send_telegram(
            "🤖 <b>أوامر النظام</b>\n"
            "─"*25 + "\n"
            "/status    — حالة النظام والمحفظة\n"
            "/pnl       — الأرباح والخسائر\n"
            "/positions — تفاصيل المراكز\n"
            "/regime    — حالة السوق\n"
            "/stop      — إيقاف التداول\n"
            "/resume    — استئناف التداول\n"
            "/help      — هذه القائمة"
        )

    else:
        send_telegram(f"❓ أمر غير معروف: {text}\nأرسل /help لقائمة الأوامر")

# ─── Daily Summary ────────────────────────────────────────────────────────────
def send_daily_summary():
    """تقرير يومي تلقائي"""
    try:
        account   = trading_client.get_account()
        portfolio = float(account.portfolio_value)
        cash      = float(account.cash)
        positions = trading_client.list_positions()

        daily_pnl = 0
        if system_state["daily_start"]:
            daily_pnl = portfolio - system_state["daily_start"]
            daily_pct = daily_pnl / system_state["daily_start"] * 100
        else:
            daily_pct = 0

        total_pnl = 0
        pos_lines = ""
        for pos in positions:
            pnl = float(pos.unrealized_pl)
            pnl_pct = float(pos.unrealized_plpc) * 100
            emoji = "🟢" if pnl >= 0 else "🔴"
            pos_lines += f"{emoji} {pos.symbol}: {pnl_pct:+.1f}%\n"
            total_pnl += pnl

        emoji_day = "📈" if daily_pnl >= 0 else "📉"
        regime    = "صحي ✅" if is_market_healthy() else "هابط ⚠️"

        msg = (
            f"{emoji_day} <b>التقرير اليومي</b> — {datetime.now().strftime('%Y-%m-%d')}\n"
            f"{'─'*25}\n"
            f"قيمة المحفظة: ${portfolio:,.0f}\n"
            f"النقد المتاح: ${cash:,.0f}\n"
            f"P&amp;L اليوم: ${daily_pnl:+,.0f} ({daily_pct:+.1f}%)\n"
            f"P&amp;L المراكز: ${total_pnl:+,.0f}\n"
            f"عدد المراكز: {len(positions)}\n"
            f"حالة السوق: {regime}\n"
        )
        if pos_lines:
            msg += f"\n<b>المراكز:</b>\n{pos_lines}"

        send_telegram(msg)
        system_state["daily_start"] = portfolio
    except Exception as e:
        send_telegram(f"❌ خطأ في التقرير اليومي: {e}")

# ─── حلقة Telegram Commands ──────────────────────────────────────────────────
def telegram_listener():
    """خيط منفصل لاستقبال الأوامر"""
    print("[Telegram] بدء الاستماع للأوامر...")
    send_telegram(
        "🚀 <b>النظام المحدّث يعمل!</b>\n"
        "─"*20 + "\n"
        "✅ Market Regime Filter\n"
        "✅ Circuit Breaker\n"
        "✅ Telegram Commands\n"
        "✅ Daily Summary\n\n"
        "أرسل /help لقائمة الأوامر"
    )

    last_summary_hour = -1

    while system_state["running"]:
        try:
            # فحص الأوامر
            updates = get_telegram_updates()
            for update in updates:
                system_state["last_update_id"] = update["update_id"]
                if "message" in update and "text" in update["message"]:
                    handle_command(update["message"]["text"])

            # Daily Summary الساعة 6 مساءً
            now = datetime.now()
            if now.hour in [10, 22] and now.minute < 5 and last_summary_hour != now.hour:
                send_daily_summary()
                last_summary_hour = now.hour

            time.sleep(TELEGRAM_POLL_INTERVAL)

        except Exception as e:
            print(f"[Telegram Listener] خطأ: {e}")
            time.sleep(10)

# ─── فحص Regime دوري ─────────────────────────────────────────────────────────
def regime_monitor():
    """فحص حالة السوق كل 30 دقيقة"""
    last_regime_check = None

    while system_state["running"]:
        try:
            now = datetime.now()

            # فحص كل 30 دقيقة
            if last_regime_check is None or (now - last_regime_check).seconds >= 1800:
                healthy = is_market_healthy()
                last_regime_check = now

                if not healthy and not system_state["paused_by_regime"]:
                    system_state["trading_enabled"]  = False
                    system_state["paused_by_regime"]  = True
                    send_telegram(
                        "📉 <b>تنبيه: السوق هابط!</b>\n"
                        "SPY تحت MA200\n"
                        "تم إيقاف الشراء الجديد تلقائياً\n"
                        "المراكز الحالية محمية بـ Stop Loss"
                    )
                    print("[Regime] السوق هابط — إيقاف الشراء")

                elif healthy and system_state["paused_by_regime"]:
                    system_state["trading_enabled"]  = True
                    system_state["paused_by_regime"]  = False
                    send_telegram(
                        "📈 <b>السوق عاد للصحة!</b>\n"
                        "SPY فوق MA200\n"
                        "استُؤنف البحث عن فرص"
                    )
                    print("[Regime] السوق صحي — استئناف التداول")

            # فحص Circuit Breaker كل دقيقة
            check_circuit_breaker()

            time.sleep(60)

        except Exception as e:
            print(f"[Regime Monitor] خطأ: {e}")
            time.sleep(60)

# ─── نقطة الدخول ─────────────────────────────────────────────────────────────
def start_upgrade():
    """تشغيل كل التحسينات في خيوط منفصلة"""
    print("=" * 50)
    print("  Monitor Upgrade — بدء التشغيل")
    print("=" * 50)

    # تهيئة قيمة المحفظة
    try:
        account = trading_client.get_account()
        system_state["start_portfolio"] = float(account.portfolio_value)
        system_state["daily_start"]     = float(account.portfolio_value)
        print(f"[Init] قيمة المحفظة: ${system_state['start_portfolio']:,.0f}")
    except Exception as e:
        print(f"[Init] خطأ: {e}")

    # تشغيل خيوط منفصلة
    t1 = threading.Thread(target=telegram_listener, daemon=True)
    t2 = threading.Thread(target=regime_monitor,    daemon=True)

    t1.start()
    t2.start()

    print("[Upgrade] كل الخدمات تعمل ✅")
    return system_state  # نرجع state للاستخدام في auto_monitor

if __name__ == "__main__":
    # تشغيل مستقل للاختبار
    start_upgrade()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        system_state["running"] = False
        print("\n[Upgrade] تم الإيقاف")
