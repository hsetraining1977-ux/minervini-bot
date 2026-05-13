#!/bin/bash
# ============================================================
# start_system.sh — Production Startup Script
# Minervini Trading Bot | Production Stabilization
# Usage: bash /root/start_system.sh
# ============================================================

set -e

# ── Colors ───────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}"
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║   MINERVINI AI TRADING BOT — PRODUCTION     ║"
echo "  ║   Starting all services...                   ║"
echo "  ╚══════════════════════════════════════════════╝"
echo -e "${NC}"

# ── Directories ──────────────────────────────────────────────
mkdir -p /root/logs/archive
cd /root

# ── Load environment ─────────────────────────────────────────
if [ -f /root/.env ]; then
    export $(grep -v '^#' /root/.env | xargs) 2>/dev/null
    echo -e "${GREEN}✅ Environment loaded from .env${NC}"
else
    echo -e "${RED}❌ ERROR: /root/.env not found!${NC}"
    exit 1
fi

# ── Validate required keys ────────────────────────────────────
if [ -z "$ALPACA_API_KEY" ]; then
    echo -e "${RED}❌ ALPACA_API_KEY missing!${NC}"; exit 1
fi
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo -e "${RED}❌ TELEGRAM_BOT_TOKEN missing!${NC}"; exit 1
fi
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo -e "${YELLOW}⚠️  ANTHROPIC_API_KEY missing — AI layer will be limited${NC}"
fi
echo -e "${GREEN}✅ API keys validated${NC}"

# ── Kill existing processes ───────────────────────────────────
echo -e "\n${YELLOW}🛑 Stopping existing processes...${NC}"
pkill -f "auto_monitor.py"        2>/dev/null || true
pkill -f "monitor_upgrade.py"     2>/dev/null || true
pkill -f "phase2_upgrade.py"      2>/dev/null || true
pkill -f "phase3_sectors.py"      2>/dev/null || true
pkill -f "ai_layer.py"            2>/dev/null || true
pkill -f "event_awareness.py"     2>/dev/null || true
pkill -f "institutional_layer.py" 2>/dev/null || true
pkill -f "master_orchestrator.py" 2>/dev/null || true
pkill -f "telegram_commands.py"   2>/dev/null || true
pkill -f "intraday_engine.py"     2>/dev/null || true
pkill -f "health_monitor.py"      2>/dev/null || true
pkill -f "auto_restart.py"        2>/dev/null || true
pkill -f "resource_monitor.py"    2>/dev/null || true
pkill -f "log_rotator.py"         2>/dev/null || true
pkill -f streamlit                2>/dev/null || true
sleep 3
echo -e "${GREEN}✅ Old processes cleared${NC}"

# ── Ensure dashboard.py is the NEW version ───────────────────
echo -e "\n${YELLOW}📋 Verifying dashboard...${NC}"
if [ -f /root/dashboard_new.py ]; then
    cat /root/dashboard_new.py > /root/dashboard.py
    echo -e "${GREEN}✅ dashboard.py updated to new version${NC}"
else
    echo -e "${YELLOW}⚠️  dashboard_new.py not found — using existing dashboard.py${NC}"
fi

# ── Helper function ───────────────────────────────────────────
start_service() {
    local name="$1"
    local cmd="$2"
    local logfile="$3"
    
    nohup bash -c "$cmd >> $logfile 2>&1" &
    local pid=$!
    sleep 1
    if kill -0 $pid 2>/dev/null; then
        echo -e "  ${GREEN}✅ ${name} started (PID: ${pid})${NC}"
    else
        echo -e "  ${RED}❌ ${name} FAILED to start${NC}"
    fi
}

# ── Start core trading services ───────────────────────────────
echo -e "\n${BLUE}🚀 Starting Core Trading Services...${NC}"
start_service "Auto Monitor"       "python3 /root/auto_monitor.py"        "/root/nohup.out"
start_service "Monitor Upgrade"    "python3 /root/monitor_upgrade.py"     "/root/nohup.out"
start_service "Phase2 Upgrade"     "python3 /root/phase2_upgrade.py"      "/root/phase2.out"
start_service "Phase3 Sectors"     "python3 /root/phase3_sectors.py"      "/root/phase3.out"
sleep 3
start_service "Event Awareness"    "python3 /root/event_awareness.py"     "/root/event.out"
start_service "Institutional Layer""python3 /root/institutional_layer.py" "/root/institutional.out"
start_service "Master Orchestrator""python3 /root/master_orchestrator.py" "/root/orchestrator.out"
start_service "Intraday Engine"    "python3 /root/intraday_engine.py"     "/root/intraday.out"
start_service "Telegram Commands"  "python3 /root/telegram_commands.py"   "/root/telegram.out"

