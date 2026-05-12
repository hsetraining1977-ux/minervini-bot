#!/usr/bin/env python3
"""
Telegram Command Center
========================
Intelligence & Alerts — No Auto Trading
"""

import asyncio
import os
import sys
import psutil
from datetime import datetime
import yfinance as yf

sys.path.insert(0, '/root')
from dotenv import load_dotenv
load_dotenv('/root/.env')

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")

# ===== Helpers =====
def fmt(text): return f"<pre>{text}</pre>"

def get_spy_data():
    try:
        spy = yf.Ticker("SPY")
        hist = spy.history(period="1d", interval="5m")
        vix  = yf.Ticker("^VIX").history(period="1d")
        spy_price = float(hist["Close"].iloc[-1])
        spy_open  = float(hist["Open"].iloc[0])
        spy_chg   = (spy_price - spy_open) / spy_open * 100
        vix_val   = float(vix["Close"].iloc[-1]) if not vix.empty else 0

        tp  = (hist["High"] + hist["Low"] + hist["Close"]) / 3
        tpv = tp * hist["Volume"]
        vwap = float((tpv.cumsum() / hist["Volume"].cumsum()).iloc[-1])
        above_vwap = spy_price > vwap

        return {"price": spy_price, "change": spy_chg, "vwap": vwap,
                "above_vwap": above_vwap, "vix": vix_val}
    except:
        return {}

def check_process(name):
    for p in psutil.process_iter(['name', 'cmdline']):
        try:
            cmd = " ".join(p.info['cmdline'] or [])
            if name in cmd:
                return True
        except:
            pass
    return False

# ===========================================================
# COMMANDS
# ===========================================================
async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = """🤖 <b>Minervini Bot Commands</b>

📊 <b>Market</b>
/market — Market regime + VIX + SPY
/spy    — SPY status + VWAP

🔍 <b>Scanner</b>
/scan   — Run intraday scan
/hot    — HOT opportunities
/strong — STRONG opportunities

⚙️ <b>System</b>
/status — Services status
/help   — This menu

⚠️ Intelligence only — No auto trading"""
    await update.message.reply_text(msg, parse_mode="HTML")

