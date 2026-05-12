"""
lifecycle_dashboard.py
TRADE LIFECYCLE CENTER — Streamlit Dashboard
⚠️ PAPER TRADING ONLY
"""

import streamlit as st
import json
import os
import datetime
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

DATA_DIR = "/root/logs"

def _load(path, default):
    try:
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    except Exception:
        pass
    return default

STAGE_COLORS = {
    "PLANNED":     "#888888",
    "PENDING":     "#ffaa00",
    "ENTERED":     "#00aaff",
    "SCALED_IN":   "#0066ff",
    "PARTIAL_EXIT":"#ff6600",
    "TRAILING":    "#00ff88",
    "CLOSED":      "#888888",
    "CANCELLED":   "#ff4444",
}

GRADE_COLORS = {
    "A+": "#00ff88", "A": "#44ff44",
    "B":  "#ffff00", "C": "#ffaa00", "D": "#ff4444",
}

def _gauge(value, title, max_val=100, color="#00ff88", key="gauge"):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title={"text": title, "font": {"color": "#ccc", "size": 13}},
        gauge={
            "axis":  {"range": [0, max_val], "tickcolor": "#555"},
            "bar":   {"color": color},
            "steps": [
                {"range": [0, max_val*0.4],  "color": "#1a0000"},
                {"range": [max_val*0.4, max_val*0.7], "color": "#1a1a00"},
                {"range": [max_val*0.7, max_val],     "color": "#001a00"},
            ],
        },
        number={"font": {"color": color, "size": 24}},
    ))
    fig.update_layout(
        height=180, paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=30, b=0, l=10, r=10),
    )
    st.plotly_chart(fig, use_container_width=True,
                    key=f"{key}_{int(datetime.datetime.now().timestamp()*1000)}")

