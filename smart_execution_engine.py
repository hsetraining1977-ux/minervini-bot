"""
smart_execution_engine.py
SMART EXECUTION & POSITION MANAGEMENT ENGINE
Minervini Bot — Vultr VPS

⚠️ PAPER TRADING ONLY — NO LIVE EXECUTION ⚠️
All trades are simulated. No real money involved.
"""

import json
import os
import time
import datetime
import logging
from typing import Optional
from config import (
    ALPACA_API_KEY, ALPACA_SECRET_KEY,
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
)
import requests

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("smart_execution")

# ── Constants — PAPER ONLY ────────────────────────────────────────────────────
PAPER_BASE        = "https://paper-api.alpaca.markets"
PAPER_ONLY        = True   # NEVER change to False
PORTFOLIO         = 50_000.0

STARTER_PCT       = 0.30   # Stage 1: 30%
CONFIRM_PCT       = 0.40   # Stage 2: 40%
MOMENTUM_PCT      = 0.30   # Stage 3: 30%

TP1_EXIT_PCT      = 0.30   # Sell 30% at Target1
TP2_EXIT_PCT      = 0.40   # Sell 40% at Target2
RUNNER_PCT        = 0.30   # Leave 30% as runner

MAX_RISK_PER_TRADE = 0.01  # 1% max risk
MAX_POSITIONS      = 3
DAILY_DD_LIMIT     = 0.03  # 3% daily drawdown

DATA_DIR  = "/root/logs"
POSITIONS_FILE    = f"{DATA_DIR}/smart_positions.json"
JOURNAL_FILE      = f"{DATA_DIR}/trade_journal.json"
HEALTH_FILE       = f"{DATA_DIR}/position_health.json"
PERFORMANCE_FILE  = f"{DATA_DIR}/paper_performance.json"

# ── Alpaca Paper Headers ──────────────────────────────────────────────────────
def _alpaca_headers():
    return {
        "APCA-API-KEY-ID":     ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
        "Content-Type":        "application/json",
    }

def _alpaca_get(endpoint: str) -> dict:
    try:
        r = requests.get(
            f"{PAPER_BASE}{endpoint}",
            headers=_alpaca_headers(), timeout=10
        )
        return r.json() if r.status_code == 200 else {}
    except Exception as e:
        log.error(f"Alpaca GET error: {e}")
        return {}

def _alpaca_post(endpoint: str, payload: dict) -> dict:
    try:
        r = requests.post(
            f"{PAPER_BASE}{endpoint}",
            headers=_alpaca_headers(),
            json=payload, timeout=10
        )
        return r.json()
    except Exception as e:
        log.error(f"Alpaca POST error: {e}")
        return {}

def _alpaca_delete(endpoint: str) -> bool:
    try:
        r = requests.delete(
            f"{PAPER_BASE}{endpoint}",
            headers=_alpaca_headers(), timeout=10
        )
        return r.status_code in (200, 204)
    except Exception as e:
        log.error(f"Alpaca DELETE error: {e}")
        return False

# ── Telegram ──────────────────────────────────────────────────────────────────
def _send_telegram(msg: str):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id":    TELEGRAM_CHAT_ID,
                "text":       msg,
                "parse_mode": "Markdown",
            }, timeout=10
        )
    except Exception as e:
        log.warning(f"Telegram error: {e}")

# ── File helpers ──────────────────────────────────────────────────────────────
def _load(path: str, default):
    try:
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    except Exception:
        pass
    return default

def _save(path: str, data):
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        log.error(f"Save error {path}: {e}")

# ── Market data helpers ───────────────────────────────────────────────────────
def get_latest_price(symbol: str) -> float:
    data = _alpaca_get(f"/v2/stocks/{symbol}/quotes/latest")
    try:
        return float(data["quote"]["ap"])   # ask price
    except Exception:
        try:
            data2 = _alpaca_get(f"/v2/stocks/{symbol}/trades/latest")
            return float(data2["trade"]["p"])
        except Exception:
            return 0.0

