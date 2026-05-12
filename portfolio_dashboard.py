"""
portfolio_dashboard.py
PORTFOLIO INTELLIGENCE CENTER — Streamlit Panel
⚠️ PAPER TRADING ONLY
"""

import streamlit as st
import json
import os
import datetime
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

DATA_DIR = "/root/logs"

def _load(path, default):
    try:
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    except Exception:
        pass
    return default

def render_portfolio_dashboard():
    st.markdown("""
    <div style='background:linear-gradient(135deg,#0a0a0a,#1a0a2e);
                padding:18px 22px;border-radius:14px;
                border-left:4px solid #ff6600;margin-bottom:24px'>
        <h2 style='color:#ff6600;margin:0;font-size:1.4em;letter-spacing:1px'>
            🏛️ PORTFOLIO INTELLIGENCE CENTER
        </h2>
        <p style='color:#666;margin:6px 0 0;font-size:0.82em'>
            ⚠️ PAPER TRADING ONLY — Institutional Risk Management
        </p>
    </div>
    """, unsafe_allow_html=True)

    heat    = _load(f"{DATA_DIR}/portfolio_heat.json", {})
    corr    = _load(f"{DATA_DIR}/correlation_risk.json", {})
    alloc   = _load(f"{DATA_DIR}/capital_allocation.json", {})
    warns   = _load(f"{DATA_DIR}/concentration_warnings.json", {})

    if not heat:
        st.info("Portfolio data loading... Run portfolio_engine.py first.")
        return

    # ── Top KPIs ──────────────────────────────────────────────────────────────
    c1,c2,c3,c4,c5 = st.columns(5)
    heat_pct  = heat.get("portfolio_heat_pct", 0)
    cash_pct  = heat.get("cash_pct", 100)
    util_pct  = heat.get("capital_utilized", 0)
    positions = heat.get("position_count", 0)
    unreal    = heat.get("total_unrealized", 0)

    heat_color = "normal" if heat_pct < 4 else "inverse"

    with c1:
        st.metric("Portfolio Heat", f"{heat_pct:.1f}%",
                  delta="SAFE" if heat_pct < 4 else "HIGH",
                  delta_color="normal" if heat_pct < 4 else "inverse")
    with c2:
        st.metric("Cash Reserve", f"{cash_pct:.1f}%")
    with c3:
        st.metric("Capital Used", f"{util_pct:.1f}%")
    with c4:
        st.metric("Positions", positions)
    with c5:
        st.metric("Unrealized PnL", f"${unreal:+.2f}",
                  delta_color="normal" if unreal >= 0 else "inverse")

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        # ── Portfolio Heat Gauge ──────────────────────────────────────────────
        st.markdown("### 🌡️ Portfolio Heat")
        heat_color_val = "#00ff88" if heat_pct < 3 else ("#ffaa00" if heat_pct < 5 else "#ff4444")
        fig_heat = go.Figure(go.Indicator(
            mode  = "gauge+number+delta",
            value = heat_pct,
            title = {"text": "Heat %", "font": {"color": "#ccc"}},
            delta = {"reference": 3, "increasing": {"color": "#ff4444"},
                     "decreasing": {"color": "#00ff88"}},
            gauge = {
                "axis":  {"range": [0, 10], "tickcolor": "#555"},
                "bar":   {"color": heat_color_val},
                "steps": [
                    {"range": [0, 3],  "color": "#001a00"},
                    {"range": [3, 6],  "color": "#1a1a00"},
                    {"range": [6, 10], "color": "#1a0000"},
                ],
                "threshold": {"line": {"color": "red", "width": 3},
                              "thickness": 0.75, "value": 6},
            },
            number={"suffix": "%", "font": {"color": heat_color_val}},
        ))
        fig_heat.update_layout(
            height=220, paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor ="rgba(0,0,0,0)",
            margin=dict(t=30, b=0, l=10, r=10)
        )
        st.plotly_chart(fig_heat, use_container_width=True,
                        key=f"heat_gauge_{int(datetime.datetime.now().timestamp()*1000)}")

    with col2:
        # ── Capital Allocation Pie ────────────────────────────────────────────
        st.markdown("### 💰 Capital Allocation")
        alloc_data = alloc.get("allocation", {"swing": 0.70, "intraday": 0.20, "cash": 0.10})
        fig_alloc = go.Figure(go.Pie(
            labels=["Swing", "Intraday", "Cash"],
            values=[alloc_data.get("swing", 0)*100,
                    alloc_data.get("intraday", 0)*100,
                    alloc_data.get("cash", 0)*100],
            marker_colors=["#00ff88", "#4488ff", "#ffaa00"],
            hole=0.55,
            textinfo="label+percent",
            textfont={"color": "#ccc", "size": 12},
        ))
        fig_alloc.update_layout(
            height=220, paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=10, b=10, l=0, r=0),
            showlegend=False,
        )
        st.plotly_chart(fig_alloc, use_container_width=True,
                        key=f"alloc_pie_{int(datetime.datetime.now().timestamp()*1000)}")

        # Allocation reasons
        reasons = alloc.get("reasons", [])
        if reasons:
            for r in reasons[:3]:
                st.caption(f"• {r}")

    st.markdown("---")

    # ── Sector Exposure ───────────────────────────────────────────────────────
    st.markdown("### 🏭 Sector Exposure")
    sector_data = heat.get("sector_exposure", {})
    if sector_data:
        sectors = list(sector_data.keys())
        values  = list(sector_data.values())
        limits  = [40 if s == "Technology" else 30 for s in sectors]
        colors  = ["#ff4444" if v > l else "#00ff88"
                   for v, l in zip(values, limits)]

        fig_sector = go.Figure()
        fig_sector.add_trace(go.Bar(
            x=sectors, y=values,
            marker_color=colors, name="Exposure",
        ))
        fig_sector.add_trace(go.Scatter(
            x=sectors, y=limits,
            mode="markers+lines",
            marker=dict(color="#ff6600", size=8, symbol="line-ew"),
            line=dict(color="#ff6600", dash="dash", width=1),
            name="Limit",
        ))
        fig_sector.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor ="rgba(0,0,0,0)",
            font_color="#ccc", height=200,
            margin=dict(t=10, b=10, l=0, r=0),
            yaxis=dict(title="%", gridcolor="#222"),
            legend=dict(orientation="h", y=1.1),
        )
        st.plotly_chart(fig_sector, use_container_width=True,
                        key=f"sector_{int(datetime.datetime.now().timestamp()*1000)}")
    else:
        st.caption("No sector data yet.")

    st.markdown("---")

    # ── Correlation Map ───────────────────────────────────────────────────────
    st.markdown("### 🔗 Correlation Groups")
    group_exp = corr.get("group_exposure", {})
    corr_warns = corr.get("corr_warnings", [])

    if group_exp:
        rows = []
        for group, data in group_exp.items():
            if group == "Other":
                continue
            rows.append({
                "Group":   group,
                "Symbols": ", ".join(data.get("symbols", [])),
                "Count":   data.get("count", 0),
                "Heat%":   f"{data.get('heat_pct', 0):.2f}%",
                "Status":  "⚠️ HIGH" if data.get("count", 0) >= 2 else "✅ OK",
            })
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.caption("No correlation data yet.")

    # Correlation warnings
    if corr_warns:
        for w in corr_warns:
            st.warning(f"🔗 **{w['group']}**: {w['warning']}")

    st.markdown("---")

    # ── Positions Table ───────────────────────────────────────────────────────
    st.markdown("### 📊 Open Positions — Risk View")
    positions_data = heat.get("positions", [])
    if positions_data:
        df_pos = pd.DataFrame(positions_data)
        show_cols = ["symbol","sector","qty","entry","current",
                     "market_value","unrealized","open_risk","risk_pct","weight"]
        show_cols = [c for c in show_cols if c in df_pos.columns]
        st.dataframe(df_pos[show_cols], use_container_width=True, hide_index=True)
    else:
        st.caption("No open positions.")

    # ── Warnings ─────────────────────────────────────────────────────────────
    warning_list = warns.get("warnings", [])
    if warning_list:
        st.markdown("---")
        st.markdown("### ⚠️ Concentration Warnings")
        for w in warning_list:
            if w["level"] == "HIGH":
                st.error(f"🔴 **{w['type']}**: {w['message']}")
            else:
                st.warning(f"🟡 **{w['type']}**: {w['message']}")

    st.caption(f"⚠️ PAPER TRADING ONLY | Updated: {heat.get('timestamp','')[:16]}")


if __name__ == "__main__":
    st.set_page_config(page_title="Portfolio Intelligence", layout="wide")
    render_portfolio_dashboard()
