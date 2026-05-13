#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║   MINERVINI AI — ADAPTIVE INTELLIGENCE DASHBOARD                 ║
║   Streamlit — Human Governance & Learning Monitor                ║
║   Run: streamlit run /root/adaptive_dashboard.py --server.port 8503
╚══════════════════════════════════════════════════════════════════╝
"""

import streamlit as st
import json
import os
import sys
import subprocess
import pandas as pd
import numpy as np
from datetime import datetime

sys.path.insert(0, "/root")

# ── Page Config ───────────────────────────────────────────────────
st.set_page_config(
    page_title="Minervini AI — Adaptive Intelligence",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Styles ────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Sora:wght@300;400;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Sora', sans-serif; }
.stApp { background: #060b14; color: #b8c5d6; }

.level-badge {
    display: inline-block; padding: 2px 12px; border-radius: 20px;
    font-size: 11px; font-weight: 700; font-family: 'JetBrains Mono', monospace;
}
.level-1 { background: #0f3a1e; color: #4ade80; border: 1px solid #16a34a; }
.level-2 { background: #3a2a0f; color: #fbbf24; border: 1px solid #d97706; }
.level-3 { background: #3a0f0f; color: #f87171; border: 1px solid #dc2626; }

.metric-box {
    background: #0d1420; border: 1px solid #1a2535;
    border-radius: 10px; padding: 18px 22px; margin: 4px 0;
}
.metric-val {
    font-family: 'JetBrains Mono', monospace;
    font-size: 30px; font-weight: 600; color: #60a5fa;
}
.metric-lbl {
    font-size: 10px; text-transform: uppercase;
    letter-spacing: 1.5px; color: #4a5568; margin-top: 4px;
}
.positive { color: #22c55e !important; }
.negative { color: #ef4444 !important; }
.neutral  { color: #f59e0b !important; }

.section-hdr {
    font-family: 'JetBrains Mono', monospace; font-size: 10px;
    text-transform: uppercase; letter-spacing: 2.5px; color: #60a5fa;
    border-bottom: 1px solid #1a2535; padding-bottom: 8px; margin: 28px 0 14px;
}
.approval-card {
    background: #0f1f0f; border: 1px solid #16a34a;
    border-radius: 8px; padding: 16px; margin: 10px 0;
}
.pending-card {
    background: #1f1500; border: 1px solid #d97706;
    border-radius: 8px; padding: 16px; margin: 10px 0;
}
.narrative-box {
    background: #0a1020; border-left: 3px solid #60a5fa;
    border-radius: 4px; padding: 16px 20px; font-size: 14px;
    line-height: 1.75; color: #8899aa; margin: 10px 0;
}
.finding  { background:#0a1f0a; border-left:3px solid #22c55e; padding:8px 14px; border-radius:4px; margin:5px 0; }
.issue    { background:#1f0a0a; border-left:3px solid #ef4444; padding:8px 14px; border-radius:4px; margin:5px 0; }
.rec-box  { background:#1a1500; border-left:3px solid #f59e0b; padding:12px 16px; border-radius:4px; margin:8px 0; }
.warn-banner {
    background:#1a0a00; border:1px solid #f59e0b; border-radius:6px;
    padding:10px 16px; font-size:11px; color:#fbbf24; text-align:center;
    font-family:'JetBrains Mono',monospace; margin-bottom:18px;
}
.rollback-zone {
    background:#1f0505; border:2px solid #7f1d1d;
    border-radius:10px; padding:20px; margin-top:20px;
}
</style>
""", unsafe_allow_html=True)

# ── Data Loaders ──────────────────────────────────────────────────
@st.cache_data(ttl=20)
def load_memory_module():
    try:
        import adaptive_memory as m
        return m
    except Exception:
        return None

@st.cache_data(ttl=20)
def _load_weights():
    try:
        import adaptive_memory as m
        return m.load_weights()
    except Exception:
        return {}

@st.cache_data(ttl=20)
def _load_setup_stats():
    try:
        import adaptive_memory as m
        return m.get_setup_stats()
    except Exception:
        return {}

@st.cache_data(ttl=20)
def _load_regime_perf():
    try:
        import adaptive_memory as m
        return m.get_regime_perf()
    except Exception:
        return {}

@st.cache_data(ttl=20)
def _load_changes():
    try:
        import adaptive_memory as m
        return m.get_changes(50)
    except Exception:
        return []

