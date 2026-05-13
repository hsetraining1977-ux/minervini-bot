#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║   MINERVINI AI — ADAPTIVE REVIEW ENGINE                          ║
║   Human Governance Layer — Approval & Rollback                   ║
║   LEVEL 2 & 3 PROTECTION                                         ║
╚══════════════════════════════════════════════════════════════════╝
"""

import sys
import os
sys.path.insert(0, "/root")

import json
import requests
from datetime import datetime
from typing import Optional

import adaptive_memory  as mem
import adaptive_scoring as scoring

# ── Telegram ──────────────────────────────────────────────────────
def _send_telegram(msg: str):
    try:
        from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception:
        pass

# ══════════════════════════════════════════════════════════════════
# REVIEW FUNCTIONS
# ══════════════════════════════════════════════════════════════════

def review_pending_approvals() -> dict:
    """Display all pending Level 2 approvals"""
    pending = mem.get_pending_approvals()

    print(f"\n{'='*60}")
    print(f"  PENDING APPROVALS ({len(pending)} items)")
    print(f"{'='*60}")

    if not pending:
        print("  ✔ No pending approvals\n")
        return {"count": 0, "items": []}

    for i, a in enumerate(pending, 1):
        print(f"\n  [{i}] ID: {a['id']}")
        print(f"      Title:   {a['title']}")
        print(f"      Level:   {a['level']}")
        print(f"      Created: {a['timestamp']}")
        print(f"      Desc:    {a['description']}")
        print(f"      Change:  {json.dumps(a.get('proposed_change', {}))}")

    return {"count": len(pending), "items": pending}

def approve(approval_id: str) -> bool:
    """Human approves a Level 2 suggestion"""
    result = mem.approve_change(approval_id)
    if result:
        print(f"  ✔ Approved: {approval_id}")
        _send_telegram(
            f"✅ <b>Adaptive Change Approved</b>\n"
            f"ID: {approval_id}\n"
            f"Time: {datetime.now().strftime('%H:%M ET')}"
        )
    else:
        print(f"  ✗ Not found or already processed: {approval_id}")
    return result

def reject(approval_id: str) -> bool:
    """Human rejects a Level 2 suggestion"""
    result = mem.reject_change(approval_id)
    if result:
        print(f"  ✔ Rejected: {approval_id}")
    else:
        print(f"  ✗ Not found: {approval_id}")
    return result

# ── Rollback ──────────────────────────────────────────────────────
def rollback_to_defaults() -> bool:
    """
    LEVEL 3 PROTECTION — Instant rollback to static weights.
    No AI input — pure human control.
    """
    print(f"\n{'='*60}")
    print(f"  ⚠  ROLLBACK TO DEFAULT WEIGHTS")
    print(f"{'='*60}")

    confirm = input("  Type CONFIRM to rollback all adaptive weights: ").strip()
    if confirm != "CONFIRM":
        print("  Rollback cancelled")
        return False

    result = mem.reset_weights()
    if result:
        print("  ✔ All weights reset to factory defaults")
        print("  ✔ Trading system now uses static scoring")
        _send_telegram(
            "⚠️ <b>ADAPTIVE WEIGHTS ROLLED BACK</b>\n"
            "System reverted to static scoring defaults.\n"
            f"Time: {datetime.now().strftime('%H:%M ET')}"
        )
        return True

    print("  ✗ Rollback failed")
    return False

def rollback_no_confirm() -> bool:
    """Rollback without confirmation (for dashboard use)"""
    result = mem.reset_weights()
    if result:
        _send_telegram(
            "⚠️ <b>ADAPTIVE WEIGHTS ROLLED BACK</b>\n"
            "Dashboard rollback to static defaults.\n"
            f"Time: {datetime.now().strftime('%H:%M ET')}"
        )
    return result

# ── Performance Review ────────────────────────────────────────────
def generate_performance_review() -> dict:
    """Full adaptive performance review"""
    setup_stats  = mem.get_setup_stats()
    regime_perf  = mem.get_regime_perf()
    changes      = mem.get_changes(20)
    history      = mem.get_learning_history(10)
    weights      = mem.load_weights()
    pending      = mem.get_pending_approvals()
    missed       = mem.get_missed_analysis(50)
    narrative    = mem.get_latest_narrative()

    print(f"\n{'='*60}")
    print(f"  ADAPTIVE INTELLIGENCE REVIEW")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")

    # Weights status
    print(f"\n  WEIGHTS STATUS")
    print(f"  Version:  {weights.get('version', 1)}")
    print(f"  Updated:  {weights.get('updated_at', 'never')}")

    # Setup performance
    print(f"\n  SETUP PERFORMANCE (top 5)")
    ranked = []
    for setup, data in setup_stats.items():
        total = data.get("total", 0)
        if total >= 3:
            wr = data.get("wins", 0) / total
            ranked.append((setup, wr, total, data.get("total_pnl", 0)))
    ranked.sort(key=lambda x: x[1], reverse=True)

    for setup, wr, total, pnl in ranked[:5]:
        mod = weights.get("setup_modifiers", {}).get(setup, 1.0)
        print(f"  {setup:30s} WR:{wr:.1%} Trades:{total:3d} "
              f"PnL:{pnl:+.1f}% Modifier:{mod:.2f}x")

    # Regime performance
    print(f"\n  REGIME PERFORMANCE")
    for regime, data in regime_perf.items():
        total = data.get("total", 0)
        if total == 0:
            continue
        wr = data.get("wins", 0) / total
        aggr = weights.get("regime_aggressiveness", {}).get(regime, 1.0)
        print(f"  {regime:15s} WR:{wr:.1%} Trades:{total:3d} Aggr:{aggr:.2f}x")

    # Recent changes
    print(f"\n  RECENT ADAPTATIONS ({len(changes)})")
    for c in changes[-5:]:
        auto = "AUTO" if c.get("auto_applied") else "MANUAL"
        print(f"  [{auto}] {c.get('timestamp','')[:16]} — {c.get('description','')}")

    # Pending approvals
    print(f"\n  PENDING APPROVALS: {len(pending)}")
    for p in pending:
        print(f"  [{p['id']}] {p['title']}")

    # Missed opportunities
    sig_missed = [m for m in missed if m.get("move_pct", 0) > 3]
    print(f"\n  MISSED OPPORTUNITIES: {len(sig_missed)} significant (>3%)")

    # Narrative
    if narrative:
        n = narrative.get("narrative", narrative)
        if isinstance(n, dict):
            print(f"\n  AI NARRATIVE:")
            print(f"  📊 {n.get('headline', '')}")
            print(f"  💡 {n.get('recommendation', '')}")

    print(f"\n{'='*60}\n")

    return {
        "timestamp":       datetime.now().isoformat(),
        "weights_version": weights.get("version", 1),
        "setup_count":     len(setup_stats),
        "regime_count":    len(regime_perf),
        "pending":         len(pending),
        "changes":         len(changes),
        "significant_missed": len(sig_missed),
        "top_setups":      [(s[0], round(s[1], 3)) for s in ranked[:3]],
    }

# ── Stability Check ───────────────────────────────────────────────
def check_stability() -> dict:
    """
    Verify adaptive weights are within safe limits.
    Alert if any modifier is near its limit.
    """
    weights = mem.load_weights()
    limits  = mem.SAFETY_LIMITS
    issues  = []

    for setup, mod in weights.get("setup_modifiers", {}).items():
        if mod >= limits["setup_modifier_max"] * 0.95:
            issues.append(f"Setup {setup} modifier near MAX: {mod:.3f}")
        if mod <= limits["setup_modifier_min"] * 1.05:
            issues.append(f"Setup {setup} modifier near MIN: {mod:.3f}")

    for regime, aggr in weights.get("regime_aggressiveness", {}).items():
        if aggr >= limits["regime_aggr_max"] * 0.95:
            issues.append(f"Regime {regime} aggr near MAX: {aggr:.3f}")
        if aggr <= limits["regime_aggr_min"] * 1.05:
            issues.append(f"Regime {regime} aggr near MIN: {aggr:.3f}")

    stable = len(issues) == 0

    if not stable:
        print(f"\n  ⚠  STABILITY WARNINGS:")
        for issue in issues:
            print(f"    • {issue}")
        _send_telegram(
            f"⚠️ <b>Adaptive Stability Warning</b>\n" +
            "\n".join(f"• {i}" for i in issues)
        )
    else:
        print("  ✔ All adaptive weights within safe limits")

    return {"stable": stable, "issues": issues,
            "timestamp": datetime.now().isoformat()}

# ── CLI Interface ─────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Minervini AI — Adaptive Review Engine"
    )
    parser.add_argument("--action", required=True,
                        choices=["review","pending","approve","reject",
                                 "rollback","stability"],
                        help="Action to perform")
    parser.add_argument("--id", type=str, help="Approval ID for approve/reject")

    args = parser.parse_args()

    print("""
╔══════════════════════════════════════════════════════════════════╗
║   MINERVINI AI — ADAPTIVE REVIEW ENGINE                          ║
║   Human Governance Layer                                         ║
╚══════════════════════════════════════════════════════════════════╝
    """)

    if args.action == "review":
        generate_performance_review()

    elif args.action == "pending":
        review_pending_approvals()

    elif args.action == "approve":
        if not args.id:
            print("  ✗ --id required for approve")
        else:
            approve(args.id)

    elif args.action == "reject":
        if not args.id:
            print("  ✗ --id required for reject")
        else:
            reject(args.id)

    elif args.action == "rollback":
        rollback_to_defaults()

    elif args.action == "stability":
        check_stability()
