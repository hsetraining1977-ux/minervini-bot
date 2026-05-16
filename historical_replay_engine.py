#!/usr/bin/env python3
"""
historical_replay_engine.py
Feeds historical market data into the adaptive learning system.
Goal: boost setups_tracked from 9 → 5000+

Data sources: yfinance (free, no API key needed)
Symbols: SPY, QQQ, IWM, DIA + sector ETFs + individual leaders
"""

import os, json, logging, time, random
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [HistoricalReplay] %(message)s"
)

ADAPTIVE_DIR  = Path("/root/adaptive")
MEMORY_DIR    = Path("/root/adaptive")

# ── Symbols to replay ─────────────────────────────────────────────────────
REPLAY_SYMBOLS = {
    "indices":  ["SPY", "QQQ", "IWM", "DIA"],
    "sectors":  ["XLK", "XLF", "XLE", "XLU", "XLV", "XLY", "XLP", "XLI", "XLB", "XLRE"],
    "leaders":  [
        "NVDA", "AAPL", "MSFT", "AMZN", "META", "GOOGL", "TSLA",
        "AMD",  "AVGO", "ARM",  "SMCI", "ORCL", "CRM",  "NOW",
        "ANET", "PANW", "CRWD", "DDOG", "SNOW", "MELI",
    ],
    "vix":      ["^VIX"],
}

ALL_SYMBOLS = (
    REPLAY_SYMBOLS["indices"] +
    REPLAY_SYMBOLS["sectors"] +
    REPLAY_SYMBOLS["leaders"]
)

# ── Setup detection parameters ────────────────────────────────────────────
SETUP_RULES = {
    "ORB_BREAKOUT": {
        "description": "Opening Range Breakout",
        "conditions": lambda o,h,l,c,v,avg_v: (
            v > avg_v * 1.5 and
            c > o * 1.005 and
            (h - l) / o > 0.005
        ),
    },
    "TIGHT_CONSOLIDATION_BREAK": {
        "description": "Tight consolidation breakout",
        "conditions": lambda o,h,l,c,v,avg_v: (
            abs(c - o) / o < 0.008 and
            v > avg_v * 1.2 and
            c > o
        ),
    },
    "MOMENTUM_BURST_UP": {
        "description": "Strong upward momentum",
        "conditions": lambda o,h,l,c,v,avg_v: (
            (c - o) / o > 0.012 and
            v > avg_v * 1.8 and
            c > h * 0.98
        ),
    },
    "MOMENTUM_BURST_DOWN": {
        "description": "Strong downward momentum",
        "conditions": lambda o,h,l,c,v,avg_v: (
            (o - c) / o > 0.012 and
            v > avg_v * 1.8 and
            c < l * 1.02
        ),
    },
    "VWAP_CROSS_UP": {
        "description": "Price crosses above VWAP",
        "conditions": lambda o,h,l,c,v,avg_v: (
            o < (h+l)/2 and
            c > (h+l)/2 and
            v > avg_v * 1.1
        ),
    },
    "VWAP_CROSS_DOWN": {
        "description": "Price crosses below VWAP",
        "conditions": lambda o,h,l,c,v,avg_v: (
            o > (h+l)/2 and
            c < (h+l)/2 and
            v > avg_v * 1.1
        ),
    },
    "VOLUME_SPIKE": {
        "description": "Unusual volume spike",
        "conditions": lambda o,h,l,c,v,avg_v: (
            v > avg_v * 2.5 and
            abs(c - o) / o > 0.003
        ),
    },
    "ORB_BREAKDOWN": {
        "description": "Opening Range Breakdown",
        "conditions": lambda o,h,l,c,v,avg_v: (
            v > avg_v * 1.5 and
            c < o * 0.995 and
            (h - l) / o > 0.005
        ),
    },
    "RELATIVE_STRENGTH_LEADER": {
        "description": "Outperforming the market",
        "conditions": lambda o,h,l,c,v,avg_v: (
            (c - o) / o > 0.008 and
            v > avg_v and
            c > o
        ),
    },
}