def get_vwap(symbol: str) -> float:
    """Approximate VWAP from Alpaca bars."""
    try:
        now   = datetime.datetime.utcnow()
        start = now.replace(hour=13, minute=30, second=0, microsecond=0)
        if now < start:
            start = start - datetime.timedelta(days=1)
        params = f"?timeframe=5Min&start={start.strftime('%Y-%m-%dT%H:%M:%SZ')}&limit=100"
        data = _alpaca_get(f"/v2/stocks/{symbol}/bars{params}")
        bars = data.get("bars", [])
        if not bars:
            return 0.0
        tp_vol = sum(
            ((b["h"] + b["l"] + b["c"]) / 3) * b["v"] for b in bars
        )
        total_vol = sum(b["v"] for b in bars)
        return round(tp_vol / total_vol, 2) if total_vol else 0.0
    except Exception:
        return 0.0

def get_atr(symbol: str, period: int = 14) -> float:
    """Calculate ATR from daily bars."""
    try:
        data = _alpaca_get(
            f"/v2/stocks/{symbol}/bars?timeframe=1Day&limit={period + 1}"
        )
        bars = data.get("bars", [])
        if len(bars) < 2:
            return 0.0
        trs = []
        for i in range(1, len(bars)):
            h, l, pc = bars[i]["h"], bars[i]["l"], bars[i - 1]["c"]
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        return round(sum(trs) / len(trs), 4)
    except Exception:
        return 0.0

def get_volume_ratio(symbol: str) -> float:
    """Current volume vs 20-day avg volume ratio."""
    try:
        data = _alpaca_get(
            f"/v2/stocks/{symbol}/bars?timeframe=1Day&limit=21"
        )
        bars = data.get("bars", [])
        if len(bars) < 2:
            return 1.0
        avg_vol  = sum(b["v"] for b in bars[:-1]) / (len(bars) - 1)
        curr_vol = bars[-1]["v"]
        return round(curr_vol / avg_vol, 2) if avg_vol else 1.0
    except Exception:
        return 1.0

def get_vix() -> float:
    try:
        data = _alpaca_get("/v2/stocks/VIXY/bars?timeframe=1Day&limit=1")
        bars = data.get("bars", [])
        return float(bars[-1]["c"]) if bars else 20.0
    except Exception:
        return 20.0

# ── Kill switch ───────────────────────────────────────────────────────────────
def is_kill_switch_active() -> bool:
    ks = _load(f"{DATA_DIR}/kill_switch.json", {})
    return ks.get("active", False)

def activate_kill_switch(reason: str):
    _save(f"{DATA_DIR}/kill_switch.json", {
        "active": True, "reason": reason,
        "timestamp": datetime.datetime.now().isoformat()
    })
    log.warning(f"KILL SWITCH ACTIVATED: {reason}")
    _send_telegram(f"🔴 *KILL SWITCH ACTIVATED*\n`{reason}`\n⚠️ PAPER ONLY")

# ── Dynamic threshold ─────────────────────────────────────────────────────────
def get_dynamic_threshold() -> tuple:
    try:
        mi = _load(f"{DATA_DIR}/market_intelligence.json", {})
        regime = mi.get("regime", mi.get("market_regime", "NEUTRAL")).upper()
    except Exception:
        regime = "NEUTRAL"
    thresholds = {"RISK_ON": 75, "NEUTRAL": 85, "RISK_OFF": 92}
    return thresholds.get(regime, 85), regime

# ══════════════════════════════════════════════════════════════════════════════
# 1. MULTI-STAGE ENTRY ENGINE
# ══════════════════════════════════════════════════════════════════════════════
def calc_stage_sizes(plan: dict, portfolio: float = PORTFOLIO) -> dict:
    """Calculate share counts for each entry stage."""
    entry      = float(plan.get("entry", plan.get("entry_price", 0)))
    stop_loss  = float(plan.get("stop_loss", plan.get("sl", entry * 0.95)))
    risk_amt   = portfolio * MAX_RISK_PER_TRADE
    risk_per   = abs(entry - stop_loss)
    if risk_per == 0:
        return {}
    total_shares = int(risk_amt / risk_per)
    return {
        "starter":    max(1, int(total_shares * STARTER_PCT)),
        "confirm":    max(1, int(total_shares * CONFIRM_PCT)),
        "momentum":   max(1, int(total_shares * MOMENTUM_PCT)),
        "total":      total_shares,
        "entry":      entry,
        "stop_loss":  stop_loss,
        "risk_per_share": round(risk_per, 4),
        "max_loss":   round(total_shares * risk_per, 2),
    }

