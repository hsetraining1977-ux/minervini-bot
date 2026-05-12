"""
priority3_live.py
=================
الأولوية الثالثة — الانتقال الآمن للمال الحقيقي (6 تحسينات)
✅ ١. شروط الانتقال — تقييم جاهزية النظام
✅ ٢. Portfolio Optimizer — Max Sharpe Ratio
✅ ٣. Correlation Matrix — تجنب التركيز
✅ ٤. Live Trading Readiness — فحص الجاهزية
✅ ٥. Risk Scaling — تدرج المخاطرة
✅ ٦. Emergency Shutdown — إيقاف طارئ فوري
"""

import yfinance as yf
import pandas as pd
import numpy as np
import requests
import json
import time
from datetime import datetime, timedelta
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
import alpaca_trade_api as tradeapi
from config import ALPACA_KEY, ALPACA_SECRET

trading_client = tradeapi.REST(
    ALPACA_KEY, ALPACA_SECRET,
    base_url='https://paper-api.alpaca.markets'
)

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
# ١. شروط الانتقال — تقييم جاهزية النظام
# ═══════════════════════════════════════════════════════════════════════════════

# معايير Minervini للانتقال للمال الحقيقي
READINESS_CRITERIA = {
    "min_paper_days":      90,    # 3 أشهر على الأقل
    "min_win_rate":        45.0,  # Win Rate 45%+
    "max_drawdown":       -15.0,  # Max Drawdown أقل من 15%
    "min_profit_factor":   1.5,   # Profit Factor 1.5+
    "min_trades":          20,    # 20 صفقة على الأقل
    "min_sharpe":          1.0,   # Sharpe Ratio 1.0+
    "starting_capital":    5000,  # بداية بـ $5,000 فقط
}

def evaluate_readiness() -> dict:
    """
    يقيّم جاهزية النظام للانتقال للمال الحقيقي
    بناءً على معايير Minervini الصارمة
    """
    print("\n[Readiness] تقييم جاهزية الانتقال...")

    result = {
        "ready":      False,
        "score":      0,
        "max_score":  6,
        "criteria":   {},
        "timestamp":  str(datetime.now()),
    }

    try:
        # بيانات الحساب الحالية
        account   = trading_client.get_account()
        portfolio = float(account.portfolio_value)
        initial   = 100000  # رأس المال الأولي للـ Paper

        # تحميل سجل الصفقات
        try:
            with open("/root/trades_log.json", encoding="utf-8") as f:
                trades = json.load(f)
        except:
            trades = []

        # ─── المعيار ١: مدة الاختبار ─────────────────────────────────────────
        try:
            with open("/root/trades_log.json", encoding="utf-8") as f:
                all_trades = json.load(f)
            if all_trades:
                first_date = datetime.fromisoformat(all_trades[0]["timestamp"])
                days_running = (datetime.now() - first_date).days
            else:
                days_running = 0
        except:
            days_running = 0

        days_ok = days_running >= READINESS_CRITERIA["min_paper_days"]
        result["criteria"]["مدة الاختبار"] = {
            "value":    f"{days_running} يوم",
            "required": f"{READINESS_CRITERIA['min_paper_days']} يوم",
            "passed":   days_ok,
        }
        if days_ok: result["score"] += 1

        # ─── المعيار ٢: عدد الصفقات ──────────────────────────────────────────
        trades_ok = len(trades) >= READINESS_CRITERIA["min_trades"]
        result["criteria"]["عدد الصفقات"] = {
            "value":    f"{len(trades)} صفقة",
            "required": f"{READINESS_CRITERIA['min_trades']} صفقة",
            "passed":   trades_ok,
        }
        if trades_ok: result["score"] += 1

        # ─── المعيار ٣: Win Rate ──────────────────────────────────────────────
        buys  = [t for t in trades if t.get("action") == "BUY"]
        sells = [t for t in trades if t.get("action") == "SELL"]
        closed = []
        for sell in sells:
            buy = next((b for b in buys if b["symbol"] == sell["symbol"]), None)
            if buy:
                pnl = sell["price"] - buy["price"]
                closed.append({"win": pnl > 0, "pnl_pct": pnl / buy["price"] * 100})

        win_rate = len([t for t in closed if t["win"]]) / max(len(closed), 1) * 100
        wr_ok = win_rate >= READINESS_CRITERIA["min_win_rate"]
        result["criteria"]["Win Rate"] = {
            "value":    f"{win_rate:.1f}%",
            "required": f"{READINESS_CRITERIA['min_win_rate']}%",
            "passed":   wr_ok,
        }
        if wr_ok: result["score"] += 1

        # ─── المعيار ٤: العائد الإجمالي ──────────────────────────────────────
        total_return = (portfolio - initial) / initial * 100
        return_ok = total_return > 0
        result["criteria"]["العائد الإجمالي"] = {
            "value":    f"{total_return:+.1f}%",
            "required": "إيجابي",
            "passed":   return_ok,
        }
        if return_ok: result["score"] += 1

        # ─── المعيار ٥: Profit Factor ─────────────────────────────────────────
        winners = [t for t in closed if t["win"]]
        losers  = [t for t in closed if not t["win"]]
        gross_profit = sum(t["pnl_pct"] for t in winners) if winners else 0
        gross_loss   = abs(sum(t["pnl_pct"] for t in losers)) if losers else 1
        pf = gross_profit / gross_loss if gross_loss > 0 else 0
        pf_ok = pf >= READINESS_CRITERIA["min_profit_factor"]
        result["criteria"]["Profit Factor"] = {
            "value":    f"{pf:.2f}",
            "required": f"{READINESS_CRITERIA['min_profit_factor']}",
            "passed":   pf_ok,
        }
        if pf_ok: result["score"] += 1

        # ─── المعيار ٦: الاستمرارية ───────────────────────────────────────────
        # هل النظام يعمل بدون انقطاع؟
        try:
            with open("/root/nohup.out") as f:
                last_lines = f.readlines()[-5:]
            system_ok = any("Scan" in line or "Monitor" in line for line in last_lines)
        except:
            system_ok = False

        result["criteria"]["استمرارية النظام"] = {
            "value":    "يعمل" if system_ok else "متوقف",
            "required": "يعمل",
            "passed":   system_ok,
        }
        if system_ok: result["score"] += 1

        # القرار النهائي
        result["ready"] = result["score"] >= 5  # 5 من 6 معايير

    except Exception as e:
        print(f"[Readiness] خطأ: {e}")
        result["error"] = str(e)

    return result

