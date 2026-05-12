"""
data_sources.py
===============
مصادر البيانات الشاملة — يعالج كل النواقص في ملف واحد

المصادر المجانية:
✅ FRED API    — GDP, CPI, NFP, الفائدة، بيانات الفيدرالي
✅ Finnhub     — أخبار حقيقية + Earnings + Insider
✅ Alpha Vantage — Economic Calendar + أخبار
✅ CFTC/Quandl — COT Report الحقيقي
✅ yfinance    — الأسعار + البيانات المالية (موجود)

ثم يربط كل شيء بـ decision_engine تلقائياً
"""

import yfinance as yf
import pandas as pd
import numpy as np
import requests
import json
import time
import os
from datetime import datetime, timedelta
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

# ─── API Keys (مجانية — سجّل وأضفها) ────────────────────────────────────────
# FRED: https://fred.stlouisfed.org/docs/api/api_key.html
from config import FRED_API_KEY

# Finnhub: https://finnhub.io (Free tier)
try:
    from config import FINNHUB_API_KEY
except:
    FINNHUB_API_KEY = ""

# Alpha Vantage: https://www.alphavantage.co/support/#api-key
try:
    from config import ALPHA_VANTAGE_KEY
except:
    ALPHA_VANTAGE_KEY = ""

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
# ١. FRED API — البيانات الاقتصادية الأمريكية الرسمية
# ═══════════════════════════════════════════════════════════════════════════════

FRED_SERIES = {
    "CPI":         "CPIAUCSL",    # مؤشر أسعار المستهلك
    "CORE_CPI":    "CPILFESL",    # CPI الأساسي (بدون طاقة وغذاء)
    "PPI":         "PPIACO",      # مؤشر أسعار المنتجين
    "GDP":         "GDP",         # الناتج المحلي الإجمالي
    "UNEMPLOYMENT":"UNRATE",      # معدل البطالة
    "FED_RATE":    "FEDFUNDS",    # سعر الفائدة الفيدرالي
    "M2":          "M2SL",        # عرض النقود M2
    "RETAIL":      "RSAFS",       # مبيعات التجزئة
    "HOUSING":     "HOUST",       # مبدوءات البناء
    "CONSUMER_SENT": "UMCSENT",   # ثقة المستهلك
    "ISM_MFG":     "MANEMP",      # التوظيف في التصنيع
    "YIELD_10Y":   "GS10",        # عائد سندات 10 سنوات
    "YIELD_2Y":    "GS2",         # عائد سندات 2 سنوات
    "YIELD_SPREAD":"T10Y2Y",      # الفرق بين 10Y و 2Y
    "REAL_GDP":    "GDPC1",       # GDP الحقيقي
}

def fetch_fred_series(series_id: str, limit: int = 12) -> dict:
    """يجلب بيانات من FRED API"""
    if not FRED_API_KEY:
        return {"error": "FRED_API_KEY غير موجود"}

    try:
        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            "series_id":     series_id,
            "api_key":       FRED_API_KEY,
            "file_type":     "json",
            "sort_order":    "desc",
            "limit":         limit,
            "observation_end": datetime.now().strftime("%Y-%m-%d"),
        }
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()

        if "observations" not in data:
            return {"error": f"لا بيانات لـ {series_id}"}

        obs = [o for o in data["observations"] if o["value"] != "."]
        if not obs:
            return {"error": "لا قيم متاحة"}

        latest = float(obs[0]["value"])
        prev   = float(obs[1]["value"]) if len(obs) > 1 else latest
        change = latest - prev
        change_pct = (change / abs(prev) * 100) if prev != 0 else 0

        return {
            "series_id": series_id,
            "latest":    round(latest, 3),
            "previous":  round(prev, 3),
            "change":    round(change, 3),
            "change_pct": round(change_pct, 2),
            "date":      obs[0]["date"],
            "history":   [(o["date"], float(o["value"])) for o in obs[:6]],
        }

    except Exception as e:
        return {"error": str(e)}

def fetch_all_fred_data() -> dict:
    """يجلب كل البيانات الاقتصادية من FRED"""
    print("\n[FRED] جلب البيانات الاقتصادية الأمريكية...")
    results = {}

    for name, series_id in FRED_SERIES.items():
        data = fetch_fred_series(series_id)
        if "error" not in data:
            results[name] = data
            print(f"  ✅ {name}: {data['latest']} ({data['change_pct']:+.2f}%)")
        else:
            print(f"  ❌ {name}: {data['error']}")
        time.sleep(0.2)

    return results

