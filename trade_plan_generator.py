#!/usr/bin/env python3
"""
trade_plan_generator.py — Trade Plan Generator
SEMI-AUTONOMOUS EXECUTION LAYER | Intelligence Only — No Auto Trading
Generates complete institutional trade plans for HOT/STRONG opportunities.
"""

import os, json, time
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Optional

try:
    from logger import get_logger
    log = get_logger("trade_plan_generator")
except ImportError:
    import logging
    log = logging.getLogger("trade_plan_generator")
    logging.basicConfig(level=logging.INFO)

from dotenv import load_dotenv
load_dotenv("/root/.env")

# ── Constants ─────────────────────────────────────────────────
PORTFOLIO_VALUE   = 50000   # Paper trading portfolio
DEFAULT_RISK_PCT  = 0.02    # 2% risk per trade
PLANS_FILE        = "/root/logs/trade_plans.json"
os.makedirs("/root/logs", exist_ok=True)


# ── Trade Plan Dataclass ──────────────────────────────────────
@dataclass
class TradePlan:
    symbol:          str
    plan_id:         str
    created_at:      str
    trade_type:      str        # INTRADAY / SWING
    direction:       str        # LONG / SHORT
    regime:          str
    setup:           str        # e.g. "ORB Breakout", "SEPA Trend"

    # Price levels
    entry:           float
    stop_loss:       float
    take_profit_1:   float
    take_profit_2:   float
    take_profit_3:   float

    # Risk metrics
    atr:             float
    atr_stop:        float
    risk_per_share:  float
    reward_per_share:float
    risk_reward:     float
    position_size:   int
    max_loss_usd:    float
    potential_gain:  float

    # Scoring
    score:           float
    confidence:      int        # 0-100
    execution_score: int        # 0-100

    # Checklist
    checklist:       dict

    # AI reasoning
    why_this_trade:  str
    positive_factors:list
    risk_factors:    list
    ai_summary:      str

    # Lifecycle
    status:          str        # CREATED/READY/ACTIVE/TP_HIT/SL_HIT/EXPIRED
    expires_at:      str



def get_current_price(symbol: str) -> float:
    """Get real-time price from Alpaca Paper API."""
    try:
        from config import ALPACA_API_KEY, ALPACA_SECRET_KEY
        import requests
        h = {"APCA-API-KEY-ID": ALPACA_API_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY}
        r = requests.get(f"https://data.alpaca.markets/v2/stocks/{symbol}/trades/latest",
                         headers=h, timeout=8)
        return float(r.json()["trade"]["p"])
    except Exception:
        return 0.0

def get_atr(symbol: str, period: int = 14) -> float:
    """Get ATR from Alpaca daily bars."""
    try:
        from config import ALPACA_API_KEY, ALPACA_SECRET_KEY
        import requests
        h = {"APCA-API-KEY-ID": ALPACA_API_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY}
        r = requests.get(
            f"https://paper-api.alpaca.markets/v2/stocks/{symbol}/bars?timeframe=1Day&limit={period+1}",
            headers=h, timeout=8)
        bars = r.json().get("bars", [])
        if len(bars) < 2:
            return 5.0
        trs = [max(bars[i]["h"]-bars[i]["l"],
                   abs(bars[i]["h"]-bars[i-1]["c"]),
                   abs(bars[i]["l"]-bars[i-1]["c"]))
               for i in range(1, len(bars))]
        return round(sum(trs)/len(trs), 2)
    except Exception:
        return 5.0

