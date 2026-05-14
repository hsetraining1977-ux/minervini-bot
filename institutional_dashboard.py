#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║   MINERVINI AI — INSTITUTIONAL INTELLIGENCE DASHBOARD            ║
║   Port 8504 — Real-time Regime + Breadth + Sector + Vol + Liq   ║
║   ANALYTICS ONLY — PAPER MODE                                    ║
╚══════════════════════════════════════════════════════════════════╝
"""

import streamlit as st
import json
import os
import time
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

# ── Page Config ───────────────────────────────────────────────────
st.set_page_config(
    page_title="Minervini AI — Institutional Intelligence",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Paths ─────────────────────────────────────────────────────────
PATHS = {
    "regime":    "/root/adaptive/institutional_regime.json",
    "breadth":   "/root/adaptive/breadth_metrics.json",
    "sector":    "/root/adaptive/sector_rotation.json",
    "vol":       "/root/adaptive/volatility_regime.json",
    "liquidity": "/root/adaptive/liquidity_state.json",
    "history":   "/root/adaptive/regime_history.json",
}

# ── Color Theme ───────────────────────────────────────────────────
REGIME_COLORS = {
    "STRONG_RISK_ON": "#00ff88",
    "RISK_ON":        "#44dd66",
    "NEUTRAL":        "#aaaaaa",
    "CHOPPY":         "#ffaa00",
    "RISK_OFF":       "#ff6644",
    "PANIC":          "#ff2222",
}

RATING_COLORS = {
    "HIGHLY_FAVORABLE": "#00ff88",
    "FAVORABLE":        "#44cc66",
    "NEUTRAL":          "#888888",
    "REDUCED":          "#ff8800",
    "AVOID":            "#ff3333",
    "DANGEROUS":        "#cc0000",
}

# ── CSS ───────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #0a0a0a; }
    .stApp { background-color: #0a0a0a; color: #e0e0e0; }
    
    .regime-card {
        background: linear-gradient(135deg, #0d1117 0%, #161b22 100%);
        border-radius: 16px;
        padding: 28px;
        text-align: center;
        border: 2px solid #30363d;
        margin-bottom: 16px;
    }
    .regime-label {
        font-size: 11px;
        letter-spacing: 3px;
        color: #8b949e;
        text-transform: uppercase;
        margin-bottom: 8px;
    }
    .regime-value {
        font-size: 28px;
        font-weight: 900;
        letter-spacing: 1px;
        margin-bottom: 4px;
    }
    .regime-sub {
        font-size: 13px;
        color: #8b949e;
    }
    
    .metric-card {
        background: #0d1117;
        border: 1px solid #21262d;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
    }
    .metric-label {
        font-size: 10px;
        letter-spacing: 2px;
        color: #6e7681;
        text-transform: uppercase;
    }
    .metric-value {
        font-size: 32px;
        font-weight: 700;
        margin: 6px 0;
    }
    .metric-sub {
        font-size: 12px;
        color: #8b949e;
    }
    
    .section-header {
        font-size: 11px;
        letter-spacing: 3px;
        color: #6e7681;
        text-transform: uppercase;
        border-bottom: 1px solid #21262d;
        padding-bottom: 8px;
        margin: 24px 0 16px 0;
    }
    
    .setup-pill {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 600;
        margin: 3px;
        letter-spacing: 0.5px;
    }
    
    .narrative-box {
        background: #0d1117;
        border-left: 3px solid #00ff88;
        border-radius: 8px;
        padding: 20px 24px;
        font-size: 14px;
        line-height: 1.7;
        color: #c9d1d9;
        font-style: italic;
    }
    
    .score-bar-container {
        background: #161b22;
        border-radius: 6px;
        height: 8px;
        width: 100%;
        margin-top: 6px;
    }
    
    .stButton button {
        background: #21262d;
        color: #e6edf3;
        border: 1px solid #30363d;
        border-radius: 8px;
        font-size: 12px;
        letter-spacing: 1px;
    }
</style>
""", unsafe_allow_html=True)


# ── Data Loaders ──────────────────────────────────────────────────
@st.cache_data(ttl=60)
def load_json(path: str) -> dict:
    try:
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def load_all() -> dict:
    return {k: load_json(v) for k, v in PATHS.items()}


