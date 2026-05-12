import time
#!/usr/bin/env python3
"""
trade_center.py — Trade Center Dashboard Module
SEMI-AUTONOMOUS EXECUTION LAYER | Intelligence Only
Streamlit component showing Trade Plans, Watchlist, Risk Simulator.
Import this in dashboard.py or run standalone.
"""

import os, json
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# ── Data loaders ──────────────────────────────────────────────
PLANS_FILE     = "/root/logs/trade_plans.json"
WATCHLIST_FILE = "/root/logs/watchlist.json"

def load_plans() -> dict:
    try:
        if os.path.exists(PLANS_FILE):
            with open(PLANS_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def load_watchlist() -> dict:
    try:
        if os.path.exists(WATCHLIST_FILE):
            with open(WATCHLIST_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


# ── Color helpers ─────────────────────────────────────────────
def score_color(score: float) -> str:
    if score >= 85: return "#00ff88"
    if score >= 70: return "#ffdd00"
    if score >= 55: return "#ff8800"
    return "#ff4444"

def status_badge(status: str) -> str:
    badges = {
        "READY":   "🟢 READY",
        "CREATED": "🔵 CREATED",
        "ACTIVE":  "⚡ ACTIVE",
        "TP_HIT":  "🏆 TP HIT",
        "SL_HIT":  "🔴 SL HIT",
        "EXPIRED": "⏰ EXPIRED",
    }
    return badges.get(status, status)


# ── Trade Center Main ─────────────────────────────────────────
def render_trade_center():
    """Main Trade Center UI — call from dashboard.py"""

    st.markdown("""
    <div style='background: linear-gradient(135deg, #0a0a1a 0%, #0d1117 100%);
                border: 1px solid #1a2332; border-radius: 12px;
                padding: 16px 24px; margin-bottom: 20px;'>
        <h2 style='color: #00d4ff; margin:0; font-family: monospace;
                   letter-spacing: 3px; font-size: 1.3em;'>
            🎯 TRADE CENTER
        </h2>
        <p style='color: #556677; margin:4px 0 0 0; font-size: 0.8em;'>
            AI-Assisted Institutional Intelligence | NO AUTO EXECUTION
        </p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Trade Plans", "👁 Watchlist", "🎯 Risk Simulator", "📊 Lifecycle"
    ])

    with tab1:
        render_trade_plans()

    with tab2:
        render_watchlist()

    with tab3:
        render_risk_simulator()

    with tab4:
        render_lifecycle()


# ── Tab 1: Trade Plans ────────────────────────────────────────
def render_trade_plans():
    plans = load_plans()
    now   = datetime.now()

    active = [p for p in plans.values()
              if p.get("status") in ("READY", "CREATED", "ACTIVE")]
    active = sorted(active, key=lambda x: x.get("execution_score", 0), reverse=True)

    if not active:
        st.info("No active trade plans. System is scanning for opportunities...")
        return

    st.markdown(f"**{len(active)} Active Plans** — sorted by Execution Score")

    for plan in active[:10]:
        with st.expander(
            f"{status_badge(plan.get('status',''))} | "
            f"{plan['symbol']} | "
            f"Score: {plan.get('score',0):.0f} | "
            f"Exec: {plan.get('execution_score',0)}/100 | "
            f"{plan.get('trade_type','SWING')}",
            expanded=plan.get("execution_score", 0) >= 80
        ):
            col1, col2, col3 = st.columns(3)

            with col1:
                st.markdown("**💰 Price Levels**")
                st.metric("Entry",      f"${plan.get('entry', 0):.2f}")
                st.metric("Stop Loss",  f"${plan.get('stop_loss', 0):.2f}",
                          delta=f"-${plan.get('risk_per_share', 0):.2f}")
                st.metric("Target 2",   f"${plan.get('take_profit_2', 0):.2f}",
                          delta=f"+${plan.get('reward_per_share', 0):.2f}")

            with col2:
                st.markdown("**📐 Risk Metrics**")
                st.metric("Position",    f"{plan.get('position_size', 0):,} shares")
                st.metric("Max Loss",    f"${plan.get('max_loss_usd', 0):,.0f}")
                st.metric("R:R Ratio",   f"{plan.get('risk_reward', 0):.1f}:1")

            with col3:
                st.markdown("**✅ Checklist**")
                cl = plan.get("checklist", {})
                for key, label in [
                    ("regime_ok",       "Regime"),
                    ("liquidity_ok",    "Liquidity"),
                    ("volume_confirmed","Volume"),
                    ("mtf_confirmed",   "MTF"),
                    ("rs_strong",       "RS Rating"),
                ]:
                    icon = "✅" if cl.get(key) else "❌"
                    st.write(f"{icon} {label}")

            # AI Panel
            st.markdown("---")
            st.markdown("**🤖 AI Reasoning**")
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("**Positive Factors**")
                for f in plan.get("positive_factors", [])[:4]:
                    st.markdown(f"✦ {f}")
            with col_b:
                st.markdown("**Risk Factors**")
                for f in plan.get("risk_factors", [])[:3]:
                    st.markdown(f"⚠️ {f}")

            st.info(f"🤖 {plan.get('ai_summary', '')}")
            st.caption(f"Plan ID: {plan.get('plan_id','')} | "
                      f"Expires: {plan.get('expires_at','')[:16]}")

            # Execution readiness gauge
            exec_score = plan.get("execution_score", 0)
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=exec_score,
                title={"text": "Execution Readiness"},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar":  {"color": score_color(exec_score)},
                    "steps": [
                        {"range": [0, 60],  "color": "#1a1a2e"},
                        {"range": [60, 80], "color": "#16213e"},
                        {"range": [80, 100],"color": "#0f3460"},
                    ],
                    "threshold": {
                        "line":  {"color": "#00ff88", "width": 4},
                        "thickness": 0.75,
                        "value": 80,
                    },
                },
            ))
            fig.update_layout(
                height=200,
                paper_bgcolor="rgba(0,0,0,0)",
                font_color="#aabbcc",
                margin=dict(t=30, b=0, l=0, r=0),
            )
            st.plotly_chart(fig, use_container_width=True, key=f"chart_1_{int(time.time()*1000) % 99999}")


# ── Tab 2: Watchlist ──────────────────────────────────────────
def render_watchlist():
    wl = load_watchlist()

    if not wl:
        st.info("Watchlist not yet generated. Run watchlist_intelligence.py")
        return

    st.markdown(f"**Regime:** `{wl.get('regime','?')}` | "
                f"**VIX:** `{wl.get('vix', 0):.1f}` | "
                f"**Updated:** `{wl.get('timestamp','')[:16]}`")
    st.caption(wl.get("rationale", ""))

    watchlist = wl.get("watchlist", {})

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🥇 Tier 1 — Primary Focus")
        for sym in watchlist.get("TIER_1", []):
            st.markdown(f"```\n{sym}\n```")

    with col2:
        st.markdown("### 🥈 Tier 2 — Secondary")
        for sym in watchlist.get("TIER_2", []):
            st.markdown(f"```\n{sym}\n```")

    avoid = watchlist.get("AVOID", [])
    if avoid:
        st.markdown("### 🚫 Avoid in Current Regime")
        st.write(", ".join(avoid))

    st.markdown("---")
    st.markdown("**📡 Scan Focus** (Top 10 to scan first):")
    focus = wl.get("scan_focus", [])
    cols  = st.columns(min(5, len(focus)))
    for i, sym in enumerate(focus[:10]):
        with cols[i % 5]:
            st.metric(sym, "🎯")


# ── Tab 3: Risk Simulator ─────────────────────────────────────
def render_risk_simulator():
    st.markdown("### 🎯 Position Risk Simulator")
    st.caption("⚠️ Simulation only — no orders are placed")

    col1, col2 = st.columns(2)
    with col1:
        capital  = st.number_input("Portfolio Capital ($)", value=50000,
                                    min_value=1000, step=1000)
        risk_pct = st.slider("Risk per Trade (%)", 0.5, 5.0, 2.0, 0.5) / 100
        entry    = st.number_input("Entry Price ($)", value=100.0,
                                    min_value=0.01, step=0.5)

    with col2:
        stop  = st.number_input("Stop Loss ($)", value=97.0,
                                 min_value=0.01, step=0.5)
        tp    = st.number_input("Take Profit ($)", value=108.0,
                                 min_value=0.01, step=0.5)
        sym   = st.text_input("Symbol (optional)", value="")

    if st.button("🔢 Calculate Risk", type="primary"):
        try:
            from risk_simulator import simulate_risk, format_simulation
            sim = simulate_risk(capital, risk_pct, entry, stop, tp)
            if sim:
                col_a, col_b, col_c, col_d = st.columns(4)
                col_a.metric("Position Size", f"{sim.position_size:,} shares")
                col_b.metric("Max Loss",      f"${sim.max_loss_usd:,.0f}",
                              delta=f"-{sim.max_loss_pct:.1f}%")
                col_c.metric("Target Gain",   f"${sim.target_gain:,.0f}",
                              delta=f"+{sim.target_gain_pct:.1f}%")
                col_d.metric("R:R Ratio",     f"{sim.risk_reward:.1f}:1")

                # Warnings
                for w in sim.warnings:
                    st.warning(w)

                st.success(sim.recommendation)

                # Chart
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=["Max Loss", "Target Gain"],
                    y=[-sim.max_loss_usd, sim.target_gain],
                    marker_color=["#ff4444", "#00ff88"],
                    name="P&L"
                ))
                fig.update_layout(
                    title="Risk vs Reward",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font_color="#aabbcc",
                    height=300,
                )
                st.plotly_chart(fig, use_container_width=True, key=f"chart_2_{int(time.time()*1000) % 99999}")
        except ImportError:
            st.error("risk_simulator.py not found on server")
        except Exception as e:
            st.error(f"Calculation error: {e}")


# ── Tab 4: Lifecycle ──────────────────────────────────────────
def render_lifecycle():
    plans = load_plans()

    if not plans:
        st.info("No trade history yet.")
        return

    # Status summary
    status_counts = {}
    for p in plans.values():
        s = p.get("status", "UNKNOWN")
        status_counts[s] = status_counts.get(s, 0) + 1

    cols = st.columns(len(status_counts))
    for i, (status, count) in enumerate(status_counts.items()):
        cols[i].metric(status_badge(status), count)

    st.markdown("---")
    st.markdown("**📋 All Trade Plans**")

    rows = []
    for p in plans.values():
        rows.append({
            "Symbol":   p.get("symbol", ""),
            "Type":     p.get("trade_type", ""),
            "Entry":    f"${p.get('entry', 0):.2f}",
            "SL":       f"${p.get('stop_loss', 0):.2f}",
            "TP2":      f"${p.get('take_profit_2', 0):.2f}",
            "R:R":      f"{p.get('risk_reward', 0):.1f}",
            "Score":    p.get("score", 0),
            "Exec":     p.get("execution_score", 0),
            "Status":   status_badge(p.get("status", "")),
            "Created":  p.get("created_at", "")[:16],
        })

    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)


# ── Standalone run ────────────────────────────────────────────
if __name__ == "__main__":
    st.set_page_config(
        page_title="Trade Center",
        page_icon="🎯",
        layout="wide"
    )
    render_trade_center()
