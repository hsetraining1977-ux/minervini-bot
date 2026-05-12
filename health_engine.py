"""
health_engine.py
POSITION HEALTH ENGINE
Minervini Bot — PAPER TRADING ONLY
"""

import json
import os
import datetime
import logging
import requests
from config import ALPACA_API_KEY, ALPACA_SECRET_KEY

log = logging.getLogger("health_engine")
DATA_DIR   = "/root/logs"
PAPER_BASE = "https://paper-api.alpaca.markets"

def _alpaca_get(endpoint):
    try:
        r = requests.get(
            f"{PAPER_BASE}{endpoint}",
            headers={
                "APCA-API-KEY-ID":     ALPACA_API_KEY,
                "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
            }, timeout=8
        )
        return r.json() if r.status_code == 200 else {}
    except Exception:
        return {}

def _load(path, default):
    try:
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    except Exception:
        pass
    return default

# ── Market data ───────────────────────────────────────────────────────────────
def _get_price(symbol):
    try:
        d = _alpaca_get(f"/v2/stocks/{symbol}/trades/latest")
        return float(d["trade"]["p"])
    except Exception:
        return 0.0

def _get_vwap(symbol):
    try:
        now   = datetime.datetime.utcnow()
        start = now.replace(hour=13, minute=30, second=0, microsecond=0)
        if now < start:
            start -= datetime.timedelta(days=1)
        d    = _alpaca_get(
            f"/v2/stocks/{symbol}/bars"
            f"?timeframe=5Min&start={start.strftime('%Y-%m-%dT%H:%M:%SZ')}&limit=100"
        )
        bars = d.get("bars", [])
        if not bars:
            return 0.0
        tp_v  = sum(((b["h"]+b["l"]+b["c"])/3)*b["v"] for b in bars)
        tot_v = sum(b["v"] for b in bars)
        return round(tp_v / tot_v, 2) if tot_v else 0.0
    except Exception:
        return 0.0

def _get_atr(symbol, period=14):
    try:
        d    = _alpaca_get(f"/v2/stocks/{symbol}/bars?timeframe=1Day&limit={period+1}")
        bars = d.get("bars", [])
        if len(bars) < 2:
            return 0.0
        trs = [max(bars[i]["h"]-bars[i]["l"],
                   abs(bars[i]["h"]-bars[i-1]["c"]),
                   abs(bars[i]["l"]-bars[i-1]["c"]))
               for i in range(1, len(bars))]
        return round(sum(trs)/len(trs), 4)
    except Exception:
        return 0.0

def _get_vol_ratio(symbol):
    try:
        d    = _alpaca_get(f"/v2/stocks/{symbol}/bars?timeframe=1Day&limit=21")
        bars = d.get("bars", [])
        if len(bars) < 2:
            return 1.0
        avg  = sum(b["v"] for b in bars[:-1]) / (len(bars)-1)
        curr = bars[-1]["v"]
        return round(curr/avg, 2) if avg else 1.0
    except Exception:
        return 1.0

def _get_spy_trend():
    """Return SPY alignment: 1=bullish, 0=neutral, -1=bearish."""
    try:
        d    = _alpaca_get("/v2/stocks/SPY/bars?timeframe=1Day&limit=5")
        bars = d.get("bars", [])
        if len(bars) < 2:
            return 0
        if bars[-1]["c"] > bars[-2]["c"]:
            return 1
        if bars[-1]["c"] < bars[-2]["c"]:
            return -1
        return 0
    except Exception:
        return 0

def _get_rs(symbol):
    """Relative strength vs SPY (1-day return diff)."""
    try:
        sym_d = _alpaca_get(f"/v2/stocks/{symbol}/bars?timeframe=1Day&limit=2")
        spy_d = _alpaca_get("/v2/stocks/SPY/bars?timeframe=1Day&limit=2")
        sym_b = sym_d.get("bars", [])
        spy_b = spy_d.get("bars", [])
        if len(sym_b) < 2 or len(spy_b) < 2:
            return 0.0
        sym_ret = (sym_b[-1]["c"] - sym_b[-2]["c"]) / sym_b[-2]["c"]
        spy_ret = (spy_b[-1]["c"] - spy_b[-2]["c"]) / spy_b[-2]["c"]
        return round((sym_ret - spy_ret) * 100, 2)
    except Exception:
        return 0.0

