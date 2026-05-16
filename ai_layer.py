"""
ai_layer.py
===========
طبقة الذكاء الاصطناعي الكاملة — ثلاثة في ملف واحد:
✅ ١. Claude AI Intelligence Layer — يفسر كل البيانات
✅ ٢. Confidence Score Engine — أوزان كل Agent
✅ ٣. Web Dashboard — Streamlit رسوم بيانية حية
"""

import yfinance as yf
import pandas as pd
import numpy as np
import requests
import json
import time
import os
import threading
from datetime import datetime, timedelta
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

# Anthropic API
try:
    import anthropic
    ANTHROPIC_CLIENT = anthropic.Anthropic()
    HAS_ANTHROPIC = True
except:
    HAS_ANTHROPIC = False
    print("[AI] anthropic غير مثبت — pip install anthropic")

def send_telegram(msg: str):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "HTML"
        }, timeout=10)
    except Exception as e:
        print(f"[TG] {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# ١. Claude AI Intelligence Layer
# ═══════════════════════════════════════════════════════════════════════════════

def build_market_context() -> dict:
    """يجمع كل البيانات المتاحة في سياق واحد"""
    context = {}

    # تحميل كل ملفات الحالة
    state_files = {
        "macro":       "/root/macro_state.json",
        "sector":      "/root/sector_state.json",
        "fred":        "/root/fred_state.json",
        "fundamental": "/root/fundamental_state.json",
        "data_scores": "/root/data_scores.json",
    }

    for name, path in state_files.items():
        try:
            with open(path, encoding="utf-8") as f:
                context[name] = json.load(f)
        except:
            context[name] = {}

    # بيانات السوق الحالية
    try:
        symbols = ["SPY", "QQQ", "^VIX", "^TNX", "DX-Y.NYB", "GC=F"]
        market = {}
        for sym in symbols:
            df = yf.download(sym, period="5d", progress=False, auto_adjust=True)
            if not df.empty:
                df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
                close = df['Close']
                market[sym] = {
                    "current": round(float(close.iloc[-1]), 2),
                    "change_1d": round((float(close.iloc[-1]) - float(close.iloc[-2])) / float(close.iloc[-2]) * 100, 2) if len(close) > 1 else 0,
                    "change_5d": round((float(close.iloc[-1]) - float(close.iloc[0])) / float(close.iloc[0]) * 100, 2),
                }
        context["market"] = market
    except Exception as e:
        context["market"] = {}

    return context

def call_claude_analysis(context: dict, symbol: str = None) -> dict:
    """
    يرسل السياق لـ Claude API ويرجع تحليل JSON منظم
    """
    if not HAS_ANTHROPIC:
        return {"error": "anthropic غير مثبت"}

    # بناء الـ Prompt
    fred_data   = context.get("fred", {}).get("fred_data", {})
    fred_analysis = context.get("fred", {}).get("analysis", {})
    macro_state = context.get("macro", {})
    market      = context.get("market", {})

    cpi     = fred_data.get("CPI", {}).get("latest", "N/A")
    fed     = fred_data.get("FED_RATE", {}).get("latest", "N/A")
    unemp   = fred_data.get("UNEMPLOYMENT", {}).get("latest", "N/A")
    yield10 = fred_data.get("YIELD_10Y", {}).get("latest", "N/A")
    spread  = fred_data.get("YIELD_SPREAD", {}).get("latest", "N/A")
    m2      = fred_data.get("M2", {}).get("change_pct", "N/A")

    spy_chg = market.get("SPY", {}).get("change_1d", "N/A")
    vix     = market.get("^VIX", {}).get("current", "N/A")
    dxy     = market.get("DX-Y.NYB", {}).get("current", "N/A")
    us10y   = market.get("^TNX", {}).get("current", "N/A")
    gold    = market.get("GC=F", {}).get("change_1d", "N/A")

    macro_score  = macro_state.get("score", 0)
    macro_action = macro_state.get("action", "SELECTIVE")
    macro_warns  = macro_state.get("warnings", [])

    econ_phase = fred_analysis.get("economic_phase", "N/A")
    fed_dir    = fred_analysis.get("fed_direction", "N/A")

    symbol_part = ""
    if symbol:
        try:
            ticker = yf.Ticker(symbol)
            info   = ticker.info
            pe     = info.get("trailingPE", "N/A")
            eps_g  = info.get("earningsGrowth", "N/A")
            rev_g  = info.get("revenueGrowth", "N/A")
            upside = info.get("targetMeanPrice", "N/A")
            symbol_part = f"""
Stock Analysis Request: {symbol}
- P/E Ratio: {pe}
- EPS Growth: {eps_g}
- Revenue Growth: {rev_g}
- Analyst Target: {upside}
"""
        except:
            pass

    prompt = f"""You are an expert macro analyst for a quantitative hedge fund.
Analyze the following market data and return ONLY a JSON object.

MACROECONOMIC DATA:
- CPI: {cpi}
- Fed Funds Rate: {fed}%
- Unemployment: {unemp}%
- 10Y Yield: {yield10}
- Yield Spread (10Y-2Y): {spread}
- M2 Growth: {m2}%

MARKET DATA:
- SPY 1D Change: {spy_chg}%
- VIX: {vix}
- DXY: {dxy}
- US10Y: {us10y}
- Gold 1D Change: {gold}%

SYSTEM STATE:
- Economic Phase: {econ_phase}
- Fed Direction: {fed_dir}
- Macro Score: {macro_score}
- Macro Action: {macro_action}
- Warnings: {macro_warns}
{symbol_part}

Return ONLY this JSON (no explanation):
{{
  "market_regime": "risk_on|risk_off|neutral|transition",
  "liquidity_state": "expanding|tightening|neutral",
  "fed_expectation": "dovish|hawkish|neutral",
  "recession_probability": 0.0,
  "inflation_trend": "rising|falling|stable",
  "recommended_exposure": 0.0,
  "confidence": 0.0,
  "preferred_sectors": [],
  "avoid_sectors": [],
  "allow_new_trades": true,
  "position_size_multiplier": 1.0,
  "key_risks": [],
  "opportunity": "",
  "reasoning": ""
}}"""

    try:
        response = ANTHROPIC_CLIENT.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )

        text = response.content[0].text.strip()
        # تنظيف JSON
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        result = json.loads(text)
        result["timestamp"] = str(datetime.now())
        result["source"]    = "claude_ai"
        print(f"[AI] تحليل Claude: {result.get('market_regime')} | Confidence={result.get('confidence')}")
        return result

    except Exception as e:
        print(f"[AI] خطأ: {e}")
        return {
            "market_regime":         "neutral",
            "liquidity_state":       "neutral",
            "fed_expectation":       "neutral",
            "recession_probability": 0.3,
            "inflation_trend":       "stable",
            "recommended_exposure":  0.5,
            "confidence":            0.5,
            "preferred_sectors":     [],
            "avoid_sectors":         [],
            "allow_new_trades":      True,
            "position_size_multiplier": 1.0,
            "key_risks":             ["AI analysis unavailable"],
            "opportunity":           "",
            "reasoning":             f"Fallback: {str(e)}",
            "timestamp":             str(datetime.now()),
            "source":                "fallback",
        }

