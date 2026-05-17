from telegram_gate import send_telegram, send_alert
#!/usr/bin/env python3
"""
Event Awareness System — Hedge Fund Level
يراقب الأحداث الخطرة ويحمي المحفظة تلقائياً
"""

import requests
import json
import time
import schedule
from datetime import datetime, timedelta
import pytz

# ===== استيراد الإعدادات =====
import sys
sys.path.insert(0, '/root')
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, ALPACA_API_KEY, ALPACA_SECRET_KEY
ALPACA_KEY = ALPACA_API_KEY
ALPACA_SECRET = ALPACA_SECRET_KEY

# ===== الإعدادات =====
ALPACA_BASE = "https://paper-api.alpaca.markets"
ET = pytz.timezone('America/New_York')
STATE_FILE = "/root/event_state.json"

HEADERS_ALPACA = {
    "APCA-API-KEY-ID": ALPACA_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET
}

# ===== الأحداث الاقتصادية الثابتة (تُحدَّث شهرياً) =====
# تواريخ 2026 — أضف المواعيد الفعلية من: https://www.federalreserve.gov/monetarypolicy/fomccalendar.htm
ECONOMIC_EVENTS = [
    # FOMC Meetings 2026
    {"name": "FOMC Meeting", "date": "2026-01-28", "type": "FOMC", "risk": "HIGH"},
    {"name": "FOMC Meeting", "date": "2026-03-18", "type": "FOMC", "risk": "HIGH"},
    {"name": "FOMC Meeting", "date": "2026-05-06", "type": "FOMC", "risk": "HIGH"},
    {"name": "FOMC Meeting", "date": "2026-06-17", "type": "FOMC", "risk": "HIGH"},
    {"name": "FOMC Meeting", "date": "2026-07-29", "type": "FOMC", "risk": "HIGH"},
    {"name": "FOMC Meeting", "date": "2026-09-16", "type": "FOMC", "risk": "HIGH"},
    {"name": "FOMC Meeting", "date": "2026-11-04", "type": "FOMC", "risk": "HIGH"},
    {"name": "FOMC Meeting", "date": "2026-12-16", "type": "FOMC", "risk": "HIGH"},

    # CPI Reports 2026 (تقريبية — كل 2nd Wednesday)
    {"name": "CPI Report", "date": "2026-01-14", "type": "CPI", "risk": "HIGH"},
    {"name": "CPI Report", "date": "2026-02-11", "type": "CPI", "risk": "HIGH"},
    {"name": "CPI Report", "date": "2026-03-11", "type": "CPI", "risk": "HIGH"},
    {"name": "CPI Report", "date": "2026-04-15", "type": "CPI", "risk": "HIGH"},
    {"name": "CPI Report", "date": "2026-05-13", "type": "CPI", "risk": "HIGH"},
    {"name": "CPI Report", "date": "2026-06-10", "type": "CPI", "risk": "HIGH"},
    {"name": "CPI Report", "date": "2026-07-15", "type": "CPI", "risk": "HIGH"},
    {"name": "CPI Report", "date": "2026-08-12", "type": "CPI", "risk": "HIGH"},
    {"name": "CPI Report", "date": "2026-09-09", "type": "CPI", "risk": "HIGH"},
    {"name": "CPI Report", "date": "2026-10-14", "type": "CPI", "risk": "HIGH"},
    {"name": "CPI Report", "date": "2026-11-12", "type": "CPI", "risk": "HIGH"},
    {"name": "CPI Report", "date": "2026-12-09", "type": "CPI", "risk": "HIGH"},

    # NFP Reports 2026 (1st Friday of each month)
    {"name": "NFP Jobs Report", "date": "2026-01-09", "type": "NFP", "risk": "MEDIUM"},
    {"name": "NFP Jobs Report", "date": "2026-02-06", "type": "NFP", "risk": "MEDIUM"},
    {"name": "NFP Jobs Report", "date": "2026-03-06", "type": "NFP", "risk": "MEDIUM"},
    {"name": "NFP Jobs Report", "date": "2026-04-03", "type": "NFP", "risk": "MEDIUM"},
    {"name": "NFP Jobs Report", "date": "2026-05-01", "type": "NFP", "risk": "MEDIUM"},
    {"name": "NFP Jobs Report", "date": "2026-06-05", "type": "NFP", "risk": "MEDIUM"},
    {"name": "NFP Jobs Report", "date": "2026-07-10", "type": "NFP", "risk": "MEDIUM"},
    {"name": "NFP Jobs Report", "date": "2026-08-07", "type": "NFP", "risk": "MEDIUM"},
    {"name": "NFP Jobs Report", "date": "2026-09-04", "type": "NFP", "risk": "MEDIUM"},
    {"name": "NFP Jobs Report", "date": "2026-10-02", "type": "NFP", "risk": "MEDIUM"},
    {"name": "NFP Jobs Report", "date": "2026-11-06", "type": "NFP", "risk": "MEDIUM"},
    {"name": "NFP Jobs Report", "date": "2026-12-04", "type": "NFP", "risk": "MEDIUM"},
]

# ===== إرسال Telegram =====

# ===== قراءة وحفظ الحالة =====
def load_state():
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except:
        return {"lockdown": False, "warning": False, "last_event": None, "mode": "normal"}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

