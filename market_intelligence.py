#!/usr/bin/env python3
"""
market_intelligence.py — Multi-Asset Correlation + AI Market Narrative
INSTITUTIONAL MARKET INTELLIGENCE LAYER
Analyzes cross-asset relationships and generates daily AI market narrative.
"""

import os, json, time
from datetime import datetime
from typing import Optional

try:
    from logger import get_logger
    log = get_logger("market_intelligence")
except ImportError:
    import logging
    log = logging.getLogger("market_intelligence")
    logging.basicConfig(level=logging.INFO)

from dotenv import load_dotenv
load_dotenv("/root/.env")

INTELLIGENCE_FILE = "/root/logs/market_intelligence.json"
os.makedirs("/root/logs", exist_ok=True)

# ── Multi-Asset Universe ──────────────────────────────────────
ASSETS = {
    "SPY":  {"name": "S&P 500",        "type": "equity"},
    "QQQ":  {"name": "Nasdaq",         "type": "equity"},
    "IWM":  {"name": "Russell 2000",   "type": "equity"},
    "DXY":  {"name": "US Dollar",      "type": "currency",  "ticker": "UUP"},
    "TNX":  {"name": "10Y Yield",      "type": "rate",      "ticker": "TLT"},
    "GLD":  {"name": "Gold",           "type": "commodity"},
    "USO":  {"name": "Oil",            "type": "commodity"},
    "BTC":  {"name": "Bitcoin",        "type": "crypto",    "ticker": "IBIT"},
    "VIX":  {"name": "Volatility",     "type": "volatility","ticker": "UVXY"},
    "XLK":  {"name": "Tech",           "type": "sector"},
    "XLF":  {"name": "Financials",     "type": "sector"},
    "XLE":  {"name": "Energy",         "type": "sector"},
    "XLV":  {"name": "Healthcare",     "type": "sector"},
    "XLI":  {"name": "Industrials",    "type": "sector"},
    "XLRE": {"name": "Real Estate",    "type": "sector"},
}

# ── RS Ranking Universe ───────────────────────────────────────
RS_UNIVERSE = [
    "NVDA","AMD","AVGO","ARM","ANET","MRVL","SMCI","TSM",
    "MSFT","AAPL","META","GOOGL","AMZN","NFLX","CRM","ORCL",
    "LLY","UNH","ABBV","TMO","ISRG","DXCM",
    "GS","JPM","V","MA","MS","BX","KKR",
    "TSLA","RIVN","F","GM",
    "CRWD","PANW","DDOG","NET","ZS","FTNT","S",
    "CAT","DE","ETN","GE","HON","RTX","LMT",
]


def fetch_asset_data(ticker: str, period: str = "3mo") -> Optional[dict]:
    """Fetch price data for an asset."""
    try:
        import yfinance as yf
        hist = yf.Ticker(ticker).history(period=period)
        if hist.empty or len(hist) < 5:
            return None
        close   = hist["Close"]
        current = float(close.iloc[-1])
        prev    = float(close.iloc[-2])
        w1_ago  = float(close.iloc[-5]) if len(close) >= 5 else current
        m1_ago  = float(close.iloc[-21]) if len(close) >= 21 else current
        m3_ago  = float(close.iloc[0])
        return {
            "ticker":   ticker,
            "price":    round(current, 3),
            "chg_1d":   round((current - prev)   / prev   * 100, 2),
            "chg_1w":   round((current - w1_ago) / w1_ago * 100, 2),
            "chg_1m":   round((current - m1_ago) / m1_ago * 100, 2),
            "chg_3m":   round((current - m3_ago) / m3_ago * 100, 2),
            "ma50":     round(float(close.tail(50).mean()), 3),
            "above_ma": current > float(close.tail(50).mean()),
        }
    except Exception as e:
        log.error(f"Fetch failed for {ticker}: {e}")
        return None


def build_correlation_matrix(assets_data: dict) -> dict:
    """Build simplified cross-asset correlation interpretation."""
    spy  = assets_data.get("SPY", {})
    qqq  = assets_data.get("QQQ", {})
    tlt  = assets_data.get("TNX", {})
    gld  = assets_data.get("GLD", {})
    uso  = assets_data.get("USO", {})
    btc  = assets_data.get("BTC", {})
    vix  = assets_data.get("VIX", {})

    # Risk-on signals
    risk_on_signals  = 0
    risk_off_signals = 0

    if spy.get("chg_1d", 0) > 0:  risk_on_signals  += 1
    if qqq.get("chg_1d", 0) > 0:  risk_on_signals  += 1
    if btc.get("chg_1d", 0) > 0:  risk_on_signals  += 1
    if uso.get("chg_1d", 0) > 0:  risk_on_signals  += 1
    if vix.get("chg_1d", 0) < 0:  risk_on_signals  += 1   # VIX falling = risk on
    if gld.get("chg_1d", 0) > 1:  risk_off_signals += 1   # Gold surging = fear
    if tlt.get("chg_1d", 0) > 0:  risk_off_signals += 1   # Bonds up = risk off

    total = risk_on_signals + risk_off_signals
    risk_on_pct = risk_on_signals / total * 100 if total > 0 else 50

    quality = (
        "STRONG_RISK_ON"  if risk_on_pct >= 75 else
        "RISK_ON"         if risk_on_pct >= 60 else
        "NEUTRAL"         if risk_on_pct >= 40 else
        "RISK_OFF"        if risk_on_pct >= 25 else
        "STRONG_RISK_OFF"
    )

    return {
        "risk_on_signals":  risk_on_signals,
        "risk_off_signals": risk_off_signals,
        "risk_on_pct":      round(risk_on_pct, 1),
        "quality":          quality,
    }


