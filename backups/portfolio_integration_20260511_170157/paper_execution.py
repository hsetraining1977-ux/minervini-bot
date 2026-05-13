#!/usr/bin/env python3
"""
paper_execution.py — Paper Auto Execution Engine (Alpaca Paper Trading)
PAPER TRADING ONLY — NO REAL MONEY — NO LIVE TRADING
Uses Alpaca Paper Trading API for realistic paper execution.
"""

import os, json, time, requests
from datetime import datetime, timedelta
from typing import Optional

try:
    from logger import get_logger
    log = get_logger("paper_execution")
except ImportError:
    import logging
    log = logging.getLogger("paper_execution")
    logging.basicConfig(level=logging.INFO)

from dotenv import load_dotenv
load_dotenv("/root/.env")

# ═══════════════════════════════════════════════════
# ⚠️  PAPER TRADING ONLY — ALPACA PAPER API
# ═══════════════════════════════════════════════════

PAPER_ONLY   = True   # NEVER change this
PAPER_BASE   = "https://paper-api.alpaca.markets"
DATA_BASE    = "https://data.alpaca.markets"
PORTFOLIO    = 50000

ALPACA_KEY    = os.getenv("ALPACA_API_KEY")    or os.getenv("ALPACA_KEY")
ALPACA_SECRET = os.getenv("ALPACA_SECRET_KEY") or os.getenv("ALPACA_SECRET")

HEADERS = {
    "APCA-API-KEY-ID":     ALPACA_KEY    or "",
    "APCA-API-SECRET-KEY": ALPACA_SECRET or "",
    "Content-Type":        "application/json",
}

# ── Files ─────────────────────────────────────────────────────
TRADES_FILE      = "/root/logs/paper_trades.json"
PERFORMANCE_FILE = "/root/logs/paper_performance.json"
KILL_SWITCH_FILE = "/root/logs/kill_switch.json"
os.makedirs("/root/logs", exist_ok=True)

# ── Risk Rules ────────────────────────────────────────────────
MAX_RISK_PCT    = 0.01
MAX_TRADES      = 3
DAILY_DD_LIMIT  = 0.03
MIN_EXEC_SCORE  = 85
BLOCKED_REGIMES = {"RISK_OFF", "CRISIS", "STRONG_RISK_OFF"}


# ── Alpaca Paper API ──────────────────────────────────────────


# ── PORTFOLIO INTELLIGENCE GUARD (PAPER ONLY) ─────────────────────────────────
import json as _json_pg
import os   as _os_pg

_PORTFOLIO_GUARD_LOADED = True
_DATA_DIR_PG = "/root/logs"

def _pg_load(path, default={}):
    try:
        if _os_pg.path.exists(path):
            with open(path) as f:
                return _json_pg.load(f)
    except Exception:
        pass
    return default