# ══════════════════════════════════════════════════════════════════════════════
# 2. SMART ENTRY LOGIC
# ══════════════════════════════════════════════════════════════════════════════
def check_entry_conditions(plan: dict) -> tuple:
    """Validate real-time entry conditions. Returns (ok, reasons)."""
    symbol    = plan.get("symbol", "")
    entry     = float(plan.get("entry", 0))
    reasons   = []
    passed    = []

    price     = get_latest_price(symbol)
    vwap      = get_vwap(symbol)
    vol_ratio = get_volume_ratio(symbol)
    atr       = get_atr(symbol)
    vix       = get_vix()

    # VIX check
    if vix > 30:
        reasons.append(f"VIX too high: {vix:.1f}")
    else:
        passed.append(f"VIX OK: {vix:.1f}")

    # Volume expansion
    if vol_ratio >= 1.5:
        passed.append(f"Volume expansion: {vol_ratio:.1f}x")
    else:
        reasons.append(f"Volume weak: {vol_ratio:.1f}x < 1.5x")

    # VWAP reclaim
    if price > vwap > 0:
        passed.append(f"Above VWAP: ${price:.2f} > ${vwap:.2f}")
    elif vwap > 0:
        reasons.append(f"Below VWAP: ${price:.2f} < ${vwap:.2f}")

    # Price near entry (within 1 ATR)
    if atr > 0 and abs(price - entry) <= atr:
        passed.append(f"Price near entry: ${price:.2f} ≈ ${entry:.2f}")
    elif atr > 0:
        reasons.append(f"Price too far from entry: ${price:.2f} vs ${entry:.2f}")

    # ATR volatility check
    if atr > entry * 0.05:
        reasons.append(f"ATR too high: {atr:.2f} ({atr/entry*100:.1f}%)")
    else:
        passed.append(f"ATR acceptable: {atr:.2f}")

    ok = len(reasons) == 0
    return ok, passed, reasons

# ══════════════════════════════════════════════════════════════════════════════
# 3. DYNAMIC STOP LOSS ENGINE
# ══════════════════════════════════════════════════════════════════════════════
def calc_dynamic_stop(position: dict) -> float:
    """Calculate dynamic SL based on ATR, VWAP, structure."""
    symbol    = position["symbol"]
    entry     = float(position["entry_price"])
    orig_sl   = float(position.get("stop_loss", entry * 0.95))
    stage     = position.get("stage", 1)

    price  = get_latest_price(symbol)
    vwap   = get_vwap(symbol)
    atr    = get_atr(symbol)

    # ATR-based stop: tighten as trade matures
    atr_mult  = {1: 2.0, 2: 1.5, 3: 1.0}.get(stage, 1.5)
    atr_stop  = price - (atr * atr_mult) if atr > 0 else orig_sl

    # VWAP-based stop
    vwap_stop = vwap * 0.995 if vwap > 0 else orig_sl

    # Use the highest (most protective) stop
    dynamic_sl = max(orig_sl, atr_stop, vwap_stop)

    # Never move stop below original SL
    dynamic_sl = max(dynamic_sl, orig_sl)

    # Never move stop above current price
    if dynamic_sl >= price:
        dynamic_sl = price * 0.98

    return round(dynamic_sl, 2)