def analyze_fred_data(fred_data: dict) -> dict:
    """يحلل بيانات FRED ويعطي توصيات"""
    analysis = {
        "economic_phase": "غير محدد",
        "fed_direction":  "محايد",
        "inflation_trend": "محايد",
        "score":          0,
        "signals":        [],
        "sector_rotation": [],
    }

    if not fred_data:
        return analysis

    score = 0

    # ─── CPI — التضخم ──────────────────────────────────────────────────────
    if "CPI" in fred_data:
        cpi = fred_data["CPI"]
        cpi_yoy = cpi["change_pct"]

        if cpi_yoy < 2.5:
            score += 2
            analysis["signals"].append(f"✅ CPI منخفض ({cpi_yoy:+.1f}%) — بيئة ممتازة")
            analysis["inflation_trend"] = "منخفض — داعم للأسهم"
        elif cpi_yoy > 4:
            score -= 2
            analysis["signals"].append(f"🔴 CPI مرتفع ({cpi_yoy:+.1f}%) — ضغط على الأسهم")
            analysis["inflation_trend"] = "مرتفع — خطر على التكنولوجيا"
        else:
            analysis["signals"].append(f"⚪ CPI معتدل ({cpi_yoy:+.1f}%)")
            analysis["inflation_trend"] = "معتدل"

    # ─── سعر الفائدة الفيدرالي ──────────────────────────────────────────────
    if "FED_RATE" in fred_data:
        fed = fred_data["FED_RATE"]
        fed_rate = fed["latest"]
        fed_change = fed["change"]

        if fed_change < 0:
            score += 3
            analysis["fed_direction"] = "خفض فائدة 🟢🟢"
            analysis["signals"].append(f"✅ الفيدرالي يخفض الفائدة ({fed_rate:.2f}%)")
            analysis["sector_rotation"].extend(["التكنولوجيا", "أشباه الموصلات", "النمو"])
        elif fed_change > 0:
            score -= 2
            analysis["fed_direction"] = "رفع فائدة 🔴"
            analysis["signals"].append(f"🔴 الفيدرالي يرفع الفائدة ({fed_rate:.2f}%)")
            analysis["sector_rotation"].extend(["الطاقة", "البنوك", "الدفاعيات"])
        else:
            analysis["fed_direction"] = "ثبات ⚪"
            analysis["signals"].append(f"⚪ الفيدرالي يثبت الفائدة ({fed_rate:.2f}%)")

    # ─── GDP ─────────────────────────────────────────────────────────────────
    if "GDP" in fred_data:
        gdp = fred_data["GDP"]
        if gdp["change_pct"] > 2:
            score += 2
            analysis["signals"].append(f"✅ GDP ينمو ({gdp['change_pct']:+.1f}%)")
        elif gdp["change_pct"] < 0:
            score -= 3
            analysis["signals"].append(f"🔴 GDP ينكمش ({gdp['change_pct']:+.1f}%) — خطر ركود")

    # ─── البطالة ─────────────────────────────────────────────────────────────
    if "UNEMPLOYMENT" in fred_data:
        unemp = fred_data["UNEMPLOYMENT"]
        if unemp["latest"] < 4.5:
            score += 1
            analysis["signals"].append(f"✅ بطالة منخفضة ({unemp['latest']:.1f}%)")
        elif unemp["latest"] > 6:
            score -= 2
            analysis["signals"].append(f"🔴 بطالة مرتفعة ({unemp['latest']:.1f}%)")

    # ─── منحنى العائد ────────────────────────────────────────────────────────
    if "YIELD_SPREAD" in fred_data:
        spread = fred_data["YIELD_SPREAD"]
        if spread["latest"] < 0:
            score -= 2
            analysis["signals"].append(f"🚨 Yield Curve مقلوب ({spread['latest']:.2f}%) — خطر ركود")
        elif spread["latest"] > 1:
            score += 1
            analysis["signals"].append(f"✅ Yield Curve طبيعي (+{spread['latest']:.2f}%)")

    # ─── M2 — عرض النقود ─────────────────────────────────────────────────────
    if "M2" in fred_data:
        m2 = fred_data["M2"]
        if m2["change_pct"] > 5:
            score += 1
            analysis["signals"].append(f"✅ M2 ينمو ({m2['change_pct']:+.1f}%) — سيولة كافية")
        elif m2["change_pct"] < -2:
            score -= 1
            analysis["signals"].append(f"⚠️ M2 يتقلص ({m2['change_pct']:+.1f}%) — ضغط على السيولة")

    analysis["score"] = score

    # تحديد المرحلة الاقتصادية
    if score >= 6:
        analysis["economic_phase"] = "توسع قوي 🚀 — اشتر النمو بجرأة"
    elif score >= 3:
        analysis["economic_phase"] = "نمو معتدل 📈 — انتقائي في النمو"
    elif score >= 0:
        analysis["economic_phase"] = "محايد ⚖️ — ركز على الجودة"
    elif score >= -3:
        analysis["economic_phase"] = "تباطؤ ⚠️ — قلل المخاطر"
    else:
        analysis["economic_phase"] = "ركود محتمل 🔴 — دفاعيات + كاش"

    return analysis

