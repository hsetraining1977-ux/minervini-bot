import time
#!/usr/bin/env python3
"""
paper_performance_dashboard.py — Paper Performance Panel
PAPER TRADING ONLY
Streamlit dashboard component: equity curve, PnL, trades, win rate.
"""

import os, json, sys
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

sys.path.insert(0, '/root')

TRADES_FILE      = "/root/logs/paper_trades.json"
PERFORMANCE_FILE = "/root/logs/paper_performance.json"
KILL_SWITCH_FILE = "/root/logs/kill_switch.json"
REVIEW_FILE      = "/root/logs/daily_reviews.json"

DARK_BG  = "rgba(0,0,0,0)"
FONT_CLR = "#aabbcc"
PORTFOLIO = 50000


def load_json(path: str) -> dict:
    try:
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def render_paper_performance():
    """Main paper performance dashboard — call from dashboard_new.py"""

    # Kill switch banner
    ks = load_json(KILL_SWITCH_FILE)
    if ks.get("active"):
        st.error(f"🚨 KILL SWITCH ACTIVE: {ks.get('reason','Unknown')} — "
                 f"Trading HALTED since {ks.get('timestamp','')[:16]}")

    st.markdown("""
    <div style='background:linear-gradient(135deg,#0a0500,#1a0a00);
                border:1px solid #ff8800; border-radius:12px;
                padding:16px 24px; margin:20px 0;'>
        <h2 style='color:#ff8800; margin:0; font-family:monospace;
                   letter-spacing:3px; font-size:1.2em;'>
            📋 PAPER TRADING PERFORMANCE
        </h2>
        <p style='color:#554433; margin:4px 0 0; font-size:0.8em;'>
            ⚠️ PAPER ONLY — No Real Money — Validation & Calibration Mode
        </p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Overview", "📈 Equity Curve", "📋 Trades", "📝 AI Review"
    ])

    with tab1: render_overview()
    with tab2: render_equity_curve()
    with tab3: render_trades()
    with tab4: render_ai_review()


def render_overview():
    perf   = load_json(PERFORMANCE_FILE)
    trades = load_json(TRADES_FILE)

    total  = perf.get("total_trades", 0)
    wins   = perf.get("wins", 0)
    losses = perf.get("losses", 0)
    pnl    = perf.get("total_pnl", 0)
    dd     = perf.get("max_drawdown", 0)
    equity = PORTFOLIO + pnl

    win_rate = round(wins / total * 100, 1) if total > 0 else 0
    pf_wins  = sum(t.get("realized_pnl", 0) for t in trades.values()
                   if t.get("realized_pnl", 0) > 0)
    pf_loss  = abs(sum(t.get("realized_pnl", 0) for t in trades.values()
                       if t.get("realized_pnl", 0) < 0))
    profit_factor = round(pf_wins / pf_loss, 2) if pf_loss > 0 else 0

    # Active trades
    active = [t for t in trades.values()
              if t.get("status") in ("EXECUTED", "ACTIVE")]
    open_pnl = sum(t.get("unrealized_pnl", 0) for t in active)

    # KPIs
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Paper Equity",   f"${equity:,.2f}",
                delta=f"${pnl:+,.2f}")
    col2.metric("Win Rate",       f"{win_rate:.1f}%",
                delta=f"{wins}W / {losses}L")
    col3.metric("Profit Factor",  f"{profit_factor}x")
    col4.metric("Max Drawdown",   f"${dd:,.0f}")
    col5.metric("Open Positions", len(active),
                delta=f"PnL ${open_pnl:+.0f}")

    st.markdown("---")

    col_a, col_b = st.columns(2)

    # Win/Loss donut
    if total > 0:
        with col_a:
            fig = go.Figure(go.Pie(
                labels=["Wins", "Losses"],
                values=[wins, losses],
                hole=0.6,
                marker_colors=["#00ff88", "#ff4444"],
            ))
            fig.update_layout(
                title="Win/Loss Ratio",
                paper_bgcolor=DARK_BG, font_color=FONT_CLR,
                height=250, margin=dict(t=40,b=0,l=0,r=0),
                showlegend=True,
            )
            st.plotly_chart(fig, use_container_width=True, key=f"chart_1_{int(time.time()*1000) % 99999}")

    # Regime performance
    regime_perf = perf.get("regime_perf", {})
    if regime_perf:
        with col_b:
            regs   = list(regime_perf.keys())
            rp_pnl = [regime_perf[r]["pnl"] for r in regs]
            colors = ["#00ff88" if v > 0 else "#ff4444" for v in rp_pnl]
            fig = go.Figure(go.Bar(
                x=regs, y=rp_pnl,
                marker_color=colors,
                text=[f"${v:+.0f}" for v in rp_pnl],
                textposition="outside",
            ))
            fig.update_layout(
                title="P&L by Regime",
                paper_bgcolor=DARK_BG, plot_bgcolor=DARK_BG,
                font_color=FONT_CLR, height=250,
                margin=dict(t=40,b=0,l=0,r=0),
            )
            st.plotly_chart(fig, use_container_width=True, key=f"chart_2_{int(time.time()*1000) % 99999}")

    # Best/Worst
    col_c, col_d = st.columns(2)
    with col_c:
        best = perf.get("best_trade")
        if best:
            st.success(f"🏆 Best: {best['symbol']} | "
                      f"${best.get('pnl',0):+.2f} ({best.get('pct',0):+.1f}%)")
    with col_d:
        worst = perf.get("worst_trade")
        if worst and worst.get("pnl", 0) < 0:
            st.error(f"🔴 Worst: {worst['symbol']} | "
                    f"${worst.get('pnl',0):+.2f} ({worst.get('pct',0):+.1f}%)")

    # Open trades
    if active:
        st.markdown("### ⚡ Open Positions")
        rows = []
        for t in active:
            rows.append({
                "Symbol":    t["symbol"],
                "Entry":     f"${t['entry_price']:.2f}",
                "Current":   f"${t['current_price']:.2f}",
                "Shares":    t["shares"],
                "Unreal PnL":f"${t['unrealized_pnl']:+.2f}",
                "Unreal %":  f"{t['unrealized_pct']:+.2f}%",
                "SL":        f"${t['stop_loss']:.2f}",
                "TP2":       f"${t['take_profit_2']:.2f}",
                "Type":      t["trade_type"],
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_equity_curve():
    perf = load_json(PERFORMANCE_FILE)
    eq   = perf.get("equity_curve", [])

    if not eq:
        st.info("No trades yet. Equity curve will appear after first closed trade.")
        return

    # Daily P&L
    daily = perf.get("daily_pnl", {})
    dates = sorted(daily.keys())
    pnls  = [daily[d] for d in dates]
    cum   = []
    running = 0
    for p in pnls:
        running += p
        cum.append(round(PORTFOLIO + running, 2))

    fig = go.Figure()

    # Equity line
    if cum:
        colors = ["#00ff88" if v >= PORTFOLIO else "#ff4444" for v in cum]
        fig.add_trace(go.Scatter(
            x=dates, y=cum,
            mode="lines+markers",
            name="Paper Equity",
            line=dict(color="#00d4ff", width=2),
            fill="tozeroy",
            fillcolor="rgba(0,212,255,0.1)",
        ))
        fig.add_hline(y=PORTFOLIO, line_dash="dash",
                      line_color="#888", annotation_text="Starting Capital")

    fig.update_layout(
        title="Paper Portfolio Equity Curve",
        xaxis_title="Date",
        yaxis_title="Equity ($)",
        paper_bgcolor=DARK_BG, plot_bgcolor=DARK_BG,
        font_color=FONT_CLR, height=400,
        margin=dict(t=40,b=40,l=60,r=0),
    )
    st.plotly_chart(fig, use_container_width=True, key=f"chart_3_{int(time.time()*1000) % 99999}")

    # Daily bar chart
    if dates:
        fig2 = go.Figure(go.Bar(
            x=dates, y=pnls,
            marker_color=["#00ff88" if v > 0 else "#ff4444" for v in pnls],
            text=[f"${v:+.0f}" for v in pnls],
            textposition="outside",
        ))
        fig2.update_layout(
            title="Daily P&L",
            paper_bgcolor=DARK_BG, plot_bgcolor=DARK_BG,
            font_color=FONT_CLR, height=300,
            margin=dict(t=40,b=0,l=0,r=0),
        )
        st.plotly_chart(fig2, use_container_width=True, key=f"chart_4_{int(time.time()*1000) % 99999}")


def render_trades():
    trades = load_json(TRADES_FILE)
    if not trades:
        st.info("No paper trades yet.")
        return

    # Filter controls
    status_filter = st.multiselect(
        "Filter by Status",
        ["ACTIVE","EXECUTED","TP_HIT","SL_HIT","EXPIRED","CLOSED"],
        default=["ACTIVE","EXECUTED","TP_HIT","SL_HIT"]
    )

    rows = []
    for t in trades.values():
        if t.get("status") not in status_filter:
            continue
        rows.append({
            "Symbol":    t["symbol"],
            "Status":    t.get("status",""),
            "Entry":     f"${t['entry_price']:.2f}",
            "Exit":      f"${t.get('exit_price',0):.2f}" if t.get("exit_price") else "—",
            "Shares":    t["shares"],
            "PnL $":     f"${t.get('realized_pnl', t.get('unrealized_pnl',0)):+.2f}",
            "PnL %":     f"{t.get('realized_pct', t.get('unrealized_pct',0)):+.2f}%",
            "Exit Reason":t.get("exit_reason","—"),
            "Regime":    t.get("regime",""),
            "Exec Score":t.get("execution_score",0),
            "Entry Time":t.get("entry_time","")[:16],
        })

    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption(f"Showing {len(rows)} trades")
    else:
        st.info("No trades match filter")


def render_ai_review():
    reviews = load_json(REVIEW_FILE)
    if not reviews:
        st.info("No daily reviews yet. Reviews are generated at market close.")
        st.code("python3 /root/daily_review.py")
        return

    dates = sorted(reviews.keys(), reverse=True)
    selected = st.selectbox("Select Date", dates)

    if selected:
        review_data = reviews[selected]
        stats = review_data.get("stats", {})

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Trades",   stats.get("trades", 0))
        col2.metric("Win Rate", f"{stats.get('win_rate',0):.1f}%")
        col3.metric("P&L",      f"${stats.get('pnl',0):+.2f}")
        col4.metric("Prof.Factor", stats.get("profit_factor", 0))

        st.markdown("---")
        st.markdown("**🤖 AI Daily Review**")
        st.markdown(f"""
        <div style='background:#050510; border:1px solid #1a2332;
                    border-radius:8px; padding:16px; font-family:monospace;
                    font-size:0.82em; color:#aabbcc; white-space:pre-wrap;'>
{review_data.get('review','')}
        </div>
        """, unsafe_allow_html=True)


if __name__ == "__main__":
    st.set_page_config(
        page_title="Paper Performance",
        page_icon="📋",
        layout="wide"
    )
    render_paper_performance()
