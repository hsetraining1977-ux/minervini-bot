#!/bin/bash
# ============================================================
#  MINERVINI AI TRADING BOT — PRODUCTION START SCRIPT
#  Rebuilt clean with nice priorities to prevent CPU 100%
# ============================================================

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}"
echo '  ╔══════════════════════════════════════╗'
echo '  ║   MINERVINI AI TRADING BOT           ║'
echo '  ║   Starting all services...           ║'
echo '  ╚══════════════════════════════════════╝'
echo -e "${NC}"

# ── Directories ──────────────────────────────────────────────
mkdir -p /root/logs/archive
mkdir -p /root/adaptive
cd /root

# ── Load environment ─────────────────────────────────────────
if [ -f /root/.env ]; then
    export $(grep -v '^#' /root/.env | xargs) 2>/dev/null
    echo -e "${GREEN}✦ Environment loaded from .env${NC}"
else
    echo -e "${RED}✦ ERROR: /root/.env not found!${NC}"
    exit 1
fi

# ── Validate required keys ───────────────────────────────────
if [ -z "$ALPACA_API_KEY" ]; then
    echo -e "${RED}✦ ALPACA_API_KEY missing!${NC}"; exit 1
fi
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo -e "${RED}✦ TELEGRAM_BOT_TOKEN missing!${NC}"; exit 1
fi
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo -e "${YELLOW}✦✦ ANTHROPIC_API_KEY missing — AI layer will be limited${NC}"
fi
echo -e "${GREEN}✦ API keys validated${NC}"

# ── Kill existing processes ──────────────────────────────────
echo -e "\n${YELLOW}✦ Stopping existing processes...${NC}"
for proc in auto_monitor.py monitor_upgrade.py phase2_upgrade.py phase3_sectors.py \
            ai_layer.py event_awareness.py institutional_layer.py master_orchestrator.py \
            telegram_commands.py intraday_engine.py health_monitor.py auto_restart.py \
            resource_monitor.py log_rotator.py adaptive_learning.py macro_intelligence.py \
            regime_sync.py; do
    pkill -f "$proc" 2>/dev/null || true
done
pkill -f streamlit 2>/dev/null || true
sleep 3
echo -e "${GREEN}✦ Old processes cleared${NC}"

# ── Ensure dashboard.py is latest ───────────────────────────
echo -e "\n${YELLOW}✦ Verifying dashboard...${NC}"
if [ -f /root/dashboard_new.py ]; then
    cat /root/dashboard_new.py > /root/dashboard.py
    echo -e "${GREEN}✦ dashboard.py updated to new version${NC}"
else
    echo -e "${YELLOW}✦✦ dashboard_new.py not found — using existing dashboard.py${NC}"
fi

# ── Helper: start service with nice ─────────────────────────
# Usage: start_service "Label" <nice_value> <command>
start_service() {
    local label="$1"
    local nice_val="$2"
    shift 2
    nohup nice -n "$nice_val" "$@" >> /root/logs/$(echo "$label" | tr ' ' '_' | tr '[:upper:]' '[:lower:]').log 2>&1 &
    echo -e "${GREEN}  ✦ $label started (PID: $!, nice: $nice_val)${NC}"
}

# ── check_proc: verify process running ──────────────────────
check_proc() {
    local label="$1"
    local pattern="$2"
    if pgrep -f "$pattern" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✦ $label${NC}"
    else
        echo -e "  ${RED}✦ $label — NOT RUNNING${NC}"
    fi
}

echo -e "\n${CYAN}── Starting Core Services ──────────────────────${NC}"

# ── Phase2 / Phase3 upgrades (low priority) ──────────────────
start_service "Phase2 Upgrade"   15   python3 /root/phase2_upgrade.py
start_service "Phase3 Sectors"   15   python3 /root/phase3_sectors.py

# ── Event Awareness ──────────────────────────────────────────
start_service "Event Awareness"  10   python3 /root/event_awareness.py

# ── Institutional Layer (heavy — nice 10) ────────────────────
start_service "Institutional Layer" 10 python3 /root/institutional_layer.py

# ── Master Orchestrator (core — nice 5) ──────────────────────
start_service "Master Orchestrator" 5  python3 /root/master_orchestrator.py

# ── Intraday Engine ───────────────────────────────────────────
start_service "Intraday Engine"  10   python3 /root/intraday_engine.py

# ── Telegram Commands ─────────────────────────────────────────
start_service "Telegram Commands" 10  python3 /root/telegram_commands.py

# ── AI Layer (heavy — nice 10, via run script) ────────────────
if [ -f /root/run_ai_layer.sh ]; then
    nohup nice -n 10 bash /root/run_ai_layer.sh >> /root/logs/ai_layer.log 2>&1 &
    echo -e "${GREEN}  ✦ AI Layer started via run_ai_layer.sh (PID: $!, nice: 10)${NC}"
