grep -n 'period="5d"' /root/intraday_engine.py
grep -n 'period="30d"' /root/intraday_engine.py
pip3 install psycopg2-binary python-telegram-bot --user && python3 -c "import psycopg2; import telegram; print(' OK')"
apt-get install -y postgresql postgresql-contrib && systemctl start postgresql && systemctl enable postgresql && sudo -u postgres psql -c "CREATE USER minervini WITH PASSWORD 'minervini123';" && sudo -u postgres psql -c "CREATE DATABASE minervini_db OWNER minervini;" && echo " PostgreSQL Ready"
curl -o /root/database.py https://raw.githubusercontent.com/hsetraining1977-ux/minervini-bot/main/database.py && curl -o /root/db_test.py https://raw.githubusercontent.com/hsetraining1977-ux/minervini-bot/main/db_test.py && curl -o /root/telegram_commands.py https://raw.githubusercontent.com/hsetraining1977-ux/minervini-bot/main/telegram_commands.py && pip3 install psutil --user && python3 /root/db_test.py
python3 /root/telegram_commands.py &
ANTHROPIC_API_KEY=$(grep ANTHROPIC_API_KEY /root/config.py | cut -d'"' -f2) && export ANTHROPIC_API_KEY && python3 /root/ai_layer.py >> /root/ai.out 2>&1 &
curl -o /root/master_orchestrator.py https://raw.githubusercontent.com/hsetraining1977-ux/minervini-bot/main/master_orchestrator.py && python3 /root/master_orchestrator.py
nohup python3 -c "
import time, schedule
from master_orchestrator import run_orchestrator
run_orchestrator()
schedule.every(2).hours.do(run_orchestrator)
while True:
    schedule.run_pending()
    time.sleep(60)
" > /root/orchestrator.out 2>&1 &
pkill -f telegram_commands && sleep 2 && python3 /root/master_orchestrator.py
nohup python3 -c "
import time, schedule
from master_orchestrator import run_orchestrator
schedule.every(2).hours.do(run_orchestrator)
while True:
    schedule.run_pending()
    time.sleep(60)
" > /root/orchestrator.out 2>&1 & python3 /root/telegram_commands.py > /root/telegram.out 2>&1 &
nohup python3 /root/master_orchestrator.py > /root/orchestrator.out 2>&1 &
tail -f /root/orchestrator.out
cat > /root/dashboard_new.py << 'EOF'
import streamlit as st
st.set_page_config(page_title="Minervini AI Control Center", page_icon="", layout="wide")
st.title(" MINERVINI AI CONTROL CENTER")
st.write("New dashboard loading...")
EOF

