#!/usr/bin/env python3
"""
telegram_trade_cards.py — Institutional Telegram Trade Cards
SEMI-AUTONOMOUS EXECUTION LAYER | Intelligence Only
Sends formatted trade plan cards to Telegram.
"""

import os, json, time, requests
from datetime import datetime

try:
    from logger import get_logger
    log = get_logger("telegram_trade_cards")
except ImportError:
    import logging
    log = logging.getLogger("telegram_trade_cards")
    logging.basicConfig(level=logging.INFO)

from dotenv import load_dotenv
load_dotenv("/root/.env")

TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

SENT_FILE = "/root/logs/sent_cards.json"
os.makedirs("/root/logs", exist_ok=True)


def _load_sent() -> set:
    try:
        if os.path.exists(SENT_FILE):
            with open(SENT_FILE) as f:
                return set(json.load(f))
    except Exception:
        pass
    return set()


def _save_sent(sent: set):
    try:
        with open(SENT_FILE, "w") as f:
            json.dump(list(sent), f)
    except Exception as e:
        log.error(f"Failed to save sent cards: {e}")


def send_message(text: str) -> bool:
    if not TOKEN or not CHAT_ID:
        log.warning("Telegram credentials missing")
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=15
        )
        return r.status_code == 200
    except Exception as e:
        log.error(f"Telegram send failed: {e}")
        return False


