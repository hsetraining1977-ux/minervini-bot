#!/usr/bin/env python3
"""
fix_duplicate_approvals.py
One-time fix: removes duplicate Level-2 approval suggestions from
/root/adaptive/pending_approvals.json, keeping only unique ones.
Run once: python3 fix_duplicate_approvals.py
"""

import json, os
from datetime import datetime

APPROVALS_PATH = "/root/adaptive/pending_approvals.json"

def fix():
    if not os.path.exists(APPROVALS_PATH):
        print(f"File not found: {APPROVALS_PATH}")
        return

    with open(APPROVALS_PATH, "r") as f:
        data = json.load(f)

    # Handle both list and dict formats
    if isinstance(data, dict):
        approvals = data.get("approvals", data.get("pending", []))
        is_dict   = True
    else:
        approvals = data
        is_dict   = False

    print(f"Found {len(approvals)} pending approvals")

    # Deduplicate: key = (setup, regime, change_type, value)
    seen    = set()
    unique  = []
    removed = []

    for ap in approvals:
        # Build a fingerprint of the meaningful content
        key = (
            ap.get("setup", ap.get("setup_name", "")),
            str(ap.get("change", ap.get("suggestion", ap.get("regime_boost", "")))),
            ap.get("level", ""),
            ap.get("reason", ap.get("description", ""))[:80],
        )
        if key not in seen:
            seen.add(key)
            unique.append(ap)
        else:
            removed.append(ap.get("id", key))

    print(f"  Unique approvals: {len(unique)}")
    print(f"  Duplicates removed: {len(removed)}")

    if removed:
        for r in removed:
            print(f"    - Removed duplicate: {r}")

    # Also flag stale approvals (older than 7 days)
    fresh   = []
    stale   = []
    cutoff  = datetime.now().timestamp() - (7 * 24 * 3600)

    for ap in unique:
        ts_str = ap.get("timestamp", ap.get("created_at", ""))
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
            if ts < cutoff:
                stale.append(ap)
            else:
                fresh.append(ap)
        except Exception:
            fresh.append(ap)  # Keep if can't parse timestamp

    if stale:
        print(f"\n  Stale approvals (>7 days old): {len(stale)}")
        for s in stale:
            print(f"    - {s.get('id', 'unknown')} from {s.get('timestamp', '?')}")
        print("  → Moving stale approvals to archive")
        unique = fresh

    # Save cleaned file
    if is_dict:
        data["approvals"] = unique
        data["last_cleaned"] = datetime.now().isoformat()
        out = data
    else:
        out = unique

    # Backup original
    backup_path = APPROVALS_PATH.replace(".json", f"_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(backup_path, "w") as f:
        json.dump({"original": approvals}, f, indent=2)
    print(f"\n  Backup saved: {backup_path}")

    with open(APPROVALS_PATH, "w") as f:
        json.dump(out, f, indent=2)

    print(f"✅ pending_approvals.json cleaned: {len(approvals)} → {len(unique)} approvals")

if __name__ == "__main__":
    fix()
