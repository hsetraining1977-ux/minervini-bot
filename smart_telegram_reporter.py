#!/usr/bin/env python3
"""
smart_telegram_reporter.py
Replaces minute-by-minute scanner spam with:
- Hourly summaries during market hours
- Event-driven alerts only (trade, stop, regime shift, kill switch)
- Silence during market closed / weekend / holiday
"""

import os, json, logging, time, threading
from datetime import datetime, timedelta
from typing import Optional
from collections import defaultdict

log = logging.getLogger(__name__)

# ── Telegram config (reads from .env) ────────────────────────────────────
def _get_telegram_config():
    token   = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    return token, chat_id

def _send_telegram(message: str, parse_mode: str = "HTML") -> bool:
    """Low-level Telegram send."""
    try:
        import requests
        token, chat_id = _get_telegram_config()
        if not token or not chat_id:
            log.warning("Telegram not configured")
            return False
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        r = requests.post(url, json={
            "chat_id":    chat_id,
            "text":       message,
            "parse_mode": parse_mode,
        }, timeout=10)
        return r.status_code == 200
    except Exception as e:
        log.error(f"Telegram send error: {e}")
        return False


# ── Scan aggregator ───────────────────────────────────────────────────────
class ScanAggregator:
    """Aggregates scanner results within a time window."""

    def __init__(self):
        self.reset()
        self._lock = threading.Lock()

    def reset(self):
        self.scans_executed  = 0
        self.setups_found    = 0
        self.symbols_seen    = defaultdict(int)
        self.best_setups     = defaultdict(int)
        self.trades_executed = 0
        self.window_start    = datetime.utcnow()

    def add_scan(self, result: dict):
        with self._lock:
            self.scans_executed += 1
            setups = result.get("setups", [])
            self.setups_found += len(setups)
            for s in setups:
                sym   = s.get("symbol", "")
                setup = s.get("setup_type", s.get("pattern", ""))
                if sym:
                    self.symbols_seen[sym] += 1
                if setup:
                    self.best_setups[setup] += 1

    def add_trade(self):
        with self._lock:
            self.trades_executed += 1

    def get_summary(self) -> dict:
        with self._lock:
            top_symbols = sorted(
                self.symbols_seen.items(), key=lambda x: x[1], reverse=True
            )[:5]
            top_setups = sorted(
                self.best_setups.items(), key=lambda x: x[1], reverse=True
            )[:3]
            elapsed = (datetime.utcnow() - self.window_start).total_seconds() / 60
            return {
                "scans_executed":  self.scans_executed,
                "setups_found":    self.setups_found,
                "top_symbols":     [s for s, _ in top_symbols],
                "top_setups":      [s for s, _ in top_setups],
                "trades_executed": self.trades_executed,
                "window_minutes":  round(elapsed, 1),
            }


