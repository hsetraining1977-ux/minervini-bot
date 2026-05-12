#!/usr/bin/env python3
"""
smart_money.py — Smart Money Flow Detection
INSTITUTIONAL MARKET INTELLIGENCE LAYER
Detects: unusual volume, accumulation, distribution, institutional signatures.
"""

import os, json, time
from datetime import datetime, timedelta
from typing import Optional

try:
    from logger import get_logger
    log = get_logger("smart_money")
except ImportError:
    import logging
    log = logging.getLogger("smart_money")
    logging.basicConfig(level=logging.INFO)

from dotenv import load_dotenv
load_dotenv("/root/.env")

SMART_MONEY_FILE = "/root/logs/smart_money.json"
os.makedirs("/root/logs", exist_ok=True)

# ── Scan universe ─────────────────────────────────────────────
SCAN_UNIVERSE = [
    "NVDA","AMD","MSFT","AAPL","META","GOOGL","AMZN","TSLA","AVGO","ARM",
    "ANET","MRVL","CRWD","PANW","DDOG","NET","SNOW","SMCI","TSM","ASML",
    "LLY","UNH","V","MA","GS","JPM","MS","BX","KKR","ORCL"
]


def analyze_symbol(symbol: str) -> Optional[dict]:
    """Analyze a symbol for smart money signatures."""
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        hist   = ticker.history(period="60d")

        if len(hist) < 20:
            return None

        close   = hist["Close"]
        volume  = hist["Volume"]
        high    = hist["High"]
        low     = hist["Low"]

        current_price  = float(close.iloc[-1])
        avg_vol_20     = float(volume.tail(20).mean())
        today_vol      = float(volume.iloc[-1])
        vol_ratio      = round(today_vol / avg_vol_20, 2) if avg_vol_20 > 0 else 1.0

        # Price action
        price_5d_ago   = float(close.iloc[-5])
        price_change_5d = round((current_price - price_5d_ago) / price_5d_ago * 100, 2)

        # Accumulation/Distribution
        # Chaikin Money Flow approximation
        cmf_values = []
        for i in range(-10, 0):
            h = float(high.iloc[i])
            l = float(low.iloc[i])
            c = float(close.iloc[i])
            v = float(volume.iloc[i])
            if h != l:
                mfm = ((c - l) - (h - c)) / (h - l)
                cmf_values.append(mfm * v)

        cmf = sum(cmf_values) / (avg_vol_20 * 10) if avg_vol_20 > 0 else 0
        cmf = max(-1, min(1, cmf))

        # Up days on high volume vs down days on high volume
        up_vol   = 0
        down_vol = 0
        for i in range(-10, 0):
            day_change = float(close.iloc[i]) - float(close.iloc[i-1])
            day_vol    = float(volume.iloc[i])
            if day_change > 0: up_vol   += day_vol
            else:              down_vol += day_vol

        vol_pressure = "ACCUMULATION" if up_vol > down_vol * 1.2 else \
                       "DISTRIBUTION" if down_vol > up_vol * 1.2 else "NEUTRAL"

        # Unusual volume detection
        unusual_vol = vol_ratio >= 2.0

        # Institutional signature score
        inst_score = 0
        if vol_ratio >= 1.5:      inst_score += 20
        if vol_ratio >= 2.0:      inst_score += 15
        if cmf > 0.1:             inst_score += 20
        if vol_pressure == "ACCUMULATION": inst_score += 20
        if price_change_5d > 2:   inst_score += 15
        if price_change_5d > 5:   inst_score += 10
        inst_score = min(100, inst_score)

        # Signal
        if inst_score >= 70 and vol_pressure == "ACCUMULATION":
            signal = "STRONG_BUY"
        elif inst_score >= 50 and cmf > 0:
            signal = "ACCUMULATING"
        elif vol_pressure == "DISTRIBUTION" and cmf < -0.1:
            signal = "DISTRIBUTING"
        elif inst_score >= 40:
            signal = "WATCH"
        else:
            signal = "NEUTRAL"

        return {
            "symbol":        symbol,
            "price":         round(current_price, 2),
            "vol_ratio":     vol_ratio,
            "unusual_vol":   unusual_vol,
            "vol_pressure":  vol_pressure,
            "cmf":           round(cmf, 3),
            "price_5d_chg":  price_change_5d,
            "inst_score":    inst_score,
            "signal":        signal,
        }

    except Exception as e:
        log.error(f"Smart money analysis failed for {symbol}: {e}")
        return None