# ═══════════════════════════════════════════════════════════════════════════════
# ٢. Finnhub — أخبار + Earnings + Insider حقيقي
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_finnhub_news(symbol: str, days: int = 7) -> list:
    """يجلب أخبار السهم من Finnhub"""
    if not FINNHUB_API_KEY:
        return []

    try:
        end   = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        url   = f"https://finnhub.io/api/v1/company-news"
        params = {
            "symbol": symbol,
            "from":   start,
            "to":     end,
            "token":  FINNHUB_API_KEY,
        }
        resp = requests.get(url, params=params, timeout=10)
        news = resp.json()

        if isinstance(news, list):
            return [{"headline": n.get("headline", ""), "source": n.get("source", ""), "datetime": n.get("datetime", 0)} for n in news[:10]]
        return []

    except Exception as e:
        return []

def fetch_finnhub_earnings(symbol: str) -> dict:
    """يجلب تفاصيل الأرباح من Finnhub"""
    if not FINNHUB_API_KEY:
        return {}

    try:
        url    = f"https://finnhub.io/api/v1/stock/earnings"
        params = {"symbol": symbol, "limit": 4, "token": FINNHUB_API_KEY}
        resp   = requests.get(url, params=params, timeout=10)
        data   = resp.json()

        if not data:
            return {}

        latest = data[0] if data else {}
        actual   = latest.get("actual", None)
        estimate = latest.get("estimate", None)
        surprise = latest.get("surprisePercent", None)

        return {
            "actual":       actual,
            "estimate":     estimate,
            "surprise_pct": round(surprise, 1) if surprise else None,
            "beat":         actual > estimate if (actual and estimate) else None,
            "period":       latest.get("period", ""),
        }

    except Exception as e:
        return {}

def fetch_finnhub_insider(symbol: str) -> list:
    """يجلب نشاط المديرين التنفيذيين من Finnhub"""
    if not FINNHUB_API_KEY:
        return []

    try:
        url    = f"https://finnhub.io/api/v1/stock/insider-transactions"
        params = {"symbol": symbol, "token": FINNHUB_API_KEY}
        resp   = requests.get(url, params=params, timeout=10)
        data   = resp.json()

        transactions = data.get("data", []) if isinstance(data, dict) else []
        recent = []
        cutoff = datetime.now() - timedelta(days=90)

        for t in transactions[:20]:
            try:
                t_date = datetime.strptime(t.get("transactionDate", ""), "%Y-%m-%d")
                if t_date >= cutoff:
                    recent.append({
                        "name":   t.get("name", ""),
                        "action": t.get("transactionCode", ""),
                        "shares": t.get("share", 0),
                        "value":  t.get("transactionPrice", 0),
                        "date":   t.get("transactionDate", ""),
                    })
            except:
                pass

        return recent

    except Exception as e:
        return []