def portfolio_check_trade(symbol: str, planned_qty: int, entry_price: float) -> dict:
    """
    Full portfolio intelligence check before any trade.
    Returns dict with: approved, size_multiplier, reason, risk_score.
    PAPER TRADING ONLY — no live execution.
    """
    heat      = _pg_load(f"{_DATA_DIR_PG}/portfolio_heat.json")
    corr_data = _pg_load(f"{_DATA_DIR_PG}/correlation_risk.json")
    alloc     = _pg_load(f"{_DATA_DIR_PG}/capital_allocation.json")

    heat_pct  = float(heat.get("portfolio_heat_pct", 0))
    cash_pct  = float(heat.get("cash_pct", 100))
    positions = heat.get("positions", [])
    port_val  = float(heat.get("portfolio_value", 50000))

    # ── Sector map ────────────────────────────────────────────────────────────
    SECTOR_MAP = {
        "NVDA":"Technology","AMD":"Technology","MSFT":"Technology",
        "AAPL":"Technology","GOOGL":"Technology","META":"Technology",
        "SMCI":"Technology","AVGO":"Technology","ARM":"Technology",
        "TSLA":"Technology","MRVL":"Technology","INTC":"Technology",
        "LLY":"Healthcare","UNH":"Healthcare","JNJ":"Healthcare",
        "JPM":"Financials","GS":"Financials","MS":"Financials",
        "V":"Financials","MA":"Financials",
        "BTCUSD":"Crypto","ETHUSD":"Crypto",
    }
    CORR_GROUPS = {
        "Semiconductors": ["NVDA","AMD","SMCI","AVGO","MRVL","ARM","INTC","MU"],
        "MegaCap_Tech":   ["AAPL","MSFT","GOOGL","META","AMZN"],
        "Crypto":         ["BTCUSD","ETHUSD","COIN","MSTR"],
        "EV":             ["TSLA","RIVN","LCID","NIO"],
    }

    sector        = SECTOR_MAP.get(symbol, "Other")
    sector_exp    = float(heat.get("sector_exposure", {}).get(sector, 0))
    symbol_weight = next(
        (float(p.get("weight", 0)) for p in positions if p.get("symbol") == symbol),
        0.0
    )
    trade_value   = planned_qty * entry_price
    new_weight    = trade_value / port_val * 100 if port_val else 0

    # ── Correlation check ─────────────────────────────────────────────────────
    existing_symbols = [p.get("symbol", "") for p in positions]
    corr_group       = "Other"
    corr_count       = 0
    for grp, members in CORR_GROUPS.items():
        if symbol in members:
            corr_group = grp
            corr_count = sum(1 for s in existing_symbols if s in members)
            break

    # ── Risk score 0-100 ──────────────────────────────────────────────────────
    risk_score = 0
    risk_score += min(40, heat_pct * 6.7)          # heat contribution (0-40)
    risk_score += min(20, max(0, sector_exp - 20))  # sector concentration (0-20)
    risk_score += min(20, corr_count * 10)          # correlation (0-20)
    risk_score += min(20, max(0, (100-cash_pct)-50))# capital utilization (0-20)
    risk_score  = min(100, int(risk_score))

    # ── Decision logic ────────────────────────────────────────────────────────
    size_mult = 1.0
    reasons   = []
    approved  = True

    # BLOCK: heat > 90%
    if heat_pct > 5.4:  # 90% of 6% max
        return {
            "approved":        False,
            "size_multiplier": 0.0,
            "reason":          f"Portfolio heat {heat_pct:.1f}% > 90% limit — trades BLOCKED",
            "risk_score":      risk_score,
            "heat_pct":        heat_pct,
            "sector":          sector,
            "sector_exp":      sector_exp,
            "corr_group":      corr_group,
            "paper_only":      True,
        }

    # BLOCK: duplicate symbol
    if symbol in existing_symbols:
        return {
            "approved":        False,
            "size_multiplier": 0.0,
            "reason":          f"{symbol} already in portfolio",
            "risk_score":      risk_score,
            "heat_pct":        heat_pct,
            "sector":          sector,
            "sector_exp":      sector_exp,
            "corr_group":      corr_group,
            "paper_only":      True,
        }

    # BLOCK: max correlation
    if corr_count >= 2:
        return {
            "approved":        False,
            "size_multiplier": 0.0,
            "reason":          f"Correlation limit: {corr_count} {corr_group} positions",
            "risk_score":      risk_score,
            "heat_pct":        heat_pct,
            "sector":          sector,
            "sector_exp":      sector_exp,
            "corr_group":      corr_group,
            "paper_only":      True,
        }

    # REDUCE: sector > 35%
    if sector_exp > 35:
        size_mult *= 0.5
        reasons.append(f"Sector {sector} {sector_exp:.1f}% > 35% → size 50%")

    # REDUCE: symbol weight > 15%
    if new_weight > 15:
        size_mult *= 0.6
        reasons.append(f"Weight {new_weight:.1f}% > 15% → size 60%")

    # REDUCE: heat > 70% of max (4.2%)
    if heat_pct > 4.2:
        size_mult *= 0.7
        reasons.append(f"Heat {heat_pct:.1f}% > 70% max → size 70%")

    # REDUCE: one correlated position
    if corr_count == 1:
        size_mult *= 0.75
        reasons.append(f"1 {corr_group} position → size 75%")

    size_mult = round(max(0.25, min(1.0, size_mult)), 2)
    reason    = " | ".join(reasons) if reasons else "Portfolio check passed"

    return {
        "approved":        approved,
        "size_multiplier": size_mult,
        "reason":          reason,
        "risk_score":      risk_score,
        "heat_pct":        heat_pct,
        "sector":          sector,
        "sector_exp":      round(sector_exp, 2),
        "new_weight":      round(new_weight, 2),
        "corr_group":      corr_group,
        "corr_count":      corr_count,
        "paper_only":      True,
    }