def age_str(data: dict) -> str:
    try:
        ts  = datetime.fromisoformat(data.get("timestamp", "2000-01-01"))
        age = int((datetime.now() - ts).total_seconds())
        if age < 60:   return f"{age}s ago"
        if age < 3600: return f"{age//60}m ago"
        return f"{age//3600}h ago"
    except Exception:
        return "unknown"


# ── Gauge Chart ───────────────────────────────────────────────────
def gauge_chart(value: float, title: str, color: str = "#00ff88",
                max_val: float = 100) -> go.Figure:
    fig = go.Figure(go.Indicator(
        mode  = "gauge+number",
        value = value,
        title = {"text": title, "font": {"size": 12, "color": "#8b949e"}},
        number= {"font": {"size": 28, "color": color}},
        gauge = {
            "axis":      {"range": [0, max_val], "tickcolor": "#444"},
            "bar":       {"color": color, "thickness": 0.3},
            "bgcolor":   "#161b22",
            "bordercolor": "#30363d",
            "steps": [
                {"range": [0,  33],       "color": "#1a0a0a"},
                {"range": [33, 66],       "color": "#0a1a0a"},
                {"range": [66, max_val],  "color": "#0a2a1a"},
            ],
        },
    ))
    fig.update_layout(
        height=180,
        margin=dict(t=40, b=10, l=20, r=20),
        paper_bgcolor="#0d1117",
        font_color="#e0e0e0",
    )
    return fig


# ── Radar Chart for Setup Suitability ────────────────────────────
def suitability_radar(suitability: dict) -> go.Figure:
    if not suitability:
        return go.Figure()
    setups = list(suitability.keys())
    scores = [suitability[s]["score"] for s in setups]
    short  = [s.replace("_", "\n") for s in setups]

    fig = go.Figure(go.Scatterpolar(
        r     = scores + [scores[0]],
        theta = short  + [short[0]],
        fill  = "toself",
        fillcolor = "rgba(0,255,136,0.1)",
        line  = dict(color="#00ff88", width=2),
        name  = "Suitability",
    ))
    fig.update_layout(
        polar = dict(
            bgcolor   = "#0d1117",
            radialaxis= dict(visible=True, range=[0,100],
                             color="#444", gridcolor="#222"),
            angularaxis= dict(color="#8b949e", gridcolor="#222"),
        ),
        showlegend    = False,
        paper_bgcolor = "#0d1117",
        height        = 320,
        margin        = dict(t=20, b=20, l=40, r=40),
    )
    return fig


# ── Regime History Chart ──────────────────────────────────────────
def regime_history_chart(history: list) -> go.Figure:
    if not history or len(history) < 2:
        return go.Figure()

    df = pd.DataFrame(history[-50:])
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    regime_num = {
        "STRONG_RISK_ON": 6, "RISK_ON": 5, "NEUTRAL": 4,
        "CHOPPY": 3, "RISK_OFF": 2, "PANIC": 1,
    }
    df["regime_num"] = df["regime"].map(regime_num).fillna(3)
    df["color"]      = df["regime"].map(REGIME_COLORS).fillna("#888")

    fig = go.Figure()
    for regime, color in REGIME_COLORS.items():
        mask = df["regime"] == regime
        if mask.any():
            fig.add_trace(go.Scatter(
                x    = df[mask]["timestamp"],
                y    = df[mask]["regime_num"],
                mode = "markers",
                name = regime,
                marker= dict(color=color, size=10, symbol="circle"),
            ))

    fig.add_trace(go.Scatter(
        x    = df["timestamp"],
        y    = df["regime_num"],
        mode = "lines",
        line = dict(color="#333", width=1, dash="dot"),
        showlegend = False,
    ))

    fig.update_layout(
        paper_bgcolor = "#0d1117",
        plot_bgcolor  = "#0d1117",
        height        = 220,
        margin        = dict(t=10, b=10, l=60, r=20),
        xaxis = dict(color="#444", gridcolor="#1a1a1a"),
        yaxis = dict(
            color     = "#8b949e",
            gridcolor = "#1a1a1a",
            tickvals  = list(regime_num.values()),
            ticktext  = list(regime_num.keys()),
        ),
        legend = dict(bgcolor="#0d1117", font_color="#8b949e", x=1.01),
    )
    return fig