# ── Regime classifier ─────────────────────────────────────────────────────
def classify_regime_from_data(spy_chg: float, vix: float,
                               advance_pct: float) -> str:
    """Simple regime classification from historical data."""
    if vix < 15 and spy_chg > 0.3 and advance_pct > 60:
        return "STRONG_RISK_ON"
    if vix < 20 and spy_chg > 0 and advance_pct > 50:
        return "RISK_ON"
    if vix > 30 or spy_chg < -1.5:
        return "PANIC"
    if vix > 25 or spy_chg < -0.5:
        return "RISK_OFF"
    if abs(spy_chg) < 0.3 and 18 < vix < 25:
        return "CHOPPY"
    return "NEUTRAL"

# ── Outcome estimator ─────────────────────────────────────────────────────
def estimate_outcome(setup: str, regime: str,
                     c: float, h: float, l: float,
                     next_c: float = None) -> dict:
    """Estimate trade outcome based on next day's close."""
    if next_c is None:
        # Simulate if no next day data
        if "UP" in setup or setup in ("ORB_BREAKOUT", "RELATIVE_STRENGTH_LEADER",
                                       "TIGHT_CONSOLIDATION_BREAK", "VOLUME_SPIKE"):
            win = random.random() < 0.42
        else:
            win = random.random() < 0.38

        pnl = random.uniform(0.3, 2.5) if win else random.uniform(-1.5, -0.3)
        return {"win": win, "pnl_pct": round(pnl, 3)}

    pnl_pct = (next_c - c) / c * 100
    if "DOWN" in setup or setup == "ORB_BREAKDOWN":
        pnl_pct = -pnl_pct

    win = pnl_pct > 0.2
    return {"win": win, "pnl_pct": round(pnl_pct, 3)}


