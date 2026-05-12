"""
position_management_dashboard.py
POSITION MANAGEMENT CENTER — Streamlit Panel
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

def render_position_management():
    st.markdown("""
    <div style='background:linear-gradient(135deg,#0a0a0a,#1a1a2e);
                padding:16px 20px;border-radius:12px;
                border-left:4px solid #00ff88;margin-bottom:20px'>
        <h2 style='color:#00ff88;margin:0;font-size:1.4em'>
            ⚡ POSITION MANAGEMENT CENTER
        </h2>
        <p style='color:#888;margin:4px 0 0;font-size:0.85em'>
            ⚠️ PAPER TRADING ONLY — NO REAL MONEY
        </p>
    </div>
    """, unsafe_allow_html=True)

    positions  = _load(f"{DATA_DIR}/smart_positions.json", {})
    health_all = _load(f"{DATA_DIR}/position_health.json", {})
    journal    = _load(f"{DATA_DIR}/trade_journal.json", [])
    perf       = _load(f"{DATA_DIR}/paper_performance.json", {})

    active = {
        tid: p for tid, p in positions.items()
        if p.get("status") in ("ACTIVE", "PARTIAL")
    }
    closed = {
        tid: p for tid, p in positions.items()
        if p.get("status") not in ("ACTIVE", "PARTIAL")
    }

    # ── Top metrics ───────────────────────────────────────────────────────────
    col1, col2, col3, col4, col5 = st.columns(5)
    total_trades = perf.get("total_trades", 0)
    wins         = perf.get("wins", 0)
    win_rate     = (wins / total_trades * 100) if total_trades else 0
    total_pnl    = perf.get("total_pnl", 0.0)
    max_dd       = perf.get("max_drawdown", 0.0)

    with col1:
        st.metric("Active Positions", f"{len(active)}/3")
    with col2:
        st.metric("Total Trades", total_trades)
    with col3:
        st.metric("Win Rate", f"{win_rate:.1f}%")
    with col4:
        delta_color = "normal" if total_pnl >= 0 else "inverse"
        st.metric("Total PnL", f"${total_pnl:+.2f}", delta_color=delta_color)
    with col5:
        st.metric("Max Drawdown", f"${max_dd:.2f}")

    st.markdown("---")

    # ── Active positions ──────────────────────────────────────────────────────
    st.markdown("### 📊 Open Positions")
    if not active:
        st.info("No active positions. Waiting for market open or valid signals.")
    else:
        for trade_id, pos in active.items():
            health = health_all.get(trade_id, {})
            symbol = pos.get("symbol", "?")
            entry  = float(pos.get("entry_price", 0))
            curr_sl = float(pos.get("current_sl", pos.get("stop_loss", 0)))
            tp1    = float(pos.get("take_profit_1", 0))
            tp2    = float(pos.get("take_profit_2", 0))
            shares = pos.get("shares", 0)
            stage  = pos.get("stage", 1)
            partials = pos.get("partials_taken", [])
            price  = health.get("price", entry)
            pnl    = (price - entry) * shares
            pnl_pct = health.get("pnl_pct", 0)
            score  = health.get("score", 50)
            status = health.get("status", "🟡 CAUTION")
            h_color = "#00ff88" if score >= 70 else ("#ffaa00" if score >= 45 else "#ff4444")

            with st.expander(
                f"{status}  |  {symbol}  |  PnL: ${pnl:+.2f}  ({pnl_pct:+.1f}%)",
                expanded=True
            ):
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.metric("Entry Price",   f"${entry:.2f}")
                    st.metric("Current SL",    f"${curr_sl:.2f}")
                with c2:
                    st.metric("Target 1",      f"${tp1:.2f}")
                    st.metric("Target 2",      f"${tp2:.2f}")
                with c3:
                    st.metric("Shares",        shares)
                    st.metric("Stage",         f"{stage}/3")
                with c4:
                    st.metric("Partials",      ", ".join(partials) or "None")
                    st.metric("Entry Quality", pos.get("entry_quality", "N/A"))

                # Health gauge
                fig_health = go.Figure(go.Indicator(
                    mode  = "gauge+number",
                    value = score,
                    title = {"text": "Health Score", "font": {"color": "#ccc"}},
                    gauge = {
                        "axis":  {"range": [0, 100], "tickcolor": "#666"},
                        "bar":   {"color": h_color},
                        "steps": [
                            {"range": [0,  45], "color": "#1a0000"},
                            {"range": [45, 70], "color": "#1a1a00"},
                            {"range": [70, 100],"color": "#001a00"},
                        ],
                        "threshold": {
                            "line":  {"color": "white", "width": 2},
                            "thickness": 0.75,
                            "value": score,
                        },
                    },
                    number={"font": {"color": h_color}},
                ))
                fig_health.update_layout(
                    height=200, paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font_color="#ccc", margin=dict(t=30, b=0, l=0, r=0)
                )
                st.plotly_chart(fig_health, use_container_width=True,
                                key=f"health_{trade_id}_{int(datetime.datetime.now().timestamp())}")

                # Execution timeline
                opened  = pos.get("opened_at", "")[:16]
                st.caption(f"📅 Opened: {opened} | Paper Trade ID: `{trade_id}`")

    st.markdown("---")

    # ── Closed trades table ───────────────────────────────────────────────────
    st.markdown("### 📋 Closed Trades")
    if not closed:
        st.caption("No closed trades yet.")
    else:
        rows = []
        for tid, p in closed.items():
            entry  = float(p.get("entry_price", 0))
            exit_p = float(p.get("exit_price", 0))
            shares = p.get("shares", 0)
            pnl    = round((exit_p - entry) * shares, 2)
            rows.append({
                "Symbol":  p.get("symbol", "?"),
                "Entry":   f"${entry:.2f}",
                "Exit":    f"${exit_p:.2f}",
                "Shares":  shares,
                "PnL":     f"${pnl:+.2f}",
                "Result":  p.get("exit_reason", ""),
                "Status":  p.get("status", ""),
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("---")

    # ── Equity curve ─────────────────────────────────────────────────────────
    st.markdown("### 📈 Equity Curve")
    equity_curve = perf.get("equity_curve", [])
    if len(equity_curve) >= 2:
        df_eq = pd.DataFrame(equity_curve)
        fig_eq = go.Figure()
        fig_eq.add_trace(go.Scatter(
            x=df_eq.get("ts", list(range(len(equity_curve)))),
            y=df_eq.get("equity", [50000] * len(equity_curve)),
            mode="lines",
            line=dict(color="#00ff88", width=2),
            fill="tozeroy",
            fillcolor="rgba(0,255,136,0.05)",
            name="Equity",
        ))
        fig_eq.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor ="rgba(0,0,0,0)",
            font_color   ="#ccc",
            xaxis=dict(gridcolor="#222"),
            yaxis=dict(gridcolor="#222"),
            height=250,
            margin=dict(t=10, b=10, l=0, r=0),
        )
        st.plotly_chart(fig_eq, use_container_width=True,
                        key=f"equity_{int(datetime.datetime.now().timestamp())}")
    else:
        st.caption("Equity curve will appear after first trades.")

    # ── Daily PnL bar ─────────────────────────────────────────────────────────
    daily_pnl = perf.get("daily_pnl", {})
    if daily_pnl:
        st.markdown("### 📊 Daily PnL")
        df_daily = pd.DataFrame([
            {"Date": d, "PnL": v} for d, v in sorted(daily_pnl.items())
        ])
        fig_daily = px.bar(
            df_daily, x="Date", y="PnL",
            color="PnL",
            color_continuous_scale=["#ff4444", "#888888", "#00ff88"],
            color_continuous_midpoint=0,
        )
        fig_daily.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor ="rgba(0,0,0,0)",
            font_color   ="#ccc",
            height=200,
            margin=dict(t=10, b=10, l=0, r=0),
            showlegend=False,
        )
        st.plotly_chart(fig_daily, use_container_width=True,
                        key=f"daily_{int(datetime.datetime.now().timestamp())}")

    # ── Trade journal ─────────────────────────────────────────────────────────
    if journal:
        st.markdown("### 📓 Trade Journal (Last 10)")
        df_j = pd.DataFrame(journal[-10:][::-1])
        cols = ["timestamp","symbol","event","market_regime",
                "entry_price","execution_quality","exit_quality",
                "efficiency_score","notes"]
        cols = [c for c in cols if c in df_j.columns]
        st.dataframe(df_j[cols], use_container_width=True, hide_index=True)

    st.caption("⚠️ PAPER TRADING ONLY — All figures are simulated. No real money.")


if __name__ == "__main__":
    st.set_page_config(page_title="Position Management", layout="wide")
    render_position_management()
