"""
exit_intelligence.py
EXIT INTELLIGENCE LAYER
Minervini Bot — PAPER TRADING ONLY
"""

import datetime
import logging
from health_engine import _get_price, _get_vwap, _get_vol_ratio, _get_atr, _get_spy_trend, _get_rs

log = logging.getLogger("exit_intelligence")

# ── Exit signal weights ───────────────────────────────────────────────────────
EXIT_SIGNALS = {
    "weak_momentum":       {"weight": 25, "description": "Momentum fading"},
    "volatility_spike":    {"weight": 30, "description": "Volatility too high"},
    "failed_breakout":     {"weight": 35, "description": "Breakout failed"},
    "trailing_stop":       {"weight": 100,"description": "Trailing stop hit"},
    "breadth_deterioration":{"weight": 20,"description": "Market breadth weak"},
    "relative_weakness":   {"weight": 25, "description": "Underperforming SPY"},
    "vwap_loss":           {"weight": 30, "description": "VWAP lost"},
    "volume_collapse":     {"weight": 25, "description": "Volume collapsed"},
}

def analyze_exit_signals(trade: dict) -> dict:
    """
    Analyze all exit signals for a trade.
    Returns exit recommendation with full signal breakdown.
    PAPER TRADING ONLY.
    """
    symbol    = trade.get("symbol", "")
    entry     = float(trade.get("entry_price", 0))
    curr_sl   = float(trade.get("current_sl", trade.get("stop_loss", 0)))
    orig_sl   = float(trade.get("stop_loss", 0))

    price     = _get_price(symbol)
    vwap      = _get_vwap(symbol)
    vol_ratio = _get_vol_ratio(symbol)
    atr       = _get_atr(symbol)
    spy       = _get_spy_trend()
    rs        = _get_rs(symbol)

    signals_triggered = []
    total_weight      = 0

    # 1. Trailing stop hit
    if curr_sl > 0 and price <= curr_sl:
        signals_triggered.append({
            "signal":      "trailing_stop",
            "weight":      100,
            "description": f"Price ${price:.2f} ≤ SL ${curr_sl:.2f}",
            "severity":    "CRITICAL",
        })
        total_weight = 100

    # 2. Weak momentum (volume collapse)
    if vol_ratio < 0.6:
        w = EXIT_SIGNALS["weak_momentum"]["weight"]
        signals_triggered.append({
            "signal":      "weak_momentum",
            "weight":      w,
            "description": f"Volume {vol_ratio:.1f}x (< 0.6x avg)",
            "severity":    "HIGH",
        })
        total_weight += w

    # 3. Volume collapse (severe)
    if vol_ratio < 0.4:
        w = EXIT_SIGNALS["volume_collapse"]["weight"]
        signals_triggered.append({
            "signal":      "volume_collapse",
            "weight":      w,
            "description": f"Volume collapsed: {vol_ratio:.1f}x",
            "severity":    "HIGH",
        })
        total_weight += w

    # 4. VWAP loss
    if vwap > 0 and price < vwap * 0.997:
        w = EXIT_SIGNALS["vwap_loss"]["weight"]
        signals_triggered.append({
            "signal":      "vwap_loss",
            "weight":      w,
            "description": f"Price ${price:.2f} below VWAP ${vwap:.2f}",
            "severity":    "HIGH",
        })
        total_weight += w

    # 5. Failed breakout
    if entry > 0:
        ret_pct = (price - entry) / entry * 100
        if ret_pct < -1.5 and vol_ratio < 0.8:
            w = EXIT_SIGNALS["failed_breakout"]["weight"]
            signals_triggered.append({
                "signal":      "failed_breakout",
                "weight":      w,
                "description": f"Price below entry {ret_pct:.1f}% + weak volume",
                "severity":    "CRITICAL",
            })
            total_weight += w

    # 6. Relative weakness vs SPY
    if rs < -2.0:
        w = EXIT_SIGNALS["relative_weakness"]["weight"]
        signals_triggered.append({
            "signal":      "relative_weakness",
            "weight":      w,
            "description": f"Underperforming SPY by {rs:.1f}%",
            "severity":    "MEDIUM",
        })
        total_weight += w

    # 7. SPY deterioration
    if spy == -1 and entry > 0 and price < entry:
        w = EXIT_SIGNALS["breadth_deterioration"]["weight"]
        signals_triggered.append({
            "signal":      "breadth_deterioration",
            "weight":      w,
            "description": "SPY bearish + position losing",
            "severity":    "HIGH",
        })
        total_weight += w

    # 8. Volatility spike
    if atr > 0 and entry > 0:
        atr_pct = atr / entry * 100
        if atr_pct > 5:
            w = EXIT_SIGNALS["volatility_spike"]["weight"]
            signals_triggered.append({
                "signal":      "volatility_spike",
                "weight":      w,
                "description": f"ATR {atr_pct:.1f}% of price",
                "severity":    "HIGH",
            })
            total_weight += w

    # ── Exit recommendation ───────────────────────────────────────────────────
    total_weight = min(total_weight, 100)

    if total_weight >= 100:
        recommendation = "EXIT_NOW"
        urgency        = "🔴 CRITICAL"
    elif total_weight >= 60:
        recommendation = "CONSIDER_EXIT"
        urgency        = "🟠 HIGH"
    elif total_weight >= 35:
        recommendation = "MONITOR_CLOSELY"
        urgency        = "🟡 MEDIUM"
    else:
        recommendation = "HOLD"
        urgency        = "🟢 LOW"

    return {
        "symbol":           symbol,
        "price":            price,
        "exit_score":       total_weight,
        "recommendation":   recommendation,
        "urgency":          urgency,
        "signals_triggered": signals_triggered,
        "signal_count":     len(signals_triggered),
        "metrics": {
            "vol_ratio": vol_ratio,
            "vwap":      vwap,
            "rs":        rs,
            "spy":       spy,
            "atr":       atr,
        },
        "timestamp":  datetime.datetime.now().isoformat(),
        "paper_only": True,
    }