def fetch_finnhub_earnings_calendar() -> list:
    """يجلب تقويم أرباح الشركات القادمة"""
    if not FINNHUB_API_KEY:
        return []

    try:
        end   = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
        start = datetime.now().strftime("%Y-%m-%d")
        url   = "https://finnhub.io/api/v1/calendar/earnings"
        params = {"from": start, "to": end, "token": FINNHUB_API_KEY}
        resp  = requests.get(url, params=params, timeout=10)
        data  = resp.json()

        earnings = data.get("earningsCalendar", []) if isinstance(data, dict) else []
        return [
            {
                "symbol":   e.get("symbol", ""),
                "date":     e.get("date", ""),
                "eps_est":  e.get("epsEstimate", None),
                "rev_est":  e.get("revenueEstimate", None),
            }
            for e in earnings
            if e.get("symbol", "") in [
                "NVDA","MSFT","AAPL","GOOGL","META","AMZN",
                "AVGO","AMD","CRWD","PANW","PLTR","NOW",
                "TSLA","V","MA","LLY","COST"
            ]
        ]

    except Exception as e:
        return []

def analyze_finnhub_sentiment(symbol: str) -> dict:
    """يحلل معنويات السهم من الأخبار والـ Insider"""
    result = {
        "symbol":    symbol,
        "sentiment": "محايد",
        "score":     0,
        "news_count": 0,
        "insider_buying": False,
        "earnings_beat":  None,
    }

    # أخبار
    news = fetch_finnhub_news(symbol)
    result["news_count"] = len(news)

    positive_words = ["beat", "surge", "record", "growth", "upgrade", "strong", "profit"]
    negative_words = ["miss", "decline", "loss", "weak", "downgrade", "lawsuit", "cut"]

    pos = neg = 0
    for n in news:
        title = n["headline"].lower()
        pos += sum(1 for w in positive_words if w in title)
        neg += sum(1 for w in negative_words if w in title)

    score = (pos - neg)

    # Insider
    insider = fetch_finnhub_insider(symbol)
    buys  = [t for t in insider if t["action"] in ["P", "A"]]
    sells = [t for t in insider if t["action"] in ["S", "D"]]
    if len(buys) > len(sells):
        score += 2
        result["insider_buying"] = True

    # Earnings
    earnings = fetch_finnhub_earnings(symbol)
    if earnings.get("beat"):
        score += 2
        result["earnings_beat"] = True
    elif earnings.get("beat") is False:
        score -= 1
        result["earnings_beat"] = False

    result["score"] = score
    result["sentiment"] = (
        "إيجابي قوي 🟢🟢" if score >= 4 else
        "إيجابي 🟢"        if score >= 2 else
        "سلبي 🔴"          if score <= -2 else
        "محايد ⚪"
    )

    print(f"[Finnhub] {symbol}: Sentiment={result['sentiment']} | News={len(news)} | Insider={'شراء' if result['insider_buying'] else 'طبيعي'}")
    return result

# ═══════════════════════════════════════════════════════════════════════════════
# ٣. Alpha Vantage — Economic Calendar + أخبار السوق
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_alpha_economic_calendar() -> list:
    """يجلب تقويم الأحداث الاقتصادية من Alpha Vantage"""
    if not ALPHA_VANTAGE_KEY:
        return []

    try:
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "ECONOMIC_CALENDAR",
            "horizon":  "3month",
            "apikey":   ALPHA_VANTAGE_KEY,
        }
        resp  = requests.get(url, params=params, timeout=10)
        data  = resp.json()

        events = []
        for event in data if isinstance(data, list) else []:
            try:
                event_date = datetime.strptime(event.get("date", ""), "%Y-%m-%d")
                days_until = (event_date - datetime.now()).days
                if 0 <= days_until <= 14:
                    events.append({
                        "event":      event.get("event", ""),
                        "date":       event.get("date", ""),
                        "days_until": days_until,
                        "country":    event.get("country", ""),
                        "impact":     event.get("impact", ""),
                        "forecast":   event.get("forecast", ""),
                        "previous":   event.get("previous", ""),
                    })
            except:
                pass

        return sorted(events, key=lambda x: x["days_until"])

    except Exception as e:
        return []

def fetch_alpha_news_sentiment(symbol: str) -> dict:
    """يجلب تحليل Sentiment الأخبار من Alpha Vantage"""
    if not ALPHA_VANTAGE_KEY:
        return {}

    try:
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "NEWS_SENTIMENT",
            "tickers":  symbol,
            "limit":    20,
            "apikey":   ALPHA_VANTAGE_KEY,
        }
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()

        feed = data.get("feed", [])
        if not feed:
            return {}

        scores = []
        for article in feed[:10]:
            for ticker in article.get("ticker_sentiment", []):
                if ticker.get("ticker") == symbol:
                    score = float(ticker.get("ticker_sentiment_score", 0))
                    scores.append(score)

        if not scores:
            return {}

        avg_score = np.mean(scores)
        return {
            "symbol":     symbol,
            "avg_score":  round(avg_score, 3),
            "articles":   len(feed),
            "sentiment":  (
                "Bullish 🟢" if avg_score > 0.15 else
                "Bearish 🔴" if avg_score < -0.15 else
                "Neutral ⚪"
            ),
        }

    except Exception as e:
        return {}

