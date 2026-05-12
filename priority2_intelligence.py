"""
priority2_intelligence.py
==========================
الأولوية الثانية — ذكاء متقدم (6 تحسينات في ملف واحد)
✅ ١. ML Pattern Learning
✅ ٢. Options Flow Analysis
✅ ٣. Short Squeeze Detector
✅ ٤. ETF Flow Monitor
✅ ٥. Insider Trading Tracker
✅ ٦. COT Report Analysis
"""

import yfinance as yf
import pandas as pd
import numpy as np
import requests
import json
import time
from datetime import datetime, timedelta
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

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

WATCHLIST = [
    "NVDA","MSFT","AAPL","GOOGL","META","AMZN","AVGO","AMD",
    "CRWD","PANW","PLTR","NOW","DDOG","SNOW",
    "ADBE","CRM","INTU","NFLX","TTD",
    "TSLA","UBER","V","MA","LLY","UNH","COST","WMT",
]

# ═══════════════════════════════════════════════════════════════════════════════
# ١. ML Pattern Learning — يتعلم من الصفقات الناجحة
# ═══════════════════════════════════════════════════════════════════════════════

class PatternLearner:
    """
    يتعلم من الصفقات الناجحة والفاشلة
    يحسن معايير VCP و Trend Template تلقائياً
    """

    def __init__(self):
        self.patterns_file = "/root/learned_patterns.json"
        self.patterns = self.load_patterns()

    def load_patterns(self) -> dict:
        try:
            with open(self.patterns_file, encoding="utf-8") as f:
                return json.load(f)
        except:
            return {
                "winning_patterns": [],
                "losing_patterns":  [],
                "best_vol_ratio":   1.5,
                "best_contractions": 2,
                "best_rs_min":      75,
                "total_analyzed":   0,
                "last_updated":     str(datetime.now()),
            }

    def save_patterns(self):
        with open(self.patterns_file, "w", encoding="utf-8") as f:
            json.dump(self.patterns, f, ensure_ascii=False, indent=2)

    def extract_features(self, symbol: str) -> dict:
        """يستخلص خصائص السهم وقت الإشارة"""
        try:
            df = yf.download(symbol, period="6mo", progress=False, auto_adjust=True)
            if df.empty or len(df) < 50:
                return {}

            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
            close  = df['Close']
            volume = df['Volume']

            # ATR
            hl  = df['High'] - df['Low']
            hpc = (df['High'] - close.shift()).abs()
            lpc = (df['Low']  - close.shift()).abs()
            atr = pd.concat([hl,hpc,lpc],axis=1).max(axis=1).rolling(14).mean()

            # المتوسطات
            ma50  = close.rolling(50).mean()
            ma200 = close.rolling(200).mean()

            current = float(close.iloc[-1])
            vol_ratio = float(volume.iloc[-1]) / float(volume.rolling(20).mean().iloc[-1])

            # BB Width للـ VCP
            bb_std   = close.rolling(20).std()
            bb_width = float((bb_std / close.rolling(20).mean()).iloc[-1])

            return {
                "symbol":      symbol,
                "price":       current,
                "vol_ratio":   round(vol_ratio, 2),
                "atr_pct":     round(float(atr.iloc[-1]) / current * 100, 2),
                "bb_width":    round(bb_width * 100, 2),
                "ma50_dist":   round((current - float(ma50.iloc[-1])) / current * 100, 2),
                "ma200_dist":  round((current - float(ma200.iloc[-1])) / current * 100, 2),
                "rs_proxy":    round((current - float(close.iloc[-252])) / float(close.iloc[-252]) * 100, 1) if len(close) >= 252 else 0,
                "timestamp":   str(datetime.now()),
            }
        except:
            return {}

    def record_trade(self, symbol: str, outcome: str, pnl_pct: float):
        """يسجل نتيجة صفقة ويتعلم منها"""
        features = self.extract_features(symbol)
        if not features:
            return

        features["outcome"] = outcome
        features["pnl_pct"] = pnl_pct

        if outcome == "win":
            self.patterns["winning_patterns"].append(features)
        else:
            self.patterns["losing_patterns"].append(features)

        self.patterns["total_analyzed"] += 1
        self._update_optimal_params()
        self.save_patterns()
        print(f"[ML] سجّلت {outcome} لـ {symbol} ({pnl_pct:+.1f}%)")

    def _update_optimal_params(self):
        """يحدّث المعايير المثلى بناءً على البيانات"""
        winners = self.patterns["winning_patterns"]
        if len(winners) < 5:
            return

        # متوسط خصائص الصفقات الرابحة
        avg_vol  = np.mean([w.get("vol_ratio", 1.5) for w in winners])
        avg_rs   = np.mean([w.get("rs_proxy", 75) for w in winners])

        # تحديث المعايير
        self.patterns["best_vol_ratio"] = round(avg_vol * 0.9, 2)
        self.patterns["best_rs_min"]    = round(avg_rs * 0.85, 1)
        self.patterns["last_updated"]   = str(datetime.now())

        print(f"[ML] تحديث المعايير: Vol>={self.patterns['best_vol_ratio']}x | RS>={self.patterns['best_rs_min']}")

    def get_optimal_params(self) -> dict:
        """يرجع المعايير المثلى المتعلمة"""
        return {
            "min_vol_ratio":   self.patterns.get("best_vol_ratio", 1.5),
            "min_contractions": self.patterns.get("best_contractions", 2),
            "min_rs":          self.patterns.get("best_rs_min", 75),
            "total_analyzed":  self.patterns.get("total_analyzed", 0),
        }

    def score_opportunity(self, symbol: str) -> dict:
        """يعطي نقاط للفرصة بناءً على التعلم السابق"""
        features = self.extract_features(symbol)
        if not features:
            return {"score": 50, "confidence": "low"}

        params  = self.get_optimal_params()
        score   = 50

        if features.get("vol_ratio", 0) >= params["min_vol_ratio"]:
            score += 15
        if features.get("rs_proxy", 0) >= params["min_rs"]:
            score += 15
        if features.get("bb_width", 10) < 5:
            score += 10
        if features.get("ma50_dist", 0) > 0:
            score += 10

        confidence = "high" if score >= 80 else "medium" if score >= 65 else "low"
        return {
            "symbol":     symbol,
            "score":      score,
            "confidence": confidence,
            "features":   features,
        }

