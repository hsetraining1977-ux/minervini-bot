#!/bin/bash
# ============================================================
# fix_thresholds.sh — رفع threshold من 5 → 15 دقيقة
# الملفات المتأثرة: health_dashboard.py + reliability_layer.py
# ============================================================

echo "============================================"
echo "  Minervini Bot — Data Freshness Fix"
echo "  Threshold: 5 min → 15 min"
echo "============================================"
echo ""

# ── 1. health_dashboard.py ──────────────────────────────────
TARGET_HD="/root/health_dashboard.py"

if [ ! -f "$TARGET_HD" ]; then
    echo "❌ File not found: $TARGET_HD"
    exit 1
fi

# Backup
cp "$TARGET_HD" "${TARGET_HD}.bak_$(date +%Y%m%d_%H%M%S)"
echo "✅ Backup created for health_dashboard.py"

# Fix السطر 99: "Fresh" if age < 5 else "STALE"
# نرفع الـ threshold من 5 → 15
sed -i 's/"Fresh" if age < 5 else "STALE"/"Fresh" if age < 15 else "STALE"/g' "$TARGET_HD"

# تحقق من التطبيق
if grep -q '"Fresh" if age < 15 else "STALE"' "$TARGET_HD"; then
    echo "✅ health_dashboard.py — threshold updated to 15 min"
else
    echo "❌ health_dashboard.py — fix failed, check manually"
fi

echo ""

# ── 2. reliability_layer.py ────────────────────────────────
TARGET_RL="/root/reliability_layer.py"

if [ ! -f "$TARGET_RL" ]; then
    echo "❌ File not found: $TARGET_RL"
    exit 1
fi

# Backup
cp "$TARGET_RL" "${TARGET_RL}.bak_$(date +%Y%m%d_%H%M%S)"
echo "✅ Backup created for reliability_layer.py"

# Fix السطر 22: STALE_DATA_MINS = 5 → 15
sed -i 's/STALE_DATA_MINS\s*=\s*5/STALE_DATA_MINS = 15/g' "$TARGET_RL"

# تحقق من التطبيق
if grep -q 'STALE_DATA_MINS = 15' "$TARGET_RL"; then
    echo "✅ reliability_layer.py — STALE_DATA_MINS updated to 15"
else
    echo "❌ reliability_layer.py — fix failed, check manually"
fi

echo ""

# ── 3. تحقق نهائي ──────────────────────────────────────────
echo "============================================"
echo "  VERIFICATION"
echo "============================================"
echo ""
echo "[ health_dashboard.py — Data Freshness section ]"
grep -n "Fresh\|STALE\|age <" "$TARGET_HD" | head -10
echo ""
echo "[ reliability_layer.py — STALE_DATA_MINS ]"
grep -n "STALE_DATA_MINS" "$TARGET_RL"
echo ""

# ── 4. Restart Dashboard 8501 ───────────────────────────────
echo "============================================"
echo "  Restarting Dashboard 8501..."
echo "============================================"

# إيقاف المنفذ 8501 إن كان يعمل
PID_8501=$(lsof -ti:8501 2>/dev/null)
if [ -n "$PID_8501" ]; then
    kill -9 $PID_8501 2>/dev/null
    echo "✅ Stopped existing process on port 8501 (PID: $PID_8501)"
    sleep 2
fi

# إعادة التشغيل عبر nohup
cd /root
nohup streamlit run health_dashboard.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true \
    > /root/logs/dashboard_8501.log 2>&1 &

NEW_PID=$!
sleep 3

if ps -p $NEW_PID > /dev/null 2>&1; then
    echo "✅ Dashboard 8501 restarted (PID: $NEW_PID)"
else
    echo "⚠️  Dashboard may have failed to start — check: tail -20 /root/logs/dashboard_8501.log"
fi

echo ""
echo "============================================"
echo "  ✅ Fix Complete!"
echo "  Data Freshness threshold: 5 min → 15 min"
echo "  Open: http://144.202.11.183:8501"
echo "============================================"
