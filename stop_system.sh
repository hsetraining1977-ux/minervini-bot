#!/bin/bash
# ============================================================
# stop_system.sh — Graceful System Shutdown
# Minervini Trading Bot | Production Stabilization
# Usage: bash /root/stop_system.sh
# ============================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${YELLOW}"
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║   MINERVINI BOT — STOPPING ALL SERVICES     ║"
echo "  ╚══════════════════════════════════════════════╝"
echo -e "${NC}"

stop_service() {
    local name="$1"
    local keyword="$2"
    if pgrep -f "$keyword" > /dev/null; then
        pkill -f "$keyword" 2>/dev/null || true
        sleep 1
        # Force kill if still running
        pkill -9 -f "$keyword" 2>/dev/null || true
        echo -e "  ${GREEN}✅ Stopped: ${name}${NC}"
    else
        echo -e "  ${CYAN}⚪ Not running: ${name}${NC}"
    fi
}

echo -e "\n${YELLOW}Stopping monitoring stack...${NC}"
stop_service "Log Rotator"      "log_rotator.py"
stop_service "Resource Monitor" "resource_monitor.py"
stop_service "Auto Restart"     "auto_restart.py"
stop_service "Health Monitor"   "health_monitor.py"

echo -e "\n${YELLOW}Stopping dashboard...${NC}"
stop_service "Streamlit" "streamlit"

echo -e "\n${YELLOW}Stopping AI & trading services...${NC}"
stop_service "AI Layer"            "ai_layer.py"
stop_service "Telegram Commands"   "telegram_commands.py"
stop_service "Intraday Engine"     "intraday_engine.py"
stop_service "Master Orchestrator" "master_orchestrator.py"
stop_service "Institutional Layer" "institutional_layer.py"
stop_service "Event Awareness"     "event_awareness.py"
stop_service "Phase3 Sectors"      "phase3_sectors.py"
stop_service "Phase2 Upgrade"      "phase2_upgrade.py"
stop_service "Monitor Upgrade"     "monitor_upgrade.py"
stop_service "Auto Monitor"        "auto_monitor.py"

sleep 2

echo -e "\n${CYAN}═══════════════════════════════════════${NC}"
REMAINING=$(ps aux | grep python | grep -v grep | wc -l)
if [ "$REMAINING" -eq 0 ]; then
    echo -e "${GREEN}✅ All services stopped successfully${NC}"
else
    echo -e "${YELLOW}⚠️  ${REMAINING} Python process(es) still running:${NC}"
    ps aux | grep python | grep -v grep
fi
echo -e "${CYAN}═══════════════════════════════════════${NC}"
echo -e "\nTo restart: ${GREEN}bash /root/start_system.sh${NC}\n"