# ═══════════════════════════════════════════════════════════════════════════════
# ٤. CFTC COT Report — مراكز البنوك الكبرى الحقيقية
# ═══════════════════════════════════════════════════════════════════════════════

COT_ASSETS = {
    "S&P 500": "13874+",
    "Nasdaq":  "209742",
    "Gold":    "088691",
    "Oil":     "067651",
    "Dollar":  "098662",
}

def fetch_cot_report() -> dict:
    """
    يجلب تقرير COT الحقيقي من CFTC
    يُنشر كل جمعة — يُظهر مراكز البنوك والمؤسسات
    """
    print("\n[COT] جلب تقرير Commitment of Traders...")
    result = {}

    try:
        url = "https://www.cftc.gov/dea/newcot/f_disagg.txt"
        resp = requests.get(url, timeout=15)

        if resp.status_code != 200:
            return {"error": "فشل جلب COT"}

        lines = resp.text.split('\n')

        for asset_name, asset_code in COT_ASSETS.items():
            for line in lines:
                if asset_code in line:
                    parts = line.split(',')
                    if len(parts) > 20:
                        try:
                            comm_long  = int(parts[8].strip().replace('"', ''))
                            comm_short = int(parts[9].strip().replace('"', ''))
                            non_comm_long  = int(parts[5].strip().replace('"', ''))
                            non_comm_short = int(parts[6].strip().replace('"', ''))

                            comm_net     = comm_long - comm_short
                            non_comm_net = non_comm_long - non_comm_short

                            result[asset_name] = {
                                "commercial_net":     comm_net,
                                "non_commercial_net": non_comm_net,
                                "commercial_bias":    "شراء 🟢" if comm_net > 0 else "بيع 🔴",
                                "spec_bias":          "شراء 🟢" if non_comm_net > 0 else "بيع 🔴",
                            }
                            print(f"  {asset_name}: Commercial={'شراء' if comm_net > 0 else 'بيع'} ({comm_net:+,})")
                        except:
                            pass
                    break

    except Exception as e:
        print(f"[COT] خطأ: {e}")
        return {"error": str(e)}

    return result

# ═══════════════════════════════════════════════════════════════════════════════
# ٥. ربط كل شيء بـ Decision Engine
# ═══════════════════════════════════════════════════════════════════════════════

def comprehensive_data_score(symbol: str, fred_analysis: dict = None) -> dict:
    """
    يجمع كل مصادر البيانات في نقاط واحدة
    تُستخدم في decision_engine لقرار الشراء
    """
    result = {
        "symbol":       symbol,
        "total_score":  0,
        "allowed":      True,
        "blocks":       [],
        "reasons":      [],
        "data_quality": "yfinance فقط",
    }

    score = 0

    # ─── FRED Analysis ──────────────────────────────────────────────────────
    if fred_analysis:
        fred_score = fred_analysis.get("score", 0)
        score += fred_score // 2

        phase = fred_analysis.get("economic_phase", "")
        if "ركود" in phase:
            result["blocks"].append("❌ FRED: خطر ركود اقتصادي")
            result["allowed"] = False
        elif "توسع" in phase or "نمو" in phase:
            result["reasons"].append(f"✅ FRED: {phase}")
        result["data_quality"] = "FRED + yfinance"

    # ─── Finnhub Sentiment ──────────────────────────────────────────────────
    if FINNHUB_API_KEY:
        sentiment = analyze_finnhub_sentiment(symbol)
        finn_score = sentiment.get("score", 0)
        score += finn_score // 2

        if sentiment.get("insider_buying"):
            score += 1
            result["reasons"].append("✅ Insider شراء مؤخراً")

        if sentiment.get("earnings_beat") is False:
            score -= 1
            result["reasons"].append("⚠️ أرباح أقل من التوقعات")
        elif sentiment.get("earnings_beat"):
            score += 1
            result["reasons"].append("✅ أرباح تجاوزت التوقعات")

        result["data_quality"] += " + Finnhub"

    # ─── Alpha Vantage News ──────────────────────────────────────────────────
    if ALPHA_VANTAGE_KEY:
        alpha_sent = fetch_alpha_news_sentiment(symbol)
        if alpha_sent:
            alpha_score = alpha_sent.get("avg_score", 0)
            if alpha_score > 0.15:
                score += 1
                result["reasons"].append(f"✅ Alpha Vantage: {alpha_sent['sentiment']}")
            elif alpha_score < -0.15:
                score -= 1
                result["reasons"].append(f"⚠️ Alpha Vantage: {alpha_sent['sentiment']}")
        result["data_quality"] += " + Alpha Vantage"

    result["total_score"] = score

    if score < -2:
        result["allowed"] = False
        result["blocks"].append(f"❌ نقاط سلبية من مصادر البيانات: {score}")

    return result