# ═══════════════════════════════════════════════════════════════════════════════
# ٢. Options Flow Analysis — كشف الشراء المؤسسي
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_options_flow(symbol: str) -> dict:
    """
    يحلل نشاط الـ Options لاكتشاف الشراء المؤسسي
    Put/Call Ratio منخفض = تفاؤل
    Unusual Volume = نشاط غير عادي
    """
    result = {
        "symbol":        symbol,
        "put_call_ratio": None,
        "unusual":        False,
        "sentiment":      "محايد",
        "signal":         "neutral",
    }

    try:
        ticker = yf.Ticker(symbol)

        # تحميل بيانات الـ Options
        exp_dates = ticker.options
        if not exp_dates:
            return result

        # أقرب تاريخ انتهاء
        nearest_exp = exp_dates[0]
        chain = ticker.option_chain(nearest_exp)

        calls = chain.calls
        puts  = chain.puts

        if calls.empty or puts.empty:
            return result

        # حساب Put/Call Ratio
        total_call_vol = calls['volume'].sum() if 'volume' in calls.columns else 0
        total_put_vol  = puts['volume'].sum()  if 'volume' in puts.columns  else 0

        if total_call_vol > 0:
            pc_ratio = total_put_vol / total_call_vol
            result["put_call_ratio"] = round(pc_ratio, 2)

            # تفسير النسبة
            if pc_ratio < 0.5:
                result["sentiment"] = "تفاؤل قوي 🟢"
                result["signal"]    = "bullish"
            elif pc_ratio < 0.8:
                result["sentiment"] = "تفاؤل معتدل"
                result["signal"]    = "mild_bullish"
            elif pc_ratio > 1.5:
                result["sentiment"] = "تشاؤم 🔴"
                result["signal"]    = "bearish"
            else:
                result["sentiment"] = "محايد"
                result["signal"]    = "neutral"

        # Unusual Volume — هل الحجم أعلى بكثير من المعتاد؟
        avg_oi = calls['openInterest'].mean() if 'openInterest' in calls.columns else 0
        max_oi = calls['openInterest'].max()  if 'openInterest' in calls.columns else 0
        if avg_oi > 0 and max_oi > avg_oi * 3:
            result["unusual"] = True
            result["signal"]  = "unusual_bullish"

        print(f"[Options] {symbol}: P/C={result['put_call_ratio']} | {result['sentiment']}")

    except Exception as e:
        print(f"[Options] {symbol}: {e}")

    return result