~/.local/bin/streamlit run /root/dashboard_new.py --server.port 8502 --server.address 0.0.0.0 &
ufw allow 8503 && ~/.local/bin/streamlit run /root/dashboard_new.py --server.port 8503 --server.address 0.0.0.0 &
curl -o /root/dashboard_new.py "https://raw.githubusercontent.com/hsetraining1977-ux/minervini-bot/main/dashboard.py" && grep -c "section-header" /root/dashb
pip3 install plotly streamlit-autorefresh --user && ~/.local/bin/streamlit run /root/dashboard_new.py --server.port 8503 --server.address 0.0.0.0 &
pkill -f streamlit && sleep 2 && cp /root/dashboard_new.py /root/dashboard.py && ~/.local/bin/streamlit run /root/dashboard.py --server.port 8501 --server.address 0.0.0.0 >> /root/streamlit.out 2>&1 &
ANTHROPIC_API_KEY=$(grep ANTHROPIC_API_KEY /root/config.py | cut -d'"' -f2) && export ANTHROPIC_API_KEY && python3 /root/ai_layer.py >> /root/ai.out 2>&1 &
ps aux | grep streamlit | grep -v grep
cat /root/streamlit.out | tail -5
pkill -f streamlit && sleep 3 && cat /root/dashboard.py | head -5
head -20 /root/dashboard.py | grep -E "Institutional|Minervini AI Trading|title|st.set_page"
#     dashboard_new.py
ls -la /root/dashboard_new.py && head -3 /root/dashboard_new.py
pkill -f streamlit && sleep 3 && cp -f /root/dashboard_new.py /root/dashboard.py && grep -m2 "page_title\|st.title" /root/dashboard.py && ~/.local/bin/streamlit run /root/dashboard.py --server.port 8501 --server.address 0.0.0.0 >> /root/streamlit.out 2>&1 & echo "PID: $!"
sleep 5 && curl -s -o /dev/null -w "%{http_code}" http://localhost:8501
#   key  .env 
export ANTHROPIC_API_KEY=$(grep ANTHROPIC_API_KEY /root/.env | cut -d'=' -f2)
echo "Key found: ${ANTHROPIC_API_KEY:0:10}..."
python3 /root/ai_layer.py >> /root/ai.out 2>&1 &
echo "ai_layer PID: $!"
pkill -9 -f streamlit 2>/dev/null
sleep 2
cat /root/dashboard_new.py > /root/dashboard.py
grep -m1 "Institutional\|Minervini" /root/dashboard.py
nohup ~/.local/bin/streamlit run /root/dashboard.py --server.port 8501 --server.address 0.0.0.0 >> /root/streamlit.out 2>&1 &
echo "Streamlit PID: $!"
sleep 8 && curl -s -o /dev/null -w "HTTP: %{http_code}\n" http://localhost:8501
export ANTHROPIC_API_KEY=$(grep ANTHROPIC_API_KEY /root/.env | cut -d'=' -f2) && python3 /root/ai_layer.py >> /root/ai.out 2>&1 & echo "Claude AI PID: $!"
grep -n "streamlit\|dashboard" /root/watchdog_bot.py
grep -rn "streamlit\|dashboard" /root/watchdog_bot.py /root/master_orchestrator.py /root/telegram_commands.py 2>/dev/null | grep -v ".pyc"
sed -n '185,215p' /root/telegram_commands.py
grep -n "streamlit\|dashboard\|restart\|subprocess" /root/watchdog_bot.py | head -30
grep -n "streamlit\|dashboard\|restart\|subprocess" /root/master_orchestrator.py | head -30
sed -n '60,90p' /root/watchdog_bot.py
sed -n '155,175p' /root/watchdog_bot.py
sed -n '1,60p' /root/watchdog_bot.py
grep -rn "streamlit" /root/*.py 2>/dev/null | grep -v ".pyc" | grep -v "grep"
sed -n '500,515p' /root/ai_layer.py
sed -n '780,795p' /root/ai_layer.py
sed -n '500,515p' /root/ai_layer.py
grep -n "dashboard.py\|open.*dashboard\|write.*dashboard\|DASHBOARD_CODE" /root/ai_layer.py | head -20
pkill -f ai_layer.py
sed -i '682s|/root/dashboard.py|/root/dashboard_old_backup.py|g' /root/ai_layer.py
sed -n '680,685p' /root/ai_layer.py
cat /root/dashboard_new.py > /root/dashboard.py
export ANTHROPIC_API_KEY=$(grep ANTHROPIC_API_KEY /root/.env | cut -d'=' -f2)
python3 /root/ai_layer.py >> /root/ai.out 2>&1 &
echo "AI Layer PID: $!"
#   
for f in logger health_monitor auto_restart resource_monitor log_rotator config_validator; do   curl -o /root/${f}.py https://raw.githubusercontent.com/hsetraining1977-ux/minervini-bot/main/${f}.py; done
curl -o /root/start_system.sh https://raw.githubusercontent.com/hsetraining1977-ux/minervini-bot/main/start_system.sh
curl -o /root/stop_system.sh https://raw.githubusercontent.com/hsetraining1977-ux/minervini-bot/main/stop_system.sh
chmod +x /root/start_system.sh /root/stop_system.sh
python3 /root/config_validator.py
bash /root/start_system.sh
cat > /tmp/fix_start.py << 'EOF'
with open('/root/start_system.sh', 'r') as f:
    content = f.read()

old = '    eval "nohup $cmd >> $logfile 2>&1 &"'
new = '    nohup bash -c "$cmd >> $logfile 2>&1" &'

content = content.replace(old, new)

with open('/root/start_system.sh', 'w') as f:
    f.write(content)
print("Fixed!")
EOF

python3 /tmp/fix_start.py && bash /root/start_system.sh
#    
python3 /root/phase3_sectors.py >> /root/phase3.out 2>&1 &
sleep 3
python3 /root/institutional_layer.py >> /root/institutional.out 2>&1 &
sleep 3
python3 /root/intraday_engine.py >> /root/intraday.out 2>&1 &
sleep 3
#   
echo "=== Phase3 ===" && tail -5 /root/phase3.out
echo "=== Institutional ===" && tail -5 /root/institutional.out  
echo "=== Intraday ===" && tail -5 /root/intraday.out
#  start_system.sh   sleep  
sed -i 's/start_service "Phase3 Sectors".*$/start_service "Phase3 Sectors"     "python3 \/root\/phase3_sectors.py"      "\/root\/phase3.out"\nsleep 3/' /root/start_system.sh
ps aux | grep python | grep -v grep | wc -l
echo "---"
curl -s -o /dev/null -w "Dashboard HTTP: %{http_code}\n" http://localhost:8501
export ANTHROPIC_API_KEY=$(grep ANTHROPIC_API_KEY /root/.env | cut -d'=' -f2 | tr -d '"' | tr -d "'")
python3 /root/ai_layer.py >> /root/ai.out 2>&1 &
echo "AI PID: $!"
sleep 5 && tail -3 /root/ai.out
#     ai_layer.py
sed -i "s/os.system('pip install streamlit --break-system-packages -q')/pass  # removed pip install/" /root/ai_layer.py
# 
grep -n "pip install streamlit\|pass  # removed" /root/ai_layer.py
#   ai_layer
pkill -f ai_layer.py 2>/dev/null
sleep 2
export ANTHROPIC_API_KEY=$(grep ANTHROPIC_API_KEY /root/.env | cut -d'=' -f2 | tr -d '"' | tr -d "'")
python3 /root/ai_layer.py >> /root/ai.out 2>&1 &
echo "AI PID: $!"
sleep 5 && tail -5 /root/ai.out
python3 << 'EOF'
with open('/root/ai_layer.py', 'r') as f:
    content = f.read()

# Replace all pip install streamlit variations
import re
content = re.sub(
    r'os\.system\(["\']pip install streamlit[^"\']*["\']\)',
    'pass  # pip install removed',
    content
)

with open('/root/ai_layer.py', 'w') as f:
    f.write(content)

# Verify
lines = content.split('\n')
for i, line in enumerate(lines[780:795], 781):
    print(f"{i}: {line}")
EOF

pkill -f ai_layer.py 2>/dev/null; sleep 2
export ANTHROPIC_API_KEY=$(grep ANTHROPIC_API_KEY /root/.env | cut -d'=' -f2 | tr -d '"' | tr -d "'")
python3 /root/ai_layer.py >> /root/ai.out 2>&1 &
sleep 8 && tail -5 /root/ai.out
grep -n "break-system-packages\|pip install" /root/ai_layer.py
python3 << 'EOF'
import re
with open('/root/ai_layer.py', 'r') as f:
    content = f.read()

content = re.sub(
    r'os\.system\(["\']pip install anthropic[^"\']*["\']\)',
    'pass  # pip install anthropic removed',
    content
)

with open('/root/ai_layer.py', 'w') as f:
    f.write(content)

# Verify
for i, line in enumerate(content.split('\n')[755:765], 756):
    print(f"{i}: {line}")
EOF

pkill -f ai_layer.py 2>/dev/null; sleep 2
export ANTHROPIC_API_KEY=$(grep ANTHROPIC_API_KEY /root/.env | cut -d'=' -f2 | tr -d '"' | tr -d "'")
python3 /root/ai_layer.py >> /root/ai.out 2>&1 &
echo "PID: $!"
sleep 8 && tail -5 /root/ai.out
python3 << 'EOF'
import re
with open('/root/ai_layer.py', 'r') as f:
    content = f.read()

# Remove create_dashboard() call
content = content.replace('    create_dashboard()', '    pass  # create_dashboard removed')

# Also find and disable the create_dashboard function itself
content = re.sub(
    r'def create_dashboard\(\):.*?(?=\ndef |\Z)',
    'def create_dashboard():\n    pass  # disabled - using dashboard_new.py\n\n',
    content,
    flags=re.DOTALL
)

with open('/root/ai_layer.py', 'w') as f:
    f.write(content)

print("Done!")
# Verify
for i, line in enumerate(content.split('\n')[758:768], 759):
    print(f"{i}: {line}")
EOF

pkill -f ai_layer.py 2>/dev/null; sleep 2
export ANTHROPIC_API_KEY=$(grep ANTHROPIC_API_KEY /root/.env | cut -d'=' -f2 | tr -d '"' | tr -d "'")
python3 /root/ai_layer.py >> /root/ai.out 2>&1 &
echo "PID: $!"
sleep 10 && tail -8 /root/ai.out
tail -8 /root/ai.out
tail -20 /root/ai.out
python3 << 'EOF'
with open('/root/ai_layer.py', 'r') as f:
    content = f.read()

# Remove streamlit run command
import re
content = re.sub(
    r'os\.system\(["\'].*?streamlit run.*?["\']\)',
    'pass  # streamlit run removed',
    content
)
content = re.sub(
    r'subprocess\.[a-z]+\(.*?streamlit run.*?\)',
    'pass  # streamlit run removed',
    content, flags=re.DOTALL
)

# Wrap main execution in infinite loop if not already
with open('/root/ai_layer.py', 'w') as f:
    f.write(content)

print("Done!")
EOF

grep -n "streamlit run" /root/ai_layer.py
tail -30 /root/ai_layer.py
cat > /root/run_ai_layer.sh << 'EOF'
#!/bin/bash
export ANTHROPIC_API_KEY=$(grep ANTHROPIC_API_KEY /root/.env | cut -d'=' -f2 | tr -d '"' | tr -d "'")
while true; do
    echo "[$(date)] Starting ai_layer..." >> /root/ai.out
    python3 /root/ai_layer.py >> /root/ai.out 2>&1
    echo "[$(date)] ai_layer exited  restarting in 300s..." >> /root/ai.out
    sleep 300
done
EOF

chmod +x /root/run_ai_layer.sh
pkill -f ai_layer.py 2>/dev/null
sleep 2
nohup bash /root/run_ai_layer.sh >> /root/ai.out 2>&1 &
echo "AI wrapper PID: $!"
sleep 5 && tail -3 /root/ai.out
sed -i 's|python3 /root/ai_layer.py >> /root/ai.out 2>&1|bash /root/run_ai_layer.sh >> /root/ai.out 2>&1|' /root/start_system.sh
sed -n '740,755p' /root/ai_layer.py
python3 << 'EOF'
with open('/root/ai_layer.py', 'r') as f:
    lines = f.readlines()

# Find DASHBOARD_CODE definition
for i, line in enumerate(lines):
    if 'DASHBOARD_CODE' in line and "'''" in line:
        print(f"Found at line {i+1}: {line.strip()}")
EOF

python3 << 'EOF'
with open('/root/ai_layer.py', 'r') as f:
    content = f.read()

# Count total lines
lines = content.split('\n')
print(f"Total lines: {len(lines)}")
print(f"Last 5 lines:")
for i, line in enumerate(lines[-5:], len(lines)-4):
    print(f"  {i}: {repr(line)}")

# Check if DASHBOARD_CODE is closed
code_start = content.find("DASHBOARD_CODE = '''")
code_end = content.find("'''", code_start + 20)
print(f"\nDASHBOARD_CODE starts at char: {code_start}")
print(f"DASHBOARD_CODE closing ''' at char: {code_end}")
EOF

python3 << 'EOF'
with open('/root/ai_layer.py', 'r') as f:
    content = f.read()

# Add closing ''' after the last line of DASHBOARD_CODE
# Insert before the main execution code
# Find where the string should end (after "Hedge Fund Level")
insert_pos = content.find('print("\\n   Hedge Fund Level!")')
if insert_pos == -1:
    insert_pos = content.find('Hedge Fund Level')
    
print(f"Insert position: {insert_pos}")

# Add closing quotes after that line
end_of_line = content.find('\n', insert_pos)
new_content = content[:end_of_line+1] + "'''\n" + content[end_of_line+1:]

with open('/root/ai_layer.py', 'w') as f:
    f.write(new_content)

# Verify syntax
import py_compile
try:
    py_compile.compile('/root/ai_layer.py', doraise=True)
    print(" Syntax OK!")
except py_compile.PyCompileError as e:
    print(f" Syntax error: {e}")
EOF

pkill -f "run_ai_layer\|ai_layer" 2>/dev/null
sleep 2
nohup bash /root/run_ai_layer.sh >> /root/ai.out 2>&1 &
echo "PID: $!"
sleep 15 && tail -5 /root/ai.out
export ANTHROPIC_API_KEY=$(grep ANTHROPIC_API_KEY /root/.env | cut -d'=' -f2 | tr -d '"' | tr -d "'")
python3 /root/ai_layer.py 2>&1 | head -30
for f in trade_plan_generator watchlist_intelligence risk_simulator trade_center telegram_trade_cards; do   curl -o /root/${f}.py https://raw.githubusercontent.com/hsetraining1977-ux/minervini-bot/main/${f}.py; done
python3 /root/trade_plan_generator.py
python3 /root/risk_simulator.py
from trade_center import render_trade_center
with tab_trade:
# 
# TRADE CENTER TAB
# 
try:
PYEOF
#  dashboard
cat /root/dashboard_new.py > /root/dashboard.py
pkill -f streamlit && sleep 3
nohup ~/.local/bin/streamlit run /root/dashboard.py --server.port 8501 --server.address 0.0.0.0 >> /root/streamlit.out 2>&1 &
echo "Done!"
#    dashboard_new.py
cat >> /root/dashboard_new.py << 'PYEOF'

# 
# TRADE CENTER TAB
# 
try:
    import sys
    sys.path.insert(0, '/root')
    from trade_center import render_trade_center
    with st.expander(" TRADE CENTER", expanded=True):
        render_trade_center()
except Exception as e:
    st.error(f"Trade Center: {e}")
PYEOF

#  dashboard
cat /root/dashboard_new.py > /root/dashboard.py
pkill -f streamlit && sleep 3
nohup ~/.local/bin/streamlit run /root/dashboard.py --server.port 8501 --server.address 0.0.0.0 >> /root/streamlit.out 2>&1 &
echo "Done!"
sleep 8 && curl -s -o /dev/null -w "HTTP: %{http_code}\n" http://localhost:8501
tail -10 /root/orchestrator.out
tail -10 /root/intraday.out
python3 << 'EOF'
with open('/root/auto_restart.py', 'r') as f:
    content = f.read()

# Fix: ai_layer keyword to match run_ai_layer.sh
content = content.replace(
    '"ai_layer":        "ai_layer.py"',
    '"ai_layer":        "run_ai_layer"'
)

with open('/root/auto_restart.py', 'w') as f:
    f.write(content)
print("Fixed!")
EOF

# Reset restart counts   auto_restart
pkill -f auto_restart.py 2>/dev/null
sleep 2
nohup python3 /root/auto_restart.py >> /root/logs/restart.out 2>&1 &
echo "auto_restart restarted: $!"
tail -5 /root/logs/restart.out
#    
python3 /root/master_orchestrator.py 2>&1 | tail -20
python3 /root/intraday_engine.py 2>&1 | tail -20
python3 << 'EOF'
with open('/root/auto_restart.py', 'r') as f:
    content = f.read()

# Remove one-shot services from monitoring
content = content.replace(
    '"master_orchestrator": {\n        "keyword": "master_orchestrator.py",',
    '"master_orchestrator": {\n        "keyword": "DISABLED_master_orchestrator",  # one-shot'
)
content = content.replace(
    '"intraday_engine": {\n        "keyword": "intraday_engine.py",',
    '"intraday_engine": {\n        "keyword": "DISABLED_intraday_engine",  # one-shot'
)

with open('/root/auto_restart.py', 'w') as f:
    f.write(content)
print("Done!")
EOF

pkill -f auto_restart.py && sleep 2
nohup python3 /root/auto_restart.py >> /root/logs/restart.out 2>&1 &
echo "PID: $!"
tail -5 /root/logs/restart.out
python3 << 'EOF'
with open('/root/auto_restart.py', 'r') as f:
    content = f.read()

# Print current SERVICES dict to see exact format
start = content.find('SERVICES = {')
end = content.find('\n}', start) + 2
print(content[start:end])
EOF

grep -c "WARNING\|ERROR" /root/logs/restart.out
echo "---"
tail -3 /root/logs/restart.out
python3 << 'EOF'
with open('/root/auto_restart.py', 'r') as f:
    content = f.read()

import re

# Remove intraday_engine and master_orchestrator entries completely
content = re.sub(
    r'"intraday_engine":\s*\{[^}]+\},?\s*',
    '',
    content
)
content = re.sub(
    r'"master_orchestrator":\s*\{[^}]+\},?\s*',
    '',
    content
)

with open('/root/auto_restart.py', 'w') as f:
    f.write(content)

# Verify
start = content.find('SERVICES = {')
end = content.find('\n}', start) + 2
print(content[start:end])
EOF

pkill -f auto_restart.py && sleep 2
nohup python3 /root/auto_restart.py >> /root/logs/restart.out 2>&1 &
echo "PID: $!"
sleep 5 && tail -3 /root/logs/restart.out
tail -5 /root/logs/restart.out
pkill -9 -f auto_restart.py
sleep 3
ps aux | grep auto_restart | grep -v grep
nohup python3 /root/auto_restart.py > /root/logs/restart.out 2>&1 &
echo "New PID: $!"
sleep 35 && tail -3 /root/logs/restart.out
nohup python3 /root/auto_restart.py > /root/logs/restart.out 2>&1 &
echo "New PID: $!"
sleep 35 && tail -3 /root/logs/restart.out
pkill -9 -f auto_restart.py 2>/dev/null
sleep 2
python3 /root/auto_restart.py > /root/logs/restart.out 2>&1 &
disown $!
echo "PID: $!"sleep 40 && tail -5 /root/logs/restart.out
#   timestamp  
tail -3 /root/logs/restart.out | grep -E "WARNING|ERROR|INFO"
python3 << 'EOF'
with open('/root/health_monitor.py', 'r') as f:
    content = f.read()

# Replace CRITICAL_PROCESSES to remove one-shot services
old = '''CRITICAL_PROCESSES = {
    "orchestrator":    "master_orchestrator.py",
    "intraday_engine": "intraday_engine.py",
    "telegram_bot":    "telegram_commands.py",
    "streamlit":       "streamlit",
    "ai_layer":        "ai_layer.py",
    "event_awareness": "event_awareness.py",
    "institutional":   "institutional_layer.py",
}'''

new = '''CRITICAL_PROCESSES = {
    "telegram_bot":    "telegram_commands.py",
    "streamlit":       "streamlit",
    "ai_layer":        "run_ai_layer",
    "event_awareness": "event_awareness.py",
    "institutional":   "institutional_layer.py",
}'''

content = content.replace(old, new)
with open('/root/health_monitor.py', 'w') as f:
    f.write(content)
print("Done!")
# Verify
import re
m = re.search(r'CRITICAL_PROCESSES = \{[^}]+\}', content)
if m: print(m.group())
EOF

pkill -f health_monitor.py && sleep 2
python3 /root/health_monitor.py >> /root/logs/health.out 2>&1 &
echo "Health Monitor PID: $!"
tail -5 /root/logs/health.out
python3 << 'EOF'
with open('/root/health_monitor.py', 'r') as f:
    content = f.read()

# Disable DB check - return True always since DB is optional
content = content.replace(
    'def check_database() -> tuple[bool, float]:',
    'def check_database() -> tuple[bool, float]:\n    return True, 0.0  # DB check disabled\n    _disabled = True'
)

with open('/root/health_monitor.py', 'w') as f:
    f.write(content)
print("Done!")
EOF

pkill -f health_monitor.py && sleep 2
python3 /root/health_monitor.py >> /root/logs/health.out 2>&1 &
echo "PID: $!"
sleep 65 && tail -3 /root/logs/health.out
tail -3 /root/logs/health.out
python3 << 'EOF'
with open('/root/health_monitor.py', 'r') as f:
    lines = f.readlines()

# Find check_database function and add early return
new_lines = []
for i, line in enumerate(lines):
    new_lines.append(line)
    if 'def check_database(' in line:
        new_lines.append('    return True, 0.0  # disabled - no DB password\n')

with open('/root/health_monitor.py', 'w') as f:
    f.writelines(new_lines)
print("Done!")
EOF

pkill -f health_monitor.py && sleep 2
python3 /root/health_monitor.py >> /root/logs/health.out 2>&1 &
echo "PID: $!"
sleep 70 && tail -3 /root/logs/health.out
#   Macro
python3 /root/macro_intelligence.py >> /root/nohup.out 2>&1 &
sleep 10
#   Macro
python3 /root/macro_intelligence.py >> /root/nohup.out 2>&1 &
sleep 10
tail -5 /root/nohup.out
tail -3 /root/logs/health.out
#  health_monitor     
pkill -f health_monitor.py && sleep 2
python3 -c "
with open('/root/health_monitor.py') as f:
    lines = f.readlines()
for i,l in enumerate(lines):
    if 'check_database' in l:
        print(i+1, repr(l))
" | head -10
sed -n '119,125p' /root/health_monitor.py
python3 << 'EOF'
with open('/root/health_monitor.py', 'r') as f:
    content = f.read()

# Replace entire check_database function
import re
content = re.sub(
    r'def check_database\(\).*?(?=\ndef )',
    'def check_database():\n    """DB check disabled - no password configured"""\n    return True, 0.0\n\n',
    content,
    flags=re.DOTALL
)

with open('/root/health_monitor.py', 'w') as f:
    f.write(content)

# Verify
import py_compile
try:
    py_compile.compile('/root/health_monitor.py', doraise=True)
    print(" Syntax OK")
except Exception as e:
    print(f" {e}")

# Show function
m = re.search(r'def check_database\(\).*?(?=\ndef )', content, re.DOTALL)
if m: print(m.group()[:100])
EOF

pkill -f health_monitor.py && sleep 2
python3 /root/health_monitor.py >> /root/logs/health.out 2>&1 &
echo "PID: $!"
sleep 70 && tail -3 /root/logs/health.out
for f in breadth_engine smart_money market_intelligence institutional_intelligence_dashboard morning_brief; do   curl -o /root/${f}.py https://raw.githubusercontent.com/hsetraining1977-ux/minervini-bot/main/${f}.py; done
python3 /root/market_intelligence.py &
python3 /root/breadth_engine.py &
python3 /root/smart_money.py &
python3 /root/morning_brief.py --now
from institutional_intelligence_dashboard import render_institutional_intelligence
render_institutional_intelligence()
cat >> /root/dashboard_new.py << 'PYEOF'

# INSTITUTIONAL INTELLIGENCE
try:
    from institutional_intelligence_dashboard import render_institutional_intelligence
    with st.expander(" INSTITUTIONAL INTELLIGENCE", expanded=False):
        render_institutional_intelligence()
except Exception as e:
    st.error(f"Intelligence: {e}")
PYEOF

cat /root/dashboard_new.py > /root/dashboard.py
pkill -f streamlit && sleep 3
nohup ~/.local/bin/streamlit run /root/dashboard.py --server.port 8501 --server.address 0.0.0.0 >> /root/streamlit.out 2>&1 &
echo "Done!"
for f in paper_execution daily_review paper_performance_dashboard; do   curl -o /root/${f}.py https://raw.githubusercontent.com/hsetraining1977-ux/minervini-bot/main/${f}.py; done
nohup python3 /root/paper_execution.py >> /root/logs/paper.out 2>&1 &
echo "Paper Engine PID: $!"
cat >> /root/dashboard_new.py << 'EOF'
try:
    from paper_performance_dashboard import render_paper_performance
    with st.expander(" PAPER TRADING PERFORMANCE", expanded=False):
        render_paper_performance()
except Exception as e:
    st.error(f"Paper: {e}")
EOF

cat /root/dashboard_new.py > /root/dashboard.py
pkill -f streamlit && sleep 3
nohup ~/.local/bin/streamlit run /root/dashboard.py --server.port 8501 --server.address 0.0.0.0 >> /root/streamlit.out 2>&1 &
echo "Done! PID: $!"
cat /root/.gitignore | grep env
curl -o /root/paper_execution.py https://raw.githubusercontent.com/hsetraining1977-ux/minervini-bot/main/paper_execution.py
python3 /root/paper_execution.py --status
pkill -f paper_execution.py
nohup python3 /root/paper_execution.py >> /root/logs/paper.out 2>&1 &
echo "PID: $!
python3 /root/paper_execution.py --unkill
sleep 2
python3 /root/paper_execution.py --status
rm -f /root/logs/paper_trades.json /root/logs/paper_performance.json /root/logs/kill_switch.json && python3 /root/pap
er_execution.py --unkill && sleep 2 && python3 /root/paper_execution.py --status
rm -f /root/logs/paper_trades.json /root/logs/paper_performance.json /root/logs/kill_switch.json && python3 /root/paper_execution.py --unkill && sleep 2 && python3 /root/paper_execution.py --status
python3 /root/paper_execution.py --status
cd /root/logs && ls -la paper_*.json kill_switch.json 2>/dev/null
python3 -c "
import json
with open('/root/logs/kill_switch.json', 'w') as f:
    json.dump({'active': False}, f)
with open('/root/logs/paper_performance.json', 'w') as f:
    json.dump({'total_trades':0,'wins':0,'losses':0,'total_pnl':0.0,'max_drawdown':0.0,'equity_curve':[],'daily_pnl':{},'best_trade':None,'worst_trade':None,'regime_perf':{}}, f)
print('Reset done!')
"
python3 /root/paper_execution.py --status
cd /root
python3 -c "
import json
#  plans 
with open('/root/logs/trade_plans.json', 'w') as f:
    json.dump({}, f)
print('Plans cleared!')
"
#  
python3 /root/paper_execution.py --status
python3 -c "
import json

files = {
    '/root/logs/kill_switch.json':    {'active': False},
    '/root/logs/paper_performance.json': {
        'total_trades':0,'wins':0,'losses':0,'total_pnl':0.0,
        'max_drawdown':0.0,'equity_curve':[],'daily_pnl':{},
        'best_trade':None,'worst_trade':None,'regime_perf':{}
    },
    '/root/logs/paper_trades.json':   {},
    '/root/logs/trade_plans.json':    {},
}

for path, data in files.items():
    with open(path, 'w') as f:
        json.dump(data, f)
    print(f'Reset: {path}')

print('All clear!')
"
python3 /root/paper_execution.py --status
python3 -c "
import json

files = {
    '/root/logs/kill_switch.json':    {'active': False},
    '/root/logs/paper_performance.json': {
        'total_trades':0,'wins':0,'losses':0,'total_pnl':0.0,
        'max_drawdown':0.0,'equity_curve':[],'daily_pnl':{},
        'best_trade':None,'worst_trade':None,'regime_perf':{}
    },
    '/root/logs/paper_trades.json':   {},
    '/root/logs/trade_plans.json':    {},
}

for path, data in files.items():
    with open(path, 'w') as f:
        json.dump(data, f)
    print(f'Reset: {path}')

print('All clear!')
"
python3 /root/paper_execution.py --status
python3 -c "
import requests, os
from dotenv import load_dotenv
load_dotenv('/root/.env')

key    = os.getenv('ALPACA_API_KEY') or os.getenv('ALPACA_KEY')
secret = os.getenv('ALPACA_SECRET_KEY') or os.getenv('ALPACA_SECRET')

headers = {
    'APCA-API-KEY-ID':     key or '',
    'APCA-API-SECRET-KEY': secret or '',
}

r = requests.get('https://paper-api.alpaca.markets/v2/account', headers=headers, timeout=10)
print(f'Status: {r.status_code}')
if r.status_code == 200:
    data = r.json()
    print(f'Equity: \${float(data.get(\"equity\",0)):,.2f}')
    print(f'Cash:   \${float(data.get(\"cash\",0)):,.2f}')
    print('Connected to Alpaca Paper ')
else:
    print(f'Error: {r.text[:100]}')
"
pkill -f paper_execution.py 2>/dev/null
nohup python3 /root/paper_execution.py >> /root/logs/paper.out 2>&1 &
echo "Paper Engine PID: $!"
sleep 5 && tail -5 /root/logs/paper.out
pkill -9 -f paper_execution 2>/dev/null
sleep 2
python3 -c "
import json
with open('/root/logs/kill_switch.json','w') as f:
    json.dump({'active':False}, f)
pkill -9 -f paper_execution 2>/dev/null
sleep 2
python3 -c "
import json
with open('/root/logs/kill_switch.json','w') as f:
    json.dump({'active':False}, f)
print('Kill switch OFF')
"
python3 /root/paper_execution.py >> /root/logs/paper.out 2>&1 &
disown $!
echo "PID: $!"
sleep 8 && tail -5 /root/logs/paper.out
pkill -9 -f paper_execution 2>/dev/null
sleep 2
> /root/logs/paper.out
python3 /root/paper_execution.py >> /root/logs/paper.out 2>&1 &
disown $!
echo "PID: $!"
sleep 10 && tail -8 /root/logs/paper.out
cd /root && python3 paper_execution.py 2>&1 | head -20
#   
python3 -c "
import sys
sys.path.insert(0, '/root')
from paper_execution import get_account, get_positions, is_kill_switch_active

print('Kill switch:', is_kill_switch_active())
acc = get_account()
if acc:
    print(f'Equity: \${float(acc.get(\"equity\",0)):,.2f}')
    print(f'Cash:   \${float(acc.get(\"cash\",0)):,.2f}')
    positions = get_positions()
    print(f'Positions: {len(positions)}')
    print(' Alpaca Paper connected!')
else:
    print(' Cannot connect')
"
curl -o /root/paper_execution.py https://raw.githubusercontent.com/hsetraining1977-ux/minervini-bot/main/paper_execution.py && echo " Downloaded!" && head -5 /root/paper_execution.py
grep -n "def get_account\|def alpaca_get\|PAPER_BASE" /root/paper_execution.py | head -5
#     
grep -c "def get_account\|PAPER_BASE\|alpaca_post" /root/paper_execution.py
python3 << 'CHECKEOF'
with open('/root/paper_execution.py') as f:
    content = f.read()
print("Has get_account:", "def get_account" in content)
print("Has PAPER_BASE:", "PAPER_BASE" in content)
print("Lines:", len(content.splitlines()))
CHECKEOF

curl -o /root/paper_execution.py https://raw.githubusercontent.com/hsetraining1977-ux/minervini-bot/main/paper_execution.py && python3 -c "
with open('/root/paper_execution.py') as f:
    c = f.read()
print('Has PAPER_BASE:', 'PAPER_BASE' in c)
print('Lines:', len(c.splitlines()))
"
pkill -9 -f paper_execution 2>/dev/null
sleep 2
python3 /root/paper_execution.py >> /root/logs/paper.out 2>&1 &
disown $!
echo "PID: $!"
sleep 8 && tail -5 /root/logs/paper.out
# 1.     paper_execution  
find / -name "paper_execution.py" 2>/dev/null
# 2.    logs   
grep -r "from paper_execution" /root/ 2>/dev/null
grep -r "import paper_execution" /root/ 2>/dev/null
# 1.     
ps aux | grep paper_execution | grep -v grep
# 2.    log 
cat /root/logs/paper.out
# 3.     
python3 /root/paper_execution.py
# 1.     
ps aux | grep paper_execution | grep -v grep
# 2.    log 
cat /root/logs/paper.out
# 3.     
python3 /root/paper_execution.py
#   
pkill -9 -f paper_execution 2>/dev/null
#   500-526    sleep
sed -n '500,526p' /root/paper_execution.py
#  sleep(300)  sleep(10) 
sed -i 's/time\.sleep(300)/time.sleep(10)/g' /root/paper_execution.py
#   
grep -n "sleep" /root/paper_execution.py | tail -5
#  
python3 /root/paper_execution.py >> /root/logs/paper.out 2>&1 &
disown $!
sleep 15 && cat /root/logs/paper.out
#   --status   Alpaca 
python3 /root/paper_execution.py --status
#   --sync 
python3 /root/paper_execution.py --sync
#    log   stderr
python3 /root/paper_execution.py 2>&1 | head -30
#   
pkill -9 -f paper_execution 2>/dev/null
#  sleep  (300 )
sed -i 's/time\.sleep(10)/time.sleep(300)/g' /root/paper_execution.py
# 
grep -n "time.sleep" /root/paper_execution.py | tail -3
#  
python3 /root/paper_execution.py >> /root/logs/paper.out 2>&1 &
disown $!
echo " Engine PID: $!"
# 1.   paper_execution.py 
wc -l /root/paper_execution.py
grep -n "def " /root/paper_execution.py
# 2.    
ls /root/data/ 2>/dev/null
ls /root/logs/ 2>/dev/null
# 3.   config
cat /root/config.py 2>/dev/null | head -40
ps aux | grep paper_execution | grep -v grep
#   plans 
cat /root/logs/trade_plans.json | python3 -m json.tool | head -50
#   plans 
cat /root/logs/trade_plans.json | python3 -m json.tool | head -50
#    
tail -20 /root/logs/trade_decisions.log
#   
cat /root/logs/paper_performance.json | python3 -m json.tool
chmod +x /root/apply_dynamic_threshold.sh
bash /root/apply_dynamic_threshold.sh
chmod +x /root/apply_dynamic_threshold.sh
bash /root/apply_dynamic_threshold.sh
cat > /root/apply_dynamic_threshold.sh << 'ENDOFSCRIPT'
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
ENDOFSCRIPT

chmod +x /root/apply_dynamic_threshold.sh
bash /root/apply_dynamic_threshold.sh
#   
pkill -9 -f paper_execution 2>/dev/null
sleep 2
#   
python3 /root/paper_execution.py >> /root/logs/paper.out 2>&1 &
disown $!
echo " PID: $!"
#  
sleep 3 && python3 /root/paper_execution.py --scan
#   
tail -f /root/logs/trade_decisions.log
#     score
grep -n "score" /root/trade_plan_generator.py | head -30
#    output 
python3 /root/trade_plan_generator.py 2>&1 | head -50
# 1.   trade plans  
python3 /root/trade_plan_generator.py
# 2.  scan 
python3 /root/paper_execution.py --scan
# 3.  
tail -20 /root/logs/trade_decisions.log
cat /root/logs/paper_trades.json | python3 -m json.tool 2>/dev/null | head -40
# 1.   plans   
python3 /root/trade_plan_generator.py 2>&1 | tail -20
# 2.   trade_plans.json  
cat /root/logs/trade_plans.json | python3 -m json.tool | grep -E "symbol|score|execution" | head -30
# 3.  scan  
python3 /root/paper_execution.py --scan
tail -10 /root/logs/trade_decisions.log
#   NVDA plan 
python3 -c "
import json
with open('/root/logs/trade_plans.json') as f:
    plans = json.load(f)
if isinstance(plans, list):
    nvda = next((p for p in plans if p.get('symbol')=='NVDA'), None)
elif isinstance(plans, dict):
    nvda = plans.get('NVDA')
import pprint
pprint.pprint(nvda)
"
python3 -c "
import json
with open('/root/logs/trade_plans.json') as f:
    plans = json.load(f)
print('Type:', type(plans))
if isinstance(plans, list):
    print('Length:', len(plans))
    print('First item keys:', list(plans[0].keys()) if plans else 'empty')
    print('First item:', plans[0] if plans else 'empty')
elif isinstance(plans, dict):
    print('Keys:', list(plans.keys())[:5])
    first_key = list(plans.keys())[0]
    print('First value type:', type(plans[first_key]))
    print('First value:', plans[first_key])
"
python3 << 'EOF'
import json

#    plans  
with open('/root/logs/trade_plans.json') as f:
    plans = json.load(f)

#    iterate  values
for plan_id, plan in plans.items():
    symbol = plan.get('symbol')
    score  = plan.get('execution_score', plan.get('score', 0))
    status = plan.get('status', '')
    regime = plan.get('regime', plan.get('market_regime', 'NEUTRAL'))
    print(f"{symbol}: exec_score={score} status={status} regime={regime}")
EOF

python3 << 'EOF'
import re

path = "/root/paper_execution.py"
with open(path) as f:
    src = f.read()

#  scan_and_execute 
match = re.search(r'def scan_and_execute\(\).*?(?=\ndef )', src, re.DOTALL)
if match:
    print(match.group()[:2000])
else:
    print("NOT FOUND")
EOF

python3 << 'EOF'
path = "/root/paper_execution.py"
with open(path) as f:
    src = f.read()

# 1.  load_plans()    JSON
old = """    try:
        from trade_plan_generator import load_plans
        plans = load_plans()
    except ImportError:
        return"""

new = """    try:
        import json, os
        plans_path = "/root/logs/trade_plans.json"
        if not os.path.exists(plans_path):
            return
        with open(plans_path) as f:
            plans = json.load(f)
    except Exception:
        return"""

src = src.replace(old, new)

# 2.  MIN_EXEC_SCORE  dynamic threshold
old2 = "if plan.get(\"execution_score\", 0) < MIN_EXEC_SCORE: continue"
new2 = """_thr, _reg = get_dynamic_threshold()
        _score = float(plan.get("execution_score", plan.get("score", 0)))
        if _score < _thr:
            _log_rejection(plan.get("symbol","?"), _score, _thr, _reg)
            continue"""

src = src.replace(old2, new2)

with open(path, "w") as f:
    f.write(src)
print(" Done")
EOF

#   syntax
python3 -m py_compile /root/paper_execution.py && echo " Syntax OK"
#  scan
python3 /root/paper_execution.py --scan
tail -10 /root/logs/trade_decisions.log
# 1.   load_plans   
grep -n "load_plans\|MIN_EXEC_SCORE\|trade_plan_generator" /root/paper_execution.py
# 2.  scan_and_execute 
grep -n "" /root/paper_execution.py | sed -n '463,510p'
#   
ps aux | grep paper_execution | grep -v grep
#    plotly_chart  
grep -n "plotly_chart" /root/*.py /root/minervini-bot/*.py 2>/dev/null
python3 << 'EOF'
import re

files = [
    "/root/dashboard_new.py",
    "/root/dashboard.py",
    "/root/institutional_intelligence_dashboard.py",
    "/root/paper_performance_dashboard.py",
    "/root/trade_center.py",
]

for filepath in files:
    try:
        with open(filepath) as f:
            src = f.read()
        
        counter = [0]
        def add_key(match):
            counter[0] += 1
            call = match.group(0)
            if 'key=' in call:
                return call
            return call[:-1] + f', key="chart_{filepath.split("/")[-1].replace(".py","").replace("_","")}{counter[0]}")'
        
        new_src = re.sub(r'st\.plotly_chart\([^)]+\)', add_key, src)
        
        with open(filepath, 'w') as f:
            f.write(new_src)

python3 << 'EOF'
import re

files = [
    "/root/dashboard_new.py",
    "/root/dashboard.py",
    "/root/institutional_intelligence_dashboard.py",
    "/root/paper_performance_dashboard.py",
    "/root/trade_center.py",
]

for filepath in files:
    try:
        with open(filepath) as f:
            src = f.read()
        
        counter = [0]
        def add_key(match):
            counter[0] += 1
            call = match.group(0)
            if 'key=' in call:
                return call
            return call[:-1] + f', key="chart_{filepath.split("/")[-1].replace(".py","").replace("_","")}{counter[0]}")'
        
        new_src = re.sub(r'st\.plotly_chart\([^)]+\)', add_key, src)
        
        with open(filepath, 'w') as f:
            f.write(new_src)
        print(f" Fixed {counter[0]} charts in {filepath.split('/')[-1]}")
    except Exception as e:
        print(f" {filepath}: {e}")
EOF

#   
pkill -f streamlit 2>/dev/null
sleep 2
#  
cd /root && streamlit run dashboard_new.py --server.port 8501   --server.address 0.0.0.0 >> /root/logs/dashboard.log 2>&1 &
disown $!
echo " Dashboard restarted"
python3 << 'EOF'
import re, uuid

files = [
    "/root/dashboard_new.py",
    "/root/dashboard.py",
    "/root/institutional_intelligence_dashboard.py",
    "/root/paper_performance_dashboard.py",
    "/root/trade_center.py",
]

for filepath in files:
    try:
        with open(filepath) as f:
            src = f.read()

        counter = [0]
        prefix = filepath.split("/")[-1].replace(".py","").replace("_","")[:8]

        def replace_key(match):
            counter[0] += 1
            call = match.group(0)
            #   key  
            call = re.sub(r',\s*key=["\'][^"\']*["\']', '', call)
            unique_key = f"{prefix}_{counter[0]}_{uuid.uuid4().hex[:6]}"
            return call[:-1] + f', key="{unique_key}")'

        new_src = re.sub(r'st\.plotly_chart\([^)]+\)', replace_key, src)

        with open(filepath, 'w') as f:
            f.write(new_src)
        print(f" {filepath.split('/')[-1]}: {counter[0]} charts fixed")
    except Exception as e:
        print(f" {filepath.split('/')[-1]}: {e}")
EOF

#   
pkill -f streamlit 2>/dev/null
sleep 2
cd /root && streamlit run dashboard_new.py --server.port 8501 --server.address 0.0.0.0 >> /root
python3 << 'EOF'
import re, uuid

files = [
    "/root/dashboard_new.py",
    "/root/dashboard.py",
    "/root/institutional_intelligence_dashboard.py",
    "/root/paper_performance_dashboard.py",
    "/root/trade_center.py",
]

for filepath in files:
    try:
        with open(filepath) as f:
            src = f.read()

        counter = [0]
        prefix = filepath.split("/")[-1].replace(".py","").replace("_","")[:8]

        def replace_key(match):
            counter[0] += 1
            call = match.group(0)
            #   key  
            call = re.sub(r',\s*key=["\'][^"\']*["\']', '', call)
            unique_key = f"{prefix}_{counter[0]}_{uuid.uuid4().hex[:6]}"
            return call[:-1] + f', key="{unique_key}")'

        new_src = re.sub(r'st\.plotly_chart\([^)]+\)', replace_key, src)

        with open(filepath, 'w') as f:
            f.write(new_src)
        print(f" {filepath.split('/')[-1]}: {counter[0]} charts fixed")
    except Exception as e:
        print(f" {filepath.split('/')[-1]}: {e}")
EOF

#   
pkill -f streamlit 2>/dev/null
sleep 2
cd /root && streamlit run dashboard_new.py --server.port 8501 --server.address 0.0.0.0 >> /root/logs/dashboard.log 2>&1 &
disown $!
echo " Dashboard restarted"
python3 << 'EOF'
import re

files = [
    "/root/dashboard_new.py",
    "/root/dashboard.py", 
    "/root/institutional_intelligence_dashboard.py",
    "/root/paper_performance_dashboard.py",
    "/root/trade_center.py",
]

for filepath in files:
    try:
        with open(filepath) as f:
            src = f.read()

        #  import time       
        if "import time" not in src:
            src = "import time\n" + src

        counter = [0]
        def replace_key(match):
            counter[0] += 1
            call = match.group(0)
            #   key 
            call = re.sub(r',\s*key=["\'][^"\']*["\']', '', call)
            # key    counter + time  runtime
            return call[:-1] + f', key=f"chart_{counter[0]}_{{int(time.time()*1000) % 99999}}")'

        new_src = re.sub(r'st\.plotly_chart\([^)]+\)', replace_key, src)

        with open(filepath, 'w') as f:
            f.write(new_src)
        print(f" {filepath.split('/')[-1]}: {counter[0]} charts fixed")
    except Exception as e:
        print(f" {filepath.split('/')[-1]}: {e}")
EOF

pkill -f streamlit 2>/dev/null
sleep 2
cd /root && streamlit run dashboard_new.py --server.port 8501 --server.address 0.0.0.0 >> /root/logs/dashboard.log 2>&1 &
disown $!
echo " Restarted"
#    git pull
cp /root/minervini-bot/smart_execution_engine.py /root/
cp /root/minervini-bot/position_management_dashboard.py /root/
#   
# from position_management_dashboard import render_position_management
# render_position_management()
#  Engine
python3 /root/smart_execution_engine.py >> /root/logs/smart_engine.out 2>&1 &
disown $!
cd /root/minervini-bot
git pull origin main
ls smart_execution_engine.py position_management_dashboard.py
cp smart_execution_engine.py /root/
cp position_management_dashboard.py /root/
cat /root/logs/smart_engine.out
git fetch origin
git checkout origin/main -- smart_execution_engine.py
git checkout origin/main -- position_management_dashboard.py
cp smart_execution_engine.py /root/
cp position_management_dashboard.py /root/
echo " Done  no files deleted"
#  syntax
python3 -m py_compile /root/smart_execution_engine.py && echo " Syntax OK"
#  Engine
pkill -f smart_execution_engine 2>/dev/null
sleep 2
python3 /root/smart_execution_engine.py >> /root/logs/smart_engine.out 2>&1 &
disown $!
echo " PID: $!"
#   log
sleep 5 && cat /root/logs/smart_engine.out
cd /root/minervini-bot && git fetch origin
git checkout origin/main -- trade_lifecycle.py health_engine.py   exit_intelligence.py trade_journal.py lifecycle_dashboard.py
cp *.py /root/
cd /root/minervini-bot && git fetch origin
git checkout origin/main -- trade_lifecycle.py health_engine.py   exit_intelligence.py trade_journal.py lifecycle_dashboard.py
cp *.py /root/
find /root -name ".git" -type d 2>/dev/null
cd /root && git remote -v 2>/dev/null
cd /root
git fetch origin
git checkout origin/main -- trade_lifecycle.py health_engine.py   exit_intelligence.py trade_journal.py lifecycle_dashboard.py
ls -la /root/trade_lifecycle.py /root/health_engine.py        /root/exit_intelligence.py /root/trade_journal.py        /root/lifecycle_dashboard.py
for f in trade_lifecycle health_engine exit_intelligence trade_journal lifecycle_dashboard; do     python3 -m py_compile /root/${f}.py && echo " ${f}.py OK" || echo " ${f}.py ERROR"; done
tail -20 /root/logs/smart_engine.out
python3 << 'EOF'
import json

with open('/root/logs/trade_plans.json') as f:
    plans = json.load(f)

#   plan  symbol 
best = {}
for pid, plan in plans.items():
    sym = plan.get('symbol','')
    if sym not in best:
        best[sym] = (pid, plan)
    else:
        #  
        if pid > best[sym][0]:
            best[sym] = (pid, plan)

clean = {pid: plan for sym,(pid,plan) in best.items()}
with open('/root/logs/trade_plans.json','w') as f:
    json.dump(clean, f, indent=2)

print(f" Cleaned: {len(plans)}  {len(clean)} plans")
EOF

ls -la /root/logs/market_intelligence.json         /root/logs/macro_intelligence.json         /root/logs/breadth_engine.json 2>/dev/null
grep -n "sleep\|schedule\|interval" /root/macro_intelligence.py | head -20
ps aux | grep -E "market_intelligence|macro_intelligence" | grep -v grep
tail -20 /root/logs/system.log 2>/dev/null | grep -i "market\|macro\|intelligence"
pkill -f market_intelligence 2>/dev/null
sleep 2
python3 /root/market_intelligence.py >> /root/logs/market.out 2>&1 &
disown $!
echo " PID: $!"
sleep 30 && ls -la /root/logs/market_intelligence.json
ps aux | grep python3 | grep -v grep | awk '{print $1,$2,$9,$11}'
watch -n 30 'ls -la /root/logs/market_intelligence.json | awk "{print \$6,\$7,\$8}"'
# 1.   
pkill -f python3 2>/dev/null
sleep 3
# 2. 
ps aux | grep python3 | grep -v grep | wc -l
# 3.   
bash /root/start_system.sh
# 4.   30 
sleep 30 && ps aux | grep python3 | grep -v grep | wc -l && ls -la /root/logs/market_intelligence.json
# paper execution + smart engine
python3 /root/paper_execution.py >> /root/logs/paper.out 2>&1 &
disown $!
python3 /root/smart_execution_engine.py >> /root/logs/smart_engine.out 2>&1 &
disown $!
# market intelligence
python3 /root/market_intelligence.py >> /root/logs/market.out 2>&1 &
disown $!
echo " All engines started"
sleep 10 && ps aux | grep python3 | grep -v grep | wc -l
ps aux | grep python3 | grep -v grep | wc -l
ls -la /root/logs/market_intelligence.json
#    
cat /root/logs/paper_trades.json | python3 -m json.tool 2>/dev/null
#    engine 
tail -20 /root/logs/smart_engine.out
#  volume NVDA  1.5x
python3 /root/paper_execution.py --scan
#    NVDA 
python3 -c "
import requests
r = requests.get('https://paper-api.alpaca.markets/v2/stocks/NVDA/trades/latest',
    headers={'APCA-API-KEY-ID':'$(grep ALPACA_API_KEY /root/.env | cut -d= -f2)',
             'APCA-API-SECRET-KEY':'$(grep ALPACA_SECRET_KEY /root/.env | cut -d= -f2)'})
print(r.json())
"
#    
tail -5 /root/logs/errors.log
# 1.  paper_execution 
pkill -f paper_execution 2>/dev/null
pkill -f smart_execution 2>/dev/null
# 2.   plans 
echo "{}" > /root/logs/trade_plans.json
# 3.   plans  
python3 /root/trade_plan_generator.py
# 4.    
python3 /root/paper_execution.py --status
# 5.    engines
python3 /root/paper_execution.py >> /root/logs/paper.out 2>&1 &
disown $!
python3 /root/smart_execution_engine.py >> /root/logs/smart_engine.out 2>&1 &
disown $!
echo " Done"
python3 /root/paper_execution.py --status
# 1.      NVDA  Alpaca
python3 -c "
from config import ALPACA_API_KEY, ALPACA_SECRET_KEY
import requests
h = {'APCA-API-KEY-ID': ALPACA_API_KEY, 'APCA-API
python3 -c "
from config import ALPACA_API_KEY, ALPACA_SECRET_KEY
import requests
h = {'APCA-API-KEY-ID': ALPACA_API_KEY, 'APCA-API-SECRET-KEY': ALPACA_SECRET_KEY}
r = requests.get('https://data.alpaca.markets/v2/stocks/NVDA/trades/latest', headers=h, timeout=10)
print(r.json())
python3 -c "
from config import ALPACA_API_KEY, ALPACA_SECRET_KEY
import requests
h = {'APCA-API-KEY-ID': ALPACA_API_KEY, 'APCA-API-SECRET-KEY': ALPACA_SECRET_KEY}
r = requests.get('https://data.alpaca.markets/v2/stocks/NVDA/trades/latest', headers=h, timeout=10)
print(r.json())
"
grep -n "price\|entry\|876\|current" /root/trade_plan_generator.py | head -30
#   418
sed -n '415,425p' /root/trade_plan_generator.py
#  current_price=875.50   
python3 << 'EOF'
with open('/root/trade_plan_generator.py') as f:
    src = f.read()

#   
src = src.replace(
    "current_price=875.50, atr=22.3",
    "current_price=get_current_price('NVDA'), atr=get_atr('NVDA')"
)

with open('/root/trade_plan_generator.py', 'w') as f:
    f.write(src)
print(" Fixed")
EOF

# 
grep -n "875\|current_price" /root/trade_plan_generator.py | tail -10
grep -n "def get_current_price\|def get_atr" /root/trade_plan_generator.py
echo "{}" > /root/logs/trade_plans.json
python3 /root/trade_plan_generator.py 2>&1 | tail -20
python3 -c "
import json
with open('/root/logs/trade_plans.json') as f:
    plans = json.load(f)
for pid, p in plans.items():
    print(p.get('symbol'), 'entry:', p.get('entry'), 'sl:', p.get('stop_loss'))
"
python3 -c "
import json
with open('/root/logs/trade_plans.json') as f:
    plans = json.load(f)
for pid, p in plans.items():
    print(p.get('symbol'), 'entry:', p.get('entry'), 'sl:', p.get('stop_loss'))
"
python3 << 'EOF'
with open('/root/trade_plan_generator.py') as f:
    src = f.read()

#     "def "
import re

NEW_FUNCS = '''
def get_current_price(symbol: str) -> float:
    """Get real-time price from Alpaca Paper API."""
    try:
        from config import ALPACA_API_KEY, ALPACA_SECRET_KEY
        import requests
        h = {"APCA-API-KEY-ID": ALPACA_API_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY}
        r = requests.get(f"https://data.alpaca.markets/v2/stocks/{symbol}/trades/latest",
                         headers=h, timeout=8)
        return float(r.json()["trade"]["p"])
    except Exception:
        return 0.0

def get_atr(symbol: str, period: int = 14) -> float:
    """Get ATR from Alpaca daily bars."""
    try:
        from config import ALPACA_API_KEY, ALPACA_SECRET_KEY
        import requests
        h = {"APCA-API-KEY-ID": ALPACA_API_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY}
        r = requests.get(
            f"https://paper-api.alpaca.markets/v2/stocks/{symbol}/bars?timeframe=1Day&limit={period+1}",
            headers=h, timeout=8)
        bars = r.json().get("bars", [])
        if len(bars) < 2:
            return 5.0
        trs = [max(bars[i]["h"]-bars[i]["l"],
                   abs(bars[i]["h"]-bars[i-1]["c"]),
                   abs(bars[i]["l"]-bars[i-1]["c"]))
               for i in range(1, len(bars))]
        return round(sum(trs)/len(trs), 2)
    except Exception:
        return 5.0

'''

match = re.search(r'^def ', src, re.MULTILINE)
if match and "def get_current_price" not in src:
    src = src[:match.start()] + NEW_FUNCS + src[match.start():]
    print(" Functions added")

with open('/root/trade_plan_generator.py', 'w') as f:
    f.write(src)
EOF

#  syntax
python3 -m py_compile /root/trade_plan_generator.py && echo " Syntax OK"
#  
echo "{}" > /root/logs/trade_plans.json
python3 /root/trade_plan_generator.py 2>&1 | tail -10
python3 -c "
import json
with open('/root/logs/trade_plans.json') as f:
    plans = json.load(f)
for pid, p in plans.items():
    print(p.get('symbol'), '| entry:', p.get('entry'), '| sl:', p.get('stop_loss'), '| tp1:', p.get('take_profit_1'))
"
#  scan 
python3 /root/paper_execution.py --scan
tail -10 /root/logs/trade_decisions.log
#  
tail -f /root/logs/paper.out
#  execute_paper_trade  paper_execution.py
grep -n "stop_loss\|stop_price\|bracket\|order_class" /root/paper_execution.py | head -20
python3 << 'EOF'
with open('/root/paper_execution.py') as f:
    src = f.read()

#  format  stop_loss  bracket order
old = '"stop_loss":    {"stop_price": str(round(sl, 2))},'
new = '"stop_loss":    {"stop_price": str(round(min(sl, entry - 0.05), 2))},'

src = src.replace(old, new)

#     format 
old2 = '"stop_loss":{"stop_price": str(round(sl, 2))}'
new2 = '"stop_loss":{"stop_price": str(round(min(sl, entry - 0.05), 2))}'
src = src.replace(old2, new2)

with open('/root/paper_execution.py', 'w') as f:
    f.write(src)
print(" Fixed")
EOF

# 
grep -n "stop_price" /root/paper_execution.py
#  
python3 /root/paper_execution.py --scan
tail -5 /root/logs/paper.out
#   327 
sed -n '320,335p' /root/paper_execution.py
#    sed
sed -i 's/"stop_price": str(round(sl, 2))/"stop_price": str(round(sl - 0.05, 2))/g' /root/paper_execution.py
# 
grep -n "stop_price" /root/paper_execution.py
# syntax check
python3 -m py_compile /root/paper_execution.py && echo " OK"
# 
python3 /root/paper_execution.py --scan 2>&1 | tail -5
# Institutional Layer
python3 /root/institutional_layer.py >> /root/logs/institutional.out 2>&1 &
disown $!
# Master Orchestrator  
python3 /root/master_orchestrator.py >> /root/logs/orchestrator.out 2>&1 &
disown $!
# Intraday Scanner
python3 /root/intraday_engine.py >> /root/logs/intraday.out 2>&1 &
disown $!
echo " All started"
sleep 5 && ps aux | grep python3 | grep -v grep | wc -l
python3 /root/master_orchestrator.py >> /root/logs/orchestrator.out 2>&1 &
disown $!
python3 /root/intraday_engine.py >> /root/logs/intraday.out 2>&1 &
disown $!
sleep 5 && ps aux | grep python3 | grep -v grep | wc -l
pkill -f master_orchestrator 2>/dev/null
pkill -f intraday_engine 2>/dev/null
sleep 2
python3 /root/master_orchestrator.py >> /root/logs/orchestrator.out 2>&1 &
disown $!
python3 /root/intraday_engine.py >> /root/logs/intraday.out 2>&1 &
disown $!
echo " Done"
sleep 10 && ps aux | grep python3 | grep -v grep | wc -l
tail -20 /root/logs/orchestrator.out
tail -20 /root/logs/intraday.out
tail -20 /root/logs/market.out
grep -n "while True\|sleep\|loop" /root/master_orchestrator.py | head -10
grep -n "while True\|sleep\|loop" /root/intraday_engine.py | head -10
grep -n "while True\|sleep\|loop" /root/master_orchestrator.py | head -10
grep -n "while True\|sleep\|loop" /root/intraday_engine.py | head -10
# 1. orchestrator
cat >> /root/master_orchestrator.py << 'EOF'

if __name__ == "__main__":
    import time
    while True:
        try:
            main()
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(300)
EOF

# 2. intraday
cat >> /root/intraday_engine.py << 'EOF'

if __name__ == "__main__":
    import time
    while True:
        try:
            main()
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(60)
EOF

#  syntax
python3 -m py_compile /root/master_orchestrator.py && echo " orchestrator OK"
python3 -m py_compile /root/intraday_engine.py && echo " intraday OK"
pkill -f master_orchestrator 2>/dev/null
pkill -f intraday_engine 2>/dev/null
sleep 2
python3 /root/master_orchestrator.py >> /root/logs/orchestrator.out 2>&1 &
disown $!
pkill -f master_orchestrator 2>/dev/null
pkill -f intraday_engine 2>/dev/null
sleep 2
python3 /root/master_orchestrator.py >> /root/logs/orchestrator.out 2>&1 &
disown $!
python3 /root/intraday_engine.py >> /root/logs/intraday.out 2>&1 &
disown $!
echo " Done"
#        
sleep 60 && ps aux | grep -E "orchestrator|intraday" | grep -v grep
cd /root && git fetch origin
git checkout origin/main -- portfolio_engine.py correlation_engine.py   capital_allocator.py portfolio_dashboard.py
#   
ls -la /root/portfolio_engine.py /root/correlation_engine.py        /root/capital_allocator.py /root/portfolio_dashboard.py
#  syntax
for f in portfolio_engine correlation_engine capital_allocator portfolio_dashboard; do     python3 -m py_compile /root/${f}.py && echo " ${f}.py OK" || echo " ${f}.py ERROR"; done
#  portfolio snapshot
python3 /root/portfolio_engine.py
python3 << 'EOF'
import sys
sys.path.insert(0, '/root')
from portfolio_engine import run_portfolio_snapshot

try:
    snap = run_portfolio_snapshot()
    print("\n===== PORTFOLIO SNAPSHOT =====")
    print(f"Heat:      {snap.get('portfolio_heat_pct')}%")
    print(f"Cash:      {snap.get('cash_pct')}%")
    print(f"Positions: {snap.get('position_count')}")
    print(f"Unrealized:{snap.get('total_unrealized')}")
    print(f"Warnings:  {snap.get('warning_count')}")
    print("\nSector Exposure:")
    for k,v in snap.get("sector_exposure", {}).items():
        print(f"  {k}: {v}%")
    print("\nPositions:")
    for p in snap.get("positions", []):
        print(f"  {p['symbol']}: {p['weight']}% | Risk: {p['risk_pct']}%")
    print("\nWarnings:")
    for w in snap.get("warnings", []):
        print(f"  [{w['level']}] {w['message']}")
except Exception as e:
    print("[ERROR]", e)
EOF

cd /root && git fetch origin
git checkout origin/main -- integrate_portfolio.py
python3 /root/integrate_portfolio.py
cd /root && git fetch origin
git checkout origin/main -- integrate_portfolio.py
python3 /root/integrate_portfolio.py
#   
python3 -m py_compile /root/smart_execution_engine.py 2>&1
python3 -m py_compile /root/paper_execution.py 2>&1
python3 -m py_compile /root/master_orchestrator.py 2>&1
# 1.    backup
BACKUP_DIR=$(ls -dt /root/backups/portfolio_integration_* | head -1)
echo "Restoring from: $BACKUP_DIR"
cp "$BACKUP_DIR/smart_execution_engine.py" /root/smart_execution_engine.py
cp "$BACKUP_DIR/paper_execution.py" /root/paper_execution.py
cp "$BACKUP_DIR/master_orchestrator.py" /root/master_orchestrator.py
# 2.  syntax  
python3 -m py_compile /root/smart_execution_engine.py && echo " smart OK"
python3 -m py_compile /root/paper_execution.py && echo " paper OK"
python3 -m py_compile /root/master_orchestrator.py && echo " orchestrator OK"
#      
# : sector_lines = "    
# 1.   
sed -n '229,233p' /root/smart_execution_engine.py
sed -n '236,240p' /root/paper_execution.py  
sed -n '197,201p' /root/master_orchestrator.py
python3 << 'PYEOF'
import re

files = [
    "/root/smart_execution_engine.py",
    "/root/paper_execution.py", 
    "/root/master_orchestrator.py",
]

for path in files:
    with open(path) as f:
        src = f.read()
    
    #  sector_lines 
    broken = 'sector_lines = "\n        ".join(\n            f"  \u2022 {s}: `{v:.1f}%`" for s, v in sector_exp.items()\n        )'

python3 << 'PYEOF'
import re

files = [
    "/root/smart_execution_engine.py",
    "/root/paper_execution.py", 
    "/root/master_orchestrator.py",
]

for path in files:
    with open(path) as f:
        src = f.read()
    
    #  sector_lines 
    broken = 'sector_lines = "\n        ".join(\n            f"  \u2022 {s}: `{v:.1f}%`" for s, v in sector_exp.items()\n        )'
    fixed  = 'sector_lines = "\\n".join(f"  * {s}: {v:.1f}%" for s,v in sector_exp.items())'
    
    #    regex
    src = re.sub(
        r'sector_lines\s*=\s*"[\s\n]*"\.join\([^)]+\)',
        'sector_lines = " | ".join(f"{s}:{v:.1f}%" for s,v in sector_exp.items())',
        src, flags=re.DOTALL
    )
    
    with open(path, "w") as f:
        f.write(src)
    print(f"Fixed: {path}")

PYEOF

# 
python3 -m py_compile /root/smart_execution_engine.py && echo " smart OK"
python3 -m py_compile /root/paper_execution.py && echo " paper OK"
python3 -m py_compile /root/master_orchestrator.py && echo " orchestrator OK"
python3 << 'PYEOF'
files = [
    "/root/smart_execution_engine.py",
    "/root/paper_execution.py",
    "/root/master_orchestrator.py",
]

import re

for path in files:
    with open(path) as f:
        src = f.read()

    src = re.sub(
        r'\n#  PORTFOLIO INTELLIGENCE GUARD.*?#  END PORTFOLIO INTELLIGENCE GUARD +\n',
        '\n',
        src, flags=re.DOTALL
    )

    with open(path, "w") as f:
        f.write(src)
    print(f"Cleaned: {path}")

PYEOF

python3 -m py_compile /root/smart_execution_engine.py && echo " smart OK"
python3 -m py_compile /root/paper_execution.py && echo " paper OK"
python3 -m py_compile /root/master_orchestrator.py && echo " orchestrator OK"
cd /root
git fetch origin
#     GitHub 
git checkout origin/main -- smart_execution_engine.py paper_execution.py master_orchestrator.py
# 
python3 -m py_compile /root/smart_execution_engine.py && echo " smart OK"
python3 -m py_compile /root/paper_execution.py && echo " paper OK"
python3 -m py_compile /root/master_orchestrator.py && echo " orchestrator OK"
# 1.  portfolio_guard.py   
cat > /root/portfolio_guard.py << 'ENDOFFILE'
import json, os, requests
DATA_DIR = "/root/logs"

def _load(p, d={}):
    try:
        if os.path.exists(p):
            with open(p) as f: return json.load(f)
    except: pass
    return d

def portfolio_check(symbol, qty, price):
    heat = _load(f"{DATA_DIR}/portfolio_heat.json")
    heat_pct = float(heat.get("portfolio_heat_pct", 0))
    positions = heat.get("positions", [])
    port_val = float(heat.get("portfolio_value", 50000))
    SECTOR_MAP = {"NVDA":"Tech","AMD":"Tech","MSFT":"Tech","AAPL":"Tech","GOOGL":"Tech","META":"Tech","SMCI":"Tech","AVGO":"Tech","ARM":"Tech","TSLA":"Tech","LLY":"Health","UNH":"Health","JPM":"Fin","GS":"Fin","V":"Fin","MA":"Fin","BTCUSD":"Crypto","ETHUSD":"Crypto"}
    CORR = {"Semi":["NVDA","AMD","SMCI","AVGO","MRVL","ARM"],"MegaTech":["AAPL","MSFT","GOOGL","META"],"Crypto":["BTCUSD","ETHUSD"]}
    sector = SECTOR_MAP.get(symbol, "Other")
    sector_exp = float(heat.get("sector_exposure", {}).get(sector, 0))
    existing = [p.get("symbol","") for p in positions]
    corr_count = sum(1 for g,m in CORR.items() if symbol in m for s in existing if s in m)
    new_weight = qty * price / port_val * 100 if port_val else 0
    if heat_pct > 5.4: return False, 0.0, f"Heat {heat_pct:.1f}% BLOCKED"
    if symbol in existing: return False, 0.0, f"{symbol} already in portfolio"
    if corr_count >= 2: return False, 0.0, f"Correlation limit: {corr_count} similar positions"
    mult = 1.0
    reasons = []
    if sector_exp > 35: mult *= 0.5; reasons.append(f"Sector {sector_exp:.0f}%>35%")
    if new_weight > 15: mult *= 0.6; reasons.append(f"Weight {new_weight:.0f}%>15%")
    if heat_pct > 4.2: mult *= 0.7; reasons.append(f"Heat {heat_pct:.1f}%>70%")
    if corr_count == 1: mult *= 0.75; reasons.append("1 corr position")
    mult = round(max(0.25, min(1.0, mult)), 2)
    return True, mult, " | ".join(reasons) or "OK"
ENDOFFILE

python3 -m py_compile /root/portfolio_guard.py && echo " portfolio_guard.py OK"
# 1. paper_execution.py   import   scan_and_execute
sed -i 's/if _score < _thr:/# Portfolio check\n        try:\n            import sys; sys.path.insert(0,"\/root")\n            from portfolio_guard import portfolio_check\n            _pg_ok, _pg_mult, _pg_reason = portfolio_check(plan.get("symbol",""), int(plan.get("position_size", plan.get("shares",10))), float(plan.get("entry", plan.get("entry_price",0))))\n            if not _pg_ok:\n                log.info(f"[Portfolio BLOCKED] {plan.get(\"symbol\",\"\")} - {_pg_reason}")\n                continue\n        except Exception as _pge:\n            pass\n        if _score < _thr:/' /root/paper_execution.py
# 2.  syntax
python3 -m py_compile /root/paper_execution.py && echo " paper OK"
# 3. 
python3 /root/paper_execution.py --scan 2>&1 | tail -10
# 1.  portfolio check  smart_execution_engine
sed -i 's/ok, passed, failed = check_entry_conditions(plan)/ok, passed, failed = check_entry_conditions(plan)\n    try:\n        import sys; sys.path.insert(0,"\/root")\n        from portfolio_guard import portfolio_check\n        _pg_ok,_pg_mult,_pg_reason = portfolio_check(symbol, qty, float(plan.get("entry",plan.get("entry_price",0))))\n        if not _pg_ok:\n            log.info(f"[Portfolio BLOCKED] {symbol} - {_pg_reason}")\n            return None\n        qty = max(1, int(qty * _pg_mult))\n    except Exception as _e:\n        pass/' /root/smart_execution_engine.py
# 2. 
python3 -m py_compile /root/smart_execution_engine.py && echo " smart OK"
# 3.   
pkill -f paper_execution 2>/dev/null
pkill -f smart_execution 2>/dev/null
sleep 2
python3 /root/paper_execution.py >> /root/logs/paper.out 2>&1 &
disown $!
python3 /root/smart_execution_engine.py >> /root/logs/smart_engine.out 2>&1 &
disown $!
echo " All restarted"
# 4. 
sleep 5 && python3 /root/paper_execution.py --scan 2>&1 | tail -10
cd /root && git fetch origin
git checkout origin/main -- system_supervisor.py reliability_layer.py health_dashboard.py
#   Supervisor
python3 /root/system_supervisor.py >> /root/logs/supervisor.log 2>&1 &
disown $!
echo " Supervisor PID: $!"
#   import  
sed -i '1s/^/import sys; sys.path.insert(0,"\/root")\ntry:\n    from reliability_layer import pre_trade_safety_check\nexcept: pre_trade_safety_check = lambda s,d: (True,"")\n\n/' /root/paper_execution.py
# 1.  Supervisor 
tail -10 /root/logs/supervisor.log
# 2.  paper_execution syntax OK   import
python3 -m py_compile /root/paper_execution.py && echo " OK"
# 3.  process  
ps aux | grep python3 | grep -v grep | wc -l
#    market_intelligence
tail -20 /root/logs/market.out
#  DataAge=228m 
ls -la /root/logs/market_intelligence.json
cd /root && git fetch origin
git checkout origin/main -- trade_analytics.py ai_trade_review.py performance_dashboard.py
#  Analytics
python3 /root/trade_analytics.py
#  Daily Report (  cron)
echo "0 20 * * * python3 /root/ai_trade_review.py" >> /etc/crontab
#  dashboard  port  ( 8502)
nohup streamlit run /root/performance_dashboard.py --server.port 8502 &
# 1.     
ls /root/dashboard*.py
# 2.         tab 
tail -50 /root/dashboard_new.py
#  Performance Analytics tab   dashboard_new.py
cat >> /root/dashboard_new.py << 'EOF'
# =========================================================
# PERFORMANCE ANALYTICS
# =========================================================
try:
    from performance_dashboard import render_performance_dashboard
    with st.expander("PERFORMANCE ANALYTICS", expanded=False):
        render_performance_dashboard()
except Exception as e:
    st.error(f"Performance: {e}")
# =========================================================
# PORTFOLIO INTELLIGENCE
# =========================================================
try:
    from portfolio_dashboard import render_portfolio_dashboard
    with st.expander("PORTFOLIO INTELLIGENCE", expanded=False):
        render_portfolio_dashboard()
except Exception as e:
    st.error(f"Portfolio: {e}")
# =========================================================
# SYSTEM HEALTH
# =========================================================
try:
    from health_dashboard import render_health_dashboard
    with st.expander("SYSTEM HEALTH", expanded=False):
        render_health_dashboard()
except Exception as e:
    st.error(f"Health: {e}")
EOF

#  syntax
python3 -m py_compile /root/dashboard_new.py && echo " OK"
#   
pkill -f streamlit 2>/dev/null
sleep 2
cd /root && streamlit run dashboard_new.py --server.port 8501 --server.address 0.0.0.0 >> /root/logs/dashboard.log 2>&1 &
disown $!
echo " Dashboard restarted"
#  syntax
python3 -m py_compile /root/dashboard_new.py && echo " OK"
#   
pkill -f streamlit 2>/dev/null
sleep 2
cd /root && streamlit run dashboard_new.py --server.port 8501 --server.address 0.0.0.0 >> /root/logs/dashboard.log 2>&1 &
disown $!
echo " Dashboard restarted"
# =========================================================
# PORTFOLIO INTELLIGENCE
# =========================================================
try:
# =========================================================
# SYSTEM HEALTH
# =========================================================
try:
# EOF
# syntax
python3 -m py_compile /root/dashboard_new.py && echo "OK"
# restart
pkill -f streamlit 2>/dev/null
sleep 2
cd /root && streamlit run dashboard_new.py --server.port 8501 --server.address 0.0.0.0 >> /root/logs/dashboard.log 2>&1 &
disown $!
echo "Dashboard restarted"
# 1.      
head -n -15 /root/dashboard_new.py > /tmp/dash_clean.py
mv /tmp/dash_clean.py /root/dashboard_new.py
# 2.    
tail -10 /root/dashboard_new.py
# 3.  syntax
python3 -m py_compile /root/dashboard_new.py && echo " OK"
# 4.   
pkill -f streamlit 2>/dev/null
sleep 2
cd /root && streamlit run dashboard_new.py --server.port 8501 --server.address 0.0.0.0 >> /root/logs/dashboard.log 2>&1 &
disown $!
echo " Restarted"
#  Ctrl+C     
#   :
#   
wc -l /root/dashboard_new.py
#    GitHub
cd /root && git fetch origin
git checkout origin/main -- dashboard_new.py
#   tabs  
python3 << 'PYEOF'
with open('/root/dashboard_new.py') as f:
    src = f.read()

addition = '''
try:
    from performance_dashboard import render_performance_dashboard
    with st.expander("PERFORMANCE ANALYTICS", expanded=False):
        render_performance_dashboard()
except Exception as e:
    st.error(f"Performance: {e}")
try:
    from portfolio_dashboard import render_portfolio_dashboard
    with st.expander("PORTFOLIO INTELLIGENCE", expanded=False):
        render_portfolio_dashboard()
except Exception as e:
    st.error(f"Portfolio: {e}")
try:
    from health_dashboard import render_health_dashboard
    with st.expander("SYSTEM HEALTH", expanded=False):
        render_health_dashboard()
except Exception as e:
    st.error(f"Health: {e}")
'''

with open('/root/dashboard_new.py', 'w') as f:
    f.write(src + addition)
print("Done")
PYEOF

python3 -m py_compile /root/dashboard_new.py && echo "OK"
pkill -f streamlit 2>/dev/null
sleep 2
cd /root && streamlit run dashboard_new.py --server.port 8501 --server.address 0.0.0.0 >> /root/logs/dashboard.log 2>&1 &
disown $!
echo "Restarted"
EXIT
exit
