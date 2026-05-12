#!/usr/bin/env python3
"""
daily_review.py — Daily AI Performance Review
PAPER TRADING ONLY
Generates end-of-day review: wins, losses, lessons, calibration.
"""

import os, json, requests
from datetime import datetime, timedelta

try:
    from logger import get_logger
    log = get_logger("daily_review")
except ImportError:
    import logging
    log = logging.getLogger("daily_review")
    logging.basicConfig(level=logging.INFO)

from dotenv import load_dotenv
load_dotenv("/root/.env")

TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

TRADES_FILE      = "/root/logs/paper_trades.json"
PERFORMANCE_FILE = "/root/logs/paper_performance.json"
REVIEW_FILE      = "/root/logs/daily_reviews.json"
ANTHROPIC_KEY    = os.getenv("ANTHROPIC_API_KEY", "")


def send_telegram(msg: str):
    if not TOKEN or not CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": msg,
                  "parse_mode": "HTML", "disable_web_page_preview": True},
            timeout=15
        )
    except Exception as e:
        log.error(f"Telegram failed: {e}")


def load_json(path: str) -> dict:
    try:
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def get_todays_trades() -> list:
    """Get all trades closed today."""
    trades  = load_json(TRADES_FILE)
    today   = datetime.now().strftime("%Y-%m-%d")
    result  = []
    for t in trades.values():
        exit_time = t.get("exit_time", "")
        if exit_time and exit_time.startswith(today):
            result.append(t)
    return result


def calculate_daily_stats(trades: list) -> dict:
    """Calculate daily performance statistics."""
    if not trades:
        return {"trades": 0, "wins": 0, "losses": 0, "pnl": 0, "win_rate": 0}

    wins   = [t for t in trades if t.get("realized_pnl", 0) > 0]
    losses = [t for t in trades if t.get("realized_pnl", 0) <= 0]
    total_pnl = sum(t.get("realized_pnl", 0) for t in trades)

    win_pnl  = sum(t.get("realized_pnl", 0) for t in wins)
    loss_pnl = abs(sum(t.get("realized_pnl", 0) for t in losses))

    profit_factor = round(win_pnl / loss_pnl, 2) if loss_pnl > 0 else float("inf")

    rr_ratios = []
    for t in trades:
        risk  = t.get("max_risk_usd", 1)
        pnl   = t.get("realized_pnl", 0)
        if risk > 0:
            rr_ratios.append(pnl / risk)

    avg_rr = round(sum(rr_ratios) / len(rr_ratios), 2) if rr_ratios else 0

    return {
        "trades":        len(trades),
        "wins":          len(wins),
        "losses":        len(losses),
        "pnl":           round(total_pnl, 2),
        "win_rate":      round(len(wins) / len(trades) * 100, 1) if trades else 0,
        "profit_factor": profit_factor,
        "avg_rr":        avg_rr,
        "best_trade":    max(trades, key=lambda x: x.get("realized_pnl", 0),
                             default=None),
        "worst_trade":   min(trades, key=lambda x: x.get("realized_pnl", 0),
                             default=None),
    }


def generate_ai_review(stats: dict, trades: list, perf: dict) -> str:
    """Generate AI review using Claude API."""
    if not ANTHROPIC_KEY:
        return _generate_rule_based_review(stats, trades, perf)

    try:
        trades_summary = json.dumps([{
            "symbol": t["symbol"],
            "pnl":    t.get("realized_pnl", 0),
            "reason": t.get("exit_reason", ""),
            "regime": t.get("regime", ""),
            "setup":  t.get("setup", ""),
            "exec":   t.get("execution_score", 0),
        } for t in trades], indent=2)

        prompt = f"""You are an institutional trading coach reviewing paper trading performance.

Today's Stats:
- Trades: {stats['trades']}
- Win Rate: {stats['win_rate']}%
- P&L: ${stats['pnl']:+.2f}
- Profit Factor: {stats['profit_factor']}
- Avg R:R: {stats['avg_rr']}

Today's Trades:
{trades_summary}

Overall Performance:
- Total Trades: {perf.get('total_trades', 0)}
- Overall Win Rate: {round(perf.get('wins',0)/max(perf.get('total_trades',1),1)*100,1)}%
- Total P&L: ${perf.get('total_pnl', 0):+.2f}

Provide a concise institutional trading review covering:
1. Why we won (if applicable)
2. Why we lost (if applicable)
3. Best setups today
4. Worst setups today
5. Is the system disciplined?
6. Execution quality assessment
7. Recommendations for tomorrow

Be direct, specific, and institutional in tone. Max 400 words."""

        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key":         ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01",
                "content-type":      "application/json",
            },
            json={
                "model":      "claude-sonnet-4-20250514",
                "max_tokens": 600,
                "messages":   [{"role": "user", "content": prompt}],
            },
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            return data["content"][0]["text"]

    except Exception as e:
        log.error(f"AI review failed: {e}")

    return _generate_rule_based_review(stats, trades, perf)