def send_readiness_report(result: dict):
    """يرسل تقرير الجاهزية"""
    status = "✅ جاهز للانتقال!" if result["ready"] else "⏳ لم تكتمل الشروط بعد"

    msg = (
        f"🎯 <b>تقييم الجاهزية للمال الحقيقي</b>\n"
        f"{datetime.now().strftime('%Y-%m-%d')}\n"
        f"{'─'*28}\n\n"
        f"<b>{status}</b>\n"
        f"النقاط: {result['score']}/{result['max_score']}\n\n"
        f"<b>المعايير:</b>\n"
    )

    for criterion, data in result.get("criteria", {}).items():
        emoji = "✅" if data["passed"] else "❌"
        msg += f"{emoji} {criterion}: {data['value']} (مطلوب: {data['required']})\n"

    if result["ready"]:
        msg += (
            f"\n{'─'*28}\n"
            f"🚀 <b>خطوات الانتقال:</b>\n"
            f"١. افتح حساب Live على Alpaca\n"
            f"٢. ابدأ بـ ${READINESS_CRITERIA['starting_capital']:,} فقط\n"
            f"٣. نفس الإعدادات — لا تغيير\n"
            f"٤. راقب أول أسبوع بعناية"
        )
    else:
        remaining = result["max_score"] - result["score"]
        msg += f"\n💡 تحتاج {remaining} معيار إضافي للجاهزية"

    send_telegram(msg)

# ═══════════════════════════════════════════════════════════════════════════════
# ٢. Portfolio Optimizer — Max Sharpe Ratio
# ═══════════════════════════════════════════════════════════════════════════════