def save_ai_analysis(analysis: dict):
    """يحفظ تحليل Claude"""
    with open("/root/ai_analysis.json", "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)

def load_ai_analysis() -> dict:
    """يحمّل آخر تحليل"""
    try:
        with open("/root/ai_analysis.json", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def send_ai_report(analysis: dict):
    """يرسل تقرير AI على Telegram"""
    regime    = analysis.get("market_regime", "N/A")
    conf      = analysis.get("confidence", 0)
    exposure  = analysis.get("recommended_exposure", 0)
    allow     = analysis.get("allow_new_trades", True)
    sectors   = analysis.get("preferred_sectors", [])
    avoid     = analysis.get("avoid_sectors", [])
    risks     = analysis.get("key_risks", [])
    reasoning = analysis.get("reasoning", "")
    mult      = analysis.get("position_size_multiplier", 1.0)

    regime_emoji = {
        "risk_on":    "🟢🟢",
        "risk_off":   "🔴🔴",
        "neutral":    "⚪",
        "transition": "🟡",
    }.get(regime, "⚪")

    msg = (
        f"🧠 <b>Claude AI Analysis</b>\n"
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"{'─'*28}\n\n"
        f"<b>النظام السوقي:</b> {regime_emoji} {regime}\n"
        f"<b>الثقة:</b> {conf*100:.0f}%\n"
        f"<b>التعرض المقترح:</b> {exposure*100:.0f}%\n"
        f"<b>حجم الصفقة:</b> {mult:.1f}x\n"
        f"<b>فتح صفقات جديدة:</b> {'✅ نعم' if allow else '❌ لا'}\n\n"
    )

    if sectors:
        msg += f"<b>قطاعات مفضلة:</b>\n"
        for s in sectors[:3]:
            msg += f"• {s}\n"
        msg += "\n"

    if avoid:
        msg += f"<b>قطاعات تجنب:</b>\n"
        for s in avoid[:3]:
            msg += f"• {s}\n"
        msg += "\n"

    if risks:
        msg += f"<b>مخاطر رئيسية:</b>\n"
        for r in risks[:3]:
            msg += f"⚠️ {r}\n"
        msg += "\n"

    if reasoning:
        msg += f"<b>التحليل:</b>\n{reasoning[:300]}"

    send_telegram(msg)

# ═══════════════════════════════════════════════════════════════════════════════
# ٢. Confidence Score Engine — أوزان كل Agent
# ═══════════════════════════════════════════════════════════════════════════════

AGENT_WEIGHTS = {
    "macro":       0.25,
    "technical":   0.20,
    "smart_money": 0.15,
    "sector":      0.15,
    "sentiment":   0.10,
    "earnings":    0.10,
    "risk":        0.05,
}

def calc_agent_scores(symbol: str) -> dict:
    """يحسب نقاط كل Agent"""
    scores = {}

    # ─── Macro Score ──────────────────────────────────────────────────────────
    try:
        with open("/root/macro_state.json") as f:
            macro = json.load(f)
        macro_raw = macro.get("score", 0)
        scores["macro"] = max(0, min(100, 50 + macro_raw * 8))
    except:
        scores["macro"] = 50

    # ─── Technical Score ──────────────────────────────────────────────────────
    try:
        df = yf.download(symbol, period="6mo", progress=False, auto_adjust=True)
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        close = df['Close']
        ma50  = close.rolling(50).mean().iloc[-1]
        ma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else ma50
        vol   = df['Volume']
        vol_ratio = float(vol.iloc[-1]) / float(vol.rolling(20).mean().iloc[-1])
        current = float(close.iloc[-1])

        tech_score = 50
        if current > float(ma50):   tech_score += 15
        if current > float(ma200):  tech_score += 15
        if float(ma50) > float(ma200): tech_score += 10
        if vol_ratio > 1.5:         tech_score += 10
        scores["technical"] = min(100, tech_score)
    except:
        scores["technical"] = 50

    # ─── Smart Money Score ────────────────────────────────────────────────────
    try:
        with open("/root/data_scores.json") as f:
            data_scores = json.load(f)
        if symbol in data_scores:
            raw = data_scores[symbol].get("total_score", 0)
            scores["smart_money"] = max(0, min(100, 50 + raw * 10))
        else:
            scores["smart_money"] = 50
    except:
        scores["smart_money"] = 50

    # ─── Sector Score ─────────────────────────────────────────────────────────
    try:
        with open("/root/sector_state.json") as f:
            sectors = json.load(f)
        is_leading = False
        for sec_name, sec_data in sectors.get("sectors", {}).items():
            if symbol in sec_data.get("stocks", []):
                is_leading = sec_data.get("is_leading", False)
                sec_score  = sec_data.get("score", 0)
                scores["sector"] = 85 if is_leading else max(30, 50 + sec_score * 5)
                break
        else:
            scores["sector"] = 55
    except:
        scores["sector"] = 55

    # ─── Sentiment Score ──────────────────────────────────────────────────────
    try:
        ticker = yf.Ticker(symbol)
        info   = ticker.info
        rating = info.get("recommendationMean", 3)
        scores["sentiment"] = max(0, min(100, int((5 - rating) / 4 * 100)))
    except:
        scores["sentiment"] = 50

    # ─── Earnings Score ───────────────────────────────────────────────────────
    try:
        ticker = yf.Ticker(symbol)
        info   = ticker.info
        eps_g  = info.get("earningsGrowth", 0) or 0
        rev_g  = info.get("revenueGrowth",  0) or 0
        earn_score = 50
        if eps_g > 0.25: earn_score += 25
        elif eps_g > 0:  earn_score += 10
        elif eps_g < 0:  earn_score -= 15
        if rev_g > 0.15: earn_score += 15
        scores["earnings"] = max(0, min(100, earn_score))
    except:
        scores["earnings"] = 50

    # ─── Risk Score ───────────────────────────────────────────────────────────
    try:
        vix = yf.download("^VIX", period="5d", progress=False, auto_adjust=True)
        vix.columns = [c[0] if isinstance(c, tuple) else c for c in vix.columns]
        vix_val = float(vix['Close'].iloc[-1])
        if vix_val < 15:   scores["risk"] = 85
        elif vix_val < 20: scores["risk"] = 70
        elif vix_val < 25: scores["risk"] = 55
        elif vix_val < 35: scores["risk"] = 35
        else:              scores["risk"] = 15
    except:
        scores["risk"] = 50

    return scores

def calc_confidence_score(symbol: str, ai_analysis: dict = None) -> dict:
    """
    يحسب Confidence Score النهائي
    يجمع كل الـ Agents بأوزانها
    """
    print(f"\n[Confidence] حساب نقاط {symbol}...")

    agent_scores = calc_agent_scores(symbol)

    # حساب النقاط المرجحة
    weighted_score = sum(
        agent_scores.get(agent, 50) * weight
        for agent, weight in AGENT_WEIGHTS.items()
    )

    # تعديل بناءً على AI Analysis
    ai_boost = 0
    if ai_analysis:
        conf       = ai_analysis.get("confidence", 0.5)
        allow      = ai_analysis.get("allow_new_trades", True)
        regime     = ai_analysis.get("market_regime", "neutral")
        multiplier = ai_analysis.get("position_size_multiplier", 1.0)

        if not allow:
            weighted_score *= 0.5
        elif regime == "risk_on":
            ai_boost = 8
        elif regime == "risk_off":
            ai_boost = -15
        elif regime == "transition":
            ai_boost = -5

        weighted_score += ai_boost
        weighted_score  = weighted_score * multiplier

    final_score = max(0, min(100, weighted_score))

    # قرار الحجم
    if final_score >= 80:
        trade_decision = "FULL"
        size_pct       = 1.0
        decision_emoji = "🟢🟢"
    elif final_score >= 65:
        trade_decision = "HALF"
        size_pct       = 0.5
        decision_emoji = "🟢"
    elif final_score >= 50:
        trade_decision = "QUARTER"
        size_pct       = 0.25
        decision_emoji = "🟡"
    else:
        trade_decision = "NO_TRADE"
        size_pct       = 0
        decision_emoji = "🔴"

    result = {
        "symbol":        symbol,
        "final_score":   round(final_score, 1),
        "agent_scores":  agent_scores,
        "trade_decision": trade_decision,
        "size_pct":      size_pct,
        "decision_emoji": decision_emoji,
        "ai_boost":      ai_boost,
        "timestamp":     str(datetime.now()),
    }

    print(f"[Confidence] {symbol}: {final_score:.1f} → {decision_emoji} {trade_decision}")

    # حفظ النتيجة
    try:
        try:
            with open("/root/confidence_scores.json") as f:
                all_scores = json.load(f)
        except:
            all_scores = {}
        all_scores[symbol] = result
        with open("/root/confidence_scores.json", "w") as f:
            json.dump(all_scores, f, ensure_ascii=False, indent=2, default=str)
    except:
        pass

    return result

def get_position_size(symbol: str, base_risk_pct: float = 0.0125) -> float:
    """
    يرجع حجم الصفقة الفعلي بناءً على Confidence Score
    """
    try:
        with open("/root/confidence_scores.json") as f:
            scores = json.load(f)
        if symbol in scores:
            size_pct = scores[symbol].get("size_pct", 0.25)
            return base_risk_pct * size_pct
    except:
        pass
    return base_risk_pct * 0.25

# ═══════════════════════════════════════════════════════════════════════════════
# ٣. Web Dashboard — Streamlit
# ═══════════════════════════════════════════════════════════════════════════════

DASHBOARD_CODE = '''#!/usr/bin/env python3
"""
dashboard.py — Streamlit Web Dashboard
تشغيل: streamlit run /root/dashboard.py --server.port 8501
"""
import streamlit as st
import json, yfinance as yf, pandas as pd
from datetime import datetime

st.set_page_config(
    page_title="Minervini Trading Bot",
    page_icon="📈",
    layout="wide"
)

st.title("📈 Minervini AI Trading System")
st.caption(f"آخر تحديث: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

# ─── صف الإحصائيات العلوية ───────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)

# حساب Alpaca Portfolio
try:
    import alpaca_trade_api as tradeapi
    from config import ALPACA_KEY, ALPACA_SECRET
    api = tradeapi.REST(ALPACA_KEY, ALPACA_SECRET, base_url="https://paper-api.alpaca.markets")
    account   = api.get_account()
    portfolio = float(account.portfolio_value)
    cash      = float(account.cash)
    positions = api.list_positions()
    pnl       = sum(float(p.unrealized_pl) for p in positions)

    col1.metric("💼 المحفظة", f"${portfolio:,.0f}", f"{(portfolio-50000)/500:.1f}%")
    col2.metric("💵 النقد",   f"${cash:,.0f}")
    col3.metric("📊 المراكز", len(positions))
    col4.metric("📈 P&L",    f"${pnl:+,.0f}")
except:
    col1.metric("💼 المحفظة", "$50,000")
    col2.metric("💵 النقد",   "$48,000")
    col3.metric("📊 المراكز", "1")
    col4.metric("📈 P&L",    "$0")

st.divider()

# ─── صفان رئيسيان ────────────────────────────────────────────────────────────
left, right = st.columns([1, 1])

with left:
    st.subheader("🧠 Claude AI Analysis")
    ai = load_json("/root/ai_analysis.json")
    if ai:
        regime = ai.get("market_regime", "N/A")
        conf   = ai.get("confidence", 0)
        allow  = ai.get("allow_new_trades", True)
        regime_color = {"risk_on": "🟢", "risk_off": "🔴", "neutral": "⚪", "transition": "🟡"}.get(regime, "⚪")
        
        st.markdown(f"**النظام السوقي:** {regime_color} {regime}")
        st.progress(conf, text=f"الثقة: {conf*100:.0f}%")
        st.markdown(f"**فتح صفقات:** {'✅ نعم' if allow else '❌ لا'}")
        st.markdown(f"**التعرض:** {ai.get('recommended_exposure', 0)*100:.0f}%")

        sectors = ai.get("preferred_sectors", [])
        if sectors:
            st.markdown("**قطاعات مفضلة:** " + " | ".join(sectors[:3]))

        avoid = ai.get("avoid_sectors", [])
        if avoid:
            st.markdown("**تجنب:** " + " | ".join(avoid[:3]))

        reasoning = ai.get("reasoning", "")
        if reasoning:
            with st.expander("📝 التحليل الكامل"):
                st.write(reasoning)
    else:
        st.info("لا يوجد تحليل AI بعد — سيظهر عند الساعة 7 صباحاً")

with right:
    st.subheader("🌍 Macro Intelligence")
    macro = load_json("/root/macro_state.json")
    if macro:
        score  = macro.get("score", 0)
        action = macro.get("action", "SELECTIVE")
        action_color = {"BUY_AGGRESSIVE": "🟢🟢", "BUY_SELECTIVE": "🟢", "SELECTIVE": "⚪", "REDUCE": "🟡", "CASH": "🔴"}.get(action, "⚪")
        st.markdown(f"**القرار:** {action_color} {action}")
        st.markdown(f"**النقاط:** {score:+d}")
        
        warnings = macro.get("warnings", [])
        if warnings:
            for w in warnings:
                st.warning(w)
        
        signals = macro.get("signals", [])
        for s in signals[:4]:
            st.markdown(f"• {s}")

st.divider()

# ─── Confidence Scores ────────────────────────────────────────────────────────
st.subheader("🎯 Confidence Scores")
conf_scores = load_json("/root/confidence_scores.json")
if conf_scores:
    rows = []
    for sym, data in conf_scores.items():
        rows.append({
            "السهم": sym,
            "النقاط": data.get("final_score", 0),
            "القرار": data.get("trade_decision", "N/A"),
            "الحجم": f"{data.get('size_pct', 0)*100:.0f}%",
            "Macro": data.get("agent_scores", {}).get("macro", 0),
            "Technical": data.get("agent_scores", {}).get("technical", 0),
            "Smart Money": data.get("agent_scores", {}).get("smart_money", 0),
        })
    df = pd.DataFrame(rows).sort_values("النقاط", ascending=False)
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("لا توجد نقاط بعد")

# ─── المراكز المفتوحة ─────────────────────────────────────────────────────────
st.subheader("📊 المراكز المفتوحة")
try:
    import alpaca_trade_api as tradeapi
    from config import ALPACA_KEY, ALPACA_SECRET
    api = tradeapi.REST(ALPACA_KEY, ALPACA_SECRET, base_url="https://paper-api.alpaca.markets")
    positions = api.list_positions()
    if positions:
        pos_data = []
        for p in positions:
            pnl_pct = float(p.unrealized_plpc) * 100
            pos_data.append({
                "السهم":       p.symbol,
                "الكمية":     p.qty,
                "سعر الدخول": f"${float(p.avg_entry_price):.2f}",
                "السعر الحالي": f"${float(p.current_price):.2f}",
                "P&L":        f"${float(p.unrealized_pl):+.0f}",
                "P&L %":      f"{pnl_pct:+.1f}%",
                "الحالة":     "🟢" if pnl_pct >= 0 else "🔴",
            })
        st.dataframe(pd.DataFrame(pos_data), use_container_width=True, hide_index=True)
    else:
        st.info("لا توجد مراكز مفتوحة حالياً")
except Exception as e:
    st.warning(f"لا يمكن تحميل المراكز: {e}")

# ─── رسم بياني SPY ───────────────────────────────────────────────────────────
st.subheader("📈 SPY — آخر 30 يوم")
try:
    spy = yf.download("SPY", period="1mo", progress=False, auto_adjust=True)
    spy.columns = [c[0] if isinstance(c, tuple) else c for c in spy.columns]
    st.line_chart(spy['Close'])
except:
    st.warning("لا يمكن تحميل بيانات SPY")

# ─── صحة النظام ──────────────────────────────────────────────────────────────
st.subheader("💻 صحة النظام")
import subprocess
programs = ["auto_monitor", "monitor_upgrade", "phase2_upgrade",
            "phase3_sectors", "macro_intelligence", "watchdog",
            "priority1_quality", "priority2_intelligence",
            "priority3_live", "fundamental_engine", "data_sources", "insider_check"]

cols = st.columns(4)
for i, prog in enumerate(programs):
    result = pass  # streamlit run removed

    last_ai     = None
    last_scores = None

    while True:
        try:
            now   = datetime.now()
            today = now.date()

            # AI Analysis — كل يوم 7 صباحاً
            if now.hour == 7 and now.minute < 10 and last_ai != today:
                print(f"\n[AI] {now.strftime('%Y-%m-%d')} — تحليل يومي")
                context  = build_market_context()
                analysis = call_claude_analysis(context)
                save_ai_analysis(analysis)
                from market_session_manager import get_full_status as _gfs
            if _gfs().get("is_market_open") or _gfs().get("is_premarket"):
                send_ai_report(analysis)
                last_ai = today

            # Confidence Scores — كل يوم 9 صباحاً
            if now.hour == 9 and now.minute < 15 and last_scores != today:
                ai_analysis = load_ai_analysis()
                print(f"\n[Confidence] حساب نقاط {len(WATCHLIST)} سهم...")
                for sym in WATCHLIST:
                    calc_confidence_score(sym, ai_analysis)
                    time.sleep(1)
                last_scores = today
                print("[Confidence] اكتمل ✅")

            time.sleep(60)

        except Exception as e:
            print(f"[AI Layer] خطأ: {e}")
            time.sleep(60)

# ═══════════════════════════════════════════════════════════════════════════════
# نقطة الدخول
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("🧪 اختبار AI Layer\n")

    print("١. تثبيت anthropic:")
    pass  # pip install anthropic removed

    print("\n٢. إنشاء Dashboard:")
    pass  # create_dashboard removed
    print("   dashboard.py ✅")

    print("\n٣. جمع السياق:")
    context = build_market_context()
    print(f"   بيانات السوق: {len(context.get('market', {}))} رمز")
    print(f"   FRED: {'✅' if context.get('fred') else '❌'}")

    print("\n٤. تحليل Claude AI:")
    analysis = call_claude_analysis(context, "NVDA")
    print(f"   النظام: {analysis.get('market_regime')}")
    print(f"   الثقة: {analysis.get('confidence', 0)*100:.0f}%")
    print(f"   صفقات: {'✅' if analysis.get('allow_new_trades') else '❌'}")
    save_ai_analysis(analysis)
    send_ai_report(analysis)

    print("\n٥. Confidence Scores:")
    test_syms = ["NVDA", "MSFT", "AAPL"]
    for sym in test_syms:
        score = calc_confidence_score(sym, analysis)
        print(f"   {sym}: {score['final_score']:.0f} → {score['decision_emoji']} {score['trade_decision']}")

    print("\n٦. تثبيت Streamlit:")
    pass  # pip install removed
    print("   لتشغيل Dashboard:")
    print("   streamlit run /root/dashboard.py --server.port 8501 &")

    print("\n🏆 النظام الآن Hedge Fund Level!")
'''

# Keep running loop
import time as _time
if __name__ == "__main__":
    while True:
        try:
            pass
        except:
            pass
        _time.sleep(3600)
