#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║   MINERVINI AI — HISTORICAL REPLAY DASHBOARD TAB                 ║
║   Add to adaptive_dashboard.py as new tab                        ║
║   Run standalone: streamlit run replay_dashboard_tab.py          ║
╚══════════════════════════════════════════════════════════════════╝
"""

import streamlit as st
import json
import os
import sys
import subprocess
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

sys.path.insert(0, "/root")

# ── Standalone Config ─────────────────────────────────────────────
_STANDALONE = __name__ == "__main__"

if _STANDALONE:
    st.set_page_config(
        page_title="Minervini AI — Historical Replay",
        page_icon="📈",
        layout="wide",
    )
    st.markdown("""
    <style>
    .stApp { background: #060b14; color: #b8c5d6; }
    .section-header {
        font-size:11px; text-transform:uppercase; letter-spacing:2px;
        color:#60a5fa; border-bottom:1px solid #1a2535;
        padding-bottom:8px; margin:20px 0 12px;
    }
    </style>
    """, unsafe_allow_html=True)

# ── Paths ─────────────────────────────────────────────────────────
MEMORY_DIR   = "/root/adaptive/memory"
ADAPTIVE_DIR = "/root/adaptive"

PATHS = {
    "library":    f"{MEMORY_DIR}/setup_library.json",
    "expectancy": f"{MEMORY_DIR}/setup_expectancy.json",
    "rankings":   f"{MEMORY_DIR}/historical_rankings.json",
    "regime":     f"{MEMORY_DIR}/regime_performance.json",
    "progress":   f"{MEMORY_DIR}/replay_progress.json",
    "daemon":     f"{ADAPTIVE_DIR}/daemon.log",
    "state":      f"{MEMORY_DIR}/daemon_state.json",
    "suggestions":f"{MEMORY_DIR}/adaptive_suggestions.json",
    "evolution":  f"{MEMORY_DIR}/confidence_evolution.json",
    "summary":    f"{MEMORY_DIR}/memory_summary.json",
}

# ── Loaders ───────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def _load(path: str, default=None):
    if default is None:
        default = {}
    try:
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    except Exception:
        pass
    return default

def _load_list(path: str) -> list:
    data = _load(path, [])
    return data if isinstance(data, list) else [data]

# ── Main Render Function ──────────────────────────────────────────
def render_replay_tab():
    """Call this from adaptive_dashboard.py"""

    library     = _load(PATHS["library"],    {})
    expectancy  = _load(PATHS["expectancy"], {})
    rankings    = _load(PATHS["rankings"],   {})
    regime_perf = _load(PATHS["regime"],     {})
    state       = _load(PATHS["state"],      {})
    summary     = _load(PATHS["summary"],    {})
    suggestions = _load_list(PATHS["suggestions"])
    evolution   = _load_list(PATHS["evolution"])
    progress    = _load_list(PATHS["progress"])

    total_trades = sum(v.get("total_trades", 0) for v in library.values())
    phase        = summary.get("phase", "PHASE_0_INITIALIZING")

    # ── Warning Banner ────────────────────────────────────────────
    st.markdown("""
    <div style='background:#0a1f00;border:1px solid #22c55e;border-radius:6px;
    padding:8px 16px;font-size:11px;color:#4ade80;text-align:center;margin-bottom:16px;
    font-family:monospace;'>
    📚 HISTORICAL LEARNING — ADVISORY ONLY — NO LIVE TRADING — LOW CPU PRIORITY
    </div>""", unsafe_allow_html=True)

    # ── Phase Progress ────────────────────────────────────────────
    st.markdown("<div class='section-header'>🚀 LEARNING PHASE PROGRESS</div>",
                unsafe_allow_html=True)

    phases = [
        ("PHASE_0_INITIALIZING", 0,    50,   "🔵 Initializing"),
        ("PHASE_1_BOOTSTRAP",    50,   500,  "🟡 Bootstrap"),
        ("PHASE_2_ADVANCED",     500,  5000, "🟠 Advanced"),
        ("PHASE_3_MULTI_REGIME", 5000, 9999, "🟢 Institutional"),
    ]

    col_phases = st.columns(4)
    for i, (ph, min_t, max_t, label) in enumerate(phases):
        with col_phases[i]:
            is_current = phase == ph
            pct = min(100, (total_trades - min_t) / max(max_t - min_t, 1) * 100) if total_trades >= min_t else 0
            border = "#22c55e" if is_current else "#1a2535"
            st.markdown(f"""
            <div style='background:#0d1420;border:2px solid {border};border-radius:8px;padding:12px;text-align:center;'>
            <div style='font-size:11px;color:#64748b;'>{label}</div>
            <div style='font-size:20px;font-weight:bold;color:{"#22c55e" if is_current else "#4a5568"};'>
            {min_t}–{max_t}</div>
            <div style='font-size:10px;color:#94a3b8;'>trades</div>
            {"<div style='color:#22c55e;font-size:11px;margin-top:4px;'>▶ CURRENT</div>" if is_current else ""}
            </div>""", unsafe_allow_html=True)

    # ── Key Metrics ───────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        st.metric("📊 Setups Tracked",   total_trades,
                  delta=f"+{progress[-1].get('total_trades',0)}" if progress else None)
    with c2:
        st.metric("🎯 Setup Types",      len([v for v in library.values() if v.get("total_trades", 0) >= 5]))
    with c3:
        st.metric("🌍 Regimes Mapped",   len(regime_perf))
    with c4:
        cycles = state.get("total_cycles", 0)
        st.metric("🔄 Replay Cycles",    cycles)
    with c5:
        best = summary.get("best_setup", "N/A")
        st.metric("🏆 Best Setup",       best)
    with c6:
        phase_short = phase.replace("PHASE_", "P").replace("_", " ")
        st.metric("📈 Phase",            phase_short)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Setup Performance Table ───────────────────────────────────
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("<div class='section-header'>⚡ SETUP LIBRARY — EXPECTANCY RANKING</div>",
                    unsafe_allow_html=True)

        if library:
            rows = []
            for setup, data in library.items():
                total = data.get("total_trades", 0)
                if total < 3:
                    continue
                rows.append({
                    "Setup":    setup,
                    "Dir":      data.get("direction", "L")[:1],
                    "Trades":   total,
                    "WR %":     round(data.get("win_rate", 0), 1),
                    "Exp %":    round(data.get("expectancy", 0), 3),
                    "PF":       round(data.get("profit_factor", 0), 2),
                    "Sharpe":   round(data.get("sharpe", 0), 2),
                    "Avg RR":   round(data.get("avg_rr", 0), 2),
                    "Best Reg": _best_reg(data.get("by_regime", {})),
                })

            if rows:
                df = pd.DataFrame(rows).sort_values("Exp %", ascending=False)
                st.dataframe(df, use_container_width=True, height=350,
                             column_config={
                                 "WR %":  st.column_config.NumberColumn(format="%.1f%%"),
                                 "Exp %": st.column_config.NumberColumn(format="%+.3f%%"),
                             })
            else:
                st.info("Run replay cycles to populate setup library")
        else:
            st.info("No setup data yet — start the learning daemon")

    with col_right:
        st.markdown("<div class='section-header'>🌍 REGIME INTELLIGENCE</div>",
                    unsafe_allow_html=True)

        if regime_perf:
            rows = []
            for regime, data in regime_perf.items():
                total = data.get("total_trades", 0)
                rows.append({
                    "Regime":    regime,
                    "Trades":    total,
                    "WR %":      round(data.get("win_rate", 0), 1),
                    "Avg PnL %": round(data.get("total_pnl", 0) / max(total, 1), 3),
                    "Best Setup":_best_setup_in_regime(data.get("by_setup", {})),
                    "Days":      data.get("days_classified", 0),
                })
            reg_df = pd.DataFrame(rows).sort_values("WR %", ascending=False)
            st.dataframe(reg_df, use_container_width=True, height=200,
                         column_config={
                             "WR %":      st.column_config.NumberColumn(format="%.1f%%"),
                             "Avg PnL %": st.column_config.NumberColumn(format="%+.3f%%"),
                         })

            # Regime WR chart
            if len(rows) > 0:
                wr_df = pd.DataFrame(rows)[["Regime", "WR %"]].set_index("Regime")
                st.bar_chart(wr_df, color="#22c55e", height=150)
        else:
            st.info("No regime data yet")

    # ── Rankings ──────────────────────────────────────────────────
    if rankings:
        st.markdown("<div class='section-header'>🏆 SETUP RANKINGS</div>",
                    unsafe_allow_html=True)
        r1, r2, r3, r4 = st.columns(4)

        with r1:
            st.caption("By Expectancy")
            for item in rankings.get("by_expectancy", [])[:5]:
                st.markdown(f"`{item['setup'][:20]}` {item.get('expectancy', 0):+.2f}%")

        with r2:
            st.caption("By Win Rate")
            for item in rankings.get("by_win_rate", [])[:5]:
                st.markdown(f"`{item['setup'][:20]}` {item.get('win_rate', 0):.1f}%")

        with r3:
            st.caption("Best Long Setups")
            for item in rankings.get("best_long", [])[:5]:
                st.markdown(f"`{item['setup'][:20]}` {item.get('expectancy', 0):+.2f}%")

        with r4:
            st.caption("Best Short Setups")
            if rankings.get("best_short"):
                for item in rankings.get("best_short", [])[:5]:
                    st.markdown(f"`{item['setup'][:20]}` {item.get('expectancy', 0):+.2f}%")
            else:
                st.caption("Insufficient short data")

    # ── Confidence Evolution ──────────────────────────────────────
    if evolution:
        st.markdown("<div class='section-header'>📈 CONFIDENCE EVOLUTION</div>",
                    unsafe_allow_html=True)
        try:
            evo_rows = []
            for record in evolution[-20:]:
                ts = record.get("timestamp", "")[:16]
                for setup, data in record.get("setups", {}).items():
                    evo_rows.append({
                        "time":      ts,
                        "setup":     setup,
                        "win_rate":  data.get("win_rate", 0),
                        "expectancy":data.get("expectancy", 0),
                    })
            if evo_rows:
                evo_df = pd.DataFrame(evo_rows)
                pivot  = evo_df.pivot_table(
                    index="time", columns="setup",
                    values="win_rate", aggfunc="last"
                ).fillna(method="ffill")
                st.line_chart(pivot, height=180)
        except Exception:
            st.info("Evolution chart will populate after multiple cycles")

    # ── Suggestions ───────────────────────────────────────────────
    if suggestions:
        st.markdown("<div class='section-header'>💡 ADAPTIVE SUGGESTIONS (Advisory)</div>",
                    unsafe_allow_html=True)
        sig_df = pd.DataFrame(suggestions[:10])[[
            "type", "setup", "title", "confidence", "trades", "level"
        ]] if suggestions else pd.DataFrame()
        if not sig_df.empty:
            st.dataframe(sig_df, use_container_width=True, height=200)

    # ── Daemon Controls ───────────────────────────────────────────
    st.markdown("<div class='section-header'>⚙️ DAEMON CONTROLS</div>",
                unsafe_allow_html=True)

    dc1, dc2, dc3, dc4 = st.columns(4)
    with dc1:
        if st.button("▶ Phase 1 Bootstrap",
                     key="ph1", use_container_width=True):
            with st.spinner("Starting Phase 1..."):
                subprocess.Popen([
                    sys.executable, "/root/historical_learning_daemon.py",
                    "--mode", "phase1",
                ])
            st.success("✔ Phase 1 started in background!")

    with dc2:
        if st.button("▶ Phase 2 Advanced",
                     key="ph2", use_container_width=True):
            with st.spinner("Starting Phase 2..."):
                subprocess.Popen([
                    sys.executable, "/root/historical_learning_daemon.py",
                    "--mode", "phase2",
                ])
            st.success("✔ Phase 2 started!")

    with dc3:
        if st.button("▶ Single Cycle",
                     key="once", use_container_width=True):
            with st.spinner("Running..."):
                subprocess.run([
                    sys.executable, "/root/historical_learning_daemon.py",
                    "--mode", "once",
                ], capture_output=True, timeout=300)
                st.cache_data.clear()
            st.success("✔ Cycle complete!")

    with dc4:
        if st.button("🔄 Refresh Stats",
                     key="refresh_rep", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # ── Daemon Log ────────────────────────────────────────────────
    if os.path.exists(PATHS["daemon"]):
        with st.expander("📋 Daemon Log (last 20 lines)"):
            try:
                with open(PATHS["daemon"]) as f:
                    lines = f.readlines()[-20:]
                st.code("".join(lines), language="text")
            except Exception:
                st.info("Log not available")

    # ── Daemon State ──────────────────────────────────────────────
    if state:
        with st.expander("🔧 Daemon State"):
            st.json(state)

# ── Helpers ───────────────────────────────────────────────────────
def _best_reg(by_regime: dict) -> str:
    qualified = {k: v for k, v in by_regime.items() if v.get("total", 0) >= 3}
    if not qualified:
        return "N/A"
    return max(qualified.items(),
               key=lambda x: x[1].get("win_rate", 0),
               default=("N/A", {}))[0]

def _best_setup_in_regime(by_setup: dict) -> str:
    qualified = {k: v for k, v in by_setup.items() if v.get("total", 0) >= 3}
    if not qualified:
        return "N/A"
    return max(qualified.items(),
               key=lambda x: x[1].get("win_rate", 0),
               default=("N/A", {}))[0]

# ── Standalone Mode ───────────────────────────────────────────────
if _STANDALONE:
    st.markdown("# 📈 Historical Replay Intelligence")
    render_replay_tab()
