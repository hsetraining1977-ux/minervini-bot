#!/bin/bash
cd /root
cp /root/.env /root/backups/.env.backup 2>/dev/null
git add -A
git commit -m "auto-backup $(date +%Y-%m-%d_%H:%M)"
git push origin main --force
echo "Backup done: $(date)"