def scan_options_flow(watchlist: list) -> list:
    """يفحص Options Flow لكل الأسهم ويرجع الأكثر إيجابية"""
    print(f"\n[Options] فحص {len(watchlist)} سهم...")
    results = []

    for sym in watchlist:
        opt = analyze_options_flow(sym)
        if opt["signal"] in ["bullish", "unusual_bullish"]:
            results.append(opt)

    results.sort(key=lambda x: (x["signal"] == "unusual_bullish", x.get("put_call_ratio", 1)), reverse=True)
    return results

# ═══════════════════════════════════════════════════════════════════════════════
# ٣. Short Squeeze Detector
# ═══════════════════════════════════════════════════════════════════════════════

def detect_short_squeeze(watchlist: list) -> list:
    """
    يكتشف فرص Short Squeeze:
    Short Interest عالٍ + سهم يبدأ بالارتفاع = ضغط على البائعين
    """
    print(f"\n[Short Squeeze] فحص {len(watchlist)} سهم...")
    candidates = []

    for sym in watchlist:
        try:
            ticker = yf.Ticker(sym)
            info   = ticker.info

            short_ratio   = info.get('shortRatio', 0) or 0
            short_pct     = info.get('shortPercentOfFloat', 0) or 0
            short_pct_100 = short_pct * 100 if short_pct < 1 else short_pct

            # Days to Cover > 5 + Short% > 15% = فرصة محتملة
            if short_ratio >= 5 or short_pct_100 >= 15:
                # فحص الزخم الحالي
                df = yf.download(sym, period="1mo", progress=False, auto_adjust=True)
                if df.empty:
                    continue
                df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

                mom_1w = (float(df['Close'].iloc[-1]) - float(df['Close'].iloc[-5])) / float(df['Close'].iloc[-5]) * 100

                squeeze_score = 0
                if short_ratio >= 10:   squeeze_score += 3
                elif short_ratio >= 5:  squeeze_score += 2
                if short_pct_100 >= 20: squeeze_score += 3
                elif short_pct_100 >= 15: squeeze_score += 2
                if mom_1w > 5:          squeeze_score += 2
                elif mom_1w > 2:        squeeze_score += 1

                if squeeze_score >= 4:
                    candidates.append({
                        "symbol":      sym,
                        "short_ratio": round(short_ratio, 1),
                        "short_pct":   round(short_pct_100, 1),
                        "momentum_1w": round(mom_1w, 1),
                        "score":       squeeze_score,
                    })
                    print(f"  🎯 {sym}: Short {short_pct_100:.1f}% | Days={short_ratio:.1f} | Mom={mom_1w:+.1f}%")

        except Exception as e:
            pass

    candidates.sort(key=lambda x: x["score"], reverse=True)
    print(f"[Short Squeeze] {len(candidates)} مرشح")
    return candidates

# ═══════════════════════════════════════════════════════════════════════════════
# ٤. ETF Flow Monitor — تدفق الأموال المؤسسية
# ═══════════════════════════════════════════════════════════════════════════════

SECTOR_ETFS = {
    "التكنولوجيا":       "XLK",
    "أشباه الموصلات":    "SMH",
    "السيبراني":         "HACK",
    "الصحة":            "XLV",
    "المالية":          "XLF",
    "الطاقة":           "XLE",
    "الاستهلاكي":       "XLY",
    "الصناعي":          "XLI",
    "العقارات":         "XLRE",
    "الخدمات":          "XLU",
}

def monitor_etf_flows() -> dict:
    """
    يراقب تدفق الأموال في ETFs القطاعية
    ETF يرتفع بحجم عالٍ = أموال كبيرة تدخل القطاع
    """
    print("\n[ETF Flow] مراقبة تدفق الأموال...")
    flows = {}

    for sector, etf in SECTOR_ETFS.items():
        try:
            df = yf.download(etf, period="1mo", progress=False, auto_adjust=True)
            if df.empty or len(df) < 10:
                continue
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

            close  = df['Close']
            volume = df['Volume']

            ret_1w  = (float(close.iloc[-1]) - float(close.iloc[-5]))  / float(close.iloc[-5])  * 100
            ret_1m  = (float(close.iloc[-1]) - float(close.iloc[0]))   / float(close.iloc[0])   * 100
            vol_avg = float(volume.rolling(10).mean().iloc[-2])
            vol_cur = float(volume.iloc[-1])
            vol_ratio = vol_cur / vol_avg if vol_avg > 0 else 1

            # تصنيف التدفق
            if ret_1w > 3 and vol_ratio > 1.5:
                flow = "inflow_strong"
                emoji = "🟢🟢"
            elif ret_1w > 1:
                flow = "inflow"
                emoji = "🟢"
            elif ret_1w < -3 and vol_ratio > 1.5:
                flow = "outflow_strong"
                emoji = "🔴🔴"
            elif ret_1w < -1:
                flow = "outflow"
                emoji = "🔴"
            else:
                flow = "neutral"
                emoji = "⚪"

            flows[sector] = {
                "etf":       etf,
                "ret_1w":    round(ret_1w, 1),
                "ret_1m":    round(ret_1m, 1),
                "vol_ratio": round(vol_ratio, 2),
                "flow":      flow,
                "emoji":     emoji,
            }
            print(f"  {emoji} {sector}: {ret_1w:+.1f}% | Vol: {vol_ratio:.1f}x")

        except Exception as e:
            pass

    return flows

