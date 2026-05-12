#!/usr/bin/env python3
"""
dashboard.py — Streamlit Web Dashboard
تشغيل: streamlit run /root/dashboard.py --server.port 8501
"""
import streamlit as st
import json, yfinance as yf, pandas as pd
from datetime import datetime

st.set_page_config(
    page_title="Minervini Trading Bot",
    page_icon="📈",
    layout="wide"
)

st.title("📈 Minervini AI Trading System")
st.caption(f"آخر تحديث: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

# ─── صف الإحصائيات العلوية ───────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)

# حساب Alpaca Portfolio
try:
    import alpaca_trade_api as tradeapi
    from config import ALPACA_KEY, ALPACA_SECRET
    api = tradeapi.REST(ALPACA_KEY, ALPACA_SECRET, base_url="https://paper-api.alpaca.markets")
    account   = api.get_account()
    portfolio = float(account.portfolio_value)
    cash      = float(account.cash)
    positions = api.list_positions()
    pnl       = sum(float(p.unrealized_pl) for p in positions)

    col1.metric("💼 المحفظة", f"${portfolio:,.0f}", f"{(portfolio-50000)/500:.1f}%")
    col2.metric("💵 النقد",   f"${cash:,.0f}")
    col3.metric("📊 المراكز", len(positions))
    col4.metric("📈 P&L",    f"${pnl:+,.0f}")
except:
    col1.metric("💼 المحفظة", "$50,000")
    col2.metric("💵 النقد",   "$48,000")
    col3.metric("📊 المراكز", "1")
    col4.metric("📈 P&L",    "$0")

st.divider()

# ─── صفان رئيسيان ────────────────────────────────────────────────────────────
left, right = st.columns([1, 1])

with left:
    st.subheader("🧠 Claude AI Analysis")
    ai = load_json("/root/ai_analysis.json")
    if ai:
        regime = ai.get("market_regime", "N/A")
        conf   = ai.get("confidence", 0)
        allow  = ai.get("allow_new_trades", True)
        regime_color = {"risk_on": "🟢", "risk_off": "🔴", "neutral": "⚪", "transition": "🟡"}.get(regime, "⚪")
        
        st.markdown(f"**النظام السوقي:** {regime_color} {regime}")
        st.progress(conf, text=f"الثقة: {conf*100:.0f}%")
        st.markdown(f"**فتح صفقات:** {'✅ نعم' if allow else '❌ لا'}")
        st.markdown(f"**التعرض:** {ai.get('recommended_exposure', 0)*100:.0f}%")

        sectors = ai.get("preferred_sectors", [])
        if sectors:
            st.markdown("**قطاعات مفضلة:** " + " | ".join(sectors[:3]))

        avoid = ai.get("avoid_sectors", [])
        if avoid:
            st.markdown("**تجنب:** " + " | ".join(avoid[:3]))

        reasoning = ai.get("reasoning", "")
        if reasoning:
            with st.expander("📝 التحليل الكامل"):
                st.write(reasoning)
    else:
        st.info("لا يوجد تحليل AI بعد — سيظهر عند الساعة 7 صباحاً")

with right:
    st.subheader("🌍 Macro Intelligence")
    macro = load_json("/root/macro_state.json")
    if macro:
        score  = macro.get("score", 0)
        action = macro.get("action", "SELECTIVE")
        action_color = {"BUY_AGGRESSIVE": "🟢🟢", "BUY_SELECTIVE": "🟢", "SELECTIVE": "⚪", "REDUCE": "🟡", "CASH": "🔴"}.get(action, "⚪")
        st.markdown(f"**القرار:** {action_color} {action}")
        st.markdown(f"**النقاط:** {score:+d}")
        
        warnings = macro.get("warnings", [])
        if warnings:
            for w in warnings:
                st.warning(w)
        
        signals = macro.get("signals", [])
        for s in signals[:4]:
            st.markdown(f"• {s}")

st.divider()

# ─── Confidence Scores ────────────────────────────────────────────────────────
st.subheader("🎯 Confidence Scores")
conf_scores = load_json("/root/confidence_scores.json")
if conf_scores:
    rows = []
    for sym, data in conf_scores.items():
        rows.append({
            "السهم": sym,
            "النقاط": data.get("final_score", 0),
            "القرار": data.get("trade_decision", "N/A"),
            "الحجم": f"{data.get('size_pct', 0)*100:.0f}%",
            "Macro": data.get("agent_scores", {}).get("macro", 0),
            "Technical": data.get("agent_scores", {}).get("technical", 0),
            "Smart Money": data.get("agent_scores", {}).get("smart_money", 0),
        })
    df = pd.DataFrame(rows).sort_values("النقاط", ascending=False)
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("لا توجد نقاط بعد")

# ─── المراكز المفتوحة ─────────────────────────────────────────────────────────
st.subheader("📊 المراكز المفتوحة")
try:
    import alpaca_trade_api as tradeapi
    from config import ALPACA_KEY, ALPACA_SECRET
    api = tradeapi.REST(ALPACA_KEY, ALPACA_SECRET, base_url="https://paper-api.alpaca.markets")
    positions = api.list_positions()
    if positions:
        pos_data = []
        for p in positions:
            pnl_pct = float(p.unrealized_plpc) * 100
            pos_data.append({
                "السهم":       p.symbol,
                "الكمية":     p.qty,
                "سعر الدخول": f"${float(p.avg_entry_price):.2f}",
                "السعر الحالي": f"${float(p.current_price):.2f}",
                "P&L":        f"${float(p.unrealized_pl):+.0f}",
                "P&L %":      f"{pnl_pct:+.1f}%",
                "الحالة":     "🟢" if pnl_pct >= 0 else "🔴",
            })
        st.dataframe(pd.DataFrame(pos_data), use_container_width=True, hide_index=True)
    else:
        st.info("لا توجد مراكز مفتوحة حالياً")
except Exception as e:
    st.warning(f"لا يمكن تحميل المراكز: {e}")

# ─── رسم بياني SPY ───────────────────────────────────────────────────────────
st.subheader("📈 SPY — آخر 30 يوم")
try:
    spy = yf.download("SPY", period="1mo", progress=False, auto_adjust=True)
    spy.columns = [c[0] if isinstance(c, tuple) else c for c in spy.columns]
    st.line_chart(spy['Close'])
except:
    st.warning("لا يمكن تحميل بيانات SPY")

# ─── صحة النظام ──────────────────────────────────────────────────────────────
st.subheader("💻 صحة النظام")
import subprocess
programs = ["auto_monitor", "monitor_upgrade", "phase2_upgrade",
            "phase3_sectors", "macro_intelligence", "watchdog",
            "priority1_quality", "priority2_intelligence",
            "priority3_live", "fundamental_engine", "data_sources", "insider_check"]

cols = st.columns(4)
for i, prog in enumerate(programs):
    result = subprocess.run(["pgrep", "-f", prog], capture_output=True)
    running = result.returncode == 0
    cols[i % 4].metric(prog[:20], "✅ يعمل" if running else "❌ متوقف")

if st.button("🔄 تحديث"):
    st.rerun()
