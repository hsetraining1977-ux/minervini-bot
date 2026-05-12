#!/bin/bash
set -e
SCRIPT="/root/paper_execution.py"
BACKUP="/root/paper_execution.py.bak_$(date +%Y%m%d_%H%M%S)"
cp "$SCRIPT" "$BACKUP"
echo " Backup: $BACKUP"

python3 << 'PYEOF'
import re, sys

path = "/root/paper_execution.py"
with open(path) as f:
    src = f.read()

NEW_FUNC = '''
def get_dynamic_threshold():
    import json, os
    try:
        mi_path = "/root/logs/market_intelligence.json"
        if os.path.exists(mi_path):
            with open(mi_path) as f:
                mi = json.load(f)
            regime = mi.get("regime", mi.get("market_regime", "NEUTRAL")).upper()
        else:
            regime = "NEUTRAL"
    except Exception:
        regime = "NEUTRAL"
    thresholds = {"RISK_ON": 75, "NEUTRAL": 85, "RISK_OFF": 92}
    return thresholds.get(regime, 85), regime

def _log_rejection(symbol, score, threshold, regime):
    import datetime
    msg = f"[REJECTED] {symbol} | Score={score} | Required={threshold} | Regime={regime} | {datetime.datetime.now()}"
    try:
        with open("/root/logs/trade_decisions.log","a") as f:
            f.write(msg+"\\n")
    except: pass
    print(msg)

'''

if "def get_dynamic_threshold" not in src:
    match = re.search(r'^def ', src, re.MULTILINE)
    if match:
        src = src[:match.start()] + NEW_FUNC + src[match.start():]
        print(" Added get_dynamic_threshold()")

src, n = re.subn(r'>=\s*85(?!\d)', '>= get_dynamic_threshold()[0]', src)
if n: print(f" Patched {n} threshold(s)")

with open(path,"w") as f:
    f.write(src)
print(" Done")
PYEOF

python3 -m py_compile "$SCRIPT" && echo " Syntax OK" || { echo " Error - restoring"; cp "$BACKUP" "$SCRIPT"; }
wc -l "$SCRIPT"