def rank_rs(universe: list) -> list:
    """Rank stocks by relative strength vs SPY."""
    log.info(f"Ranking RS for {len(universe)} symbols...")
    spy_data = fetch_asset_data("SPY", "3mo")
    spy_3m   = spy_data.get("chg_3m", 0) if spy_data else 0

    rankings = []
    for sym in universe:
        data = fetch_asset_data(sym, "3mo")
        if not data:
            continue
        rs_vs_spy = round(data["chg_3m"] - spy_3m, 2)
        momentum  = round(
            data["chg_1d"] * 0.2 +
            data["chg_1w"] * 0.3 +
            data["chg_1m"] * 0.5,
            2
        )
        leadership = min(100, max(0, int(
            (rs_vs_spy * 2) + (momentum * 3) + (50 if data["above_ma"] else 0)
        ) + 50))

        rankings.append({
            "symbol":      sym,
            "price":       data["price"],
            "chg_1d":      data["chg_1d"],
            "chg_1m":      data["chg_1m"],
            "chg_3m":      data["chg_3m"],
            "rs_vs_spy":   rs_vs_spy,
            "momentum":    momentum,
            "leadership":  leadership,
            "above_ma50":  data["above_ma"],
        })
        time.sleep(0.15)

    rankings.sort(key=lambda x: x["leadership"], reverse=True)
    return rankings


def generate_ai_narrative(assets: dict, correlation: dict,
                           breadth: dict = None, rs_top: list = None) -> str:
    """Generate institutional AI market narrative."""
    spy    = assets.get("SPY", {})
    qqq    = assets.get("QQQ", {})
    xlk    = assets.get("XLK", {})
    xlf    = assets.get("XLF", {})
    quality = correlation.get("quality", "NEUTRAL")
    bscore  = breadth.get("overall_score", 50) if breadth else 50
    bqual   = breadth.get("overall_quality", "NEUTRAL") if breadth else "NEUTRAL"
    leaders = [x["symbol"] for x in (rs_top or [])[:5]]

    # Market regime interpretation
    if quality in ("STRONG_RISK_ON", "RISK_ON"):
        regime_text = "The market is in RISK-ON mode with broad institutional participation."
        swing_text  = "Environment is FAVORABLE for swing trades. Focus on momentum leaders."
        intraday    = "Intraday opportunities exist in high-momentum tech and growth names."
    elif quality == "NEUTRAL":
        regime_text = "The market is in a NEUTRAL phase with mixed cross-asset signals."
        swing_text  = "Swing setups require higher conviction scores. Be selective."
        intraday    = "Intraday: focus on individual stock catalysts over broad market plays."
    else:
        regime_text = "The market is showing RISK-OFF characteristics. Capital seeking safety."
        swing_text  = "Reduce swing exposure. Tighten stops. Prefer defensive sectors."
        intraday    = "Intraday: volatility elevated, reduce position sizes."

    # Liquidity analysis
    spy_chg  = spy.get("chg_1d", 0)
    qqq_chg  = qqq.get("chg_1d", 0)
    if spy_chg > 0.5 and qqq_chg > 0.5:
        liquidity_text = "Liquidity is FLOWING INTO equities. Broad buying across indices."
    elif spy_chg < -0.5:
        liquidity_text = "Liquidity is EXITING equities. Watch for support levels."
    else:
        liquidity_text = "Liquidity flow is BALANCED. Sector-specific rotation dominant."

    # Leading sectors
    sectors = []
    for s, name in [("XLK","Tech"), ("XLF","Financials"), ("XLE","Energy"),
                     ("XLV","Healthcare"), ("XLI","Industrials")]:
        d = assets.get(s, {})
        if d.get("chg_1d", 0) > 0.3:
            sectors.append(name)

    sector_text = f"Leading sectors: {', '.join(sectors[:3])}" if sectors else \
                  "No clear sector leadership today."

    narrative = f"""DAILY MARKET NARRATIVE — {datetime.now().strftime('%Y-%m-%d')}

REGIME: {quality}
{regime_text}

BREADTH: {bqual} ({bscore}/100)
Market breadth {'confirms' if bscore > 50 else 'diverges from'} price action.
{'Broad participation supports the trend.' if bscore > 60 else 'Narrow leadership — caution advised.'}

LIQUIDITY: {liquidity_text}

SECTOR LEADERSHIP: {sector_text}

INSTITUTIONAL LEADERS: {', '.join(leaders) if leaders else 'Data loading...'}

SWING ENVIRONMENT: {swing_text}
INTRADAY: {intraday}

HEALTH CHECK: {'✅ Market structure intact' if quality != 'STRONG_RISK_OFF' else '⚠️ Market under pressure — defensive posture recommended'}"""

    return narrative


