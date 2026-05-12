#!/usr/bin/env python3
"""
morning_brief.py — Institutional Morning Briefing
INSTITUTIONAL MARKET INTELLIGENCE LAYER
Sends comprehensive morning brief to Telegram at market open.
"""

import os, json, time, requests
from datetime import datetime

try:
    from logger import get_logger
    log = get_logger("morning_brief")
except ImportError:
    import logging
    log = logging.getLogger("morning_brief")
    logging.basicConfig(level=logging.INFO)

from dotenv import load_dotenv
load_dotenv("/root/.env")

TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


def send(msg: str) -> bool:
    if not TOKEN or not CHAT_ID:
        log.warning("Telegram credentials missing")
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": msg,
                  "parse_mode": "HTML", "disable_web_page_preview": True},
            timeout=15
        )
        return r.status_code == 200
    except Exception as e:
        log.error(f"Send failed: {e}")
        return False


def load_json(path: str) -> dict:
    try:
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def build_morning_brief() -> str:
    """Build comprehensive institutional morning brief."""
    intel    = load_json("/root/logs/market_intelligence.json")
    breadth  = load_json("/root/logs/breadth_data.json")
    smart    = load_json("/root/logs/smart_money.json")
    plans    = load_json("/root/logs/trade_plans.json")
    health   = load_json("/root/logs/health_status.json")

    now = datetime.now()
    ts  = now.strftime("%Y-%m-%d %H:%M ET")

    # ── Cross-Asset ───────────────────────────────────────────
    corr    = intel.get("correlation", {})
    quality = corr.get("quality", "UNKNOWN")
    ro_pct  = corr.get("risk_on_pct", 50)
    assets  = intel.get("assets", {})

    spy_chg = assets.get("SPY", {}).get("chg_1d", 0)
    qqq_chg = assets.get("QQQ", {}).get("chg_1d", 0)
    vix_chg = assets.get("VIX", {}).get("chg_1d", 0)
    gld_chg = assets.get("GLD", {}).get("chg_1d", 0)

    quality_emoji = {
        "STRONG_RISK_ON": "🚀", "RISK_ON": "🟢",
        "NEUTRAL": "🟡",
        "RISK_OFF": "🔴", "STRONG_RISK_OFF": "🚨",
    }.get(quality, "⚪")

    # ── Breadth ───────────────────────────────────────────────
    b_score   = breadth.get("overall_score", 0)
    b_quality = breadth.get("overall_quality", "N/A")
    b_health  = breadth.get("market_health", "N/A")

    # ── Leaders ───────────────────────────────────────────────
    leaders = intel.get("top_leaders", [])[:5]
    leaders_str = "\n".join(
        f"  {i+1}. <b>{x['symbol']}</b> | RS:{x.get('rs_vs_spy',0):+.1f}% "
        f"| 3M:{x.get('chg_3m',0):+.1f}%"
        for i, x in enumerate(leaders)
    ) or "  Data loading..."

    # ── Smart Money ───────────────────────────────────────────
    flow     = smart.get("flow_bias", "UNKNOWN")
    summary  = smart.get("summary", "")
    strong_b = [x["symbol"] for x in smart.get("strong_buy", [])[:3]]
    distributing = [x["symbol"] for x in smart.get("distributing", [])[:3]]

    flow_emoji = {
        "INSTITUTIONAL_BUYING": "🟢", "INSTITUTIONAL_SELLING": "🔴",
        "MIXED_FLOW": "🟡"
    }.get(flow, "⚪")

    # ── Trade Plans ───────────────────────────────────────────
    active_plans = [p for p in plans.values()
                    if p.get("status") in ("READY", "ACTIVE")]
    active_plans.sort(key=lambda x: x.get("execution_score", 0), reverse=True)
    plans_str = "\n".join(
        f"  • <b>{p['symbol']}</b> | Exec:{p.get('execution_score',0)} "
        f"| R:R {p.get('risk_reward',0):.1f}:1 | ${p.get('entry',0):.2f}"
        for p in active_plans[:3]
    ) or "  No active plans"

    # ── AI Narrative ──────────────────────────────────────────
    narrative = intel.get("narrative", "")
    # Extract first 300 chars
    narrative_short = narrative[:350].replace("\n", " ").strip() + "..."

    # ── System Health ─────────────────────────────────────────
    sys_ok = health.get("healthy", False)
    sys_emoji = "✅" if sys_ok else "⚠️"

    # ── Sector Leaders ────────────────────────────────────────
    sectors = []
    for s, name in [("XLK","Tech"),("XLF","Fin"),("XLE","Energy"),
                     ("XLV","Health"),("XLI","Indus")]:
        chg = assets.get(s, {}).get("chg_1d", 0)
        if chg > 0.3:
            sectors.append(f"{name}(+{chg:.1f}%)")
    sectors_str = ", ".join(sectors[:3]) or "None leading"

    brief = f"""🏛️ <b>INSTITUTIONAL MORNING BRIEF</b>
{ts}
{'━'*32}

{quality_emoji} <b>REGIME: {quality}</b>
Risk-On Quality: {ro_pct:.0f}%

<b>📊 INDICES</b>
SPY: {spy_chg:+.2f}% | QQQ: {qqq_chg:+.2f}%
VIX: {vix_chg:+.2f}% | Gold: {gld_chg:+.2f}%

<b>🌡️ MARKET BREADTH</b>
Score: {b_score}/100 | {b_quality}
{b_health[:60]}

<b>📈 SECTOR LEADERS</b>
{sectors_str}

<b>🏆 INSTITUTIONAL LEADERS (RS)</b>
{leaders_str}

<b>💰 SMART MONEY FLOW</b>
{flow_emoji} {flow}
Buyers: {', '.join(strong_b) or 'None'}
Sellers: {', '.join(distributing) or 'None'}

<b>🎯 ACTIVE TRADE PLANS</b>
{plans_str}

<b>🤖 AI MARKET VIEW</b>
<i>{narrative_short}</i>

<b>⚙️ SYSTEM</b>
{sys_emoji} All services {'operational' if sys_ok else 'CHECK REQUIRED'}

{'━'*32}
⚠️ <i>Intelligence Only — No Auto Execution</i>
🤖 Minervini AI Platform v2.0"""

    return brief