# ── Sector Bar Chart ──────────────────────────────────────────────
def sector_bar_chart(sector_data: dict, rankings: list) -> go.Figure:
    if not rankings:
        return go.Figure()

    tickers = [r["ticker"] for r in rankings]
    scores  = [r["score"]  for r in rankings]
    names   = [r["name"]   for r in rankings]
    colors  = ["#00ff88" if s > 0 else "#ff4444" for s in scores]

    fig = go.Figure(go.Bar(
        x           = names,
        y           = scores,
        marker_color= colors,
        text        = [f"{s:+.1f}" for s in scores],
        textposition= "outside",
    ))
    fig.update_layout(
        paper_bgcolor = "#0d1117",
        plot_bgcolor  = "#0d1117",
        height        = 260,
        margin        = dict(t=10, b=10, l=20, r=20),
        xaxis = dict(color="#8b949e", gridcolor="#1a1a1a", tickangle=-30),
        yaxis = dict(color="#8b949e", gridcolor="#1a1a1a",
                     zeroline=True, zerolinecolor="#333"),
        showlegend = False,
    )
    return fig


# ── Vol Score Chart ───────────────────────────────────────────────
def vol_timeline_chart(vol: dict) -> go.Figure:
    vix   = vol.get("vix_current", 20)
    score = vol.get("volatility_score", 50)
    cats  = ["LOW_VOL", "NORMAL_VOL", "HIGH_VOL", "EXTREME_VOL"]
    vals  = [25, 50, 75, 100]
    colors= ["#00ff88", "#44aaff", "#ffaa00", "#ff3333"]

    fig = go.Figure()
    for c, v, col in zip(cats, vals, colors):
        fig.add_shape(type="rect",
            x0=v-25, x1=v, y0=0, y1=1,
            fillcolor=col, opacity=0.15,
            line=dict(width=0),
        )
        fig.add_annotation(x=v-12.5, y=0.5, text=c.replace("_VOL",""),
                           showarrow=False, font=dict(size=9, color=col))

    fig.add_shape(type="line",
        x0=score, x1=score, y0=0, y1=1,
        line=dict(color="#ffffff", width=3),
    )
    fig.add_annotation(x=score, y=1.05,
        text=f"VIX {vix:.1f}", showarrow=False,
        font=dict(size=11, color="#ffffff"),
    )
    fig.update_layout(
        paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
        height=100, margin=dict(t=30, b=10, l=10, r=10),
        xaxis=dict(range=[0,100], showgrid=False, showticklabels=False),
        yaxis=dict(range=[0,1.2], showgrid=False, showticklabels=False),
    )
    return fig