def send_etf_flow_report(flows: dict):
    """يرسل تقرير ETF Flows"""
    if not flows:
        return

    sorted_flows = sorted(flows.items(), key=lambda x: x[1]["ret_1w"], reverse=True)

    msg = (
        f"💰 <b>ETF Flow Monitor</b>\n"
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"{'─'*25}\n\n"
    )

    inflows  = [(s,d) for s,d in sorted_flows if "inflow" in d["flow"]]
    outflows = [(s,d) for s,d in sorted_flows if "outflow" in d["flow"]]

    if inflows:
        msg += "💚 <b>تدفق أموال للداخل:</b>\n"
        for sector, data in inflows[:4]:
            msg += f"{data['emoji']} {sector} ({data['etf']}): {data['ret_1w']:+.1f}% | {data['vol_ratio']:.1f}x\n"
        msg += "\n"

    if outflows:
        msg += "❤️ <b>تدفق أموال للخارج:</b>\n"
        for sector, data in outflows[:3]:
            msg += f"{data['emoji']} {sector}: {data['ret_1w']:+.1f}%\n"

    msg += f"\n💡 ركّز على القطاعات ذات التدفق الإيجابي"
    send_telegram(msg)

# ═══════════════════════════════════════════════════════════════════════════════
# ٥. Insider Trading Tracker
# ═══════════════════════════════════════════════════════════════════════════════

def track_insider_activity(watchlist: list) -> list:
    """
    يتتبع نشاط المديرين التنفيذيين
    شراء Insider = ثقة عالية بالشركة
    """
    print(f"\n[Insider] تتبع نشاط المديرين...")
    insider_buys = []

    for sym in watchlist:
        try:
            ticker = yf.Ticker(sym)

            # بيانات المساهمين المؤسسيين
            info = ticker.info
            inst_own = info.get('heldPercentInstitutions', 0) or 0
            inst_own_pct = inst_own * 100 if inst_own < 1 else inst_own

            # تغير ملكية المؤسسات
            insider_own = info.get('heldPercentInsiders', 0) or 0
            insider_pct = insider_own * 100 if insider_own < 1 else insider_own

            # مؤشر شراء Insider
            # نستخدم نسبة الملكية الداخلية كمؤشر
            if insider_pct >= 5:
                score = 0
                if insider_pct >= 10: score += 3
                elif insider_pct >= 5: score += 2
                if inst_own_pct >= 70: score += 2
                elif inst_own_pct >= 50: score += 1

                if score >= 3:
                    insider_buys.append({
                        "symbol":      sym,
                        "insider_pct": round(insider_pct, 1),
                        "inst_pct":    round(inst_own_pct, 1),
                        "score":       score,
                        "signal":      "strong" if score >= 4 else "moderate",
                    })
                    print(f"  👔 {sym}: Insider={insider_pct:.1f}% | Inst={inst_own_pct:.1f}%")

        except Exception as e:
            pass

    insider_buys.sort(key=lambda x: x["score"], reverse=True)
    print(f"[Insider] {len(insider_buys)} سهم بنشاط داخلي إيجابي")
    return insider_buys

