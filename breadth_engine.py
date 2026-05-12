#!/usr/bin/env python3
"""
breadth_engine.py — Market Breadth Engine
INSTITUTIONAL MARKET INTELLIGENCE LAYER
Measures: A/D ratio, new highs/lows, % above MAs, breadth score.
"""

import os, json, time
from datetime import datetime
from typing import Optional

try:
    from logger import get_logger
    log = get_logger("breadth_engine")
except ImportError:
    import logging
    log = logging.getLogger("breadth_engine")
    logging.basicConfig(level=logging.INFO)

from dotenv import load_dotenv
load_dotenv("/root/.env")

BREADTH_FILE = "/root/logs/breadth_data.json"
os.makedirs("/root/logs", exist_ok=True)

# ── Universe for breadth sampling ────────────────────────────
SPY_COMPONENTS = [
    "AAPL","MSFT","NVDA","AMZN","META","GOOGL","GOOG","BRK-B","LLY","AVGO",
    "JPM","TSLA","UNH","V","XOM","MA","JNJ","PG","HD","COST",
    "MRK","ABBV","CVX","CRM","BAC","NFLX","AMD","PEP","KO","TMO",
    "WMT","ACN","MCD","LIN","CSCO","ABT","TXN","ADBE","PM","GE",
    "DHR","ISRG","CAT","INTU","QCOM","RTX","GS","VZ","SPGI","MS"
]

QQQ_COMPONENTS = [
    "AAPL","MSFT","NVDA","AMZN","META","GOOGL","GOOG","AVGO","TSLA","COST",
    "NFLX","AMD","ADBE","QCOM","TXN","INTU","ISRG","CSCO","AMAT","MU",
    "LRCX","KLAC","SNPS","CDNS","MRVL","PANW","CRWD","FTNT","DDOG","ZS"
]


def get_price_data(symbol: str) -> Optional[dict]:
    """Fetch price data using yfinance."""
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        hist   = ticker.history(period="1y")
        if hist.empty:
            return None
        current = float(hist["Close"].iloc[-1])
        ma50    = float(hist["Close"].tail(50).mean())
        ma200   = float(hist["Close"].tail(200).mean()) if len(hist) >= 200 else ma50
        prev    = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else current
        high52  = float(hist["Close"].max())
        low52   = float(hist["Close"].min())
        return {
            "symbol":  symbol,
            "price":   round(current, 2),
            "prev":    round(prev, 2),
            "ma50":    round(ma50, 2),
            "ma200":   round(ma200, 2),
            "high52":  round(high52, 2),
            "low52":   round(low52, 2),
            "change":  round((current - prev) / prev * 100, 2),
        }
    except Exception as e:
        log.error(f"Price fetch failed for {symbol}: {e}")
        return None


def calculate_breadth(universe: list, label: str = "SPY") -> dict:
    """Calculate breadth metrics for a universe of stocks."""
    log.info(f"Calculating breadth for {label} ({len(universe)} stocks)...")

    advances = declines = unchanged = 0
    above_50  = above_200 = 0
    new_highs = new_lows  = 0
    total     = 0

    for sym in universe[:30]:  # Limit for speed
        data = get_price_data(sym)
        if not data:
            continue
        total += 1

        # Advance/Decline
        if data["change"] > 0.1:    advances  += 1
        elif data["change"] < -0.1: declines  += 1
        else:                        unchanged += 1

        # Above MAs
        if data["price"] > data["ma50"]:   above_50  += 1
        if data["price"] > data["ma200"]:  above_200 += 1

        # New highs/lows (within 2% of 52w)
        if data["price"] >= data["high52"] * 0.98: new_highs += 1
        if data["price"] <= data["low52"]  * 1.02: new_lows  += 1

        time.sleep(0.1)  # Rate limit

    if total == 0:
        return {}

    pct_above_50  = round(above_50  / total * 100, 1)
    pct_above_200 = round(above_200 / total * 100, 1)
    ad_ratio      = round(advances  / total * 100, 1)

    # Breadth Score /100
    score = (
        pct_above_50  * 0.30 +
        pct_above_200 * 0.30 +
        ad_ratio      * 0.25 +
        min(100, new_highs / total * 200) * 0.15
    )

    # Breadth quality
    if score >= 70:   quality = "STRONG"
    elif score >= 50: quality = "NEUTRAL"
    elif score >= 30: quality = "WEAK"
    else:             quality = "BEARISH"

    return {
        "label":        label,
        "total":        total,
        "advances":     advances,
        "declines":     declines,
        "unchanged":    unchanged,
        "ad_ratio":     ad_ratio,
        "above_50ma":   pct_above_50,
        "above_200ma":  pct_above_200,
        "new_highs":    new_highs,
        "new_lows":     new_lows,
        "breadth_score":round(score, 1),
        "quality":      quality,
    }


