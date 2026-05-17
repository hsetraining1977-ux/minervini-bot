from telegram_gate import send_telegram, send_alert
#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║   MINERVINI AI — ADAPTIVE LEARNING ENGINE                        ║
║   Async Background Learning — Non-Blocking                       ║
║   PAPER TRADING ONLY — NO LIVE EXECUTION                         ║
╚══════════════════════════════════════════════════════════════════╝

Architecture:
  - Runs COMPLETELY ASYNC from trading engines
  - Trading engines NEVER wait for this module
  - If this crashes → trading continues normally
  - Reviews every 30 minutes during market hours
  - Deep analysis after market close (16:30 ET)
"""

import sys
import os
sys.path.insert(0, "/root")

import json
import time
import threading
import requests
import schedule
from datetime import datetime, timedelta
from typing import Optional

import adaptive_memory  as mem
import adaptive_scoring as scoring

# ── Config ────────────────────────────────────────────────────────
LOG_DIR              = "/root/logs"
REPLAY_TRADES_LOG    = f"{LOG_DIR}/replay_trades.json"
REPLAY_MISSED_LOG    = f"{LOG_DIR}/replay_missed.json"
REPLAY_SUMMARY_LOG   = f"{LOG_DIR}/replay_summary.json"

PAPER_TRADES_LOG     = f"{LOG_DIR}/paper_trades.json"
PAPER_DECISIONS_LOG  = f"{LOG_DIR}/paper_decisions.json"

ADAPTIVE_LOG         = "/root/adaptive/adaptive_engine.log"
os.makedirs("/root/adaptive", exist_ok=True)

# ── Telegram ──────────────────────────────────────────────────────
def _get_telegram_config():
    try:
        sys.path.insert(0, "/root")
        from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
        return TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
    except Exception:
        return None, None


# ── Logging ───────────────────────────────────────────────────────
def _log(msg: str):
    ts  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(ADAPTIVE_LOG, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass

# ── Data Loaders ──────────────────────────────────────────────────
def _load_json(path: str) -> list:
    try:
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
            return data if isinstance(data, list) else [data]
    except Exception:
        pass
    return []

# ── Claude AI Narrative ───────────────────────────────────────────
def _get_api_key() -> str:
    try:
        with open("/root/.env") as f:
            for line in f:
                if "ANTHROPIC_API_KEY" in line:
                    return line.split("=")[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return ""

def generate_narrative(context: dict) -> dict:
    api_key = _get_api_key()
    if not api_key:
        return _fallback_narrative(context)

    try:
        setup_stats  = context.get("setup_stats", {})
        regime_perf  = context.get("regime_perf", {})
        changes      = context.get("recent_changes", [])
        missed_count = context.get("missed_count", 0)
        weights_ver  = context.get("weights_version", 1)

        top_setups = sorted(
            [(k, v.get("wins", 0) / max(v.get("total", 1), 1), v.get("total", 0))
             for k, v in setup_stats.items() if v.get("total", 0) >= 5],
            key=lambda x: x[1], reverse=True
        )[:3]

        prompt = f"""You are analyzing the Minervini AI trading system adaptive learning results.

ADAPTIVE WEIGHTS VERSION: {weights_ver}
RECENT CHANGES: {len(changes)} adaptations applied

TOP PERFORMING SETUPS:
{json.dumps([(s[0], f"{s[1]:.1%}", f"{s[2]} trades") for s in top_setups], indent=2)}

REGIME PERFORMANCE:
{json.dumps({k: {"wr": f"{v.get('wins',0)/max(v.get('total',1),1):.1%}", "trades": v.get('total',0)} 
             for k, v in regime_perf.items()}, indent=2)}

MISSED OPPORTUNITIES: {missed_count} filtered trades

Generate a concise institutional narrative (2-3 sentences max per section):

