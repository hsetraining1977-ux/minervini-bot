#!/usr/bin/env python3
"""
risk_simulator.py — Position Risk Simulator
SEMI-AUTONOMOUS EXECUTION LAYER | Intelligence Only
Calculates position sizing, max loss, and expected return.
"""

import os
from dataclasses import dataclass
from typing import Optional

try:
    from logger import get_logger
    log = get_logger("risk_simulator")
except ImportError:
    import logging
    log = logging.getLogger("risk_simulator")
    logging.basicConfig(level=logging.INFO)


@dataclass
class RiskSimulation:
    # Inputs
    capital:        float
    risk_pct:       float
    entry:          float
    stop_loss:      float
    take_profit:    float

    # Calculated
    risk_amount:    float   # $ at risk
    risk_per_share: float
    position_size:  int     # shares
    position_value: float   # total $ invested
    max_loss_usd:   float
    max_loss_pct:   float
    target_gain:    float
    target_gain_pct:float
    risk_reward:    float
    breakeven_pct:  float   # % move needed to break even (commissions)
    position_pct_of_portfolio: float  # what % of portfolio is committed

    # Assessment
    sizing_ok:      bool
    warnings:       list
    recommendation: str


def simulate_risk(capital: float, risk_pct: float,
                   entry: float, stop_loss: float,
                   take_profit: float,
                   commission_per_share: float = 0.005) -> RiskSimulation:
    """
    Full position risk simulation.

    Args:
        capital:     Total portfolio capital
        risk_pct:    Risk per trade as decimal (e.g. 0.02 = 2%)
        entry:       Entry price
        stop_loss:   Stop loss price
        take_profit: Take profit price
        commission_per_share: Estimated commission cost
    """
    warnings = []

    risk_amount    = capital * risk_pct
    risk_per_share = abs(entry - stop_loss)

    if risk_per_share == 0:
        return None

    position_size  = int(risk_amount / risk_per_share)
    position_value = round(position_size * entry, 2)
    max_loss_usd   = round(position_size * risk_per_share, 2)
    max_loss_pct   = round((max_loss_usd / capital) * 100, 2)

    reward_per_share = abs(take_profit - entry)
    target_gain      = round(position_size * reward_per_share, 2)
    target_gain_pct  = round((target_gain / capital) * 100, 2)

    rr = round(reward_per_share / risk_per_share, 2) if risk_per_share > 0 else 0

    # Commissions impact
    total_commission = position_size * commission_per_share * 2  # entry + exit
    breakeven_pct    = round((total_commission / position_value) * 100, 4)

    position_pct = round((position_value / capital) * 100, 1)

    # Warnings
    if risk_pct > 0.03:
        warnings.append(f"⚠️ Risk {risk_pct*100:.0f}% exceeds recommended 2% maximum")
    if position_pct > 25:
        warnings.append(f"⚠️ Position is {position_pct}% of portfolio — consider reducing")
    if rr < 2.0:
        warnings.append(f"⚠️ R:R ratio {rr}:1 below recommended minimum of 2:1")
    if position_size < 1:
        warnings.append("⚠️ Position size too small — entry/stop too close")
    if position_value > capital:
        warnings.append("⚠️ Position value exceeds total capital — use margin carefully")

    # Sizing check
    sizing_ok = (
        risk_pct <= 0.03 and
        position_pct <= 30 and
        rr >= 1.5 and
        position_size >= 1
    )

    # Recommendation
    if sizing_ok and rr >= 2.5 and risk_pct <= 0.02:
        rec = "✅ EXCELLENT — Optimal sizing with strong R:R"
    elif sizing_ok and rr >= 2.0:
        rec = "✅ GOOD — Acceptable sizing and R:R ratio"
    elif rr < 2.0:
        rec = "⚠️ MARGINAL — Improve R:R before entry"
    else:
        rec = "❌ REVIEW — Adjust position size or levels"

    return RiskSimulation(
        capital=capital,
        risk_pct=risk_pct,
        entry=entry,
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_amount=round(risk_amount, 2),
        risk_per_share=round(risk_per_share, 2),
        position_size=position_size,
        position_value=position_value,
        max_loss_usd=max_loss_usd,
        max_loss_pct=max_loss_pct,
        target_gain=target_gain,
        target_gain_pct=target_gain_pct,
        risk_reward=rr,
        breakeven_pct=breakeven_pct,
        position_pct_of_portfolio=position_pct,
        sizing_ok=sizing_ok,
        warnings=warnings,
        recommendation=rec,
    )


def format_simulation(sim: RiskSimulation, symbol: str = "") -> str:
    """Format simulation results for display."""
    warn_str = "\n".join(sim.warnings) if sim.warnings else "None"
    return f"""
╔══════════════════════════════════╗
║  🎯 RISK SIMULATION{f' — {symbol}' if symbol else '':10s}  ║
╚══════════════════════════════════╝

📊 INPUTS
├ Capital:      ${sim.capital:,.0f}
├ Risk:         {sim.risk_pct*100:.1f}% (${sim.risk_amount:,.0f})
├ Entry:        ${sim.entry:.2f}
├ Stop Loss:    ${sim.stop_loss:.2f}
└ Take Profit:  ${sim.take_profit:.2f}

📐 POSITION SIZING
├ Shares:       {sim.position_size:,}
├ Position $:   ${sim.position_value:,.0f} ({sim.position_pct_of_portfolio:.1f}% of portfolio)
└ Risk/Share:   ${sim.risk_per_share:.2f}

💰 OUTCOME SCENARIOS
├ Max Loss:     -${sim.max_loss_usd:,.0f} (-{sim.max_loss_pct:.2f}%)
├ Target Gain:  +${sim.target_gain:,.0f} (+{sim.target_gain_pct:.2f}%)
└ R:R Ratio:    {sim.risk_reward:.1f}:1

⚡ EFFICIENCY
└ Breakeven Cost: {sim.breakeven_pct:.3f}% (commissions)

⚠️ WARNINGS
{warn_str}

{sim.recommendation}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ SIMULATION ONLY — NO AUTO EXECUTION
""".strip()


def quick_size(capital: float, risk_pct: float,
               entry: float, stop: float) -> dict:
    """Quick position sizing without full simulation."""
    risk_per_share = abs(entry - stop)
    if risk_per_share == 0:
        return {"size": 0, "risk_usd": 0}
    risk_usd  = capital * risk_pct
    size      = int(risk_usd / risk_per_share)
    return {
        "size":     size,
        "risk_usd": round(risk_usd, 2),
        "value":    round(size * entry, 2),
    }


# ── Test ──────────────────────────────────────────────────────
if __name__ == "__main__":
    sim = simulate_risk(
        capital=50000,
        risk_pct=0.02,
        entry=875.50,
        stop_loss=851.00,
        take_profit=949.00,
    )
    print(format_simulation(sim, "NVDA"))
