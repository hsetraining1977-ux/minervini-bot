#!/usr/bin/env python3
"""
Master AI Orchestrator
=======================
العقل المركزي للنظام — Intelligence Only, No Execution
"""

import json, time, os, sys
from datetime import datetime
import yfinance as yf
import pytz

sys.path.insert(0, '/root')

ET = pytz.timezone('America/New_York')

# ===== Telegram =====

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
def send_telegram(msg):
    try:
        import requests
        from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                      json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
                      timeout=10)
    except Exception as e:
        print(f"[TG ERROR] {e}")

def load_json(path, default={}):
    try:
        with open(path) as f: return json.load(f)
    except: return default

# ===========================================================
# 1) READ MARKET STATE
# ===========================================================
def read_market_state() -> dict:
    print("[Orchestrator] Reading market state...")

    # Event Awareness
    event_state = load_json("/root/event_state.json", {"mode": "normal", "lockdown": False})
    event_lockdown = event_state.get("lockdown", False)

    # Macro Intelligence
    macro = load_json("/root/macro_state.json", {"action": "SELECTIVE", "score": 0})
    macro_action = macro.get("action", "SELECTIVE")

    # Institutional Layer
    cross  = load_json("/root/cross_asset_state.json", {"cross_signal": "NEUTRAL", "risk_score": 50})
    liq    = load_json("/root/liquidity_state.json",   {"regime": "NEUTRAL", "liquidity_score": 50})
    psych  = load_json("/root/psychology_state.json",  {"market_state": "NEUTRAL", "fear_score": 50, "vix": 20})

    # Live SPY Data
    spy_above_vwap = False
    spy_momentum   = 0.0
    vix_level      = psych.get("vix", 20)

    try:
        spy_data = yf.Ticker("SPY").history(period="1d", interval="5m")
        if not spy_data.empty:
            spy_price = float(spy_data["Close"].iloc[-1])
            spy_open  = float(spy_data["Open"].iloc[0])
            tp  = (spy_data["High"] + spy_data["Low"] + spy_data["Close"]) / 3
            tpv = tp * spy_data["Volume"]
            vwap = float((tpv.cumsum() / spy_data["Volume"].cumsum()).iloc[-1])
            spy_above_vwap = spy_price > vwap
            spy_momentum   = (spy_price - spy_open) / spy_open * 100
    except Exception as e:
        print(f"[Orchestrator] SPY fetch error: {e}")

    try:
        vix_data  = yf.Ticker("^VIX").history(period="1d")
        if not vix_data.empty:
            vix_level = float(vix_data["Close"].iloc[-1])
    except: pass

    # Determine Market Regime
    risk_score = 50
    if cross.get("cross_signal") == "RISK_ON":    risk_score += 20
    elif cross.get("cross_signal") == "RISK_OFF": risk_score -= 20
    if liq.get("regime") == "EXPANDING":          risk_score += 15
    elif liq.get("regime") == "CONTRACTING":      risk_score -= 15
    if spy_above_vwap:                             risk_score += 10
    if spy_momentum > 0.3:                         risk_score += 5
    elif spy_momentum < -0.3:                      risk_score -= 10
    if vix_level > 30:                             risk_score -= 25
    elif vix_level < 18:                           risk_score += 10

    risk_score = max(0, min(100, risk_score))

    if risk_score >= 65:   market_regime = "RISK_ON"
    elif risk_score >= 40: market_regime = "NEUTRAL"
    else:                  market_regime = "RISK_OFF"

    return {
        "market_regime":   market_regime,
        "risk_score":      risk_score,
        "spy_above_vwap":  spy_above_vwap,
        "spy_momentum":    round(spy_momentum, 2),
        "vix_level":       round(vix_level, 1),
        "event_lockdown":  event_lockdown,
        "macro_action":    macro_action,
        "cross_signal":    cross.get("cross_signal", "NEUTRAL"),
        "liquidity":       liq.get("regime", "NEUTRAL"),
        "psychology":      psych.get("market_state", "NEUTRAL"),
    }

# ===========================================================
# 2) SELECT OPERATING MODE
# ===========================================================
def select_mode(state: dict) -> str:
    vix        = state["vix_level"]
    regime     = state["market_regime"]
    spy_vwap   = state["spy_above_vwap"]
    spy_mom    = state["spy_momentum"]
    lockdown   = state["event_lockdown"]
    liquidity  = state["liquidity"]

    # Safety Override
    if lockdown or vix > 30 or (not spy_vwap and spy_mom < -1.0):
        return "DEFENSIVE"

    # Aggressive Intraday
    if (regime == "RISK_ON" and spy_vwap and vix < 20
            and spy_mom > 0.2 and liquidity in ["EXPANDING", "NEUTRAL"]):
        return "AGGRESSIVE_INTRADAY"

    # Swing Focus
    if regime in ["RISK_ON", "NEUTRAL"] and vix < 25:
        return "SWING_FOCUS"

    return "DEFENSIVE"

