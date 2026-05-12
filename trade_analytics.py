"""
trade_analytics.py
TRADE ANALYTICS ENGINE
Minervini Bot — PAPER TRADING ONLY
Calculates all performance metrics from trade history.
"""

import json, os, math, datetime, logging
from typing import Optional

log = logging.getLogger("trade_analytics")
DATA_DIR   = "/root/logs"
PAPER_ONLY = True
PORTFOLIO  = 50_000.0

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
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        log.error(f"Save error: {e}")

# ── Load all closed trades ────────────────────────────────────────────────────
def load_closed_trades() -> list:
    """Load all closed trades from journal."""
    journal = _load(f"{DATA_DIR}/trade_journal_v2.json", [])
    paper   = _load(f"{DATA_DIR}/paper_trades.json", {})

    trades = []

    # From journal
    for t in journal:
        if t.get("exit_price") and t.get("entry_price"):
            trades.append(t)

    # From paper_trades if not in journal
    journal_ids = {t.get("trade_id","") for t in trades}
    for tid, t in paper.items():
        if t.get("status") in ("CLOSED","SL_HIT","TP_HIT","PARTIAL_EXIT"):
            if tid not in journal_ids:
                entry = float(t.get("entry_price", 0))
                exit_p= float(t.get("exit_price", 0))
                shares= int(t.get("shares", 0))
                pnl   = round((exit_p - entry) * shares, 2) if exit_p else 0
                trades.append({
                    "trade_id":      tid,
                    "symbol":        t.get("symbol",""),
                    "pnl":           pnl,
                    "entry_price":   entry,
                    "exit_price":    exit_p,
                    "shares":        shares,
                    "market_regime": t.get("market_regime","NEUTRAL"),
                    "setup_type":    t.get("setup_type","SWING"),
                    "exit_reason":   t.get("exit_reason","MANUAL"),
                    "duration_mins": t.get("duration_mins", 0),
                    "mfe":           t.get("mfe", 0),
                    "mae":           t.get("mae", 0),
                    "closed_at":     t.get("closed_at",""),
                })

    return trades

# ══════════════════════════════════════════════════════════════════════════════
# CORE METRICS
# ══════════════════════════════════════════════════════════════════════════════
def calc_core_metrics(trades: list) -> dict:
    if not trades:
        return {"total_trades": 0, "message": "No closed trades yet"}

    pnls    = [float(t.get("pnl", 0)) for t in trades]
    wins    = [p for p in pnls if p > 0]
    losses  = [p for p in pnls if p <= 0]
    total   = len(trades)

    win_rate    = len(wins) / total * 100 if total else 0
    avg_win     = sum(wins) / len(wins)     if wins   else 0
    avg_loss    = sum(losses) / len(losses) if losses else 0
    expectancy  = (win_rate/100 * avg_win) + ((1-win_rate/100) * avg_loss)
    profit_factor = abs(sum(wins) / sum(losses)) if losses and sum(losses) != 0 else float("inf")

    # Sharpe (simplified daily returns)
    if len(pnls) > 1:
        mean_r = sum(pnls) / len(pnls)
        std_r  = math.sqrt(sum((p - mean_r)**2 for p in pnls) / len(pnls))
        sharpe = (mean_r / std_r * math.sqrt(252)) if std_r > 0 else 0
    else:
        sharpe = 0

    # Max drawdown
    equity = PORTFOLIO
    peak   = PORTFOLIO
    max_dd = 0
    for p in pnls:
        equity += p
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak * 100
        if dd > max_dd:
            max_dd = dd

    # R-multiple (assuming 1% risk per trade)
    risk_per = PORTFOLIO * 0.01
    r_multiples = [p / risk_per for p in pnls]
    avg_r = sum(r_multiples) / len(r_multiples) if r_multiples else 0

    # Hold time
    durations = [int(t.get("duration_mins", 0)) for t in trades if t.get("duration_mins")]
    avg_hold  = sum(durations) / len(durations) if durations else 0

    # Consecutive stats
    max_consec_wins   = max_consec_losses = curr = 0
    for p in pnls:
        if p > 0:
            curr = curr + 1 if curr > 0 else 1
            max_consec_wins = max(max_consec_wins, curr)
        else:
            curr = curr - 1 if curr < 0 else -1
            max_consec_losses = max(max_consec_losses, abs(curr))

    return {
        "total_trades":       total,
        "wins":               len(wins),
        "losses":             len(losses),
        "win_rate":           round(win_rate, 2),
        "total_pnl":          round(sum(pnls), 2),
        "avg_win":            round(avg_win, 2),
        "avg_loss":           round(avg_loss, 2),
        "expectancy":         round(expectancy, 2),
        "profit_factor":      round(profit_factor, 3),
        "sharpe_ratio":       round(sharpe, 3),
        "max_drawdown_pct":   round(max_dd, 2),
        "avg_r_multiple":     round(avg_r, 3),
        "avg_hold_mins":      round(avg_hold, 1),
        "max_consec_wins":    max_consec_wins,
        "max_consec_losses":  max_consec_losses,
        "best_trade":         max(pnls) if pnls else 0,
        "worst_trade":        min(pnls) if pnls else 0,
        "paper_only":         True,
        "calculated_at":      datetime.datetime.now().isoformat(),
    }