def render_lifecycle_dashboard():
    st.markdown("""
    <div style='background:linear-gradient(135deg,#050510,#0a0a2e);
                padding:18px 22px;border-radius:14px;
                border-left:4px solid #4488ff;margin-bottom:24px'>
        <h2 style='color:#4488ff;margin:0;font-size:1.5em;letter-spacing:1px'>
            🔬 TRADE LIFECYCLE INTELLIGENCE CENTER
        </h2>
        <p style='color:#666;margin:6px 0 0;font-size:0.82em'>
            ⚠️ PAPER TRADING ONLY — Institutional Position Intelligence
        </p>
    </div>
    """, unsafe_allow_html=True)

    lifecycles = _load(f"{DATA_DIR}/trade_lifecycle.json", {})
    health_all = _load(f"{DATA_DIR}/position_health.json", {})
    analytics  = _load(f"{DATA_DIR}/trade_analytics.json", {})
    journal    = _load(f"{DATA_DIR}/trade_journal_v2.json", [])

    active = {
        tid: lc for tid, lc in lifecycles.items()
        if lc.get("current_stage") not in ("CLOSED", "CANCELLED")
    }
    closed = {
        tid: lc for tid, lc in lifecycles.items()
        if lc.get("current_stage") in ("CLOSED", "CANCELLED")
    }

    # ── Top KPIs ──────────────────────────────────────────────────────────────
    total   = analytics.get("total_trades", 0)
    wins    = analytics.get("wins", 0)
    wr      = wins / total * 100 if total else 0
    total_pnl = analytics.get("total_pnl", 0)
    avg_eff = analytics.get("avg_efficiency", 0)
    avg_dur = analytics.get("avg_duration", 0)

    c1,c2,c3,c4,c5,c6 = st.columns(6)
    with c1: st.metric("Active",       len(active))
    with c2: st.metric("Total Trades", total)
    with c3: st.metric("Win Rate",     f"{wr:.1f}%")
    with c4: st.metric("Total PnL",    f"${total_pnl:+.2f}")
    with c5: st.metric("Avg Efficiency",f"{avg_eff:.0f}/100")
    with c6: st.metric("Avg Duration", f"{avg_dur:.0f}m")

    st.markdown("---")

    # ── Active trade cards ────────────────────────────────────────────────────
    st.markdown("### 📡 Active Positions — Live Intelligence")
    if not active:
        st.info("No active positions. Engine scanning for setups...")
    else:
        for trade_id, lc in active.items():
            symbol  = lc.get("symbol", "?")
            stage   = lc.get("current_stage", "PLANNED")
            health  = health_all.get(trade_id, {})
            h_score = health.get("score", 50)
            h_grade = health.get("grade", "CAUTION")
            h_icon  = health.get("icon", "🟡")
            action  = health.get("action", "MONITOR")
            price   = health.get("price", 0)
            pnl_pct = health.get("pnl_pct", 0)
            entry   = float(lc.get("entry_price", 0))
            curr_sl = float(lc.get("current_sl", lc.get("stop_loss", 0)))
            tp1     = float(lc.get("take_profit_1", 0))

            stage_color = STAGE_COLORS.get(stage, "#888")
            h_color     = "#00ff88" if h_score >= 75 else ("#ffaa00" if h_score >= 60 else "#ff4444")

            with st.expander(
                f"{h_icon} {symbol}  |  Stage: {stage}  |  "
                f"Health: {h_score}/100  |  PnL: {pnl_pct:+.1f}%",
                expanded=True
            ):
                col_l, col_r = st.columns([2, 1])

                with col_l:
                    # Lifecycle timeline
                    st.markdown("**📊 Lifecycle Timeline**")
                    history = lc.get("stage_history", [])
                    for ev in history:
                        sc = STAGE_COLORS.get(ev["stage"], "#888")
                        ts = ev["timestamp"][:16]
                        st.markdown(
                            f"<span style='color:{sc};font-size:0.85em'>"
                            f"● {ev['stage']}</span> "
                            f"<span style='color:#555;font-size:0.75em'>{ts}</span> "
                            f"<span style='color:#888;font-size:0.8em'>{ev.get('notes','')}</span>",
                            unsafe_allow_html=True
                        )

                    st.markdown("**🎯 Price Levels**")
                    r1,r2,r3 = st.columns(3)
                    with r1: st.metric("Entry",  f"${entry:.2f}")
                    with r2: st.metric("SL",     f"${curr_sl:.2f}")
                    with r3: st.metric("TP1",    f"${tp1:.2f}")

                    # Distance metrics
                    if price > 0 and curr_sl > 0:
                        dist_sl  = round((price - curr_sl) / price * 100, 2)
                        dist_tp  = round((tp1 - price) / price * 100, 2) if tp1 else 0
                        m1,m2 = st.columns(2)
                        with m1: st.metric("Distance to SL", f"{dist_sl:.1f}%")
                        with m2: st.metric("Distance to TP1",f"{dist_tp:.1f}%")

                    # Health components
                    if health.get("components"):
                        st.markdown("**🔬 Health Breakdown**")
                        comps = health["components"]
                        for k, v in comps.items():
                            color = "#00ff88" if "+" in str(v) else "#ff4444"
                            st.markdown(
                                f"<span style='color:#888;font-size:0.82em'>{k}:</span> "
                                f"<span style='color:{color};font-size:0.85em'>{v}</span>",
                                unsafe_allow_html=True
                            )

                with col_r:
                    _gauge(h_score, "Health Score", color=h_color,
                           key=f"health_{trade_id}")

                    st.markdown(
                        f"<div style='text-align:center;margin-top:8px'>"
                        f"<span style='color:{h_color};font-size:1.1em;font-weight:bold'>"
                        f"{h_icon} {h_grade}</span><br>"
                        f"<span style='color:#888;font-size:0.8em'>Action: {action}</span>"
                        f"</div>",
                        unsafe_allow_html=True
                    )

                    # PnL evolution mini chart
                    pnl_hist = lc.get("pnl_history", [])
                    if len(pnl_hist) >= 3:
                        df_p = pd.DataFrame(pnl_hist[-50:])
                        fig_p = go.Figure(go.Scatter(
                            y=df_p["pnl"],
                            mode="lines",
                            line=dict(
                                color="#00ff88" if df_p["pnl"].iloc[-1] >= 0 else "#ff4444",
                                width=2
                            ),
                            fill="tozeroy",
                            fillcolor="rgba(0,255,136,0.08)",
                        ))
                        fig_p.update_layout(
                            height=120, showlegend=False,
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor ="rgba(0,0,0,0)",
                            margin=dict(t=5, b=5, l=0, r=0),
                            xaxis=dict(visible=False),
                            yaxis=dict(gridcolor="#222", tickfont=dict(size=9)),
                        )
                        st.plotly_chart(fig_p, use_container_width=True,
                                        key=f"pnl_{trade_id}_{int(datetime.datetime.now().timestamp()*1000)}")

    st.markdown("---")

    # ── Closed trades analysis ────────────────────────────────────────────────
    if journal:
        st.markdown("### 📋 Trade Journal — Efficiency Analysis")

        df_j = pd.DataFrame(journal[-20:][::-1])
        show_cols = ["symbol","pnl","efficiency_grade","exit_reason",
                     "market_regime","duration_mins","mfe","mae"]
        show_cols = [c for c in show_cols if c in df_j.columns]

        def color_grade(val):
            c = GRADE_COLORS.get(val, "#888")
            return f"color: {c}; font-weight: bold"
        def color_pnl(val):
            try:
                return f"color: {'#00ff88' if float(val) >= 0 else '#ff4444'}"
            except Exception:
                return ""

        styled = df_j[show_cols].style
        if "efficiency_grade" in show_cols:
            styled = styled.applymap(color_grade, subset=["efficiency_grade"])
        if "pnl" in show_cols:
            styled = styled.applymap(color_pnl, subset=["pnl"])
        st.dataframe(styled, use_container_width=True, hide_index=True)

    st.markdown("---")

    # ── Institutional analytics ───────────────────────────────────────────────
    if analytics.get("total_trades", 0) > 0:
        st.markdown("### 🏛️ Institutional Analytics")

        col1, col2 = st.columns(2)

        with col1:
            # Grade distribution
            grade_data = analytics.get("by_grade", {})
            if any(v > 0 for v in grade_data.values()):
                fig_grade = go.Figure(go.Bar(
                    x=list(grade_data.keys()),
                    y=list(grade_data.values()),
                    marker_color=[GRADE_COLORS.get(g,"#888") for g in grade_data.keys()],
                ))
                fig_grade.update_layout(
                    title="Trade Grade Distribution",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor ="rgba(0,0,0,0)",
                    font_color="#ccc", height=220,
                    margin=dict(t=30,b=10,l=0,r=0),
                )
                st.plotly_chart(fig_grade, use_container_width=True,
                                key=f"grade_dist_{int(datetime.datetime.now().timestamp()*1000)}")

        with col2:
            # Regime performance
            regime_data = analytics.get("by_regime", {})
            if regime_data:
                regimes = list(regime_data.keys())
                pnls    = [regime_data[r]["pnl"] for r in regimes]
                fig_reg = go.Figure(go.Bar(
                    x=regimes, y=pnls,
                    marker_color=["#00ff88" if p >= 0 else "#ff4444" for p in pnls],
                ))
                fig_reg.update_layout(
                    title="PnL by Market Regime",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor ="rgba(0,0,0,0)",
                    font_color="#ccc", height=220,
                    margin=dict(t=30,b=10,l=0,r=0),
                )
                st.plotly_chart(fig_reg, use_container_width=True,
                                key=f"regime_perf_{int(datetime.datetime.now().timestamp()*1000)}")

        # Best/Worst setups
        best  = analytics.get("best_trade")
        worst = analytics.get("worst_trade")
        if best or worst:
            b1, b2 = st.columns(2)
            with b1:
                if best:
                    st.success(
                        f"🏆 Best Trade: **{best['symbol']}**  "
                        f"PnL: ${best['pnl']:.2f}  Grade: {best['grade']}"
                    )
            with b2:
                if worst:
                    st.error(
                        f"💔 Worst Trade: **{worst['symbol']}**  "
                        f"PnL: ${worst['pnl']:.2f}  Grade: {worst['grade']}"
                    )

    st.caption("⚠️ PAPER TRADING ONLY — All data simulated. No real money.")


if __name__ == "__main__":
    st.set_page_config(page_title="Trade Lifecycle Center", layout="wide")
    render_lifecycle_dashboard()
