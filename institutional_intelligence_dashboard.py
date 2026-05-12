import time
#!/usr/bin/env python3
"""
institutional_intelligence_dashboard.py
INSTITUTIONAL MARKET INTELLIGENCE LAYER
New dashboard sections: Breadth, Sector Heatmap, Leaders, Smart Money, Cross-Asset Matrix.
Import this in dashboard_new.py or run standalone.
"""

import os, json, sys
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

sys.path.insert(0, '/root')

# ── Data loaders ──────────────────────────────────────────────
def load_json(path: str) -> dict:
    try:
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def load_breadth():       return load_json("/root/logs/breadth_data.json")
def load_smart_money():   return load_json("/root/logs/smart_money.json")
def load_intelligence():  return load_json("/root/logs/market_intelligence.json")


# ── Color helpers ─────────────────────────────────────────────
DARK_BG  = "rgba(0,0,0,0)"
FONT_CLR = "#aabbcc"

def pct_color(v): return "#00ff88" if v > 0 else "#ff4444" if v < 0 else "#888"
def score_color(s):
    if s >= 75: return "#00ff88"
    if s >= 50: return "#ffdd00"
    if s >= 30: return "#ff8800"
    return "#ff4444"


# ── MAIN RENDER FUNCTION ──────────────────────────────────────
def render_institutional_intelligence():
    """Call this from dashboard_new.py to add institutional intelligence."""

    st.markdown("""
    <div style='background:linear-gradient(135deg,#050510,#0a0a1e);
                border:1px solid #1a2332; border-radius:12px;
                padding:16px 24px; margin:20px 0;'>
        <h2 style='color:#00d4ff; margin:0; font-family:monospace;
                   letter-spacing:3px; font-size:1.2em;'>
            🏛️ INSTITUTIONAL MARKET INTELLIGENCE
        </h2>
        <p style='color:#445566; margin:4px 0 0; font-size:0.8em;'>
            Breadth · Leaders · Smart Money · Cross-Asset · AI Narrative
        </p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Breadth",
        "🏆 Leaders",
        "💰 Smart Money",
        "🌐 Cross-Asset",
        "🤖 AI Narrative",
    ])

    with tab1: render_breadth_monitor()
    with tab2: render_institutional_leaders()
    with tab3: render_smart_money_flow()
    with tab4: render_cross_asset_matrix()
    with tab5: render_ai_narrative()


# ── Tab 1: Breadth Monitor ────────────────────────────────────
def render_breadth_monitor():
    data = load_breadth()
    if not data:
        st.info("Breadth data loading... Run: python3 /root/breadth_engine.py")
        _show_run_button("breadth_engine")
        return

    overall = data.get("overall_score", 0)
    quality = data.get("overall_quality", "N/A")
    ts      = data.get("timestamp", "")[:16]

    # Overall gauge
    col1, col2, col3 = st.columns(3)
    col1.metric("Breadth Score", f"{overall}/100", quality)
    col2.metric("Market Health", data.get("market_health", "")[:30])
    col3.metric("Updated", ts)

    st.markdown("---")

    # SPY vs QQQ
    spy = data.get("spy", {})
    qqq = data.get("qqq", {})

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**📈 SPY Breadth**")
        _breadth_metrics(spy)

    with col_b:
        st.markdown("**🔵 QQQ Breadth**")
        _breadth_metrics(qqq)

    # Gauge chart
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=overall,
        title={"text": "Market Breadth Score"},
        delta={"reference": 50},
        gauge={
            "axis": {"range": [0, 100]},
            "bar":  {"color": score_color(overall)},
            "steps": [
                {"range": [0, 30],  "color": "#1a0a0a"},
                {"range": [30, 50], "color": "#1a1500"},
                {"range": [50, 70], "color": "#0a1500"},
                {"range": [70, 100],"color": "#001a10"},
            ],
            "threshold": {"line": {"color": "#00ff88", "width": 3},
                          "thickness": 0.8, "value": 60},
        }
    ))
    fig.update_layout(height=250, paper_bgcolor=DARK_BG,
                      font_color=FONT_CLR, margin=dict(t=30,b=0,l=0,r=0))
    st.plotly_chart(fig, use_container_width=True, key=f"chart_1_{int(time.time()*1000) % 99999}")

    st.info(f"💡 {data.get('market_health','')}")


def _breadth_metrics(d: dict):
    if not d:
        st.warning("No data")
        return
    m1, m2 = st.columns(2)
    m1.metric("A/D Ratio",    f"{d.get('ad_ratio',0):.0f}%")
    m2.metric("Breadth Score",f"{d.get('breadth_score',0)}/100")
    m1.metric("Above 50MA",   f"{d.get('above_50ma',0):.0f}%")
    m2.metric("Above 200MA",  f"{d.get('above_200ma',0):.0f}%")
    m1.metric("New Highs",    d.get("new_highs", 0))
    m2.metric("New Lows",     d.get("new_lows",  0))


# ── Tab 2: Institutional Leaders ─────────────────────────────
def render_institutional_leaders():
    data    = load_intelligence()
    leaders = data.get("rs_rankings", [])

    if not leaders:
        st.info("RS Rankings loading... Run: python3 /root/market_intelligence.py")
        _show_run_button("market_intelligence")
        return

    st.markdown(f"**Top {min(20, len(leaders))} Institutional Leaders** "
                f"| Updated: {data.get('timestamp','')[:16]}")

    # Dataframe
    rows = []
    for r in leaders[:20]:
        rows.append({
            "Symbol":      r["symbol"],
            "Price":       f"${r['price']:.2f}",
            "1D%":         f"{r.get('chg_1d',0):+.2f}%",
            "1M%":         f"{r.get('chg_1m',0):+.2f}%",
            "3M%":         f"{r.get('chg_3m',0):+.2f}%",
            "RS vs SPY":   f"{r.get('rs_vs_spy',0):+.2f}%",
            "Leadership":  r.get("leadership", 0),
            "Above 50MA":  "✅" if r.get("above_ma50") else "❌",
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Bar chart of leadership scores
    top10  = leaders[:10]
    symbols = [x["symbol"] for x in top10]
    scores  = [x.get("leadership", 0) for x in top10]
    colors  = [score_color(s) for s in scores]

    fig = go.Figure(go.Bar(
        x=symbols, y=scores,
        marker_color=colors,
        text=scores, textposition="outside",
    ))
    fig.update_layout(
        title="Institutional Leadership Score",
        paper_bgcolor=DARK_BG, plot_bgcolor=DARK_BG,
        font_color=FONT_CLR, height=300,
        margin=dict(t=40, b=0, l=0, r=0),
    )
    st.plotly_chart(fig, use_container_width=True, key=f"chart_2_{int(time.time()*1000) % 99999}")


# ── Tab 3: Smart Money Flow ───────────────────────────────────
def render_smart_money_flow():
    data = load_smart_money()
    if not data:
        st.info("Smart Money data loading... Run: python3 /root/smart_money.py")
        _show_run_button("smart_money")
        return

    flow    = data.get("flow_bias", "UNKNOWN")
    scanned = data.get("scanned", 0)
    ts      = data.get("timestamp", "")[:16]

    flow_color = {"INSTITUTIONAL_BUYING": "🟢", "INSTITUTIONAL_SELLING": "🔴",
                  "MIXED_FLOW": "🟡"}.get(flow, "⚪")

    col1, col2, col3 = st.columns(3)
    col1.metric("Flow Bias",  f"{flow_color} {flow}")
    col2.metric("Scanned",    scanned)
    col3.metric("Updated",    ts)

    st.info(f"💡 {data.get('summary','')}")
    st.markdown("---")

    # Strong Buy
    strong = data.get("strong_buy", [])
    acc    = data.get("accumulating", [])
    dist   = data.get("distributing", [])
    uv     = data.get("unusual_volume", [])

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**🟢 STRONG BUY Signals**")
        if strong:
            for x in strong[:5]:
                st.markdown(f"`{x['symbol']}` | Score:{x['inst_score']} "
                            f"| Vol:{x['vol_ratio']}x | {x['vol_pressure']}")
        else:
            st.caption("None detected")

        st.markdown("**📈 Accumulating**")
        if acc:
            for x in acc[:5]:
                st.markdown(f"`{x['symbol']}` | CMF:{x['cmf']:.3f}")
        else:
            st.caption("None detected")

    with col_b:
        st.markdown("**🔴 Distributing**")
        if dist:
            for x in dist[:5]:
                st.markdown(f"`{x['symbol']}` | CMF:{x['cmf']:.3f}")
        else:
            st.caption("None detected")

        st.markdown("**⚡ Unusual Volume**")
        if uv:
            for x in uv[:5]:
                st.markdown(f"`{x['symbol']}` | {x['vol_ratio']}x average")
        else:
            st.caption("None detected")

    # Volume leaders chart
    top = data.get("top_leaders", [])[:8]
    if top:
        fig = go.Figure(go.Bar(
            x=[x["symbol"] for x in top],
            y=[x["inst_score"] for x in top],
            marker_color=[score_color(x["inst_score"]) for x in top],
            text=[f"{x['vol_ratio']}x" for x in top],
            textposition="outside",
        ))
        fig.update_layout(
            title="Institutional Score by Symbol",
            paper_bgcolor=DARK_BG, plot_bgcolor=DARK_BG,
            font_color=FONT_CLR, height=280,
            margin=dict(t=40,b=0,l=0,r=0),
        )
        st.plotly_chart(fig, use_container_width=True, key=f"chart_3_{int(time.time()*1000) % 99999}")


# ── Tab 4: Cross-Asset Matrix ─────────────────────────────────
def render_cross_asset_matrix():
    data   = load_intelligence()
    assets = data.get("assets", {})
    corr   = data.get("correlation", {})

    if not assets:
        st.info("Cross-asset data loading... Run: python3 /root/market_intelligence.py")
        return

    quality = corr.get("quality", "NEUTRAL")
    ro_pct  = corr.get("risk_on_pct", 50)

    quality_color = {
        "STRONG_RISK_ON": "#00ff88", "RISK_ON": "#88ff88",
        "NEUTRAL": "#ffdd00",
        "RISK_OFF": "#ff8800", "STRONG_RISK_OFF": "#ff4444",
    }.get(quality, "#888")

    st.markdown(f"""
    <div style='background:#0a0a1e; border:1px solid {quality_color};
                border-radius:8px; padding:12px; margin-bottom:16px; text-align:center;'>
        <span style='color:{quality_color}; font-size:1.4em; font-weight:bold;
                     font-family:monospace;'>{quality}</span>
        <span style='color:#aaa; margin-left:16px;'>Risk-On: {ro_pct:.0f}%</span>
    </div>
    """, unsafe_allow_html=True)

    # Asset table
    rows = []
    display_order = ["SPY","QQQ","IWM","GLD","USO","BTC","VIX",
                      "XLK","XLF","XLE","XLV","XLI","XLRE","TNX"]
    for key in display_order:
        d = assets.get(key)
        if not d:
            continue
        rows.append({
            "Asset":  f"{key} ({ASSETS_META.get(key,'')[:12]})",
            "1D%":    f"{d.get('chg_1d',0):+.2f}%",
            "1W%":    f"{d.get('chg_1w',0):+.2f}%",
            "1M%":    f"{d.get('chg_1m',0):+.2f}%",
            "3M%":    f"{d.get('chg_3m',0):+.2f}%",
            "vs 50MA":"✅" if d.get("above_ma") else "❌",
        })

    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # Heatmap of 1D changes
    heatmap_data = {
        k: v.get("chg_1d", 0) for k, v in assets.items()
        if k in display_order
    }
    if heatmap_data:
        keys = list(heatmap_data.keys())
        vals = list(heatmap_data.values())
        fig  = go.Figure(go.Bar(
            x=keys, y=vals,
            marker_color=[pct_color(v) for v in vals],
            text=[f"{v:+.2f}%" for v in vals],
            textposition="outside",
        ))
        fig.update_layout(
            title="Cross-Asset 1-Day Change %",
            paper_bgcolor=DARK_BG, plot_bgcolor=DARK_BG,
            font_color=FONT_CLR, height=300,
            margin=dict(t=40,b=0,l=0,r=0),
        )
        st.plotly_chart(fig, use_container_width=True, key=f"chart_4_{int(time.time()*1000) % 99999}")


ASSETS_META = {
    "SPY":"S&P 500","QQQ":"Nasdaq","IWM":"Russell",
    "GLD":"Gold","USO":"Oil","BTC":"Bitcoin","VIX":"Volatility",
    "XLK":"Tech","XLF":"Financials","XLE":"Energy",
    "XLV":"Healthcare","XLI":"Industrials","XLRE":"Real Estate","TNX":"10Y Yield",
}


# ── Tab 5: AI Narrative ───────────────────────────────────────
def render_ai_narrative():
    data = load_intelligence()
    narrative = data.get("narrative", "")

    if not narrative:
        st.info("AI Narrative loading... Run: python3 /root/market_intelligence.py")
        _show_run_button("market_intelligence")
        return

    ts = data.get("timestamp", "")[:16]
    st.markdown(f"**Generated:** `{ts}`")
    st.markdown("---")

    st.markdown(f"""
    <div style='background:#050510; border:1px solid #1a2332; border-radius:8px;
                padding:20px; font-family:monospace; font-size:0.85em;
                color:#aabbcc; line-height:1.8; white-space:pre-wrap;'>
{narrative}
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.caption("⚠️ AI-generated market narrative — Intelligence Only, No Auto Execution")


def _show_run_button(module: str):
    st.code(f"python3 /root/{module}.py >> /root/logs/{module}.out 2>&1 &")


# ── Standalone run ────────────────────────────────────────────
if __name__ == "__main__":
    st.set_page_config(
        page_title="Institutional Intelligence",
        page_icon="🏛️",
        layout="wide"
    )
    render_institutional_intelligence()