# ===== جلب Earnings من Alpaca =====
def get_upcoming_earnings():
    try:
        # جلب الأسهم في المحفظة
        r = requests.get(f"{ALPACA_BASE}/v2/positions", headers=HEADERS_ALPACA, timeout=10)
        if r.status_code != 200:
            return []
        positions = r.json()
        symbols = [p['symbol'] for p in positions]

        earnings_events = []
        today = datetime.now(ET).date()

        for symbol in symbols:
            # Finnhub Earnings Calendar
            try:
                from config import FINNHUB_API_KEY
                url = f"https://finnhub.io/api/v1/calendar/earnings?from={today}&to={today + timedelta(days=7)}&symbol={symbol}&token={FINNHUB_API_KEY}"
                r2 = requests.get(url, timeout=10)
                data = r2.json()
                for item in data.get('earningsCalendar', []):
                    earnings_events.append({
                        "name": f"Earnings: {symbol}",
                        "date": item['date'],
                        "type": "EARNINGS",
                        "risk": "HIGH",
                        "symbol": symbol
                    })
            except:
                pass

        return earnings_events
    except:
        return []

# ===== فحص الأحداث القادمة =====
def check_events():
    state = load_state()
    today = datetime.now(ET).date()
    tomorrow = today + timedelta(days=1)
    
    all_events = ECONOMIC_EVENTS + get_upcoming_earnings()
    
    # إعادة تعيين الحالة افتراضياً
    new_mode = "normal"
    active_event = None
    warning_event = None

    for event in all_events:
        event_date = datetime.strptime(event['date'], "%Y-%m-%d").date()
        
        # الحدث اليوم → LOCKDOWN
        if event_date == today:
            new_mode = "lockdown"
            active_event = event
            break
        
        # الحدث غداً → WARNING
        elif event_date == tomorrow:
            if new_mode != "lockdown":
                new_mode = "warning"
                warning_event = event

    # تحديث الحالة وإرسال التنبيهات
    old_mode = state.get("mode", "normal")

    if new_mode == "lockdown" and old_mode != "lockdown":
        state["mode"] = "lockdown"
        state["lockdown"] = True
        state["warning"] = False
        state["last_event"] = active_event['name']
        save_state(state)
        
        msg = f"""🔴 <b>LOCKDOWN MODE — حدث خطر اليوم</b>

📅 الحدث: <b>{active_event['name']}</b>
⚠️ المخاطر: {active_event['risk']}
🚫 الإجراء: <b>لا صفقات جديدة</b>
📉 التعرض: تقليل المراكز الجديدة

النظام في وضع الحماية حتى انتهاء الحدث."""
        send_telegram(msg)
        print(f"[EventAwareness] 🔴 LOCKDOWN: {active_event['name']}")

    elif new_mode == "warning" and old_mode != "warning":
        state["mode"] = "warning"
        state["lockdown"] = False
        state["warning"] = True
        state["last_event"] = warning_event['name']
        save_state(state)
        
        msg = f"""🟡 <b>WARNING — حدث خطر غداً</b>

📅 الحدث: <b>{warning_event['name']}</b>
⚠️ المخاطر: {warning_event['risk']}
⚡ الإجراء: تقليل الحجم 50%
🔍 مراقبة إضافية مفعّلة

استعد للتقلبات غداً."""
        send_telegram(msg)
        print(f"[EventAwareness] 🟡 WARNING: {warning_event['name']}")

    elif new_mode == "normal" and old_mode != "normal":
        state["mode"] = "normal"
        state["lockdown"] = False
        state["warning"] = False
        state["last_event"] = None
        save_state(state)
        
        msg = "✅ <b>العودة للوضع الطبيعي</b>\n\nانتهى الحدث — النظام يعمل بكامل طاقته."
        send_telegram(msg)
        print("[EventAwareness] ✅ NORMAL mode resumed")

    else:
        print(f"[EventAwareness] Mode: {new_mode} | Event: {active_event['name'] if active_event else warning_event['name'] if warning_event else 'None'}")

    return state

# ===== تقرير الأحداث القادمة =====
def weekly_events_report():
    today = datetime.now(ET).date()
    next_2_weeks = today + timedelta(days=14)
    
    upcoming = []
    for event in ECONOMIC_EVENTS:
        event_date = datetime.strptime(event['date'], "%Y-%m-%d").date()
        if today <= event_date <= next_2_weeks:
            days_left = (event_date - today).days
            upcoming.append((days_left, event))
    
    upcoming.sort(key=lambda x: x[0])
    
    if not upcoming:
        return
    
    msg = "📅 <b>الأحداث القادمة — 2 أسبوع</b>\n\n"
    for days_left, event in upcoming:
        emoji = "🔴" if event['risk'] == "HIGH" else "🟡"
        msg += f"{emoji} <b>{event['name']}</b>\n"
        msg += f"   📅 {event['date']} (بعد {days_left} يوم)\n\n"
    
    send_telegram(msg)
    print("[EventAwareness] Weekly report sent")

# ===== الحالة للأنظمة الأخرى =====
def get_event_state():
    """تُستخدم من decision_engine و auto_monitor"""
    return load_state()

def is_trading_allowed():
    """هل يسمح بالتداول الآن؟"""
    state = load_state()
    return state.get("mode", "normal") != "lockdown"

def get_position_multiplier():
    """مضاعف حجم الصفقة حسب الحدث"""
    state = load_state()
    mode = state.get("mode", "normal")
    if mode == "lockdown":
        return 0.0   # لا تداول
    elif mode == "warning":
        return 0.5   # نصف الحجم
    else:
        return 1.0   # حجم كامل

# ===== التشغيل الرئيسي =====
def run_event_awareness():
    print("[EventAwareness] 🚀 بدء نظام Event Awareness")
    
    # فحص فوري
    check_events()
    
    # جدول التشغيل
    schedule.every(1).hours.do(check_events)
    schedule.every().monday.at("08:00").do(weekly_events_report)
    
    # تقرير فوري عند البدء
    weekly_events_report()
    
    while True:
        schedule.run_pending()
        time.sleep(300)

if __name__ == "__main__":
    run_event_awareness()
