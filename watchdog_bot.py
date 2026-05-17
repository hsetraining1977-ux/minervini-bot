from telegram_gate import send_telegram, send_alert
"""
watchdog.py
===========
نظام مراقبة ذاتية — يضمن عمل كل البرامج 24/7
✅ يراقب كل البرامج كل دقيقة
✅ يعيد تشغيل أي برنامج توقف تلقائياً
✅ يرسل تنبيه على Telegram عند أي إعادة تشغيل
✅ يرسل تقرير صحة النظام كل 6 ساعات
✅ يتحقق من اتصال الإنترنت
"""

import subprocess
import time
import requests
import psutil
import os
from datetime import datetime
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

# ─── البرامج المراد مراقبتها ─────────────────────────────────────────────────
PROGRAMS = {
    "auto_monitor": {
        "file":    "/root/auto_monitor.py",
        "cmd":     "python3 /root/auto_monitor.py > /root/nohup.out 2>&1",
        "restarts": 0,
        "last_restart": None,
    },
    "monitor_upgrade": {
        "file":    "/root/monitor_upgrade.py",
        "cmd":     "python3 /root/monitor_upgrade.py > /root/upgrade.out 2>&1",
        "restarts": 0,
        "last_restart": None,
    },
    "phase2_upgrade": {
        "file":    "/root/phase2_upgrade.py",
        "cmd":     "python3 -c \"import threading; from phase2_upgrade import run_phase2; t=threading.Thread(target=run_phase2,daemon=True); t.start(); import time\nwhile True: time.sleep(60)\" > /root/phase2.out 2>&1",
        "restarts": 0,
        "last_restart": None,
    },
    "phase3_sectors": {
        "file":    "/root/phase3_sectors.py",
        "cmd":     "python3 -c \"import threading; from phase3_sectors import run_sector_rotation; t=threading.Thread(target=run_sector_rotation,daemon=True); t.start(); import time\nwhile True: time.sleep(60)\" > /root/phase3.out 2>&1",
        "restarts": 0,
        "last_restart": None,
    },
}

# ─── Telegram ─────────────────────────────────────────────────────────────────

# ─── فحص البرامج ──────────────────────────────────────────────────────────────
def is_running(program_name: str) -> bool:
    """يتحقق إن كان البرنامج يعمل"""
    try:
        result = subprocess.run(
            ["pgrep", "-f", program_name],
            capture_output=True, text=True
        )
        return bool(result.stdout.strip())
    except:
        return False

def restart_program(name: str, program: dict):
    """يعيد تشغيل برنامج متوقف"""
    try:
        os.system(f"cd /root && {program['cmd']} &")
        program["restarts"] += 1
        program["last_restart"] = datetime.now()

        msg = (
            f"🔄 <b>إعادة تشغيل تلقائية</b>\n"
            f"{'─'*20}\n"
            f"البرنامج: {name}\n"
            f"الوقت: {datetime.now().strftime('%H:%M:%S')}\n"
            f"عدد مرات الإعادة: {program['restarts']}"
        )
        send_telegram(msg)
        print(f"[Watchdog] ✅ أعيد تشغيل {name}")
        return True
    except Exception as e:
        print(f"[Watchdog] ❌ فشل إعادة تشغيل {name}: {e}")
        return False

# ─── فحص الإنترنت ─────────────────────────────────────────────────────────────
def check_internet() -> bool:
    try:
        requests.get("https://api.telegram.org", timeout=5)
        return True
    except:
        return False

# ─── تقرير الصحة ──────────────────────────────────────────────────────────────
def send_health_report():
    """تقرير صحة النظام كل 6 ساعات"""
    try:
        cpu    = psutil.cpu_percent(interval=1)
        mem    = psutil.virtual_memory()
        disk   = psutil.disk_usage('/')
        uptime = datetime.now() - datetime.fromtimestamp(psutil.boot_time())

        status_lines = ""
        for name, prog in PROGRAMS.items():
            running = is_running(name)
            emoji   = "✅" if running else "❌"
            restarts = prog["restarts"]
            status_lines += f"{emoji} {name}: {'يعمل' if running else 'متوقف'}"
            if restarts > 0:
                status_lines += f" (أُعيد {restarts}×)"
            status_lines += "\n"

        msg = (
            f"💻 <b>تقرير صحة النظام</b>\n"
            f"{datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"{'─'*25}\n\n"
            f"<b>البرامج:</b>\n{status_lines}\n"
            f"<b>الخادم:</b>\n"
            f"CPU: {cpu:.1f}%\n"
            f"RAM: {mem.percent:.1f}% ({mem.used//1024//1024:,} MB)\n"
            f"Disk: {disk.percent:.1f}%\n"
            f"Uptime: {str(uptime).split('.')[0]}\n"
            f"الإنترنت: {'✅' if check_internet() else '❌'}"
        )
        send_telegram(msg)
        print(f"[Watchdog] تقرير الصحة أُرسل ✅")
    except Exception as e:
        print(f"[Watchdog] خطأ في تقرير الصحة: {e}")

# ─── الحلقة الرئيسية ──────────────────────────────────────────────────────────
def run_watchdog():
    print("=" * 50)
    print("  Watchdog — مراقبة النظام 24/7")
    print("=" * 50)

    send_telegram(
        "🐕 <b>Watchdog يعمل!</b>\n"
        "─"*20 + "\n"
        "يراقب كل البرامج كل دقيقة\n"
        "يعيد التشغيل تلقائياً عند أي توقف\n"
        "تقرير صحة كل 6 ساعات 💪"
    )

    last_health_report = datetime.now()
    check_count = 0

    while True:
        try:
            check_count += 1
            now = datetime.now()

            # فحص كل برنامج
            for name, program in PROGRAMS.items():
                if not is_running(name):
                    print(f"[Watchdog] ⚠️  {name} متوقف — إعادة التشغيل...")
                    restart_program(name, program)
                    time.sleep(5)  # انتظر قليلاً بعد الإعادة

            # تقرير الصحة كل 6 ساعات
            hours_since = (now - last_health_report).seconds / 3600
            if hours_since >= 6:
                send_health_report()
                last_health_report = now

            # طباعة حالة كل 10 دقائق
            if check_count % 10 == 0:
                running = [n for n in PROGRAMS if is_running(n)]
                print(f"[Watchdog] {now.strftime('%H:%M')} — يعمل: {len(running)}/{len(PROGRAMS)}")

            time.sleep(60)  # فحص كل دقيقة

        except KeyboardInterrupt:
            print("\n[Watchdog] إيقاف يدوي")
            break
        except Exception as e:
            print(f"[Watchdog] خطأ: {e}")
            time.sleep(30)

if __name__ == "__main__":
    run_watchdog()