def send_portfolio_summary_telegram():
    """Send portfolio summary to Telegram. PAPER ONLY."""
    try:
        import requests as _req
        from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
        heat  = _pg_load(f"{_DATA_DIR_PG}/portfolio_heat.json")
        warns = _pg_load(f"{_DATA_DIR_PG}/concentration_warnings.json", {"warnings":[]})
        alloc = _pg_load(f"{_DATA_DIR_PG}/capital_allocation.json", {})

        heat_pct  = heat.get("portfolio_heat_pct", 0)
        cash_pct  = heat.get("cash_pct", 100)
        positions = heat.get("position_count", 0)
        unreal    = heat.get("total_unrealized", 0)
        sector_exp= heat.get("sector_exposure", {})
        w_count   = len(warns.get("warnings", []))
        regime    = alloc.get("regime", "NEUTRAL")

        # Risk score
        risk_score = min(100, int(heat_pct * 16.7))

        sector_lines = "
".join(
            f"  • {s}: `{v:.1f}%`" for s, v in sector_exp.items()
        )
        warn_lines = "
".join(
            f"  ⚠️ {w.get('message','')}"
            for w in warns.get("warnings", [])[:3]
        )

        msg = (
            f"📊 *PORTFOLIO SUMMARY — PAPER*
"
            f"━━━━━━━━━━━━━━━━━━━━━
"
            f"🌡️ Heat: `{heat_pct:.1f}%` | 💰 Cash: `{cash_pct:.1f}%`
"
            f"📈 Positions: `{positions}` | P&L: `${unreal:+.2f}`
"
            f"🧠 Regime: `{regime}` | Risk Score: `{risk_score}/100`
"
            f"
🏭 Sector Exposure:
{sector_lines or '  None'}
"
            + (f"
⚠️ Warnings ({w_count}):
{warn_lines}" if w_count else "")
            + f"

⚠️ PAPER TRADING ONLY"
        )
        _req.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"},
            timeout=10
        )
    except Exception as e:
        pass

# ── END PORTFOLIO INTELLIGENCE GUARD ─────────────────────────────────────────
def get_dynamic_threshold():
    import json, os
    try:
        mi_path = "/root/logs/market_intelligence.json"
        if os.path.exists(mi_path):
            with open(mi_path) as f:
                mi = json.load(f)
            regime = mi.get("regime", mi.get("market_regime", "NEUTRAL")).upper()
        else:
            regime = "NEUTRAL"
    except Exception:
        regime = "NEUTRAL"
    thresholds = {"RISK_ON": 75, "NEUTRAL": 85, "RISK_OFF": 92}
    return thresholds.get(regime, 85), regime

def _log_rejection(symbol, score, threshold, regime):
    import datetime
    msg = f"[REJECTED] {symbol} | Score={score} | Required={threshold} | Regime={regime} | {datetime.datetime.now()}"
    try:
        with open("/root/logs/trade_decisions.log","a") as f:
            f.write(msg+"\n")
    except: pass
    print(msg)