@st.cache_data(ttl=20)
def _load_pending():
    try:
        import adaptive_memory as m
        return m.get_pending_approvals()
    except Exception:
        return []

@st.cache_data(ttl=20)
def _load_history():
    try:
        import adaptive_memory as m
        return m.get_learning_history(20)
    except Exception:
        return []

@st.cache_data(ttl=20)
def _load_narrative():
    try:
        import adaptive_memory as m
        return m.get_latest_narrative()
    except Exception:
        return {}

@st.cache_data(ttl=20)
def _load_confidence_history():
    try:
        import adaptive_memory as m
        return m.get_confidence_history(100)
    except Exception:
        return []

def _metric(label, value, cls=""):
    st.markdown(f"""
    <div class="metric-box">
        <div class="metric-val {cls}">{value}</div>
        <div class="metric-lbl">{label}</div>
    </div>""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🧠 Adaptive Intelligence")
    st.markdown('<div class="warn-banner">⚠ CONTROLLED ADAPTATION<br>PAPER MODE ONLY</div>',
                unsafe_allow_html=True)

    st.markdown("### Quick Actions")

    if st.button("▶ Run Learning Cycle", use_container_width=True):
        with st.spinner("Running..."):
            try:
                r = subprocess.run(
                    [sys.executable, "/root/adaptive_learning.py", "--mode", "once"],
                    capture_output=True, text=True, timeout=120,
                )
                st.cache_data.clear()
                st.success("✔ Learning cycle complete!")
            except Exception as e:
                st.error(f"Error: {e}")

    if st.button("📊 Generate Suggestions", use_container_width=True):
        with st.spinner("Analyzing..."):
            try:
                import adaptive_scoring as sc
                suggestions = sc.generate_level2_suggestions()
                st.cache_data.clear()
                st.success(f"✔ {len(suggestions)} suggestions generated")
            except Exception as e:
                st.error(f"Error: {e}")

    if st.button("🔍 Stability Check", use_container_width=True):
        try:
            import adaptive_review_engine as rev
            result = rev.check_stability()
            st.cache_data.clear()
            if result["stable"]:
                st.success("✔ All weights stable")
            else:
                for issue in result["issues"]:
                    st.warning(issue)
        except Exception as e:
            st.error(f"Error: {e}")

    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    # Rollback Zone
    st.markdown('<div class="rollback-zone">', unsafe_allow_html=True)
    st.markdown("### ⚠ Emergency Rollback")
    st.caption("Resets ALL adaptive weights to factory defaults")
    if st.button("🔴 ROLLBACK TO DEFAULTS", use_container_width=True, type="primary"):
        try:
            import adaptive_review_engine as rev
            result = rev.rollback_no_confirm()
            if result:
                st.cache_data.clear()
                st.success("✔ Weights reset to defaults!")
            else:
                st.error("Rollback failed")
        except Exception as e:
            st.error(f"Error: {e}")
    st.markdown('</div>', unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────
st.markdown("# 🧠 Adaptive Intelligence Center")
st.markdown('<div class="warn-banner">CONTROLLED ADAPTATION — LEVEL 1 AUTO · LEVEL 2 SUGGESTED · LEVEL 3 PROTECTED · PAPER ONLY</div>',
            unsafe_allow_html=True)

# ── Load Data ─────────────────────────────────────────────────────
weights     = _load_weights()
setup_stats = _load_setup_stats()
regime_perf = _load_regime_perf()
changes     = _load_changes()
pending     = _load_pending()
history     = _load_history()
narrative   = _load_narrative()
conf_hist   = _load_confidence_history()

# ── Tabs ──────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Overview",
    "⚡ Setup Learning",
    "🌍 Regime Intelligence",
    "📋 Approvals & Changes",
    "🤖 AI Narrative",
    "🔬 Deep Analytics",
])

# ══════════════════════════════════════════════════════════════════
# TAB 1: OVERVIEW
# ══════════════════════════════════════════════════════════════════
with tab1:
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        _metric("Weights Version", f"v{weights.get('version', 1)}")
    with c2:
        _metric("Setups Tracked", str(len(setup_stats)))
    with c3:
        _metric("Pending Approvals", str(len(pending)),
                "neutral" if pending else "positive")
    with c4:
        _metric("Learning Cycles", str(len(history)))
    with c5:
        _metric("Auto Changes", str(len([c for c in changes if c.get("auto_applied")])))

    # Adaptation Levels
    st.markdown('<div class="section-hdr">Adaptation Architecture</div>',
                unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        <div style="background:#0a1f0a;border:1px solid #16a34a;border-radius:10px;padding:16px">
        <span class="level-badge level-1">LEVEL 1 — AUTO</span>
        <div style="margin-top:12px;font-size:13px;color:#86efac">
        ✅ Setup modifier tuning<br>
        ✅ Regime aggressiveness<br>
        ✅ Confidence weighting<br>
        ✅ Setup ranking<br><br>
        <b style="color:#4ade80">No approval needed</b>
        </div></div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div style="background:#1f1500;border:1px solid #d97706;border-radius:10px;padding:16px">
        <span class="level-badge level-2">LEVEL 2 — SUGGESTED</span>
        <div style="margin-top:12px;font-size:13px;color:#fcd34d">
        📋 Threshold recommendations<br>
        📋 Sizing suggestions<br>
        📋 Aggressiveness calibration<br>
        📋 Regime-specific tuning<br><br>
        <b style="color:#f59e0b">Requires your approval</b>
        </div></div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown("""
        <div style="background:#1f0505;border:1px solid #dc2626;border-radius:10px;padding:16px">
        <span class="level-badge level-3">LEVEL 3 — PROTECTED</span>
        <div style="margin-top:12px;font-size:13px;color:#fca5a5">
        🔒 Stop loss architecture<br>
        🔒 Portfolio protection<br>
        🔒 Kill switch logic<br>
        🔒 Core risk engine<br><br>
        <b style="color:#ef4444">NEVER modified</b>
        </div></div>
        """, unsafe_allow_html=True)

    # Learning History Chart
    if history:
        st.markdown('<div class="section-hdr">Learning Progress</div>',
                    unsafe_allow_html=True)
        hist_df = pd.DataFrame(history)
        if "trades_analyzed" in hist_df.columns:
            hist_df["trades_analyzed"] = pd.to_numeric(
                hist_df["trades_analyzed"], errors="coerce").fillna(0)
            st.area_chart(hist_df["trades_analyzed"].tail(20),
                          color="#60a5fa", height=150)

# ══════════════════════════════════════════════════════════════════
# TAB 2: SETUP LEARNING
# ══════════════════════════════════════════════════════════════════
with tab2:
    if setup_stats:
        st.markdown('<div class="section-hdr">Setup Performance & Adaptive Modifiers</div>',
                    unsafe_allow_html=True)

        rows = []
        setup_mods = weights.get("setup_modifiers", {})
        for setup, data in setup_stats.items():
            total = data.get("total", 0)
            if total == 0:
                continue
            wr  = data.get("wins", 0) / total * 100
            pnl = data.get("total_pnl", 0)
            mod = setup_mods.get(setup, 1.0)
            rows.append({
                "Setup":      setup,
                "Trades":     total,
                "Win Rate %": round(wr, 1),
                "Total PnL %":round(pnl, 2),
                "Avg PnL %":  round(pnl / total, 2),
                "Modifier":   round(mod, 3),
                "Status":     "↑ Boosted" if mod > 1.01 else "↓ Reduced" if mod < 0.99 else "= Neutral",
            })

        df = pd.DataFrame(rows).sort_values("Win Rate %", ascending=False)

        col1, col2 = st.columns([3, 2])
        with col1:
            st.dataframe(df, use_container_width=True, height=350,
                         column_config={
                             "Win Rate %":  st.column_config.NumberColumn(format="%.1f%%"),
                             "Total PnL %": st.column_config.NumberColumn(format="%+.2f%%"),
                             "Avg PnL %":   st.column_config.NumberColumn(format="%+.2f%%"),
                             "Modifier":    st.column_config.NumberColumn(format="%.3f"),
                         })
        with col2:
            if len(df) > 0:
                st.bar_chart(df.set_index("Setup")["Win Rate %"],
                             color="#22c55e", height=350)

    # Confidence History
    if conf_hist:
        st.markdown('<div class="section-hdr">Modifier Evolution</div>',
                    unsafe_allow_html=True)
        ch_df = pd.DataFrame(conf_hist)
        if "new_value" in ch_df.columns and "setup" in ch_df.columns:
            pivot = ch_df.pivot_table(
                index=ch_df.index, columns="setup",
                values="new_value", aggfunc="last"
            ).fillna(method="ffill")
            st.line_chart(pivot, height=200)
    else:
        st.info("Run learning cycles to see modifier evolution")

# ══════════════════════════════════════════════════════════════════
# TAB 3: REGIME INTELLIGENCE
# ══════════════════════════════════════════════════════════════════
with tab3:
    if regime_perf:
        st.markdown('<div class="section-hdr">Regime Performance</div>',
                    unsafe_allow_html=True)

        regime_aggr   = weights.get("regime_aggressiveness", {})
        sizing_mods   = weights.get("sizing_modifiers", {})
        conf_floors   = weights.get("confidence_floor", {})

        cols = st.columns(len(regime_perf))
        for i, (regime, data) in enumerate(regime_perf.items()):
            with cols[i]:
                total = data.get("total", 0)
                wr    = (data.get("wins", 0) / total * 100) if total > 0 else 0
                cls   = "positive" if wr >= 55 else "negative" if wr < 45 else "neutral"
                _metric(regime, f"{wr:.1f}%", cls)
                st.caption(
                    f"Trades: {total} | PnL: {data.get('total_pnl', 0):+.1f}%\n"
                    f"Aggr: {regime_aggr.get(regime, 1.0):.2f}x | "
                    f"Size: {sizing_mods.get(regime, 1.0):.2f}x | "
                    f"Floor: {conf_floors.get(regime, 0.65):.2f}"
                )

        # Regime table
        rows = []
        for regime, data in regime_perf.items():
            total = data.get("total", 0)
            rows.append({
                "Regime":      regime,
                "Trades":      total,
                "Win Rate %":  round(data.get("wins", 0) / max(total, 1) * 100, 1),
                "Total PnL %": round(data.get("total_pnl", 0), 2),
                "Aggressiveness": round(regime_aggr.get(regime, 1.0), 3),
                "Sizing Mod":  round(sizing_mods.get(regime, 1.0), 3),
                "Conf Floor":  round(conf_floors.get(regime, 0.65), 3),
            })
        reg_df = pd.DataFrame(rows)
        st.dataframe(reg_df, use_container_width=True)

    else:
        st.info("No regime data yet. Run learning cycles to build regime intelligence.")

# ══════════════════════════════════════════════════════════════════
# TAB 4: APPROVALS & CHANGES
# ══════════════════════════════════════════════════════════════════
with tab4:
    # Pending Approvals (Level 2)
    st.markdown('<div class="section-hdr">Pending Approvals (Level 2)</div>',
                unsafe_allow_html=True)

    if pending:
        for p in pending:
            with st.container():
                st.markdown(f"""
                <div class="pending-card">
                <b>{p['title']}</b>
                <span class="level-badge level-2" style="float:right">LEVEL {p.get('level',2)}</span><br>
                <small style="color:#9ca3af">{p['timestamp'][:16]} | ID: {p['id']}</small><br><br>
                {p['description']}<br><br>
                <code>{json.dumps(p.get('proposed_change', {}))}</code>
                </div>
                """, unsafe_allow_html=True)

                col1, col2, _ = st.columns([1, 1, 4])
                with col1:
                    if st.button(f"✅ Approve", key=f"apr_{p['id']}"):
                        try:
                            import adaptive_memory as m
                            m.approve_change(p["id"])
                            st.cache_data.clear()
                            st.success("Approved!")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
                with col2:
                    if st.button(f"❌ Reject", key=f"rej_{p['id']}"):
                        try:
                            import adaptive_memory as m
                            m.reject_change(p["id"])
                            st.cache_data.clear()
                            st.success("Rejected")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
    else:
        st.success("✔ No pending approvals")

    # Recent Changes Log
    st.markdown('<div class="section-hdr">Recent Adaptive Changes</div>',
                unsafe_allow_html=True)

    if changes:
        ch_df = pd.DataFrame(changes)[
            ["timestamp", "type", "description", "component",
             "auto_applied", "level", "status"]
        ].sort_values("timestamp", ascending=False)

        st.dataframe(ch_df, use_container_width=True, height=350,
                     column_config={
                         "auto_applied": st.column_config.CheckboxColumn("Auto"),
                         "timestamp":    st.column_config.TextColumn("Time"),
                     })
    else:
        st.info("No adaptive changes yet")

# ══════════════════════════════════════════════════════════════════
# TAB 5: AI NARRATIVE
# ══════════════════════════════════════════════════════════════════
with tab5:
    st.markdown('<div class="section-hdr">Latest AI Narrative</div>',
                unsafe_allow_html=True)

    if narrative:
        n = narrative.get("narrative", narrative)
        ts = narrative.get("timestamp", "")
        src = narrative.get("source", "")

        st.caption(f"Generated: {ts[:16]} | Source: {src}")

        if isinstance(n, dict):
            headline = n.get("headline", "")
            if headline:
                st.markdown(f'<div class="narrative-box">📊 <b>{headline}</b></div>',
                            unsafe_allow_html=True)

            col1, col2 = st.columns(2)
            with col1:
                setup_n = n.get("setup_narrative", "")
                if setup_n:
                    st.markdown("**Setup Intelligence**")
                    st.markdown(f'<div class="finding">{setup_n}</div>',
                                unsafe_allow_html=True)

                missed_n = n.get("missed_narrative", "")
                if missed_n:
                    st.markdown("**Missed Opportunities**")
                    st.markdown(f'<div class="issue">{missed_n}</div>',
                                unsafe_allow_html=True)

            with col2:
                regime_n = n.get("regime_narrative", "")
                if regime_n:
                    st.markdown("**Regime Intelligence**")
                    st.markdown(f'<div class="finding">{regime_n}</div>',
                                unsafe_allow_html=True)

                rec = n.get("recommendation", "")
                if rec:
                    st.markdown("**Recommendation**")
                    st.markdown(f'<div class="rec-box">💡 {rec}</div>',
                                unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="narrative-box">{n}</div>',
                        unsafe_allow_html=True)
    else:
        st.info("Run a learning cycle to generate AI narrative")

    # Narrative History
    st.markdown('<div class="section-hdr">Narrative History</div>',
                unsafe_allow_html=True)
    try:
        import adaptive_memory as m
        all_narratives = m._read(m.PATHS["narratives"], [])
        if all_narratives:
            for narr in reversed(all_narratives[-5:]):
                n = narr.get("narrative", {})
                ts = narr.get("timestamp", "")
                headline = n.get("headline", str(n)[:80]) if isinstance(n, dict) else str(n)[:80]
                st.caption(f"📅 {ts[:16]} — {headline}")
    except Exception:
        pass

# ══════════════════════════════════════════════════════════════════
# TAB 6: DEEP ANALYTICS
# ══════════════════════════════════════════════════════════════════
with tab6:
    col1, col2 = st.columns(2)

    with col1:
        # Current Weights
        st.markdown('<div class="section-hdr">Current Weights (Level 1)</div>',
                    unsafe_allow_html=True)
        setup_mods = weights.get("setup_modifiers", {})
        if setup_mods:
            mod_df = pd.DataFrame(
                [(k, round(v, 4), "↑" if v > 1.01 else "↓" if v < 0.99 else "=")
                 for k, v in setup_mods.items()],
                columns=["Setup", "Modifier", "Dir"]
            )
            st.dataframe(mod_df, use_container_width=True)

        # Safety limits reference
        st.markdown('<div class="section-hdr">Safety Limits</div>',
                    unsafe_allow_html=True)
        try:
            import adaptive_memory as m
            limits_df = pd.DataFrame(
                list(m.SAFETY_LIMITS.items()),
                columns=["Limit", "Value"]
            )
            st.dataframe(limits_df, use_container_width=True)
        except Exception:
            pass

    with col2:
        # Learning history
        st.markdown('<div class="section-hdr">Learning Cycle History</div>',
                    unsafe_allow_html=True)
        if history:
            hist_df = pd.DataFrame(history)[
                ["timestamp", "source", "trades_analyzed", "changes_made", "summary"]
            ].sort_values("timestamp", ascending=False)
            st.dataframe(hist_df, use_container_width=True, height=300)

        # Memory status
        st.markdown('<div class="section-hdr">Memory Status</div>',
                    unsafe_allow_html=True)
        try:
            import adaptive_memory as m
            status = m.get_memory_status()
            status_df = pd.DataFrame(
                [(k, str(v)) for k, v in status.items() if k != "files"],
                columns=["Key", "Value"]
            )
            st.dataframe(status_df, use_container_width=True)
        except Exception:
            st.info("Memory module not available")

# ── Footer ────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("""
<div style='text-align:center;color:#1e293b;font-size:10px;font-family:JetBrains Mono,monospace'>
MINERVINI AI · ADAPTIVE INTELLIGENCE CENTER · CONTROLLED ADAPTATION · PAPER MODE ONLY
</div>""", unsafe_allow_html=True)
