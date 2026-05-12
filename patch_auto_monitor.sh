#!/bin/bash
# ربط decision_engine بـ auto_monitor.py
# يضيف سطر import واحد وشرط فحص قبل الشراء

cd /root

# ١. أضف import في أول الملف
if ! grep -q "decision_engine" auto_monitor.py; then
    sed -i '1s/^/from decision_engine import get_buy_decision\n/' auto_monitor.py
    echo "✅ تم إضافة import"
else
    echo "⚠️ import موجود مسبقاً"
fi

# ٢. أضف فحص القرار قبل الشراء
# ابحث عن مكان الشراء وأضف الفحص قبله
if ! grep -q "get_buy_decision" auto_monitor.py; then
    # أضف الفحص قبل submit_order
    sed -i 's/trading_client.submit_order(MarketOrderRequest(/if not get_buy_decision(symbol):\n                    print(f"[Decision] {symbol} محجوب")\n                    continue\n            trading_client.submit_order(MarketOrderRequest(/' auto_monitor.py
    echo "✅ تم إضافة فحص القرار"
else
    echo "⚠️ الفحص موجود مسبقاً"
fi

echo ""
echo "✅ التكامل اكتمل!"
echo "أعد تشغيل auto_monitor.py"