# ── Start AI Layer with proper key ───────────────────────────
echo -e "\n${BLUE}🧠 Starting AI Layer...${NC}"
export ANTHROPIC_API_KEY=$(grep ANTHROPIC_API_KEY /root/.env | cut -d'=' -f2 | tr -d '"' | tr -d "'")
nohup bash /root/run_ai_layer.sh >> /root/ai.out 2>python3 /root/ai_layer.py >> /root/ai.out 2>&11 &
echo -e "  ${GREEN}✅ AI Layer started (PID: $!)${NC}"

# ── Start Dashboard ───────────────────────────────────────────
echo -e "\n${BLUE}📊 Starting Dashboard...${NC}"
sleep 2
nohup ~/.local/bin/streamlit run /root/dashboard.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    >> /root/streamlit.out 2>&1 &
STREAMLIT_PID=$!
echo -e "  ${GREEN}✅ Dashboard started (PID: ${STREAMLIT_PID})${NC}"

# ── Start Production Monitoring Stack ────────────────────────
echo -e "\n${BLUE}🛡️  Starting Production Monitoring...${NC}"
start_service "Health Monitor"   "python3 /root/health_monitor.py"   "/root/logs/health.out"
start_service "Auto Restart"     "python3 /root/auto_restart.py"     "/root/logs/restart.out"
start_service "Resource Monitor" "python3 /root/resource_monitor.py" "/root/logs/resource.out"
start_service "Log Rotator"      "python3 /root/log_rotator.py --daemon" "/root/logs/rotator.log"

# ── Wait and verify ───────────────────────────────────────────
echo -e "\n${YELLOW}⏳ Waiting for services to initialize (10s)...${NC}"
sleep 10

# ── Health check ─────────────────────────────────────────────
echo -e "\n${CYAN}═══════════════════════════════════════${NC}"
echo -e "${CYAN}  SYSTEM STATUS CHECK${NC}"
echo -e "${CYAN}═══════════════════════════════════════${NC}"

check_proc() {
    local name="$1"
    local keyword="$2"
    if pgrep -f "$keyword" > /dev/null; then
        echo -e "  ${GREEN}🟢 ${name}${NC}"
    else
        echo -e "  ${RED}🔴 ${name} — NOT RUNNING${NC}"
    fi
}

check_proc "Auto Monitor"        "auto_monitor.py"
check_proc "Monitor Upgrade"     "monitor_upgrade.py"
check_proc "Phase2 Upgrade"      "phase2_upgrade.py"
check_proc "Phase3 Sectors"      "phase3_sectors.py"
check_proc "Event Awareness"     "event_awareness.py"
check_proc "Institutional Layer" "institutional_layer.py"
check_proc "Master Orchestrator" "master_orchestrator.py"
check_proc "Intraday Engine"     "intraday_engine.py"
check_proc "Telegram Commands"   "telegram_commands.py"
check_proc "AI Layer"            "ai_layer.py"
check_proc "Streamlit Dashboard" "streamlit"
check_proc "Health Monitor"      "health_monitor.py"
check_proc "Auto Restart"        "auto_restart.py"
check_proc "Resource Monitor"    "resource_monitor.py"
check_proc "Log Rotator"         "log_rotator.py"

# ── Streamlit HTTP check ──────────────────────────────────────
echo ""
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8501 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    echo -e "  ${GREEN}🌐 Dashboard HTTP: 200 OK${NC}"
else
    echo -e "  ${YELLOW}⏳ Dashboard HTTP: ${HTTP_CODE} (may still be loading)${NC}"
fi

# ── Resource usage ────────────────────────────────────────────
echo ""
CPU=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
RAM=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100}')
DISK=$(df / | tail -1 | awk '{print $5}')
echo -e "  💻 CPU: ${CPU}% | RAM: ${RAM}% | Disk: ${DISK}"

# ── Final summary ─────────────────────────────────────────────
echo -e "\n${CYAN}═══════════════════════════════════════${NC}"
echo -e "${GREEN}✅ SYSTEM STARTUP COMPLETE${NC}"
echo -e ""
echo -e "  📊 Dashboard:  http://144.202.11.183:8501"
echo -e "  📁 Logs dir:   /root/logs/"
echo -e "  🛑 Stop all:   bash /root/stop_system.sh"
echo -e ""
echo -e "  Quick commands:"
echo -e "  • Status:  ps aux | grep python | grep -v grep"
echo -e "  • Errors:  tail -f /root/logs/errors.log"
echo -e "  • Health:  cat /root/logs/health_status.json"
echo -e "${CYAN}═══════════════════════════════════════${NC}"

# Starting Macro Intelligence
nohup python3 /root/macro_intelligence.py >> /root/macro.out 2>&1 &
echo "   Macro Intelligence started (PID: $!)"