Return ONLY valid JSON:
{{
  "headline": "one sentence overall status",
  "setup_narrative": "which setups working and why",
  "regime_narrative": "regime performance insight",
  "missed_narrative": "missed opportunity pattern if any",
  "recommendation": "one specific actionable suggestion"
}}"""

        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model":      "claude-sonnet-4-5",
                "max_tokens": 600,
                "messages":   [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )

        if response.status_code == 200:
            text = response.json()["content"][0]["text"]
            text = text.replace("```json", "").replace("```", "").strip()
            return json.loads(text)

    except Exception as e:
        _log(f"  Narrative error: {e}")

    return _fallback_narrative(context)

def _fallback_narrative(context: dict) -> dict:
    setup_stats = context.get("setup_stats", {})
    regime_perf = context.get("regime_perf", {})

    best_setup = max(
        setup_stats.items(),
        key=lambda x: x[1].get("wins", 0) / max(x[1].get("total", 1), 1),
        default=("N/A", {})
    )[0] if setup_stats else "N/A"

    best_regime = max(
        regime_perf.items(),
        key=lambda x: x[1].get("wins", 0) / max(x[1].get("total", 1), 1),
        default=("N/A", {})
    )[0] if regime_perf else "N/A"

    return {
        "headline":        f"Adaptive system v{context.get('weights_version',1)} — {best_setup} leading",
        "setup_narrative": f"{best_setup} shows strongest performance across tracked sessions.",
        "regime_narrative":f"{best_regime} conditions produce best outcomes based on current data.",
        "missed_narrative":f"{context.get('missed_count',0)} opportunities missed by filters this cycle.",
        "recommendation":  f"Focus on {best_setup} setups during {best_regime} conditions.",
    }

# ══════════════════════════════════════════════════════════════════
# LEARNING MODULES
# ══════════════════════════════════════════════════════════════════

# ── Module 1: Learn from Replay Data ─────────────────────────────
def learn_from_replay() -> int:
    _log("  [Learn] Processing replay trades...")
    trades = _load_json(REPLAY_TRADES_LOG)
    if not trades:
        _log("  [Learn] No replay trades found")
        return 0

    count = 0
    for t in trades:
        won    = t.get("pnl_pct", 0) > 0
        pnl    = t.get("pnl_pct", 0)
        regime = t.get("regime", "UNKNOWN")
        setups = t.get("setups", [])

        for setup in setups:
            mem.update_setup_stat(setup, won, pnl, regime, source="replay")

        mem.update_regime_perf(regime, won, pnl, source="replay")
        count += 1

    _log(f"  [Learn] Processed {count} replay trades")
    return count

# ── Module 2: Learn from Paper Trades ────────────────────────────
def learn_from_paper() -> int:
    _log("  [Learn] Processing paper trades...")
    trades = _load_json(PAPER_TRADES_LOG)
    if not trades:
        _log("  [Learn] No paper trades found")
        return 0

    count = 0
    for t in trades:
        pnl = t.get("pnl_pct", t.get("pnl", 0))
        if isinstance(pnl, str):
            try:
                pnl = float(pnl)
            except Exception:
                pnl = 0

        won    = pnl > 0
        regime = t.get("regime", t.get("market_regime", "UNKNOWN"))
        setups = t.get("setups", t.get("setup_type", []))
        if isinstance(setups, str):
            setups = [setups]

        for setup in setups:
            mem.update_setup_stat(setup, won, pnl, regime, source="paper")

        mem.update_regime_perf(regime, won, pnl, source="paper")
        count += 1

    _log(f"  [Learn] Processed {count} paper trades")
    return count

# ── Module 3: Missed Opportunity Analysis ─────────────────────────
def analyze_missed() -> int:
    _log("  [Learn] Analyzing missed opportunities...")
    missed = _load_json(REPLAY_MISSED_LOG)
    if not missed:
        return 0

    significant = [m for m in missed if m.get("max_move_pct", 0) > 3.0]
    _log(f"  [Learn] {len(significant)} significant missed opportunities (>3%)")

    # Log patterns
    for m in significant:
        mem.log_missed(
            symbol  = m.get("symbol", "?"),
            move_pct= m.get("max_move_pct", 0),
            regime  = m.get("regime", "UNKNOWN"),
            setups  = m.get("setups", []),
            score   = m.get("score", 0),
            reason  = m.get("reason_missed", "filtered"),
        )

    return len(significant)

# ── Module 4: Run Full Learning Cycle ────────────────────────────
def run_learning_cycle(source: str = "scheduled") -> dict:
    _log(f"\n{'='*55}")
    _log(f"  ADAPTIVE LEARNING CYCLE — {source.upper()}")
    _log(f"{'='*55}")

    result = {
        "timestamp":      datetime.now().isoformat(),
        "source":         source,
        "replay_trades":  0,
        "paper_trades":   0,
        "missed_count":   0,
        "adaptations":    0,
        "suggestions":    0,
        "narrative":      {},
    }

    try:
        # Phase 1: Ingest data
        result["replay_trades"] = learn_from_replay()
        result["paper_trades"]  = learn_from_paper()
        result["missed_count"]  = analyze_missed()

        total_trades = result["replay_trades"] + result["paper_trades"]
        _log(f"  Total trades processed: {total_trades}")

        if total_trades == 0:
            _log("  Insufficient data for adaptation — skipping")
            return result

        # Phase 2: Level 1 auto-adaptation
        _log("\n  Phase 2: Level 1 Auto-Adaptation...")
        adapt_result = scoring.run_adaptation_cycle(source=source)
        result["adaptations"] = adapt_result.get("changes_made", 0)

        # Phase 3: Level 2 suggestions
        _log("\n  Phase 3: Level 2 Suggestions...")
        suggestions = scoring.generate_level2_suggestions()
        result["suggestions"] = len(suggestions)
        if suggestions:
            _log(f"  {len(suggestions)} suggestions require human approval")

        # Phase 4: Generate narrative
        _log("\n  Phase 4: Generating AI narrative...")
        narrative = generate_narrative({
            "setup_stats":     mem.get_setup_stats(),
            "regime_perf":     mem.get_regime_perf(),
            "recent_changes":  mem.get_changes(10),
            "missed_count":    result["missed_count"],
            "weights_version": mem.load_weights().get("version", 1),
        })
        result["narrative"] = narrative
        mem.save_narrative(narrative, source=source)

        # Phase 5: Telegram alert if significant changes
        if result["adaptations"] > 0 or result["suggestions"] > 0:
            msg = (
                f"🧠 <b>Adaptive Learning Update</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"📊 Trades analyzed: {total_trades}\n"
                f"⚡ Auto-adaptations: {result['adaptations']}\n"
                f"📋 Pending approvals: {result['suggestions']}\n"
                f"🔍 Missed opportunities: {result['missed_count']}\n\n"
                f"💬 <i>{narrative.get('headline', '')}</i>"
            )
            send_telegram(msg)

        _log(f"\n  ✔ Learning cycle complete")
        _log(f"    Adaptations: {result['adaptations']}")
        _log(f"    Suggestions: {result['suggestions']}")

    except Exception as e:
        _log(f"  ✗ Learning cycle error: {e}")
        # FAIL SAFE — do not crash trading system

    return result

# ── Deep Analysis (Post-Market) ───────────────────────────────────
def run_deep_analysis():
    _log("\n  [Deep Analysis] Running post-market deep analysis...")
    try:
        result = run_learning_cycle(source="post_market_deep")
        summary = mem.get_memory_status()
        _log(f"  Deep analysis complete — {summary['setups_tracked']} setups tracked")

        msg = (
            f"📈 <b>Post-Market Deep Analysis</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🧠 Setups tracked: {summary['setups_tracked']}\n"
            f"📊 Learning cycles: {summary['learning_cycles']}\n"
            f"⚡ Weights v{summary['weights_version']}\n"
            f"⏳ Pending approvals: {summary['pending_approvals']}"
        )
        send_telegram(msg)

    except Exception as e:
        _log(f"  Deep analysis error: {e}")

# ── Scheduler ─────────────────────────────────────────────────────
def start_async_scheduler():
    """
    Run completely async — trading engines never blocked.
    Uses low-priority background thread.
    """
    _log("  [Scheduler] Starting adaptive learning scheduler...")

    # Every 30 minutes during market hours
    schedule.every(30).minutes.do(
        lambda: run_learning_cycle(source="scheduled_30min")
    )

    # Deep analysis after market close
    schedule.every().day.at("16:45").do(run_deep_analysis)

    # Level 2 suggestions every hour
    schedule.every(60).minutes.do(scoring.generate_level2_suggestions)

    _log("  [Scheduler] Schedule:")
    _log("    • Every 30 min  → learning cycle")
    _log("    • 16:45 ET      → deep post-market analysis")
    _log("    • Every 60 min  → level 2 suggestions")

    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            _log(f"  Scheduler error (non-fatal): {e}")
        time.sleep(60)

# ── Main Entry Point ──────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Minervini AI — Adaptive Learning Engine"
    )
    parser.add_argument("--mode", choices=["daemon","once","deep"],
                        default="daemon",
                        help="daemon=background scheduler, once=single cycle, deep=post-market")
    args = parser.parse_args()

    print("""
╔══════════════════════════════════════════════════════════════════╗
║   MINERVINI AI — ADAPTIVE LEARNING ENGINE                        ║
║   PAPER TRADING ONLY — ASYNC — NON-BLOCKING                      ║
╚══════════════════════════════════════════════════════════════════╝
    """)

    if args.mode == "once":
        run_learning_cycle(source="manual")

    elif args.mode == "deep":
        run_deep_analysis()

    elif args.mode == "daemon":
        _log("  Starting in DAEMON mode (async background process)")
        _log("  Trading engines will NOT be affected")

        # Run initial cycle
        run_learning_cycle(source="startup")

        # Start background scheduler
        t = threading.Thread(target=start_async_scheduler, daemon=True)
        t.start()
        _log("  ✔ Adaptive Learning Engine running in background")

        # Keep alive
        while True:
            time.sleep(300)