# ── Smart reporter ────────────────────────────────────────────────────────
class SmartTelegramReporter:
    """
    Professional event-driven Telegram reporter.
    Replaces per-scan messages with hourly summaries + critical alerts.
    """

    HOURLY_INTERVAL = 3600   # seconds between summaries

    def __init__(self):
        self.aggregator      = ScanAggregator()
        self._last_summary   = datetime.utcnow() - timedelta(hours=2)
        self._last_heartbeat = datetime.utcnow() - timedelta(hours=2)
        self._lock           = threading.Lock()
        self._started        = False

    # ── Public API ────────────────────────────────────────────────────────

    def record_scan(self, scan_result: dict):
        """Call this every time the scanner runs — does NOT send Telegram."""
        self.aggregator.add_scan(scan_result)

    def maybe_send_hourly_summary(self, session_state: str, regime: str,
                                   breadth: float = None, vix: float = None):
        """Call this every minute. Sends summary only when interval elapsed + market open."""
        from market_session_manager import should_send_telegram_summary
        if not should_send_telegram_summary(session_state):
            return
        with self._lock:
            elapsed = (datetime.utcnow() - self._last_summary).total_seconds()
            if elapsed < self.HOURLY_INTERVAL:
                return
            self._last_summary = datetime.utcnow()

        summary = self.aggregator.get_summary()
        self.aggregator.reset()
        self._send_hourly_summary(summary, regime, breadth, vix, session_state)

    def send_heartbeat(self, session_state: str):
        """Sends a heartbeat every 2 hours when market is closed."""
        from market_session_manager import SessionState
        if session_state not in (
            SessionState.MARKET_CLOSED,
            SessionState.WEEKEND,
            SessionState.HOLIDAY
        ):
            return
        with self._lock:
            elapsed = (datetime.utcnow() - self._last_heartbeat).total_seconds()
            if elapsed < 7200:
                return
            self._last_heartbeat = datetime.utcnow()

        self._send_heartbeat(session_state)

    # ── Critical event alerts (always send immediately) ───────────────────

    def alert_trade_executed(self, symbol: str, direction: str, price: float,
                              quantity: int, setup: str, regime: str,
                              score: float = None, rr: float = None):
        self.aggregator.add_trade()
        lines = [
            "🚀 <b>TRADE EXECUTED</b>",
            f"Symbol:   <b>{symbol}</b>",
            f"Direction: {direction}",
            f"Price:    ${price:.2f}",
            f"Quantity: {quantity} shares",
            f"Setup:    {setup}",
            f"Regime:   {regime}",
        ]
        if score:  lines.append(f"Score:    {score:.1f}/100")
        if rr:     lines.append(f"R:R Ratio: {rr:.1f}:1")
        lines.append(f"\n⏰ {datetime.utcnow().strftime('%H:%M UTC')}")
        _send_telegram("\n".join(lines))

    def alert_stop_hit(self, symbol: str, entry: float, stop: float,
                        loss_pct: float, loss_usd: float):
        _send_telegram(
            f"🛑 <b>STOP LOSS HIT</b>\n"
            f"Symbol:  <b>{symbol}</b>\n"
            f"Entry:   ${entry:.2f}\n"
            f"Stop:    ${stop:.2f}\n"
            f"Loss:    -${loss_usd:.2f} ({loss_pct:.1f}%)\n"
            f"⏰ {datetime.utcnow().strftime('%H:%M UTC')}"
        )

    def alert_target_hit(self, symbol: str, entry: float, target: float,
                          gain_pct: float, gain_usd: float):
        _send_telegram(
            f"🎯 <b>TARGET HIT</b> 🎉\n"
            f"Symbol:  <b>{symbol}</b>\n"
            f"Entry:   ${entry:.2f}\n"
            f"Target:  ${target:.2f}\n"
            f"Gain:    +${gain_usd:.2f} (+{gain_pct:.1f}%)\n"
            f"⏰ {datetime.utcnow().strftime('%H:%M UTC')}"
        )

    def alert_regime_shift(self, old_regime: str, new_regime: str,
                            confidence: float, breadth: float = None):
        emoji = "🚀" if "RISK_ON" in new_regime else "⚠️" if "NEUTRAL" in new_regime else "🔴"
        msg = (
            f"{emoji} <b>REGIME SHIFT</b>\n"
            f"From: {old_regime}\n"
            f"To:   <b>{new_regime}</b>\n"
            f"Confidence: {confidence:.0%}\n"
        )
        if breadth:
            msg += f"Breadth: {breadth:.1f}\n"
        msg += f"⏰ {datetime.utcnow().strftime('%H:%M UTC')}"
        _send_telegram(msg)

    def alert_kill_switch(self, reason: str, portfolio_value: float,
                           drawdown_pct: float):
        _send_telegram(
            f"🚨 <b>KILL SWITCH ACTIVATED</b> 🚨\n"
            f"Reason:    {reason}\n"
            f"Portfolio: ${portfolio_value:,.2f}\n"
            f"Drawdown:  -{drawdown_pct:.1f}%\n"
            f"All positions being closed.\n"
            f"⏰ {datetime.utcnow().strftime('%H:%M UTC')}"
        )

    def alert_system_error(self, component: str, error: str):
        _send_telegram(
            f"🔴 <b>SYSTEM ERROR</b>\n"
            f"Component: {component}\n"
            f"Error: {error[:200]}\n"
            f"⏰ {datetime.utcnow().strftime('%H:%M UTC')}"
        )

    def alert_session_open(self, regime: str, breadth: float, vix: float,
                            best_setups: list, liquidity: str):
        setups_str = " · ".join(best_setups[:3]) if best_setups else "N/A"
        _send_telegram(
            f"🔔 <b>MARKET OPEN</b>\n"
            f"Regime:    <b>{regime}</b>\n"
            f"Breadth:   {breadth:.1f}\n"
            f"VIX:       {vix:.1f}\n"
            f"Liquidity: {liquidity}\n"
            f"Best Setups: {setups_str}\n"
            f"⏰ {datetime.utcnow().strftime('%H:%M UTC')}"
        )

    def alert_session_close(self, regime: str, trades: int,
                             pnl_usd: float, pnl_pct: float):
        emoji = "🟢" if pnl_usd >= 0 else "🔴"
        _send_telegram(
            f"🔕 <b>MARKET CLOSE</b>\n"
            f"Regime:  {regime}\n"
            f"Trades:  {trades}\n"
            f"P&L:     {emoji} ${pnl_usd:+.2f} ({pnl_pct:+.1f}%)\n"
            f"⏰ {datetime.utcnow().strftime('%H:%M UTC')}"
        )

    # ── Private senders ───────────────────────────────────────────────────

    def _send_hourly_summary(self, summary: dict, regime: str,
                              breadth: float, vix: float, session: str):
        top_syms  = "\n".join(f"  • {s}" for s in summary["top_symbols"]) or "  None"
        top_setup = summary["top_setups"][0] if summary["top_setups"] else "N/A"

        msg = (
            f"📊 <b>MINERVINI AI — HOURLY SUMMARY</b>\n"
            f"{'='*32}\n"
            f"Scans:      {summary['scans_executed']}\n"
            f"Setups:     {summary['setups_found']}\n"
            f"Best Setup: {top_setup}\n"
        )
        if summary["top_symbols"]:
            msg += f"\nTop Symbols:\n{top_syms}\n"

        msg += (
            f"\nRegime: <b>{regime}</b>\n"
        )
        if breadth: msg += f"Breadth: {breadth:.1f}\n"
        if vix:     msg += f"VIX: {vix:.1f}\n"

        if summary["trades_executed"]:
            msg += f"\n✅ Trades: {summary['trades_executed']}\n"
        else:
            msg += f"\n— No trades this hour —\n"

        msg += f"\n⏰ {datetime.utcnow().strftime('%H:%M UTC')}"
        _send_telegram(msg)

    def _send_heartbeat(self, session_state: str):
        from market_session_manager import get_full_status
        status = get_full_status()
        _send_telegram(
            f"💤 <b>SYSTEM HEARTBEAT</b>\n"
            f"Status:   {session_state}\n"
            f"Next Open: {status.get('next_open_et','?')}\n"
            f"({status.get('hours_to_open','?')}h away)\n"
            f"All systems nominal.\n"
            f"⏰ {datetime.utcnow().strftime('%H:%M UTC')}"
        )


# ── Singleton ─────────────────────────────────────────────────────────────
_reporter = SmartTelegramReporter()

def get_reporter() -> SmartTelegramReporter:
    return _reporter


# ── CLI test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Testing Smart Telegram Reporter...")
    r = get_reporter()

    # Simulate 5 scans
    for i in range(5):
        r.record_scan({
            "setups": [
                {"symbol": "NVDA", "setup_type": "ORB_BREAKOUT"},
                {"symbol": "ARM",  "setup_type": "TIGHT_CONSOLIDATION_BREAK"},
            ]
        })

    summary = r.aggregator.get_summary()
    print(f"Aggregated: {summary}")
    print("✅ SmartTelegramReporter ready")
    print("   Alerts: alert_trade_executed(), alert_stop_hit(), alert_regime_shift()")
    print("   Summary: maybe_send_hourly_summary() — call every minute")