async def cmd_market(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Fetching market data...", parse_mode="HTML")
    try:
        d = get_spy_data()
        vix = d.get("vix", 0)
        spy_chg = d.get("change", 0)
        above = d.get("above_vwap", False)

        if not above and spy_chg < -0.3 and vix > 22:
            regime = "🔴 RISK_OFF"
        elif above and spy_chg > 0.3 and vix < 20:
            regime = "🟢 RISK_ON"
        else:
            regime = "🟡 NEUTRAL"

        msg = f"""🌍 <b>Market Intelligence</b>
{datetime.now().strftime('%Y-%m-%d %H:%M ET')}

📊 <b>SPY:</b> ${d.get('price', 0):.2f} ({spy_chg:+.2f}%)
📈 <b>VWAP:</b> ${d.get('vwap', 0):.2f} {'✅ Above' if above else '❌ Below'}
😱 <b>VIX:</b> {vix:.1f} {'🟢 Low' if vix < 18 else '🟡 Normal' if vix < 25 else '🔴 High'}
🎯 <b>Regime:</b> {regime}"""
        await update.message.reply_text(msg, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}", parse_mode="HTML")

async def cmd_spy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        d = get_spy_data()
        msg = f"""📈 <b>SPY Status</b>

💰 Price: <b>${d.get('price',0):.2f}</b>
📊 Change: <b>{d.get('change',0):+.2f}%</b>
〽️ VWAP: <b>${d.get('vwap',0):.2f}</b>
🎯 Position: <b>{'✅ Above VWAP' if d.get('above_vwap') else '❌ Below VWAP'}</b>
😱 VIX: <b>{d.get('vix',0):.1f}</b>"""
        await update.message.reply_text(msg, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def cmd_scan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Running intraday scan... (30-60 seconds)", parse_mode="HTML")
    try:
        from intraday_engine import scan_intraday_opportunities
        symbols = ["NVDA","AMD","TSLA","AAPL","META","MSFT","AVGO","SMCI","GOOGL","AMZN"]
        results = scan_intraday_opportunities(symbols)

        hot    = [r for r in results if r["rating"] == "HOT"]
        strong = [r for r in results if r["rating"] == "STRONG"]
        watch  = [r for r in results if r["rating"] == "WATCH"]

        msg = f"""🔍 <b>Intraday Scan Results</b>
{datetime.now().strftime('%H:%M ET')}

🔥 HOT: {len(hot)} | 💪 STRONG: {len(strong)} | 👀 WATCH: {len(watch)}
"""
        for r in (hot + strong)[:5]:
            emoji = "🔥" if r["rating"] == "HOT" else "💪"
            msg += f"\n{emoji} <b>{r['symbol']}</b> | Score: {r['score']} | {r['rating']}"
            msg += f"\n   Gap:{r['gap_pct']:+.1f}% Mom:{r['momentum_pct']:+.1f}% ATR:{r.get('atr',0):.2f}"
            msg += f"\n   SL:{r.get('stop_loss',0):.2f} T1:{r.get('target_1',0):.2f}\n"

        await update.message.reply_text(msg, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Scan error: {e}")

async def cmd_hot(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 Scanning for HOT opportunities...", parse_mode="HTML")
    try:
        from intraday_engine import scan_intraday_opportunities
        symbols = ["NVDA","AMD","TSLA","AAPL","META","MSFT","AVGO","SMCI","GOOGL","AMZN"]
        results = scan_intraday_opportunities(symbols)
        hot = [r for r in results if r["rating"] == "HOT"]

        if not hot:
            await update.message.reply_text("❌ No HOT opportunities right now.")
            return

        msg = f"🔥 <b>HOT Opportunities ({len(hot)})</b>\n\n"
        for r in hot:
            msg += f"🔥 <b>{r['symbol']}</b> — Score: {r['score']}\n"
            msg += f"   📈 Gap: {r['gap_pct']:+.1f}% | Mom: {r['momentum_pct']:+.1f}%\n"
            msg += f"   🎯 SL: ${r.get('stop_loss',0):.2f} | T1: ${r.get('target_1',0):.2f}\n"
            msg += f"   {'🚀 ORB' if r.get('orb_breakout') else ''} {'✅ MTF' if r.get('mtf_alignment') else ''}\n\n"

        await update.message.reply_text(msg, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def cmd_strong(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💪 Scanning for STRONG opportunities...", parse_mode="HTML")
    try:
        from intraday_engine import scan_intraday_opportunities
        symbols = ["NVDA","AMD","TSLA","AAPL","META","MSFT","AVGO","SMCI","GOOGL","AMZN"]
        results = scan_intraday_opportunities(symbols)
        strong = [r for r in results if r["rating"] == "STRONG"]

        if not strong:
            await update.message.reply_text("❌ No STRONG opportunities right now.")
            return

        msg = f"💪 <b>STRONG Opportunities ({len(strong)})</b>\n\n"
        for r in strong:
            msg += f"💪 <b>{r['symbol']}</b> — Score: {r['score']}\n"
            msg += f"   📈 Gap: {r['gap_pct']:+.1f}% | Mom: {r['momentum_pct']:+.1f}%\n"
            msg += f"   🎯 SL: ${r.get('stop_loss',0):.2f} | T1: ${r.get('target_1',0):.2f}\n\n"

        await update.message.reply_text(msg, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    services = {
        "auto_monitor":       "Trading Core",
        "ai_layer":           "Claude AI",
        "event_awareness":    "Event Guard",
        "institutional_layer":"Institutional",
        "streamlit":          "Dashboard",
        "intraday_engine":    "Intraday Scanner",
    }
    msg = f"⚙️ <b>System Status</b>\n{datetime.now().strftime('%H:%M ET')}\n\n"
    for proc, name in services.items():
        status = "✅ Running" if check_process(proc) else "❌ Stopped"
        msg += f"{status} — {name}\n"

    try:
        import psutil
        cpu  = psutil.cpu_percent(interval=1)
        ram  = psutil.virtual_memory().percent
        disk = psutil.disk_usage('/').percent
        msg += f"\n💻 CPU: {cpu}% | RAM: {ram}% | Disk: {disk}%"
    except: pass

    await update.message.reply_text(msg, parse_mode="HTML")

# ===========================================================
# MAIN
# ===========================================================
def main():
    if not TOKEN:
        print("[TG] ERROR: TELEGRAM_BOT_TOKEN not found in .env")
        return

    print(f"[TG] 🚀 Starting Telegram Command Center...")
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("help",   cmd_help))
    app.add_handler(CommandHandler("start",  cmd_help))
    app.add_handler(CommandHandler("market", cmd_market))
    app.add_handler(CommandHandler("spy",    cmd_spy))
    app.add_handler(CommandHandler("scan",   cmd_scan))
    app.add_handler(CommandHandler("hot",    cmd_hot))
    app.add_handler(CommandHandler("strong", cmd_strong))
    app.add_handler(CommandHandler("status", cmd_status))

    print("[TG] ✅ Bot running — Waiting for commands...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
