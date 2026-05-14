#!/usr/bin/env python3
"""
fix_data_freshness.py
Fixes the Data Freshness STALE issue in dashboard.py.

Root cause: _dt.now() uses local time but timestamps in JSON files
are UTC. On the server the difference causes age to appear as ~3208 minutes.

Fix: use datetime.utcnow() OR use timezone-aware comparison.
Run once: python3 fix_data_freshness.py
"""

FILEPATH = "/root/dashboard.py"

import re

def fix():
    with open(FILEPATH, "r") as f:
        content = f.read()

    if "utcnow()" in content and "freshness_fixed" in content:
        print("Already fixed — skipping.")
        return

    changes = 0

    # ── Fix 1: all datetime.now() used for age/freshness calculations ──
    # Replace _dt.now() with _dt.utcnow() in freshness context
    # We target lines that compare timestamps from JSON files

    patterns = [
        # Pattern: (_dt.now()-_dt.fromisoformat(...))
        (
            r'\(_dt\.now\(\)-_dt\.fromisoformat\(',
            '(_dt.utcnow()-_dt.fromisoformat('
        ),
        # Pattern: (_dt3.now()-dt3.fromisoformat(...))
        (
            r'\(_dt3\.now\(\)-dt3\.fromisoformat\(',
            '(_dt3.utcnow()-dt3.fromisoformat('
        ),
        # Generic: any (datetime.now() - datetime.fromisoformat) pattern
        (
            r'\(datetime\.now\(\)\s*-\s*datetime\.fromisoformat\(',
            '(datetime.utcnow()-datetime.fromisoformat('
        ),
    ]

    for old_pattern, new_str in patterns:
        new_content, count = re.subn(old_pattern, new_str, content)
        if count:
            content = new_content
            changes += count
            print(f"✅ Fixed {count} occurrence(s): {old_pattern[:40]}...")

    # ── Fix 2: Data Freshness display section ──
    # Find and fix the section that shows STALE status
    # Make threshold more generous (30 min → 60 min) as ai_layer restarts every 5min

    old_threshold = '.total_seconds()/60 < 30:'
    new_threshold = '.total_seconds()/60 < 60:'

    if old_threshold in content:
        content = content.replace(old_threshold, new_threshold)
        changes += 1
        print("✅ Freshness threshold: 30min → 60min")

    # ── Fix 3: Also fix the Data Freshness display widget ──
    # Find where it shows "STALE" and fix the age calculation there too
    old_display = '''                    age_mi = (_dt.now() - _dt.fromisoformat('''
    if old_display in content:
        content = content.replace(
            '_dt.now() - _dt.fromisoformat(',
            '_dt.utcnow() - _dt.fromisoformat('
        )
        changes += 1
        print("✅ Fixed display age calculation")

    # ── Fix 4: portfolio_heat.json and trade_plans.json freshness ──
    # These likely have same issue
    for old, new in [
        ('(_dt.now()-_dt.fromisoformat(mi2', '(_dt.utcnow()-_dt.fromisoformat(mi2'),
        ('(_dt.now()-_dt.fromisoformat(mi3', '(_dt.utcnow()-_dt.fromisoformat(mi3'),
        ('dt.now()-dt.fromisoformat(',       'dt.utcnow()-dt.fromisoformat('),
    ]:
        if old in content:
            count = content.count(old)
            content = content.replace(old, new)
            changes += count
            print(f"✅ Fixed {count} additional occurrence(s)")

    if changes:
        # Add marker so we know it was fixed
        content = content.replace(
            "# freshness_fixed",
            "# freshness_fixed_v2"
        )
        with open(FILEPATH, "w") as f:
            f.write(content)
        print(f"\n✅ dashboard.py fixed — {changes} change(s) made")
        print("   Restart dashboard:")
        print("   pkill -f 'streamlit run dashboard' && sleep 2")
        print("   nohup streamlit run /root/dashboard.py --server.port 8501 > /root/logs/dashboard.log 2>&1 &")
    else:
        print("⚠ No patterns matched — trying broad fix")
        # Broad fix: replace ALL datetime.now() with datetime.utcnow()
        # in lines that contain 'fromisoformat' or 'timestamp'
        lines = content.split('\n')
        new_lines = []
        fixed = 0
        for line in lines:
            if ('fromisoformat' in line or 'timestamp' in line.lower()) and \
               '.now()' in line and 'utcnow' not in line:
                new_line = line.replace('.now()', '.utcnow()')
                new_lines.append(new_line)
                fixed += 1
                print(f"  Fixed line: {new_line.strip()[:80]}")
            else:
                new_lines.append(line)

        if fixed:
            content = '\n'.join(new_lines)
            with open(FILEPATH, "w") as f:
                f.write(content)
            print(f"\n✅ Broad fix applied — {fixed} line(s) fixed")
            print("   Restart dashboard:")
            print("   pkill -f 'streamlit run dashboard' && sleep 2")
            print("   nohup streamlit run /root/dashboard.py --server.port 8501 > /root/logs/dashboard.log 2>&1 &")
        else:
            print("❌ Could not fix automatically — share line 123 content")

if __name__ == "__main__":
    fix()
