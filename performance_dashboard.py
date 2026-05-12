"""
performance_dashboard.py
PERFORMANCE ANALYTICS DASHBOARD
Minervini Bot — PAPER TRADING ONLY
"""

import streamlit as st
import json, os, datetime
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

DATA_DIR = "/root/logs"

def _load(path, default={}):
    try:
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    except Exception:
        pass
    return default

def _color(val):
    return "#00ff88" if float(val) >= 0 else "#ff4444"

def render_performance_dashboard():
    st.markdown(
        "<div style='background:linear-gradient(135deg,#0a0010,#001020);"
        "padding:18px;border-radius:14px;"
        "border-left:4px solid #aa44ff;margin-bottom:24px'>"
        "<h2 style='color:#aa44ff;margin:0'>📊 PERFORMANCE ANALYTICS</h2>"
        "<p style='color:#555;margin:4px 0 0;font-size:0.82em'>"
        "PAPER TRADING ONLY — Full Strategy Analysis</p></div>",
        unsafe_allow_html=True
    )

    analytics = _load(f"{DATA_DIR}/analytics_snapshot.json", {})
    reviews   = _load(f"{DATA_DIR}/trade_reviews.json", {})

    if not analytics or analytics.get("total_trades", 0) == 0:
        st.info("No closed trades yet. Analytics will appear after first completed trade.")
        st.caption("Run: python3 /root/trade_analytics.py to refresh")
        return

    # ── KPI Row ───────────────────────────────────────────────────────────────
    st.markdown("### 📈 Key Performance Indicators")
    k1,k2,k3,k4,k5,k6,k7,k8 = st.columns(8)
    metrics = [
        ("Win Rate",      f"{analytics.get('win_rate',0):.1f}%",     k1),
        ("Profit Factor", f"{analytics.get('profit_factor',0):.2f}", k2),
        ("Expectancy",    f"${analytics.get('expectancy',0):.2f}",    k3),
        ("Sharpe",        f"{analytics.get('sharpe_ratio',0):.2f}",   k4),
        ("Max DD",        f"{analytics.get('max_drawdown_pct',0):.1f}%", k5),
        ("Total Trades",  analytics.get("total_trades",0),            k6),
        ("Avg R",         f"{analytics.get('avg_r_multiple',0):.2f}R",k7),
        ("Total PnL",     f"${analytics.get('total_pnl',0):+.2f}",    k8),
    ]
    for label, val, col in metrics:
        with col:
            st.metric(label, val)

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        # ── Equity Curve ──────────────────────────────────────────────────────
        st.markdown("### 📈 Equity Curve")
        eq = analytics.get("equity_curve", [])
        if len(eq) >= 2:
            df_eq = pd.DataFrame(eq)
            fig_eq = go.Figure()
            fig_eq.add_trace(go.Scatter(
                x=list(range(len(df_eq))),
                y=df_eq["equity"],
                mode="lines",
                line=dict(color="#aa44ff", width=2),
                fill="tozeroy",
                fillcolor="rgba(170,68,255,0.08)",
                name="Equity",
            ))
            fig_eq.update_layout(
                height=250, paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#ccc",
                xaxis=dict(gridcolor="#222", title="Trade #"),
                yaxis=dict(gridcolor="#222", title="$"),
                margin=dict(t=10,b=10,l=0,r=0),
            )
            st.plotly_chart(fig_eq, use_container_width=True,
                            key=f"equity_{id(fig_eq)}")
        else:
            st.caption("Equity curve will appear after 2+ trades")

    with col2:
        # ── Daily PnL ─────────────────────────────────────────────────────────
        st.markdown("### 📊 Daily PnL")
        daily = analytics.get("daily_pnl", {})
        if daily:
            df_d = pd.DataFrame([{"Date":d,"PnL":v} for d,v in sorted(daily.items())])
            fig_d = px.bar(df_d, x="Date", y="PnL",
                           color="PnL",
                           color_continuous_scale=["#ff4444","#333","#00ff88"],
                           color_continuous_midpoint=0)
            fig_d.update_layout(
                height=250, paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#ccc", showlegend=False,
                margin=dict(t=10,b=10,l=0,r=0),
            )
            st.plotly_chart(fig_d, use_container_width=True,
                            key=f"daily_{id(fig_d)}")
        else:
            st.caption("Daily PnL will appear after trades")

    st.markdown("---")

    col3, col4 = st.columns(2)

    with col3:
        # ── Win/Loss Distribution ─────────────────────────────────────────────
        st.markdown("### 🎯 Win/Loss Distribution")
        wins   = analytics.get("wins",   0)
        losses = analytics.get("losses", 0)
        if wins + losses > 0:
            fig_wl = go.Figure(go.Pie(
                labels=["Wins","Losses"],
                values=[wins, losses],
                marker_colors=["#00ff88","#ff4444"],
                hole=0.5,
                textinfo="label+percent",
                textfont={"color":"#ccc"},
            ))
            fig_wl.update_layout(
                height=220, paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=10,b=10,l=0,r=0), showlegend=False,
            )
            st.plotly_chart(fig_wl, use_container_width=True,
                            key=f"wl_{id(fig_wl)}")
            c1,c2 = st.columns(2)
            with c1: st.metric("Avg Win",  f"${analytics.get('avg_win',0):.2f}")
            with c2: st.metric("Avg Loss", f"${analytics.get('avg_loss',0):.2f}")

    with col4:
        # ── Regime Performance ────────────────────────────────────────────────
        st.markdown("### 🏛️ Regime Performance")
        by_regime = analytics.get("by_regime", {})
        if by_regime:
            df_r = pd.DataFrame([
                {"Regime": k, "PnL": v["pnl"], "WR": v["win_rate"],
                 "Trades": v["trades"]}
                for k,v in by_regime.items()
            ])
            fig_r = px.bar(df_r, x="Regime", y="PnL",
                           color="PnL",
                           color_continuous_scale=["#ff4444","#333","#00ff88"],
                           color_continuous_midpoint=0,
                           text="WR")
            fig_r.update_traces(texttemplate="%{text:.0f}% WR")
            fig_r.update_layout(
                height=220, paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#ccc", showlegend=False,
                margin=dict(t=10,b=10,l=0,r=0),
            )
            st.plotly_chart(fig_r, use_container_width=True,
                            key=f"regime_{id(fig_r)}")

    st.markdown("---")

    col5, col6 = st.columns(2)

    with col5:
        # ── Best Symbols ──────────────────────────────────────────────────────
        st.markdown("### 🏆 Best Symbols")
        best_syms = analytics.get("best_symbols", {})
        if best_syms:
            df_bs = pd.DataFrame([{"Symbol":k,"PnL":v} for k,v in best_syms.items()])
            fig_bs = px.bar(df_bs, x="Symbol", y="PnL",
                            color_discrete_sequence=["#00ff88"])
            fig_bs.update_layout(
                height=200, paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#ccc", showlegend=False,
                margin=dict(t=10,b=10,l=0,r=0),
            )
            st.plotly_chart(fig_bs, use_container_width=True,
                            key=f"best_{id(fig_bs)}")

    with col6:
        # ── Setup Breakdown ───────────────────────────────────────────────────
        st.markdown("### ⚡ Setup Performance")
        by_setup = analytics.get("by_setup", {})
        if by_setup:
            df_s = pd.DataFrame([
                {"Setup": k, "PnL": v["pnl"], "Trades": v["trades"],
                 "WR%": v["win_rate"]}
                for k,v in by_setup.items()
            ])
            st.dataframe(df_s, use_container_width=True, hide_index=True)

    st.markdown("---")

    # ── AI Trade Reviews ──────────────────────────────────────────────────────
    st.markdown("### 🤖 AI Trade Reviews")
    if reviews:
        review_rows = []
        for tid, r in list(reviews.items())[-10:]:
            review_rows.append({
                "Symbol":   r.get("symbol","?"),
                "Verdict":  r.get("verdict","?"),
                "PnL":      f"${r.get('pnl',0):+.2f}",
                "Score":    f"{r.get('confidence_score',0)}/100",
                "Quality":  r.get("execution_quality","?"),
                "Exit":     r.get("exit_assessment","?"),
                "Lesson":   r.get("lessons_learned",[""])[0][:40] if r.get("lessons_learned") else "",
            })
        if review_rows:
            st.dataframe(
                pd.DataFrame(review_rows[::-1]),
                use_container_width=True, hide_index=True
            )
    else:
        st.caption("AI reviews will appear after trades are closed")

    st.markdown("---")

    # ── Strategy Comparison ───────────────────────────────────────────────────
    st.markdown("### 📋 Strategy Stats Summary")
    summary_data = {
        "Metric":       ["Win Rate","Profit Factor","Expectancy","Sharpe","Max DD","Avg Hold","Avg R"],
        "Value":        [
            f"{analytics.get('win_rate',0):.1f}%",
            f"{analytics.get('profit_factor',0):.2f}",
            f"${analytics.get('expectancy',0):.2f}",
            f"{analytics.get('sharpe_ratio',0):.2f}",
            f"{analytics.get('max_drawdown_pct',0):.1f}%",
            f"{analytics.get('avg_hold_mins',0):.0f}m",
            f"{analytics.get('avg_r_multiple',0):.2f}R",
        ],
        "Benchmark":    ["50%+", "1.5+", ">$0", "1.0+", "<10%", "—", "1.0R+"],
        "Status":       [
            "✅" if analytics.get("win_rate",0) >= 50 else "❌",
            "✅" if analytics.get("profit_factor",0) >= 1.5 else "❌",
            "✅" if analytics.get("expectancy",0) > 0 else "❌",
            "✅" if analytics.get("sharpe_ratio",0) >= 1 else "⚠️",
            "✅" if analytics.get("max_drawdown_pct",0) < 10 else "❌",
            "—",
            "✅" if analytics.get("avg_r_multiple",0) >= 1 else "⚠️",
        ]
    }
    st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)

    ts = analytics.get("calculated_at","")[:16]
    st.caption(f"⚠️ PAPER TRADING ONLY | Analytics updated: {ts}")


if __name__ == "__main__":
    st.set_page_config(page_title="Performance Analytics", layout="wide")
    render_performance_dashboard()