# ── Health Score ──────────────────────────────────────────────────────────────
def calc_health_score(trade: dict) -> dict:
    """
    Calculate dynamic health score 0-100.
    Grades: ELITE(90+) HEALTHY(75+) CAUTION(60+) EXIT_RISK(<60)
    """
    symbol  = trade.get("symbol", "")
    entry   = float(trade.get("entry_price", 0))
    curr_sl = float(trade.get("current_sl", trade.get("stop_loss", 0)))
    tp1     = float(trade.get("take_profit_1", 0))

    price     = _get_price(symbol)
    vwap      = _get_vwap(symbol)
    vol_ratio = _get_vol_ratio(symbol)
    atr       = _get_atr(symbol)
    spy       = _get_spy_trend()
    rs        = _get_rs(symbol)

    score      = 50
    components = {}

    # 1. Trend strength (price vs entry)
    if entry > 0:
        pnl_pct = (price - entry) / entry * 100
        if pnl_pct > 5:
            ts = 20; components["trend"] = f"+20 (PnL={pnl_pct:.1f}%)"
        elif pnl_pct > 2:
            ts = 12; components["trend"] = f"+12 (PnL={pnl_pct:.1f}%)"
        elif pnl_pct > 0:
            ts = 5;  components["trend"] = f"+5 (PnL={pnl_pct:.1f}%)"
        elif pnl_pct > -2:
            ts = -5; components["trend"] = f"-5 (PnL={pnl_pct:.1f}%)"
        else:
            ts = -15;components["trend"] = f"-15 (PnL={pnl_pct:.1f}%)"
        score += ts
    else:
        pnl_pct = 0

    # 2. Relative strength vs SPY
    if rs > 1.5:
        score += 12; components["rs"] = f"+12 (RS={rs:.2f}%)"
    elif rs > 0:
        score += 6;  components["rs"] = f"+6 (RS={rs:.2f}%)"
    elif rs > -1:
        score -= 3;  components["rs"] = f"-3 (RS={rs:.2f}%)"
    else:
        score -= 10; components["rs"] = f"-10 (RS={rs:.2f}%)"

    # 3. Volume quality
    if vol_ratio > 1.8:
        score += 12; components["volume"] = f"+12 ({vol_ratio:.1f}x)"
    elif vol_ratio > 1.2:
        score += 6;  components["volume"] = f"+6 ({vol_ratio:.1f}x)"
    elif vol_ratio > 0.8:
        score -= 3;  components["volume"] = f"-3 ({vol_ratio:.1f}x)"
    else:
        score -= 10; components["volume"] = f"-10 ({vol_ratio:.1f}x)"

    # 4. VWAP position
    if vwap > 0:
        if price > vwap * 1.005:
            score += 10; components["vwap"] = f"+10 (above VWAP)"
        elif price > vwap:
            score += 5;  components["vwap"] = f"+5 (at VWAP)"
        elif price > vwap * 0.995:
            score -= 5;  components["vwap"] = f"-5 (near VWAP)"
        else:
            score -= 12; components["vwap"] = f"-12 (below VWAP)"

    # 5. SPY alignment
    if spy == 1:
        score += 8;  components["spy"] = "+8 (SPY bullish)"
    elif spy == -1:
        score -= 8;  components["spy"] = "-8 (SPY bearish)"
    else:
        components["spy"] = "0 (SPY neutral)"

    # 6. Volatility stability
    if atr > 0 and entry > 0:
        atr_pct = atr / entry * 100
        if atr_pct < 1.5:
            score += 8;  components["vol_stability"] = f"+8 (ATR={atr_pct:.1f}%)"
        elif atr_pct < 3:
            score += 3;  components["vol_stability"] = f"+3 (ATR={atr_pct:.1f}%)"
        elif atr_pct > 5:
            score -= 10; components["vol_stability"] = f"-10 (ATR={atr_pct:.1f}%)"
        else:
            components["vol_stability"] = f"0 (ATR={atr_pct:.1f}%)"

    # 7. Distance to stop (safety buffer)
    if curr_sl > 0 and price > 0:
        dist_sl_pct = (price - curr_sl) / price * 100
        if dist_sl_pct > 3:
            score += 5;  components["sl_dist"] = f"+5 (SL dist={dist_sl_pct:.1f}%)"
        elif dist_sl_pct < 1:
            score -= 8;  components["sl_dist"] = f"-8 (SL dist={dist_sl_pct:.1f}%)"
        else:
            components["sl_dist"] = f"0 (SL dist={dist_sl_pct:.1f}%)"

    # 8. Progress to target
    if tp1 > 0 and entry > 0 and price > entry:
        progress = (price - entry) / (tp1 - entry) * 100
        if progress > 70:
            score += 8;  components["tp_progress"] = f"+8 (TP1={progress:.0f}%)"
        elif progress > 40:
            score += 4;  components["tp_progress"] = f"+4 (TP1={progress:.0f}%)"
        else:
            components["tp_progress"] = f"0 (TP1={progress:.0f}%)"

    score = max(0, min(100, score))

    # Grade
    if score >= 90:
        grade = "ELITE";     icon = "🏆"; action = "HOLD_STRONG"
    elif score >= 75:
        grade = "HEALTHY";   icon = "🟢"; action = "HOLD"
    elif score >= 60:
        grade = "CAUTION";   icon = "🟡"; action = "MONITOR"
    else:
        grade = "EXIT_RISK"; icon = "🔴"; action = "CONSIDER_EXIT"

    return {
        "symbol":       symbol,
        "score":        score,
        "grade":        grade,
        "icon":         icon,
        "action":       action,
        "price":        price,
        "vwap":         vwap,
        "vol_ratio":    vol_ratio,
        "atr":          atr,
        "spy_trend":    spy,
        "rs":           rs,
        "pnl_pct":      round(pnl_pct, 2),
        "components":   components,
        "timestamp":    datetime.datetime.now().isoformat(),
        "paper_only":   True,
    }

def update_trade_health(trade_id: str, trade: dict) -> dict:
    """Calculate and store health score for a trade."""
    health = calc_health_score(trade)
    health_store = {}
    path = f"{DATA_DIR}/position_health.json"
    try:
        if os.path.exists(path):
            with open(path) as f:
                health_store = json.load(f)
    except Exception:
        pass
    health_store[trade_id] = health
    try:
        with open(path, "w") as f:
            json.dump(health_store, f, indent=2, default=str)
    except Exception as e:
        log.error(f"Health save error: {e}")
    return health

def get_all_health() -> dict:
    path = f"{DATA_DIR}/position_health.json"
    try:
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    except Exception:
        pass
    return {}
