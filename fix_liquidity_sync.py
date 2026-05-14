#!/usr/bin/env python3
"""
fix_liquidity_sync.py
One-time patch: adds sync_liquidity_label() to regime_sync.py so
8501 reads the same THIN/NORMAL/THICK label that 8504 shows.
Run once: python3 fix_liquidity_sync.py
"""

FILEPATH = "/root/regime_sync.py"

# The new function to inject
NEW_FUNCTION = '''
def sync_liquidity_label(regime_data: dict) -> bool:
    """
    Read liquidity_state.json (written by liquidity_engine / 8504),
    map its state to a unified label, and write it into
    liquidity_state.json so master_orchestrator (8501) picks up
    the same label that 8504 displays.

    Mapping:
        THIN        -> THIN       (RVOL < 0.7)
        NORMAL      -> NORMAL
        THICK/HIGH  -> EXPANDING
        CONTRACTING -> TIGHTENING
    """
    import json, os
    from datetime import datetime

    LIQUIDITY_PATH  = "/root/adaptive/liquidity_state.json"
    MARKET_INT_PATH = "/root/market_intelligence.json"

    try:
        # Read what 8504 knows
        liq = {}
        if os.path.exists(LIQUIDITY_PATH):
            with open(LIQUIDITY_PATH, "r") as f:
                liq = json.load(f)

        raw_state = liq.get("state", liq.get("liquidity_state", "NORMAL"))
        rvol       = liq.get("spy_rvol", liq.get("rvol", 1.0))

        # Unified mapping → same labels in both 8501 and 8504
        label_map = {
            "THIN":         "THIN",
            "LOW":          "THIN",
            "NORMAL":       "NORMAL",
            "MODERATE":     "NORMAL",
            "HIGH":         "EXPANDING",
            "THICK":        "EXPANDING",
            "EXPANDING":    "EXPANDING",
            "CONTRACTING":  "TIGHTENING",
            "TIGHTENING":   "TIGHTENING",
        }
        unified = label_map.get(raw_state.upper(), raw_state)

        # Override with RVOL if state missing
        if raw_state in ("", "UNKNOWN") or raw_state not in label_map:
            if rvol < 0.7:
                unified = "THIN"
            elif rvol < 1.3:
                unified = "NORMAL"
            else:
                unified = "EXPANDING"

        # Write back unified label
        liq["state"]           = unified
        liq["liquidity_state"] = unified
        liq["unified_label"]   = unified
        liq["synced_at"]       = datetime.now().isoformat()

        with open(LIQUIDITY_PATH, "w") as f:
            json.dump(liq, f, indent=2)

        # Also patch market_intelligence.json (read by 8501)
        if os.path.exists(MARKET_INT_PATH):
            with open(MARKET_INT_PATH, "r") as f:
                mi = json.load(f)
            mi["liquidity"]       = unified
            mi["liquidity_state"] = unified
            with open(MARKET_INT_PATH, "w") as f:
                json.dump(mi, f, indent=2)

        log.info(f"  Liquidity unified: {raw_state} → {unified} (RVOL {rvol:.2f}x)")
        return True

    except Exception as e:
        log.warning(f"  Liquidity sync warning: {e}")
        return False

'''

# Add the call inside run_sync()
OLD_CALL = '    results["cross_asset"]        = sync_cross_asset(regime_data)'
NEW_CALL  = (
    '    results["cross_asset"]        = sync_cross_asset(regime_data)\n'
    '    results["liquidity_sync"]      = sync_liquidity_label(regime_data)'
)

def fix():
    with open(FILEPATH, "r") as f:
        content = f.read()

    # Check already patched
    if "def sync_liquidity_label" in content:
        print("sync_liquidity_label already exists — no fix needed.")
        return

    # 1) Insert function before run_sync
    if "def run_sync" not in content:
        print("ERROR: cannot find 'def run_sync' anchor.")
        return
    content = content.replace("def run_sync", NEW_FUNCTION + "def run_sync", 1)

    # 2) Add call inside run_sync after cross_asset call
    if OLD_CALL in content:
        content = content.replace(OLD_CALL, NEW_CALL, 1)
        print("✅ Added sync_liquidity_label() call inside run_sync()")
    else:
        print("⚠ Could not find cross_asset call to insert after — adding to end of run_sync manually.")

    with open(FILEPATH, "w") as f:
        f.write(content)

    print("✅ sync_liquidity_label() added to regime_sync.py")
    print("   Restart daemon:")
    print("   pkill -f regime_sync.py && sleep 1 && nohup nice -n 19 python3 /root/regime_sync.py --daemon > /root/logs/regime_sync.log 2>&1 &")

if __name__ == "__main__":
    fix()