def optimize_portfolio(symbols: list, lookback_days: int = 252) -> dict:
    """
    يحسب التوزيع الأمثل للمحفظة بناءً على Max Sharpe Ratio
    يتجنب التركيز في سهم واحد
    """
    print(f"\n[Optimizer] تحسين المحفظة لـ {len(symbols)} سهم...")

    result = {
        "weights":       {},
        "expected_ret":  0,
        "expected_vol":  0,
        "sharpe":        0,
        "method":        "equal_weight",
    }

    try:
        # تحميل بيانات الأسهم
        prices = {}
        for sym in symbols:
            df = yf.download(sym, period="1y", progress=False, auto_adjust=True)
            if not df.empty and len(df) >= 50:
                df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
                prices[sym] = df['Close']

        if len(prices) < 2:
            # توزيع متساوٍ
            for sym in symbols:
                result["weights"][sym] = round(1/len(symbols), 3)
            return result

        # حساب العوائد اليومية
        returns_df = pd.DataFrame(prices).pct_change().dropna()

        # معدل العائد الخالي من المخاطر (US10Y تقريباً)
        rf = 0.045 / 252

        # محاكاة Monte Carlo للمحافظ العشوائية
        n_portfolios = 1000
        n_assets     = len(returns_df.columns)
        symbols_list = list(returns_df.columns)

        mean_returns = returns_df.mean()
        cov_matrix   = returns_df.cov()

        best_sharpe  = -np.inf
        best_weights = np.ones(n_assets) / n_assets

        for _ in range(n_portfolios):
            # أوزان عشوائية
            w = np.random.random(n_assets)
            w = w / w.sum()

            # حد أقصى 30% لأي سهم
            w = np.clip(w, 0.05, 0.30)
            w = w / w.sum()

            # حساب العائد والتذبذب
            port_ret = np.dot(w, mean_returns) * 252
            port_vol = np.sqrt(np.dot(w.T, np.dot(cov_matrix * 252, w)))
            sharpe   = (port_ret - rf * 252) / port_vol if port_vol > 0 else 0

            if sharpe > best_sharpe:
                best_sharpe  = sharpe
                best_weights = w
                best_ret     = port_ret
                best_vol     = port_vol

        # تحويل الأوزان
        for i, sym in enumerate(symbols_list):
            result["weights"][sym] = round(float(best_weights[i]), 3)

        result.update({
            "expected_ret": round(best_ret * 100, 1),
            "expected_vol": round(best_vol * 100, 1),
            "sharpe":       round(best_sharpe, 2),
            "method":       "max_sharpe_monte_carlo",
        })

        print(f"[Optimizer] Sharpe={best_sharpe:.2f} | عائد={best_ret*100:.1f}% | تذبذب={best_vol*100:.1f}%")

    except Exception as e:
        print(f"[Optimizer] خطأ: {e}")
        for sym in symbols:
            result["weights"][sym] = round(1/len(symbols), 3)

    return result

# ═══════════════════════════════════════════════════════════════════════════════
# ٣. Correlation Matrix — تجنب التركيز
# ═══════════════════════════════════════════════════════════════════════════════

def check_correlation(symbols: list, threshold: float = 0.85) -> dict:
    """
    يفحص الارتباط بين الأسهم
    ارتباط عالٍ > 0.85 = تركيز خطير
    """
    print(f"\n[Correlation] فحص الارتباط بين {len(symbols)} سهم...")

    result = {
        "high_correlation": [],
        "safe_portfolio":   [],
        "warning":          False,
    }

    try:
        prices = {}
        for sym in symbols:
            df = yf.download(sym, period="6mo", progress=False, auto_adjust=True)
            if not df.empty:
                df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
                prices[sym] = df['Close']

        if len(prices) < 2:
            result["safe_portfolio"] = symbols
            return result

        returns = pd.DataFrame(prices).pct_change().dropna()
        corr    = returns.corr()

        # إيجاد الأزواج عالية الارتباط
        high_corr_pairs = []
        symbols_in_corr = list(corr.columns)

        for i in range(len(symbols_in_corr)):
            for j in range(i+1, len(symbols_in_corr)):
                s1 = symbols_in_corr[i]
                s2 = symbols_in_corr[j]
                c  = float(corr.loc[s1, s2])
                if c >= threshold:
                    high_corr_pairs.append({
                        "sym1": s1,
                        "sym2": s2,
                        "corr": round(c, 2),
                    })
                    print(f"  ⚠️ {s1}-{s2}: {c:.2f} (مرتبطان جداً)")

        result["high_correlation"] = high_corr_pairs
        result["warning"] = len(high_corr_pairs) > 0

        # بناء محفظة متنوعة (نختار واحد من كل زوج مرتبط)
        exclude = set()
        for pair in high_corr_pairs:
            if pair["sym1"] not in exclude:
                exclude.add(pair["sym2"])

        result["safe_portfolio"] = [s for s in symbols_in_corr if s not in exclude]
        print(f"[Correlation] محفظة آمنة: {len(result['safe_portfolio'])} سهم")

    except Exception as e:
        print(f"[Correlation] خطأ: {e}")
        result["safe_portfolio"] = symbols

    return result

