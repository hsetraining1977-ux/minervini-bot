"""
health_dashboard.py - System Health Panel - PAPER TRADING ONLY
"""
import streamlit as st
import json, os, time, datetime
import pandas as pd
import plotly.graph_objects as go

DATA_DIR = "/root/logs"

def _load(path, default={}):
    try:
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    except Exception:
        pass
    return default

def render_health_dashboard():
    st.markdown(
        "<div style='background:linear-gradient(135deg,#050510,#001a00);"
        "padding:18px;border-radius:14px;border-left:4px solid #00ff88;"
        "margin-bottom:24px'>"
        "<h2 style='color:#00ff88;margin:0'>SYSTEM HEALTH CENTER</h2>"
        "<p style='color:#555;margin:4px 0 0;font-size:0.82em'>"
        "PAPER TRADING ONLY</p></div>",
        unsafe_allow_html=True
    )

    health   = _load(f"{DATA_DIR}/health_status.json")
    em_state = _load(f"{DATA_DIR}/emergency_mode.json", {"active": False})
    ks_state = _load(f"{DATA_DIR}/kill_switch.json",    {"active": False})
    heat     = _load(f"{DATA_DIR}/portfolio_heat.json", {})

    if em_state.get("active"):
        triggers = ", ".join(em_state.get("triggers", []))
        st.error(f"EMERGENCY SAFE MODE ACTIVE | {triggers}")
    if ks_state.get("active"):
        st.error(f"KILL SWITCH ACTIVE | {ks_state.get('reason','')}")

    st.markdown("### System Resources")
    c1, c2, c3, c4 = st.columns(4)
    cpu     = health.get("cpu_pct", 0)
    ram     = health.get("ram_pct", 0)
    disk    = health.get("disk_pct", 0)
    api_lat = health.get("api_latency_ms", 9999)
    with c1: st.metric("CPU",         f"{cpu:.1f}%")
    with c2: st.metric("RAM",         f"{ram:.1f}%")
    with c3: st.metric("Disk",        f"{disk:.1f}%")
    with c4: st.metric("API Latency", f"{api_lat:.0f}ms")

    col1, col2 = st.columns(2)
    for fig_val, fig_title, col in [(cpu,"CPU %",col1),(ram,"RAM %",col2)]:
        color = "#00ff88" if fig_val < 70 else "#ff4444"
        fig = go.Figure(go.Indicator(
            mode="gauge+number", value=fig_val,
            title={"text": fig_title, "font": {"color": "#ccc"}},
            gauge={
                "axis": {"range": [0,100]},
                "bar":  {"color": color},
                "steps": [
                    {"range": [0,70],  "color": "#001a00"},
                    {"range": [70,90], "color": "#1a1a00"},
                    {"range": [90,100],"color": "#1a0000"},
                ],
            },
        ))
        fig.update_layout(height=180, paper_bgcolor="rgba(0,0,0,0)",
                          margin=dict(t=30,b=0,l=0,r=0))
        with col:
            st.plotly_chart(fig, use_container_width=True,
                            key=f"{fig_title}_{int(time.time()*1000)}")

    st.markdown("---")
    st.markdown("### Process Status")
    procs     = health.get("processes", {})
    restarts  = health.get("restart_counts", {})
    if procs:
        rows = [{"Process": n, "Status": "Running" if r else "Stopped",
                 "Restarts": restarts.get(n,0)} for n,r in procs.items()]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.caption("Run system_supervisor.py to enable process monitoring")

    st.markdown("---")
    st.markdown("### Data Freshness")
    files = {
        "market_intelligence.json": "Market Intelligence",
        "portfolio_heat.json":      "Portfolio Heat",
        "trade_plans.json":         "Trade Plans",
    }
    rows = []
    for fname, label in files.items():
        path = f"{DATA_DIR}/{fname}"
        if os.path.exists(path):
            age = (time.time() - os.path.getmtime(path)) / 60
            rows.append({"Source": label, "Age": f"{age:.1f}m",
                         "Status": "Fresh" if age < 15 else "STALE"})
        else:
            rows.append({"Source": label, "Age": "N/A", "Status": "Missing"})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("### Portfolio + Safety")
    h1,h2,h3,h4,h5,h6 = st.columns(6)
    with h1: st.metric("Heat",      f"{heat.get('portfolio_heat_pct',0):.1f}%")
    with h2: st.metric("Cash",      f"{heat.get('cash_pct',100):.1f}%")
    with h3: st.metric("Positions", heat.get("position_count",0))
    with h4: st.metric("PnL",       f"${heat.get('total_unrealized',0):+.2f}")
    with h5: st.metric("Emergency", "ON" if em_state.get("active") else "OFF")
    with h6: st.metric("Data Age",  f"{health.get('data_age_mins',0):.1f}m")

    ts = health.get("timestamp","")[:16]
    st.caption(f"PAPER TRADING ONLY | Health check: {ts}")

if __name__ == "__main__":
    st.set_page_config(page_title="System Health", layout="wide")
    render_health_dashboard()