def send_morning_brief():
    """Build and send the morning brief."""
    log.info("Building morning brief...")
    try:
        brief = build_morning_brief()
        ok    = send(brief)
        if ok:
            log.info("Morning brief sent successfully")
        else:
            log.error("Failed to send morning brief")
        return ok
    except Exception as e:
        log.error(f"Morning brief error: {e}", exc_info=True)
        return False


def should_send_brief() -> bool:
    """Check if we should send brief (market hours)."""
    now   = datetime.utcnow()
    # ET = UTC-4 (EDT) or UTC-5 (EST)
    et_hour = (now.hour - 4) % 24
    # Send at 9:00-9:05 AM ET on weekdays
    return now.weekday() < 5 and 9 <= et_hour < 10


def run_scheduler():
    """Run as scheduler — check every 5 min."""
    log.info("Morning Brief Scheduler started")
    sent_today = None

    while True:
        try:
            today = datetime.now().date()
            if should_send_brief() and sent_today != today:
                send_morning_brief()
                sent_today = today
        except Exception:
            log.error("Scheduler error", exc_info=True)
        time.sleep(300)  # Check every 5 min


if __name__ == "__main__":
    import sys
    if "--now" in sys.argv:
        # Force send immediately
        ok = send_morning_brief()
        print(f"Brief sent: {ok}")
    elif "--schedule" in sys.argv:
        run_scheduler()
    else:
        # Default: send now
        ok = send_morning_brief()
        print(f"Brief sent: {ok}")