def alpaca_get(endpoint: str) -> Optional[dict]:
    try:
        r = requests.get(f"{PAPER_BASE}{endpoint}", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return r.json()
        log.error(f"Alpaca GET {endpoint}: {r.status_code} {r.text[:100]}")
    except Exception as e:
        log.error(f"Alpaca GET error: {e}")
    return None


def alpaca_post(endpoint: str, data: dict) -> Optional[dict]:
    assert PAPER_ONLY, "PAPER ONLY"
    try:
        r = requests.post(
            f"{PAPER_BASE}{endpoint}",
            headers=HEADERS, json=data, timeout=10
        )
        if r.status_code in (200, 201):
            return r.json()
        log.error(f"Alpaca POST {endpoint}: {r.status_code} {r.text[:200]}")
    except Exception as e:
        log.error(f"Alpaca POST error: {e}")
    return None


def alpaca_delete(endpoint: str) -> bool:
    assert PAPER_ONLY, "PAPER ONLY"
    try:
        r = requests.delete(
            f"{PAPER_BASE}{endpoint}", headers=HEADERS, timeout=10
        )
        return r.status_code in (200, 204)
    except Exception as e:
        log.error(f"Alpaca DELETE error: {e}")
    return False


def get_account() -> Optional[dict]:
    return alpaca_get("/v2/account")


def get_positions() -> list:
    result = alpaca_get("/v2/positions")
    return result if isinstance(result, list) else []


def get_orders(status: str = "open") -> list:
    result = alpaca_get(f"/v2/orders?status={status}&limit=50")
    return result if isinstance(result, list) else []


def get_current_price(symbol: str) -> Optional[float]:
    try:
        r = requests.get(
            f"{DATA_BASE}/v2/stocks/{symbol}/trades/latest",
            headers=HEADERS, timeout=10
        )
        if r.status_code == 200:
            price = float(r.json().get("trade", {}).get("p", 0))
            if price > 0:
                return price
    except Exception:
        pass
    try:
        import yfinance as yf
        hist = yf.Ticker(symbol).history(period="1d", interval="1m")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass
    return None


def is_market_open() -> bool:
    data = alpaca_get("/v2/clock")
    if data:
        return data.get("is_open", False)
    return False


# ── Kill Switch ───────────────────────────────────────────────
def is_kill_switch_active() -> bool:
    try:
        if os.path.exists(KILL_SWITCH_FILE):
            with open(KILL_SWITCH_FILE) as f:
                return json.load(f).get("active", False)
    except Exception:
        pass
    return False


def activate_kill_switch(reason: str):
    with open(KILL_SWITCH_FILE, "w") as f:
        json.dump({"active": True, "reason": reason,
                   "timestamp": datetime.now().isoformat()}, f)
    log.error(f"🚨 KILL SWITCH: {reason}")
    _send_telegram(
        f"🚨 <b>KILL SWITCH ACTIVATED</b>\n"
        f"Reason: {reason}\n"
        f"⚠️ <i>PAPER TRADING HALTED</i>"
    )


def deactivate_kill_switch():
    with open(KILL_SWITCH_FILE, "w") as f:
        json.dump({"active": False,
                   "timestamp": datetime.now().isoformat()}, f)
    log.info("Kill switch deactivated")


# ── Telegram ──────────────────────────────────────────────────
def _send_telegram(msg: str):
    token   = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e:
        log.error(f"Telegram failed: {e}")


# ── Data Store ────────────────────────────────────────────────
def load_trades() -> dict:
    try:
        if os.path.exists(TRADES_FILE):
            with open(TRADES_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_trades(trades: dict):
    try:
        with open(TRADES_FILE, "w") as f:
            json.dump(trades, f, indent=2, default=str)
    except Exception as e:
        log.error(f"Save trades failed: {e}")


def load_performance() -> dict:
    try:
        if os.path.exists(PERFORMANCE_FILE):
            with open(PERFORMANCE_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {
        "total_trades": 0, "wins": 0, "losses": 0,
        "total_pnl": 0.0, "max_drawdown": 0.0,
        "equity_curve": [], "daily_pnl": {},
        "best_trade": None, "worst_trade": None,
        "regime_perf": {},
    }


def save_performance(perf: dict):
    try:
        with open(PERFORMANCE_FILE, "w") as f:
            json.dump(perf, f, indent=2, default=str)
    except Exception as e:
        log.error(f"Save performance failed: {e}")


# ── Position Sizing ───────────────────────────────────────────
def calc_position(entry: float, stop: float, portfolio: float = PORTFOLIO) -> dict:
    risk_usd   = portfolio * MAX_RISK_PCT
    risk_share = abs(entry - stop)
    if risk_share == 0:
        return {"shares": 0, "risk_usd": 0}
    shares = max(1, int(risk_usd / risk_share))
    return {"shares": shares, "risk_usd": round(shares * risk_share, 2)}


# ── Entry Validation ──────────────────────────────────────────
def validate_entry(plan: dict) -> tuple[bool, str]:
    if is_kill_switch_active():
        return False, "Kill switch active"
    if not is_market_open():
        return False, "Market closed"
    if plan.get("execution_score", 0) < MIN_EXEC_SCORE:
        return False, f"Exec score {plan.get('execution_score')} < {MIN_EXEC_SCORE}"
    if plan.get("regime", "") in BLOCKED_REGIMES:
        return False, f"Regime blocked: {plan.get('regime')}"

    cl = plan.get("checklist", {})
    for check in ["regime_ok", "liquidity_ok", "volume_confirmed",
                  "atr_valid", "risk_acceptable"]:
        if not cl.get(check, False):
            return False, f"Checklist failed: {check}"

    positions = get_positions()
    if len(positions) >= MAX_TRADES:
        return False, f"Max positions ({MAX_TRADES}) reached"

    for pos in positions:
        if pos.get("symbol") == plan.get("symbol"):
            return False, f"Already in {plan.get('symbol')}"

    perf  = load_performance()
    today = datetime.now().strftime("%Y-%m-%d")
    if perf.get("daily_pnl", {}).get(today, 0) < -(PORTFOLIO * DAILY_DD_LIMIT):
        activate_kill_switch("Daily DD limit hit")
        return False, "Daily drawdown limit hit"

    return True, "OK"


# ── Execute on Alpaca Paper ───────────────────────────────────
def execute_paper_trade(plan: dict) -> Optional[dict]:
    assert PAPER_ONLY, "PAPER ONLY"

    valid, reason = validate_entry(plan)
    if not valid:
        log.info(f"Rejected — {plan.get('symbol')}: {reason}")
        return None

    symbol = plan["symbol"]
    sl     = plan["stop_loss"]
    tp2    = plan["take_profit_2"]

    current = get_current_price(symbol)
    actual_entry = current if current else plan["entry"]

    account = get_account()
    equity  = float(account.get("equity", PORTFOLIO)) if account else PORTFOLIO

    pos = calc_position(actual_entry, sl, equity)
    if pos["shares"] == 0:
        log.warning(f"Position size 0 for {symbol}")
        return None

    # Submit bracket order to Alpaca Paper
    order_data = {
        "symbol":        symbol,
        "qty":           str(pos["shares"]),
        "side":          "buy",
        "type":          "market",
        "time_in_force": "day",
        "order_class":   "bracket",
        "stop_loss":     {"stop_price": str(round(sl - 0.05, 2))},
        "take_profit":   {"limit_price": str(round(tp2, 2))},
    }

    order = alpaca_post("/v2/orders", order_data)
    if not order:
        log.error(f"Order failed for {symbol}")
        return None

    order_id = order.get("id", "")

    trade = {
        "trade_id":       f"PT_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "order_id":       order_id,
        "plan_id":        plan.get("plan_id", ""),
        "symbol":         symbol,
        "trade_type":     plan.get("trade_type", "SWING"),
        "direction":      "LONG",
        "status":         "EXECUTED",
        "entry_price":    round(actual_entry, 2),
        "entry_time":     datetime.now().isoformat(),
        "shares":         pos["shares"],
        "position_value": round(pos["shares"] * actual_entry, 2),
        "stop_loss":      sl,
        "take_profit_1":  plan.get("take_profit_1", tp2),
        "take_profit_2":  tp2,
        "take_profit_3":  plan.get("take_profit_3", tp2),
        "risk_per_share": round(actual_entry - sl, 2),
        "max_risk_usd":   pos["risk_usd"],
        "current_price":  round(actual_entry, 2),
        "unrealized_pnl": 0.0,
        "unrealized_pct": 0.0,
        "realized_pnl":   0.0,
        "exit_price":     0.0,
        "exit_time":      "",
        "exit_reason":    "",
        "execution_score":plan.get("execution_score", 0),
        "regime":         plan.get("regime", ""),
        "setup":          plan.get("setup", ""),
        "alpaca_order_id":order_id,
    }

    trades = load_trades()
    trades[trade["trade_id"]] = trade
    save_trades(trades)

    log.info(f"✅ ORDER ON ALPACA PAPER: {symbol} x{pos['shares']} | {order_id[:8]}")

    _send_telegram(
        f"📋 <b>PAPER ORDER — ALPACA</b>\n"
        f"{'━'*28}\n"
        f"🏷 <b>{symbol}</b> | {trade['trade_type']} LONG\n"
        f"📐 Shares:  {pos['shares']:,}\n"
        f"💰 Entry:   <code>~${actual_entry:.2f}</code>\n"
        f"🛑 Stop:    <code>${sl:.2f}</code>\n"
        f"🎯 Target:  <code>${tp2:.2f}</code>\n"
        f"💸 Risk:    ${pos['risk_usd']:,.0f}\n"
        f"⚡ Score:   {plan.get('execution_score',0)}/100\n"
        f"🆔 <code>{order_id[:20]}</code>\n"
        f"{'━'*28}\n"
        f"⚠️ <i>PAPER ONLY — ALPACA PAPER API</i>"
    )

    return trade


# ── Sync with Alpaca ──────────────────────────────────────────
def sync_with_alpaca():
    """Sync local records with Alpaca Paper positions."""
    positions = get_positions()
    trades    = load_trades()
    perf      = load_performance()
    updated   = False

    pos_map = {p["symbol"]: p for p in positions}

    for tid, trade in trades.items():
        if trade["status"] not in ("EXECUTED", "ACTIVE"):
            continue

        symbol = trade["symbol"]

        if symbol in pos_map:
            pos = pos_map[symbol]
            trade["current_price"]  = round(float(pos.get("current_price", trade["entry_price"])), 2)
            trade["unrealized_pnl"] = round(float(pos.get("unrealized_pl", 0)), 2)
            trade["unrealized_pct"] = round(float(pos.get("unrealized_plpc", 0)) * 100, 2)
            trade["status"]         = "ACTIVE"
            trades[tid]             = trade
            updated = True
        else:
            # Check if closed
            closed_orders = alpaca_get(f"/v2/orders?status=closed&symbols={symbol}&limit=5")
            if isinstance(closed_orders, list):
                for order in closed_orders:
                    if (order.get("status") == "filled" and
                            order.get("side") == "sell"):
                        exit_price = float(order.get("filled_avg_price", 0) or 0)
                        if exit_price > 0:
                            realized = (exit_price - trade["entry_price"]) * trade["shares"]
                            pct      = (exit_price - trade["entry_price"]) / trade["entry_price"] * 100
                            reason   = ("TP_HIT" if exit_price >= trade["take_profit_2"] * 0.99
                                        else "SL_HIT" if exit_price <= trade["stop_loss"] * 1.01
                                        else "CLOSED")

                            trade.update({
                                "status": reason, "exit_price": round(exit_price, 2),
                                "exit_time": datetime.now().isoformat(),
                                "realized_pnl": round(realized, 2),
                                "realized_pct": round(pct, 2),
                                "exit_reason": reason, "unrealized_pnl": 0.0,
                            })
                            trades[tid] = trade
                            _update_performance(perf, trade, realized, pct)
                            updated = True

                            emoji = "🏆" if reason == "TP_HIT" else "🔴"
                            _send_telegram(
                                f"{emoji} <b>PAPER CLOSED — {reason}</b>\n"
                                f"🏷 {symbol} | ${realized:+.2f} ({pct:+.2f}%)\n"
                                f"⚠️ <i>PAPER ONLY</i>"
                            )
                            break

    if updated:
        save_trades(trades)
        save_performance(perf)


def _update_performance(perf: dict, trade: dict, realized: float, pct: float):
    perf["total_trades"] = perf.get("total_trades", 0) + 1
    perf["total_pnl"]    = round(perf.get("total_pnl", 0) + realized, 2)
    today = datetime.now().strftime("%Y-%m-%d")
    daily = perf.get("daily_pnl", {})
    daily[today] = round(daily.get(today, 0) + realized, 2)
    perf["daily_pnl"] = daily
    if realized > 0: perf["wins"] = perf.get("wins", 0) + 1
    else:            perf["losses"] = perf.get("losses", 0) + 1
    eq = perf.get("equity_curve", [])
    eq.append({"ts": datetime.now().isoformat(),
                "equity": round(PORTFOLIO + perf["total_pnl"], 2),
                "pnl": realized, "symbol": trade["symbol"]})
    perf["equity_curve"] = eq[-200:]
    if perf["total_pnl"] < perf.get("max_drawdown", 0):
        perf["max_drawdown"] = perf["total_pnl"]
    if not perf.get("best_trade") or realized > perf["best_trade"].get("pnl", 0):
        perf["best_trade"] = {"symbol": trade["symbol"], "pnl": realized, "pct": pct}
    if not perf.get("worst_trade") or realized < perf["worst_trade"].get("pnl", 0):
        perf["worst_trade"] = {"symbol": trade["symbol"], "pnl": realized, "pct": pct}
    regime = trade.get("regime", "UNKNOWN")
    rp = perf.get("regime_perf", {})
    rp.setdefault(regime, {"trades": 0, "wins": 0, "pnl": 0.0})
    rp[regime]["trades"] += 1
    rp[regime]["pnl"] = round(rp[regime]["pnl"] + realized, 2)
    if realized > 0: rp[regime]["wins"] += 1
    perf["regime_perf"] = rp
    if daily.get(today, 0) < -(PORTFOLIO * DAILY_DD_LIMIT):
        activate_kill_switch(f"Daily DD: ${daily.get(today,0):.0f}")


# ── Scanner ───────────────────────────────────────────────────
def scan_and_execute():
    if is_kill_switch_active() or not is_market_open():
        return
    try:
        import json, os
        plans_path = "/root/logs/trade_plans.json"
        if not os.path.exists(plans_path):
            return
        with open(plans_path) as f:
            plans = json.load(f)
    except Exception:
        return

    trades   = load_trades()
    executed = {t["plan_id"] for t in trades.values()
                if t["status"] not in ("SL_HIT","TP_HIT","CLOSED","EXPIRED")}

    for pid, plan in plans.items():
        if pid in executed: continue
        if plan.get("status") != "READY": continue
        _thr, _reg = get_dynamic_threshold()
        _score = float(plan.get("execution_score", plan.get("score", 0)))
        if _score < _thr:
            _log_rejection(plan.get("symbol","?"), _score, _thr, _reg)
            continue
        trade = execute_paper_trade(plan)
        if trade:
            time.sleep(3)


# ── Main ──────────────────────────────────────────────────────
def run_paper_engine():
    log.info("⚠️ PAPER ENGINE STARTED — ALPACA PAPER API")
    acc = get_account()
    if not acc:
        log.error("Cannot connect to Alpaca Paper API")
        return
    equity = float(acc.get("equity", 0))
    log.info(f"Alpaca Paper: ${equity:,.2f}")
    _send_telegram(
        f"📋 <b>PAPER ENGINE — ALPACA PAPER</b>\n"
        f"Equity: ${equity:,.2f}\n"
        f"⚠️ <i>PAPER ONLY — No Real Money</i>"
    )
    cycle = 0
    while True:
        try:
            if not is_kill_switch_active():
                sync_with_alpaca()
                if cycle % 6 == 0:
                    scan_and_execute()
            cycle += 1
        except Exception:
            log.error("Engine error", exc_info=True)
        time.sleep(300)


if __name__ == "__main__":
    import sys
    if "--status" in sys.argv:
        acc = get_account()
        if acc:
            print(f"✅ Alpaca Paper: ${float(acc.get('equity',0)):,.2f}")
            for p in get_positions():
                print(f"  {p['symbol']}: {p['qty']} | PnL:${float(p.get('unrealized_pl',0)):+.2f}")
        else:
            print("❌ Cannot connect")
    elif "--scan"   in sys.argv: scan_and_execute()
    elif "--sync"   in sys.argv: sync_with_alpaca(); print("Synced")
    elif "--kill"   in sys.argv: activate_kill_switch("Manual")
    elif "--unkill" in sys.argv: deactivate_kill_switch(); print("OFF")
    else: run_paper_engine()