# ===========================================================
# 3) CAPITAL ALLOCATION
# ===========================================================
def get_capital_allocation(mode: str) -> dict:
    allocations = {
        "AGGRESSIVE_INTRADAY": {
            "intraday": 0.60, "swing": 0.40, "cash": 0.00,
            "description": "60% Intraday | 40% Swing"
        },
        "SWING_FOCUS": {
            "intraday": 0.20, "swing": 0.80, "cash": 0.00,
            "description": "80% Swing | 20% Intraday"
        },
        "DEFENSIVE": {
            "intraday": 0.00, "swing": 0.20, "cash": 0.80,
            "description": "80% Cash | 20% Defensive Watchlist"
        },
    }
    return allocations.get(mode, allocations["DEFENSIVE"])

# ===========================================================
# 4) RUN ENGINES
# ===========================================================
INTRADAY_SYMBOLS = ["NVDA","AMD","TSLA","AAPL","META","MSFT","AVGO","SMCI","GOOGL","AMZN"]
SWING_SYMBOLS    = ["NVDA","MSFT","AAPL","GOOGL","AVGO","LLY","UNH","V","MA","JPM"]

def run_intraday_engine() -> list:
    try:
        from intraday_engine import scan_intraday_opportunities
        results = scan_intraday_opportunities(INTRADAY_SYMBOLS)
        hot = [r for r in results if r["rating"] in ["HOT", "STRONG"]]
        return sorted(hot, key=lambda x: x["score"], reverse=True)[:5]
    except Exception as e:
        print(f"[Orchestrator] Intraday engine error: {e}")
        return []

def run_swing_engine() -> list:
    try:
        from decision_engine import should_buy
        results = []
        for symbol in SWING_SYMBOLS:
            try:
                r = should_buy(symbol)
                if r.get("allowed") and r.get("score_pct", 0) >= 60:
                    results.append({
                        "symbol":    symbol,
                        "score_pct": r.get("score_pct", 0),
                        "rating":    r.get("rating", "UNKNOWN"),
                        "size_pct":  r.get("position_size_pct", 0),
                        "size_usd":  r.get("position_size_dollars", 0),
                    })
            except: pass
        return sorted(results, key=lambda x: x["score_pct"], reverse=True)[:5]
    except Exception as e:
        print(f"[Orchestrator] Swing engine error: {e}")
        return []

# ===========================================================
# 5) SAFETY CHECKS
# ===========================================================
def run_safety_checks(state: dict) -> list:
    warnings = []
    if state["event_lockdown"]:
        warnings.append("🔴 Event Lockdown active — no new trades")
    if state["vix_level"] > 30:
        warnings.append(f"🔴 VIX={state['vix_level']} — extreme fear")
    elif state["vix_level"] > 25:
        warnings.append(f"🟡 VIX={state['vix_level']} — elevated volatility")
    if not state["spy_above_vwap"]:
        warnings.append("🟡 SPY below VWAP — caution")
    if state["spy_momentum"] < -1.0:
        warnings.append(f"🔴 SPY momentum {state['spy_momentum']:+.2f}% — weak market")
    if state["liquidity"] == "CONTRACTING":
        warnings.append("🟡 Liquidity contracting")
    if state["psychology"] == "EUPHORIC":
        warnings.append("⚠️ Market EUPHORIC — risk of reversal")
    return warnings

# ===========================================================
# 6) SAVE TO DATABASE
# ===========================================================
def save_to_database(result: dict):
    try:
        from database import insert_market_snapshot
        insert_market_snapshot({
            "market_regime": result["market_regime"],
            "risk_on": result["market_regime"] == "RISK_ON",
            "vix": result["state"]["vix_level"],
            "spy": None,
        })
    except Exception as e:
        print(f"[Orchestrator] DB save error: {e}")