else
    start_service "AI Layer" 10 python3 /root/ai_layer.py
fi

# ── Streamlit Dashboards ──────────────────────────────────────
echo -e "\n${CYAN}── Starting Dashboards ─────────────────────────${NC}"
nohup nice -n 5 /root/.local/bin/streamlit run /root/dashboard.py \
    --server.port 8501 --server.address 0.0.0.0 \
    >> /root/streamlit.out 2>&1 &
echo -e "${GREEN}  ✦ Control Center (8501) started (PID: $!)${NC}"

sleep 1

nohup nice -n 5 python3 -m streamlit run /root/adaptive_dashboard.py \
    --server.port 8503 --server.address 0.0.0.0 \
    >> /root/adaptive/dashboard.log 2>&1 &
echo -e "${GREEN}  ✦ Adaptive Intelligence (8503) started (PID: $!)${NC}"

nohup nice -n 5 /root/.local/bin/streamlit run /root/institutional_dashboard.py \
    --server.port 8504 --server.address 0.0.0.0 \
    >> /root/logs/institutional_dashboard.log 2>&1 &
echo -e "${GREEN}  ✦ Institutional Intelligence (8504) started (PID: $!)${NC}"

# ── Monitoring Stack (lowest priority) ───────────────────────
echo -e "\n${CYAN}── Starting Monitoring Stack ───────────────────${NC}"
start_service "Health Monitor"    15  python3 /root/health_monitor.py
start_service "Auto Restart"      15  python3 /root/auto_restart.py --daemon
start_service "Resource Monitor"  19  python3 /root/resource_monitor.py
start_service "Log Manager"       19  python3 /root/log_manager.py --daemon
start_service "Auto Monitor"      15  python3 /root/auto_monitor.py
start_service "Monitor Upgrade"   15  python3 /root/monitor_upgrade.py

# ── Macro Intelligence ────────────────────────────────────────
start_service "Macro Intelligence" 10 python3 /root/macro_intelligence.py

# ── Adaptive Learning Engine ──────────────────────────────────
start_service "Adaptive Learning"  15 python3 /root/adaptive_learning.py --mode daemon
start_service "Replay Scheduler"   19 python3 /root/replay_scheduler.py

sleep 10

# ── Status check ─────────────────────────────────────────────
echo -e "\n${CYAN}── SYSTEM STATUS CHECK ─────────────────────────${NC}"
check_proc "Auto Monitor"           "auto_monitor.py"
check_proc "Monitor Upgrade"        "monitor_upgrade.py"
check_proc "Phase2 Upgrade"         "phase2_upgrade.py"
check_proc "Phase3 Sectors"         "phase3_sectors.py"
check_proc "Event Awareness"        "event_awareness.py"
check_proc "Institutional Layer"    "institutional_layer.py"
check_proc "Master Orchestrator"    "master_orchestrator.py"
check_proc "Intraday Engine"        "intraday_engine.py"
check_proc "Telegram Commands"      "telegram_commands.py"
check_proc "AI Layer"               "ai_layer"
check_proc "Streamlit Dashboard"    "streamlit"
check_proc "Health Monitor"         "health_monitor.py"
check_proc "Auto Restart"           "auto_restart.py"
check_proc "Resource Monitor"       "resource_monitor.py"
check_proc "Log Manager"            "log_manager.py"
check_proc "Replay Scheduler"       "replay_scheduler.py"

# ── Streamlit HTTP check ──────────────────────────────────────
echo ""
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8501 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    echo -e "  ${GREEN}✦ Dashboard HTTP: 200 OK${NC}"
else
    echo -e "  ${YELLOW}✦ Dashboard HTTP: ${HTTP_CODE} (may still be loading)${NC}"
fi

# ── Resource usage ────────────────────────────────────────────
echo ""
CPU=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
RAM=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100}')
DISK=$(df / | tail -1 | awk '{print $5}')
echo -e "  ${GREEN}✦ CPU: ${CPU}% | RAM: ${RAM}% | Disk: ${DISK}${NC}"

# ── Final summary ─────────────────────────────────────────────
echo -e "\n${CYAN}════════════════════════════════════════${NC}"
echo -e "${GREEN}✦ SYSTEM STARTUP COMPLETE${NC}"
echo -e ""
echo -e "  ✦ Dashboard:  http://144.202.11.183:8501"
echo -e "  ✦ Adaptive:   http://144.202.11.183:8503"
echo -e "  ✦ Institutional: http://144.202.11.183:8504"
echo -e "  ✦ Logs dir:   /root/logs/"
echo -e "  ✦ Stop all:   bash /root/stop_system.sh"
echo -e ""
echo -e "  Quick commands:"
echo -e "  • Status:  ps aux | grep python | grep -v grep"
echo -e "  • Errors:  tail -f /root/logs/errors.log"
echo -e "  • Health:  cat /root/logs/health_status.json"
echo -e "${CYAN}════════════════════════════════════════${NC}"