def run_smart_money_scan(universe: list = None) -> dict:
    """Full smart money scan across universe."""
    if universe is None:
        universe = SCAN_UNIVERSE

    log.info(f"Running smart money scan on {len(universe)} symbols...")
    results   = []
    start     = time.time()

    for sym in universe:
        data = analyze_symbol(sym)
        if data:
            results.append(data)
        time.sleep(0.2)

    # Sort by institutional score
    results.sort(key=lambda x: x["inst_score"], reverse=True)

    # Categorize
    strong_buy    = [r for r in results if r["signal"] == "STRONG_BUY"]
    accumulating  = [r for r in results if r["signal"] == "ACCUMULATING"]
    distributing  = [r for r in results if r["signal"] == "DISTRIBUTING"]
    unusual_vols  = [r for r in results if r["unusual_vol"]]

    # Overall flow
    acc_count  = len(accumulating) + len(strong_buy)
    dist_count = len(distributing)
    total      = len(results)

    if acc_count > dist_count * 1.5:
        flow_bias = "INSTITUTIONAL_BUYING"
    elif dist_count > acc_count * 1.5:
        flow_bias = "INSTITUTIONAL_SELLING"
    else:
        flow_bias = "MIXED_FLOW"

    output = {
        "timestamp":     datetime.now().isoformat(),
        "duration_sec":  round(time.time() - start, 1),
        "scanned":       total,
        "flow_bias":     flow_bias,
        "strong_buy":    strong_buy[:5],
        "accumulating":  accumulating[:5],
        "distributing":  distributing[:5],
        "unusual_volume":unusual_vols[:5],
        "top_leaders":   results[:10],
        "summary":       _summarize(flow_bias, strong_buy, accumulating, distributing),
    }

    _save(output)
    log.info(f"Smart money scan done: {flow_bias} | {acc_count} acc vs {dist_count} dist")
    return output


def _summarize(flow: str, strong: list, acc: list, dist: list) -> str:
    sb  = ", ".join(x["symbol"] for x in strong[:3])
    ac  = ", ".join(x["symbol"] for x in acc[:3])
    di  = ", ".join(x["symbol"] for x in dist[:3])

    if flow == "INSTITUTIONAL_BUYING":
        msg = f"Smart money is BUYING. Leaders: {sb or ac}."
    elif flow == "INSTITUTIONAL_SELLING":
        msg = f"Smart money is SELLING. Under pressure: {di}."
    else:
        msg = f"Mixed institutional flow. Buyers: {sb or ac}. Sellers: {di}."

    return msg


def _save(data: dict):
    try:
        with open(SMART_MONEY_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        log.error(f"Save failed: {e}")


def load_smart_money() -> dict:
    try:
        if os.path.exists(SMART_MONEY_FILE):
            with open(SMART_MONEY_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def format_telegram_smart_money(data: dict) -> str:
    strong = data.get("strong_buy", [])
    acc    = data.get("accumulating", [])
    dist   = data.get("distributing", [])
    uv     = data.get("unusual_volume", [])

    sb_str = "\n".join(
        f"  ✦ {x['symbol']} | Score:{x['inst_score']} | Vol:{x['vol_ratio']}x"
        for x in strong[:3]
    ) or "  None detected"

    dist_str = "\n".join(
        f"  ⚠ {x['symbol']} | CMF:{x['cmf']:.2f}"
        for x in dist[:3]
    ) or "  None detected"

    uv_str = ", ".join(x["symbol"] for x in uv[:5]) or "None"

    flow_emoji = {
        "INSTITUTIONAL_BUYING":  "🟢",
        "INSTITUTIONAL_SELLING": "🔴",
        "MIXED_FLOW":            "🟡",
    }.get(data.get("flow_bias", ""), "⚪")

    return f"""
💰 <b>SMART MONEY FLOW</b>
{datetime.now().strftime('%Y-%m-%d %H:%M ET')}
{'━'*28}

{flow_emoji} Flow Bias: <b>{data.get('flow_bias','?')}</b>
Scanned: {data.get('scanned',0)} symbols

<b>🏆 STRONG BUY Signals</b>
{sb_str}

<b>⚠️ DISTRIBUTION Signals</b>
{dist_str}

<b>⚡ Unusual Volume</b>
{uv_str}

💡 {data.get('summary','')}
{'━'*28}
⚠️ <i>Intelligence Only — No Auto Execution</i>""".strip()


if __name__ == "__main__":
    result = run_smart_money_scan(SCAN_UNIVERSE[:10])
    print(f"\n✅ Flow Bias: {result['flow_bias']}")
    print(f"Strong Buy: {[x['symbol'] for x in result['strong_buy']]}")
    print(f"Summary: {result['summary']}")