# ===========================================================
# 7) SEND TELEGRAM REPORT
# ===========================================================
def send_orchestrator_report(result: dict):
    mode    = result["mode"]
    regime  = result["market_regime"]
    alloc   = result["capital_allocation"]
    top_i   = result["top_intraday"]
    top_s   = result["top_swing"]
    warnings= result["warnings"]

    mode_emoji = {"AGGRESSIVE_INTRADAY": "🚀", "SWING_FOCUS": "📈", "DEFENSIVE": "🛡️"}.get(mode, "🤖")
    regime_emoji = {"RISK_ON": "🟢", "NEUTRAL": "🟡", "RISK_OFF": "🔴"}.get(regime, "⚪")

    msg = f"""🧠 <b>MASTER AI ORCHESTRATOR</b>
{datetime.now(ET).strftime('%Y-%m-%d %H:%M ET')}

{mode_emoji} <b>Mode:</b> {mode}
{regime_emoji} <b>Regime:</b> {regime}
😱 <b>VIX:</b> {result['state']['vix_level']}

💰 <b>Capital Allocation:</b>
{alloc['description']}"""

    if top_i:
        msg += "\n\n🔥 <b>Top Intraday:</b>"
        for r in top_i[:3]:
            msg += f"\n  • <b>{r['symbol']}</b> | Score:{r['score']} | {r['rating']}"

    if top_s:
        msg += "\n\n📈 <b>Top Swing:</b>"
        for r in top_s[:3]:
            msg += f"\n  • <b>{r['symbol']}</b> | {r['score_pct']}% | {r['rating']}"

    if warnings:
        msg += "\n\n⚠️ <b>Warnings:</b>"
        for w in warnings:
            msg += f"\n  {w}"

    msg += "\n\n⚠️ <i>Intelligence only — No auto trading</i>"
    send_telegram(msg)

# ===========================================================
# MASTER RUN
# ===========================================================
def run_orchestrator(send_report: bool = True) -> dict:
    print("\n" + "="*55)
    print("  🧠 MASTER AI ORCHESTRATOR")
    print("="*55)
    print(f"  {datetime.now(ET).strftime('%Y-%m-%d %H:%M ET')}")
    print("="*55)

    # 1. Market State
    state = read_market_state()
    print(f"\n  Regime:  {state['market_regime']} (score:{state['risk_score']})")
    print(f"  VIX:     {state['vix_level']}")
    print(f"  SPY:     {'Above' if state['spy_above_vwap'] else 'Below'} VWAP | Mom:{state['spy_momentum']:+.2f}%")
    print(f"  Lockdown:{state['event_lockdown']}")

    # 2. Mode
    mode  = select_mode(state)
    alloc = get_capital_allocation(mode)
    print(f"\n  Mode:    {mode}")
    print(f"  Capital: {alloc['description']}")

    # 3. Safety
    warnings = run_safety_checks(state)
    if warnings:
        print("\n  ⚠️ Warnings:")
        for w in warnings: print(f"    {w}")

    # 4. Run Engines
    top_intraday = []
    top_swing    = []

    if mode == "AGGRESSIVE_INTRADAY":
        print("\n  🚀 Running Intraday Engine...")
        top_intraday = run_intraday_engine()
        print(f"  📈 Running Swing Engine...")
        top_swing = run_swing_engine()

    elif mode == "SWING_FOCUS":
        print("\n  📈 Running Swing Engine...")
        top_swing = run_swing_engine()
        if alloc["intraday"] > 0:
            print("  🔍 Running Intraday Engine (partial)...")
            top_intraday = run_intraday_engine()

    else:
        print("\n  🛡️ DEFENSIVE — No new trades")

    # 5. Print Results
    print(f"\n{'='*55}")
    print(f"  CAPITAL ALLOCATION: {alloc['description']}")

    if top_intraday:
        print(f"\n  🔥 Top Intraday ({len(top_intraday)}):")
        for r in top_intraday:
            print(f"    {r['symbol']:6s} | Score:{r['score']:5.1f} | {r['rating']}")

    if top_swing:
        print(f"\n  📈 Top Swing ({len(top_swing)}):")
        for r in top_swing:
            print(f"    {r['symbol']:6s} | {r['score_pct']:5.1f}% | {r['rating']}")

    print(f"{'='*55}\n")

    result = {
        "mode":              mode,
        "market_regime":     state["market_regime"],
        "risk_score":        state["risk_score"],
        "intraday_allowed":  mode in ["AGGRESSIVE_INTRADAY"],
        "swing_allowed":     mode in ["AGGRESSIVE_INTRADAY", "SWING_FOCUS"],
        "capital_allocation":alloc,
        "top_intraday":      top_intraday,
        "top_swing":         top_swing,
        "warnings":          warnings,
        "state":             state,
        "timestamp":         datetime.now(ET).isoformat(),
    }

    # 6. Save & Report
    save_to_database(result)
    if send_report:
        send_orchestrator_report(result)

    return result

# ===========================================================
# MAIN
# ===========================================================
if __name__ == "__main__":
    run_orchestrator(send_report=True)

if __name__ == "__main__":
    import time
    while True:
        try:
            main()
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(300)