def update_decision_engine_with_data(symbol: str, fred_analysis: dict = None) -> bool:
    """
    يحدّث قرار decision_engine بناءً على مصادر البيانات الخارجية
    يُحفظ في ملف JSON يقرأه decision_engine
    """
    data_score = comprehensive_data_score(symbol, fred_analysis)

    try:
        # تحميل الملف الموجود
        try:
            with open("/root/data_scores.json", encoding="utf-8") as f:
                all_scores = json.load(f)
        except:
            all_scores = {}

        all_scores[symbol] = {
            **data_score,
            "timestamp": str(datetime.now()),
        }

        with open("/root/data_scores.json", "w", encoding="utf-8") as f:
            json.dump(all_scores, f, ensure_ascii=False, indent=2)

        return data_score["allowed"]

    except Exception as e:
        print(f"[DataScore] خطأ: {e}")
        return True

# ═══════════════════════════════════════════════════════════════════════════════
# ٦. تحديث decision_engine ليقرأ data_scores.json
# ═══════════════════════════════════════════════════════════════════════════════

DECISION_ENGINE_PATCH = '''
# ─── إضافة لـ decision_engine.py ────────────────────────────────────────────
# ضع هذه الدالة في decision_engine.py

def check_data_sources(symbol: str) -> tuple:
    """يفحص نتيجة مصادر البيانات الخارجية"""
    try:
        with open("/root/data_scores.json", encoding="utf-8") as f:
            scores = json.load(f)
        
        if symbol in scores:
            data = scores[symbol]
            # تحقق من أن البيانات ليست قديمة (أكثر من 24 ساعة)
            timestamp = datetime.fromisoformat(data["timestamp"])
            if (datetime.now() - timestamp).hours > 24:
                return True, "بيانات قديمة — نتجاهلها"
            
            if not data["allowed"]:
                return False, " | ".join(data["blocks"])
            return True, f"مصادر البيانات: {data['data_quality']}"
    except:
        pass
    return True, "لا بيانات خارجية — نتجاهل"

# أضف هذا السطر في دالة should_buy() بعد فحص الـ Earnings Risk:
# data_ok, data_reason = check_data_sources(symbol)
# if data_ok:
#     result["score"] += 1
#     result["reasons"].append(f"✅ {data_reason}")
# else:
#     result["allowed"] = False
#     result["blocks"].append(f"❌ {data_reason}")
'''

# ═══════════════════════════════════════════════════════════════════════════════
# ٧. التقرير الشامل من كل المصادر
# ═══════════════════════════════════════════════════════════════════════════════