def run_breadth_analysis() -> dict:
    """Full breadth analysis for SPY and QQQ."""
    log.info("Starting full breadth analysis...")
    start = time.time()

    spy_breadth = calculate_breadth(SPY_COMPONENTS, "SPY")
    qqq_breadth = calculate_breadth(QQQ_COMPONENTS[:20], "QQQ")

    # Combined score
    combined = 0
    count    = 0
    if spy_breadth:
        combined += spy_breadth.get("breadth_score", 0)
        count    += 1
    if qqq_breadth:
        combined += qqq_breadth.get("breadth_score", 0)
        count    += 1

    overall_score   = round(combined / count, 1) if count > 0 else 0
    overall_quality = (
        "STRONG"  if overall_score >= 70 else
        "NEUTRAL" if overall_score >= 50 else
        "WEAK"    if overall_score >= 30 else
        "BEARISH"
    )

    result = {
        "timestamp":       datetime.now().isoformat(),
        "duration_sec":    round(time.time() - start, 1),
        "spy":             spy_breadth,
        "qqq":             qqq_breadth,
        "overall_score":   overall_score,
        "overall_quality": overall_quality,
        "market_health":   _interpret_breadth(spy_breadth, qqq_breadth),
    }

    _save(result)
    log.info(f"Breadth analysis complete: {overall_quality} ({overall_score}/100)")
    return result


def _interpret_breadth(spy: dict, qqq: dict) -> str:
    """Generate market health interpretation."""
    spy_score = spy.get("breadth_score", 50)
    qqq_score = qqq.get("breadth_score", 50)
    avg       = (spy_score + qqq_score) / 2

    if avg >= 75:
        return "Market breadth is STRONG — broad participation, healthy rally"
    if avg >= 60:
        return "Market breadth is GOOD — majority of stocks participating"
    if avg >= 45:
        return "Market breadth is MIXED — selective leadership, proceed cautiously"
    if avg >= 30:
        return "Market breadth is WEAK — narrow leadership, risk increasing"
    return "Market breadth is BEARISH — distribution phase, defensive posture advised"


def _save(data: dict):
    try:
        with open(BREADTH_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        log.error(f"Save failed: {e}")


def load_breadth() -> dict:
    try:
        if os.path.exists(BREADTH_FILE):
            with open(BREADTH_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def format_telegram_breadth(data: dict) -> str:
    spy = data.get("spy", {})
    qqq = data.get("qqq", {})
    return f"""
📊 <b>MARKET BREADTH REPORT</b>
{datetime.now().strftime('%Y-%m-%d %H:%M ET')}
{'━'*28}

🏆 Overall: <b>{data.get('overall_quality','?')}</b> ({data.get('overall_score',0)}/100)

<b>SPY Breadth:</b>
├ A/D Ratio:    {spy.get('ad_ratio',0):.0f}% advancing
├ Above 50MA:   {spy.get('above_50ma',0):.0f}%
├ Above 200MA:  {spy.get('above_200ma',0):.0f}%
├ New Highs:    {spy.get('new_highs',0)}
└ Score:        {spy.get('breadth_score',0)}/100

<b>QQQ Breadth:</b>
├ A/D Ratio:    {qqq.get('ad_ratio',0):.0f}% advancing
├ Above 50MA:   {qqq.get('above_50ma',0):.0f}%
└ Score:        {qqq.get('breadth_score',0)}/100

💡 {data.get('market_health','')}
{'━'*28}
⚠️ <i>Intelligence Only</i>""".strip()


if __name__ == "__main__":
    result = run_breadth_analysis()
    print(f"\n✅ Breadth Score: {result['overall_score']}/100 — {result['overall_quality']}")
    print(f"SPY: {result['spy'].get('breadth_score','N/A')} | QQQ: {result['qqq'].get('breadth_score','N/A')}")
    print(f"Health: {result['market_health']}")
