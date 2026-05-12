"""
ai_trade_review.py
AI SELF REVIEW ENGINE
Minervini Bot — PAPER TRADING ONLY
Reviews every closed trade with AI analysis.
"""

import json, os, datetime, logging, requests
import sys
sys.path.insert(0, "/root")

log = logging.getLogger("ai_review")
DATA_DIR   = "/root/logs"
PAPER_ONLY = True

def _load(path, default={}):
    try:
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    except Exception:
        pass
    return default

def _save(path, data):
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        log.error(f"Save: {e}")

def _tg(msg: str):
    try:
        from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"},
            timeout=10
        )
    except Exception:
        pass

# ── Rule-based AI Review (no external API needed) ────────────────────────────
def review_trade(trade: dict) -> dict:
    """
    AI self-review of a closed trade.
    Returns structured review with scores and lessons.
    PAPER TRADING ONLY.
    """
    symbol      = trade.get("symbol", "?")
    entry       = float(trade.get("entry_price", 0))
    exit_price  = float(trade.get("exit_price", 0))
    pnl         = float(trade.get("pnl", 0))
    regime      = str(trade.get("market_regime", "NEUTRAL")).upper()
    setup       = trade.get("setup_type", "SWING")
    exit_reason = trade.get("exit_reason", "MANUAL")
    duration    = int(trade.get("duration_mins", 0))
    mfe         = float(trade.get("mfe", 0))
    mae         = float(trade.get("mae", 0))
    exec_score  = float(trade.get("execution_score", 0))
    efficiency  = trade.get("efficiency_grade", "C")

    review      = {}
    score       = 50
    lessons     = []
    positives   = []
    negatives   = []

    # ── Entry Analysis ────────────────────────────────────────────────────────
    if exec_score >= 85:
        positives.append(f"Strong execution score {exec_score:.0f}/100")
        score += 10
    elif exec_score >= 70:
        positives.append(f"Adequate score {exec_score:.0f}/100")
        score += 5
    else:
        negatives.append(f"Low execution score {exec_score:.0f}/100 — should have waited")
        lessons.append("Wait for higher execution score before entry")
        score -= 10

    # ── Regime Analysis ───────────────────────────────────────────────────────
    if "RISK_ON" in regime and pnl > 0:
        positives.append("Correct: entered LONG in RISK_ON regime")
        score += 8
    elif "RISK_OFF" in regime and pnl < 0:
        negatives.append("Poor: traded in RISK_OFF regime — should have avoided")
        lessons.append("Avoid entries in RISK_OFF regime")
        score -= 12
    elif "NEUTRAL" in regime:
        review["regime_note"] = "NEUTRAL regime — moderate conditions"

    # ── Exit Analysis ─────────────────────────────────────────────────────────
    if exit_reason in ("TP2_HIT", "TP1_HIT"):
        positives.append(f"Excellent exit: {exit_reason}")
        score += 15
    elif exit_reason == "TRAILING_STOP":
        positives.append("Good: Trailing stop captured trend properly")
        score += 8
    elif exit_reason == "SL_HIT":
        negatives.append("Stop loss hit — review entry quality")
        lessons.append("Review if setup was truly valid at entry")
        score -= 5
    elif exit_reason == "FAKE_BREAKOUT":
        negatives.append("Fake breakout — need better confirmation")
        lessons.append("Add volume confirmation before breakout entries")
        score -= 8
    elif exit_reason == "HEALTH_EXIT":
        positives.append("Proactive: exited on health degradation")
        score += 5

    # ── MFE/MAE Efficiency ────────────────────────────────────────────────────
    if mfe > 0 and pnl > 0:
        capture_ratio = pnl / mfe
        if capture_ratio > 0.7:
            positives.append(f"Excellent capture ratio: {capture_ratio:.0%} of max gain")
            score += 10
        elif capture_ratio > 0.4:
            positives.append(f"Good capture ratio: {capture_ratio:.0%}")
            score += 5
        else:
            negatives.append(f"Poor capture: only {capture_ratio:.0%} of max gain realized")
            lessons.append("Exit strategy needs improvement — left too much on table or exited too early")
            score -= 5

    if mae < 0 and entry > 0:
        dd_pct = abs(mae) / (entry * trade.get("shares", 1)) * 100
        if dd_pct > 3:
            negatives.append(f"High adverse excursion: {dd_pct:.1f}%")
            lessons.append("Position experienced significant drawdown — tighter initial stop?")

    # ── Duration Analysis ─────────────────────────────────────────────────────
    if duration > 0:
        if duration < 30 and pnl > 0:
            positives.append(f"Quick profitable trade: {duration}m")
        elif duration > 480 and pnl < 0:
            negatives.append(f"Held losing trade too long: {duration}m")
            lessons.append("Cut losses faster — don't hold losers over 8 hours")

    # ── Volume / Timing (inferred) ────────────────────────────────────────────
    entry_hour = 0
    try:
        entered_at = trade.get("entered_at","")
        if entered_at:
            entry_hour = int(entered_at[11:13])  # UTC hour
    except Exception:
        pass

    if 13 <= entry_hour <= 14:   # 9:30-10:30 AM ET
        positives.append("Good timing: entered in opening hour (high volume)")
        score += 5
    elif 19 <= entry_hour <= 20: # 3-4 PM ET
        negatives.append("Late entry: near close reduces risk/reward")
        lessons.append("Avoid entries in final hour of trading")

    # ── PnL Verdict ───────────────────────────────────────────────────────────
    if pnl > 0:
        verdict = "WIN"
        summary = f"Profitable trade +${pnl:.2f} in {setup} setup during {regime}"
    else:
        verdict = "LOSS"
        summary = f"Loss of ${abs(pnl):.2f} — review entry conditions and exit timing"

    # ── Final Score ───────────────────────────────────────────────────────────
    score = max(0, min(100, score))

    if score >= 80:   quality = "EXCELLENT"
    elif score >= 65: quality = "GOOD"
    elif score >= 50: quality = "AVERAGE"
    elif score >= 35: quality = "POOR"
    else:             quality = "VERY_POOR"

    # ── Lesson Dedup ──────────────────────────────────────────────────────────
    lessons = list(dict.fromkeys(lessons))[:3]   # max 3 unique lessons

    result = {
        "trade_id":          trade.get("trade_id",""),
        "symbol":            symbol,
        "verdict":           verdict,
        "pnl":               pnl,
        "confidence_score":  score,
        "execution_quality": quality,
        "entry_assessment":  "GOOD" if exec_score >= 75 else "MARGINAL",
        "exit_assessment":   "GOOD" if exit_reason in ("TP2_HIT","TP1_HIT","TRAILING_STOP") else "AVERAGE",
        "regime_suitable":   "RISK_OFF" not in regime,
        "summary":           summary,
        "positives":         positives[:4],
        "negatives":         negatives[:4],
        "lessons_learned":   lessons,
        "reviewed_at":       datetime.datetime.now().isoformat(),
        "paper_only":        True,
    }

    # Save review
    reviews = _load(f"{DATA_DIR}/trade_reviews.json", {})
    reviews[trade.get("trade_id", f"review_{int(datetime.datetime.now().timestamp())}")] = result
    _save(f"{DATA_DIR}/trade_reviews.json", reviews)

    log.info(f"[{symbol}] Review: {quality} ({score}/100) | {verdict} | Lessons: {len(lessons)}")
    return result