def run_full_intelligence() -> dict:
    """Run complete market intelligence analysis."""
    log.info("Starting full market intelligence analysis...")
    start = time.time()

    # Fetch all assets
    assets_data = {}
    for key, info in ASSETS.items():
        ticker = info.get("ticker", key)
        data   = fetch_asset_data(ticker)
        if data:
            assets_data[key] = data
        time.sleep(0.2)

    # Build correlation matrix
    correlation = build_correlation_matrix(assets_data)

    # RS Rankings (top 20)
    rs_rankings = rank_rs(RS_UNIVERSE[:20])

    # Load breadth if available
    try:
        from breadth_engine import load_breadth
        breadth = load_breadth()
    except Exception:
        breadth = {}

    # Generate narrative
    narrative = generate_ai_narrative(assets_data, correlation, breadth, rs_rankings)

    result = {
        "timestamp":    datetime.now().isoformat(),
        "duration_sec": round(time.time() - start, 1),
        "assets":       assets_data,
        "correlation":  correlation,
        "rs_rankings":  rs_rankings[:20],
        "narrative":    narrative,
        "top_leaders":  rs_rankings[:10],
        "risk_quality": correlation.get("quality", "NEUTRAL"),
    }

    _save(result)
    log.info(f"Intelligence complete: {correlation['quality']} | {len(rs_rankings)} stocks ranked")
    return result


def _save(data: dict):
    try:
        with open(INTELLIGENCE_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        log.error(f"Save failed: {e}")


def load_intelligence() -> dict:
    try:
        if os.path.exists(INTELLIGENCE_FILE):
            with open(INTELLIGENCE_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def format_telegram_briefing(data: dict) -> str:
    """Format institutional morning briefing for Telegram."""
    corr    = data.get("correlation", {})
    leaders = data.get("top_leaders", [])[:5]
    assets  = data.get("assets", {})

    spy_chg = assets.get("SPY", {}).get("chg_1d", 0)
    qqq_chg = assets.get("QQQ", {}).get("chg_1d", 0)
    vix_chg = assets.get("VIX", {}).get("chg_1d", 0)
    gld_chg = assets.get("GLD", {}).get("chg_1d", 0)

    quality_emoji = {
        "STRONG_RISK_ON":  "🚀",
        "RISK_ON":         "🟢",
        "NEUTRAL":         "🟡",
        "RISK_OFF":        "🔴",
        "STRONG_RISK_OFF": "🚨",
    }.get(corr.get("quality", ""), "⚪")

    leaders_str = "\n".join(
        f"  {i+1}. {x['symbol']:6s} | RS:{x['rs_vs_spy']:+.1f}% | {x['chg_1m']:+.1f}%/mo"
        for i, x in enumerate(leaders)
    )

    narrative_short = data.get("narrative", "")[:400] + "..."

    return f"""
🏛️ <b>INSTITUTIONAL MORNING BRIEF</b>
{datetime.now().strftime('%Y-%m-%d %H:%M ET')}
{'━'*30}

{quality_emoji} Risk Quality: <b>{corr.get('quality','?')}</b>
Risk-On Score: {corr.get('risk_on_pct',50):.0f}%

<b>📊 CROSS-ASSET</b>
├ SPY:  {spy_chg:+.2f}%
├ QQQ:  {qqq_chg:+.2f}%
├ VIX:  {vix_chg:+.2f}%
└ Gold: {gld_chg:+.2f}%

<b>🏆 INSTITUTIONAL LEADERS (RS)</b>
{leaders_str}

<b>🤖 AI NARRATIVE</b>
<i>{narrative_short}</i>

{'━'*30}
⚠️ <i>Intelligence Only — No Auto Execution</i>""".strip()


if __name__ == "__main__":
    result = run_full_intelligence()
    print(f"\n✅ Risk Quality: {result['risk_quality']}")
    print(f"Top Leaders: {[x['symbol'] for x in result['top_leaders'][:5]]}")
    print(f"\nNARRATIVE:\n{result['narrative'][:500]}")