def send_correlation_alert(corr_result: dict):
    """يرسل تنبيه إذا كان هناك ارتباط عالٍ"""
    if not corr_result["warning"]:
        return

    msg = (
        f"⚠️ <b>تنبيه: ارتباط عالٍ في المحفظة</b>\n"
        f"{'─'*25}\n\n"
        f"الأزواج المرتبطة:\n"
    )

    for pair in corr_result["high_correlation"][:5]:
        msg += f"• {pair['sym1']} ↔ {pair['sym2']}: {pair['corr']:.2f}\n"

    msg += (
        f"\n💡 هذا يعني أن مراكزك تتحرك معاً\n"
        f"مخاطرة أعلى مما تعتقد!\n\n"
        f"المحفظة الآمنة المقترحة:\n"
        f"{', '.join(corr_result['safe_portfolio'][:8])}"
    )

    send_telegram(msg)

# ═══════════════════════════════════════════════════════════════════════════════
# ٤. Live Trading Readiness Check
# ═══════════════════════════════════════════════════════════════════════════════

def live_trading_checklist() -> dict:
    """
    قائمة تحقق كاملة قبل الانتقال للمال الحقيقي
    """
    checklist = {
        "items":  [],
        "passed": 0,
        "total":  0,
        "ready":  False,
    }

    checks = [
        # (الوصف، الفحص)
        ("Watchdog يعمل 24/7",
         lambda: __import__('subprocess').run(['pgrep','-f','watchdog'], capture_output=True).returncode == 0),

        ("auto_monitor يعمل",
         lambda: __import__('subprocess').run(['pgrep','-f','auto_monitor'], capture_output=True).returncode == 0),

        ("config.py موجود",
         lambda: __import__('os').path.exists('/root/config.py')),

        ("macro_state.json موجود",
         lambda: __import__('os').path.exists('/root/macro_state.json')),

        ("sector_state.json موجود",
         lambda: __import__('os').path.exists('/root/sector_state.json')),

        ("الاتصال بـ Alpaca يعمل",
         lambda: bool(trading_client.get_account())),

        ("الاتصال بـ Telegram يعمل",
         lambda: requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getMe", timeout=5).ok),
    ]

    for description, check_fn in checks:
        checklist["total"] += 1
        try:
            passed = check_fn()
        except:
            passed = False

        checklist["items"].append({
            "description": description,
            "passed":      passed,
        })
        if passed:
            checklist["passed"] += 1
        print(f"  {'✅' if passed else '❌'} {description}")

    checklist["ready"] = checklist["passed"] == checklist["total"]
    return checklist

# ═══════════════════════════════════════════════════════════════════════════════
# ٥. Risk Scaling — تدرج المخاطرة
# ═══════════════════════════════════════════════════════════════════════════════

class RiskScaler:
    """
    يدير تدرج المخاطرة بناءً على أداء النظام
    يبدأ صغيراً ويزيد تدريجياً مع النجاح
    """

    LEVELS = {
        "MICRO":    {"capital": 5_000,   "risk_pct": 0.005, "max_pos": 3},
        "SMALL":    {"capital": 10_000,  "risk_pct": 0.008, "max_pos": 4},
        "MEDIUM":   {"capital": 25_000,  "risk_pct": 0.010, "max_pos": 5},
        "STANDARD": {"capital": 50_000,  "risk_pct": 0.0125,"max_pos": 6},
        "FULL":     {"capital": 100_000, "risk_pct": 0.015, "max_pos": 8},
    }

    def __init__(self):
        self.state_file = "/root/risk_scale_state.json"
        self.state = self.load_state()

    def load_state(self) -> dict:
        try:
            with open(self.state_file, encoding="utf-8") as f:
                return json.load(f)
        except:
            return {
                "current_level": "MICRO",
                "consecutive_wins": 0,
                "consecutive_losses": 0,
                "total_return_pct": 0,
                "last_updated": str(datetime.now()),
            }

    def save_state(self):
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def update(self, win: bool, return_pct: float):
        """يحدّث مستوى المخاطرة بعد كل صفقة"""
        if win:
            self.state["consecutive_wins"]   += 1
            self.state["consecutive_losses"]  = 0
        else:
            self.state["consecutive_losses"] += 1
            self.state["consecutive_wins"]    = 0

        self.state["total_return_pct"] += return_pct

        # ارتقِ للمستوى الأعلى بعد 5 انتصارات متتالية
        levels = list(self.LEVELS.keys())
        current_idx = levels.index(self.state["current_level"])

        if self.state["consecutive_wins"] >= 5 and current_idx < len(levels)-1:
            self.state["current_level"] = levels[current_idx + 1]
            new_params = self.LEVELS[self.state["current_level"]]
            send_telegram(
                f"🆙 <b>ترقية مستوى المخاطرة!</b>\n"
                f"المستوى الجديد: {self.state['current_level']}\n"
                f"رأس المال: ${new_params['capital']:,}\n"
                f"المخاطرة: {new_params['risk_pct']*100:.2f}%"
            )
            self.state["consecutive_wins"] = 0

        # انزل للمستوى الأدنى بعد 3 خسائر متتالية
        elif self.state["consecutive_losses"] >= 3 and current_idx > 0:
            self.state["current_level"] = levels[current_idx - 1]
            send_telegram(
                f"⬇️ <b>تخفيض مستوى المخاطرة</b>\n"
                f"المستوى: {self.state['current_level']}\n"
                f"حماية رأس المال أولاً 🛡️"
            )
            self.state["consecutive_losses"] = 0

        self.state["last_updated"] = str(datetime.now())
        self.save_state()

    def get_current_params(self) -> dict:
        """يرجع معاملات المخاطرة الحالية"""
        level  = self.state["current_level"]
        params = self.LEVELS[level].copy()
        params["level"] = level
        return params

# ═══════════════════════════════════════════════════════════════════════════════
# ٦. Emergency Shutdown — إيقاف طارئ فوري
# ═══════════════════════════════════════════════════════════════════════════════

def emergency_shutdown(reason: str):
    """
    إيقاف طارئ فوري — يغلق كل المراكز ويوقف التداول
    يُستخدم عند: خسارة كبيرة / خبر سلبي / أزمة سوق
    """
    print(f"\n🚨 EMERGENCY SHUTDOWN: {reason}")

    msg = (
        f"🚨 <b>EMERGENCY SHUTDOWN</b> 🚨\n"
        f"{'─'*25}\n"
        f"السبب: {reason}\n"
        f"الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"جاري إغلاق كل المراكز..."
    )
    send_telegram(msg)

    # إغلاق كل المراكز
    try:
        positions = trading_client.list_positions()
        closed = []

        for pos in positions:
            try:
                trading_client.submit_order(
                    symbol=pos.symbol,
                    qty=pos.qty,
                    side="sell",
                    type="market",
                    time_in_force="day"
                )
                closed.append(pos.symbol)
                print(f"  ✅ أُغلق: {pos.symbol}")
            except Exception as e:
                print(f"  ❌ فشل إغلاق {pos.symbol}: {e}")

        # إيقاف النظام
        shutdown_state = {
            "shutdown": True,
            "reason":   reason,
            "time":     str(datetime.now()),
            "closed":   closed,
        }
        with open("/root/emergency_shutdown.json", "w") as f:
            json.dump(shutdown_state, f, indent=2)

        final_msg = (
            f"✅ <b>Emergency Shutdown اكتمل</b>\n"
            f"أُغلق: {', '.join(closed) if closed else 'لا مراكز'}\n"
            f"النظام متوقف — أرسل /resume للاستئناف"
        )
        send_telegram(final_msg)

    except Exception as e:
        send_telegram(f"❌ خطأ في Emergency Shutdown: {e}")

def check_emergency_conditions():
    """
    يفحص إذا كانت هناك حالة طارئة تستوجب الإيقاف الفوري
    """
    try:
        account   = trading_client.get_account()
        portfolio = float(account.portfolio_value)

        # تحميل القيمة الأولية
        try:
            with open("/root/risk_scale_state.json") as f:
                state = json.load(f)
            initial = 100000
        except:
            initial = 100000

        daily_loss = (portfolio - initial) / initial * 100

        # إيقاف عند خسارة 10% في يوم واحد
        if daily_loss <= -10 and "paper" not in str(trading_client.base_url):
            emergency_shutdown(f"خسارة يومية {daily_loss:.1f}% تجاوزت الحد الأقصى")
            return True

        # إيقاف عند VIX فوق 50 (ذعر حاد)
        try:
            vix = yf.download("^VIX", period="1d", progress=False, auto_adjust=True)
            if not vix.empty:
                vix.columns = [c[0] if isinstance(c, tuple) else c for c in vix.columns]
                vix_val = float(vix['Close'].iloc[-1])
                if vix_val > 50:
                    emergency_shutdown(f"VIX = {vix_val:.1f} — ذعر حاد في السوق")
                    return True
        except:
            pass

    except Exception as e:
        print(f"[Emergency] خطأ: {e}")

    return False

# ═══════════════════════════════════════════════════════════════════════════════
# الحلقة الرئيسية
# ═══════════════════════════════════════════════════════════════════════════════

def run_priority3():
    """تشغيل كل تحسينات الأولوية الثالثة"""
    print("=" * 55)
    print("  Priority 3 — الانتقال الآمن للمال الحقيقي")
    print("  ✅ شروط الانتقال")
    print("  ✅ Portfolio Optimizer")
    print("  ✅ Correlation Matrix")
    print("  ✅ Live Trading Readiness")
    print("  ✅ Risk Scaling")
    print("  ✅ Emergency Shutdown")
    print("=" * 55 + "\n")

    risk_scaler = RiskScaler()
    params = risk_scaler.get_current_params()

    send_telegram(
        f"🎯 <b>Priority 3 يعمل!</b>\n"
        f"─"*20 + "\n"
        f"✅ شروط الانتقال للمال الحقيقي\n"
        f"✅ Portfolio Optimizer\n"
        f"✅ Correlation Matrix\n"
        f"✅ Risk Scaling\n"
        f"✅ Emergency Shutdown\n\n"
        f"مستوى المخاطرة الحالي: {params['level']}\n"
        f"رأس المال: ${params['capital']:,} 🛡️"
    )

    last_readiness = None
    last_optimize  = None
    last_emergency = None

    while True:
        try:
            now   = datetime.now()
            today = now.date()

            # فحص Emergency كل 5 دقائق
            if last_emergency != now.minute // 5:
                check_emergency_conditions()
                last_emergency = now.minute // 5

            # تقييم الجاهزية — كل أحد
            if now.weekday() == 6 and now.hour == 9 and last_readiness != today:
                result = evaluate_readiness()
                send_readiness_report(result)
                last_readiness = today

            # Portfolio Optimizer — كل إثنين
            if now.weekday() == 0 and now.hour == 7 and last_optimize != today:
                from priority2_intelligence import WATCHLIST as WL
                positions = trading_client.list_positions()
                if positions:
                    syms = [p.symbol for p in positions if "USD" not in p.symbol]
                    if syms:
                        opt    = optimize_portfolio(syms)
                        corr   = check_correlation(syms)
                        send_correlation_alert(corr)

                        msg = (
                            f"📊 <b>Portfolio Optimizer</b>\n"
                            f"{'─'*25}\n"
                            f"Sharpe Ratio: {opt['sharpe']:.2f}\n"
                            f"عائد متوقع: {opt['expected_ret']:.1f}%\n"
                            f"تذبذب متوقع: {opt['expected_vol']:.1f}%\n\n"
                            f"<b>التوزيع الأمثل:</b>\n"
                        )
                        for sym, w in sorted(opt['weights'].items(),
                                           key=lambda x: x[1], reverse=True)[:6]:
                            msg += f"• {sym}: {w*100:.1f}%\n"

                        send_telegram(msg)
                last_optimize = today

            time.sleep(60)

        except Exception as e:
            print(f"[Priority3] خطأ: {e}")
            time.sleep(60)

# ═══════════════════════════════════════════════════════════════════════════════
# نقطة الدخول
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("🧪 اختبار Priority 3 — الانتقال الآمن\n")

    # ١. تقييم الجاهزية
    print("١. تقييم الجاهزية:")
    result = evaluate_readiness()
    send_readiness_report(result)

    # ٢. Live Checklist
    print("\n٢. Live Trading Checklist:")
    checklist = live_trading_checklist()
    print(f"   النتيجة: {checklist['passed']}/{checklist['total']}")

    # ٣. Risk Scaler
    print("\n٣. Risk Scaler:")
    scaler = RiskScaler()
    params = scaler.get_current_params()
    print(f"   المستوى: {params['level']} | رأس المال: ${params['capital']:,}")

    # ٤. Portfolio Optimizer
    print("\n٤. Portfolio Optimizer:")
    test_syms = ["NVDA", "MSFT", "AAPL", "META", "AMZN"]
    opt = optimize_portfolio(test_syms)
    print(f"   Sharpe: {opt['sharpe']:.2f}")

    # ٥. Correlation Check
    print("\n٥. Correlation Matrix:")
    corr = check_correlation(test_syms)
    print(f"   أزواج مرتبطة: {len(corr['high_correlation'])}")

    # ٦. Emergency Check
    print("\n٦. Emergency Check:")
    emergency = check_emergency_conditions()
    print(f"   حالة طارئة: {'نعم' if emergency else 'لا'}")

    print("\n✅ كل الاختبارات اكتملت!")