# ══════════════════════════════════════════════════════════════════════════════
# 4 & 5. PARTIAL PROFIT TAKING + TRAILING STOP
# ══════════════════════════════════════════════════════════════════════════════
def check_partial_exits(position: dict) -> list:
    """Check if partial profit targets are hit. Returns list of exit actions."""
    symbol   = position["symbol"]
    price    = get_latest_price(symbol)
    tp1      = float(position.get("take_profit_1", position.get("tp1", 0)))
    tp2      = float(position.get("take_profit_2", position.get("tp2", 0)))
    exits    = []
    taken    = position.get("partials_taken", [])

    if tp1 > 0 and price >= tp1 and "TP1" not in taken:
        exits.append({
            "type":    "TP1",
            "price":   price,
            "pct":     TP1_EXIT_PCT,
            "shares":  int(position.get("shares", 0) * TP1_EXIT_PCT),
            "reason":  f"Target1 hit: ${price:.2f} >= ${tp1:.2f}",
        })
    if tp2 > 0 and price >= tp2 and "TP2" not in taken:
        exits.append({
            "type":    "TP2",
            "price":   price,
            "pct":     TP2_EXIT_PCT,
            "shares":  int(position.get("shares", 0) * TP2_EXIT_PCT),
            "reason":  f"Target2 hit: ${price:.2f} >= ${tp2:.2f}",
        })
    return exits

def calc_trailing_stop(position: dict) -> float:
    """AI trailing stop based on ATR, momentum, VWAP, volume."""
    symbol  = position["symbol"]
    price   = get_latest_price(symbol)
    atr     = get_atr(symbol)
    vwap    = get_vwap(symbol)
    vol_r   = get_volume_ratio(symbol)
    curr_sl = float(position.get("current_sl", position.get("stop_loss", price * 0.95)))

    # Momentum decay → tighten stop
    if vol_r < 0.7:
        trail_mult = 1.0   # tight
    elif vol_r > 1.5:
        trail_mult = 2.0   # loose — let it run
    else:
        trail_mult = 1.5

    atr_trail = price - (atr * trail_mult) if atr > 0 else curr_sl

    # VWAP loss → use VWAP as stop
    if vwap > 0 and price < vwap:
        vwap_trail = vwap * 0.998
        new_sl     = max(curr_sl, min(atr_trail, vwap_trail))
    else:
        new_sl = max(curr_sl, atr_trail)

    return round(new_sl, 2)

# ══════════════════════════════════════════════════════════════════════════════
# 6. FAKE BREAKOUT PROTECTION
# ══════════════════════════════════════════════════════════════════════════════
def check_fake_breakout(position: dict) -> tuple:
    """Detect fake breakouts for early exit. Returns (is_fake, reason)."""
    symbol    = position["symbol"]
    price     = get_latest_price(symbol)
    entry     = float(position["entry_price"])
    vwap      = get_vwap(symbol)
    vol_ratio = get_volume_ratio(symbol)
    atr       = get_atr(symbol)

    signals = []

    # Price below entry by more than 0.5 ATR
    if atr > 0 and price < entry - (atr * 0.5):
        signals.append(f"Price below entry: ${price:.2f} < ${entry:.2f}")

    # Volume collapsed
    if vol_ratio < 0.5:
        signals.append(f"Volume collapsed: {vol_ratio:.1f}x")

    # VWAP lost
    if vwap > 0 and price < vwap * 0.998:
        signals.append(f"VWAP lost: ${price:.2f} < ${vwap:.2f}")

    # Multiple signals = fake breakout
    is_fake = len(signals) >= 2
    return is_fake, signals

# ══════════════════════════════════════════════════════════════════════════════
# 7. INTRADAY VOLATILITY AWARENESS
# ══════════════════════════════════════════════════════════════════════════════
def get_volatility_size_multiplier(symbol: str) -> float:
    """Return position size multiplier based on volatility."""
    vix   = get_vix()
    atr   = get_atr(symbol)
    price = get_latest_price(symbol)

    mult = 1.0

    # High VIX
    if vix > 30:
        mult *= 0.5
        log.info(f"VIX={vix:.1f} → size reduced 50%")
    elif vix > 20:
        mult *= 0.75
        log.info(f"VIX={vix:.1f} → size reduced 25%")

    # High ATR relative to price
    if price > 0:
        atr_pct = atr / price
        if atr_pct > 0.04:   # > 4%
            mult *= 0.6
            log.info(f"ATR={atr_pct:.1%} → size reduced 40%")
        elif atr_pct > 0.025:
            mult *= 0.8

    return round(max(0.25, mult), 2)