def _generate_rule_based_review(stats: dict, trades: list, perf: dict) -> str:
    """Fallback rule-based review."""
    today = datetime.now().strftime("%Y-%m-%d")
    wr    = stats.get("win_rate", 0)
    pnl   = stats.get("pnl", 0)
    pf    = stats.get("profit_factor", 0)

    # Discipline check
    disciplined = all(
        t.get("execution_score", 0) >= 85 for t in trades
    ) if trades else True

    review = f"""DAILY PAPER TRADING REVIEW — {today}
{'='*40}

PERFORMANCE SUMMARY:
Trades: {stats['trades']} | Wins: {stats['wins']} | Losses: {stats['losses']}
Win Rate: {wr:.1f}% | P&L: ${pnl:+.2f}
Profit Factor: {pf} | Avg R:R: {stats['avg_rr']}

SYSTEM DISCIPLINE: {'✅ DISCIPLINED' if disciplined else '⚠️ REVIEW NEEDED'}
{'All entries met minimum 85 exec score.' if disciplined else 'Some entries below threshold — review filters.'}

"""
    # Best trade
    best = stats.get("best_trade")
    if best:
        review += f"BEST SETUP: {best['symbol']} | ${best.get('realized_pnl',0):+.2f}\n"
        review += f"Setup: {best.get('setup','N/A')} | Regime: {best.get('regime','N/A')}\n\n"

    # Worst trade
    worst = stats.get("worst_trade")
    if worst and worst.get("realized_pnl", 0) < 0:
        review += f"WORST SETUP: {worst['symbol']} | ${worst.get('realized_pnl',0):+.2f}\n"
        review += f"Lesson: {'Volume or regime misaligned' if worst.get('exit_reason') == 'SL_HIT' else 'Time-based exit'}\n\n"

    # Assessment
    if wr >= 60 and pnl > 0:
        review += "ASSESSMENT: Strong performance. System is working. Maintain current filters.\n"
    elif wr >= 40:
        review += "ASSESSMENT: Mixed results. Review entry timing and regime alignment.\n"
    else:
        review += "ASSESSMENT: Below expectations. Tighten entry criteria. Raise exec score threshold.\n"

    # Cumulative
    total_pnl = perf.get("total_pnl", 0)
    total_wr  = round(perf.get("wins", 0) / max(perf.get("total_trades", 1), 1) * 100, 1)
    review += f"\nCUMULATIVE: {perf.get('total_trades',0)} trades | {total_wr}% WR | ${total_pnl:+.2f} PnL\n"
    review += "\n⚠️ PAPER TRADING ONLY — No Real Money"

    return review


def save_review(review: str, stats: dict):
    """Save daily review to file."""
    reviews = load_json(REVIEW_FILE) or {}
    today   = datetime.now().strftime("%Y-%m-%d")
    reviews[today] = {
        "timestamp": datetime.now().isoformat(),
        "stats":     stats,
        "review":    review,
    }
    try:
        with open(REVIEW_FILE, "w") as f:
            json.dump(reviews, f, indent=2, default=str)
    except Exception as e:
        log.error(f"Save review failed: {e}")


def run_daily_review():
    """Run and send the daily review."""
    log.info("Running daily paper trading review...")

    today_trades = get_todays_trades()
    stats        = calculate_daily_stats(today_trades)
    perf         = load_json(PERFORMANCE_FILE)

    ai_review = generate_ai_review(stats, today_trades, perf)
    save_review(ai_review, stats)

    # Format for Telegram
    wr_emoji = "🏆" if stats["win_rate"] >= 60 else "⚠️" if stats["win_rate"] >= 40 else "🔴"

    msg = f"""📊 <b>DAILY PAPER TRADING REVIEW</b>
{datetime.now().strftime('%Y-%m-%d')}
{'━'*30}

{wr_emoji} <b>TODAY'S RESULTS</b>
Trades:   {stats['trades']}
Wins:     {stats['wins']} | Losses: {stats['losses']}
Win Rate: {stats['win_rate']:.1f}%
P&L:      <b>${stats['pnl']:+.2f}</b>
Prof.Fac: {stats['profit_factor']}
Avg R:R:  {stats['avg_rr']}

<b>📈 CUMULATIVE</b>
Total:    {perf.get('total_trades',0)} trades
Win Rate: {round(perf.get('wins',0)/max(perf.get('total_trades',1),1)*100,1)}%
Total P&L:<b>${perf.get('total_pnl',0):+.2f}</b>

<b>🤖 AI REVIEW</b>
<i>{ai_review[:600]}...</i>

{'━'*30}
⚠️ <i>PAPER TRADING ONLY</i>"""

    send_telegram(msg)
    log.info(f"Daily review sent: {stats['trades']} trades, ${stats['pnl']:+.2f} PnL")
    return stats


if __name__ == "__main__":
    stats = run_daily_review()
    print(f"\n✅ Review complete")
    print(f"Trades: {stats['trades']} | Win Rate: {stats['win_rate']}% | P&L: ${stats['pnl']:+.2f}")