# ══════════════════════════════════════════════════════════════════════════════
# BREAKDOWNS
# ══════════════════════════════════════════════════════════════════════════════
def calc_breakdowns(trades: list) -> dict:
    """PnL breakdowns by regime, sector, setup, symbol."""

    def _group(key, default="OTHER"):
        result = {}
        for t in trades:
            k   = str(t.get(key, default)).upper()
            pnl = float(t.get("pnl", 0))
            if k not in result:
                result[k] = {"trades": 0, "pnl": 0, "wins": 0, "losses": 0}
            result[k]["trades"] += 1
            result[k]["pnl"]    += pnl
            if pnl > 0: result[k]["wins"]   += 1
            else:        result[k]["losses"] += 1
        for k in result:
            t_count = result[k]["trades"]
            result[k]["win_rate"] = round(result[k]["wins"]/t_count*100, 1) if t_count else 0
            result[k]["pnl"]      = round(result[k]["pnl"], 2)
        return result

    # Symbol breakdown
    sym_pnl = {}
    for t in trades:
        sym = t.get("symbol","?")
        pnl = float(t.get("pnl",0))
        sym_pnl[sym] = round(sym_pnl.get(sym, 0) + pnl, 2)

    # Daily PnL
    daily_pnl = {}
    for t in trades:
        closed = str(t.get("closed_at",""))[:10]
        if closed:
            pnl = float(t.get("pnl",0))
            daily_pnl[closed] = round(daily_pnl.get(closed, 0) + pnl, 2)

    # Equity curve
    equity  = PORTFOLIO
    eq_curve= [{"date": "start", "equity": equity}]
    for t in sorted(trades, key=lambda x: x.get("closed_at","")):
        equity += float(t.get("pnl", 0))
        eq_curve.append({
            "date":   str(t.get("closed_at",""))[:10],
            "equity": round(equity, 2),
            "symbol": t.get("symbol",""),
            "pnl":    float(t.get("pnl",0)),
        })

    sorted_syms = sorted(sym_pnl.items(), key=lambda x: x[1], reverse=True)

    return {
        "by_regime":    _group("market_regime"),
        "by_setup":     _group("setup_type"),
        "by_exit":      _group("exit_reason"),
        "by_symbol":    sym_pnl,
        "best_symbols": dict(sorted_syms[:5]),
        "worst_symbols":dict(sorted_syms[-5:]),
        "daily_pnl":    daily_pnl,
        "equity_curve": eq_curve,
        "paper_only":   True,
    }

# ══════════════════════════════════════════════════════════════════════════════
# FULL ANALYTICS SNAPSHOT
# ══════════════════════════════════════════════════════════════════════════════
def run_analytics() -> dict:
    trades    = load_closed_trades()
    core      = calc_core_metrics(trades)
    breakdowns= calc_breakdowns(trades)

    snapshot = {**core, **breakdowns, "trade_count": len(trades)}
    _save(f"{DATA_DIR}/analytics_snapshot.json", snapshot)
    log.info(
        f"Analytics: {core.get('total_trades',0)} trades | "
        f"WR={core.get('win_rate',0):.1f}% | "
        f"PF={core.get('profit_factor',0):.2f} | "
        f"PnL=${core.get('total_pnl',0):.2f}"
    )
    return snapshot

def get_analytics() -> dict:
    return _load(f"{DATA_DIR}/analytics_snapshot.json", {})