# ════════════════════════════════════════════════════════════════
#                        MAIN DASHBOARD
# ════════════════════════════════════════════════════════════════
def main():
    # ── Sidebar ───────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### 🏛️ Institutional Intelligence")
        st.caption("ANALYTICS ONLY · PAPER MODE")
        st.divider()

        auto_refresh = st.toggle("Auto Refresh (60s)", value=True)
        if st.button("🔄 Force Refresh"):
            st.cache_data.clear()
            st.rerun()

        if st.button("⚡ Run All Engines"):
            with st.spinner("Running engines..."):
                try:
                    import subprocess
                    subprocess.Popen(
                        ["nice", "-n", "19", "python3",
                         "/root/institutional_regime_classifier.py"],
                        stdout=open("/root/logs/regime_classifier.log","a"),
                        stderr=subprocess.STDOUT,
                    )
                    st.success("Engines triggered!")
                    time.sleep(2)
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

        st.divider()
        st.markdown("**Quick Links**")
        st.markdown("📊 [Main Dashboard](http://144.202.11.183:8501)")
        st.markdown("🧠 [Adaptive Intel](http://144.202.11.183:8503)")

    # ── Load Data ─────────────────────────────────────────────────
    data    = load_all()
    regime  = data["regime"]
    breadth = data["breadth"]
    sector  = data["sector"]
    vol     = data["vol"]
    liq     = data["liquidity"]
    history = data["history"] if isinstance(data["history"], list) else []

    # ── Header ────────────────────────────────────────────────────
    col_title, col_time = st.columns([3, 1])
    with col_title:
        st.markdown("# 🏛️ Institutional Intelligence Center")
    with col_time:
        st.markdown(f"<br><small style='color:#555'>Updated: {age_str(regime)}</small>",
                    unsafe_allow_html=True)

    st.markdown(
        "<div style='background:#161b22;padding:6px 16px;border-radius:6px;"
        "font-size:11px;letter-spacing:2px;color:#8b949e;margin-bottom:20px'>"
        "BREADTH · SECTOR ROTATION · VOLATILITY · LIQUIDITY · REGIME INTELLIGENCE"
        " · PAPER ONLY</div>",
        unsafe_allow_html=True,
    )

    # ══════════════════════════════════════════════════════════════
    # SECTION 1 — MASTER REGIME
    # ══════════════════════════════════════════════════════════════
    current_regime = regime.get("regime", "UNKNOWN")
    confidence     = regime.get("regime_confidence", 0)
    inst_part      = regime.get("institutional_participation", 50)
    regime_color   = REGIME_COLORS.get(current_regime, "#888")

    st.markdown('<div class="section-header">MASTER REGIME</div>',
                unsafe_allow_html=True)

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown(f"""
        <div class="regime-card">
            <div class="regime-label">Current Regime</div>
            <div class="regime-value" style="color:{regime_color}">
                {current_regime.replace("_"," ")}
            </div>
            <div class="regime-sub">Confidence: {confidence:.0%}</div>
        </div>""", unsafe_allow_html=True)

    with c2:
        bs = breadth.get("breadth_score", 0)
        bc = "#00ff88" if bs >= 60 else "#ffaa00" if bs >= 40 else "#ff4444"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Breadth Score</div>
            <div class="metric-value" style="color:{bc}">{bs:.0f}</div>
            <div class="metric-sub">{breadth.get("breadth_momentum","—")}</div>
        </div>""", unsafe_allow_html=True)

    with c3:
        vix = vol.get("vix_current", 0)
        vc  = "#00ff88" if vix < 18 else "#ffaa00" if vix < 28 else "#ff4444"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">VIX</div>
            <div class="metric-value" style="color:{vc}">{vix:.1f}</div>
            <div class="metric-sub">{vol.get("volatility_regime","—").replace("_"," ")}</div>
        </div>""", unsafe_allow_html=True)

    with c4:
        ls = liq.get("liquidity_state","—")
        lc = "#00ff88" if ls=="INSTITUTIONAL" else "#ffaa00" if ls=="NORMAL" else "#ff4444"
        rvol = liq.get("relative_volume_spy", 0) or 0
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Liquidity</div>
            <div class="metric-value" style="color:{lc};font-size:18px">{ls}</div>
            <div class="metric-sub">RVOL: {rvol:.2f}x</div>
        </div>""", unsafe_allow_html=True)

    with c5:
        ip_c = "#00ff88" if inst_part >= 65 else "#ffaa00" if inst_part >= 45 else "#ff4444"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Institutional Part.</div>
            <div class="metric-value" style="color:{ip_c}">{inst_part:.0f}</div>
            <div class="metric-sub">out of 100</div>
        </div>""", unsafe_allow_html=True)

    # ── Regime Scores Bar ─────────────────────────────────────────
    regime_scores = regime.get("regime_scores", {})
    if regime_scores:
        st.markdown('<div class="section-header">REGIME SCORE BREAKDOWN</div>',
                    unsafe_allow_html=True)
        cols = st.columns(len(regime_scores))
        total = sum(regime_scores.values()) or 1
        for i, (r, s) in enumerate(
            sorted(regime_scores.items(), key=lambda x: x[1], reverse=True)
        ):
            pct   = s / total * 100
            color = REGIME_COLORS.get(r, "#888")
            with cols[i]:
                st.markdown(f"""
                <div style="text-align:center;padding:10px;background:#0d1117;
                            border-radius:8px;border:1px solid #21262d">
                    <div style="font-size:9px;color:#555;letter-spacing:2px">
                        {r.replace("_"," ")}
                    </div>
                    <div style="font-size:22px;font-weight:700;color:{color}">
                        {s:.0f}
                    </div>
                    <div style="font-size:10px;color:#555">{pct:.0f}%</div>
                </div>""", unsafe_allow_html=True)

    # ── AI Narrative ──────────────────────────────────────────────
    narrative = regime.get("ai_narrative", "")
    if narrative:
        st.markdown('<div class="section-header">🤖 AI NARRATIVE</div>',
                    unsafe_allow_html=True)
        st.markdown(f'<div class="narrative-box">"{narrative}"</div>',
                    unsafe_allow_html=True)

    st.divider()

    # ══════════════════════════════════════════════════════════════
    # SECTION 2 — SETUP SUITABILITY MATRIX
    # ══════════════════════════════════════════════════════════════
    st.markdown('<div class="section-header">⚡ SETUP SUITABILITY MATRIX</div>',
                unsafe_allow_html=True)

    suitability = regime.get("setup_suitability", {})
    best_setups = regime.get("best_setups", [])
    avoid_setups= regime.get("setups_to_avoid", [])

    if suitability:
        col_radar, col_table = st.columns([1, 1])

        with col_radar:
            st.plotly_chart(suitability_radar(suitability),
                            use_container_width=True)

        with col_table:
            st.markdown("**Setup Ratings:**")
            for setup, data_s in sorted(
                suitability.items(),
                key=lambda x: x[1]["score"], reverse=True
            ):
                score  = data_s["score"]
                rating = data_s["rating"]
                color  = RATING_COLORS.get(rating, "#888")
                bar_w  = int(score)
                st.markdown(f"""
                <div style="margin:6px 0;padding:8px 12px;background:#0d1117;
                            border-radius:6px;border-left:3px solid {color}">
                    <div style="display:flex;justify-content:space-between;
                                align-items:center">
                        <span style="font-size:12px;color:#c9d1d9">
                            {setup.replace("_"," ")}
                        </span>
                        <span style="font-size:11px;color:{color};font-weight:600">
                            {rating.replace("_"," ")} ({score:.0f})
                        </span>
                    </div>
                    <div style="background:#161b22;border-radius:4px;
                                height:4px;margin-top:4px">
                        <div style="background:{color};width:{bar_w}%;
                                    height:4px;border-radius:4px"></div>
                    </div>
                </div>""", unsafe_allow_html=True)

    # ── Best / Avoid ──────────────────────────────────────────────
    if best_setups or avoid_setups:
        col_b, col_a = st.columns(2)
        with col_b:
            st.markdown("**✅ Best Setups Now:**")
            pills = " ".join([
                f'<span class="setup-pill" '
                f'style="background:rgba(0,255,136,0.15);color:#00ff88;'
                f'border:1px solid #00ff8844">{s.replace("_"," ")}</span>'
                for s in best_setups
            ])
            st.markdown(pills, unsafe_allow_html=True)
        with col_a:
            st.markdown("**❌ Avoid Now:**")
            pills = " ".join([
                f'<span class="setup-pill" '
                f'style="background:rgba(255,50,50,0.15);color:#ff5555;'
                f'border:1px solid #ff333344">{s.replace("_"," ")}</span>'
                for s in avoid_setups
            ])
            st.markdown(pills, unsafe_allow_html=True)

    st.divider()

    # ══════════════════════════════════════════════════════════════
    # SECTION 3 — BREADTH INTELLIGENCE
    # ══════════════════════════════════════════════════════════════
    st.markdown('<div class="section-header">📊 BREADTH INTELLIGENCE</div>',
                unsafe_allow_html=True)

    col_g1, col_g2, col_g3 = st.columns(3)
    with col_g1:
        st.plotly_chart(
            gauge_chart(breadth.get("breadth_score", 0), "Breadth Score"),
            use_container_width=True
        )
    with col_g2:
        st.plotly_chart(
            gauge_chart(breadth.get("participation_score", 0),
                        "Participation Score", "#44aaff"),
            use_container_width=True
        )
    with col_g3:
        st.plotly_chart(
            gauge_chart(breadth.get("trend_quality_score", 0),
                        "Trend Quality", "#ffaa00"),
            use_container_width=True
        )

    # MA Analysis grid
    ma = breadth.get("ma_analysis", {})
    if ma:
        st.markdown("**ETF vs Moving Averages:**")
        cols = st.columns(6)
        for i, (etf, mdata) in enumerate(list(ma.items())[:12]):
            a20  = mdata.get("above_20ma",  False)
            a50  = mdata.get("above_50ma",  False)
            a200 = mdata.get("above_200ma", False)
            c    = "#00ff88" if (a20 and a50 and a200) else \
                   "#ffaa00" if (a20 or a50) else "#ff4444"
            with cols[i % 6]:
                st.markdown(f"""
                <div style="text-align:center;padding:8px;background:#0d1117;
                            border-radius:6px;margin:2px;border:1px solid #21262d">
                    <div style="font-size:12px;font-weight:600;color:{c}">{etf}</div>
                    <div style="font-size:9px;color:#555">
                        20:{'✅' if a20 else '❌'}
                        50:{'✅' if a50 else '❌'}
                        200:{'✅' if a200 else '❌'}
                    </div>
                </div>""", unsafe_allow_html=True)

    st.divider()

    # ══════════════════════════════════════════════════════════════
    # SECTION 4 — SECTOR ROTATION
    # ══════════════════════════════════════════════════════════════
    st.markdown('<div class="section-header">🌍 SECTOR ROTATION</div>',
                unsafe_allow_html=True)

    col_sr1, col_sr2 = st.columns([2, 1])

    with col_sr1:
        rankings = sector.get("sector_rankings", [])
        if rankings:
            st.plotly_chart(
                sector_bar_chart(sector.get("sector_data", {}), rankings),
                use_container_width=True
            )

    with col_sr2:
        rot_signal  = sector.get("rotation_signal", "—")
        mkt_char    = sector.get("market_character", "—")
        tech_lead   = sector.get("tech_leadership", False)
        semi_lead   = sector.get("semi_leadership", False)
        def_rot     = sector.get("defensive_rotation", False)
        off_rot     = sector.get("offensive_rotation", False)
        velocity    = sector.get("rotation_velocity", "—")
        leaders     = sector.get("leading_sectors", [])
        laggers     = sector.get("lagging_sectors", [])

        st.markdown(f"""
        <div style="background:#0d1117;border-radius:12px;padding:20px;
                    border:1px solid #21262d">
            <div style="font-size:10px;color:#555;letter-spacing:2px">SIGNAL</div>
            <div style="font-size:16px;font-weight:700;color:#44aaff;margin:4px 0">
                {rot_signal.replace("_"," ")}
            </div>
            <div style="font-size:10px;color:#555;margin-top:12px">CHARACTER</div>
            <div style="font-size:13px;color:#c9d1d9">{mkt_char.replace("_"," ")}</div>
            <div style="margin-top:12px;font-size:11px">
                {'🟢' if tech_lead else '🔴'} Tech Leadership<br>
                {'🟢' if semi_lead else '🔴'} Semi Leadership<br>
                {'🟡' if def_rot   else '⚪'} Defensive Rotation<br>
                {'🟢' if off_rot   else '⚪'} Offensive Rotation<br>
            </div>
            <div style="margin-top:12px;font-size:10px;color:#555">VELOCITY</div>
            <div style="font-size:12px;color:#ffaa00">{velocity}</div>
            <div style="margin-top:12px;font-size:10px;color:#555">LEADERS</div>
            <div style="font-size:12px;color:#00ff88">{" · ".join(leaders[:3])}</div>
            <div style="margin-top:8px;font-size:10px;color:#555">LAGGING</div>
            <div style="font-size:12px;color:#ff5555">{" · ".join(laggers[:3])}</div>
        </div>""", unsafe_allow_html=True)

    st.divider()

    # ══════════════════════════════════════════════════════════════
    # SECTION 5 — VOLATILITY + LIQUIDITY
    # ══════════════════════════════════════════════════════════════
    col_vol, col_liq = st.columns(2)

    with col_vol:
        st.markdown('<div class="section-header">⚡ VOLATILITY STATE</div>',
                    unsafe_allow_html=True)
        st.plotly_chart(vol_timeline_chart(vol), use_container_width=True)

        v_regime = vol.get("volatility_regime", "—")
        atr      = vol.get("atr_normalized", 0) or 0
        rv       = vol.get("realized_vol", 0) or 0
        rng      = vol.get("range_expansion", 0) or 0
        comp     = vol.get("compression_state", "—")
        exp_prob = vol.get("expansion_probability", 0)
        td_prob  = vol.get("trend_day_probability", 0)
        vix_pct  = vol.get("vix_percentile", 0)

        st.markdown(f"""
        <div style="background:#0d1117;border-radius:10px;padding:16px;
                    border:1px solid #21262d;font-size:12px">
            <table style="width:100%;color:#c9d1d9">
                <tr><td style="color:#555">Regime</td>
                    <td style="color:#44aaff;font-weight:600">
                    {v_regime.replace("_"," ")}</td></tr>
                <tr><td style="color:#555">ATR (norm)</td>
                    <td>{atr:.3f}%</td></tr>
                <tr><td style="color:#555">Realized Vol</td>
                    <td>{rv:.1f}%</td></tr>
                <tr><td style="color:#555">Range Expansion</td>
                    <td>{rng:.2f}x</td></tr>
                <tr><td style="color:#555">Compression</td>
                    <td style="color:{'#ffaa00' if comp=='COMPRESSING' else '#888'}">
                    {comp}</td></tr>
                <tr><td style="color:#555">VIX Percentile</td>
                    <td>{vix_pct:.0f}%</td></tr>
                <tr><td style="color:#555">Expansion Prob</td>
                    <td>{exp_prob:.0%}</td></tr>
                <tr><td style="color:#555">Trend Day Prob</td>
                    <td style="color:#00ff88">{td_prob:.0%}</td></tr>
            </table>
        </div>""", unsafe_allow_html=True)

        # Setup implications
        implications = vol.get("setup_implications", {})
        if implications:
            st.markdown("**Vol → Setup Implications:**")
            for setup, imp in implications.items():
                color = RATING_COLORS.get(imp, "#888")
                st.markdown(
                    f'<span style="font-size:11px;color:#555">'
                    f'{setup.replace("_"," ")}:</span> '
                    f'<span style="color:{color};font-weight:600">{imp}</span><br>',
                    unsafe_allow_html=True
                )

    with col_liq:
        st.markdown('<div class="section-header">💧 LIQUIDITY CONDITIONS</div>',
                    unsafe_allow_html=True)

        liq_state = liq.get("liquidity_state", "—")
        liq_score = liq.get("liquidity_score", 50)
        rvol_spy  = liq.get("relative_volume_spy", 0) or 0
        etf_part  = liq.get("etf_participation", 0) or 0
        open_p    = liq.get("opening_participation", 0) or 0
        close_p   = liq.get("closing_participation", 0) or 0
        dv        = liq.get("dollar_volume_spy", 0) or 0
        vol_trend = liq.get("volume_trend", "—")
        inst_sig  = liq.get("institutional_signal", False)
        panic_sig = liq.get("panic_signal", False)

        liq_color = RATING_COLORS.get(
            "HIGHLY_FAVORABLE" if liq_state=="INSTITUTIONAL" else
            "FAVORABLE"        if liq_state=="NORMAL"        else
            "REDUCED"          if liq_state=="THIN"          else
            "DANGEROUS", "#888"
        )

        st.plotly_chart(
            gauge_chart(liq_score, "Liquidity Score", liq_color),
            use_container_width=True
        )

        st.markdown(f"""
        <div style="background:#0d1117;border-radius:10px;padding:16px;
                    border:1px solid #21262d;font-size:12px">
            <table style="width:100%;color:#c9d1d9">
                <tr><td style="color:#555">State</td>
                    <td style="color:{liq_color};font-weight:600">
                    {liq_state}</td></tr>
                <tr><td style="color:#555">SPY RVOL</td>
                    <td>{rvol_spy:.2f}x</td></tr>
                <tr><td style="color:#555">ETF Participation</td>
                    <td>{etf_part:.0f}%</td></tr>
                <tr><td style="color:#555">Opening Part.</td>
                    <td>{open_p:.1f}%</td></tr>
                <tr><td style="color:#555">Closing Part.</td>
                    <td>{close_p:.1f}%</td></tr>
                <tr><td style="color:#555">Dollar Volume</td>
                    <td>${dv:.1f}B</td></tr>
                <tr><td style="color:#555">Volume Trend</td>
                    <td>{vol_trend}</td></tr>
                <tr><td style="color:#555">Institutional</td>
                    <td style="color:{'#00ff88' if inst_sig else '#555'}">
                    {'✅ YES' if inst_sig else '—'}</td></tr>
                <tr><td style="color:#555">Panic Signal</td>
                    <td style="color:{'#ff3333' if panic_sig else '#555'}">
                    {'🚨 YES' if panic_sig else '—'}</td></tr>
            </table>
        </div>""", unsafe_allow_html=True)

        # Per-ETF RVOL
        per_etf = liq.get("per_etf_rvol", {})
        if per_etf:
            st.markdown("**ETF Relative Volume:**")
            cols_etf = st.columns(4)
            for i, (etf, rv_val) in enumerate(per_etf.items()):
                rv_val = rv_val or 0
                color  = "#00ff88" if rv_val > 1.2 else \
                         "#ffaa00" if rv_val > 0.8 else "#ff4444"
                with cols_etf[i % 4]:
                    st.markdown(f"""
                    <div style="text-align:center;padding:6px;background:#0d1117;
                                border-radius:6px;margin:2px">
                        <div style="font-size:10px;color:#555">{etf}</div>
                        <div style="font-size:13px;font-weight:600;color:{color}">
                            {rv_val:.2f}x
                        </div>
                    </div>""", unsafe_allow_html=True)

    st.divider()

    # ══════════════════════════════════════════════════════════════
    # SECTION 6 — REGIME HISTORY
    # ══════════════════════════════════════════════════════════════
    if history:
        st.markdown('<div class="section-header">📈 REGIME HISTORY</div>',
                    unsafe_allow_html=True)
        st.plotly_chart(regime_history_chart(history),
                        use_container_width=True)

        # Recent regime table
        recent = history[-10:][::-1]
        st.markdown("**Recent Regime Changes:**")
        cols_h = st.columns([2, 2, 1, 2])
        cols_h[0].markdown("<small style='color:#555'>TIME</small>",
                           unsafe_allow_html=True)
        cols_h[1].markdown("<small style='color:#555'>REGIME</small>",
                           unsafe_allow_html=True)
        cols_h[2].markdown("<small style='color:#555'>CONF</small>",
                           unsafe_allow_html=True)
        cols_h[3].markdown("<small style='color:#555'>BEST SETUPS</small>",
                           unsafe_allow_html=True)
        for rec in recent:
            ts_str = rec.get("timestamp", "")[:16]
            r      = rec.get("regime", "—")
            c      = rec.get("confidence", 0)
            bs_r   = rec.get("best_setups", [])
            rc     = REGIME_COLORS.get(r, "#888")
            cols_r = st.columns([2, 2, 1, 2])
            cols_r[0].markdown(f"<small style='color:#555'>{ts_str}</small>",
                               unsafe_allow_html=True)
            cols_r[1].markdown(
                f"<small style='color:{rc};font-weight:600'>{r}</small>",
                unsafe_allow_html=True
            )
            cols_r[2].markdown(f"<small>{c:.0%}</small>",
                               unsafe_allow_html=True)
            cols_r[3].markdown(
                f"<small style='color:#555'>"
                f"{', '.join(bs_r[:2]).replace('_',' ')}</small>",
                unsafe_allow_html=True
            )

    # ── Footer ────────────────────────────────────────────────────
    st.divider()
    st.markdown(
        "<div style='text-align:center;color:#333;font-size:10px;"
        "letter-spacing:2px'>"
        "MINERVINI AI · INSTITUTIONAL INTELLIGENCE CENTER · "
        "ANALYTICS ONLY · PAPER MODE</div>",
        unsafe_allow_html=True,
    )

    # ── Auto Refresh ──────────────────────────────────────────────
    if auto_refresh:
        time.sleep(60)
        st.cache_data.clear()
        st.rerun()


if __name__ == "__main__":
    main()