def format_card_html(plan: dict) -> str:
    """Format institutional trade card in HTML for Telegram."""
    cl = plan.get("checklist", {})

    def ck(key): return "✅" if cl.get(key) else "❌"

    exec_score = plan.get("execution_score", 0)
    exec_bar   = "█" * (exec_score // 10) + "░" * (10 - exec_score // 10)

    status_emoji = {
        "READY":   "🟢", "CREATED": "🔵",
        "ACTIVE":  "⚡", "EXPIRED": "⏰",
    }.get(plan.get("status", ""), "⚪")

    positive = "\n".join(
        f"  ✦ {f}" for f in plan.get("positive_factors", [])[:3]
    )
    risks = "\n".join(
        f"  ⚠ {f}" for f in plan.get("risk_factors", [])[:2]
    )

    card = f"""<b>{'━'*30}</b>
{status_emoji} <b>TRADE PLAN — {plan['symbol']}</b>
<b>{'━'*30}</b>

🏷 <b>Setup:</b> {plan.get('setup', 'SEPA')}
📈 <b>Type:</b> {plan['trade_type']} | {plan['direction']}
🌍 <b>Regime:</b> {plan['regime']}

<b>💰 PRICE LEVELS</b>
├ Entry:    <code>${plan['entry']:.2f}</code>
├ Stop:     <code>${plan['stop_loss']:.2f}</code>  (-${plan['risk_per_share']:.2f})
├ Target1:  <code>${plan['take_profit_1']:.2f}</code>  (2:1)
├ Target2:  <code>${plan['take_profit_2']:.2f}</code>  (3:1)
└ Target3:  <code>${plan['take_profit_3']:.2f}</code>  (5:1)

<b>📐 RISK METRICS</b>
├ Shares:   <code>{plan['position_size']:,}</code>
├ Max Loss: <code>${plan['max_loss_usd']:,.0f}</code>
├ Gain:     <code>${plan['potential_gain']:,.0f}</code>
└ R:R:      <code>{plan['risk_reward']:.1f}:1</code>

<b>📊 SCORES</b>
├ Score:     {plan.get('score', 0):.0f}/100
├ Confid:    {plan.get('confidence', 0)}/100
└ Exec:  [{exec_bar}] {exec_score}/100

<b>✅ CHECKLIST</b>
{ck('regime_ok')} Regime  {ck('liquidity_ok')} Liquidity  {ck('volume_confirmed')} Volume
{ck('atr_valid')} ATR     {ck('mtf_confirmed')} MTF        {ck('rs_strong')} RS

<b>💡 WHY</b>
{plan.get('why_this_trade', '')[:200]}

<b>✦ POSITIVES</b>
{positive}

<b>⚠️ RISKS</b>
{risks}

<b>🤖 AI:</b> <i>{plan.get('ai_summary', '')[:150]}</i>

<code>{plan['plan_id']}</code>
⏰ {plan.get('expires_at', '')[:16]}
<b>{'━'*30}</b>
⚠️ <i>INTELLIGENCE ONLY — NO AUTO EXECUTION</i>"""

    return card


def send_trade_card(plan: dict) -> bool:
    """Send a single trade card to Telegram."""
    plan_id = plan.get("plan_id", "")
    sent    = _load_sent()

    if plan_id in sent:
        log.info(f"Card {plan_id} already sent — skipping")
        return False

    card = format_card_html(plan)
    ok   = send_message(card)

    if ok:
        sent.add(plan_id)
        _save_sent(sent)
        log.info(f"Trade card sent: {plan_id}")
    else:
        log.error(f"Failed to send card: {plan_id}")

    return ok


def send_daily_summary(plans: list) -> bool:
    """Send daily trade intelligence summary."""
    if not plans:
        return send_message(
            "📊 <b>DAILY INTELLIGENCE SUMMARY</b>\n\n"
            "No trade plans generated today.\n"
            "Market conditions below threshold.\n\n"
            "⚠️ <i>Intelligence Only — No Auto Trading</i>"
        )

    ready   = [p for p in plans if p.get("status") == "READY"]
    created = [p for p in plans if p.get("status") == "CREATED"]

    top3 = sorted(plans, key=lambda x: x.get("execution_score", 0), reverse=True)[:3]
    top3_str = "\n".join(
        f"  {i+1}. {p['symbol']} | Score:{p.get('score',0):.0f} | "
        f"Exec:{p.get('execution_score',0)} | {p.get('trade_type','')}"
        for i, p in enumerate(top3)
    )

    msg = f"""📊 <b>DAILY INTELLIGENCE SUMMARY</b>
{datetime.now().strftime('%Y-%m-%d %H:%M ET')}
{'━'*28}

📋 Plans Generated: {len(plans)}
🟢 READY:   {len(ready)}
🔵 CREATED: {len(created)}

<b>🏆 TOP 3 OPPORTUNITIES</b>
{top3_str}

<b>⚡ EXECUTION READINESS</b>
{'High' if any(p.get('execution_score',0)>=80 for p in plans) else 'Moderate'}

{'━'*28}
⚠️ <i>Intelligence Only — No Auto Execution</i>"""

    return send_message(msg)


def send_watchlist_update(watchlist: dict) -> bool:
    """Send watchlist update to Telegram."""
    wl = watchlist.get("watchlist", {})
    t1 = ", ".join(wl.get("TIER_1", [])[:7])
    t2 = ", ".join(wl.get("TIER_2", [])[:5])

    msg = f"""👁 <b>WATCHLIST UPDATE</b>
{datetime.now().strftime('%H:%M ET')}
{'━'*28}

🌍 Regime: <b>{watchlist.get('regime', '?')}</b>
😱 VIX: <b>{watchlist.get('vix', 0):.1f}</b>
📡 {watchlist.get('rationale', '')}

<b>🥇 TIER 1</b>
{t1}

<b>🥈 TIER 2</b>
{t2}

{'━'*28}
⚠️ <i>Intelligence Only — No Auto Execution</i>"""

    return send_message(msg)


def process_new_plans():
    """Check for new plans and send cards for READY ones."""
    try:
        from trade_plan_generator import load_plans
        plans = load_plans()
    except ImportError:
        log.error("trade_plan_generator not found")
        return

    sent  = _load_sent()
    count = 0

    for plan_id, plan in plans.items():
        if plan_id not in sent and plan.get("status") in ("READY", "ACTIVE"):
            if plan.get("execution_score", 0) >= 70:
                ok = send_trade_card(plan)
                if ok:
                    count += 1
                    time.sleep(2)   # Rate limit

    if count > 0:
        log.info(f"Sent {count} trade cards")


# ── Test ──────────────────────────────────────────────────────
if __name__ == "__main__":
    sample_plan = {
        "plan_id":        "NVDA_20260511_test",
        "symbol":         "NVDA",
        "trade_type":     "SWING",
        "direction":      "LONG",
        "regime":         "RISK_ON",
        "setup":          "Minervini SEPA Stage 2",
        "entry":          875.50,
        "stop_loss":      851.00,
        "take_profit_1":  924.50,
        "take_profit_2":  949.00,
        "take_profit_3":  998.00,
        "risk_per_share": 24.50,
        "reward_per_share": 73.50,
        "risk_reward":    3.0,
        "position_size":  40,
        "max_loss_usd":   980,
        "potential_gain": 2940,
        "score":          87.5,
        "confidence":     82,
        "execution_score": 85,
        "checklist": {
            "regime_ok": True, "liquidity_ok": True,
            "volume_confirmed": True, "atr_valid": True,
            "mtf_confirmed": True, "rs_strong": True,
        },
        "why_this_trade":  "NVDA showing HOT setup in RISK_ON regime.",
        "positive_factors": ["Score 87.5/100", "Volume surge 1.8x", "HOT rating"],
        "risk_factors":     ["Market volatility risk"],
        "ai_summary":       "High conviction — standard sizing recommended.",
        "status":           "READY",
        "expires_at":       "2026-05-14T09:30:00",
    }
    ok = send_trade_card(sample_plan)
    print(f"Card sent: {ok}")
