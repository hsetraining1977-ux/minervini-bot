#!/usr/bin/env python3
"""
Fix script: adds sync_cross_asset() function to regime_sync.py
Run on server: python3 fix_regime_sync.py
"""

import re

FILEPATH = "/root/regime_sync.py"

NEW_FUNCTION = '''
def sync_cross_asset(regime_data: dict) -> bool:
    """Sync regime signal into cross_asset_state.json so master_orchestrator reads correct regime."""
    import json, os
    from datetime import datetime
    cross_asset_path = "/root/cross_asset_state.json"
    try:
        regime = regime_data.get("regime", "NEUTRAL")
        # Map regime to cross_asset signal
        cross_map = {
            "STRONG_RISK_ON": "RISK_ON",
            "RISK_ON":        "RISK_ON",
            "NEUTRAL":        "NEUTRAL",
            "CHOPPY":         "NEUTRAL",
            "RISK_OFF":       "RISK_OFF",
            "PANIC":          "RISK_OFF",
        }
        cross_signal = cross_map.get(regime, "NEUTRAL")

        # Read existing file to preserve other fields
        cross = {}
        if os.path.exists(cross_asset_path):
            try:
                with open(cross_asset_path, "r") as f:
                    cross = json.load(f)
            except Exception:
                cross = {}

        cross["regime"]        = regime
        cross["cross_signal"]  = cross_signal
        cross["regime_detail"] = regime
        cross["timestamp"]     = datetime.now().isoformat()

        ok = _write(cross_asset_path, cross)
        if ok:
            log.info(f"  cross_asset_state.json: {cross_signal} (from {regime})")
        return ok
    except Exception as e:
        log.warning(f"  cross_asset sync warning: {e}")
        return False

'''

def fix():
    with open(FILEPATH, "r") as f:
        content = f.read()

    # Check if already fixed
    if "def sync_cross_asset" in content:
        print("sync_cross_asset already exists — no fix needed.")
        return

    # Insert the new function just before def run_sync
    if "def run_sync" not in content:
        print("ERROR: could not find 'def run_sync' anchor point.")
        return

    content = content.replace("def run_sync", NEW_FUNCTION + "def run_sync", 1)

    with open(FILEPATH, "w") as f:
        f.write(content)

    print("✅ sync_cross_asset() added successfully to regime_sync.py")
    print("   Now restart the daemon:")
    print("   pkill -f regime_sync.py && sleep 1 && nohup nice -n 19 python3 /root/regime_sync.py --daemon > /root/logs/regime_sync.log 2>&1 &")

if __name__ == "__main__":
    fix()