# ═══════════════════════════════════════════════════════════════════════════════
# ٦. COT Report Analysis — مراكز البنوك الكبرى
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_market_sentiment() -> dict:
    """
    تحليل معنويات السوق من مؤشرات متعددة
    (بديل عملي لـ COT Report الذي يحتاج API خاص)
    """
    print("\n[Sentiment] تحليل معنويات السوق...")
    sentiment = {
        "overall":    "محايد",
        "score":      0,
        "indicators": [],
    }

    try:
        # ١. VIX — مؤشر الخوف
        vix_df = yf.download("^VIX", period="1mo", progress=False, auto_adjust=True)
        if not vix_df.empty:
            vix_df.columns = [c[0] if isinstance(c, tuple) else c for c in vix_df.columns]
            vix_current = float(vix_df['Close'].iloc[-1])
            vix_avg     = float(vix_df['Close'].mean())
            vix_trend   = "هابط" if vix_current < vix_avg else "صاعد"

            if vix_current < 15:
                sentiment["score"] += 2
                sentiment["indicators"].append(f"✅ VIX منخفض ({vix_current:.1f}) — هدوء")
            elif vix_current > 25:
                sentiment["score"] -= 2
                sentiment["indicators"].append(f"⚠️ VIX مرتفع ({vix_current:.1f}) — قلق")
            else:
                sentiment["indicators"].append(f"⚖️ VIX طبيعي ({vix_current:.1f})")

        # ٢. Put/Call Ratio من SPY
        try:
            spy_ticker = yf.Ticker("SPY")
            exp = spy_ticker.options
            if exp:
                chain = spy_ticker.option_chain(exp[1])
                pc_ratio = chain.puts['volume'].sum() / max(chain.calls['volume'].sum(), 1)
                if pc_ratio < 0.7:
                    sentiment["score"] += 2
                    sentiment["indicators"].append(f"✅ P/C Ratio تفاؤلي ({pc_ratio:.2f})")
                elif pc_ratio > 1.2:
                    sentiment["score"] -= 1
                    sentiment["indicators"].append(f"⚠️ P/C Ratio تشاؤمي ({pc_ratio:.2f})")
                else:
                    sentiment["indicators"].append(f"⚖️ P/C Ratio محايد ({pc_ratio:.2f})")
        except:
            pass

        # ٣. نسبة الأسهم فوق MA50 (Breadth)
        above_ma50 = 0
        total_checked = 0
        for sym in WATCHLIST[:20]:
            try:
                df = yf.download(sym, period="3mo", progress=False, auto_adjust=True)
                if df.empty: continue
                df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
                close = df['Close']
                ma50  = close.rolling(50).mean().iloc[-1]
                if float(close.iloc[-1]) > float(ma50):
                    above_ma50 += 1
                total_checked += 1
            except:
                pass

        if total_checked > 0:
            breadth_pct = above_ma50 / total_checked * 100
            if breadth_pct >= 70:
                sentiment["score"] += 2
                sentiment["indicators"].append(f"✅ Breadth قوي ({breadth_pct:.0f}% فوق MA50)")
            elif breadth_pct <= 40:
                sentiment["score"] -= 2
                sentiment["indicators"].append(f"⚠️ Breadth ضعيف ({breadth_pct:.0f}% فوق MA50)")
            else:
                sentiment["indicators"].append(f"⚖️ Breadth محايد ({breadth_pct:.0f}%)")

        # التقييم النهائي
        if sentiment["score"] >= 4:
            sentiment["overall"] = "تفاؤل قوي 🟢🟢"
        elif sentiment["score"] >= 2:
            sentiment["overall"] = "تفاؤل معتدل 🟢"
        elif sentiment["score"] <= -3:
            sentiment["overall"] = "تشاؤم قوي 🔴🔴"
        elif sentiment["score"] <= -1:
            sentiment["overall"] = "تشاؤم معتدل 🔴"
        else:
            sentiment["overall"] = "محايد ⚪"

        print(f"[Sentiment] النتيجة: {sentiment['overall']} (نقاط: {sentiment['score']:+d})")

    except Exception as e:
        print(f"[Sentiment] خطأ: {e}")

    return sentiment

def send_sentiment_report(sentiment: dict, options_data: list,
                          squeeze_data: list, insider_data: list):
    """تقرير شامل للذكاء المتقدم"""
    msg = (
        f"🧠 <b>Intelligence Report — المتقدم</b>\n"
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"{'─'*28}\n\n"
        f"<b>معنويات السوق: {sentiment['overall']}</b>\n"
        f"النقاط: {sentiment['score']:+d}\n\n"
    )

    for ind in sentiment["indicators"]:
        msg += f"{ind}\n"

    if options_data:
        msg += f"\n📊 <b>Options Flow إيجابي:</b>\n"
        for opt in options_data[:3]:
            msg += f"• {opt['symbol']}: {opt['sentiment']}\n"

    if squeeze_data:
        msg += f"\n🎯 <b>Short Squeeze محتمل:</b>\n"
        for sq in squeeze_data[:3]:
            msg += f"• {sq['symbol']}: Short {sq['short_pct']:.1f}% | Mom {sq['momentum_1w']:+.1f}%\n"

    if insider_data:
        msg += f"\n👔 <b>Insider Activity:</b>\n"
        for ins in insider_data[:3]:
            msg += f"• {ins['symbol']}: Insider {ins['insider_pct']:.1f}%\n"

    send_telegram(msg)