def send_data_sources_report(fred_data: dict, fred_analysis: dict,
                              cot_data: dict, calendar: list):
    msg = (
        f"🌐 <b>Data Sources Report</b>\n"
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"{'─'*28}\n\n"
    )

    # FRED
    if fred_analysis:
        msg += (
            f"<b>FRED — الاقتصاد الأمريكي:</b>\n"
            f"المرحلة: {fred_analysis.get('economic_phase', 'N/A')}\n"
            f"الفيدرالي: {fred_analysis.get('fed_direction', 'N/A')}\n"
            f"التضخم: {fred_analysis.get('inflation_trend', 'N/A')}\n\n"
        )

        if fred_data.get("CPI"):
            msg += f"CPI: {fred_data['CPI']['latest']} ({fred_data['CPI']['change_pct']:+.1f}%)\n"
        if fred_data.get("FED_RATE"):
            msg += f"الفائدة: {fred_data['FED_RATE']['latest']:.2f}%\n"
        if fred_data.get("UNEMPLOYMENT"):
            msg += f"البطالة: {fred_data['UNEMPLOYMENT']['latest']:.1f}%\n"
        if fred_data.get("YIELD_SPREAD"):
            spread = fred_data['YIELD_SPREAD']['latest']
            msg += f"Yield Curve: {spread:+.2f}% {'⚠️ مقلوب' if spread < 0 else '✅ طبيعي'}\n"

    # COT
    if cot_data and "error" not in cot_data:
        msg += f"\n<b>COT — مراكز المؤسسات:</b>\n"
        for asset, data in list(cot_data.items())[:4]:
            msg += f"• {asset}: {data['commercial_bias']}\n"

    # Calendar
    if calendar:
        msg += f"\n<b>أحداث اقتصادية قادمة:</b>\n"
        for ev in calendar[:4]:
            impact_emoji = "🚨" if ev.get("impact", "").lower() == "high" else "📌"
            msg += f"{impact_emoji} {ev['event']} — بعد {ev['days_until']} يوم\n"

    send_telegram(msg)

# ═══════════════════════════════════════════════════════════════════════════════
# الإعداد الأولي — كيف تحصل على API Keys
# ═══════════════════════════════════════════════════════════════════════════════

def setup_api_keys():
    """يساعد في إعداد API Keys"""
    print("\n" + "="*60)
    print("  إعداد API Keys — كلها مجانية!")
    print("="*60)
    print("""
١. FRED API (بيانات الاقتصاد الأمريكي الرسمية):
   → https://fred.stlouisfed.org/docs/api/api_key.html
   → سجّل وستحصل على Key فوراً
   → أضفه: export FRED_API_KEY="your_key_here"

٢. Finnhub (أخبار + Earnings + Insider):
   → https://finnhub.io
   → Free tier: 60 calls/minute
   → أضفه: export FINNHUB_API_KEY="your_key_here"

٣. Alpha Vantage (Economic Calendar + News Sentiment):
   → https://www.alphavantage.co/support/#api-key
   → Free tier: 25 calls/day
   → أضفه: export ALPHA_VANTAGE_KEY="your_key_here"

بعد الحصول على الـ Keys، أضفها في /root/config.py:
   FRED_API_KEY = "your_fred_key"
   FINNHUB_API_KEY = "your_finnhub_key"
   ALPHA_VANTAGE_KEY = "your_alpha_key"
""")

# ═══════════════════════════════════════════════════════════════════════════════
# الحلقة الرئيسية
# ═══════════════════════════════════════════════════════════════════════════════

def run_data_sources():
    """تشغيل مصادر البيانات بجدول زمني"""
    print("=" * 55)
    print("  Data Sources Engine — كل المصادر")
    print("=" * 55)

    has_fred    = bool(FRED_API_KEY)
    has_finnhub = bool(FINNHUB_API_KEY)
    has_alpha   = bool(ALPHA_VANTAGE_KEY)

    send_telegram(
        f"🌐 <b>Data Sources يعمل!</b>\n"
        f"─"*20 + "\n"
        f"{'✅' if has_fred else '❌'} FRED API\n"
        f"{'✅' if has_finnhub else '❌'} Finnhub\n"
        f"{'✅' if has_alpha else '❌'} Alpha Vantage\n"
        f"✅ COT Report (CFTC)\n"
        f"✅ yfinance\n\n"
        f"{'⚠️ أضف API Keys لتفعيل كل المصادر' if not (has_fred and has_finnhub) else '🏆 كل المصادر مفعّلة!'}"
    )

    last_fred    = None
    last_cot     = None
    last_scores  = None

    while True:
        try:
            now   = datetime.now()
            today = now.date()

            # FRED + COT — كل يوم 6 صباحاً
            if now.hour == 6 and now.minute < 10 and last_fred != today:
                fred_data     = fetch_all_fred_data()
                fred_analysis = analyze_fred_data(fred_data)
                cot_data      = fetch_cot_report()
                calendar      = fetch_alpha_economic_calendar() if has_alpha else []

                # حفظ حالة FRED
                with open("/root/fred_state.json", "w", encoding="utf-8") as f:
                    json.dump({
                        "timestamp": str(now),
                        "fred_data": fred_data,
                        "analysis":  fred_analysis,
                        "cot":       cot_data,
                    }, f, ensure_ascii=False, indent=2, default=str)

                send_data_sources_report(fred_data, fred_analysis, cot_data, calendar)
                last_fred = today

            # تحديث نقاط الأسهم — كل يوم 9 صباحاً
            if now.hour == 9 and now.minute < 15 and last_scores != today:
                try:
                    with open("/root/fred_state.json", encoding="utf-8") as f:
                        fred_state = json.load(f)
                    fred_analysis = fred_state.get("analysis", {})
                except:
                    fred_analysis = {}

                from config import ALPACA_KEY  # للتحقق من الاتصال
                WATCHLIST = [
                    "NVDA","MSFT","AAPL","GOOGL","META","AMZN","AVGO","AMD",
                    "CRWD","PANW","PLTR","NOW","DDOG","TSLA","V","MA","LLY",
                ]

                print(f"\n[DataSources] تحديث نقاط {len(WATCHLIST)} سهم...")
                for sym in WATCHLIST:
                    update_decision_engine_with_data(sym, fred_analysis)
                    time.sleep(1)

                last_scores = today
                print("[DataSources] تحديث النقاط اكتمل ✅")

            time.sleep(60)

        except Exception as e:
            print(f"[DataSources] خطأ: {e}")
            time.sleep(60)