# ══════════════════════════════════════════════════════════════════════════════
# 8. POSITION HEALTH MONITOR
# ══════════════════════════════════════════════════════════════════════════════
def calc_position_health(position: dict) -> dict:
    """Calculate position health score 0-100."""
    symbol    = position["symbol"]
    entry     = float(position["entry_price"])
    price     = get_latest_price(symbol)
    vwap      = get_vwap(symbol)
    vol_ratio = get_volume_ratio(symbol)
    atr       = get_atr(symbol)

    score = 50  # baseline

    # Trend strength: above entry
    pnl_pct = (price - entry) / entry if entry > 0 else 0
    if pnl_pct > 0.05:
        score += 20
    elif pnl_pct > 0:
        score += 10
    elif pnl_pct < -0.02:
        score -= 20
    else:
        score -= 5

    # Momentum: volume
    if vol_ratio > 1.5:
        score += 15
    elif vol_ratio > 1.0:
        score += 5
    else:
        score -= 10

    # VWAP alignment
    if vwap > 0:
        if price > vwap:
            score += 15
        else:
            score -= 15

    # ATR stability
    if atr > 0 and atr / price < 0.025:
        score += 10
    elif atr > 0 and atr / price > 0.04:
        score -= 10

    score = max(0, min(100, score))

    if score >= 70:
        status = "🟢 HEALTHY"
        action = "HOLD"
    elif score >= 45:
        status = "🟡 CAUTION"
        action = "MONITOR"
    else:
        status = "🔴 EXIT"
        action = "EXIT"

    return {
        "symbol":    symbol,
        "score":     score,
        "status":    status,
        "action":    action,
        "price":     price,
        "vwap":      vwap,
        "vol_ratio": vol_ratio,
        "pnl_pct":   round(pnl_pct * 100, 2),
        "timestamp": datetime.datetime.now().isoformat(),
    }

# ══════════════════════════════════════════════════════════════════════════════
# 11. TRADE JOURNAL
# ══════════════════════════════════════════════════════════════════════════════
def log_journal_entry(position: dict, event: str, details: dict = {}):
    """Save trade journal entry with full context."""
    journal = _load(JOURNAL_FILE, [])
    mi      = _load(f"{DATA_DIR}/market_intelligence.json", {})
    regime  = mi.get("regime", "UNKNOWN")

    entry = {
        "trade_id":          position.get("trade_id", ""),
        "symbol":            position.get("symbol", ""),
        "event":             event,
        "timestamp":         datetime.datetime.now().isoformat(),
        "market_regime":     regime,
        "entry_price":       position.get("entry_price", 0),
        "current_price":     get_latest_price(position.get("symbol", "")),
        "entry_quality":     position.get("entry_quality", "N/A"),
        "execution_quality": details.get("execution_quality", "N/A"),
        "exit_quality":      details.get("exit_quality", "N/A"),
        "slippage":          details.get("slippage", 0),
        "efficiency_score":  details.get("efficiency_score", 0),
        "stage":             position.get("stage", 1),
        "notes":             details.get("notes", ""),
        "paper_only":        True,
    }
    journal.append(entry)
    _save(JOURNAL_FILE, journal)

