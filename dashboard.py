import time
#!/usr/bin/env python3
"""
Institutional AI Control Center
================================
Bloomberg-Style Trading Dashboard
"""

import streamlit as st
import json, os, sys
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import pytz

sys.path.insert(0, '/root')

# ===== Page Config =====
st.set_page_config(
    page_title="Minervini AI Control Center",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ===== Auto Refresh =====
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=30000, key="autorefresh")
except:
    pass

ET = pytz.timezone('America/New_York')

# ===== Dark Theme CSS =====
st.markdown("""
<style>
    .stApp { background-color: #0a0a0f; color: #e0e0e0; }
    .main { background-color: #0a0a0f; }
    div[data-testid="stMetricValue"] { font-size: 1.8rem; font-weight: bold; }
    .metric-card {
        background: #12121a;
        border: 1px solid #2a2a3a;
        border-radius: 8px;
        padding: 16px;
        margin: 4px;
    }
    .mode-aggressive { background: linear-gradient(135deg,#1a0a00,#2d1500); border:1px solid #ff6600; border-radius:8px; padding:20px; }
    .mode-swing      { background: linear-gradient(135deg,#001a0a,#002d15); border:1px solid #00cc66; border-radius:8px; padding:20px; }
    .mode-defensive  { background: linear-gradient(135deg,#1a001a,#2d002d); border:1px solid #cc0066; border-radius:8px; padding:20px; }
    .risk-on   { color: #00ff88; font-weight: bold; }
    .risk-off  { color: #ff4444; font-weight: bold; }
    .neutral   { color: #ffcc00; font-weight: bold; }
    .hot-row   { background-color: rgba(255,100,0,0.15); }
    .strong-row{ background-color: rgba(0,200,100,0.15); }
    .watch-row { background-color: rgba(255,200,0,0.15); }
    .section-header {
        font-size: 1.1rem;
        font-weight: bold;
        color: #7878ff;
        border-bottom: 1px solid #2a2a3a;
        padding-bottom: 8px;
        margin-bottom: 16px;
        letter-spacing: 1px;
    }
    .status-dot-green  { color: #00ff88; }
    .status-dot-red    { color: #ff4444; }
    .status-dot-yellow { color: #ffcc00; }
    h1, h2, h3 { color: #e0e0e0 !important; }
    .stDataFrame { background-color: #12121a; }
    footer { visibility: hidden; }
    #MainMenu { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ===== Helpers =====
def load_json(path, default={}):
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return default

def get_db_data():
    try:
        from database import fetch_recent_trades, fetch_recent_rejections, fetch_recent_snapshots
        return {
            "trades":     fetch_recent_trades(20),
            "rejections": fetch_recent_rejections(50),
            "snapshots":  fetch_recent_snapshots(10),
        }
    except:
        return {"trades": [], "rejections": [], "snapshots": []}

def get_orchestrator_state():
    try:
        cross  = load_json("/root/cross_asset_state.json", {})
        liq    = load_json("/root/liquidity_state.json",   {})
        psych  = load_json("/root/psychology_state.json",  {})
        event  = load_json("/root/event_state.json",       {"mode": "normal", "lockdown": False})
        macro  = load_json("/root/macro_state.json",       {})

        risk_score = 50
        cross_sig  = cross.get("cross_signal", "NEUTRAL")
        liq_reg    = liq.get("regime", "NEUTRAL")
        vix        = psych.get("vix", 20)
        spy_mom    = cross.get("risk_score", 50)

        if cross_sig == "RISK_ON":     risk_score += 20
        elif cross_sig == "RISK_OFF":  risk_score -= 20
        if liq_reg == "EXPANDING":     risk_score += 15
        elif liq_reg == "CONTRACTING": risk_score -= 15
        if vix < 18:                   risk_score += 10
        elif vix > 25:                 risk_score -= 15

        risk_score = max(0, min(100, risk_score))

        # Override with institutional regime
        try:
            import json as _j; _mi = _j.load(open("/root/market_intelligence.json"))
            from datetime import datetime as _dt
            if ((_dt.utcnow()-_dt.fromisoformat(_mi.get("timestamp","2000-01-01"))).total_seconds()/60) < 30:
                regime = _mi.get("regime_detail", "NEUTRAL")
        except: pass
        if risk_score >= 65:   regime = "RISK_ON"
        elif risk_score >= 40: regime = "NEUTRAL"
        else:                  regime = "RISK_OFF"

        lockdown = event.get("lockdown", False)
        if lockdown or vix > 30:
            mode = "DEFENSIVE"
        elif regime == "RISK_ON" and vix < 20:
            mode = "AGGRESSIVE_INTRADAY"
        elif regime in ["RISK_ON","NEUTRAL"]:
            mode = "SWING_FOCUS"
        else:
            mode = "DEFENSIVE"

        alloc = {
            "AGGRESSIVE_INTRADAY": {"Intraday": 60, "Swing": 40, "Cash": 0},
            "SWING_FOCUS":         {"Intraday": 20, "Swing": 80, "Cash": 0},
            "DEFENSIVE":           {"Intraday": 0,  "Swing": 20, "Cash": 80},
        }.get(mode, {"Intraday": 0, "Swing": 20, "Cash": 80})

        return {
            "mode":        mode,
            "regime":      regime,
            "risk_score":  risk_score,
            "vix":         vix,
            "lockdown":    lockdown,
            "liquidity":   liq_reg,
            "psychology":  psych.get("market_state", "NEUTRAL"),
            "cross_signal":cross_sig,
            "allocation":  alloc,
            "fear_score":  psych.get("fear_score", 50),
        }
    except Exception as e:
        return {"mode": "UNKNOWN", "regime": "NEUTRAL", "risk_score": 50,
                "vix": 20, "lockdown": False, "liquidity": "NEUTRAL",
                "psychology": "NEUTRAL", "cross_signal": "NEUTRAL",
                "allocation": {"Intraday": 0, "Swing": 20, "Cash": 80}, "fear_score": 50}

def get_alpaca_data():
    try:
        import requests
        from config import ALPACA_API_KEY, ALPACA_SECRET_KEY
        h = {"APCA-API-KEY-ID": ALPACA_API_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY}
        acc = requests.get("https://paper-api.alpaca.markets/v2/account",   headers=h, timeout=8).json()
        pos = requests.get("https://paper-api.alpaca.markets/v2/positions",  headers=h, timeout=8).json()
        return {"account": acc, "positions": pos if isinstance(pos, list) else []}
    except:
        return {"account": {}, "positions": []}

def get_confidence_scores():
    try:
        data = load_json("/root/confidence_scores.json", {})
        return data
    except:
        return {}

# ===========================================================
# HEADER
# ===========================================================
now_et = datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S ET")
st.markdown(f"""
<div style='background:#12121a;border-bottom:2px solid #2a2a3a;padding:12px 20px;margin-bottom:20px;'>
  <span style='font-size:1.4rem;font-weight:bold;color:#7878ff;'>📊 MINERVINI AI CONTROL CENTER</span>
  <span style='float:right;color:#666;font-size:0.85rem;'>🕐 {now_et} &nbsp;|&nbsp; Auto-refresh: 30s</span>
</div>
""", unsafe_allow_html=True)

# ===== Load Data =====
orch  = get_orchestrator_state()
# Institutional regime override
try:
    import json as _j3; from datetime import datetime as _dt3
    _mi3 = _j3.load(open("/root/market_intelligence.json"))
    _age3 = (_dt3.now()-_dt3.fromisoformat(_mi3.get("timestamp","2000-01-01"))).total_seconds()/60
    if _age3 < 30 and _mi3.get("regime_detail"): orch["regime"] = _mi3["regime_detail"]
except: pass
alpaca= get_alpaca_data()
db    = get_db_data()

account   = alpaca["account"]
positions = alpaca["positions"]

equity      = float(account.get("equity",       50000))
cash        = float(account.get("cash",         48000))
buying_power= float(account.get("buying_power", 48000))
pnl_today   = float(account.get("unrealized_pl",0)) if account else 0

# ===========================================================
# ROW 1: PORTFOLIO METRICS
# ===========================================================
c1,c2,c3,c4,c5 = st.columns(5)
with c1:
    st.metric("💼 Portfolio", f"${equity:,.2f}", delta=f"${pnl_today:+,.2f}")
with c2:
    st.metric("💵 Cash", f"${cash:,.2f}")
with c3:
    st.metric("📊 Positions", len(positions))
with c4:
    st.metric("😱 VIX", f"{orch['vix']:.1f}",
              delta="Low" if orch['vix'] < 18 else "High" if orch['vix'] > 25 else "Normal")
with c5:
    regime_color = "#00ff88" if orch['regime']=="RISK_ON" else "#ff4444" if orch['regime']=="RISK_OFF" else "#ffcc00"
    st.markdown(f"""
    <div style='background:#12121a;border:1px solid #2a2a3a;border-radius:8px;padding:12px;text-align:center;'>
      <div style='color:#888;font-size:0.75rem;'>REGIME</div>
      <div style='color:{regime_color};font-size:1.4rem;font-weight:bold;'>{orch['regime']}</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ===========================================================
# ROW 2: AI MODE + CAPITAL ALLOCATION + RISK
# ===========================================================
col_mode, col_alloc, col_risk = st.columns([2, 2, 2])

with col_mode:
    mode = orch["mode"]
    mode_css = {"AGGRESSIVE_INTRADAY":"mode-aggressive","SWING_FOCUS":"mode-swing","DEFENSIVE":"mode-defensive"}.get(mode,"mode-defensive")
    mode_emoji = {"AGGRESSIVE_INTRADAY":"🚀","SWING_FOCUS":"📈","DEFENSIVE":"🛡️"}.get(mode,"🤖")
    regime_cls = {"RISK_ON":"risk-on","RISK_OFF":"risk-off","NEUTRAL":"neutral"}.get(orch["regime"],"neutral")

    st.markdown(f"""
    <div class='{mode_css}'>
      <div class='section-header'>🧠 AI OPERATING MODE</div>
      <div style='font-size:1.6rem;font-weight:bold;margin-bottom:8px;'>{mode_emoji} {mode}</div>
      <div>Regime: <span class='{regime_cls}'>{orch['regime']}</span></div>
      <div style='margin-top:8px;'>
        <span style='color:#888;'>Risk Score: </span>
        <span style='color:#7878ff;font-weight:bold;'>{orch['risk_score']}/100</span>
      </div>
      {'<div style="color:#ff4444;margin-top:8px;">🔴 EVENT LOCKDOWN ACTIVE</div>' if orch['lockdown'] else ''}
    </div>""", unsafe_allow_html=True)

with col_alloc:
    st.markdown("<div class='section-header'>💰 CAPITAL ALLOCATION</div>", unsafe_allow_html=True)
    alloc = orch["allocation"]
    fig_alloc = go.Figure(go.Pie(
        labels=list(alloc.keys()),
        values=list(alloc.values()),
        hole=0.6,
        marker_colors=["#ff6600","#00cc66","#4444ff"],
        textinfo="label+percent",
        textfont_color="white",
    ))
    fig_alloc.update_layout(
        height=200, margin=dict(l=0,r=0,t=0,b=0),
        paper_bgcolor="#12121a", plot_bgcolor="#12121a",
        showlegend=False, font_color="white"
    )
    st.plotly_chart(fig_alloc, use_container_width=True, key=f"chart_1_{int(time.time()*1000) % 99999}")

with col_risk:
    st.markdown("<div class='section-header'>⚠️ RISK INTELLIGENCE</div>", unsafe_allow_html=True)

    def risk_dot(val, good, warn):
        if val == good:   return "🟢"
        if val == warn:   return "🟡"
        return "🔴"

    rows = [
        ("VIX Level",         f"{orch['vix']:.1f}", "🟢" if orch['vix']<18 else "🔴" if orch['vix']>25 else "🟡"),
        ("Liquidity",         orch['liquidity'],    "🟢" if orch['liquidity']=="EXPANDING" else "🔴" if orch['liquidity']=="CONTRACTING" else "🟡"),
        ("Psychology",        orch['psychology'],   "🟢" if orch['psychology'] in ["NEUTRAL","FEARFUL"] else "🔴" if orch['psychology']=="EUPHORIC" else "🟡"),
        ("Cross-Asset",       orch['cross_signal'], "🟢" if orch['cross_signal']=="RISK_ON" else "🔴" if orch['cross_signal']=="RISK_OFF" else "🟡"),
        ("Event Lockdown",    "YES" if orch['lockdown'] else "NO", "🔴" if orch['lockdown'] else "🟢"),
        ("Fear Score",        f"{orch['fear_score']}/100", "🟢" if orch['fear_score']<35 else "🔴" if orch['fear_score']>65 else "🟡"),
    ]
    for label, val, dot in rows:
        st.markdown(f"""
        <div style='display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #1a1a2a;'>
          <span style='color:#888;font-size:0.85rem;'>{label}</span>
          <span style='font-size:0.85rem;'>{dot} {val}</span>
        </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ===========================================================
# ROW 3: INTRADAY + SWING OPPORTUNITIES
# ===========================================================
col_intra, col_swing = st.columns(2)

with col_intra:
    st.markdown("<div class='section-header'>🔥 TOP INTRADAY OPPORTUNITIES</div>", unsafe_allow_html=True)
    try:
        from intraday_engine import scan_intraday_opportunities
        if st.button("🔄 Refresh Intraday Scan", key="intraday_btn"):
            with st.spinner("Scanning..."):
                intraday_results = scan_intraday_opportunities(
                    ["NVDA","AMD","TSLA","AAPL","META","MSFT","AVGO","SMCI","GOOGL","AMZN"]
                )
                st.session_state["intraday_results"] = intraday_results

        results = st.session_state.get("intraday_results", [])
        if results:
            df = pd.DataFrame([{
                "Symbol": r["symbol"], "Score": r["score"], "Rating": r["rating"],
                "Gap%": f"{r['gap_pct']:+.1f}", "Mom%": f"{r['momentum_pct']:+.1f}",
                "ATR": r.get("atr", 0), "SL": r.get("stop_loss", 0),
                "T1": r.get("target_1", 0), "Size": r.get("position_size", 0),
                "ORB": "✅" if r.get("orb_breakout") else "❌",
                "MTF": "✅" if r.get("mtf_alignment") else "❌",
            } for r in results[:8]])

            def color_rating(val):
                if val == "HOT":    return "background-color: rgba(255,100,0,0.3)"
                if val == "STRONG": return "background-color: rgba(0,200,100,0.2)"
                if val == "WATCH":  return "background-color: rgba(255,200,0,0.2)"
                return ""

            styled = df.style.applymap(color_rating, subset=["Rating"])
            st.dataframe(styled, use_container_width=True, height=280)
        else:
            st.info("Click 'Refresh Intraday Scan' to load opportunities")
    except Exception as e:
        st.error(f"Intraday engine error: {e}")

with col_swing:
    st.markdown("<div class='section-header'>📈 TOP SWING OPPORTUNITIES</div>", unsafe_allow_html=True)
    conf_scores = get_confidence_scores()

    swing_symbols = ["NVDA","MSFT","AAPL","GOOGL","AVGO","LLY","UNH","V","MA","JPM"]
    swing_data = []

    if conf_scores:
        for sym in swing_symbols:
            if sym in conf_scores:
                s = conf_scores[sym]
                swing_data.append({
                    "Symbol": sym,
                    "Score%": s.get("confidence", 0),
                    "Decision": s.get("decision", "N/A"),
                    "Regime": orch["regime"],
                })
    else:
        st.info("Loading swing signals...")

    if swing_data:
        df_swing = pd.DataFrame(swing_data)
        df_swing = df_swing.sort_values("Score%", ascending=False)
        st.dataframe(df_swing, use_container_width=True, height=280)

    # Recent DB Trades
    if db["trades"]:
        st.markdown("<div class='section-header' style='margin-top:12px;'>📋 RECENT TRADE LOGS</div>", unsafe_allow_html=True)
        df_trades = pd.DataFrame(db["trades"])[["symbol","rating","score","decision","market_regime","timestamp"]].head(5)
        st.dataframe(df_trades, use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)

# ===========================================================
# ROW 4: OPEN POSITIONS
# ===========================================================
st.markdown("<div class='section-header'>📊 OPEN POSITIONS</div>", unsafe_allow_html=True)
if positions:
    pos_data = []
    for p in positions:
        try:
            pos_data.append({
                "Symbol":   p.get("symbol",""),
                "Qty":      p.get("qty",""),
                "Entry":    f"${float(p.get('avg_entry_price',0)):.2f}",
                "Current":  f"${float(p.get('current_price',0)):.2f}",
                "P&L $":    f"${float(p.get('unrealized_pl',0)):+.2f}",
                "P&L %":    f"{float(p.get('unrealized_plpc',0))*100:+.2f}%",
                "Value":    f"${float(p.get('market_value',0)):,.2f}",
            })
        except: pass
    if pos_data:
        df_pos = pd.DataFrame(pos_data)
        st.dataframe(df_pos, use_container_width=True)
else:
    st.info("No open positions")

st.markdown("<br>", unsafe_allow_html=True)

# ===========================================================
# ROW 5: REJECTION ANALYTICS
# ===========================================================
st.markdown("<div class='section-header'>🔍 REJECTION ANALYTICS</div>", unsafe_allow_html=True)

col_rej1, col_rej2 = st.columns(2)

with col_rej1:
    # From DB
    if db["rejections"]:
        df_rej = pd.DataFrame(db["rejections"])
        if "reason" in df_rej.columns:
            reason_counts = df_rej["reason"].value_counts().head(10)
            fig_rej = go.Figure(go.Bar(
                x=reason_counts.values, y=reason_counts.index,
                orientation='h',
                marker_color="#7878ff",
                text=reason_counts.values,
                textposition="outside",
            ))
            fig_rej.update_layout(
                title="Top Rejection Reasons",
                height=300, margin=dict(l=0,r=40,t=30,b=0),
                paper_bgcolor="#12121a", plot_bgcolor="#12121a",
                font_color="white", xaxis_showgrid=False,
            )
            st.plotly_chart(fig_rej, use_container_width=True, key=f"chart_2_{int(time.time()*1000) % 99999}")
    else:
        # From trade_decisions.log
        try:
            import json as _json
            log_path = "/root/logs/trade_decisions.log"
            reasons = []
            if os.path.exists(log_path):
                with open(log_path) as f:
                    for line in f.readlines()[-200:]:
                        try:
                            entry = _json.loads(line)
                            if not entry.get("allowed"):
                                blocks = entry.get("blocks", [])
                                for b in blocks:
                                    reasons.append(b[:40] if len(b) > 40 else b)
                        except: pass

            if reasons:
                from collections import Counter
                cnt = Counter(reasons).most_common(8)
                fig_rej = go.Figure(go.Bar(
                    x=[v for _,v in cnt], y=[k for k,_ in cnt],
                    orientation='h', marker_color="#ff6644",
                ))
                fig_rej.update_layout(
                    title="Rejection Reasons (trade_decisions.log)",
                    height=300, margin=dict(l=0,r=20,t=30,b=0),
                    paper_bgcolor="#12121a", plot_bgcolor="#12121a",
                    font_color="white",
                )
                st.plotly_chart(fig_rej, use_container_width=True, key=f"chart_3_{int(time.time()*1000) % 99999}")
            else:
                st.info("No rejection data yet")
        except Exception as e:
            st.info(f"No rejection data: {e}")

with col_rej2:
    # Rejection by regime
    if db["rejections"]:
        df_rej2 = pd.DataFrame(db["rejections"])
        if "market_regime" in df_rej2.columns:
            regime_rej = df_rej2["market_regime"].value_counts()
            fig_pie = go.Figure(go.Pie(
                labels=regime_rej.index.tolist(),
                values=regime_rej.values.tolist(),
                hole=0.5,
                marker_colors=["#00ff88","#ffcc00","#ff4444","#7878ff"],
            ))
            fig_pie.update_layout(
                title="Rejections by Market Regime",
                height=300, margin=dict(l=0,r=0,t=30,b=0),
                paper_bgcolor="#12121a", plot_bgcolor="#12121a",
                font_color="white",
            )
            st.plotly_chart(fig_pie, use_container_width=True, key=f"chart_4_{int(time.time()*1000) % 99999}")
        else:
            st.info("Insufficient rejection data")
    else:
        # Allowed vs Rejected pie
        try:
            log_path = "/root/logs/trade_decisions.log"
            allowed = rejected = 0
            if os.path.exists(log_path):
                with open(log_path) as f:
                    for line in f.readlines()[-500:]:
                        try:
                            e = json.loads(line)
                            if e.get("allowed"): allowed += 1
                            else: rejected += 1
                        except: pass
            if allowed + rejected > 0:
                fig_pie = go.Figure(go.Pie(
                    labels=["Allowed","Rejected"],
                    values=[allowed, rejected],
                    hole=0.5,
                    marker_colors=["#00ff88","#ff4444"],
                ))
                fig_pie.update_layout(
                    title=f"Allow vs Reject ({allowed+rejected} decisions)",
                    height=300, margin=dict(l=0,r=0,t=30,b=0),
                    paper_bgcolor="#12121a", plot_bgcolor="#12121a",
                    font_color="white",
                )
                st.plotly_chart(fig_pie, use_container_width=True, key=f"chart_5_{int(time.time()*1000) % 99999}")
            else:
                st.info("No decision log data yet")
        except: st.info("No data yet")

st.markdown("<br>", unsafe_allow_html=True)

# ===========================================================
# ROW 6: MARKET SNAPSHOTS + SYSTEM STATUS
# ===========================================================
col_snap, col_sys = st.columns(2)

with col_snap:
    st.markdown("<div class='section-header'>📸 MARKET SNAPSHOTS</div>", unsafe_allow_html=True)
    if db["snapshots"]:
        df_snap = pd.DataFrame(db["snapshots"])[["timestamp","vix","market_regime","risk_on"]].head(8)
        st.dataframe(df_snap, use_container_width=True)
    else:
        macro = load_json("/root/macro_state.json", {})
        st.json({
            "action":   macro.get("action","N/A"),
            "score":    macro.get("score","N/A"),
            "warnings": macro.get("warnings",[]),
        })

with col_sys:
    st.markdown("<div class='section-header'>⚙️ SYSTEM STATUS</div>", unsafe_allow_html=True)
    import psutil

    def proc_running(name):
        import subprocess
        try:
            # Primary: psutil cmdline check
            for p in psutil.process_iter(['cmdline', 'pid']):
                try:
                    cmdline = " ".join(p.info['cmdline'] or [])
                    if name in cmdline:
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            # Fallback: pgrep
            result = subprocess.run(
                ['pgrep', '-f', name],
                capture_output=True, text=True
            )
            return result.returncode == 0
        except Exception:
            return False

    services = [
        ("auto_monitor",        "Trading Core"),
        ("ai_layer",            "Claude AI"),
        ("event_awareness",     "Event Guard"),
        ("institutional_layer", "Institutional"),
        ("master_orchestrator", "Orchestrator"),
        ("telegram_commands",   "Telegram Bot"),
        ("streamlit",           "Dashboard"),
        ("intraday_engine",     "Intraday Scanner"),
    ]
    for proc, name in services:
        status = proc_running(proc)
        dot = "🟢" if status else "🔴"
        st.markdown(f"""
        <div style='display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #1a1a2a;'>
          <span style='color:#ccc;'>{name}</span>
          <span>{dot} {'Running' if status else 'Stopped'}</span>
        </div>""", unsafe_allow_html=True)

    try:
        cpu  = psutil.cpu_percent(interval=1.0)
        ram  = psutil.virtual_memory().percent
        disk = psutil.disk_usage('/').percent
        st.markdown(f"""
        <div style='margin-top:12px;padding:8px;background:#1a1a2a;border-radius:6px;text-align:center;'>
          💻 CPU: {cpu}% &nbsp;|&nbsp; RAM: {ram}% &nbsp;|&nbsp; Disk: {disk}%
        </div>""", unsafe_allow_html=True)
    except: pass

# ===========================================================
# FOOTER
# ===========================================================
st.markdown(f"""
<div style='text-align:center;color:#444;font-size:0.75rem;margin-top:30px;border-top:1px solid #1a1a2a;padding-top:10px;'>
  Minervini AI Control Center &nbsp;|&nbsp; Intelligence Only — No Auto Trading &nbsp;|&nbsp; {now_et}
</div>
""", unsafe_allow_html=True)

# 
# TRADE CENTER TAB
# 
try:
    import sys
    sys.path.insert(0, '/root')
    from trade_center import render_trade_center
    with st.expander(" TRADE CENTER", expanded=True):
        render_trade_center()
except Exception as e:
    st.error(f"Trade Center: {e}")

# INSTITUTIONAL INTELLIGENCE
try:
    from institutional_intelligence_dashboard import render_institutional_intelligence
    with st.expander(" INSTITUTIONAL INTELLIGENCE", expanded=False):
        render_institutional_intelligence()
except Exception as e:
    st.error(f"Intelligence: {e}")
try:
    from paper_performance_dashboard import render_paper_performance
    with st.expander(" PAPER TRADING PERFORMANCE", expanded=False):
        render_paper_performance()
except Exception as e:
    st.error(f"Paper: {e}")
# =========================================================
# PERFORMANCE ANALYTICS
# =========================================================
try:
    from performance_dashboard import render_performance_dashboard
    with st.expander("PERFORMANCE ANALYTICS", expanded=False):
        render_performance_dashboard()
except Exception as e:
    st.error(f"Performance: {e}")
# =========================================================
# PORTFOLIO INTELLIGENCE
# =========================================================

try:
    from performance_dashboard import render_performance_dashboard
    with st.expander("PERFORMANCE ANALYTICS", expanded=False):
        render_performance_dashboard()
except Exception as e:
    st.error(f"Performance: {e}")
try:
    from portfolio_dashboard import render_portfolio_dashboard
    with st.expander("PORTFOLIO INTELLIGENCE", expanded=False):
        render_portfolio_dashboard()
except Exception as e:
    st.error(f"Portfolio: {e}")
try:
    from health_dashboard import render_health_dashboard
    with st.expander("SYSTEM HEALTH", expanded=False):
        render_health_dashboard()
except Exception as e:
    st.error(f"Health: {e}")