# ── Main replay engine ────────────────────────────────────────────────────
class HistoricalReplayEngine:

    def __init__(self):
        self.adaptive_dir = ADAPTIVE_DIR
        self.adaptive_dir.mkdir(exist_ok=True)
        self.stats_file   = self.adaptive_dir / "setup_statistics.json"
        self.learning_file = self.adaptive_dir / "learning_history.json"
        self.stats = self._load_stats()

    def _load_stats(self) -> dict:
        if self.stats_file.exists():
            try:
                with open(self.stats_file) as f:
                    return json.load(f)
            except Exception:
                pass
        return {s: {"trades": 0, "wins": 0, "total_pnl": 0.0,
                    "by_regime": {}} for s in SETUP_RULES}

    def _save_stats(self):
        with open(self.stats_file, "w") as f:
            json.dump(self.stats, f, indent=2)

    def _record_trade(self, setup: str, regime: str,
                       win: bool, pnl_pct: float):
        if setup not in self.stats:
            self.stats[setup] = {"trades": 0, "wins": 0,
                                  "total_pnl": 0.0, "by_regime": {}}
        s = self.stats[setup]
        s["trades"]    += 1
        s["wins"]      += 1 if win else 0
        s["total_pnl"] += pnl_pct

        if regime not in s["by_regime"]:
            s["by_regime"][regime] = {"trades": 0, "wins": 0, "total_pnl": 0.0}
        r = s["by_regime"][regime]
        r["trades"]    += 1
        r["wins"]      += 1 if win else 0
        r["total_pnl"] += pnl_pct

    def replay_symbol(self, symbol: str, period: str = "2y") -> int:
        """Replay one symbol. Returns number of setups recorded."""
        try:
            import yfinance as yf
        except ImportError:
            log.error("yfinance not installed. Run: pip install yfinance --break-system-packages")
            return 0

        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval="1d")
            if df.empty or len(df) < 30:
                log.warning(f"{symbol}: insufficient data")
                return 0

            df = df.reset_index()
            count = 0

            # Calculate rolling avg volume
            df["avg_vol"] = df["Volume"].rolling(20).mean()

            for i in range(20, len(df) - 1):
                row       = df.iloc[i]
                next_row  = df.iloc[i + 1] if i + 1 < len(df) else None

                o = float(row["Open"])
                h = float(row["High"])
                l = float(row["Low"])
                c = float(row["Close"])
                v = float(row["Volume"])
                avg_v = float(row["avg_vol"]) if row["avg_vol"] > 0 else v

                if o <= 0 or c <= 0:
                    continue

                # SPY change % for regime
                spy_chg     = (c - o) / o * 100
                vix_proxy   = max(10, 20 - spy_chg * 3)   # proxy if no VIX
                advance_pct = 55 + spy_chg * 5             # proxy

                regime = classify_regime_from_data(spy_chg, vix_proxy, advance_pct)

                next_c = float(next_row["Close"]) if next_row is not None else None

                # Check each setup
                for setup_name, rule in SETUP_RULES.items():
                    try:
                        if rule["conditions"](o, h, l, c, v, avg_v):
                            outcome = estimate_outcome(
                                setup_name, regime, c, h, l, next_c
                            )
                            self._record_trade(
                                setup_name, regime,
                                outcome["win"], outcome["pnl_pct"]
                            )
                            count += 1
                    except Exception:
                        pass

            log.info(f"  {symbol}: {count} setups recorded from {len(df)} days")
            return count

        except Exception as e:
            log.warning(f"{symbol}: {e}")
            return 0

    def run_full_replay(self, period: str = "3y",
                        batch_size: int = 5,
                        delay: float = 1.0) -> dict:
        """
        Run full historical replay across all symbols.
        period: '1y', '2y', '3y', '5y'
        """
        log.info("="*55)
        log.info("HISTORICAL REPLAY ENGINE STARTING")
        log.info(f"Symbols: {len(ALL_SYMBOLS)} | Period: {period}")
        log.info("="*55)

        total_setups = 0
        processed    = 0
        failed       = []

        start_time = time.time()

        for i, symbol in enumerate(ALL_SYMBOLS):
            try:
                log.info(f"[{i+1}/{len(ALL_SYMBOLS)}] Replaying {symbol}...")
                count = self.replay_symbol(symbol, period)
                total_setups += count
                processed    += 1

                # Save every batch
                if (i + 1) % batch_size == 0:
                    self._save_stats()
                    self._update_adaptive_weights()
                    elapsed = time.time() - start_time
                    log.info(
                        f"  ── Checkpoint: {processed} symbols, "
                        f"{total_setups:,} setups | {elapsed:.0f}s elapsed"
                    )

                time.sleep(delay)   # Rate limit yfinance

            except KeyboardInterrupt:
                log.info("Replay interrupted by user")
                break
            except Exception as e:
                log.warning(f"{symbol} failed: {e}")
                failed.append(symbol)

        # Final save
        self._save_stats()
        self._update_adaptive_weights()
        self._save_learning_history(total_setups, period)

        elapsed = time.time() - start_time
        result = {
            "total_setups_recorded": total_setups,
            "symbols_processed":     processed,
            "symbols_failed":        len(failed),
            "elapsed_seconds":       round(elapsed),
            "period":                period,
            "timestamp":             datetime.utcnow().isoformat(),
        }

        log.info("="*55)
        log.info("REPLAY COMPLETE")
        log.info(f"  Total setups: {total_setups:,}")
        log.info(f"  Symbols:      {processed}/{len(ALL_SYMBOLS)}")
        log.info(f"  Time:         {elapsed:.0f}s")
        log.info("="*55)

        self._print_top_performers()
        return result

    def _update_adaptive_weights(self):
        """Update current_weights.json with replay insights."""
        weights_file = self.adaptive_dir / "current_weights.json"

        weights = {}
        for setup, data in self.stats.items():
            trades = data.get("trades", 0)
            if trades < 10:
                weights[setup] = 1.0
                continue
            win_rate  = data["wins"] / trades
            avg_pnl   = data["total_pnl"] / trades

            # Score: weighted combination of win rate and avg pnl
            score = (win_rate * 0.6) + (min(max(avg_pnl, -2), 2) / 4 * 0.4)
            # Map to modifier range 0.8–1.2
            modifier = 0.8 + (score * 0.8)
            modifier = round(min(max(modifier, 0.8), 1.2), 3)
            weights[setup] = modifier

        try:
            existing = {}
            if weights_file.exists():
                with open(weights_file) as f:
                    existing = json.load(f)

            existing.update({
                "setup_modifiers": weights,
                "last_replay":     datetime.utcnow().isoformat(),
                "replay_setups":   sum(d["trades"] for d in self.stats.values()),
            })

            with open(weights_file, "w") as f:
                json.dump(existing, f, indent=2)

            log.info(f"  Weights updated: {weights}")
        except Exception as e:
            log.warning(f"Weight update error: {e}")

    def _save_learning_history(self, total: int, period: str):
        try:
            history = []
            if self.learning_file.exists():
                with open(self.learning_file) as f:
                    history = json.load(f)

            history.append({
                "timestamp":     datetime.utcnow().isoformat(),
                "type":          "historical_replay",
                "period":        period,
                "setups_added":  total,
                "symbols":       len(ALL_SYMBOLS),
            })

            with open(self.learning_file, "w") as f:
                json.dump(history[-100:], f, indent=2)  # keep last 100
        except Exception as e:
            log.warning(f"History save error: {e}")

    def _print_top_performers(self):
        """Print top performing setups by win rate."""
        log.info("\n── TOP SETUPS BY WIN RATE ──")
        ranked = []
        for setup, data in self.stats.items():
            if data["trades"] >= 50:
                wr  = data["wins"] / data["trades"] * 100
                avg = data["total_pnl"] / data["trades"]
                ranked.append((setup, wr, avg, data["trades"]))

        ranked.sort(key=lambda x: x[1], reverse=True)
        for setup, wr, avg, trades in ranked:
            log.info(f"  {setup:<35} WR={wr:.1f}%  AvgPnL={avg:+.3f}%  N={trades:,}")

    def get_current_stats(self) -> dict:
        """Returns current replay statistics."""
        total = sum(d["trades"] for d in self.stats.values())
        return {
            "total_setups_tracked": total,
            "by_setup":             {
                s: {
                    "trades":   d["trades"],
                    "win_rate": round(d["wins"]/d["trades"]*100, 1) if d["trades"] else 0,
                    "avg_pnl":  round(d["total_pnl"]/d["trades"], 3) if d["trades"] else 0,
                }
                for s, d in self.stats.items()
            },
            "timestamp": datetime.utcnow().isoformat(),
        }


# ── CLI entry point ───────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    engine = HistoricalReplayEngine()

    # Check current stats first
    stats = engine.get_current_stats()
    print(f"\nCurrent setups tracked: {stats['total_setups_tracked']:,}")
    print("By setup:")
    for s, d in stats["by_setup"].items():
        print(f"  {s:<35} trades={d['trades']:,}  WR={d['win_rate']}%")

    if "--check" in sys.argv:
        sys.exit(0)

    # Choose period
    period = "3y"
    for arg in sys.argv[1:]:
        if arg in ("1y", "2y", "3y", "5y"):
            period = arg
            break

    print(f"\nStarting historical replay — period: {period}")
    print("This will take 5–15 minutes depending on network speed.")
    print("Press Ctrl+C to stop (progress is saved)\n")

    result = engine.run_full_replay(period=period, batch_size=5, delay=0.5)
    print(f"\n✅ Replay complete: {result['total_setups_recorded']:,} setups added")
