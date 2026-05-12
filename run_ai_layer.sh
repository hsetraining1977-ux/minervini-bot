#!/bin/bash
export ANTHROPIC_API_KEY=$(grep ANTHROPIC_API_KEY /root/.env | cut -d'=' -f2 | tr -d '"' | tr -d "'")
while true; do
    echo "[$(date)] Starting ai_layer..." >> /root/ai.out
    python3 /root/ai_layer.py >> /root/ai.out 2>&1
    echo "[$(date)] ai_layer exited  restarting in 300s..." >> /root/ai.out
    sleep 300
done