# ═══════════════════════════════════════════════════════════════════════════════
# نقطة الدخول
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("🧪 اختبار Data Sources Engine\n")

    # فحص الـ Keys
    print(f"FRED API:      {'✅ موجود' if FRED_API_KEY else '❌ غائب'}")
    print(f"Finnhub:       {'✅ موجود' if FINNHUB_API_KEY else '❌ غائب'}")
    print(f"Alpha Vantage: {'✅ موجود' if ALPHA_VANTAGE_KEY else '❌ غائب'}")

    if not any([FRED_API_KEY, FINNHUB_API_KEY, ALPHA_VANTAGE_KEY]):
        print("\n⚠️ لا توجد API Keys — اعمل Setup أولاً")
        setup_api_keys()
        print("\n─── اختبار COT Report (لا يحتاج Key) ───")

    # COT Report — لا يحتاج Key
    print("\n١. COT Report:")
    cot = fetch_cot_report()
    if "error" not in cot:
        for asset, data in cot.items():
            print(f"   {asset}: {data['commercial_bias']} ({data['commercial_net']:+,})")
    else:
        print(f"   {cot}")

    # FRED إذا موجود
    if FRED_API_KEY:
        print("\n٢. FRED Data:")
        fred_data = fetch_all_fred_data()
        analysis  = analyze_fred_data(fred_data)
        print(f"   المرحلة: {analysis['economic_phase']}")
        print(f"   الفيدرالي: {analysis['fed_direction']}")

        send_data_sources_report(fred_data, analysis, cot, [])
    else:
        print("\n٢. FRED — يحتاج API Key")
        print("   سجّل مجاناً على: https://fred.stlouisfed.org/docs/api/api_key.html")

    # Finnhub إذا موجود
    if FINNHUB_API_KEY:
        print("\n٣. Finnhub (NVDA):")
        sentiment = analyze_finnhub_sentiment("NVDA")
        print(f"   Sentiment: {sentiment['sentiment']}")

        print("\n٤. Earnings Calendar:")
        calendar = fetch_finnhub_earnings_calendar()
        for ev in calendar[:3]:
            print(f"   {ev['symbol']}: {ev['date']}")
    else:
        print("\n٣. Finnhub — يحتاج API Key")
        print("   سجّل مجاناً على: https://finnhub.io")

    # اختبار الربط مع decision_engine
    print("\n٥. ربط مع Decision Engine (NVDA):")
    result = comprehensive_data_score("NVDA")
    print(f"   النقاط: {result['total_score']:+d} | مسموح: {'✅' if result['allowed'] else '❌'}")
    print(f"   جودة البيانات: {result['data_quality']}")

    print("\n✅ اكتمل!")
    print("\n📋 لتشغيل النظام كاملاً:")
    print("   python3 -c \"from data_sources import run_data_sources; run_data_sources()\" &")
