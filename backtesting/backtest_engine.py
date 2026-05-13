"""
Minervini SEPA Backtesting Engine
==================================
يختبر استراتيجية Minervini على بيانات تاريخية حقيقية
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import warnings
warnings.filterwarnings('ignore')

# ─── إعدادات الـ Backtest ────────────────────────────────────────────────────

CONFIG = {
    "start_date":        "2020-01-01",
    "end_date":          "2024-12-31",
    "initial_capital":   100_000,
    "account_risk_pct":  0.0125,    # 1.25% خطر لكل صفقة
    "stop_loss_pct":     0.07,      # 7% Stop Loss
    "take_profit_pct":   0.20,      # 20% هدف أولي
    "trailing_stop_pct": 0.10,      # 10% Trailing Stop
    "min_rr_ratio":      2.0,       # Reward:Risk 2:1
    "max_positions":     6,         # حد أقصى ٦ مراكز متزامنة
    "commission":        0.001,     # 0.1% عمولة
}

WATCHLIST = [
    "NVDA", "MSFT", "AAPL", "GOOGL", "META", "AMZN", "AVGO", "AMD",
    "CRWD", "PANW", "PLTR", "NOW", "DDOG", "SNOW",
    "ADBE", "CRM", "INTU", "NFLX", "TTD",
    "TSLA", "UBER", "V", "MA",
    "LLY", "UNH",
    "COST", "WMT",
]

# ─── تحميل البيانات ────────────────────────────────────────────────────────

def load_data(symbols: list, start: str, end: str) -> dict:
    """تحميل بيانات OHLCV لكل الأسهم"""
    data = {}
    print(f"📥 تحميل بيانات {len(symbols)} سهم...")
    
    for sym in symbols:
        try:
            df = yf.download(sym, start=start, end=end, progress=False)
            if len(df) < 200:
                continue
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
            df.index = pd.to_datetime(df.index)
            data[sym] = df
        except Exception as e:
            print(f"  ⚠️  فشل تحميل {sym}: {e}")
    
    print(f"  ✅ تم تحميل {len(data)} سهم بنجاح\n")
    return data

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """حساب كل المؤشرات المطلوبة"""
    df = df.copy()
    close = df['Close']
    volume = df['Volume']

    # المتوسطات المتحركة
    df['MA10']  = close.rolling(10).mean()
    df['MA20']  = close.rolling(20).mean()
    df['MA50']  = close.rolling(50).mean()
    df['MA150'] = close.rolling(150).mean()
    df['MA200'] = close.rolling(200).mean()

    # اتجاه MA200 (صاعد أم هابط؟)
    df['MA200_slope'] = df['MA200'].diff(20)

    # ATR للحجم الحقيقي
    high_low   = df['High'] - df['Low']
    high_close = (df['High'] - close.shift()).abs()
    low_close  = (df['Low']  - close.shift()).abs()
    df['ATR14'] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1).rolling(14).mean()

    # حجم متوسط
    df['Vol_MA20'] = volume.rolling(20).mean()
    df['Vol_ratio'] = volume / df['Vol_MA20']

    # نسبة من القمة والقاع (52 أسبوع)
    df['High52w'] = close.rolling(252).max()
    df['Low52w']  = close.rolling(252).min()
    df['pct_from_high52'] = (close - df['High52w']) / df['High52w']
    df['pct_from_low52']  = (close - df['Low52w'])  / df['Low52w']

    # Bollinger Bands لاكتشاف VCP
    df['BB_mid']   = close.rolling(20).mean()
    df['BB_std']   = close.rolling(20).std()
    df['BB_upper'] = df['BB_mid'] + 2 * df['BB_std']
    df['BB_lower'] = df['BB_mid'] - 2 * df['BB_std']
    df['BB_width']  = (df['BB_upper'] - df['BB_lower']) / df['BB_mid']

    return df

# ─── نظام الإشارات (Minervini Trend Template) ───────────────────────────────

def check_trend_template(row) -> bool:
    """
    Minervini 8-Point Trend Template
    جميع الشروط يجب أن تتحقق
    """
    try:
        c = row['Close']
        return all([
            c > row['MA50'],           # ١. السعر فوق MA50
            c > row['MA150'],          # ٢. السعر فوق MA150
            c > row['MA200'],          # ٣. السعر فوق MA200
            row['MA50'] > row['MA150'],# ٤. MA50 فوق MA150
            row['MA150'] > row['MA200'],# ٥. MA150 فوق MA200
            row['MA200_slope'] > 0,    # ٦. MA200 صاعد (شهر على الأقل)
            row['pct_from_high52'] >= -0.25,  # ٧. في 25% من القمة السنوية
            row['pct_from_low52']  >= 0.30,   # ٨. 30%+ فوق القاع السنوي
        ])
    except:
        return False

def detect_vcp(df: pd.DataFrame, idx: int, lookback: int = 60) -> dict:
    """
    كشف نمط VCP (Volatility Contraction Pattern)
    يبحث عن تضيقات تدريجية في حجم وتذبذب السعر
    """
    result = {"detected": False, "contractions": 0, "pivot": None, "vol_dry": False}

    if idx < lookback + 10:
        return result

    window = df.iloc[idx - lookback: idx]
    close  = window['Close']
    volume = window['Volume']

    # قسّم النافذة لفترات وابحث عن تضيقات
    n_periods = 4
    period_len = lookback // n_periods
    ranges = []
    vols   = []

    for i in range(n_periods):
        seg = window.iloc[i * period_len: (i + 1) * period_len]
        if len(seg) == 0:
            continue
        price_range = (seg['High'].max() - seg['Low'].min()) / seg['Close'].mean()
        avg_vol     = seg['Volume'].mean()
        ranges.append(price_range)
        vols.append(avg_vol)

    if len(ranges) < 3:
        return result

    # تحقق من التضيق التدريجي
    contractions = sum(
        1 for i in range(1, len(ranges)) if ranges[i] < ranges[i-1] * 0.85
    )

    # جفاف الحجم عند آخر فترة
    vol_dry = vols[-1] < vols[0] * 0.6 if vols[0] > 0 else False

    # نقطة الاختراق (Pivot) = أعلى سعر في آخر ١٥ يوم
    recent = df.iloc[idx - 15: idx]
    pivot  = recent['High'].max()

    result.update({
        "detected":    contractions >= 2 and vol_dry,
        "contractions": contractions,
        "pivot":       pivot,
        "vol_dry":     vol_dry,
    })
    return result

def check_entry_signal(df: pd.DataFrame, idx: int) -> dict:
    """
    فحص إشارة الدخول الكاملة:
    Trend Template ✅ + VCP ✅ + اختراق Pivot بحجم عالٍ ✅
    """
    signal = {"valid": False, "reason": ""}

    if idx < 210:
        return signal

    row  = df.iloc[idx]
    prev = df.iloc[idx - 1]

    # ١. Trend Template
    if not check_trend_template(row):
        signal["reason"] = "trend_template_fail"
        return signal

    # ٢. VCP
    vcp = detect_vcp(df, idx)
    if not vcp["detected"]:
        signal["reason"] = "no_vcp"
        return signal

    # ٣. اختراق Pivot بحجم قوي (50%+ فوق المتوسط)
    pivot = vcp["pivot"]
    broke_pivot   = prev['Close'] <= pivot <= row['Close']
    volume_surge  = row['Vol_ratio'] >= 1.5

    if not broke_pivot:
        signal["reason"] = "no_pivot_breakout"
        return signal

    if not volume_surge:
        signal["reason"] = "low_volume_breakout"
        return signal

    signal.update({
        "valid":        True,
        "pivot":        pivot,
        "vol_ratio":    round(row['Vol_ratio'], 2),
        "contractions": vcp["contractions"],
        "close":        row['Close'],
    })
    return signal

# ─── محرك الـ Backtest الرئيسي ───────────────────────────────────────────────

class MinerviniBacktest:
    def __init__(self, config: dict):
        self.cfg        = config
        self.capital    = config["initial_capital"]
        self.cash       = config["initial_capital"]
        self.positions  = {}   # {symbol: {shares, entry, stop, cost}}
        self.trades     = []   # سجل كل الصفقات
        self.equity_curve = [] # منحنى الرأس المال

    def position_size(self, price: float, stop: float) -> int:
        """حساب حجم المركز بناءً على المخاطرة"""
        risk_per_share = price - stop
        if risk_per_share <= 0:
            return 0
        account_risk   = self.cash * self.cfg["account_risk_pct"]
        shares         = int(account_risk / risk_per_share)
        cost           = shares * price * (1 + self.cfg["commission"])
        # لا تتجاوز 25% من المحفظة في صفقة واحدة
        max_cost = self.cash * 0.25
        if cost > max_cost:
            shares = int(max_cost / (price * (1 + self.cfg["commission"])))
        return max(shares, 0)

    def open_position(self, symbol: str, date, price: float, signal: dict):
        """فتح مركز جديد"""
        if symbol in self.positions:
            return
        if len(self.positions) >= self.cfg["max_positions"]:
            return

        stop   = price * (1 - self.cfg["stop_loss_pct"])
        shares = self.position_size(price, stop)
        if shares == 0:
            return

        cost = shares * price * (1 + self.cfg["commission"])
        if cost > self.cash:
            return

        self.cash -= cost
        self.positions[symbol] = {
            "shares":      shares,
            "entry_price": price,
            "entry_date":  date,
            "stop":        stop,
            "highest":     price,
            "cost":        cost,
        }

    def close_position(self, symbol: str, date, price: float, reason: str):
        """إغلاق مركز وتسجيل الصفقة"""
        if symbol not in self.positions:
            return

        pos     = self.positions.pop(symbol)
        proceeds = pos["shares"] * price * (1 - self.cfg["commission"])
        self.cash += proceeds

        pnl     = proceeds - pos["cost"]
        pnl_pct = (price - pos["entry_price"]) / pos["entry_price"] * 100
        days    = (pd.Timestamp(date) - pd.Timestamp(pos["entry_date"])).days

        self.trades.append({
            "symbol":      symbol,
            "entry_date":  str(pos["entry_date"])[:10],
            "exit_date":   str(date)[:10],
            "entry_price": round(pos["entry_price"], 2),
            "exit_price":  round(price, 2),
            "shares":      pos["shares"],
            "pnl":         round(pnl, 2),
            "pnl_pct":     round(pnl_pct, 2),
            "days_held":   days,
            "reason":      reason,
        })

    def update_stops(self, symbol: str, current_price: float, ma50: float):
        """تحديث Trailing Stop تحت MA50"""
        if symbol not in self.positions:
            return
        pos = self.positions[symbol]

        # تحديث أعلى سعر
        if current_price > pos["highest"]:
            pos["highest"] = current_price

        # Trailing Stop = أعلى من: Stop الأصلي أو تحت MA50 أو 10% من الذروة
        trail_from_high = pos["highest"] * (1 - self.cfg["trailing_stop_pct"])
        trail_from_ma50 = ma50 * 0.98  # 2% تحت MA50

        new_stop = max(pos["stop"], trail_from_high, trail_from_ma50)
        # Stop يتحرك للأعلى فقط
        pos["stop"] = max(pos["stop"], new_stop)

    def portfolio_value(self, prices: dict) -> float:
        """القيمة الإجمالية للمحفظة"""
        val = self.cash
        for sym, pos in self.positions.items():
            val += pos["shares"] * prices.get(sym, pos["entry_price"])
        return val

    def run(self, all_data: dict) -> dict:
        """تشغيل الـ Backtest الرئيسي"""
        print("🚀 بدء الـ Backtest...")

        # حساب المؤشرات لكل سهم
        processed = {}
        for sym, df in all_data.items():
            processed[sym] = compute_indicators(df)

        # إنشاء تقويم تداول موحد
        all_dates = sorted(set().union(*[set(df.index) for df in processed.values()]))
        print(f"📅 عدد أيام التداول: {len(all_dates)}")
        print(f"📊 عدد الأسهم: {len(processed)}\n")

        for date in all_dates:
            prices_today = {}

            # ١. تحديث المراكز الموجودة أولاً
            for sym in list(self.positions.keys()):
                if sym not in processed or date not in processed[sym].index:
                    continue
                row   = processed[sym].loc[date]
                price = float(row['Close'])
                ma50  = float(row['MA50']) if not pd.isna(row['MA50']) else price
                prices_today[sym] = price

                # تحديث Trailing Stop
                self.update_stops(sym, price, ma50)
                pos = self.positions[sym]

                # فحص Stop Loss
                low = float(row['Low'])
                if low <= pos["stop"]:
                    exit_price = min(price, pos["stop"])
                    self.close_position(sym, date, exit_price, "stop_loss")
                    continue

                # فحص Take Profit (جزئي عند 20%)
                pnl_pct = (price - pos["entry_price"]) / pos["entry_price"]
                if pnl_pct >= self.cfg["take_profit_pct"]:
                    # لا نغلق كاملاً، نرفع Stop فقط
                    pos["stop"] = max(pos["stop"], pos["entry_price"] * 1.05)

            # ٢. البحث عن إشارات جديدة
            if len(self.positions) < self.cfg["max_positions"]:
                for sym, df in processed.items():
                    if sym in self.positions:
                        continue
                    if date not in df.index:
                        continue

                    idx = df.index.get_loc(date)
                    if idx < 210:
                        continue

                    signal = check_entry_signal(df, idx)
                    if signal["valid"]:
                        price = float(df.loc[date, 'Close'])
                        self.open_position(sym, date, price, signal)
                        prices_today[sym] = price

            # ٣. تسجيل منحنى الرأس المال
            pv = self.portfolio_value(prices_today)
            self.equity_curve.append({
                "date":            str(date)[:10],
                "portfolio_value": round(pv, 2),
                "cash":            round(self.cash, 2),
                "open_positions":  len(self.positions),
            })

        # إغلاق كل المراكز المفتوحة في نهاية الـ Backtest
        last_date = all_dates[-1]
        for sym in list(self.positions.keys()):
            if sym in processed and last_date in processed[sym].index:
                price = float(processed[sym].loc[last_date, 'Close'])
                self.close_position(sym, last_date, price, "end_of_test")

        return self._compile_results()

    def _compile_results(self) -> dict:
        """تجميع النتائج النهائية"""
        if not self.trades:
            return {"error": "لا توجد صفقات"}

        trades_df = pd.DataFrame(self.trades)
        equity_df = pd.DataFrame(self.equity_curve)

        # ─ إحصائيات أساسية ─
        total_trades = len(trades_df)
        winners      = trades_df[trades_df['pnl'] > 0]
        losers       = trades_df[trades_df['pnl'] <= 0]
        win_rate     = len(winners) / total_trades * 100

        avg_win  = winners['pnl_pct'].mean() if len(winners) else 0
        avg_loss = losers['pnl_pct'].mean()  if len(losers)  else 0
        rr_ratio = abs(avg_win / avg_loss)    if avg_loss != 0 else 0

        # ─ أداء المحفظة ─
        initial = self.cfg["initial_capital"]
        final   = equity_df['portfolio_value'].iloc[-1]
        total_return = (final - initial) / initial * 100

        # ─ Sharpe Ratio ─
        equity_df['returns'] = equity_df['portfolio_value'].pct_change()
        daily_mean = equity_df['returns'].mean()
        daily_std  = equity_df['returns'].std()
        sharpe     = (daily_mean / daily_std * np.sqrt(252)) if daily_std > 0 else 0

        # ─ Max Drawdown ─
        rolling_max = equity_df['portfolio_value'].cummax()
        drawdown    = (equity_df['portfolio_value'] - rolling_max) / rolling_max * 100
        max_dd      = drawdown.min()

        # ─ Profit Factor ─
        gross_profit = winners['pnl'].sum() if len(winners) else 0
        gross_loss   = abs(losers['pnl'].sum()) if len(losers) else 1
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # ─ مقارنة بـ S&P 500 ─
        spy_return = self._get_benchmark_return()

        return {
            "summary": {
                "period":         f"{self.cfg['start_date']} → {self.cfg['end_date']}",
                "initial_capital": f"${initial:,.0f}",
                "final_capital":   f"${final:,.0f}",
                "total_return":    f"{total_return:.1f}%",
                "spy_return":      f"{spy_return:.1f}%",
                "alpha":           f"{total_return - spy_return:.1f}%",
                "sharpe_ratio":    round(sharpe, 2),
                "max_drawdown":    f"{max_dd:.1f}%",
                "profit_factor":   round(profit_factor, 2),
            },
            "trades": {
                "total":           total_trades,
                "winners":         len(winners),
                "losers":          len(losers),
                "win_rate":        f"{win_rate:.1f}%",
                "avg_win":         f"{avg_win:.1f}%",
                "avg_loss":        f"{avg_loss:.1f}%",
                "rr_ratio":        round(rr_ratio, 2),
                "avg_holding_days": round(trades_df['days_held'].mean(), 1),
                "best_trade":      f"{trades_df['pnl_pct'].max():.1f}%",
                "worst_trade":     f"{trades_df['pnl_pct'].min():.1f}%",
            },
            "exit_reasons": trades_df['reason'].value_counts().to_dict(),
            "top_trades":   trades_df.nlargest(5, 'pnl')[
                ['symbol','entry_date','exit_date','pnl_pct','days_held','reason']
            ].to_dict('records'),
            "raw_trades":      self.trades,
            "equity_curve":    self.equity_curve,
        }

    def _get_benchmark_return(self) -> float:
        try:
            spy = yf.download("SPY",
                              start=self.cfg["start_date"],
                              end=self.cfg["end_date"],
                              progress=False)
            if len(spy) > 0:
                spy.columns = [c[0] if isinstance(c, tuple) else c for c in spy.columns]
                return (spy['Close'].iloc[-1] - spy['Close'].iloc[0]) / spy['Close'].iloc[0] * 100
        except:
            pass
        return 0.0

# ─── نقطة الدخول ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  Minervini SEPA Backtesting Engine")
    print("=" * 60)

    # تحميل البيانات
    data = load_data(WATCHLIST, CONFIG["start_date"], CONFIG["end_date"])

    # تشغيل الـ Backtest
    bt = MinerviniBacktest(CONFIG)
    results = bt.run(data)

    # حفظ النتائج
    with open("backtest_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # طباعة الملخص
    print("\n" + "=" * 60)
    print("  📊 نتائج الـ Backtest")
    print("=" * 60)

    s = results.get("summary", {})
    t = results.get("trades",  {})

    print(f"\n  💰 الأداء العام:")
    print(f"     الفترة:          {s.get('period')}")
    print(f"     رأس المال الأولي: {s.get('initial_capital')}")
    print(f"     رأس المال النهائي:{s.get('final_capital')}")
    print(f"     العائد الكلي:     {s.get('total_return')}")
    print(f"     عائد S&P 500:    {s.get('spy_return')}")
    print(f"     Alpha:           {s.get('alpha')}")

    print(f"\n  📈 جودة الأداء:")
    print(f"     Sharpe Ratio:    {s.get('sharpe_ratio')}")
    print(f"     Max Drawdown:    {s.get('max_drawdown')}")
    print(f"     Profit Factor:   {s.get('profit_factor')}")

    print(f"\n  🎯 إحصائيات الصفقات:")
    print(f"     إجمالي الصفقات:  {t.get('total')}")
    print(f"     Win Rate:        {t.get('win_rate')}")
    print(f"     متوسط الربح:     {t.get('avg_win')}")
    print(f"     متوسط الخسارة:   {t.get('avg_loss')}")
    print(f"     R:R Ratio:       {t.get('rr_ratio')}")
    print(f"     متوسط مدة الصفقة:{t.get('avg_holding_days')} يوم")
    print(f"     أفضل صفقة:       {t.get('best_trade')}")
    print(f"     أسوأ صفقة:       {t.get('worst_trade')}")

    print(f"\n  🏆 أفضل ٥ صفقات:")
    for tr in results.get("top_trades", []):
        print(f"     {tr['symbol']:6} | {tr['entry_date']} → {tr['exit_date']} | {tr['pnl_pct']:+.1f}% | {tr['days_held']} يوم")

    print(f"\n  📤 أسباب الخروج:")
    for reason, count in results.get("exit_reasons", {}).items():
        print(f"     {reason:20} : {count}")

    print(f"\n  💾 تم حفظ النتائج في: backtest_results.json")
    print("=" * 60)