def generate_plan_id(symbol: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{symbol}_{ts}"


def calculate_atr_stop(entry: float, atr: float, direction: str,
                        multiplier: float = 2.0) -> float:
    if direction == "LONG":
        return round(entry - (atr * multiplier), 2)
    return round(entry + (atr * multiplier), 2)


def calculate_targets(entry: float, stop: float, direction: str,
                       rr_ratios: list = [2.0, 3.0, 5.0]) -> tuple:
    risk = abs(entry - stop)
    if direction == "LONG":
        return tuple(round(entry + risk * r, 2) for r in rr_ratios)
    return tuple(round(entry - risk * r, 2) for r in rr_ratios)


def calculate_position_size(entry: float, stop: float,
                              portfolio: float = PORTFOLIO_VALUE,
                              risk_pct: float = DEFAULT_RISK_PCT) -> dict:
    risk_per_share = abs(entry - stop)
    if risk_per_share == 0:
        return {"size": 0, "max_loss": 0, "risk_per_share": 0}

    risk_amount  = portfolio * risk_pct
    position_size = int(risk_amount / risk_per_share)
    max_loss     = round(position_size * risk_per_share, 2)

    return {
        "size":           position_size,
        "max_loss":       max_loss,
        "risk_per_share": round(risk_per_share, 2),
        "risk_amount":    round(risk_amount, 2),
    }


def build_checklist(data: dict) -> dict:
    """Build trade checklist from opportunity data."""
    regime    = data.get("regime", "NEUTRAL")
    score     = data.get("score", 0)
    volume    = data.get("volume_ratio", 1.0)
    atr       = data.get("atr", 0)
    liquidity = data.get("liquidity", "OK")
    mtf       = data.get("mtf_aligned", False)
    rs        = data.get("rs_rating", 50)

    return {
        "regime_ok":      regime in ["RISK_ON", "NEUTRAL"],
        "liquidity_ok":   liquidity not in ["CRISIS", "FROZEN"],
        "volume_confirmed": volume >= 1.2,
        "atr_valid":      atr > 0,
        "mtf_confirmed":  mtf,
        "risk_acceptable": score >= 60,
        "rs_strong":      rs >= 70,
        "score_ok":       score >= 75,
    }


def checklist_passed(checklist: dict) -> bool:
    """Returns True if critical checks pass."""
    critical = ["regime_ok", "liquidity_ok", "atr_valid", "risk_acceptable"]
    return all(checklist.get(k, False) for k in critical)


def build_reasoning(symbol: str, data: dict, plan: dict) -> dict:
    """Generate AI-style reasoning for the trade."""
    score     = data.get("score", 0)
    regime    = data.get("regime", "NEUTRAL")
    rating    = data.get("rating", "")
    trade_type = data.get("trade_type", "SWING")
    rs        = data.get("rs_rating", 50)
    volume    = data.get("volume_ratio", 1.0)

    positives = []
    risks     = []

    # Positive factors
    if score >= 90:   positives.append(f"Exceptional score: {score}/100")
    elif score >= 75: positives.append(f"Strong score: {score}/100")
    if regime == "RISK_ON":  positives.append("Market regime: RISK_ON — favorable")
    if rs >= 80:      positives.append(f"High Relative Strength: {rs}")
    if volume >= 1.5: positives.append(f"Volume surge: {volume:.1f}x average")
    if rating == "HOT": positives.append("HOT rating — top-tier setup")
    if data.get("mtf_aligned"): positives.append("Multi-timeframe alignment confirmed")
    if data.get("eps_growth"):  positives.append(f"EPS growth: {data['eps_growth']}")

    # Risk factors
    if regime == "NEUTRAL": risks.append("Neutral regime — reduced conviction")
    if volume < 1.2:        risks.append("Volume below ideal threshold")
    if rs < 70:             risks.append(f"Relative Strength below 70: {rs}")
    if data.get("vix", 20) > 25: risks.append("Elevated VIX — market volatility risk")
    if data.get("liquidity") == "TIGHTENING": risks.append("Liquidity tightening")

    why = (
        f"{symbol} showing {rating} setup in {regime} regime. "
        f"Score {score}/100 with {'strong' if rs >= 70 else 'moderate'} "
        f"relative strength ({rs}). "
        f"{'Volume confirming breakout. ' if volume >= 1.5 else ''}"
        f"Recommended as {trade_type} trade."
    )

    ai_summary = (
        f"AI ASSESSMENT: {symbol} qualifies as {trade_type} opportunity. "
        f"Setup integrity: {len(positives)} positives vs {len(risks)} risks. "
        f"{'High conviction — proceed with standard sizing.' if score >= 85 else 'Moderate conviction — consider reduced sizing.'}"
    )

    return {
        "why":      why,
        "positive": positives if positives else ["Meets minimum criteria"],
        "risks":    risks if risks else ["Standard market risk"],
        "summary":  ai_summary,
    }


def calculate_execution_score(data: dict) -> int:
    """0-100 execution readiness score."""
    score = 0
    score += min(20, int(data.get("score", 0) * 0.2))          # base score
    score += 15 if data.get("volume_ratio", 0) >= 1.5 else 8   # volume
    score += 15 if data.get("mtf_aligned", False) else 0        # MTF
    score += 15 if data.get("regime") == "RISK_ON" else 7       # regime
    score += 10 if data.get("rs_rating", 0) >= 80 else 5        # RS
    score += 10 if data.get("liquidity") == "LIQUID" else 3     # liquidity
    score += 10 if data.get("rating") == "HOT" else 5           # rating
    score += 5  if data.get("orb_break", False) else 0          # ORB
    return min(100, score)


def create_trade_plan(symbol: str, data: dict,
                       current_price: float,
                       atr: float) -> Optional[TradePlan]:
    """
    Main function — create a complete trade plan.
    Returns None if checklist fails.
    """
    data["atr"] = atr
    checklist = build_checklist(data)

    if not checklist_passed(checklist):
        log.info(f"Checklist FAILED for {symbol} — no plan created")
        return None

    direction  = "LONG"   # system is long-only (Minervini)
    trade_type = data.get("trade_type", "SWING")
    regime     = data.get("regime", "NEUTRAL")
    score      = data.get("score", 0)

    # Price levels
    entry     = round(current_price * 1.001, 2)   # slight slippage buffer
    atr_stop  = calculate_atr_stop(entry, atr, direction)
    stop_loss = round(min(atr_stop, entry * 0.97), 2)  # max 3% stop

    tp1, tp2, tp3 = calculate_targets(entry, stop_loss, direction)
    risk_per_share = round(entry - stop_loss, 2)
    reward         = round(tp2 - entry, 2)
    rr             = round(reward / risk_per_share, 2) if risk_per_share > 0 else 0

    pos = calculate_position_size(entry, stop_loss)
    reasoning = build_reasoning(symbol, data, {})
    exec_score = calculate_execution_score(data)
    confidence = min(100, int(score * 0.9 + exec_score * 0.1))

    expires = (datetime.now() + timedelta(hours=4 if trade_type == "INTRADAY" else 72)).isoformat()

    plan = TradePlan(
        symbol=symbol,
        plan_id=generate_plan_id(symbol),
        created_at=datetime.now().isoformat(),
        trade_type=trade_type,
        direction=direction,
        regime=regime,
        setup=data.get("setup", "Minervini SEPA"),
        entry=entry,
        stop_loss=stop_loss,
        take_profit_1=tp1,
        take_profit_2=tp2,
        take_profit_3=tp3,
        atr=round(atr, 2),
        atr_stop=atr_stop,
        risk_per_share=risk_per_share,
        reward_per_share=reward,
        risk_reward=rr,
        position_size=pos["size"],
        max_loss_usd=pos["max_loss"],
        potential_gain=round(pos["size"] * reward, 2),
        score=score,
        confidence=confidence,
        execution_score=exec_score,
        checklist=checklist,
        why_this_trade=reasoning["why"],
        positive_factors=reasoning["positive"],
        risk_factors=reasoning["risks"],
        ai_summary=reasoning["summary"],
        status="READY" if exec_score >= 70 else "CREATED",
        expires_at=expires,
    )

    save_plan(plan)
    log.info(f"Trade plan created: {plan.plan_id} | Score:{score} | Exec:{exec_score}")
    return plan


def save_plan(plan: TradePlan):
    """Append plan to JSON store."""
    try:
        plans = load_plans()
        plans[plan.plan_id] = asdict(plan)
        with open(PLANS_FILE, "w") as f:
            json.dump(plans, f, indent=2, default=str)
    except Exception as e:
        log.error(f"Failed to save plan: {e}", exc_info=True)


def load_plans() -> dict:
    """Load all plans from JSON store."""
    try:
        if os.path.exists(PLANS_FILE):
            with open(PLANS_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def update_plan_status(plan_id: str, status: str):
    """Update lifecycle status of a plan."""
    valid = {"CREATED", "READY", "ACTIVE", "TP_HIT", "SL_HIT", "EXPIRED"}
    if status not in valid:
        return
    plans = load_plans()
    if plan_id in plans:
        plans[plan_id]["status"] = status
        plans[plan_id]["updated_at"] = datetime.now().isoformat()
        with open(PLANS_FILE, "w") as f:
            json.dump(plans, f, indent=2, default=str)
        log.info(f"Plan {plan_id} status → {status}")


def get_active_plans() -> list:
    """Return all non-expired plans."""
    plans = load_plans()
    now   = datetime.now()
    active = []
    for pid, plan in plans.items():
        if plan["status"] in ("CREATED", "READY", "ACTIVE"):
            try:
                expires = datetime.fromisoformat(plan["expires_at"])
                if expires > now:
                    active.append(plan)
                else:
                    update_plan_status(pid, "EXPIRED")
            except Exception:
                active.append(plan)
    return sorted(active, key=lambda x: x.get("execution_score", 0), reverse=True)


def format_telegram_card(plan: dict) -> str:
    """Format institutional-style Telegram trade card."""
    cl = plan.get("checklist", {})
    checks = {
        "Regime":    "✅" if cl.get("regime_ok") else "❌",
        "Liquidity": "✅" if cl.get("liquidity_ok") else "❌",
        "Volume":    "✅" if cl.get("volume_confirmed") else "❌",
        "ATR":       "✅" if cl.get("atr_valid") else "❌",
        "MTF":       "✅" if cl.get("mtf_confirmed") else "❌",
        "RS":        "✅" if cl.get("rs_strong") else "❌",
    }
    pos_factors = "\n".join(f"  ✦ {f}" for f in plan.get("positive_factors", [])[:3])
    risk_factors = "\n".join(f"  ⚠ {f}" for f in plan.get("risk_factors", [])[:2])

    exec_bar = "█" * (plan.get("execution_score", 0) // 10) + "░" * (10 - plan.get("execution_score", 0) // 10)

    msg = f"""
╔══════════════════════════════╗
║  📊 TRADE PLAN — {plan['symbol']:6s}      ║
╚══════════════════════════════╝

🏷️ Setup:    {plan.get('setup','SEPA')}
📈 Type:     {plan['trade_type']} | {plan['direction']}
🌍 Regime:   {plan['regime']}

💰 PRICE LEVELS
├ Entry:     ${plan['entry']:.2f}
├ Stop Loss: ${plan['stop_loss']:.2f}  (-{plan['risk_per_share']:.2f})
├ Target 1:  ${plan['take_profit_1']:.2f}  (R:R 2:1)
├ Target 2:  ${plan['take_profit_2']:.2f}  (R:R 3:1)
└ Target 3:  ${plan['take_profit_3']:.2f}  (R:R 5:1)

📐 RISK METRICS
├ Position:  {plan['position_size']} shares
├ Max Loss:  ${plan['max_loss_usd']:.0f}
├ Potential: ${plan['potential_gain']:.0f}
└ R:R Ratio: {plan['risk_reward']:.1f}:1

📊 SCORES
├ Score:     {plan['score']:.0f}/100
├ Confidence:{plan['confidence']}/100
└ Execution: [{exec_bar}] {plan['execution_score']}/100

✅ CHECKLIST
{chr(10).join(f"  {v} {k}" for k,v in checks.items())}

💡 WHY THIS TRADE
{plan.get('why_this_trade','')}

✦ POSITIVES
{pos_factors}

⚠️ RISKS
{risk_factors}

🤖 AI: {plan.get('ai_summary','')}

🆔 {plan['plan_id']}
⏰ Expires: {plan.get('expires_at','')[:16]}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ INTELLIGENCE ONLY — NO AUTO EXECUTION
"""
    return msg.strip()


# ── Quick test ────────────────────────────────────────────────
if __name__ == "__main__":
    sample_data = {
        "regime":       "RISK_ON",
        "score":        87.5,
        "rating":       "HOT",
        "trade_type":   "SWING",
        "volume_ratio": 1.8,
        "mtf_aligned":  True,
        "rs_rating":    85,
        "liquidity":    "LIQUID",
        "vix":          17.2,
        "setup":        "Minervini SEPA Stage 2",
    }

    plan = create_trade_plan("NVDA", sample_data, current_price=get_current_price('NVDA'), atr=get_atr('NVDA'))
    if plan:
        print("✅ Plan created:")
        card = format_telegram_card(asdict(plan))
        print(card)
    else:
        print("❌ Checklist failed")