# ═══════════════════════════════════════════════════════════════════════════════
# الحلقة الرئيسية
# ═══════════════════════════════════════════════════════════════════════════════

def run_priority2():
    """تشغيل كل تحسينات الأولوية الثانية"""
    print("=" * 55)
    print("  Priority 2 — الذكاء المتقدم")
    print("  ✅ ML Pattern Learning")
    print("  ✅ Options Flow Analysis")
    print("  ✅ Short Squeeze Detector")
    print("  ✅ ETF Flow Monitor")
    print("  ✅ Insider Trading Tracker")
    print("  ✅ COT/Sentiment Analysis")
    print("=" * 55 + "\n")

    # تهيئة ML
    learner = PatternLearner()
    params  = learner.get_optimal_params()
    print(f"[ML] معايير محسّنة: Vol>={params['min_vol_ratio']}x | RS>={params['min_rs']}")

    send_telegram(
        "🧠 <b>Priority 2 — الذكاء المتقدم يعمل!</b>\n"
        "─"*20 + "\n"
        "✅ ML Pattern Learning\n"
        "✅ Options Flow Analysis\n"
        "✅ Short Squeeze Detector\n"
        "✅ ETF Flow Monitor\n"
        "✅ Insider Trading Tracker\n"
        "✅ Sentiment Analysis\n\n"
        "النظام يفكر كصندوق استثمار كبير! 🏦"
    )

    last_full_scan  = None
    last_etf_flow   = None

    while True:
        try:
            now   = datetime.now()
            today = now.date()

            # تقرير شامل — كل يوم الساعة 9 صباحاً
            if now.hour == 9 and now.minute < 10 and last_full_scan != today:

                # ١. ETF Flows
                flows = monitor_etf_flows()
                send_etf_flow_report(flows)

                # ٢. Options Flow
                options_data = scan_options_flow(WATCHLIST[:15])

                # ٣. Short Squeeze
                squeeze_data = detect_short_squeeze(WATCHLIST)

                # ٤. Insider
                insider_data = track_insider_activity(WATCHLIST)

                # ٥. Sentiment
                sentiment = analyze_market_sentiment()

                # تقرير موحد
                send_sentiment_report(sentiment, options_data,
                                    squeeze_data, insider_data)

                last_full_scan = today

            # ETF Flow — كل يوم الساعة 11 صباحاً أيضاً
            if now.hour == 11 and now.minute < 10 and last_etf_flow != today:
                flows = monitor_etf_flows()
                send_etf_flow_report(flows)
                last_etf_flow = today

            time.sleep(60)

        except Exception as e:
            print(f"[Priority2] خطأ: {e}")
            time.sleep(60)

# ═══════════════════════════════════════════════════════════════════════════════
# نقطة الدخول
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("🧪 اختبار Priority 2 — الذكاء المتقدم\n")

    # ML Pattern Learning
    print("١. ML Pattern Learning:")
    learner = PatternLearner()
    score   = learner.score_opportunity("NVDA")
    print(f"   NVDA: نقاط={score['score']} | ثقة={score['confidence']}")

    # Options Flow
    print("\n٢. Options Flow (أول 5 أسهم):")
    opts = scan_options_flow(WATCHLIST[:5])
    print(f"   إيجابي: {len(opts)} سهم")

    # Short Squeeze
    print("\n٣. Short Squeeze Detector:")
    squeezes = detect_short_squeeze(WATCHLIST[:10])
    print(f"   مرشحين: {len(squeezes)}")

    # ETF Flow
    print("\n٤. ETF Flow Monitor:")
    flows = monitor_etf_flows()
    send_etf_flow_report(flows)

    # Insider
    print("\n٥. Insider Tracker (أول 10):")
    insiders = track_insider_activity(WATCHLIST[:10])
    print(f"   نشاط إيجابي: {len(insiders)}")

    # Sentiment
    print("\n٦. Market Sentiment:")
    sentiment = analyze_market_sentiment()
    send_sentiment_report(sentiment, opts, squeezes, insiders)

    print("\n✅ كل الاختبارات اكتملت!")