# ══════════════════════════════════════════════════════════════════════════════
# PAPER EXECUTION — STAGE ENTRY
# ══════════════════════════════════════════════════════════════════════════════
def execute_stage_entry(plan: dict, stage: int = 1) -> Optional[dict]:
    """
    Execute a staged paper entry via Alpaca Paper API.
    PAPER TRADING ONLY.
    """
    assert PAPER_ONLY, "LIVE TRADING NOT ALLOWED"

    symbol  = plan.get("symbol", "")
    sizes   = calc_stage_sizes(plan)
    if not sizes:
        log.error(f"Cannot calc sizes for {symbol}")
        return None

    stage_key = {1: "starter", 2: "confirm", 3: "momentum"}.get(stage, "starter")
    qty       = sizes.get(stage_key, 1)

    # Volatility size adjustment
    vol_mult  = get_volatility_size_multiplier(symbol)
    qty       = max(1, int(qty * vol_mult))

    # Smart entry conditions
    ok, passed, failed = check_entry_conditions(plan)
    try:
        import sys; sys.path.insert(0,"/root")
        from portfolio_guard import portfolio_check
        _pg_ok,_pg_mult,_pg_reason = portfolio_check(symbol, qty, float(plan.get("entry",plan.get("entry_price",0))))
        if not _pg_ok:
            log.info(f"[Portfolio BLOCKED] {symbol} - {_pg_reason}")
            return None
        qty = max(1, int(qty * _pg_mult))
    except Exception as _e:
        pass
    if not ok and stage == 1:
        log.info(f"[{symbol}] Entry conditions failed: {failed}")
        return None

    # Build bracket order for Alpaca Paper
    sl   = float(plan.get("stop_loss", plan.get("sl", 0)))
    tp1  = float(plan.get("take_profit_1", plan.get("tp1", 0)))

    order = {
        "symbol":        symbol,
        "qty":           str(qty),
        "side":          "buy",
        "type":          "market",
        "time_in_force": "day",
    }

    if sl > 0 and tp1 > 0:
        order["order_class"]  = "bracket"
        order["stop_loss"]    = {"stop_price": str(round(sl, 2))}
        order["take_profit"]  = {"limit_price": str(round(tp1, 2))}

    result = _alpaca_post("/v2/orders", order)

    if "id" not in result:
        log.error(f"[{symbol}] Order failed: {result}")
        return None

    trade_id = f"{symbol}_{int(time.time())}"
    price    = get_latest_price(symbol)
    position = {
        "trade_id":       trade_id,
        "symbol":         symbol,
        "entry_price":    price,
        "shares":         qty,
        "stage":          stage,
        "status":         "ACTIVE",
        "stop_loss":      sl,
        "current_sl":     sl,
        "take_profit_1":  tp1,
        "take_profit_2":  float(plan.get("take_profit_2", plan.get("tp2", 0))),
        "take_profit_3":  float(plan.get("take_profit_3", plan.get("tp3", 0))),
        "partials_taken": [],
        "alpaca_order_id": result["id"],
        "entry_quality":  "GOOD" if ok else "MARGINAL",
        "vol_multiplier": vol_mult,
        "opened_at":      datetime.datetime.now().isoformat(),
        "paper_only":     True,
    }

    # Save position
    positions = _load(POSITIONS_FILE, {})
    positions[trade_id] = position
    _save(POSITIONS_FILE, positions)

    # Journal
    log_journal_entry(position, f"STAGE_{stage}_ENTRY")

    # Telegram alert
    stage_names = {1: "🟡 STARTER (30%)", 2: "🟠 CONFIRM (40%)", 3: "🟢 MOMENTUM (30%)"}
    _send_telegram(
        f"📈 *PAPER TRADE — STAGE {stage} ENTRY*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 `{symbol}` | {stage_names.get(stage,'')}\n"
        f"💵 Entry: `${price:.2f}` | Qty: `{qty}`\n"
        f"🛑 SL: `${sl:.2f}` | 🎯 TP1: `${tp1:.2f}`\n"
        f"📊 Vol mult: `{vol_mult}x`\n"
        f"✅ Conditions: {len(passed)}/{len(passed)+len(failed)}\n"
        f"⚠️ *PAPER ONLY — NO REAL MONEY*"
    )

    log.info(f"[{symbol}] Stage {stage} entry: {qty} shares @ ${price:.2f} | Paper")
    return position