def send_trade_review_telegram(trade: dict, review: dict):
    """Send trade review to Telegram."""
    symbol  = trade.get("symbol","?")
    pnl     = float(trade.get("pnl", 0))
    verdict = review.get("verdict","?")
    score   = review.get("confidence_score", 0)
    quality = review.get("execution_quality","?")
    icon    = "✅" if pnl > 0 else "❌"
    lessons = review.get("lessons_learned", [])

    positives_text = "\n".join(f"  ✦ {p}" for p in review.get("positives",[])[:2])
    negatives_text = "\n".join(f"  ⚠️ {n}" for n in review.get("negatives",[])[:2])
    lessons_text   = "\n".join(f"  📚 {l}" for l in lessons[:2])

    msg = (
        f"{icon} *TRADE REVIEW — PAPER*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 `{symbol}` | {verdict} | `${pnl:+.2f}`\n"
        f"🎯 Score: `{score}/100` | Quality: `{quality}`\n"
        f"🚪 Exit: `{trade.get('exit_reason','?')}`\n"
        + (f"\n✅ Positives:\n{positives_text}\n" if positives_text else "")
        + (f"\n⚠️ Issues:\n{negatives_text}\n" if negatives_text else "")
        + (f"\n📚 Lessons:\n{lessons_text}\n" if lessons_text else "")
        + f"\n⚠️ PAPER TRADING ONLY"
    )
    _tg(msg)

# ── Daily Telegram Report ─────────────────────────────────────────────────────
def send_daily_report():
    """Send comprehensive daily performance report to Telegram."""
    from trade_analytics import get_analytics
    analytics = get_analytics()
    heat      = _load(f"{DATA_DIR}/portfolio_heat.json", {})
    mi        = _load(f"{DATA_DIR}/market_intelligence.json", {})
    reviews   = _load(f"{DATA_DIR}/trade_reviews.json", {})

    today     = datetime.date.today().isoformat()
    daily_pnl = analytics.get("daily_pnl", {}).get(today, 0)
    total_pnl = analytics.get("total_pnl", 0)
    win_rate  = analytics.get("win_rate", 0)
    pf        = analytics.get("profit_factor", 0)
    total     = analytics.get("total_trades", 0)
    regime    = mi.get("regime", mi.get("market_regime","NEUTRAL"))
    heat_pct  = heat.get("portfolio_heat_pct", 0)
    positions = heat.get("position_count", 0)

    # Best and worst today
    today_trades = [
        t for t in reviews.values()
        if str(t.get("reviewed_at",""))[:10] == today
    ]
    best  = max(today_trades, key=lambda x: x.get("pnl",0), default=None)
    worst = min(today_trades, key=lambda x: x.get("pnl",0), default=None)

    # AI summary
    lessons_all = []
    for r in today_trades:
        lessons_all.extend(r.get("lessons_learned",[]))
    top_lesson = lessons_all[0] if lessons_all else "No lessons today — keep trading!"

    msg = (
        f"📊 *DAILY PERFORMANCE REPORT — PAPER*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 {today}\n\n"
        f"💰 Today PnL:  `${daily_pnl:+.2f}`\n"
        f"📈 Total PnL:  `${total_pnl:+.2f}`\n"
        f"🎯 Win Rate:   `{win_rate:.1f}%`\n"
        f"⚖️ Prof Factor:`{pf:.2f}`\n"
        f"📊 Total Trades:`{total}`\n\n"
        f"🏛️ Regime: `{regime}`\n"
        f"🌡️ Heat:   `{heat_pct:.1f}%`\n"
        f"📌 Positions: `{positions}`\n\n"
        + (f"🏆 Best: `{best['symbol']}` `${best['pnl']:+.2f}`\n" if best else "")
        + (f"💔 Worst: `{worst['symbol']}` `${worst['pnl']:+.2f}`\n" if worst else "")
        + f"\n🤖 AI Lesson:\n_{top_lesson}_\n\n"
        f"⚠️ PAPER TRADING ONLY"
    )
    _tg(msg)
    log.info("Daily report sent to Telegram")

if __name__ == "__main__":
    send_daily_report()
