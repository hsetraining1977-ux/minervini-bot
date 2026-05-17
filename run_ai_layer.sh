#!/bin/bash
export ANTHROPIC_API_KEY=$(grep ANTHROPIC_API_KEY /root/.env | cut -d'=' -f2 | tr -d '"' | tr -d '"')

# PID Lock   
LOCK="/tmp/ai_layer_master.lock"
if [ -f "$LOCK" ] && kill -0 $(cat "$LOCK") 2>/dev/null; then
    echo "$(date) ai_layer already running (PID $(cat $LOCK))  exit" >> /root/ai.out
    exit 1
fi
echo $$ > "$LOCK"
trap "rm -f $LOCK" EXIT

while true; do
    echo "$(date) Starting ai_layer..." >> /root/ai.out
    python3 /root/ai_layer.py >> /root/ai.out 2>&1
    echo "$(date) ai_layer exited, restarting in 300s..." >> /root/ai.out
    sleep 300
done