# ══════════════════════════════════════════════════════════════════════════════
# POSITION MANAGER — MAIN LOOP
# ══════════════════════════════════════════════════════════════════════════════
def manage_positions():
    """Monitor all open positions and manage exits/adjustments."""
    positions = _load(POSITIONS_FILE, {})
    health_data = {}

    for trade_id, pos in list(positions.items()):
        if pos.get("status") not in ("ACTIVE", "PARTIAL"):
            continue

        symbol = pos["symbol"]
        price  = get_latest_price(symbol)

        # ── Health check ──────────────────────────────────────────────────
        health = calc_position_health(pos)
        health_data[trade_id] = health

        # ── Fake breakout protection ──────────────────────────────────────
        is_fake, fake_reasons = check_fake_breakout(pos)
        if is_fake:
            log.warning(f"[{symbol}] FAKE BREAKOUT: {fake_reasons}")
            _send_telegram(
                f"⚠️ *FAKE BREAKOUT DETECTED — PAPER*\n"
                f"📌 `{symbol}` @ `${price:.2f}`\n"
                f"🔍 {' | '.join(fake_reasons)}\n"
                f"🚪 Early exit triggered"
            )
            pos["status"]     = "CLOSED"
            pos["exit_price"] = price
            pos["exit_reason"] = "FAKE_BREAKOUT"
            log_journal_entry(pos, "EARLY_EXIT_FAKE_BREAKOUT",
                              {"exit_quality": "POOR", "notes": str(fake_reasons)})
            positions[trade_id] = pos
            continue

        # ── Health downgrade alert ────────────────────────────────────────
        prev_action = pos.get("last_health_action", "HOLD")
        if health["action"] != prev_action:
            _send_telegram(
                f"{'🔴' if health['action']=='EXIT' else '🟡'} "
                f"*HEALTH DOWNGRADE — PAPER*\n"
                f"📌 `{symbol}` → {health['status']}\n"
                f"📊 Score: `{health['score']}/100`\n"
                f"💵 Price: `${price:.2f}` | PnL: `{health['pnl_pct']:.1f}%`"
            )
            pos["last_health_action"] = health["action"]

        if health["action"] == "EXIT":
            pos["status"]      = "CLOSED"
            pos["exit_price"]  = price
            pos["exit_reason"] = "HEALTH_EXIT"
            log_journal_entry(pos, "HEALTH_EXIT",
                              {"exit_quality": "FORCED", "notes": "Health score critical"})
            positions[trade_id] = pos
            continue

        # ── Partial profit taking ─────────────────────────────────────────
        partial_exits = check_partial_exits(pos)
        for ex in partial_exits:
            taken = pos.get("partials_taken", [])
            taken.append(ex["type"])
            pos["partials_taken"] = taken
            realized = ex["shares"] * (price - float(pos["entry_price"]))
            _send_telegram(
                f"💰 *PARTIAL PROFIT — PAPER*\n"
                f"📌 `{symbol}` — {ex['type']}\n"
                f"💵 Price: `${price:.2f}` | Shares: `{ex['shares']}`\n"
                f"💚 Realized: `${realized:.2f}`\n"
                f"📊 {ex['reason']}"
            )
            log_journal_entry(pos, f"PARTIAL_{ex['type']}",
                              {"exit_quality": "GOOD",
                               "efficiency_score": min(100, int(realized / 10))})

        # ── Dynamic SL update ─────────────────────────────────────────────
        new_sl = calc_dynamic_stop(pos)
        old_sl = float(pos.get("current_sl", pos.get("stop_loss", 0)))
        if new_sl > old_sl:
            pos["current_sl"] = new_sl
            _send_telegram(
                f"🔒 *TRAILING STOP MOVED — PAPER*\n"
                f"📌 `{symbol}`\n"
                f"📈 SL: `${old_sl:.2f}` → `${new_sl:.2f}`\n"
                f"💵 Price: `${price:.2f}`"
            )

        # ── Trailing stop ─────────────────────────────────────────────────
        trail_sl = calc_trailing_stop(pos)
        if trail_sl > pos.get("current_sl", 0):
            pos["current_sl"] = trail_sl

        # ── SL hit check ──────────────────────────────────────────────────
        if price <= float(pos.get("current_sl", 0)):
            pos["status"]      = "SL_HIT"
            pos["exit_price"]  = price
            pos["exit_reason"] = "STOP_LOSS"
            realized           = pos["shares"] * (price - float(pos["entry_price"]))
            _send_telegram(
                f"🔴 *STOP LOSS HIT — PAPER*\n"
                f"📌 `{symbol}` @ `${price:.2f}`\n"
                f"💔 Loss: `${realized:.2f}`\n"
                f"⚠️ PAPER ONLY"
            )
            log_journal_entry(pos, "SL_HIT",
                              {"exit_quality": "SL", "slippage": 0})

        positions[trade_id] = pos

    _save(POSITIONS_FILE, positions)
    _save(HEALTH_FILE, health_data)

