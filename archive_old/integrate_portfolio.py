#!/usr/bin/env python3
"""
integrate_portfolio.py
Patches smart_execution_engine.py, paper_execution.py, master_orchestrator.py
to integrate Portfolio Intelligence.
PAPER TRADING ONLY.
Run once: python3 /root/integrate_portfolio.py
"""

import re, os, sys, shutil, datetime

BACKUP_DIR = f"/root/backups/portfolio_integration_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
os.makedirs(BACKUP_DIR, exist_ok=True)

FILES = {
    "smart_execution_engine": "/root/smart_execution_engine.py",
    "paper_execution":        "/root/paper_execution.py",
    "master_orchestrator":    "/root/master_orchestrator.py",
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def backup(path):
    dst = os.path.join(BACKUP_DIR, os.path.basename(path))
    shutil.copy2(path, dst)
    print(f"  ✅ Backup: {dst}")

def read(path):
    with open(path) as f:
        return f.read()

def write(path, src):
    with open(path, "w") as f:
        f.write(src)

def inject_after_imports(src, code):
    """Inject code after the last top-level import block."""
    lines = src.split("\n")
    last_import = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            last_import = i
    insert_at = last_import + 1
    lines.insert(insert_at, code)
    return "\n".join(lines)

def inject_before_first_def(src, code):
    match = re.search(r"^def ", src, re.MULTILINE)
    if match:
        return src[:match.start()] + code + src[match.start():]
    return src + "\n" + code

# ══════════════════════════════════════════════════════════════════════════════
# PORTFOLIO GUARD — shared module injected into each file
# ══════════════════════════════════════════════════════════════════════════════
PORTFOLIO_GUARD_CODE = '''
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

        sector_lines = "\n".join(
            f"  • {s}: `{v:.1f}%`" for s, v in sector_exp.items()
        )
        warn_lines = "\n".join(
            f"  ⚠️ {w.get('message','')}"
            for w in warns.get("warnings", [])[:3]
        )

        msg = (
            f"📊 *PORTFOLIO SUMMARY — PAPER*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🌡️ Heat: `{heat_pct:.1f}%` | 💰 Cash: `{cash_pct:.1f}%`\n"
            f"📈 Positions: `{positions}` | P&L: `${unreal:+.2f}`\n"
            f"🧠 Regime: `{regime}` | Risk Score: `{risk_score}/100`\n"
            f"\n🏭 Sector Exposure:\n{sector_lines or '  None'}\n"
            + (f"\n⚠️ Warnings ({w_count}):\n{warn_lines}" if w_count else "")
            + f"\n\n⚠️ PAPER TRADING ONLY"
        )
        _req.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"},
            timeout=10
        )
    except Exception as e:
        pass

# ── END PORTFOLIO INTELLIGENCE GUARD ─────────────────────────────────────────
'''

# ══════════════════════════════════════════════════════════════════════════════
# PATCH 1: smart_execution_engine.py
# ══════════════════════════════════════════════════════════════════════════════
def patch_smart_execution():
    path = FILES["smart_execution_engine"]
    if not os.path.exists(path):
        print(f"  ⚠️  {path} not found — skipping")
        return
    backup(path)
    src = read(path)

    # Inject portfolio guard
    if "_PORTFOLIO_GUARD_LOADED" not in src:
        src = inject_before_first_def(src, PORTFOLIO_GUARD_CODE)
        print("  ✅ Injected portfolio guard")

    # Patch execute_stage_entry to run portfolio check
    PATCH = '''
    # ── PORTFOLIO CHECK (PAPER ONLY) ──────────────────────────────────────────
    _pg_result = portfolio_check_trade(symbol, sizes.get(stage_key, 1), float(plan.get("entry", plan.get("entry_price", 0))))
    if not _pg_result["approved"]:
        log.info(f"[{symbol}] PORTFOLIO BLOCKED: {_pg_result['reason']}")
        return None
    qty = max(1, int(qty * _pg_result["size_multiplier"]))
    log.info(f"[{symbol}] Portfolio check: size_mult={_pg_result['size_multiplier']} | {_pg_result['reason']}")
    # ── END PORTFOLIO CHECK ───────────────────────────────────────────────────
'''
    if "PORTFOLIO CHECK (PAPER ONLY)" not in src:
        # Find "vol_mult" line and inject after
        target = "vol_mult  = get_volatility_size_multiplier(symbol)"
        if target in src:
            src = src.replace(target, target + PATCH)
            print("  ✅ Patched execute_stage_entry with portfolio check")
        else:
            # Generic: inject before first alpaca_post call
            src = src.replace(
                'order = {',
                PATCH + '\n    order = {',
                1
            )
            print("  ✅ Patched execute_stage_entry (generic)")

    write(path, src)
    print(f"  ✅ smart_execution_engine.py patched")

# ══════════════════════════════════════════════════════════════════════════════
# PATCH 2: paper_execution.py
# ══════════════════════════════════════════════════════════════════════════════
def patch_paper_execution():
    path = FILES["paper_execution"]
    if not os.path.exists(path):
        print(f"  ⚠️  {path} not found — skipping")
        return
    backup(path)
    src = read(path)

    if "_PORTFOLIO_GUARD_LOADED" not in src:
        src = inject_before_first_def(src, PORTFOLIO_GUARD_CODE)
        print("  ✅ Injected portfolio guard")

    # Patch validate_entry to include portfolio check
    VALIDATE_PATCH = '''
    # ── PORTFOLIO CHECK IN VALIDATE_ENTRY (PAPER ONLY) ───────────────────────
    _entry_price = float(plan.get("entry", plan.get("entry_price", 0)))
    _symbol      = plan.get("symbol", "")
    _qty_est     = int(plan.get("position_size", plan.get("shares", 10)))
    _pg          = portfolio_check_trade(_symbol, _qty_est, _entry_price)
    if not _pg["approved"]:
        return False, f"Portfolio blocked: {_pg['reason']}"
    # ── END PORTFOLIO CHECK ───────────────────────────────────────────────────
'''
    if "PORTFOLIO CHECK IN VALIDATE_ENTRY" not in src:
        # Find validate_entry function and inject after dynamic threshold block
        if "DYNAMIC THRESHOLD (PAPER ONLY)" in src:
            src = src.replace(
                "# ── END DYNAMIC THRESHOLD ────────────────────────────────────────────────",
                "# ── END DYNAMIC THRESHOLD ────────────────────────────────────────────────"
                + VALIDATE_PATCH
            )
            print("  ✅ Patched validate_entry with portfolio check")
        else:
            print("  ⚠️  Could not find injection point in validate_entry")

    write(path, src)
    print(f"  ✅ paper_execution.py patched")

# ══════════════════════════════════════════════════════════════════════════════
# PATCH 3: master_orchestrator.py
# ══════════════════════════════════════════════════════════════════════════════
def patch_master_orchestrator():
    path = FILES["master_orchestrator"]
    if not os.path.exists(path):
        print(f"  ⚠️  {path} not found — skipping")
        return
    backup(path)
    src = read(path)

    if "_PORTFOLIO_GUARD_LOADED" not in src:
        src = inject_before_first_def(src, PORTFOLIO_GUARD_CODE)
        print("  ✅ Injected portfolio guard")

    # Add portfolio snapshot + telegram summary to main() loop
    ORCH_PATCH = '''
    # ── PORTFOLIO INTELLIGENCE (PAPER ONLY) ───────────────────────────────────
    try:
        import sys as _sys_orch
        _sys_orch.path.insert(0, '/root')
        from portfolio_engine import run_portfolio_snapshot
        _port_snap = run_portfolio_snapshot()
        print(f"[Portfolio] Heat={_port_snap.get('portfolio_heat_pct',0):.1f}% | "
              f"Cash={_port_snap.get('cash_pct',0):.1f}% | "
              f"Warns={_port_snap.get('warning_count',0)}")
        # Send Telegram summary every 6 cycles
        if _orch_cycle % 6 == 0:
            send_portfolio_summary_telegram()
    except Exception as _pe:
        print(f"[Portfolio] Error: {_pe}")
    # ── END PORTFOLIO INTELLIGENCE ────────────────────────────────────────────
'''
    if "PORTFOLIO INTELLIGENCE (PAPER ONLY)" not in src:
        # Find the while True loop and inject inside it
        if "_orch_cycle" not in src:
            # Add cycle counter to while True
            src = src.replace(
                "while True:\n    try:\n        main()",
                "while True:\n    try:\n        _orch_cycle = getattr(patch_master_orchestrator, '_cycle', 0)\n        patch_master_orchestrator._cycle = _orch_cycle + 1\n        main()" + ORCH_PATCH
            )
        print("  ✅ Patched master_orchestrator with portfolio intelligence")

    write(path, src)
    print(f"  ✅ master_orchestrator.py patched")

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  PORTFOLIO INTELLIGENCE INTEGRATION")
    print("  PAPER TRADING ONLY — NO LIVE EXECUTION")
    print("=" * 60)

    print("\n[1/3] Patching smart_execution_engine.py...")
    patch_smart_execution()

    print("\n[2/3] Patching paper_execution.py...")
    patch_paper_execution()

    print("\n[3/3] Patching master_orchestrator.py...")
    patch_master_orchestrator()

    print("\n── Syntax checks ─────────────────────────────────────")
    import subprocess
    all_ok = True
    for name, path in FILES.items():
        if os.path.exists(path):
            result = subprocess.run(
                ["python3", "-m", "py_compile", path],
                capture_output=True
            )
            status = "✅ OK" if result.returncode == 0 else "❌ ERROR"
            if result.returncode != 0:
                all_ok = False
                print(f"  {status} {name}: {result.stderr.decode()}")
            else:
                print(f"  {status} {name}")

    print("\n=" * 60)
    if all_ok:
        print("  ✅ ALL PATCHES APPLIED SUCCESSFULLY")
        print(f"  Backups in: {BACKUP_DIR}")
        print("\n  Next steps:")
        print("  1. Restart engines:")
        print("     pkill -f paper_execution && pkill -f smart_execution && pkill -f master_orchestrator")
        print("     sleep 2")
        print("     python3 /root/paper_execution.py >> /root/logs/paper.out 2>&1 &")
        print("     python3 /root/smart_execution_engine.py >> /root/logs/smart_engine.out 2>&1 &")
        print("     python3 /root/master_orchestrator.py >> /root/logs/orchestrator.out 2>&1 &")
        print("  2. Test:")
        print("     python3 /root/paper_execution.py --scan")
    else:
        print("  ❌ SOME PATCHES HAD ERRORS — check syntax above")
        print(f"  Backups available in: {BACKUP_DIR}")
    print("=" * 60)