# ── Trade efficiency score ────────────────────────────────────────────────────
def calc_efficiency_score(trade: dict) -> dict:
    """
    Calculate trade efficiency score and grade.
    Grades: A+ A B C D
    """
    entry      = float(trade.get("entry_price", 0))
    exit_price = float(trade.get("exit_price", entry))
    curr_sl    = float(trade.get("stop_loss", 0))
    tp1        = float(trade.get("take_profit_1", 0))
    mfe        = float(trade.get("mfe", 0))
    mae        = float(trade.get("mae", 0))
    shares     = int(trade.get("shares", 0))
    duration   = int(trade.get("duration_mins", 0))
    exit_reason = trade.get("exit_reason", "MANUAL")

    scores = {}

    # 1. Entry quality (how close to ideal entry)
    if entry > 0:
        # Perfect entry = exactly at plan price
        plan_entry = float(trade.get("planned_entry", entry))
        slip_pct   = abs(entry - plan_entry) / plan_entry * 100 if plan_entry else 0
        if slip_pct < 0.1:
            scores["entry_quality"] = 25
        elif slip_pct < 0.3:
            scores["entry_quality"] = 20
        elif slip_pct < 0.5:
            scores["entry_quality"] = 15
        else:
            scores["entry_quality"] = 8
    else:
        scores["entry_quality"] = 0

    # 2. Timing quality (MFE vs realized)
    if mfe > 0 and shares > 0:
        realized = (exit_price - entry) * shares
        efficiency_ratio = realized / mfe if mfe != 0 else 0
        if efficiency_ratio > 0.8:
            scores["timing_quality"] = 25
        elif efficiency_ratio > 0.6:
            scores["timing_quality"] = 18
        elif efficiency_ratio > 0.4:
            scores["timing_quality"] = 12
        elif efficiency_ratio > 0:
            scores["timing_quality"] = 6
        else:
            scores["timing_quality"] = 0
    else:
        scores["timing_quality"] = 12   # neutral if no data

    # 3. Execution quality (MAE management)
    if mae < 0 and curr_sl > 0 and entry > 0:
        max_risk = abs(entry - curr_sl) * shares
        actual_mae = abs(mae)
        mae_ratio  = actual_mae / max_risk if max_risk else 0
        if mae_ratio < 0.3:
            scores["execution_quality"] = 25
        elif mae_ratio < 0.6:
            scores["execution_quality"] = 18
        elif mae_ratio < 0.9:
            scores["execution_quality"] = 10
        else:
            scores["execution_quality"] = 4
    else:
        scores["execution_quality"] = 20   # no drawdown = good

    # 4. Exit quality
    exit_scores = {
        "TP2_HIT":       25,
        "TP1_HIT":       20,
        "TRAILING_STOP": 18,
        "HEALTH_EXIT":   12,
        "MANUAL":        10,
        "FAKE_BREAKOUT": 8,
        "SL_HIT":        5,
        "FORCED":        3,
    }
    scores["exit_quality"] = exit_scores.get(exit_reason, 10)

    # 5. Risk efficiency (PnL vs max risk)
    if curr_sl > 0 and entry > 0 and shares > 0:
        max_risk  = abs(entry - curr_sl) * shares
        realized  = (exit_price - entry) * shares
        rr_actual = realized / max_risk if max_risk > 0 else 0
        if rr_actual > 3:
            scores["risk_efficiency"] = 20
        elif rr_actual > 2:
            scores["risk_efficiency"] = 16
        elif rr_actual > 1:
            scores["risk_efficiency"] = 12
        elif rr_actual > 0:
            scores["risk_efficiency"] = 6
        else:
            scores["risk_efficiency"] = 0
    else:
        scores["risk_efficiency"] = 10

    total = sum(scores.values())
    total = max(0, min(100, total))

    if total >= 90:
        grade = "A+"
    elif total >= 80:
        grade = "A"
    elif total >= 70:
        grade = "B"
    elif total >= 55:
        grade = "C"
    else:
        grade = "D"

    return {
        "total_score":    total,
        "grade":          grade,
        "components":     scores,
        "duration_mins":  duration,
        "paper_only":     True,
    }