# ══════════════════════════════════════════════════════════════════════════════
# SCAN & EXECUTE — integrates with paper_execution.py
# ══════════════════════════════════════════════════════════════════════════════
def smart_scan_and_execute():
    """
    Scan trade plans and execute multi-stage entries.
    PAPER TRADING ONLY.
    """
    if is_kill_switch_active():
        log.info("Kill switch active — skipping scan")
        return

    positions = _load(POSITIONS_FILE, {})
    active    = [p for p in positions.values()
                 if p.get("status") in ("ACTIVE", "PARTIAL")]

    if len(active) >= MAX_POSITIONS:
        log.info(f"Max positions reached: {len(active)}/{MAX_POSITIONS}")
        return

    plans = _load(f"{DATA_DIR}/trade_plans.json", {})
    if not plans:
        log.info("No trade plans found")
        return

    thr, regime = get_dynamic_threshold()
    executed_symbols = {p["symbol"] for p in active}

    for plan_id, plan in plans.items():
        if plan.get("status") != "READY":
            continue
        symbol = plan.get("symbol", "")
        if symbol in executed_symbols:
            continue

        score = float(plan.get("execution_score", plan.get("score", 0)))
        if score < thr:
            log.info(f"[{symbol}] Score {score} < threshold {thr} ({regime})")
            continue

        # Check daily drawdown
        perf = _load(PERFORMANCE_FILE, {})
        today = datetime.date.today().isoformat()
        daily_pnl = perf.get("daily_pnl", {}).get(today, 0)
        if daily_pnl < -(PORTFOLIO * DAILY_DD_LIMIT):
            activate_kill_switch(f"Daily DD limit hit: ${daily_pnl:.2f}")
            return

        log.info(f"[{symbol}] Executing Stage 1 entry | Score={score} | Regime={regime}")
        position = execute_stage_entry(plan, stage=1)

        if position:
            executed_symbols.add(symbol)
            if len(executed_symbols) >= MAX_POSITIONS:
                break

# ══════════════════════════════════════════════════════════════════════════════
# MAIN ENGINE LOOP
# ══════════════════════════════════════════════════════════════════════════════
def run_smart_engine():
    """
    Main loop: scan + manage positions every 5 minutes.
    PAPER TRADING ONLY.
    """
    assert PAPER_ONLY, "LIVE TRADING NOT ALLOWED"
    log.info("=" * 60)
    log.info("  SMART EXECUTION ENGINE — PAPER TRADING ONLY")
    log.info("=" * 60)

    cycle = 0
    while True:
        try:
            if not is_kill_switch_active():
                # Every cycle: manage existing positions
                manage_positions()

                # Every 6 cycles (~30 min): scan for new entries
                if cycle % 6 == 0:
                    smart_scan_and_execute()

                cycle += 1
            else:
                log.warning("Kill switch active — engine paused")

        except Exception as e:
            log.error(f"Engine error: {e}", exc_info=True)

        time.sleep(300)   # 5-minute cycle


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys
    if "--status" in sys.argv:
        positions = _load(POSITIONS_FILE, {})
        active    = [p for p in positions.values()
                     if p.get("status") in ("ACTIVE", "PARTIAL")]
        print(f"📊 Active positions: {len(active)}/{MAX_POSITIONS}")
        for p in active:
            h = calc_position_health(p)
            print(f"  {p['symbol']}: {h['status']} | Score={h['score']} | PnL={h['pnl_pct']:.1f}%")
    elif "--scan" in sys.argv:
        smart_scan_and_execute()
        print("✅ Scan complete")
    elif "--manage" in sys.argv:
        manage_positions()
        print("✅ Positions managed")
    elif "--health" in sys.argv:
        positions = _load(POSITIONS_FILE, {})
        for tid, pos in positions.items():
            if pos.get("status") in ("ACTIVE", "PARTIAL"):
                h = calc_position_health(pos)
                print(f"{pos['symbol']}: {h['status']} (Score={h['score']})")
    else:
        run_smart_engine()
